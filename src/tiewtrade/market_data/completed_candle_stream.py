from datetime import datetime, timedelta
from enum import StrEnum

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig


class CandleGapError(ValueError):
    """Raised when the next candle is not contiguous with the last accepted one."""


class CandleAcceptance(StrEnum):
    ACCEPTED = "accepted"
    NOT_CLOSED = "not_closed"
    DUPLICATE_OR_OUT_OF_ORDER = "duplicate_or_out_of_order"


class CompletedCandleStream:
    def __init__(self, config: MarketDataConfig) -> None:
        self._config = config
        self._last_open_time: datetime | None = None

    def accept(self, candle: Candle, received_at: datetime) -> CandleAcceptance:
        if received_at.tzinfo is None or received_at.utcoffset() != timedelta(0):
            raise ValueError("received_at must use UTC")
        if candle.symbol != self._config.symbol:
            raise ValueError("candle symbol does not match market data configuration")
        if candle.timeframe != self._config.timeframe:
            raise ValueError(
                "candle timeframe does not match market data configuration"
            )
        if received_at < candle.close_time:
            return CandleAcceptance.NOT_CLOSED
        if self._last_open_time is not None:
            if candle.open_time <= self._last_open_time:
                return CandleAcceptance.DUPLICATE_OR_OUT_OF_ORDER
            expected = self._last_open_time + self._config.interval
            if candle.open_time != expected:
                raise CandleGapError(f"missing candle beginning {expected.isoformat()}")
        self._last_open_time = candle.open_time
        return CandleAcceptance.ACCEPTED
