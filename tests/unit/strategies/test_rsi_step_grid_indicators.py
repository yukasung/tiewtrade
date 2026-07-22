from datetime import UTC, datetime
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import WilderIndicators
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


def candle(
    minute: int,
    close: str,
    high: str,
    low: str,
) -> Candle:
    return Candle(
        symbol="CONFIGURED_SYMBOL",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def short_preset() -> RsiStepGridPreset:
    return RsiStepGridPreset(
        version="test-v1",
        rsi_period=3,
        rsi_reset_threshold=Decimal("30"),
        rsi_entry_threshold=Decimal("50"),
        atr_period=3,
        take_profit_atr_multiplier=Decimal("3"),
    )


def test_wilder_indicators_wait_for_rsi_changes_and_true_range_samples() -> None:
    indicators = WilderIndicators(short_preset())

    assert indicators.update(candle(0, "10", "11", "9")) is None
    assert indicators.update(candle(5, "14", "15", "13")) is None
    assert indicators.update(candle(10, "13", "14", "12")) is None

    snapshot = indicators.update(candle(15, "14", "14.5", "13.5"))

    assert snapshot is not None
    assert snapshot.rsi.quantize(Decimal("0.0001")) == Decimal("83.3333")
    assert snapshot.atr == Decimal("2.5")


def test_wilder_smoothing_uses_previous_averages_after_warm_up() -> None:
    indicators = WilderIndicators(short_preset())
    for value in [
        candle(0, "10", "11", "9"),
        candle(5, "9", "10", "8"),
        candle(10, "8", "9", "7"),
    ]:
        assert indicators.update(value) is None

    first = indicators.update(candle(15, "9", "10", "8"))
    second = indicators.update(candle(20, "10", "11", "9"))

    assert first is not None
    assert first.rsi.quantize(Decimal("0.0001")) == Decimal("33.3333")
    assert first.atr == Decimal("2")
    assert second is not None
    assert second.rsi.quantize(Decimal("0.0001")) == Decimal("55.5556")
    assert second.atr == Decimal("2")
