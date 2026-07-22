from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import WilderIndicators
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


def candle(index: int, close: int) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="CONFIGURED_SYMBOL",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5),
        open=price,
        high=price + Decimal("1"),
        low=price - Decimal("1"),
        close=price,
        volume=Decimal("1"),
    )


@pytest.mark.parametrize(
    ("closes", "expected_rsi"),
    [
        ([100] * 15, Decimal("50")),
        (list(range(100, 115)), Decimal("100")),
        (list(range(114, 99, -1)), Decimal("0")),
    ],
)
def test_v1_waits_for_fourteen_price_changes_and_true_range_samples(
    closes: list[int], expected_rsi: Decimal
) -> None:
    indicators = WilderIndicators(RsiStepGridPreset.v1())

    for index, close in enumerate(closes[:-1]):
        assert indicators.update(candle(index, close)) is None

    snapshot = indicators.update(candle(14, closes[-1]))

    assert snapshot is not None
    assert snapshot.rsi == expected_rsi
    assert snapshot.atr == Decimal("2")


def test_wilder_smoothing_uses_previous_averages_and_gap_true_range() -> None:
    indicators = WilderIndicators(RsiStepGridPreset.v1())
    alternating_closes = [100, 101] * 7 + [100]

    for index, close in enumerate(alternating_closes[:-1]):
        assert indicators.update(candle(index, close)) is None

    first = indicators.update(candle(14, alternating_closes[-1]))
    second = indicators.update(candle(15, 110))

    assert first is not None
    assert first.rsi == Decimal("50")
    assert first.atr == Decimal("2")
    assert second is not None
    assert second.rsi.quantize(Decimal("0.0001")) == Decimal("71.7391")
    assert second.atr == Decimal("37") / Decimal("14")
