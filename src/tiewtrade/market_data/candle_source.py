from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig


class HistoricalCandleSource(Protocol):
    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]: ...

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]: ...

    async def close(self) -> None: ...


class LiveCandleSource(Protocol):
    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]: ...


class MarketDataCandleSource(HistoricalCandleSource, LiveCandleSource, Protocol):
    pass
