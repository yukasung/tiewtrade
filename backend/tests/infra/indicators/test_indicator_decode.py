from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import RowMapping

from tiewtrade.core.market_data import CandleSeries, Timeframe
from tiewtrade.infra.market_data.indicator_reader import decode_row


def row(*, numeric_text: bool) -> RowMapping:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    values: dict[str, Any] = {
        "source": "primary_spot",
        "base": "BTC",
        "quote": "USDT",
        "timeframe": "1m",
        "open_at": opened,
        "end_at": opened + timedelta(minutes=1),
        "open": Decimal("100.12500000"),
        "high": Decimal("101.25000000"),
        "low": Decimal("99.50000000"),
        "close": Decimal("100.62500000"),
        "volume": Decimal("2.75000000"),
        "finality": "CLOSED",
        "observed_at": opened + timedelta(minutes=1),
        "fetch_started_at": opened,
        "last_checked_at": opened + timedelta(minutes=1),
    }
    if numeric_text:
        for name in ("open", "high", "low", "close", "volume"):
            values[name] = str(values[name])
    return cast(RowMapping, values)


def test_decimal_and_text_numeric_rows_decode_identically() -> None:
    series = CandleSeries("BTC", "USDT", Timeframe.M1)

    assert decode_row(row(numeric_text=False), series) == decode_row(row(numeric_text=True), series)
