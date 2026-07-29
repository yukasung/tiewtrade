from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionSetupValues,
)
from tiewtrade.ui.session_overview import SessionOverviewWidget
from tiewtrade.ui.session_setup import SessionSetupWidget
from tiewtrade.ui.session_workflow import (
    CreateSession,
    LoadActiveSession,
    SessionWorkflow,
)
from tiewtrade.ui.trade_history_page import TradeHistoryPage
from tiewtrade.ui.trade_history_workflow import (
    ListBaskets,
    ListFills,
    TradeHistoryWorkflow,
)


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
        self.navigation_items = ("Session", "Trade History")
        self.current_page_name = "Session Setup"
        self.setup = SessionSetupWidget()
        self.overview = SessionOverviewWidget()
        self.trade_history = TradeHistoryPage()
        self.unavailable_panel = QFrame()
        self.unavailable_panel.setObjectName("unavailablePanel")
        self.unavailable_message = QLabel()
        self.unavailable_message.setObjectName("unavailableMessage")
        self.unavailable_message.setWordWrap(True)
        self.unavailable_retry_button = QPushButton("Try Again")
        self.unavailable_retry_button.setObjectName("unavailableRetryButton")

        self._session_pages = QStackedWidget()
        self._session_pages.addWidget(self.setup)
        self._session_pages.addWidget(self.overview)
        self._session_pages.addWidget(self.unavailable_panel)
        self._session_pages.setCurrentWidget(self.setup)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._session_pages)
        self._pages.addWidget(self.trade_history)
        self._pages.setCurrentWidget(self._session_pages)

        self._build_window()
        self._workflow = SessionWorkflow(
            create_session=create_session,
            load_active=load_active,
            thread_pool=thread_pool,
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
            thread_pool=thread_pool,
            parent=self,
        )
        self._wire_trade_history()
        self._workflow.start()

    @Slot(object)
    def _create_requested(self, raw_values: object) -> None:
        if not isinstance(raw_values, PaperSessionSetupValues):
            return

        self.setup.clear_errors()
        self._workflow.create(raw_values)

    @Slot(bool)
    def _set_busy(self, busy: bool) -> None:
        if busy or self._session_pages.currentWidget() is self.setup:
            self.setup.set_loading(busy)
        self.unavailable_retry_button.setDisabled(busy)

    @Slot(object)
    def _show_session(self, session: ConfiguredPaperSession) -> None:
        self.overview.show_session(session)
        self._set_session_page(self.overview, "Session Overview")

    @Slot(str, str)
    def _show_validation_error(self, field: str, message: str) -> None:
        self.setup.show_field_error(field, message)

    def _show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self._set_session_page(self.unavailable_panel, "Unavailable")

    @Slot()
    def _show_setup(self) -> None:
        self._set_session_page(self.setup, "Session Setup")

    @Slot()
    def _show_session_page(self) -> None:
        self._pages.setCurrentWidget(self._session_pages)
        self.current_page_name = self._current_session_page_name()
        self._set_navigation_selection(session_selected=True)

    @Slot()
    def _show_trade_history_page(self) -> None:
        self._pages.setCurrentWidget(self.trade_history)
        self.current_page_name = "Trade History"
        self._set_navigation_selection(session_selected=False)
        if self._history_started:
            return
        self._history_started = True
        self._history_workflow.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._workflow.close()
        self._history_workflow.close()
        super().closeEvent(event)

    def _set_session_page(self, page: QWidget, page_name: str) -> None:
        self._session_pages.setCurrentWidget(page)
        if self._pages.currentWidget() is self._session_pages:
            self.current_page_name = page_name

    def _current_session_page_name(self) -> str:
        current_page = self._session_pages.currentWidget()
        if current_page is self.overview:
            return "Session Overview"
        if current_page is self.unavailable_panel:
            return "Unavailable"
        return "Session Setup"

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

    def _build_window(self) -> None:
        self.setWindowTitle("TiewTrade")
        self.setMinimumSize(960, 700)
        self.resize(1120, 780)

        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        navigation = QFrame()
        navigation.setObjectName("navigation")
        navigation.setFixedWidth(220)
        navigation_layout = QVBoxLayout(navigation)
        navigation_layout.setContentsMargins(24, 28, 24, 24)
        navigation_layout.setSpacing(12)
        brand = QLabel("TIEWTRADE")
        brand.setObjectName("brand")
        self.session_button = QPushButton("Session")
        self.trade_history_button = QPushButton("Trade History")
        self.session_button.clicked.connect(self._show_session_page)
        self.trade_history_button.clicked.connect(self._show_trade_history_page)
        self._set_navigation_selection(session_selected=True)
        navigation_layout.addWidget(brand)
        navigation_layout.addSpacing(24)
        navigation_layout.addWidget(self.session_button)
        navigation_layout.addWidget(self.trade_history_button)
        navigation_layout.addStretch()
        environment = QLabel("PAPER\nNo live orders")
        environment.setObjectName("environmentBadge")
        navigation_layout.addWidget(environment)

        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 32, 40, 32)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._pages)

        shell.addWidget(navigation)
        shell.addWidget(content, 1)
        self.setCentralWidget(central)

        unavailable_layout = QVBoxLayout(self.unavailable_panel)
        unavailable_layout.setContentsMargins(24, 24, 24, 24)
        unavailable_layout.setSpacing(12)
        heading = QLabel("Paper Session unavailable")
        heading.setObjectName("pageTitle")
        unavailable_layout.addWidget(heading)
        unavailable_layout.addWidget(self.unavailable_message)
        unavailable_layout.addWidget(self.unavailable_retry_button)
        unavailable_layout.addStretch()

    def _set_navigation_selection(self, *, session_selected: bool) -> None:
        self.session_button.setObjectName(
            "navigationButtonSelected" if session_selected else "navigationButton"
        )
        self.trade_history_button.setObjectName(
            "navigationButton" if session_selected else "navigationButtonSelected"
        )
        self.session_button.setDisabled(session_selected)
        self.trade_history_button.setDisabled(not session_selected)
        for button in (self.session_button, self.trade_history_button):
            button.style().unpolish(button)
            button.style().polish(button)
