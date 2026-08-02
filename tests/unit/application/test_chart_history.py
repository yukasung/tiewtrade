import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.application.chart_history import ChartHistory
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.trade_history import FillSide, FillSource, TradeFill


class FakeLoadChartCandles:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles
        self.requests: list[tuple[ConfiguredPaperSession, ChartRange]] = []

    async def __call__(
        self,
        configured: ConfiguredPaperSession,
        requested: ChartRange,
    ) -> tuple[Candle, ...]:
        self.requests.append((configured, requested))
        return self._candles


class FakeListChartFills:
    def __init__(self, fills: tuple[TradeFill, ...]) -> None:
        self._fills = fills
        self.requests: list[tuple[UUID, ChartRange]] = []

    def __call__(
        self,
        session_id: UUID,
        requested: ChartRange,
    ) -> tuple[TradeFill, ...]:
        self.requests.append((session_id, requested))
        return self._fills


def test_chart_history_loads_only_requested_public_range_and_session_fills() -> None:
    selected_range = chart_range()
    buy = trade_fill("buy-1", FillSide.BUY)
    sell = trade_fill("sell-1", FillSide.SELL)
    load_candles = FakeLoadChartCandles((candle(),))
    list_fills = FakeListChartFills((buy, sell))
    history = ChartHistory(
        load_candles=load_candles,
        list_fills=list_fills,
        clock=lambda: selected_range.end,
    )

    snapshot = asyncio.run(history.load(session(), selected_range))

    assert load_candles.requests == [(session(), selected_range)]
    assert list_fills.requests == [(session().config.session_id, selected_range)]
    assert snapshot.state is ChartReadState.READY
    assert [marker.fill_id for marker in snapshot.markers] == ["buy-1", "sell-1"]


def test_chart_history_delegates_each_load_to_focused_candle_callable() -> None:
    selected_range = chart_range()
    load_candles = FakeLoadChartCandles((candle(),))
    history = ChartHistory(
        load_candles=load_candles,
        list_fills=FakeListChartFills(()),
        clock=lambda: selected_range.end,
    )

    asyncio.run(history.load(session(), selected_range))
    asyncio.run(history.load(session(), selected_range))

    assert load_candles.requests == [
        (session(), selected_range),
        (session(), selected_range),
    ]


def test_refresh_completed_candle_advances_latest_range_and_reloads_durable_fills() -> (
    None
):
    selected_range = chart_range()
    completed = candle(20)
    new_fill = trade_fill("runtime-buy", FillSide.BUY)
    fills = FakeListChartFills((new_fill,))
    history = ChartHistory(
        load_candles=FakeLoadChartCandles(()),
        list_fills=fills,
        clock=lambda: completed.close_time,
    )
    current = ChartSnapshot(
        session=session(),
        chart_range=selected_range,
        observed_at_utc=selected_range.end,
        candles=(candle(0), candle(5), candle(10), candle(15)),
        fills=(),
        state=ChartReadState.READY,
    )

    refreshed = asyncio.run(history.refresh_completed(session(), current, completed))

    assert refreshed.chart_range == ChartRange(
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 25, tzinfo=UTC),
    )
    assert [item.open_time.minute for item in refreshed.candles] == [5, 10, 15, 20]
    assert fills.requests == [
        (
            session().config.session_id,
            refreshed.chart_range,
        )
    ]
    assert [marker.fill_id for marker in refreshed.markers] == ["runtime-buy"]


def chart_range() -> ChartRange:
    return ChartRange(
        datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
    )


def session() -> ConfiguredPaperSession:
    return ConfiguredPaperSession(
        config=SessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000138"),
            preset_version="rsi-step-grid-v1",
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("1000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("5"),
            entry_policy=EntryPolicy(max_entries=10),
            spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.8")),
        ),
        market_data=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        created_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )


def candle(minute: int = 10) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("106"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("1.25"),
    )


def trade_fill(fill_id: str, side: FillSide) -> TradeFill:
    return TradeFill(
        fill_id=fill_id,
        basket_id=UUID("00000000-0000-0000-0000-000000000139"),
        session_id=session().config.session_id,
        order_id=f"order-{fill_id}",
        exchange_trade_id=None,
        side=side,
        entry_number=1 if side is FillSide.BUY else None,
        filled_at_utc=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
        price=Decimal("101.25"),
        quantity=Decimal("0.1"),
        notional=Decimal("10.125"),
        commission=Decimal("0.01"),
        commission_asset="USDT",
        realized_pnl=Decimal("0"),
        source=FillSource.PAPER_EXECUTOR,
    )
