from collections.abc import Callable
from datetime import UTC, datetime

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionSetupValues,
)
from tiewtrade.market_data.config import timeframe_to_interval
from tiewtrade.ui.background_task import BackgroundTask
from tiewtrade.ui.bot_lifecycle_workflow import (
    BotLifecycleWorkflow,
    LifecycleAction,
    RuntimeSnapshotRelay,
)
from tiewtrade.ui.chart_workflow import ChartWorkflow, LoadChart
from tiewtrade.ui.session_workflow import (
    CreateSession,
    LoadActiveSession,
    SessionWorkflow,
)
from tiewtrade.ui.trade_history_workflow import (
    ListBaskets,
    ListFills,
    TradeHistoryWorkflow,
)
from tiewtrade.ui.trading_workspace import TradingWorkspace

WORKER_SHUTDOWN_TIMEOUT_MS = 5_000


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        create_session: CreateSession,
        load_active: LoadActiveSession,
        list_baskets: ListBaskets,
        list_fills: ListFills,
        start_bot: LifecycleAction | None = None,
        stop_bot: LifecycleAction | None = None,
        recover_bot: LifecycleAction | None = None,
        initialize_bot: LifecycleAction | None = None,
        runtime_snapshots: RuntimeSnapshotRelay | None = None,
        shutdown_runtime: Callable[[], None] | None = None,
        load_chart: LoadChart | None = None,
        chart_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._load_chart = load_chart
        self._chart_clock = chart_clock
        self._shutdown_runtime = shutdown_runtime
        self._close_sequence_started = False
        self._close_sequence_completed = False
        self._shutdown_task: BackgroundTask | None = None
        self._runtime_shutdown_pool = QThreadPool(self)
        self._runtime_shutdown_pool.setMaxThreadCount(1)
        self.workspace = TradingWorkspace()
        self.setup = self.workspace.setup
        self.overview = self.workspace.overview
        self.trade_history = self.workspace.trade_history
        self.unavailable_panel = self.workspace.unavailable_panel
        self.unavailable_message = self.workspace.unavailable_message
        self.unavailable_retry_button = self.workspace.unavailable_retry_button
        self.setCentralWidget(self.workspace)
        self.setWindowTitle("TiewTrade")
        self.setMinimumSize(1024, 700)
        self.resize(1440, 900)
        self._pending_validation_field: str | None = None

        self._workflow = SessionWorkflow(
            create_session=create_session,
            load_active=load_active,
            thread_pool=self._thread_pool,
            parent=self,
        )
        self._workflow.busy_changed.connect(self._set_busy)
        self._workflow.workspace_changed.connect(self.workspace.show_workspace_snapshot)
        self._workflow.setup_required.connect(self._show_setup)
        self._workflow.session_ready.connect(self._show_session)
        self._workflow.validation_failed.connect(self._show_validation_error)
        self._workflow.unavailable.connect(self._show_unavailable)
        self.setup.create_requested.connect(self._create_requested)
        self.unavailable_retry_button.clicked.connect(self._workflow.start)

        self._lifecycle_workflow = BotLifecycleWorkflow(
            start_bot=start_bot,
            stop_bot=stop_bot,
            recover=recover_bot,
            initialize_bot=initialize_bot,
            runtime_snapshots=runtime_snapshots,
            thread_pool=self._thread_pool,
            parent=self,
        )
        self._lifecycle_workflow.snapshot_changed.connect(
            self.workspace.show_bot_control_snapshot
        )
        self._lifecycle_workflow.notifications_changed.connect(
            self.workspace.show_notifications
        )
        self.workspace.start_bot_requested.connect(self._lifecycle_workflow.start_bot)
        self.workspace.stop_bot_requested.connect(self._lifecycle_workflow.stop_bot)
        self.workspace.recover_requested.connect(self._lifecycle_workflow.recover)

        self._chart_workflow = ChartWorkflow(
            load_chart=load_chart or _unused_chart_loader,
            thread_pool=self._thread_pool,
            clock=chart_clock,
            parent=self,
        )
        self._chart_workflow.snapshot_changed.connect(
            self.workspace.chart.show_snapshot
        )
        self.workspace.chart.range_requested.connect(self._chart_workflow.load_range)

        self._history_started = False
        self._history_workflow = TradeHistoryWorkflow(
            list_baskets=list_baskets,
            list_fills=list_fills,
            thread_pool=self._thread_pool,
            parent=self,
        )
        self._wire_trade_history()
        self.workspace.trade_history_activated.connect(self._start_trade_history_once)
        self._workflow.start()

    @Slot(object)
    def _create_requested(self, raw_values: object) -> None:
        if not isinstance(raw_values, PaperSessionSetupValues):
            return

        self._pending_validation_field = None
        self.setup.clear_errors()
        self._workflow.create(raw_values)

    @Slot(bool)
    def _set_busy(self, busy: bool) -> None:
        self.workspace.set_bot_busy(busy)
        if busy or self._pending_validation_field is None:
            return
        validation_field = self._pending_validation_field
        self._pending_validation_field = None
        self.workspace.show_setup_for_validation(validation_field)

    @Slot(object)
    def _show_session(self, session: ConfiguredPaperSession) -> None:
        self._pending_validation_field = None
        self._lifecycle_workflow.configure(session)
        if self._load_chart is not None:
            self._chart_workflow.configure(session)
            self._chart_workflow.load_range(
                _initial_chart_range(session, self._chart_clock())
            )

    @Slot(str, str)
    def _show_validation_error(self, field: str, message: str) -> None:
        self.setup.show_field_error(field, message)
        self._pending_validation_field = field

    def _show_unavailable(self, message: str) -> None:
        self._pending_validation_field = None
        self.workspace.show_unavailable(message)

    @Slot()
    def _show_setup(self) -> None:
        self.workspace.show_setup()

    @Slot()
    def _start_trade_history_once(self) -> None:
        if self._history_started:
            return
        self._history_started = True
        self._history_workflow.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._close_sequence_completed:
            event.ignore()
            if not self._close_sequence_started:
                self._close_sequence_started = True
                self._close_workflows()
                if self._shutdown_runtime is None:
                    self._start_worker_drain()
                else:
                    task = BackgroundTask(self._shutdown_runtime)
                    task.signals.finished.connect(self._runtime_shutdown_finished)
                    self._shutdown_task = task
                    self._runtime_shutdown_pool.start(task)
            return
        super().closeEvent(event)

    def _close_workflows(self) -> None:
        self._workflow.close()
        self._lifecycle_workflow.close()
        self._history_workflow.close()
        self._chart_workflow.close()

    @Slot()
    def _runtime_shutdown_finished(self) -> None:
        self._shutdown_task = None
        self._start_worker_drain()

    def _start_worker_drain(self) -> None:
        task = BackgroundTask(
            lambda: self._thread_pool.waitForDone(WORKER_SHUTDOWN_TIMEOUT_MS)
        )
        task.signals.finished.connect(self._close_sequence_finished)
        self._shutdown_task = task
        self._runtime_shutdown_pool.start(task)

    @Slot()
    def _close_sequence_finished(self) -> None:
        self._close_sequence_completed = True
        self._shutdown_task = None
        self.close()

    def _wire_trade_history(self) -> None:
        self.trade_history.apply_filters_requested.connect(
            self._history_workflow.apply_filters
        )
        self.trade_history.reset_requested.connect(self._history_workflow.reset_filters)
        self.trade_history.page_requested.connect(self._history_workflow.go_to_page)
        self.trade_history.basket_selected.connect(self._history_workflow.select_basket)
        self.trade_history.baskets_retry_requested.connect(
            self._history_workflow.retry_baskets
        )
        self.trade_history.fills_retry_requested.connect(
            self._history_workflow.retry_fills
        )
        self._history_workflow.baskets_loading.connect(
            self.trade_history.set_baskets_loading
        )
        self._history_workflow.baskets_ready.connect(self.trade_history.show_baskets)
        self._history_workflow.baskets_empty.connect(
            self.trade_history.show_baskets_empty
        )
        self._history_workflow.baskets_unavailable.connect(
            self.trade_history.show_baskets_unavailable
        )
        self._history_workflow.filter_invalid.connect(
            self.trade_history.show_filter_error
        )
        self._history_workflow.fills_loading.connect(
            self.trade_history.set_fills_loading
        )
        self._history_workflow.fills_ready.connect(self.trade_history.show_fills)
        self._history_workflow.fills_empty.connect(self.trade_history.show_fills_empty)
        self._history_workflow.fills_unavailable.connect(
            self.trade_history.show_fills_unavailable
        )


async def _unused_chart_loader(
    session: ConfiguredPaperSession, chart_range: ChartRange
) -> ChartSnapshot:
    return ChartSnapshot(
        session=session,
        chart_range=chart_range,
        observed_at_utc=chart_range.end,
        candles=(),
        fills=(),
        state=ChartReadState.UNAVAILABLE,
        message="Chart is unavailable",
    )


def _initial_chart_range(
    session: ConfiguredPaperSession, observed_at_utc: datetime
) -> ChartRange:
    interval = timeframe_to_interval(session.market_data.timeframe)
    elapsed = observed_at_utc - datetime(1970, 1, 1, tzinfo=UTC)
    completed_end = datetime(1970, 1, 1, tzinfo=UTC) + (elapsed // interval) * interval
    return ChartRange(
        start=completed_end - interval * 120,
        end=completed_end,
    )
