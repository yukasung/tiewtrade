import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeGuard

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tiewtrade.application.chart_data import (
    ChartCandle,
    ChartRange,
    ChartReadState,
    ChartSnapshot,
    append_completed_candle,
    default_chart_range,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.ui.background_task import BackgroundTask

LoadChart = Callable[[ConfiguredPaperSession, ChartRange], Awaitable[ChartSnapshot]]
RefreshChart = Callable[
    [ConfiguredPaperSession, ChartSnapshot, ChartCandle],
    Awaitable[ChartSnapshot],
]


class ChartWorkflow(QObject):
    """Loads chart facts off the Qt thread and discards stale callbacks."""

    snapshot_changed = Signal(object)
    loading_changed = Signal(bool)

    def __init__(
        self,
        *,
        load_chart: LoadChart,
        refresh_chart: RefreshChart | None = None,
        thread_pool: QThreadPool | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._load_chart = load_chart
        self._refresh_chart = refresh_chart
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._clock = clock
        self._session: ConfiguredPaperSession | None = None
        self._snapshot: ChartSnapshot | None = None
        self._generation = 0
        self._active_task: BackgroundTask | None = None
        self._pending_request: tuple[int, ChartRange] | None = None
        self._pending_completed_candle: ChartCandle | None = None
        self._last_safe_range: ChartRange | None = None
        self._closed = False

    def configure(self, session: ConfiguredPaperSession) -> None:
        if self._closed:
            return
        self._generation += 1
        self._session = session
        self._snapshot = None
        self._pending_request = None
        self._pending_completed_candle = None
        self._last_safe_range = None

    def start(self, session: ConfiguredPaperSession) -> None:
        self.configure(session)
        self.load_range(default_chart_range(session, self._clock()))

    def load_range(self, chart_range: ChartRange) -> None:
        if self._closed or self._session is None:
            return
        self._generation += 1
        generation = self._generation
        self._last_safe_range = chart_range
        self._publish_loading(chart_range)
        if self._active_task is not None:
            self._pending_request = (generation, chart_range)
            return
        self._start_load(generation, chart_range)

    def retry(self) -> None:
        if self._closed or self._active_task is not None:
            return
        chart_range = self._last_safe_range
        if chart_range is not None:
            self.load_range(chart_range)

    def completed_candle(self, candle: object) -> None:
        snapshot = self._snapshot
        if not self._is_current_session_candle_fact(candle):
            return
        if self._active_task is not None or (
            snapshot is not None and snapshot.state is ChartReadState.LOADING
        ):
            pending = self._pending_completed_candle
            typed_candle = candle
            if pending is None or typed_candle.close_time > pending.close_time:
                self._pending_completed_candle = typed_candle
            return
        if (
            self._closed
            or self._session is None
            or snapshot is None
            or snapshot.state
            not in (
                {ChartReadState.READY, ChartReadState.EMPTY}
                if self._refresh_chart is not None
                else {ChartReadState.READY}
            )
            or not self._is_current_session_candle(candle, snapshot)
        ):
            return
        if self._refresh_chart is not None:
            refresh_chart = self._refresh_chart
            session = self._session
            if session is None:
                return
            self._generation += 1
            generation = self._generation
            task = BackgroundTask(
                lambda: asyncio.run(
                    self._refresh_in_background(
                        refresh_chart,
                        session,
                        snapshot,
                        candle,
                    )
                )
            )
            task.signals.succeeded.connect(
                lambda result: self._refresh_succeeded(generation, result)
            )
            task.signals.failed.connect(
                lambda error: self._refresh_failed(generation, snapshot, error)
            )
            task.signals.finished.connect(lambda: self._refresh_finished(task))
            self._active_task = task
            self.loading_changed.emit(True)
            self._thread_pool.start(task)
            return
        try:
            updated = append_completed_candle(snapshot, candle)
        except ValueError:
            return
        self._snapshot = updated
        self.snapshot_changed.emit(updated)

    def _refresh_succeeded(self, generation: int, result: object) -> None:
        session = self._session
        if (
            generation != self._generation
            or not isinstance(result, ChartSnapshot)
            or session is None
            or result.session_id != session.config.session_id
        ):
            return
        self._snapshot = result
        self._last_safe_range = result.chart_range
        self.snapshot_changed.emit(result)

    def _refresh_failed(
        self,
        generation: int,
        snapshot: ChartSnapshot,
        error: object,
    ) -> None:
        del error
        session = self._session
        if generation != self._generation or session is None:
            return
        self._pending_completed_candle = None
        unavailable = ChartSnapshot(
            session=session,
            chart_range=snapshot.chart_range,
            observed_at_utc=max(self._clock(), snapshot.chart_range.end),
            candles=(),
            fills=(),
            state=ChartReadState.UNAVAILABLE,
            message="Chart is unavailable",
        )
        self._snapshot = unavailable
        self.snapshot_changed.emit(unavailable)

    def _refresh_finished(self, task: BackgroundTask) -> None:
        if task is not self._active_task:
            return
        self._active_task = None
        pending = self._pending_request
        self._pending_request = None
        if self._closed:
            return
        if pending is not None:
            self._start_load(*pending)
            return
        self.loading_changed.emit(False)
        self._drain_pending_completed_candle()

    @Slot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        self._pending_request = None
        self._pending_completed_candle = None
        self._session = None

    def _start_load(self, generation: int, chart_range: ChartRange) -> None:
        session = self._session
        if session is None:
            return
        task = BackgroundTask(
            lambda: asyncio.run(self._load_in_background(session, chart_range))
        )
        task.signals.succeeded.connect(
            lambda result: self._load_succeeded(generation, chart_range, result)
        )
        task.signals.failed.connect(
            lambda error: self._load_failed(generation, chart_range, error)
        )
        task.signals.finished.connect(lambda: self._load_finished(task))
        self._active_task = task
        self.loading_changed.emit(True)
        self._thread_pool.start(task)

    def _publish_loading(self, chart_range: ChartRange) -> None:
        session = self._session
        if session is None:
            return
        loading = ChartSnapshot(
            session=session,
            chart_range=chart_range,
            observed_at_utc=max(self._clock(), chart_range.end),
            candles=(),
            fills=(),
            state=ChartReadState.LOADING,
        )
        self._snapshot = loading
        self.snapshot_changed.emit(loading)

    def _load_succeeded(
        self, generation: int, chart_range: ChartRange, result: object
    ) -> None:
        if generation != self._generation or not self._valid_snapshot(
            result, chart_range
        ):
            return
        self._snapshot = result
        self.snapshot_changed.emit(result)

    def _load_failed(
        self, generation: int, chart_range: ChartRange, error: object
    ) -> None:
        del error
        if generation != self._generation or self._session is None:
            return
        observed_at_utc = max(self._clock(), chart_range.end)
        unavailable = ChartSnapshot(
            session=self._session,
            chart_range=chart_range,
            observed_at_utc=observed_at_utc,
            candles=(),
            fills=(),
            state=ChartReadState.UNAVAILABLE,
            message="Chart is unavailable",
        )
        self._snapshot = unavailable
        self.snapshot_changed.emit(unavailable)

    def _load_finished(self, task: BackgroundTask) -> None:
        if task is not self._active_task:
            return
        self._active_task = None
        pending = self._pending_request
        self._pending_request = None
        if self._closed:
            return
        if pending is not None:
            self._start_load(*pending)
            return
        self.loading_changed.emit(False)
        self._drain_pending_completed_candle()

    async def _load_in_background(
        self, session: ConfiguredPaperSession, chart_range: ChartRange
    ) -> ChartSnapshot:
        return await self._load_chart(session, chart_range)

    async def _refresh_in_background(
        self,
        refresh_chart: RefreshChart,
        session: ConfiguredPaperSession,
        snapshot: ChartSnapshot,
        candle: ChartCandle,
    ) -> ChartSnapshot:
        return await refresh_chart(session, snapshot, candle)

    def _valid_snapshot(
        self, result: object, chart_range: ChartRange
    ) -> TypeGuard[ChartSnapshot]:
        return (
            isinstance(result, ChartSnapshot)
            and self._session is not None
            and result.session_id == self._session.config.session_id
            and result.chart_range == chart_range
        )

    def _is_current_session_candle(
        self, candle: object, snapshot: ChartSnapshot
    ) -> TypeGuard[ChartCandle]:
        return (
            self._is_current_session_candle_fact(candle)
            and candle.open_time >= snapshot.chart_range.start
        )

    def _is_current_session_candle_fact(
        self,
        candle: object,
    ) -> TypeGuard[ChartCandle]:
        return (
            isinstance(candle, ChartCandle)
            and self._session is not None
            and candle.symbol == self._session.market_data.symbol
            and candle.timeframe == self._session.market_data.timeframe
        )

    def _drain_pending_completed_candle(self) -> None:
        pending = self._pending_completed_candle
        self._pending_completed_candle = None
        if pending is not None:
            self.completed_candle(pending)
