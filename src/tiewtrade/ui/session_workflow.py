from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tiewtrade.application.database_compatibility import DatabaseCompatibilityError
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.application.trading_workspace import (
    TradingWorkspaceSnapshot,
    WorkspaceReadState,
    configured_workspace_snapshot,
    empty_workspace_snapshot,
    failed_workspace_snapshot,
    loading_workspace_snapshot,
)
from tiewtrade.ui.background_task import BackgroundTask

CreateSession = Callable[[PaperSessionSetupValues], PaperSessionCreateOutcome]
LoadActiveSession = Callable[[], ConfiguredPaperSession | None]
_NEWER_DATABASE_MESSAGE = "Database was created by a newer version of TiewTrade"


class _Operation(Enum):
    LOAD = "load"
    CREATE = "create"


class SessionWorkflow(QObject):
    setup_required = Signal()
    session_ready = Signal(object)
    validation_failed = Signal(str, str)
    unavailable = Signal(str)
    busy_changed = Signal(bool)
    workspace_changed = Signal(object)

    def __init__(
        self,
        *,
        create_session: CreateSession,
        load_active: LoadActiveSession,
        thread_pool: QThreadPool | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._create_session = create_session
        self._load_active = load_active
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._clock = clock
        self._last_known_workspace: TradingWorkspaceSnapshot | None = None
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
        if operation is _Operation.LOAD:
            self._publish_workspace(
                loading_workspace_snapshot(self._last_known_or_empty_workspace())
            )
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
            self._publish_workspace(
                empty_workspace_snapshot(observed_at_utc=self._clock())
            )
            self.setup_required.emit()
            return
        if isinstance(result, ConfiguredPaperSession):
            self._publish_workspace(
                configured_workspace_snapshot(result, observed_at_utc=self._clock())
            )
            self.session_ready.emit(result)
            return
        self._publish_load_failure("Paper Session could not be loaded")

    def _create_succeeded(self, result: object) -> None:
        if isinstance(result, PaperSessionCreateOutcome) and isinstance(
            result.session, ConfiguredPaperSession
        ):
            self._publish_workspace(
                configured_workspace_snapshot(
                    result.session,
                    observed_at_utc=self._clock(),
                )
            )
            self.session_ready.emit(result.session)
            return
        self._publish_create_failure("Paper Session could not be created")

    def _load_failed(self, error: object) -> None:
        if isinstance(error, DatabaseCompatibilityError):
            self._publish_load_failure(_NEWER_DATABASE_MESSAGE)
            return
        if isinstance(error, PaperSessionUnavailableError):
            self._publish_load_failure("Session storage is unavailable")
            return
        self._publish_load_failure("Paper Session could not be loaded")

    def _create_failed(self, error: object) -> None:
        if isinstance(error, PaperSessionValidationError):
            self.validation_failed.emit(error.field, str(error))
            self.setup_required.emit()
            return
        if isinstance(error, DatabaseCompatibilityError):
            self._publish_create_failure(_NEWER_DATABASE_MESSAGE)
            return
        if isinstance(error, PaperSessionUnavailableError):
            self._publish_create_failure("Session storage is unavailable")
            return
        self._publish_create_failure("Paper Session could not be created")

    def _publish_load_failure(self, message: str) -> None:
        self._publish_workspace(
            failed_workspace_snapshot(self._last_known_or_empty_workspace(), message)
        )
        self.unavailable.emit(message)

    def _publish_create_failure(self, message: str) -> None:
        self._publish_workspace(
            failed_workspace_snapshot(self._last_known_or_empty_workspace(), message)
        )
        self.unavailable.emit(message)

    def _last_known_or_empty_workspace(self) -> TradingWorkspaceSnapshot:
        if self._last_known_workspace is not None:
            return self._last_known_workspace
        return empty_workspace_snapshot(observed_at_utc=self._clock())

    def _publish_workspace(self, snapshot: TradingWorkspaceSnapshot) -> None:
        if snapshot.read_state in {
            WorkspaceReadState.EMPTY,
            WorkspaceReadState.READY,
            WorkspaceReadState.STALE,
        }:
            self._last_known_workspace = snapshot
        self.workspace_changed.emit(snapshot)

    def _callbacks_are_current(self) -> bool:
        return (
            not self._closed
            and self._active_task is not None
            and self._active_generation == self._callback_generation
        )
