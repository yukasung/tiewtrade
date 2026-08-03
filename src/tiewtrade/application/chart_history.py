from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.trade_history import TradeFill

LoadChartCandles = Callable[
    [ConfiguredPaperSession, ChartRange], Awaitable[tuple[Candle, ...]]
]
ListChartFills = Callable[[UUID, ChartRange], tuple[TradeFill, ...]]


class ChartHistory:
    def __init__(
        self,
        *,
        load_candles: LoadChartCandles,
        list_fills: ListChartFills,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._load_candles = load_candles
        self._list_fills = list_fills
        self._clock = clock

    async def load(
        self,
        session: ConfiguredPaperSession,
        chart_range: ChartRange,
    ) -> ChartSnapshot:
        candles = await self._load_candles(session, chart_range)
        fills = self._list_fills(
            session.config.session_id,
            chart_range,
        )
        return ChartSnapshot(
            session=session,
            chart_range=chart_range,
            observed_at_utc=self._clock(),
            candles=candles,
            fills=fills,
            state=ChartReadState.READY if candles else ChartReadState.EMPTY,
        )

    async def refresh_completed(
        self,
        session: ConfiguredPaperSession,
        snapshot: ChartSnapshot,
        candle: Candle,
    ) -> ChartSnapshot:
        if snapshot.session_id != session.config.session_id:
            raise ValueError("ChartSnapshot Session must match Session")
        chart_range = snapshot.chart_range
        candles = snapshot.candles
        if candle.open_time >= chart_range.end:
            reload_history = candle.open_time > chart_range.end
            duration = chart_range.end - chart_range.start
            chart_range = ChartRange(
                start=candle.close_time - duration,
                end=candle.close_time,
            )
            if reload_history:
                candles = await self._load_candles(session, chart_range)
        elif not (
            chart_range.start <= candle.open_time
            and candle.close_time <= chart_range.end
        ):
            return snapshot

        candles_by_open_time = {item.open_time: item for item in candles}
        candles_by_open_time[candle.open_time] = candle
        candles = tuple(
            candles_by_open_time[open_time]
            for open_time in sorted(candles_by_open_time)
            if chart_range.start <= open_time
            and candles_by_open_time[open_time].close_time <= chart_range.end
        )
        fills = self._list_fills(
            session.config.session_id,
            chart_range,
        )
        return ChartSnapshot(
            session=session,
            chart_range=chart_range,
            observed_at_utc=max(self._clock(), candle.close_time, chart_range.end),
            candles=candles,
            fills=fills,
            state=ChartReadState.READY if candles else ChartReadState.EMPTY,
        )
