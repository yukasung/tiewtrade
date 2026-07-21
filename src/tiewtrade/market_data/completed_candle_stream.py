from datetime import datetime, timedelta

from tiewtrade.market_data.candle import CANDLE_INTERVAL, Candle


class CandleGapError(ValueError):
    """Raised when the next candle is not contiguous with the last accepted one."""


class CompletedCandleStream:
    def __init__(self) -> None:
        self._last_open_time: datetime | None = None

    def accept(self, candle: Candle, received_at: datetime) -> bool:
        if received_at.tzinfo is None or received_at.utcoffset() != timedelta(0):
            raise ValueError("received_at must use UTC")
        if received_at < candle.close_time:
            return False
        if self._last_open_time is not None:
            if candle.open_time <= self._last_open_time:
                return False
            expected = self._last_open_time + CANDLE_INTERVAL
            if candle.open_time != expected:
                raise CandleGapError(
                    f"missing candle beginning {expected.isoformat()}"
                )
        self._last_open_time = candle.open_time
        return True
