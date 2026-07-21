from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import (
    CandleGapError,
    CompletedCandleStream,
)


def candle_at(minute: int) -> Candle:
    opened = datetime(2026, 1, 1, 0, minute, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        open_time=opened,
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("10"),
    )


def test_accepts_only_closed_candles_and_deduplicates() -> None:
    stream = CompletedCandleStream()
    first = candle_at(0)

    assert not stream.accept(first, datetime(2026, 1, 1, 0, 4, 59, tzinfo=UTC))
    assert stream.accept(first, datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    assert not stream.accept(first, datetime(2026, 1, 1, 0, 6, tzinfo=UTC))


def test_rejects_a_gap_until_backfill_supplies_missing_candle() -> None:
    stream = CompletedCandleStream()
    assert stream.accept(candle_at(0), datetime(2026, 1, 1, 0, 5, tzinfo=UTC))

    with pytest.raises(CandleGapError, match="2026-01-01T00:05:00"):
        stream.accept(candle_at(10), datetime(2026, 1, 1, 0, 15, tzinfo=UTC))

    assert stream.accept(candle_at(5), datetime(2026, 1, 1, 0, 10, tzinfo=UTC))
    assert stream.accept(candle_at(10), datetime(2026, 1, 1, 0, 15, tzinfo=UTC))


def test_candle_requires_utc_and_valid_ohlc() -> None:
    with pytest.raises(ValueError, match="UTC"):
        Candle(
            symbol="BTCUSDT",
            open_time=datetime(2026, 1, 1),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("10"),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("symbol", "ETHUSDT", "symbol must be BTCUSDT"),
        ("open_time", datetime(2026, 1, 1, 0, 1, tzinfo=UTC), "5-minute boundary"),
        ("high", Decimal("100"), "OHLC range"),
        ("volume", Decimal("-1"), "volume must not be negative"),
    ],
)
def test_candle_rejects_invalid_market_data(
    field: str, value: object, message: str
) -> None:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "open_time": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        "open": Decimal("100"),
        "high": Decimal("102"),
        "low": Decimal("99"),
        "close": Decimal("101"),
        "volume": Decimal("10"),
    }
    values[field] = value

    with pytest.raises(ValueError, match=message):
        Candle(**values)  # type: ignore[arg-type]
