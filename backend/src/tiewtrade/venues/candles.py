"""Public candle observation contract; pages do not promise complete coverage."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from tiewtrade.core.market_data import Candle, CandleWindow, Timeframe
from tiewtrade.core.moments import require_aware
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.symbols import Symbol

DEFAULT_CANDLES_COST = CallCost(weight=1)


@dataclass(frozen=True, slots=True)
class CandlePage:
    symbol: Symbol
    timeframe: Timeframe
    window: CandleWindow
    candles: tuple[Candle, ...]
    received_at: datetime

    def __post_init__(self) -> None:
        require_aware("received_at", self.received_at)
        if not isinstance(self.timeframe, Timeframe):
            raise ValueError("unsupported timeframe")
        for candle in self.candles:
            if (candle.base, candle.quote, candle.timeframe) != (
                self.symbol.base,
                self.symbol.quote,
                self.timeframe,
            ) or not self.window.start <= candle.open_at < self.window.end:
                raise ValueError("candle outside requested series/window")


@dataclass(frozen=True, slots=True)
class CandleRequest:
    symbol: Symbol
    timeframe: Timeframe
    start: datetime
    end: datetime
    limit: int


def validate_request(
    timeframe: Timeframe, start: datetime, end: datetime, limit: int
) -> CandleWindow:
    if not isinstance(timeframe, Timeframe):
        raise ValueError("unsupported timeframe")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer from 1 to 1000")
    return CandleWindow(start, end)


@runtime_checkable
class CandleSource(Protocol):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage: ...
