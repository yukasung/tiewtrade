import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol, TypeGuard, cast, runtime_checkable

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
    append_completed_candle,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.ui.background_task import BackgroundTask

LoadChart = Callable[[ConfiguredPaperSession, ChartRange], Awaitable[ChartSnapshot]]


@runtime_checkable
class CompletedCandleFacts(Protocol):
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime


class ChartWorkflow(QObject):
    """Loads chart facts off the Qt thread and discards stale callbacks."""

    snapshot_changed = Signal(object)
    loading_changed = Signal(bool)

    def __init__(
        self,
        *,
        load_chart: LoadChart,
        thread_pool: QThreadPool | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._load_chart = load_chart
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._clock = clock
        self._session: ConfiguredPaperSession | None = None
        self._snapshot: ChartSnapshot | None = None
        self._generation = 0
        self._active_task: BackgroundTask | None = None
        self._pending_request: tuple[int, ChartRange] | None = None
        self._closed = False

    def configure(self, session: ConfiguredPaperSession) -> None:
        if self._closed:
            return
        self._generation += 1
        self._session = session
        self._snapshot = None
        self._pending_request = None

    def load_range(self, chart_range: ChartRange) -> None:
        if self._closed or self._session is None:
            return
        self._generation += 1
        generation = self._generation
        if self._active_task is not None:
            self._pending_request = (generation, chart_range)
            return
        self._start_load(generation, chart_range)

    def completed_candle(self, candle: object) -> None:
        snapshot = self._snapshot
        if (
            self._closed
            or self._session is None
            or snapshot is None
            or snapshot.state is not ChartReadState.READY
            or not self._is_current_session_candle(candle, snapshot)
        ):
            return
        try:
            updated = append_completed_candle(snapshot, cast(Any, candle))
        except ValueError:
            return
        self._snapshot = updated
        self.snapshot_changed.emit(updated)

    @Slot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        self._pending_request = None
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

    async def _load_in_background(
        self, session: ConfiguredPaperSession, chart_range: ChartRange
    ) -> ChartSnapshot:
        return await self._load_chart(session, chart_range)

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
    ) -> TypeGuard[CompletedCandleFacts]:
        return (
            isinstance(candle, CompletedCandleFacts)
            and self._session is not None
            and candle.symbol == self._session.market_data.symbol
            and candle.timeframe == self._session.market_data.timeframe
            and candle.open_time >= snapshot.chart_range.start
            and candle.close_time <= snapshot.chart_range.end
        )
