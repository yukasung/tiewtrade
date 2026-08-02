import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.application.chart_data import ChartRange, ChartReadState
from tiewtrade.application.chart_history import ChartHistory
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.trade_history import FillSide, FillSource, TradeFill


class FakeCandleSource:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles
        self.requests: list[tuple[MarketDataConfig, datetime, datetime]] = []
        self.closed = False

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        self.requests.append((config, start, end))
        return self._candles

    async def close(self) -> None:
        self.closed = True


class FakeTradeHistory:
    def __init__(self, fills: tuple[TradeFill, ...]) -> None:
        self._fills = fills
        self.requests: list[tuple[UUID, datetime, datetime]] = []

    def list_session_fills(
        self,
        session_id: UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> tuple[TradeFill, ...]:
        self.requests.append((session_id, start_utc, end_utc))
        return self._fills


def test_chart_history_loads_only_requested_public_range_and_session_fills() -> None:
    selected_range = chart_range()
    buy = trade_fill("buy-1", FillSide.BUY)
    sell = trade_fill("sell-1", FillSide.SELL)
    source = FakeCandleSource((candle(),))
    fills = FakeTradeHistory((buy, sell))
    history = ChartHistory(
        source_factory=lambda: source,
        trade_history=fills,
        clock=lambda: selected_range.end,
    )

    snapshot = asyncio.run(history.load(session(), selected_range))

    assert source.requests == [
        (session().market_data, selected_range.start, selected_range.end)
    ]
    assert source.closed is True
    assert fills.requests == [
        (session().config.session_id, selected_range.start, selected_range.end)
    ]
    assert snapshot.state is ChartReadState.READY
    assert [marker.fill_id for marker in snapshot.markers] == ["buy-1", "sell-1"]


def test_chart_history_creates_and_closes_a_fresh_source_for_each_load() -> None:
    selected_range = chart_range()
    first_source = FakeCandleSource((candle(),))
    second_source = FakeCandleSource((candle(),))
    sources = iter((first_source, second_source))
    history = ChartHistory(
        source_factory=lambda: next(sources),
        trade_history=FakeTradeHistory(()),
        clock=lambda: selected_range.end,
    )

    asyncio.run(history.load(session(), selected_range))
    asyncio.run(history.load(session(), selected_range))

    expected_request = [
        (session().market_data, selected_range.start, selected_range.end)
    ]
    assert first_source.requests == expected_request
    assert second_source.requests == expected_request
    assert first_source.closed is True
    assert second_source.closed is True


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


def candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
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
