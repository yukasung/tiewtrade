from collections.abc import Callable
from datetime import UTC, datetime

from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.candle_source import HistoricalCandleSource


class ChartHistory:
    def __init__(
        self,
        *,
        source_factory: Callable[[], HistoricalCandleSource],
        trade_history: SQLiteTradeHistory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._source_factory = source_factory
        self._trade_history = trade_history
        self._clock = clock

    async def load(
        self,
        session: ConfiguredPaperSession,
        chart_range: ChartRange,
    ) -> ChartSnapshot:
        source = self._source_factory()
        try:
            candles = await source.load_range(
                session.market_data,
                start=chart_range.start,
                end=chart_range.end,
            )
        finally:
            await source.close()
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

    async def refresh_completed(
        self,
        session: ConfiguredPaperSession,
        snapshot: ChartSnapshot,
        candle: Candle,
    ) -> ChartSnapshot:
        if snapshot.session_id != session.config.session_id:
            raise ValueError("ChartSnapshot Session must match Session")
        chart_range = snapshot.chart_range
        if candle.open_time == chart_range.end:
            duration = chart_range.end - chart_range.start
            chart_range = ChartRange(
                start=candle.close_time - duration,
                end=candle.close_time,
            )
        elif not (
            chart_range.start <= candle.open_time
            and candle.close_time <= chart_range.end
        ):
            return snapshot

        candles_by_open_time = {item.open_time: item for item in snapshot.candles}
        candles_by_open_time[candle.open_time] = candle
        candles = tuple(
            candles_by_open_time[open_time]
            for open_time in sorted(candles_by_open_time)
            if chart_range.start <= open_time
            and candles_by_open_time[open_time].close_time <= chart_range.end
        )
        fills = self._trade_history.list_session_fills(
            session.config.session_id,
            chart_range.start,
            chart_range.end,
        )
        return ChartSnapshot(
            session=session,
            chart_range=chart_range,
            observed_at_utc=max(self._clock(), candle.close_time, chart_range.end),
            candles=candles,
            fills=fills,
            state=ChartReadState.READY if candles else ChartReadState.EMPTY,
        )
