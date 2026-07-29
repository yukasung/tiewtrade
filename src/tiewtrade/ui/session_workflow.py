from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.ui.background_task import BackgroundTask

CreateSession = Callable[[PaperSessionSetupValues], PaperSessionCreateOutcome]
LoadActiveSession = Callable[[], ConfiguredPaperSession | None]


class _Operation(Enum):
    LOAD = "load"
    CREATE = "create"


class SessionWorkflow(QObject):
    setup_required = Signal()
    session_ready = Signal(object)
    validation_failed = Signal(str, str)
    unavailable = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        *,
        create_session: CreateSession,
        load_active: LoadActiveSession,
        thread_pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._create_session = create_session
        self._load_active = load_active
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._active_task: BackgroundTask | None = None
        self._active_operation: _Operation | None = None
        self._active_generation: int | None = None
        self._callback_generation = 0
        self._closed = False

    @Slot()
    def start(self) -> None:
        self._start_task(_Operation.LOAD, self._load_active)

    def create(self, values: PaperSessionSetupValues) -> None:
        self._start_task(_Operation.CREATE, lambda: self._create_session(values))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._callback_generation += 1

    def _start_task(
        self,
        operation: _Operation,
        callback: Callable[[], object],
    ) -> None:
        if self._closed or self._active_task is not None:
            return
        task = BackgroundTask(callback)
        task.signals.succeeded.connect(self._task_succeeded)
        task.signals.failed.connect(self._task_failed)
        task.signals.finished.connect(self._task_finished)
        self._active_task = task
        self._active_operation = operation
        self._active_generation = self._callback_generation
        self.busy_changed.emit(True)
        self._thread_pool.start(task)

    @Slot(object)
    def _task_succeeded(self, result: object) -> None:
        if not self._callbacks_are_current():
            return
        if self._active_operation is _Operation.LOAD:
            self._load_succeeded(result)
            return
        self._create_succeeded(result)

    @Slot(object)
    def _task_failed(self, error: object) -> None:
        if not self._callbacks_are_current():
            return
        if self._active_operation is _Operation.LOAD:
            self._load_failed(error)
            return
        self._create_failed(error)

    @Slot()
    def _task_finished(self) -> None:
        task = self._active_task
        if task is None or self._active_generation is None:
            return
        callbacks_are_current = self._callbacks_are_current()
        task.signals.succeeded.disconnect(self._task_succeeded)
        task.signals.failed.disconnect(self._task_failed)
        task.signals.finished.disconnect(self._task_finished)
        self._active_task = None
        self._active_operation = None
        self._active_generation = None
        if callbacks_are_current:
            self.busy_changed.emit(False)

    def _load_succeeded(self, result: object) -> None:
        if result is None:
            self.setup_required.emit()
            return
        if isinstance(result, ConfiguredPaperSession):
            self.session_ready.emit(result)
            return
        self.unavailable.emit("Paper Session could not be loaded")

    def _create_succeeded(self, result: object) -> None:
        if isinstance(result, PaperSessionCreateOutcome) and isinstance(
            result.session, ConfiguredPaperSession
        ):
            self.session_ready.emit(result.session)
            return
        self.unavailable.emit("Paper Session could not be created")

    def _load_failed(self, error: object) -> None:
        if isinstance(error, PaperSessionUnavailableError):
            self.unavailable.emit("Session storage is unavailable")
            return
        self.unavailable.emit("Paper Session could not be loaded")

    def _create_failed(self, error: object) -> None:
        if isinstance(error, PaperSessionValidationError):
            self.validation_failed.emit(error.field, str(error))
            self.setup_required.emit()
            return
        if isinstance(error, PaperSessionUnavailableError):
            self.unavailable.emit("Session storage is unavailable")
            return
        self.unavailable.emit("Paper Session could not be created")

    def _callbacks_are_current(self) -> bool:
        return (
            not self._closed
            and self._active_task is not None
            and self._active_generation == self._callback_generation
        )
