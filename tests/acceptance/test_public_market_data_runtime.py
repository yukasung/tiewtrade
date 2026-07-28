from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypeVar
from uuid import UUID

from tiewtrade.application.paper_spot_market_data import PaperSpotMarketDataSink
from tiewtrade.application.paper_spot_session import PaperSpotSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime import MarketDataRuntime
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeState,
)
from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
)
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules

_NOW = datetime(2026, 1, 1, 1, 20, tzinfo=UTC)
_T = TypeVar("_T")


class FakePublicCandleSource:
    def __init__(
        self,
        *,
        warm_up: Iterable[Candle],
        live: Iterable[Candle],
    ) -> None:
        self._warm_up = tuple(warm_up)
        self._live = tuple(live)
        self._closed = asyncio.Event()
        self.requested_warm_up_count: int | None = None
        self.close_count = 0

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.requested_warm_up_count = count
        return self._warm_up

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        raise AssertionError("contiguous acceptance candles must not backfill")

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed()

    async def close(self) -> None:
        if self._closed.is_set():
            return
        self.close_count += 1
        self._closed.set()

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        for candle in self._live:
            yield candle
        await self._closed.wait()


class FakeRuntimeScheduler:
    def now(self) -> datetime:
        return _NOW

    async def sleep(self, seconds: float) -> None:
        raise AssertionError("contiguous acceptance flow must not reconnect")

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        return await awaitable


class FakeFailureRuntimeScheduler(FakeRuntimeScheduler):
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


class FailedCompletedCandleStream:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    def __aiter__(self) -> FailedCompletedCandleStream:
        return self

    async def __anext__(self) -> Candle:
        raise self._failure


class FakeFailingPublicCandleSource(FakePublicCandleSource):
    def __init__(
        self,
        *,
        warm_up: Iterable[Candle],
        failure: Exception,
    ) -> None:
        super().__init__(warm_up=warm_up, live=())
        self._failure = failure
        self.stream_count = 0

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        self.stream_count += 1
        return FailedCompletedCandleStream(self._failure)


def test_fake_public_runtime_warms_then_processes_paper_spot_live_candle() -> None:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    warm_up = candles(start=0, count=15, config=market_data)
    live = candles(start=75, count=1, config=market_data)
    source = FakePublicCandleSource(warm_up=warm_up, live=live)
    sink = PaperSpotMarketDataSink(configured_paper_spot_session(market_data))
    runtime = MarketDataRuntime(
        config=market_data,
        warm_up_count=len(warm_up),
        source=source,
        sink=sink,
        scheduler=FakeRuntimeScheduler(),
    )

    asyncio.run(run_until_sink_receives(runtime, sink, count=len(live)))

    assert runtime.visited_states.index(
        MarketDataRuntimeState.WARMING_UP
    ) < runtime.visited_states.index(MarketDataRuntimeState.LIVE)
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED
    assert source.requested_warm_up_count == len(warm_up)
    assert source.close_count == 1
    assert sink.last_snapshot is not None
    assert sink.last_snapshot.accepted is True
    assert sink.live_candle_count == len(live)
    assert set(inspect.signature(FakePublicCandleSource).parameters) == {
        "warm_up",
        "live",
    }
    assert not hasattr(source, "credentials")
    assert not hasattr(source, "order_transport")
    assert not hasattr(source, "place_order")


def test_rate_limit_exhaustion_fails_closed_without_paper_spot_delivery() -> None:
    runtime, source, sink, scheduler = runtime_with_failing_stream(
        MarketDataRateLimitError("429", retry_after=None)
    )

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED
    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert source.stream_count == 4
    assert sink.live_candle_count == 0
    assert sink.last_snapshot is None


def test_fatal_source_failure_fails_closed_without_paper_spot_delivery() -> None:
    runtime, source, sink, scheduler = runtime_with_failing_stream(
        MarketDataFatalError("bad request")
    )

    asyncio.run(runtime.run())

    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL
    assert scheduler.sleeps == []
    assert source.stream_count == 1
    assert sink.live_candle_count == 0
    assert sink.last_snapshot is None


def runtime_with_failing_stream(
    failure: Exception,
) -> tuple[
    MarketDataRuntime,
    FakeFailingPublicCandleSource,
    PaperSpotMarketDataSink,
    FakeFailureRuntimeScheduler,
]:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    warm_up = candles(start=0, count=15, config=market_data)
    source = FakeFailingPublicCandleSource(
        warm_up=warm_up,
        failure=failure,
    )
    sink = PaperSpotMarketDataSink(configured_paper_spot_session(market_data))
    scheduler = FakeFailureRuntimeScheduler()
    runtime = MarketDataRuntime(
        config=market_data,
        warm_up_count=len(warm_up),
        source=source,
        sink=sink,
        scheduler=scheduler,
    )
    return runtime, source, sink, scheduler


async def run_until_sink_receives(
    runtime: MarketDataRuntime,
    sink: PaperSpotMarketDataSink,
    *,
    count: int,
) -> None:
    run_task = asyncio.create_task(runtime.run())
    try:
        for _ in range(100):
            if sink.live_candle_count >= count:
                break
            if run_task.done():
                await run_task
            await asyncio.sleep(0)
        else:
            raise AssertionError("runtime did not deliver the live candle")
    finally:
        await runtime.stop()
        await run_task


def configured_paper_spot_session(
    market_data: MarketDataConfig,
) -> PaperSpotSession:
    preset = RsiStepGridPreset.v1()
    return PaperSpotSession(
        SessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000099"),
            preset_version=preset.version,
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("1000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=4),
            spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
        ),
        market_data,
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        preset,
    )


def candles(
    *,
    start: int,
    count: int,
    config: MarketDataConfig,
) -> tuple[Candle, ...]:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        Candle(
            symbol=config.symbol,
            timeframe=config.timeframe,
            open_time=origin + timedelta(minutes=minute),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("10"),
        )
        for minute in range(start, start + count * 5, 5)
    )
