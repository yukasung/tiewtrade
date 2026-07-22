import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig

CSV_HEADER = ("open_time", "open", "high", "low", "close", "volume")


def load_candles_csv(path: Path, config: MarketDataConfig) -> tuple[Candle, ...]:
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = csv.reader(source)
        header = next(rows, None)
        if header != list(CSV_HEADER):
            raise ValueError("CSV header must be open_time,open,high,low,close,volume")
        candles = tuple(
            _parse_candle(row, row_number, config)
            for row_number, row in enumerate(rows, start=2)
        )
    if not candles:
        raise ValueError("CSV must contain at least one candle")
    return candles


def _parse_candle(row: list[str], row_number: int, config: MarketDataConfig) -> Candle:
    if len(row) != len(CSV_HEADER):
        raise ValueError(f"invalid CSV row {row_number}: expected 6 columns")

    try:
        open_time = datetime.fromisoformat(row[0])
        open_price, high, low, close, volume = (Decimal(value) for value in row[1:])
        return Candle(
            symbol=config.symbol,
            timeframe=config.timeframe,
            open_time=open_time,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"invalid CSV row {row_number}: {error}") from error
