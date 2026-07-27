from collections.abc import Callable

from PySide6.QtCore import QThreadPool, Slot
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
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.ui.session_overview import SessionOverviewWidget
from tiewtrade.ui.session_setup import SessionSetupWidget
from tiewtrade.ui.session_tasks import SessionTask

CreateSession = Callable[[PaperSessionSetupValues], PaperSessionCreateOutcome]


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        create_session: CreateSession,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self._create_session = create_session
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[SessionTask] = set()
        self._active_create_task: SessionTask | None = None

        self.navigation_items = ("Session",)
        self.current_page_name = "Session Setup"
        self.setup = SessionSetupWidget()
        self.overview = SessionOverviewWidget()
        self.unavailable_message = QLabel()
        self.unavailable_message.setObjectName("unavailableMessage")
        self.unavailable_message.setWordWrap(True)
        self.unavailable_message.setVisible(False)

        self._pages = QStackedWidget()
        self._pages.addWidget(self.setup)
        self._pages.addWidget(self.overview)
        self._pages.setCurrentWidget(self.setup)

        self._build_window()
        self.setup.create_requested.connect(self._create_requested)

    @Slot(object)
    def _create_requested(self, raw_values: object) -> None:
        if self._active_create_task is not None:
            return
        if not isinstance(raw_values, PaperSessionSetupValues):
            return

        self.setup.clear_errors()
        self.unavailable_message.clear()
        self.unavailable_message.setVisible(False)
        self.setup.set_loading(True)

        task = SessionTask(lambda: self._create_session(raw_values))
        task.signals.succeeded.connect(self._create_succeeded)
        task.signals.failed.connect(self._create_failed)
        task.signals.finished.connect(self._create_finished)
        self._active_create_task = task
        self._tasks.add(task)
        self._thread_pool.start(task)

    @Slot(object)
    def _create_succeeded(self, raw_outcome: object) -> None:
        if not isinstance(raw_outcome, PaperSessionCreateOutcome):
            self._show_unavailable("Unable to create Paper Session")
            return
        self.overview.show_session(raw_outcome.session)
        self._pages.setCurrentWidget(self.overview)
        self.current_page_name = "Session Overview"

    @Slot(object)
    def _create_failed(self, raw_error: object) -> None:
        if isinstance(raw_error, PaperSessionValidationError):
            self.setup.show_field_error(raw_error.field, str(raw_error))
            return
        if isinstance(raw_error, PaperSessionUnavailableError):
            self._show_unavailable(str(raw_error))
            return
        self._show_unavailable("Unable to create Paper Session")

    @Slot()
    def _create_finished(self) -> None:
        task = self._active_create_task
        if task is not None:
            self._tasks.discard(task)
        self._active_create_task = None
        if self.current_page_name == "Session Setup":
            self.setup.set_loading(False)

    def _show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self.unavailable_message.setVisible(True)

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
        content_layout.addWidget(self.unavailable_message)
        content_layout.addWidget(self._pages)

        shell.addWidget(navigation)
        shell.addWidget(content, 1)
        self.setCentralWidget(central)
