from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.application.paper_spot_session import PaperSpotSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import (
    MarketType,
    SessionConfig,
    TradeMode,
)
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_session_rejects_a_non_paper_spot_configuration() -> None:
    config = session_config(trade_mode=TradeMode.LIVE)

    with pytest.raises(ValueError, match="Paper Spot"):
        PaperSpotSession(
            config,
            MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
            SymbolRules(
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.001"),
                min_notional=Decimal("5"),
            ),
            RsiStepGridPreset.v1(),
        )


def test_pending_intent_fills_at_the_next_completed_candle_open() -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    fill_candle = candle(125, open_price="120", close_price="121")

    snapshot = application.process_completed_candle(
        fill_candle, received_at=fill_candle.close_time
    )

    assert pending.signal_candle.open_time < fill_candle.open_time
    assert snapshot.entry_fill is not None
    assert snapshot.entry_fill.intent_id == pending.intent_id
    assert snapshot.entry_fill.price == Decimal("120.30")
    assert snapshot.basket_entry_count == 1
    assert snapshot.take_profit_price == Decimal("129.30")


def test_take_profit_skips_entry_fill_candle_and_closes_on_following_candle() -> None:
    application = paper_session()
    arm_entry_intent(application)
    entry_candle = candle(125, open_price="120", close_price="121", high="140")

    entry_snapshot = application.process_completed_candle(
        entry_candle, received_at=entry_candle.close_time
    )

    assert entry_snapshot.entry_fill is not None
    assert entry_snapshot.closed_basket is None
    assert entry_snapshot.basket_entry_count == 1

    target_candle = candle(130, open_price="125", close_price="130", high="140")
    target_snapshot = application.process_completed_candle(
        target_candle, received_at=target_candle.close_time
    )

    assert target_snapshot.closed_basket is not None
    assert target_snapshot.closed_basket.entry_count == 1
    assert target_snapshot.basket_entry_count == 0
    assert target_snapshot.take_profit_price is None


def test_minimum_notional_rejection_releases_strategy_to_create_a_new_intent() -> None:
    application = paper_session(min_notional=Decimal("200"))
    first_intent = arm_entry_intent(application)
    rejected_candle = candle(125, open_price="120", close_price="121")

    rejected = application.process_completed_candle(
        rejected_candle, received_at=rejected_candle.close_time
    )

    assert rejected.entry_fill is None
    assert rejected.pending_intent is not None
    assert rejected.pending_intent.intent_id != first_intent.intent_id
    assert rejected.pending_intent.signal_candle == rejected_candle


def test_closed_two_entry_basket_resets_lifecycle_for_a_new_basket() -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent), open_price="120", close_price="121"
    )
    application.process_completed_candle(
        first_fill_candle, received_at=first_fill_candle.close_time
    )

    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    second_fill_candle = candle(
        minute_after(second_intent), open_price="100", close_price="101"
    )
    second_fill = application.process_completed_candle(
        second_fill_candle, received_at=second_fill_candle.close_time
    )
    assert second_fill.basket_entry_count == 2

    close_candle = candle(
        minute_after(second_intent) + 5,
        open_price="100",
        close_price="101",
        high="1000",
    )
    closed = application.process_completed_candle(
        close_candle, received_at=close_candle.close_time
    )
    assert closed.closed_basket is not None
    assert closed.closed_basket.entry_count == 2

    new_intent = arm_entry_intent(
        application,
        start_minute=minute_after(second_intent) + 10,
        downtrend_candles=60,
    )
    new_fill_candle = candle(
        minute_after(new_intent), open_price="120", close_price="121"
    )
    new_fill = application.process_completed_candle(
        new_fill_candle, received_at=new_fill_candle.close_time
    )

    assert new_fill.entry_fill is not None
    assert new_fill.basket_entry_count == 1


def paper_session(*, min_notional: Decimal = Decimal("5")) -> PaperSpotSession:
    return PaperSpotSession(
        session_config(),
        MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        SymbolRules(
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=min_notional,
        ),
        RsiStepGridPreset.v1(),
    )


def arm_entry_intent(
    application: PaperSpotSession,
    *,
    start_minute: int = 0,
    downtrend_candles: int = 15,
):
    close = Decimal("100")
    downtrend_end = start_minute + (downtrend_candles * 5)
    for minute in range(start_minute, downtrend_end, 5):
        candle_value = candle(minute, open_price=str(close + 1), close_price=str(close))
        application.process_completed_candle(
            candle_value, received_at=candle_value.close_time
        )
        close -= Decimal("1")

    for minute in range(downtrend_end, downtrend_end + 125, 5):
        candle_value = candle(minute, open_price=str(close), close_price=str(close + 1))
        snapshot = application.process_completed_candle(
            candle_value, received_at=candle_value.close_time
        )
        if snapshot.pending_intent is not None:
            return snapshot.pending_intent
        close += Decimal("1")

    raise AssertionError("expected a pending entry intent")


def candle(
    minute: int,
    *,
    open_price: str,
    close_price: str,
    high: str | None = None,
) -> Candle:
    open_decimal = Decimal(open_price)
    close_decimal = Decimal(close_price)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
        open=open_decimal,
        high=(
            max(open_decimal, close_decimal) + Decimal("1")
            if high is None
            else Decimal(high)
        ),
        low=min(open_decimal, close_decimal) - Decimal("1"),
        close=close_decimal,
        volume=Decimal("1"),
    )


def minute_after(intent) -> int:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    return int((intent.signal_candle.open_time - origin).total_seconds() / 60) + 5


def session_config(**overrides: object) -> SessionConfig:
    values: dict[str, object] = {
        "session_id": UUID("00000000-0000-0000-0000-000000000079"),
        "account_profile_id": UUID("00000000-0000-0000-0000-000000000001"),
        "preset_version": "rsi-step-grid-v1",
        "market_type": MarketType.SPOT,
        "trade_mode": TradeMode.PAPER,
        "available_capital": Decimal("1000"),
        "fee_rate": Decimal("0.001"),
        "slippage_bps": Decimal("25"),
        "entry_policy": EntryPolicy(max_entries=4),
        "spot_policy": SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    }
    values.update(overrides)
    return SessionConfig(**values)  # type: ignore[arg-type]
