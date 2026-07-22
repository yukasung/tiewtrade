from decimal import Decimal
from pathlib import Path

import pytest

from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.replay.csv_candles import load_candles_csv


def write_csv(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / "candles.csv"
    path.write_text(contents, encoding="utf-8")
    return path


def test_loads_utc_candle_with_market_identity_from_configuration(
    tmp_path: Path,
) -> None:
    path = write_csv(
        tmp_path,
        "open_time,open,high,low,close,volume\n"
        "2026-01-01T00:00:00+00:00,100.10,102.20,99.90,101.00,123.4500\n",
    )

    candles = load_candles_csv(path, MarketDataConfig(symbol="ETHUSDT", timeframe="5m"))

    assert isinstance(candles, tuple)
    assert candles[0].symbol == "ETHUSDT"
    assert candles[0].timeframe == "5m"
    assert candles[0].open == Decimal("100.10")
    assert candles[0].open.as_tuple().exponent == -2
    assert candles[0].volume == Decimal("123.4500")
    assert candles[0].volume.as_tuple().exponent == -4


@pytest.mark.parametrize(
    "header",
    [
        "open_time,open,high,low,close",
        "open_time,open,high,low,close,volume,extra",
        "open,open_time,high,low,close,volume",
    ],
)
def test_rejects_missing_extra_or_reordered_header(tmp_path: Path, header: str) -> None:
    path = write_csv(tmp_path, f"{header}\n")

    with pytest.raises(
        ValueError, match="CSV header must be open_time,open,high,low,close,volume"
    ):
        load_candles_csv(path, MarketDataConfig(symbol="ETHUSDT", timeframe="5m"))


@pytest.mark.parametrize(
    "row",
    [
        "2026-01-01T00:00:00,100,102,99,101,10",
        "2026-01-01T00:00:00+00:00,not-a-decimal,102,99,101,10",
        "2026-01-01T00:00:00+00:00,100,102,99,101",
    ],
)
def test_rejects_invalid_row_with_its_csv_row_number(tmp_path: Path, row: str) -> None:
    path = write_csv(
        tmp_path,
        f"open_time,open,high,low,close,volume\n{row}\n",
    )

    with pytest.raises(ValueError, match="invalid CSV row 2:"):
        load_candles_csv(path, MarketDataConfig(symbol="ETHUSDT", timeframe="5m"))


def test_rejects_header_only_csv(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "open_time,open,high,low,close,volume\n")

    with pytest.raises(ValueError, match="CSV must contain at least one candle"):
        load_candles_csv(path, MarketDataConfig(symbol="ETHUSDT", timeframe="5m"))
