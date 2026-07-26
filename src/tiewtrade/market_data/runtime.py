from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.candle_source import MarketDataCandleSource
from tiewtrade.market_data.completed_candle_stream import CompletedCandleStream
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeSnapshot,
    MarketDataRuntimeState,
)

_T = TypeVar("_T")
_WARM_UP_TIMEOUT_SECONDS = 30.0


class _WarmUpSourceError(Exception):
    pass


class _WarmUpSinkError(Exception):
    pass


class MarketDataCandleSink(Protocol):
    async def warm_up(
        self, candles: tuple[Candle, ...], *, received_at: datetime
    ) -> None: ...

    async def process_completed(
        self, candle: Candle, *, received_at: datetime
    ) -> None: ...


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
    ) -> None:
        if warm_up_count <= 0:
            raise ValueError("warm_up_count must be positive")

        self._config = config
        self._warm_up_count = warm_up_count
        self._source = source
        self._sink = sink
        self._scheduler = scheduler or AsyncioRuntimeScheduler()
        self._candles = CompletedCandleStream(config)
        self._last_accepted_open_time: datetime | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._stop_requested = False
        self._source_close_lock = asyncio.Lock()
        self._source_closed = False

        self._snapshot = MarketDataRuntimeSnapshot(
            state=MarketDataRuntimeState.STARTING,
            reason=MarketDataRuntimeReason.START_REQUESTED,
            transitioned_at=self._scheduler.now(),
            last_accepted_open_time=None,
        )
        self._visited_states = [MarketDataRuntimeState.STARTING]

    @property
    def snapshot(self) -> MarketDataRuntimeSnapshot:
        return self._snapshot

    @property
    def visited_states(self) -> tuple[MarketDataRuntimeState, ...]:
        return tuple(self._visited_states)

    async def run(self) -> None:
        if self._snapshot.state in {
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
                    and self._snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
                ):
                    try:
                        await self._close_source_once()
                    except Exception:
                        self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
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
            await self._scheduler.wait_for(
                self._perform_warm_up(completed_before),
                _WARM_UP_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            self._fail_closed(MarketDataRuntimeReason.WARM_UP_TIMEOUT)
            return False
        except _WarmUpSinkError:
            self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
            return False
        except _WarmUpSourceError:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
            return False

        self._transition(
            MarketDataRuntimeState.LIVE,
            MarketDataRuntimeReason.WARM_UP_COMPLETED,
        )
        return True

    async def _perform_warm_up(self, completed_before: datetime) -> None:
        try:
            candles = await self._source.load_recent(
                self._config,
                count=self._warm_up_count,
                completed_before=completed_before,
            )
            if len(candles) < self._warm_up_count:
                raise ValueError("insufficient warm-up candles")
            for candle in candles:
                if not self._candles.accept(candle, completed_before):
                    raise ValueError("warm-up requires new completed candles")
                self._last_accepted_open_time = candle.open_time
        except Exception as error:
            raise _WarmUpSourceError from error

        try:
            await self._sink.warm_up(candles, received_at=completed_before)
        except Exception as error:
            raise _WarmUpSinkError from error

    async def _consume_live(self) -> None:
        try:
            async for candle in self._source.stream_completed(self._config):
                if self._stop_requested:
                    return
                received_at = self._scheduler.now()
                try:
                    accepted = self._candles.accept(candle, received_at)
                except ValueError:
                    self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
                    return
                if not accepted:
                    continue

                self._last_accepted_open_time = candle.open_time
                try:
                    await self._sink.process_completed(
                        candle,
                        received_at=received_at,
                    )
                except Exception:
                    self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
                    return
                self._transition(
                    MarketDataRuntimeState.LIVE,
                    MarketDataRuntimeReason.LIVE_CANDLE_ACCEPTED,
                )
        except Exception:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
            return

        if not self._stop_requested:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)

    async def _close_source_once(self) -> None:
        async with self._source_close_lock:
            if self._source_closed:
                return
            await self._source.close()
            self._source_closed = True

    def _fail_closed(self, reason: MarketDataRuntimeReason) -> None:
        self._transition(MarketDataRuntimeState.FAILED_CLOSED, reason)

    def _transition_to_stopped(self) -> None:
        if self._snapshot.state in {
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
        self._snapshot = MarketDataRuntimeSnapshot(
            state=state,
            reason=reason,
            transitioned_at=self._scheduler.now(),
            last_accepted_open_time=self._last_accepted_open_time,
        )
        self._visited_states.append(state)
