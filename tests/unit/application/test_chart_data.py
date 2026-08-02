from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
    append_completed_candle,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.trade_history import FillSide, FillSource, TradeFill


def test_ready_snapshot_rejects_candle_from_another_session_timeframe() -> None:
    with pytest.raises(ValueError, match="candle timeframe must match Session"):
        ready_chart_snapshot(candles=(candle("15m"),), fills=())


def test_append_completed_candle_replaces_same_open_time_and_keeps_order() -> None:
    snapshot = ready_chart_snapshot(candles=(candle("5m", minute=15),))

    result = append_completed_candle(snapshot, candle("5m", minute=10))

    assert tuple(item.open_time for item in result.candles) == tuple(
        sorted(item.open_time for item in result.candles)
    )
    replacement = append_completed_candle(result, candle("5m", minute=10, close="105"))
    assert len(replacement.candles) == 2
    assert replacement.candles[0].close == Decimal("105")


def test_chart_range_requires_an_ordered_utc_half_open_range() -> None:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="start must use UTC"):
        ChartRange(datetime(2026, 1, 1), start + timedelta(minutes=5))
    with pytest.raises(ValueError, match="start must be before end"):
        ChartRange(start, start)


def test_snapshot_reads_immutable_chart_facts_from_configured_paper_session() -> None:
    snapshot = ready_chart_snapshot()

    assert snapshot.session_id == session().config.session_id
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timeframe == "5m"
    assert "session" not in ChartSnapshot.__slots__


def test_snapshot_rejects_unknown_read_state() -> None:
    with pytest.raises(ValueError, match="state must be a ChartReadState"):
        ChartSnapshot(
            session=session(),
            chart_range=chart_range(),
            observed_at_utc=datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
            candles=(),
            fills=(),
            state="ready",  # type: ignore[arg-type]
        )


def test_snapshot_rejects_range_ending_after_observation_boundary() -> None:
    with pytest.raises(
        ValueError, match="ChartRange end must not be after observed_at_utc"
    ):
        ChartSnapshot(
            session=session(),
            chart_range=chart_range(),
            observed_at_utc=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
            candles=(),
            fills=(),
            state=ChartReadState.READY,
        )


def test_snapshot_rejects_candle_not_completed_by_observation_boundary() -> None:
    with pytest.raises(ValueError, match="candle must be completed by observed_at_utc"):
        ChartSnapshot(
            session=session(),
            chart_range=ChartRange(
                datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
            ),
            observed_at_utc=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
            candles=(candle("5m", minute=10),),
            fills=(),
            state=ChartReadState.READY,
        )


def test_ready_snapshot_derives_session_scoped_markers_from_durable_fills() -> None:
    fill = trade_fill(filled_at_utc=datetime(2026, 1, 1, 0, 10, tzinfo=UTC))

    snapshot = ready_chart_snapshot(candles=(candle("5m", minute=10),), fills=(fill,))

    assert snapshot.state is ChartReadState.READY
    assert len(snapshot.markers) == 1
    assert snapshot.markers[0].fill_id == fill.fill_id
    assert snapshot.markers[0].side is FillSide.BUY
    assert snapshot.markers[0].price == fill.price
    assert snapshot.markers[0].filled_at_utc == fill.filled_at_utc


def test_ready_snapshot_rejects_fill_from_another_session_or_outside_range() -> None:
    other_session_fill = trade_fill(session_id=uuid4())
    out_of_range_fill = trade_fill(
        filled_at_utc=datetime(2026, 1, 1, 0, 30, tzinfo=UTC)
    )

    with pytest.raises(ValueError, match="fill session must match Session"):
        ready_chart_snapshot(fills=(other_session_fill,))
    with pytest.raises(ValueError, match="fill must be inside ChartRange"):
        ready_chart_snapshot(fills=(out_of_range_fill,))


def ready_chart_snapshot(
    *,
    candles: tuple[Candle, ...] = (),
    fills: tuple[TradeFill, ...] = (),
) -> ChartSnapshot:
    return ChartSnapshot(
        session=session(),
        chart_range=chart_range(),
        observed_at_utc=datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
        candles=candles,
        fills=fills,
        state=ChartReadState.READY,
    )


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


def candle(
    timeframe: str,
    *,
    minute: int = 0,
    close: str = "101",
) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe=timeframe,
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("106"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("1.25"),
    )


def trade_fill(
    *,
    session_id: UUID | None = None,
    filled_at_utc: datetime | None = None,
) -> TradeFill:
    return TradeFill(
        fill_id="fill-138",
        basket_id=uuid4(),
        session_id=session().config.session_id if session_id is None else session_id,
        order_id="order-138",
        exchange_trade_id="trade-138",
        side=FillSide.BUY,
        entry_number=1,
        filled_at_utc=(
            datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
            if filled_at_utc is None
            else filled_at_utc
        ),
        price=Decimal("101.25"),
        quantity=Decimal("0.1"),
        notional=Decimal("10.125"),
        commission=Decimal("0.01"),
        commission_asset="USDT",
        realized_pnl=Decimal("0"),
        source=FillSource.PAPER_EXECUTOR,
    )
