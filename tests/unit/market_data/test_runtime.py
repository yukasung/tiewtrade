from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Coroutine, Iterable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypeVar, cast

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.candle_pipeline import (
    MarketDataCandleSink as PipelineMarketDataCandleSink,
)
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime import MarketDataCandleSink, MarketDataRuntime
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeSnapshot,
    MarketDataRuntimeState,
)
from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
)

_NOW = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)
_T = TypeVar("_T")
_RATE_LIMIT_EXHAUSTION_STATES = (
    MarketDataRuntimeState.RATE_LIMITED,
    MarketDataRuntimeState.RECONNECTING,
    MarketDataRuntimeState.RATE_LIMITED,
    MarketDataRuntimeState.RECONNECTING,
    MarketDataRuntimeState.RATE_LIMITED,
    MarketDataRuntimeState.RECONNECTING,
    MarketDataRuntimeState.RATE_LIMITED,
    MarketDataRuntimeState.FAILED_CLOSED,
)


def candle_at(minute: int, *, symbol: str = "BTCUSDT") -> Candle:
    return Candle(
        symbol=symbol,
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("10"),
    )


def warm_up_candles() -> tuple[Candle, ...]:
    return (candle_at(0), candle_at(5), candle_at(10))


class FakeScheduler:
    def __init__(self, *, now: datetime = _NOW) -> None:
        self._now = now
        self.timeouts: list[float] = []
        self.sleeps: list[float] = []
        self.wait_for_active = False

    def now(self) -> datetime:
        return self._now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self._now += timedelta(seconds=seconds)

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        self.wait_for_active = True
        try:
            return await awaitable
        finally:
            self.wait_for_active = False


class TimeoutAfterWarmUpScheduler(FakeScheduler):
    def __init__(self, *, now: datetime) -> None:
        super().__init__(now=now)
        self._warm_up_wait_count = 0

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        self._warm_up_wait_count += 1
        if self._warm_up_wait_count <= 2:
            return await awaitable

        task = asyncio.ensure_future(awaitable)
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self._now += timedelta(seconds=timeout)
        raise TimeoutError


class RecoveringAfterStaleScheduler(FakeScheduler):
    def __init__(self, *, now: datetime) -> None:
        super().__init__(now=now)
        self._wait_count = 0

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        self._wait_count += 1
        if self._wait_count <= 2:
            return await awaitable
        if self._wait_count == 3 or timeout <= 0:
            task = asyncio.ensure_future(awaitable)
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self._now += timedelta(seconds=timeout)
            raise TimeoutError
        return await awaitable


class TimeoutScheduler(FakeScheduler):
    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        if isinstance(awaitable, Coroutine):
            awaitable.close()
        raise TimeoutError


class PipelineWarmUpTimeoutScheduler(FakeScheduler):
    def __init__(self) -> None:
        super().__init__()
        self._wait_count = 0

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        self._wait_count += 1
        if self._wait_count == 1:
            return await awaitable
        if isinstance(awaitable, Coroutine):
            awaitable.close()
        raise TimeoutError


class BackfillTimeoutScheduler(FakeScheduler):
    def __init__(self) -> None:
        super().__init__()
        self._wait_count = 0

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        self._wait_count += 1
        if self._wait_count <= 3:
            return await awaitable
        if isinstance(awaitable, Coroutine):
            awaitable.close()
        raise TimeoutError


class BlockingReconnectScheduler(FakeScheduler):
    def __init__(self) -> None:
        super().__init__()
        self.sleep_started = asyncio.Event()
        self.sleep_finished = asyncio.Event()

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.sleep_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.sleep_finished.set()


class FakeSource:
    def __init__(
        self,
        *,
        recent: Iterable[Candle] = (),
        live: Iterable[Candle] = (),
        ranges: dict[tuple[datetime, datetime], Iterable[Candle]] | None = None,
    ) -> None:
        self._recent = tuple(recent)
        self._live = tuple(live)
        self._ranges = {
            requested_range: tuple(candles)
            for requested_range, candles in (ranges or {}).items()
        }
        self._closed = asyncio.Event()
        self.recent_requests: list[tuple[MarketDataConfig, int, datetime]] = []
        self.range_requests: list[tuple[MarketDataConfig, datetime, datetime]] = []
        self.live_started = False
        self.close_count = 0

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.recent_requests.append((config, count, completed_before))
        return self._recent

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        self.range_requests.append((config, start, end))
        return self._ranges.get((start, end), ())

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed()

    async def close(self) -> None:
        if self._closed.is_set():
            return
        self.close_count += 1
        self._closed.set()

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.live_started = True
        for candle in self._live:
            yield candle
        await self._closed.wait()


class WarmUpFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(recent=warm_up_candles(), live=[candle_at(15)])
        self._failures = iter(failures)
        self.load_count = 0

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.load_count += 1
        try:
            error = next(self._failures)
        except StopIteration:
            return await super().load_recent(
                config,
                count=count,
                completed_before=completed_before,
            )
        raise error


class StreamFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(recent=warm_up_candles())
        self._failures = iter(failures)
        self.stream_count = 0

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        self.stream_count += 1
        try:
            error = next(self._failures)
        except StopIteration:
            return self._stream_completed()
        raise error


class AsyncIteratorFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(recent=warm_up_candles())
        self._failures = iter(failures)
        self.stream_count = 0

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        self.stream_count += 1
        try:
            error = next(self._failures)
        except StopIteration:
            return self._stream_completed()
        return self._raise_on_next(error)

    async def _raise_on_next(self, error: Exception) -> AsyncIterator[Candle]:
        raise error
        if False:
            yield candle_at(15)


class BackfillFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(
            recent=warm_up_candles(),
            live=[candle_at(20)],
            ranges={
                (candle_at(15).open_time, candle_at(25).open_time): (
                    candle_at(15),
                    candle_at(20),
                )
            },
        )
        self._failures = iter(failures)
        self.load_count = 0

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        self.load_count += 1
        try:
            error = next(self._failures)
        except StopIteration:
            return await super().load_range(config, start=start, end=end)
        raise error


class DeadlineAwareBackfillSource(FakeSource):
    def __init__(self, scheduler: FakeScheduler) -> None:
        super().__init__(
            recent=warm_up_candles(),
            live=[candle_at(20)],
            ranges={
                (candle_at(15).open_time, candle_at(25).open_time): (
                    candle_at(15),
                    candle_at(20),
                )
            },
        )
        self._scheduler = scheduler
        self.backfill_within_deadline = False

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        self.backfill_within_deadline = self._scheduler.wait_for_active
        return await super().load_range(config, start=start, end=end)


class BlockingWarmUpSource(FakeSource):
    def __init__(self) -> None:
        super().__init__()
        self.load_started = asyncio.Event()

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.load_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class NoneWarmUpSource(FakeSource):
    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.recent_requests.append((config, count, completed_before))
        return None  # type: ignore[return-value]


class ExplodingWarmUpBatch:
    def __len__(self) -> int:
        raise RuntimeError("warm-up batch validation failed")


class ExplodingWarmUpSource(FakeSource):
    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.recent_requests.append((config, count, completed_before))
        return cast(tuple[Candle, ...], ExplodingWarmUpBatch())


class ExplodingValidationCandle:
    def __init__(self, error: Exception) -> None:
        self._error = error

    @property
    def symbol(self) -> str:
        raise self._error


class FailingCloseSource(FakeSource):
    async def close(self) -> None:
        self.close_count += 1
        raise RuntimeError("source close failed")


class FailingCloseWarmUpSource(WarmUpFailureSource):
    async def close(self) -> None:
        self.close_count += 1
        raise RuntimeError("source close failed")


class SlowCloseSource(FakeSource):
    def __init__(
        self,
        *,
        recent: Iterable[Candle] = (),
        live: Iterable[Candle] = (),
    ) -> None:
        super().__init__(recent=recent, live=live)
        self.close_started = asyncio.Event()
        self.allow_close = asyncio.Event()

    async def close(self) -> None:
        self.close_count += 1
        self.close_started.set()
        await self.allow_close.wait()
        self._closed.set()


class AlwaysDisconnectingSource(FakeSource):
    def __init__(self) -> None:
        super().__init__(recent=warm_up_candles())
        self.stream_count = 0

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.stream_count += 1
        if False:
            yield candle_at(15)


class SynchronousDisconnectSource(FakeSource):
    def __init__(self) -> None:
        super().__init__(recent=warm_up_candles())
        self.stream_count = 0

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        self.stream_count += 1
        raise RuntimeError("websocket handshake failed")


class DisconnectThenRecoverSource(FakeSource):
    def __init__(self) -> None:
        super().__init__(
            recent=warm_up_candles(),
            ranges={
                (candle_at(15).open_time, candle_at(25).open_time): (
                    candle_at(15),
                    candle_at(20),
                )
            },
        )
        self.stream_count = 0

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.stream_count += 1
        if self.stream_count == 1:
            return
        yield candle_at(20)
        await self._closed.wait()


class MismatchedReconnectSource(DisconnectThenRecoverSource):
    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.stream_count += 1
        if self.stream_count == 1:
            return
        yield candle_at(20, symbol="ETHUSDT")
        await self._closed.wait()


class DisconnectThenDuplicateSource(FakeSource):
    def __init__(self) -> None:
        super().__init__(recent=warm_up_candles())
        self.stream_count = 0

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.stream_count += 1
        if self.stream_count == 1:
            return
        yield candle_at(10)
        yield candle_at(15)
        await self._closed.wait()


class BlockingLiveSource(FakeSource):
    def __init__(self) -> None:
        super().__init__(recent=warm_up_candles())
        self.live_wait_started = asyncio.Event()
        self.live_wait_finished = asyncio.Event()

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.live_started = True
        self.live_wait_started.set()
        try:
            await self._closed.wait()
        finally:
            self.live_wait_finished.set()
        if False:
            yield candle_at(15)


class StaleThenRecoverSource(FakeSource):
    def __init__(self) -> None:
        super().__init__(
            recent=warm_up_candles(),
            ranges={
                (candle_at(15).open_time, candle_at(20).open_time): (candle_at(15),)
            },
        )
        self.stream_count = 0

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self.stream_count += 1
        if self.stream_count == 1:
            await asyncio.Event().wait()
            return
        yield candle_at(15)
        await self._closed.wait()


class RecordingSink:
    def __init__(
        self,
        *,
        fail_warm_up: bool = False,
        fail_live: bool = False,
        fail_live_at: int | None = None,
        scheduler: FakeScheduler | None = None,
    ) -> None:
        self._fail_warm_up = fail_warm_up
        self._fail_live = fail_live
        self._fail_live_at = fail_live_at
        self._live_attempt_count = 0
        self._live_received = asyncio.Event()
        self._scheduler = scheduler
        self.calls: list[tuple[str, tuple[Candle, ...] | Candle]] = []
        self.live_candles: list[Candle] = []
        self.states_at_calls: list[MarketDataRuntimeState] = []
        self.warm_up_within_deadline = False
        self.runtime: MarketDataRuntime | None = None

    async def warm_up(
        self, candles: tuple[Candle, ...], *, received_at: datetime
    ) -> None:
        self._record_state()
        self.warm_up_within_deadline = (
            self._scheduler is not None and self._scheduler.wait_for_active
        )
        if self._fail_warm_up:
            raise RuntimeError("warm-up sink failed")
        self.calls.append(("warm_up", candles))

    async def process_completed(self, candle: Candle, *, received_at: datetime) -> None:
        self._record_state()
        self._live_attempt_count += 1
        if self._fail_live or self._live_attempt_count == self._fail_live_at:
            raise RuntimeError("live sink failed")
        self.calls.append(("process_completed", candle))
        self.live_candles.append(candle)
        self._live_received.set()

    async def wait_for_live_candle_count(self, count: int) -> None:
        while len(self.live_candles) < count:
            self._live_received.clear()
            await self._live_received.wait()

    def _record_state(self) -> None:
        assert self.runtime is not None
        self.states_at_calls.append(self.runtime.snapshot.state)


def runtime_for(
    source: FakeSource,
    sink: RecordingSink,
    *,
    scheduler: FakeScheduler | None = None,
) -> MarketDataRuntime:
    runtime = MarketDataRuntime(
        config=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        warm_up_count=3,
        source=source,
        sink=sink,
        scheduler=scheduler or FakeScheduler(),
    )
    sink.runtime = runtime
    return runtime


async def run_until_sink_receives(
    runtime: MarketDataRuntime,
    sink: RecordingSink,
    *,
    count: int,
) -> None:
    task = asyncio.create_task(runtime.run())
    await sink.wait_for_live_candle_count(count)
    await runtime.stop()
    await task


async def run_until_sink_receives_or_runtime_stops(
    runtime: MarketDataRuntime,
    sink: RecordingSink,
    *,
    count: int,
) -> None:
    run_task = asyncio.create_task(runtime.run())
    sink_task = asyncio.create_task(sink.wait_for_live_candle_count(count))
    done, _ = await asyncio.wait(
        {run_task, sink_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if sink_task in done:
        await runtime.stop()
    else:
        sink_task.cancel()
    await asyncio.gather(run_task, sink_task, return_exceptions=True)


async def run_stale_scenario_or_stop(
    runtime: MarketDataRuntime,
    source: BlockingLiveSource,
) -> None:
    run_task = asyncio.create_task(runtime.run())
    await source.live_wait_started.wait()
    for _ in range(100):
        if run_task.done():
            break
        await asyncio.sleep(0)
    if not run_task.done():
        await runtime.stop()
    await run_task


async def run_until_recovered_or_runtime_stops(runtime: MarketDataRuntime) -> None:
    run_task = asyncio.create_task(runtime.run())
    for _ in range(100):
        visited = runtime.visited_states
        if (
            MarketDataRuntimeState.STALE in visited
            and visited[-1] is MarketDataRuntimeState.LIVE
        ):
            break
        if run_task.done():
            break
        await asyncio.sleep(0)
    if not run_task.done():
        await runtime.stop()
    await run_task


async def stop_during_rate_limit_delay(
    runtime: MarketDataRuntime,
    scheduler: BlockingReconnectScheduler,
) -> None:
    run_task = asyncio.create_task(runtime.run())
    await scheduler.sleep_started.wait()
    await runtime.stop()
    await run_task


def test_runtime_state_snapshot_is_immutable() -> None:
    snapshot = MarketDataRuntimeSnapshot(
        state=MarketDataRuntimeState.STARTING,
        reason=MarketDataRuntimeReason.START_REQUESTED,
        transitioned_at=_NOW,
        last_accepted_open_time=None,
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.state = MarketDataRuntimeState.LIVE  # type: ignore[misc]


def test_runtime_reexports_pipeline_candle_sink_contract() -> None:
    assert MarketDataCandleSink is PipelineMarketDataCandleSink


def test_runtime_warms_sink_before_live_delivery() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    scheduler = FakeScheduler()
    sink = RecordingSink(scheduler=scheduler)
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert sink.calls == [
        ("warm_up", warm_up_candles()),
        ("process_completed", candle_at(15)),
    ]
    assert sink.states_at_calls == [
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeState.LIVE,
    ]
    assert MarketDataRuntimeState.LIVE in runtime.visited_states
    assert source.recent_requests == [
        (MarketDataConfig(symbol="BTCUSDT", timeframe="5m"), 3, _NOW)
    ]
    assert scheduler.timeouts[0] == 30.0
    assert sink.warm_up_within_deadline


def test_warm_up_timeout_fails_closed_without_live_delivery() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink()
    scheduler = TimeoutScheduler()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.WARM_UP_TIMEOUT
    assert sink.calls == []
    assert not source.live_started
    assert scheduler.timeouts == [30.0, 30.0, 30.0, 30.0]
    assert scheduler.sleeps == [1.0, 2.0, 4.0]


def test_pipeline_warm_up_timeout_preserves_warm_up_timeout_reason() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink()
    scheduler = PipelineWarmUpTimeoutScheduler()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.recent_requests == [
        (MarketDataConfig(symbol="BTCUSDT", timeframe="5m"), 3, _NOW)
    ]
    assert scheduler.timeouts == [30.0, 30.0]
    assert scheduler.sleeps == []
    assert sink.calls == []
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.WARM_UP_TIMEOUT


def test_fatal_warm_up_failure_fails_closed_without_retry() -> None:
    source = WarmUpFailureSource([MarketDataFatalError("bad symbol")])
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.load_count == 1
    assert scheduler.sleeps == []
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_close_failure_does_not_overwrite_fatal_source_reason() -> None:
    source = FailingCloseWarmUpSource([MarketDataFatalError("bad symbol")])
    runtime = runtime_for(source, RecordingSink())

    asyncio.run(runtime.run())

    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_retryable_warm_up_failure_uses_bounded_backoff_then_recovers() -> None:
    source = WarmUpFailureSource([MarketDataRetryableError("503")])
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=1))

    assert source.load_count == 2
    assert scheduler.sleeps == [1.0]


def test_rate_limit_uses_delta_seconds_not_reconnect_backoff() -> None:
    source = WarmUpFailureSource(
        [
            MarketDataRateLimitError(
                "429",
                retry_after=timedelta(seconds=45),
            )
        ]
    )
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 45.0
    assert MarketDataRuntimeState.RATE_LIMITED in runtime.visited_states


def test_warm_up_rate_limit_resumes_through_reconnecting_state() -> None:
    source = WarmUpFailureSource(
        [MarketDataRateLimitError("429", retry_after=timedelta(seconds=45))]
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=FakeScheduler())

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert runtime.visited_states[:5] == (
        MarketDataRuntimeState.STARTING,
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.LIVE,
    )


def test_rate_limit_http_date_uses_scheduler_clock() -> None:
    scheduler = FakeScheduler(now=_NOW)
    source = WarmUpFailureSource(
        [
            MarketDataRateLimitError(
                "429",
                retry_after=_NOW + timedelta(seconds=90),
            )
        ]
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 90.0


def test_expired_rate_limit_http_date_retries_without_extra_delay() -> None:
    scheduler = FakeScheduler(now=_NOW)
    source = WarmUpFailureSource(
        [
            MarketDataRateLimitError(
                "429",
                retry_after=_NOW - timedelta(seconds=1),
            )
        ]
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 0.0


def test_rate_limit_without_directive_uses_sixty_second_fallback() -> None:
    source = WarmUpFailureSource([MarketDataRateLimitError("429", retry_after=None)])
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 60.0


def test_stop_cancels_provider_rate_limit_delay_and_closes_source() -> None:
    source = WarmUpFailureSource([MarketDataRateLimitError("429", retry_after=None)])
    scheduler = BlockingReconnectScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(stop_during_rate_limit_delay(runtime, scheduler))

    assert scheduler.sleeps == [60.0]
    assert scheduler.sleep_finished.is_set()
    assert source.load_count == 1
    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.STOP_REQUESTED


def test_repeated_rate_limit_fails_closed_without_one_two_four_backoff() -> None:
    source = WarmUpFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)] * 4
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


def test_final_warm_up_attempt_announces_rate_limit_before_failing_closed() -> None:
    source = WarmUpFailureSource(
        [
            MarketDataRateLimitError("429", retry_after=None),
            MarketDataRetryableError("503"),
            MarketDataRetryableError("503"),
            MarketDataRateLimitError("429", retry_after=None),
        ]
    )
    runtime = runtime_for(source, RecordingSink(), scheduler=FakeScheduler())

    asyncio.run(runtime.run())

    assert runtime.visited_states == (
        MarketDataRuntimeState.STARTING,
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.FAILED_CLOSED,
    )
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


def test_rate_limited_backfill_uses_provider_delay_then_recovers() -> None:
    source = BackfillFailureSource([MarketDataRateLimitError("429", retry_after=None)])
    scheduler = FakeScheduler(now=datetime(2026, 1, 1, 0, 25, tzinfo=UTC))
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=2))

    assert scheduler.sleeps == [60.0]
    assert MarketDataRuntimeState.RATE_LIMITED in runtime.visited_states
    assert sink.live_candles == [candle_at(15), candle_at(20)]


def test_backfill_rate_limit_resumes_through_reconnecting_state() -> None:
    source = BackfillFailureSource([MarketDataRateLimitError("429", retry_after=None)])
    sink = RecordingSink()
    runtime = runtime_for(
        source,
        sink,
        scheduler=FakeScheduler(now=datetime(2026, 1, 1, 0, 25, tzinfo=UTC)),
    )

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=2))

    backfill_index = runtime.visited_states.index(MarketDataRuntimeState.BACKFILLING)
    assert runtime.visited_states[backfill_index : backfill_index + 4] == (
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.LIVE,
    )


def test_fatal_backfill_failure_fails_closed_without_retry() -> None:
    source = BackfillFailureSource([MarketDataFatalError("bad request")])
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.load_count == 1
    assert scheduler.sleeps == []
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_repeated_rate_limited_backfill_uses_only_provider_delays() -> None:
    source = BackfillFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)] * 4
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.load_count == 4
    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


def test_retryable_backfill_failure_uses_bounded_backoff_then_fails_closed() -> None:
    source = BackfillFailureSource([MarketDataRetryableError("503")] * 4)
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.load_count == 4
    assert scheduler.sleeps == [1.0, 2.0, 4.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR


def test_backfill_timeout_uses_bounded_backoff_then_fails_closed() -> None:
    source = BackfillFailureSource([])
    scheduler = BackfillTimeoutScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.timeouts[-4:] == [30.0, 30.0, 30.0, 30.0]
    assert scheduler.sleeps == [1.0, 2.0, 4.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR


def test_fatal_stream_failure_does_not_reconnect() -> None:
    source = StreamFailureSource([MarketDataFatalError("bad request")] * 4)
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == []
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_async_iterator_fatal_failure_does_not_reconnect() -> None:
    source = AsyncIteratorFailureSource([MarketDataFatalError("bad payload")])
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.stream_count == 1
    assert scheduler.sleeps == []
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_reconnect_async_iterator_fatal_failure_stops_recovery() -> None:
    source = AsyncIteratorFailureSource(
        [
            RuntimeError("disconnected"),
            MarketDataFatalError("bad payload"),
        ]
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.stream_count == 2
    assert scheduler.sleeps == [1.0]
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_final_reconnect_attempt_announces_rate_limit_before_failing_closed() -> None:
    source = AsyncIteratorFailureSource(
        [
            RuntimeError("disconnected"),
            MarketDataRateLimitError("429", retry_after=None),
            MarketDataRateLimitError("429", retry_after=None),
            MarketDataRateLimitError("429", retry_after=None),
        ]
    )
    runtime = runtime_for(source, RecordingSink(), scheduler=FakeScheduler())

    asyncio.run(runtime.run())

    assert runtime.visited_states[-8:] == (
        MarketDataRuntimeState.STALE,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.RATE_LIMITED,
        MarketDataRuntimeState.FAILED_CLOSED,
    )
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


def test_async_iterator_rate_limit_exhausts_provider_delays_in_state_order() -> None:
    source = AsyncIteratorFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)] * 4
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.stream_count == 4
    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert runtime.visited_states[-8:] == _RATE_LIMIT_EXHAUSTION_STATES
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


def test_rate_limited_stream_exhausts_only_provider_delays() -> None:
    source = StreamFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)] * 4
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert runtime.visited_states[-8:] == _RATE_LIMIT_EXHAUSTION_STATES
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


@pytest.mark.parametrize(
    "recent",
    [
        (candle_at(0), candle_at(5)),
        (candle_at(0), candle_at(10), candle_at(15)),
        (candle_at(0), candle_at(5), candle_at(10, symbol="ETHUSDT")),
    ],
)
def test_invalid_warm_up_batch_fails_closed_without_calling_sink(
    recent: tuple[Candle, ...],
) -> None:
    source = FakeSource(recent=recent, live=[candle_at(20)])
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert sink.calls == []
    assert not source.live_started


def test_none_warm_up_output_fails_closed_and_closes_source() -> None:
    source = NoneWarmUpSource()
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert runtime.snapshot.last_accepted_open_time is None
    assert sink.calls == []
    assert source.close_count == 1


def test_unexpected_warm_up_validation_error_fails_closed_and_closes_source() -> None:
    source = ExplodingWarmUpSource()
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert runtime.snapshot.last_accepted_open_time is None
    assert sink.calls == []
    assert source.close_count == 1


def test_warm_up_sink_failure_fails_closed_without_live_delivery() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink(fail_warm_up=True)
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SINK_ERROR
    assert runtime.snapshot.last_accepted_open_time is None
    assert not source.live_started


def test_duplicate_live_candle_is_ignored() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(10), candle_at(15)],
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert sink.live_candles == [candle_at(15)]
    assert runtime.snapshot.last_accepted_open_time == candle_at(15).open_time


def test_invalid_live_candle_maps_to_source_error() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(15, symbol="ETHUSDT")],
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert sink.live_candles == []


def test_unexpected_live_validation_error_fails_closed_and_closes_source() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[
            cast(
                Candle,
                ExplodingValidationCandle(
                    RuntimeError("live candle validation failed")
                ),
            )
        ],
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert runtime.snapshot.last_accepted_open_time == candle_at(10).open_time
    assert sink.live_candles == []
    assert source.close_count == 1


def test_gap_backfills_in_order_before_resuming_live() -> None:
    scheduler = FakeScheduler()
    source = DeadlineAwareBackfillSource(scheduler)
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=2))

    assert sink.live_candles == [candle_at(15), candle_at(20)]
    assert sink.states_at_calls[-2:] == [
        MarketDataRuntimeState.LIVE,
        MarketDataRuntimeState.LIVE,
    ]
    assert source.range_requests == [
        (
            MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
            candle_at(15).open_time,
            candle_at(25).open_time,
        )
    ]
    assert runtime.visited_states[-3:-1] == (
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.LIVE,
    )
    assert source.backfill_within_deadline


@pytest.mark.parametrize(
    "backfill",
    [
        (),
        (candle_at(20),),
        (candle_at(15),),
    ],
    ids=["empty", "still-gapped", "missing-observed"],
)
def test_incomplete_gap_backfill_fails_closed(
    backfill: tuple[Candle, ...],
) -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(20)],
        ranges={
            (candle_at(15).open_time, candle_at(25).open_time): backfill,
        },
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert sink.live_candles == []
    assert source.range_requests == [
        (
            MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
            candle_at(15).open_time,
            candle_at(25).open_time,
        )
    ]


def test_non_candle_backfill_output_fails_closed_and_closes_source() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(20)],
        ranges={
            (candle_at(15).open_time, candle_at(25).open_time): (
                candle_at(15),
                object(),
            )
        },
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert runtime.snapshot.last_accepted_open_time == candle_at(10).open_time
    assert sink.live_candles == []
    assert source.close_count == 1


def test_unexpected_backfill_validation_error_fails_closed_and_closes_source() -> None:
    malformed = cast(
        Candle,
        ExplodingValidationCandle(OverflowError("backfill candle time overflow")),
    )
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(20)],
        ranges={
            (candle_at(15).open_time, candle_at(25).open_time): (
                candle_at(15),
                malformed,
            )
        },
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert runtime.snapshot.last_accepted_open_time == candle_at(10).open_time
    assert sink.live_candles == []
    assert source.close_count == 1


def test_stale_wait_uses_expected_close_boundary_plus_thirty_seconds() -> None:
    source = BlockingLiveSource()
    scheduler = TimeoutAfterWarmUpScheduler(
        now=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_stale_scenario_or_stop(runtime, source))

    assert scheduler.timeouts[:3] == [30.0, 30.0, 330.0]
    assert MarketDataRuntimeState.STALE in runtime.visited_states
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RECONNECT_EXHAUSTED


def test_stale_reconnect_uses_new_boundary_deadline_and_recovers() -> None:
    source = StaleThenRecoverSource()
    scheduler = RecoveringAfterStaleScheduler(
        now=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=1))

    assert scheduler.timeouts[:4] == [30.0, 30.0, 330.0, 299.0]
    assert scheduler.sleeps == [1.0]
    assert sink.live_candles == [candle_at(15)]
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED


def test_reconnect_uses_one_two_four_seconds_then_fails_closed() -> None:
    source = AlwaysDisconnectingSource()
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == [1.0, 2.0, 4.0]
    assert source.stream_count == 4
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RECONNECT_EXHAUSTED


def test_synchronous_disconnect_uses_bounded_reconnect_policy() -> None:
    source = SynchronousDisconnectSource()
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == [1.0, 2.0, 4.0]
    assert source.stream_count == 4
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RECONNECT_EXHAUSTED


def test_reconnect_backfills_buffered_first_candle_before_returning_live() -> None:
    source = DisconnectThenRecoverSource()
    scheduler = FakeScheduler(
        now=datetime(2026, 1, 1, 0, 25, tzinfo=UTC),
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=2))

    assert sink.live_candles == [candle_at(15), candle_at(20)]
    stale_index = runtime.visited_states.index(MarketDataRuntimeState.STALE)
    assert runtime.visited_states[stale_index : stale_index + 4] == (
        MarketDataRuntimeState.STALE,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.LIVE,
    )
    assert scheduler.sleeps == [1.0]
    assert source.stream_count == 2


def test_reconnect_rejects_malformed_buffered_first_candle_before_sink() -> None:
    source = MismatchedReconnectSource()
    scheduler = FakeScheduler(
        now=datetime(2026, 1, 1, 0, 25, tzinfo=UTC),
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives_or_runtime_stops(runtime, sink, count=2))

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert sink.live_candles == []


def test_reconnect_duplicate_proves_no_missing_backfill_before_live() -> None:
    source = DisconnectThenDuplicateSource()
    scheduler = FakeScheduler(
        now=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_recovered_or_runtime_stops(runtime))

    assert sink.live_candles == []
    assert source.range_requests == []
    stale_index = runtime.visited_states.index(MarketDataRuntimeState.STALE)
    assert runtime.visited_states[stale_index : stale_index + 4] == (
        MarketDataRuntimeState.STALE,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.LIVE,
    )


def test_backfill_sink_failure_fails_closed_without_partial_delivery() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(20)],
        ranges={
            (candle_at(15).open_time, candle_at(25).open_time): (
                candle_at(15),
                candle_at(20),
            )
        },
    )
    sink = RecordingSink(fail_live=True)
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SINK_ERROR
    assert sink.live_candles == []


def test_backfill_sink_failure_reports_last_delivered_candle_watermark() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(20)],
        ranges={
            (candle_at(15).open_time, candle_at(25).open_time): (
                candle_at(15),
                candle_at(20),
            )
        },
    )
    sink = RecordingSink(fail_live_at=2)
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert sink.live_candles == [candle_at(15)]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SINK_ERROR
    assert runtime.snapshot.last_accepted_open_time == candle_at(15).open_time


def test_stop_cancels_freshness_wait_and_awaits_live_iterator_cleanup() -> None:
    source = BlockingLiveSource()
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    async def exercise() -> None:
        run_task = asyncio.create_task(runtime.run())
        await source.live_wait_started.wait()
        await runtime.stop()
        await run_task

    asyncio.run(exercise())

    assert source.live_wait_finished.is_set()
    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED


def test_stop_cancels_reconnect_delay_and_awaits_cleanup() -> None:
    source = AlwaysDisconnectingSource()
    scheduler = BlockingReconnectScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    async def exercise() -> None:
        run_task = asyncio.create_task(runtime.run())
        await scheduler.sleep_started.wait()
        await runtime.stop()
        await run_task

    asyncio.run(exercise())

    assert scheduler.sleeps == [1.0]
    assert scheduler.sleep_finished.is_set()
    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED


def test_live_sink_failure_fails_closed_and_stops_delivery() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(15), candle_at(20)],
    )
    sink = RecordingSink(fail_live=True)
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SINK_ERROR
    assert runtime.snapshot.last_accepted_open_time == candle_at(10).open_time
    assert sink.live_candles == []


def test_stop_is_idempotent_and_closes_source_once() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    async def exercise() -> None:
        task = asyncio.create_task(runtime.run())
        await sink.wait_for_live_candle_count(1)
        await runtime.stop()
        await runtime.stop()
        await task

    asyncio.run(exercise())

    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.STOP_REQUESTED


def test_stop_during_warm_up_cancels_run_without_starting_live() -> None:
    source = BlockingWarmUpSource()
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    async def exercise() -> None:
        task = asyncio.create_task(runtime.run())
        await source.load_started.wait()
        await runtime.stop()
        await task

    asyncio.run(exercise())

    assert source.close_count == 1
    assert not source.live_started
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED


def test_close_failure_fails_closed_and_awaits_cancelled_run() -> None:
    source = FailingCloseSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    async def exercise() -> None:
        task = asyncio.create_task(runtime.run())
        await sink.wait_for_live_candle_count(1)
        with pytest.raises(RuntimeError, match="source close failed"):
            await runtime.stop()
        assert task.done()

    asyncio.run(exercise())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR


def test_external_run_cancellation_fails_closed_and_closes_source() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    async def exercise() -> None:
        task = asyncio.create_task(runtime.run())
        await sink.wait_for_live_candle_count(1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR


def test_concurrent_stop_callers_wait_for_the_same_shutdown() -> None:
    source = SlowCloseSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    async def exercise() -> None:
        run_task = asyncio.create_task(runtime.run())
        await sink.wait_for_live_candle_count(1)
        first_stop = asyncio.create_task(runtime.stop())
        await source.close_started.wait()
        second_stop = asyncio.create_task(runtime.stop())
        await asyncio.sleep(0)
        assert not second_stop.done()
        source.allow_close.set()
        await asyncio.gather(first_stop, second_stop, run_task)

    asyncio.run(exercise())

    assert source.close_count == 1
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED
