from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import IndicatorSnapshot
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import RsiStepGridStrategy

SESSION_ID = UUID("00000000-0000-0000-0000-000000000078")


def candle(minute: int, open_price: str, close_price: str) -> Candle:
    high = max(Decimal(open_price), Decimal(close_price)) + Decimal("1")
    low = min(Decimal(open_price), Decimal(close_price)) - Decimal("1")
    return Candle(
        symbol="CONFIGURED_SYMBOL",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal(open_price),
        high=high,
        low=low,
        close=Decimal(close_price),
        volume=Decimal("1"),
    )


def snapshot(rsi: str, atr: str = "2.5") -> IndicatorSnapshot:
    return IndicatorSnapshot(rsi=Decimal(rsi), atr=Decimal(atr))


def armed_strategy(reset_close: str = "100") -> RsiStepGridStrategy:
    strategy = RsiStepGridStrategy(SESSION_ID, RsiStepGridPreset.v1())
    assert (
        strategy.evaluate(
            candle(0, "101", reset_close),
            snapshot("29"),
            entry_number=1,
            can_enter=True,
        )
        is None
    )
    return strategy


def test_reset_then_bullish_confirmation_creates_an_auditable_intent() -> None:
    signal_candle = candle(5, "100", "102")

    intent = armed_strategy().evaluate(
        signal_candle,
        snapshot("51", "2.75"),
        entry_number=3,
        can_enter=True,
    )

    assert intent is not None
    assert intent.session_id == SESSION_ID
    assert intent.preset_version == "rsi-step-grid-v1"
    assert intent.entry_number == 3
    assert intent.signal_candle == signal_candle
    assert intent.atr == Decimal("2.75")
    assert len(intent.intent_id) == 64


def test_same_decision_inputs_create_the_same_intent_id() -> None:
    signal_candle = candle(5, "100", "102")

    first = armed_strategy().evaluate(
        signal_candle, snapshot("51"), entry_number=1, can_enter=True
    )
    second = armed_strategy().evaluate(
        signal_candle, snapshot("51"), entry_number=1, can_enter=True
    )

    assert first is not None
    assert second is not None
    assert first.intent_id == second.intent_id


@pytest.mark.parametrize(
    ("rsi", "open_price", "close_price", "can_enter"),
    [
        ("50", "100", "102", True),
        ("51", "102", "101", True),
        ("51", "99", "100", True),
        ("51", "100", "102", False),
    ],
)
def test_confirmation_requires_every_entry_condition(
    rsi: str,
    open_price: str,
    close_price: str,
    can_enter: bool,
) -> None:
    intent = armed_strategy().evaluate(
        candle(5, open_price, close_price),
        snapshot(rsi),
        entry_number=1,
        can_enter=can_enter,
    )

    assert intent is None


def test_pending_intent_blocks_duplicates_and_fill_consumes_the_reset() -> None:
    strategy = armed_strategy()
    first = strategy.evaluate(
        candle(5, "100", "102"),
        snapshot("51"),
        entry_number=1,
        can_enter=True,
    )
    assert first is not None

    assert (
        strategy.evaluate(
            candle(10, "102", "104"),
            snapshot("60"),
            entry_number=1,
            can_enter=True,
        )
        is None
    )

    strategy.on_entry_filled(first.intent_id)

    assert (
        strategy.evaluate(
            candle(15, "104", "106"),
            snapshot("60"),
            entry_number=2,
            can_enter=True,
        )
        is None
    )
    assert (
        strategy.evaluate(
            candle(20, "105", "99"),
            snapshot("29"),
            entry_number=2,
            can_enter=True,
        )
        is None
    )
    second = strategy.evaluate(
        candle(25, "99", "101"),
        snapshot("51"),
        entry_number=2,
        can_enter=True,
    )
    assert second is not None
    assert second.intent_id != first.intent_id


def test_fill_must_match_the_pending_intent() -> None:
    strategy = armed_strategy()
    intent = strategy.evaluate(
        candle(5, "100", "102"),
        snapshot("51"),
        entry_number=1,
        can_enter=True,
    )
    assert intent is not None

    with pytest.raises(ValueError, match="pending intent"):
        strategy.on_entry_filled("wrong-id")
