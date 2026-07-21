from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

CANDLE_INTERVAL = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.symbol != "BTCUSDT":
            raise ValueError("symbol must be BTCUSDT")
        if self.open_time.tzinfo is None or self.open_time.utcoffset() != timedelta(0):
            raise ValueError("open_time must use UTC")
        if self.open_time.second or self.open_time.microsecond:
            raise ValueError("open_time must align to a minute")
        if self.open_time.minute % 5:
            raise ValueError("open_time must align to a 5-minute boundary")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.high < max(self.open, self.close) or self.low > min(
            self.open, self.close
        ):
            raise ValueError("OHLC range is invalid")
        if self.volume < 0:
            raise ValueError("volume must not be negative")

    @property
    def close_time(self) -> datetime:
        return self.open_time + CANDLE_INTERVAL
