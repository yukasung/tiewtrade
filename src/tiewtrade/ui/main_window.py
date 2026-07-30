from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionSetupValues,
)
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
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
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
        self._workflow.setup_required.connect(self._show_setup)
        self._workflow.session_ready.connect(self._show_session)
        self._workflow.validation_failed.connect(self._show_validation_error)
        self._workflow.unavailable.connect(self._show_unavailable)
        self.setup.create_requested.connect(self._create_requested)
        self.unavailable_retry_button.clicked.connect(self._workflow.start)

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
        self.workspace.show_configured_session(session)

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
        self._workflow.close()
        self._history_workflow.close()
        self._thread_pool.waitForDone(WORKER_SHUTDOWN_TIMEOUT_MS)
        super().closeEvent(event)

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
