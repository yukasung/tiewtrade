from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol, TypeVar

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.candle_pipeline import (
    CandlePipelineInputError,
    CandlePipelineSinkError,
    CompletedCandlePipeline,
)
from tiewtrade.market_data.candle_pipeline import (
    MarketDataCandleSink as MarketDataCandleSink,
)
from tiewtrade.market_data.candle_source import MarketDataCandleSource
from tiewtrade.market_data.completed_candle_stream import (
    CandleAcceptance,
    CandleGapError,
)
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime_logging import MarketDataRuntimeLog
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeSnapshot,
    MarketDataRuntimeState,
    MarketDataRuntimeStatus,
)
from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    MarketDataTimeoutError,
)

_T = TypeVar("_T")
_WARM_UP_TIMEOUT_SECONDS = 30.0
_BACKFILL_TIMEOUT_SECONDS = 30.0
_STALE_GRACE = timedelta(seconds=30)
_RECONNECT_DELAYS_SECONDS = (1.0, 2.0, 4.0)
_RATE_LIMIT_FALLBACK_SECONDS = 60.0
_LOGGER = logging.getLogger("tiewtrade.market_data.runtime")


class _WarmUpSourceError(Exception):
    pass


class _WarmUpSinkError(Exception):
    pass


class RuntimeScheduler(Protocol):
    def now(self) -> datetime: ...

    async def sleep(self, seconds: float) -> None: ...

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T: ...


class AsyncioRuntimeScheduler:
    def now(self) -> datetime:
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        return await asyncio.wait_for(awaitable, timeout)


class MarketDataRuntime:
    def __init__(
        self,
        *,
        config: MarketDataConfig,
        warm_up_count: int,
        source: MarketDataCandleSource,
        sink: MarketDataCandleSink,
        scheduler: RuntimeScheduler | None = None,
        on_transition: Callable[[MarketDataRuntimeSnapshot], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if warm_up_count <= 0:
            raise ValueError("warm_up_count must be positive")

        self._config = config
        self._warm_up_count = warm_up_count
        self._source = source
        self._scheduler = scheduler or AsyncioRuntimeScheduler()
        self._status = MarketDataRuntimeStatus(
            self._scheduler.now,
            on_transition=on_transition,
        )
        self._runtime_log = MarketDataRuntimeLog(
            logger or _LOGGER,
            symbol=config.symbol,
            timeframe=config.timeframe,
        )
        self._pipeline = CompletedCandlePipeline(
            config=config,
            sink=sink,
            on_delivery=self._status.record_delivery,
        )
        self._run_task: asyncio.Task[None] | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._stop_requested = False
        self._source_close_lock = asyncio.Lock()
        self._source_closed = False

    @property
    def snapshot(self) -> MarketDataRuntimeSnapshot:
        return self._status.snapshot

    async def run(self) -> None:
        if self._status.snapshot.state in {
            MarketDataRuntimeState.FAILED_CLOSED,
            MarketDataRuntimeState.STOPPED,
        }:
            return
        current_task = asyncio.current_task()
        if current_task is None:
            raise RuntimeError("runtime requires an asyncio task")
        if self._run_task is not None:
            raise RuntimeError("runtime is already running")
        self._run_task = current_task

        try:
            if not await self._warm_up():
                return
            await self._consume_live()
        except asyncio.CancelledError:
            if not self._stop_requested:
                self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
                raise
        finally:
            try:
                if (
                    not self._stop_requested
                    and self._status.snapshot.state
                    is MarketDataRuntimeState.FAILED_CLOSED
                ):
                    primary_reason = self._status.snapshot.reason
                    try:
                        await self._close_source_once()
                    except Exception:
                        self._fail_closed(primary_reason)
            finally:
                self._run_task = None

    async def stop(self) -> None:
        self._stop_requested = True
        if self._shutdown_task is None or self._shutdown_failed():
            self._shutdown_task = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._shutdown_task)

    async def _shutdown(self) -> None:
        run_task = self._run_task
        if run_task is not None and not run_task.done():
            run_task.cancel()

        close_error: Exception | None = None
        try:
            await self._close_source_once()
        except Exception as error:
            close_error = error
            if self._status.snapshot.state is not MarketDataRuntimeState.FAILED_CLOSED:
                self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)

        if run_task is not None:
            await asyncio.gather(run_task, return_exceptions=True)

        if close_error is not None:
            raise close_error
        self._transition_to_stopped()

    def _shutdown_failed(self) -> bool:
        assert self._shutdown_task is not None
        return (
            self._shutdown_task.done()
            and not self._shutdown_task.cancelled()
            and self._shutdown_task.exception() is not None
        )

    async def _warm_up(self) -> bool:
        self._transition(
            MarketDataRuntimeState.WARMING_UP,
            MarketDataRuntimeReason.START_REQUESTED,
        )
        completed_before = self._scheduler.now()
        try:
            await self._perform_warm_up(completed_before)
        except MarketDataFatalError:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
            return False
        except MarketDataRateLimitError:
            self._fail_closed(MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED)
            return False
        except _WarmUpSinkError:
            self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
            return False
        except (MarketDataTimeoutError, TimeoutError):
            self._fail_closed(MarketDataRuntimeReason.WARM_UP_TIMEOUT)
            return False
        except (MarketDataRetryableError, _WarmUpSourceError):
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
            return False

        self._transition(
            MarketDataRuntimeState.LIVE,
            MarketDataRuntimeReason.WARM_UP_COMPLETED,
        )
        return True

    async def _perform_warm_up(self, completed_before: datetime) -> None:
        try:
            candles = await self._run_source_operation(
                lambda: self._source.load_recent(
                    self._config,
                    count=self._warm_up_count,
                    completed_before=completed_before,
                ),
                timeout=_WARM_UP_TIMEOUT_SECONDS,
            )
        except (
            MarketDataFatalError,
            MarketDataRateLimitError,
            MarketDataRetryableError,
            TimeoutError,
        ):
            raise
        except Exception as error:
            raise _WarmUpSourceError from error

        try:
            await self._scheduler.wait_for(
                self._pipeline.warm_up(
                    candles,
                    expected_count=self._warm_up_count,
                    received_at=completed_before,
                ),
                _WARM_UP_TIMEOUT_SECONDS,
            )
        except CandlePipelineInputError as error:
            raise _WarmUpSourceError from error
        except CandlePipelineSinkError as error:
            raise _WarmUpSinkError from error

    async def _consume_live(self) -> None:
        try:
            stream = self._source.stream_completed(self._config)
        except MarketDataFatalError:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
            return
        except MarketDataRateLimitError as error:
            recovered_stream = await self._recover_stream(
                MarketDataRuntimeReason.RATE_LIMITED,
                pending_rate_limit=error,
            )
            if recovered_stream is None:
                return
            stream = recovered_stream
        except Exception:
            recovered_stream = await self._recover_stream(
                MarketDataRuntimeReason.SOURCE_DISCONNECTED
            )
            if recovered_stream is None:
                return
            stream = recovered_stream
        while not self._stop_requested:
            disconnect_reason: MarketDataRuntimeReason
            try:
                candle = await self._next_before_stale(stream)
            except TimeoutError:
                disconnect_reason = MarketDataRuntimeReason.DATA_STALE
            except MarketDataFatalError:
                self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
                return
            except MarketDataRateLimitError as error:
                recovered_stream = await self._recover_stream(
                    MarketDataRuntimeReason.RATE_LIMITED,
                    pending_rate_limit=error,
                )
                if recovered_stream is None:
                    return
                stream = recovered_stream
                continue
            except Exception:
                disconnect_reason = MarketDataRuntimeReason.SOURCE_DISCONNECTED
            else:
                if not await self._accept_live_candle(candle):
                    return
                continue

            recovered_stream = await self._recover_stream(disconnect_reason)
            if recovered_stream is None:
                return
            stream = recovered_stream

    async def _next_before_stale(
        self,
        stream: AsyncIterator[Candle],
    ) -> Candle:
        timeout = self._seconds_until(self._freshness_deadline())
        return await self._scheduler.wait_for(stream.__anext__(), timeout)

    async def _next_reconnect_candle(
        self,
        stream: AsyncIterator[Candle],
    ) -> Candle:
        now = self._scheduler.now()
        next_boundary = (
            _latest_completed_boundary(now, interval=self._config.interval)
            + self._config.interval
        )
        timeout = self._seconds_until(next_boundary + _STALE_GRACE)
        return await self._scheduler.wait_for(stream.__anext__(), timeout)

    def _seconds_until(self, deadline: datetime) -> float:
        return max(
            0.0,
            (deadline - self._scheduler.now()).total_seconds(),
        )

    def _freshness_deadline(self) -> datetime:
        last_accepted_open_time = self._status.snapshot.last_accepted_open_time
        if last_accepted_open_time is None:
            raise RuntimeError("freshness requires an accepted candle")
        expected_open_time = last_accepted_open_time + self._config.interval
        expected_close_boundary = expected_open_time + self._config.interval
        return expected_close_boundary + _STALE_GRACE

    async def _accept_live_candle(self, candle: Candle) -> bool:
        received_at = self._scheduler.now()
        try:
            decision = await self._pipeline.process_live(
                candle,
                received_at=received_at,
            )
        except CandleGapError:
            return await self._backfill_through(candle, received_at=received_at)
        except CandlePipelineInputError:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
            return False
        except CandlePipelineSinkError:
            self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
            return False
        if decision is not CandleAcceptance.ACCEPTED:
            self._runtime_log.candle_discarded(
                open_time=candle.open_time,
                received_at=received_at,
                discard_reason=decision,
            )
            if decision is CandleAcceptance.NOT_CLOSED:
                self._runtime_log.clock_skew_detected(
                    open_time=candle.open_time,
                    close_time=candle.close_time,
                    received_at=received_at,
                )
            return True

        self._transition(
            MarketDataRuntimeState.LIVE,
            MarketDataRuntimeReason.LIVE_CANDLE_ACCEPTED,
        )
        return True

    async def _backfill_through(
        self,
        observed: Candle,
        *,
        received_at: datetime,
    ) -> bool:
        return await self._backfill_to_boundary(
            observed.open_time + self._config.interval,
            received_at=received_at,
            observed=observed,
        )

    async def _backfill_to_boundary(
        self,
        end: datetime,
        *,
        received_at: datetime,
        observed: Candle,
    ) -> bool:
        last_accepted_open_time = self._status.snapshot.last_accepted_open_time
        if last_accepted_open_time is None:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
            return False

        start = last_accepted_open_time + self._config.interval
        self._transition(
            MarketDataRuntimeState.BACKFILLING,
            MarketDataRuntimeReason.GAP_DETECTED,
        )
        candles: tuple[Candle, ...] = ()
        if start < end:
            try:
                candles = await self._run_source_operation(
                    lambda: self._source.load_range(
                        self._config,
                        start=start,
                        end=end,
                    ),
                    timeout=_BACKFILL_TIMEOUT_SECONDS,
                )
            except MarketDataFatalError:
                self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
                return False
            except MarketDataRateLimitError:
                self._fail_closed(MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED)
                return False
            except (MarketDataRetryableError, TimeoutError):
                self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
                return False
            except Exception:
                self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
                return False

        def publish_backfill_ready() -> None:
            self._transition(
                MarketDataRuntimeState.LIVE,
                MarketDataRuntimeReason.BACKFILL_COMPLETED,
            )

        try:
            await self._pipeline.process_backfill(
                candles,
                start=start,
                end=end,
                observed=observed,
                received_at=received_at,
                on_ready_for_delivery=publish_backfill_ready,
            )
        except CandlePipelineInputError:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
            return False
        except CandlePipelineSinkError:
            self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
            return False
        return True

    async def _recover_stream(
        self,
        reason: MarketDataRuntimeReason,
        *,
        pending_rate_limit: MarketDataRateLimitError | None = None,
    ) -> AsyncIterator[Candle] | None:
        if pending_rate_limit is None:
            if reason is MarketDataRuntimeReason.DATA_STALE:
                self._runtime_log.stale_detected(
                    reason=reason,
                    last_accepted_open_time=(
                        self._status.snapshot.last_accepted_open_time
                    ),
                )
            self._transition(MarketDataRuntimeState.STALE, reason)
        for attempt, reconnect_delay in enumerate(
            _RECONNECT_DELAYS_SECONDS,
            start=1,
        ):
            if pending_rate_limit is None:
                attempt_delay = reconnect_delay
                await self._scheduler.sleep(attempt_delay)
                self._transition(MarketDataRuntimeState.RECONNECTING, reason)
            else:
                if (
                    self._status.snapshot.state
                    is not MarketDataRuntimeState.RATE_LIMITED
                ):
                    self._transition(
                        MarketDataRuntimeState.RATE_LIMITED,
                        MarketDataRuntimeReason.RATE_LIMITED,
                    )
                attempt_delay = self._retry_after_seconds(pending_rate_limit)
                await self._scheduler.sleep(attempt_delay)
                self._transition(MarketDataRuntimeState.RECONNECTING, reason)
            if self._stop_requested:
                return None
            self._runtime_log.reconnect_attempted(
                attempt=attempt,
                delay_seconds=attempt_delay,
                reason=reason,
            )
            try:
                stream = self._source.stream_completed(self._config)
                observed = await self._next_reconnect_candle(stream)
            except MarketDataFatalError:
                self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
                return None
            except MarketDataRateLimitError as error:
                pending_rate_limit = error
                self._transition(
                    MarketDataRuntimeState.RATE_LIMITED,
                    MarketDataRuntimeReason.RATE_LIMITED,
                )
                continue
            except Exception:
                pending_rate_limit = None
                continue

            received_at = self._scheduler.now()
            latest_boundary = _latest_completed_boundary(
                received_at,
                interval=self._config.interval,
            )
            end = max(
                observed.open_time + self._config.interval,
                latest_boundary,
            )
            if not await self._backfill_to_boundary(
                end,
                received_at=received_at,
                observed=observed,
            ):
                return None
            return stream

        exhausted_reason = (
            MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED
            if pending_rate_limit is not None
            else MarketDataRuntimeReason.RECONNECT_EXHAUSTED
        )
        self._fail_closed(exhausted_reason)
        return None

    def _retry_after_seconds(self, error: MarketDataRateLimitError) -> float:
        retry_after = error.retry_after
        if isinstance(retry_after, timedelta):
            return max(0.0, retry_after.total_seconds())
        if isinstance(retry_after, datetime):
            return max(
                0.0,
                (retry_after - self._scheduler.now()).total_seconds(),
            )
        return _RATE_LIMIT_FALLBACK_SECONDS

    async def _run_source_operation(
        self,
        operation: Callable[[], Awaitable[_T]],
        *,
        timeout: float,
    ) -> _T:
        last_error: Exception | None = None
        for attempt in range(len(_RECONNECT_DELAYS_SECONDS) + 1):
            try:
                return await self._scheduler.wait_for(operation(), timeout)
            except MarketDataFatalError:
                raise
            except MarketDataRateLimitError as error:
                last_error = error
                self._transition(
                    MarketDataRuntimeState.RATE_LIMITED,
                    MarketDataRuntimeReason.RATE_LIMITED,
                )
                if attempt == len(_RECONNECT_DELAYS_SECONDS):
                    raise
                await self._scheduler.sleep(self._retry_after_seconds(error))
                self._transition(
                    MarketDataRuntimeState.RECONNECTING,
                    MarketDataRuntimeReason.RATE_LIMITED,
                )
            except (MarketDataRetryableError, TimeoutError) as error:
                last_error = error
                if attempt == len(_RECONNECT_DELAYS_SECONDS):
                    raise
                await self._scheduler.sleep(_RECONNECT_DELAYS_SECONDS[attempt])
        if last_error is None:
            raise RuntimeError("source retry loop did not execute")
        raise last_error

    async def _close_source_once(self) -> None:
        async with self._source_close_lock:
            if self._source_closed:
                return
            await self._source.close()
            self._source_closed = True

    def _fail_closed(self, reason: MarketDataRuntimeReason) -> None:
        self._transition(MarketDataRuntimeState.FAILED_CLOSED, reason)

    def _transition_to_stopped(self) -> None:
        if self._status.snapshot.state in {
            MarketDataRuntimeState.FAILED_CLOSED,
            MarketDataRuntimeState.STOPPED,
        }:
            return
        self._transition(
            MarketDataRuntimeState.STOPPED,
            MarketDataRuntimeReason.STOP_REQUESTED,
        )

    def _transition(
        self,
        state: MarketDataRuntimeState,
        reason: MarketDataRuntimeReason,
    ) -> None:
        self._status.transition(state, reason)


def _latest_completed_boundary(value: datetime, *, interval: timedelta) -> datetime:
    interval_seconds = int(interval.total_seconds())
    boundary_timestamp = int(value.timestamp()) // interval_seconds * interval_seconds
    return datetime.fromtimestamp(boundary_timestamp, UTC)
