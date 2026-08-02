from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.trade_history import TradeFill


class ChartCandleSource(Protocol):
    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]: ...

    async def close(self) -> None: ...


class ChartFillHistory(Protocol):
    def list_session_fills(
        self,
        session_id: UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> tuple[TradeFill, ...]: ...


class ChartHistory:
    def __init__(
        self,
        *,
        source: ChartCandleSource,
        trade_history: ChartFillHistory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._source = source
        self._trade_history = trade_history
        self._clock = clock

    async def load(
        self,
        session: ConfiguredPaperSession,
        chart_range: ChartRange,
    ) -> ChartSnapshot:
        try:
            candles = await self._source.load_range(
                session.market_data,
                start=chart_range.start,
                end=chart_range.end,
            )
        finally:
            await self._source.close()
        fills = self._trade_history.list_session_fills(
            session.config.session_id,
            chart_range.start,
            chart_range.end,
        )
        return ChartSnapshot(
            session=session,
            chart_range=chart_range,
            observed_at_utc=self._clock(),
            candles=candles,
            fills=fills,
            state=ChartReadState.READY if candles else ChartReadState.EMPTY,
        )
