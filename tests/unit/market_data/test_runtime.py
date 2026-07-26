from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Coroutine, Iterable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeVar

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime import MarketDataRuntime
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeSnapshot,
    MarketDataRuntimeState,
)

_NOW = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)
_T = TypeVar("_T")


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
    def __init__(self) -> None:
        self.timeouts: list[float] = []
        self.sleeps: list[float] = []
        self.wait_for_active = False

    def now(self) -> datetime:
        return _NOW

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        self.wait_for_active = True
        try:
            return await awaitable
        finally:
            self.wait_for_active = False


class TimeoutScheduler(FakeScheduler):
    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        self.timeouts.append(timeout)
        if isinstance(awaitable, Coroutine):
            awaitable.close()
        raise TimeoutError


class FakeSource:
    def __init__(
        self,
        *,
        recent: Iterable[Candle] = (),
        live: Iterable[Candle] = (),
    ) -> None:
        self._recent = tuple(recent)
        self._live = tuple(live)
        self._closed = asyncio.Event()
        self.recent_requests: list[tuple[MarketDataConfig, int, datetime]] = []
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
        raise AssertionError("Task 4 must not request backfill")

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


class FailingCloseSource(FakeSource):
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


class RecordingSink:
    def __init__(
        self,
        *,
        fail_warm_up: bool = False,
        fail_live: bool = False,
        scheduler: FakeScheduler | None = None,
    ) -> None:
        self._fail_warm_up = fail_warm_up
        self._fail_live = fail_live
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
        if self._fail_live:
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


def test_runtime_state_snapshot_is_immutable() -> None:
    snapshot = MarketDataRuntimeSnapshot(
        state=MarketDataRuntimeState.STARTING,
        reason=MarketDataRuntimeReason.START_REQUESTED,
        transitioned_at=_NOW,
        last_accepted_open_time=None,
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.state = MarketDataRuntimeState.LIVE  # type: ignore[misc]


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
    assert scheduler.timeouts == [30.0]
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
    assert scheduler.timeouts == [30.0]


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


def test_warm_up_sink_failure_fails_closed_without_live_delivery() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[candle_at(15)])
    sink = RecordingSink(fail_warm_up=True)
    runtime = runtime_for(source, sink)

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SINK_ERROR
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
