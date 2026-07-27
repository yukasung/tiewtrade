from collections.abc import Callable

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
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.ui.session_overview import SessionOverviewWidget
from tiewtrade.ui.session_setup import SessionSetupWidget
from tiewtrade.ui.session_tasks import SessionTask

CreateSession = Callable[[PaperSessionSetupValues], PaperSessionCreateOutcome]
LoadActiveSession = Callable[[], ConfiguredPaperSession | None]


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        create_session: CreateSession,
        load_active: LoadActiveSession,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self._create_session = create_session
        self._load_active = load_active
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[SessionTask] = set()
        self._active_create_task: SessionTask | None = None
        self._active_load_task: SessionTask | None = None
        self._callback_generation = 0
        self._closed = False

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
        self.setup.create_requested.connect(self._create_requested)
        self.unavailable_retry_button.clicked.connect(self._show_setup)
        self._start_load_active()

    @Slot(object)
    def _create_requested(self, raw_values: object) -> None:
        if (
            self._closed
            or self._active_create_task is not None
            or self._active_load_task is not None
        ):
            return
        if not isinstance(raw_values, PaperSessionSetupValues):
            return

        self.setup.clear_errors()
        self.setup.set_loading(True)

        generation = self._callback_generation
        task = SessionTask(lambda: self._create_session(raw_values))
        task.signals.succeeded.connect(
            lambda raw_outcome: self._create_succeeded(generation, raw_outcome)
        )
        task.signals.failed.connect(
            lambda raw_error: self._create_failed(generation, raw_error)
        )
        task.signals.finished.connect(lambda: self._create_finished(generation, task))
        self._active_create_task = task
        self._tasks.add(task)
        self._thread_pool.start(task)

    def _start_load_active(self) -> None:
        self.setup.set_loading(True)

        generation = self._callback_generation
        task = SessionTask(self._load_active)
        task.signals.succeeded.connect(
            lambda raw_session: self._load_succeeded(generation, raw_session)
        )
        task.signals.failed.connect(
            lambda raw_error: self._load_failed(generation, raw_error)
        )
        task.signals.finished.connect(lambda: self._load_finished(generation, task))
        self._active_load_task = task
        self._tasks.add(task)
        self._thread_pool.start(task)

    def _create_succeeded(self, generation: int, raw_outcome: object) -> None:
        if not self._callbacks_are_current(generation):
            return
        if not isinstance(raw_outcome, PaperSessionCreateOutcome):
            self._show_unavailable("Paper Session could not be created")
            return
        self.overview.show_session(raw_outcome.session)
        self._pages.setCurrentWidget(self.overview)
        self.current_page_name = "Session Overview"

    def _create_failed(self, generation: int, raw_error: object) -> None:
        if not self._callbacks_are_current(generation):
            return
        self._show_error(raw_error)

    def _create_finished(self, generation: int, task: SessionTask) -> None:
        self._tasks.discard(task)
        if task is self._active_create_task:
            self._active_create_task = None
        if not self._callbacks_are_current(generation):
            return
        if self.current_page_name == "Session Setup":
            self.setup.set_loading(False)

    def _load_succeeded(self, generation: int, raw_session: object) -> None:
        if not self._callbacks_are_current(generation):
            return
        if raw_session is None:
            self._show_setup()
            return
        if not isinstance(raw_session, ConfiguredPaperSession):
            self._show_unavailable("Paper Session could not be created")
            return
        self.overview.show_session(raw_session)
        self._pages.setCurrentWidget(self.overview)
        self.current_page_name = "Session Overview"

    def _load_failed(self, generation: int, raw_error: object) -> None:
        if not self._callbacks_are_current(generation):
            return
        self._show_error(raw_error)

    def _load_finished(self, generation: int, task: SessionTask) -> None:
        self._tasks.discard(task)
        if task is self._active_load_task:
            self._active_load_task = None
        if not self._callbacks_are_current(generation):
            return
        if self.current_page_name == "Session Setup":
            self.setup.set_loading(False)

    def _show_error(self, raw_error: object) -> None:
        if isinstance(raw_error, PaperSessionValidationError):
            self.setup.show_field_error(raw_error.field, str(raw_error))
            self._show_setup()
            return
        if isinstance(raw_error, PaperSessionUnavailableError):
            self._show_unavailable("Session storage is unavailable")
            return
        self._show_unavailable("Paper Session could not be created")

    def _show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self._pages.setCurrentWidget(self.unavailable_panel)
        self.current_page_name = "Unavailable"

    @Slot()
    def _show_setup(self) -> None:
        if self._closed:
            return
        self._pages.setCurrentWidget(self.setup)
        self.current_page_name = "Session Setup"
        if self._active_create_task is None and self._active_load_task is None:
            self.setup.set_loading(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closed = True
        self._callback_generation += 1
        super().closeEvent(event)

    def _callbacks_are_current(self, generation: int) -> bool:
        return not self._closed and generation == self._callback_generation

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
