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


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        create_session: CreateSession,
        load_active: LoadActiveSession,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.navigation_items = ("Session",)
        self.current_page_name = "Session Setup"
        self.setup = SessionSetupWidget()
        self.overview = SessionOverviewWidget()
        self.unavailable_panel = QFrame()
        self.unavailable_panel.setObjectName("unavailablePanel")
        self.unavailable_message = QLabel()
        self.unavailable_message.setObjectName("unavailableMessage")
        self.unavailable_message.setWordWrap(True)
        self.unavailable_retry_button = QPushButton("Try Again")
        self.unavailable_retry_button.setObjectName("unavailableRetryButton")

        self._pages = QStackedWidget()
        self._pages.addWidget(self.setup)
        self._pages.addWidget(self.overview)
        self._pages.addWidget(self.unavailable_panel)
        self._pages.setCurrentWidget(self.setup)

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
        self._workflow.start()

    @Slot(object)
    def _create_requested(self, raw_values: object) -> None:
        if not isinstance(raw_values, PaperSessionSetupValues):
            return

        self.setup.clear_errors()
        self._workflow.create(raw_values)

    @Slot(bool)
    def _set_busy(self, busy: bool) -> None:
        if busy or self.current_page_name == "Session Setup":
            self.setup.set_loading(busy)
        self.unavailable_retry_button.setDisabled(busy)

    @Slot(object)
    def _show_session(self, session: ConfiguredPaperSession) -> None:
        self.overview.show_session(session)
        self._pages.setCurrentWidget(self.overview)
        self.current_page_name = "Session Overview"

    @Slot(str, str)
    def _show_validation_error(self, field: str, message: str) -> None:
        self.setup.show_field_error(field, message)

    def _show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self._pages.setCurrentWidget(self.unavailable_panel)
        self.current_page_name = "Unavailable"

    @Slot()
    def _show_setup(self) -> None:
        self._pages.setCurrentWidget(self.setup)
        self.current_page_name = "Session Setup"

    def closeEvent(self, event: QCloseEvent) -> None:
        self._workflow.close()
        super().closeEvent(event)

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
        session_button = QPushButton("Session")
        session_button.setObjectName("navigationButtonSelected")
        session_button.setEnabled(False)
        navigation_layout.addWidget(brand)
        navigation_layout.addSpacing(24)
        navigation_layout.addWidget(session_button)
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
