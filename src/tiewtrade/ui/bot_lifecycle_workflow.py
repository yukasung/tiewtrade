from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from enum import Enum
from threading import Lock

from PySide6.QtCore import QObject, Qt, QThreadPool, Signal, Slot

from tiewtrade.application.bot_control import (
    BotControlAction,
    BotControlSnapshot,
    BotLifecycleResult,
    blocked_bot_control,
    configured_bot_control,
    transition_bot_control,
    workspace_with_runtime_state,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.application.trading_workspace import BotRuntimeState
from tiewtrade.market_data.candle import Candle
from tiewtrade.ui.background_task import BackgroundTask
from tiewtrade.ui.notification_center import NotificationStore

LifecycleAction = Callable[[BotControlSnapshot], BotLifecycleResult]


class RuntimeSnapshotPublisher:
    def __init__(self, relay: "RuntimeSnapshotRelay", generation: int) -> None:
        self._relay = relay
        self._generation = generation

    def __call__(self, result: BotLifecycleResult) -> None:
        self._relay.snapshot_ready.emit(result, self._generation)

    def completed_candle(self, candle: Candle) -> None:
        self._relay.completed_candle_ready.emit(candle, self._generation)


class RuntimeSnapshotRelay(QObject):
    """Queue immutable runtime results onto the owning Qt thread."""

    snapshot_ready = Signal(object, int)
    completed_candle_ready = Signal(object, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = Lock()
        self._generation = 0

    def new_generation(self) -> RuntimeSnapshotPublisher:
        with self._lock:
            self._generation += 1
            generation = self._generation

        return RuntimeSnapshotPublisher(self, generation)

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1

    def is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation


class _LifecycleOperation(Enum):
    INITIALIZE = "initialize"
    START = "start"
    STOP = "stop"
    RECOVER = "recover"


class BotLifecycleWorkflow(QObject):
    snapshot_changed = Signal(object)
    busy_changed = Signal(bool)
    notifications_changed = Signal(object)

    def __init__(
        self,
        *,
        start_bot: LifecycleAction | None,
        stop_bot: LifecycleAction | None,
        recover: LifecycleAction | None,
        initialize_bot: LifecycleAction | None = None,
        runtime_snapshots: RuntimeSnapshotRelay | None = None,
        thread_pool: QThreadPool | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._start_bot = start_bot
        self._stop_bot = stop_bot
        self._recover = recover
        self._initialize_bot = initialize_bot
        self._runtime_snapshots = runtime_snapshots
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._clock = clock
        self._notification_store = NotificationStore()
        self._snapshot: BotControlSnapshot | None = None
        self._active_task: BackgroundTask | None = None
        self._active_operation: _LifecycleOperation | None = None
        self._task_generation: int | None = None
        self._generation = 0
        self._closed = False
        self._pending_runtime_result: tuple[int, BotLifecycleResult] | None = None
        if runtime_snapshots is not None:
            runtime_snapshots.snapshot_ready.connect(
                self._runtime_snapshot_received,
                Qt.ConnectionType.QueuedConnection,
            )

    @property
    def snapshot(self) -> BotControlSnapshot:
        if self._snapshot is None:
            raise RuntimeError("Bot Lifecycle Workflow has not been configured")
        return self._snapshot

    @property
    def notification_store(self) -> NotificationStore:
        return self._notification_store

    def configure(self, session: ConfiguredPaperSession) -> None:
        if self._closed:
            return
        active_task = self._active_task is not None
        self._invalidate_runtime_snapshots()
        self._generation += 1
        self._notification_store.reset_transition_identity()
        configured = configured_bot_control(
            session,
            observed_at_utc=self._clock(),
            actions=(
                frozenset()
                if active_task or self._initialize_bot is not None
                else self._actions_for(BotRuntimeState.CONFIGURED)
            ),
        )
        self._publish(configured)
        if not active_task and self._initialize_bot is not None:
            self._start_task(
                _LifecycleOperation.INITIALIZE,
                self._initialize_bot,
                configured,
            )

    @Slot()
    def start_bot(self) -> None:
        self._begin(
            _LifecycleOperation.START,
            BotControlAction.START,
            self._start_bot,
            BotRuntimeState.STARTING,
            "Starting Paper Bot",
        )

    @Slot()
    def stop_bot(self) -> None:
        self._begin(
            _LifecycleOperation.STOP,
            BotControlAction.STOP,
            self._stop_bot,
            BotRuntimeState.STOPPING,
            "Stopping Paper Bot",
        )

    @Slot()
    def recover(self) -> None:
        snapshot = self._snapshot
        if (
            self._closed
            or self._active_task is not None
            or snapshot is None
            or self._recover is None
            or BotControlAction.RECOVER not in snapshot.available_actions
        ):
            return
        self._invalidate_runtime_snapshots()
        self._start_task(_LifecycleOperation.RECOVER, self._recover, snapshot)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._invalidate_runtime_snapshots()
        self._generation += 1

    def _begin(
        self,
        operation: _LifecycleOperation,
        action_name: BotControlAction,
        action: LifecycleAction | None,
        intermediate_state: BotRuntimeState,
        progress_message: str,
    ) -> None:
        snapshot = self._snapshot
        if (
            self._closed
            or self._active_task is not None
            or snapshot is None
            or action is None
            or action_name not in snapshot.available_actions
        ):
            return
        self._invalidate_runtime_snapshots()
        transition = transition_bot_control(
            snapshot,
            result=BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    snapshot.workspace, intermediate_state
                )
            ),
            progress_message=progress_message,
        )
        self._publish(transition)
        if self._closed or self._snapshot is not transition:
            return
        self._start_task(operation, action, transition)

    def _start_task(
        self,
        operation: _LifecycleOperation,
        action: LifecycleAction,
        snapshot: BotControlSnapshot,
    ) -> None:
        task = BackgroundTask(lambda: action(snapshot))
        task.signals.succeeded.connect(self._task_succeeded)
        task.signals.failed.connect(self._task_failed)
        task.signals.finished.connect(self._task_finished)
        self._active_task = task
        self._active_operation = operation
        self._task_generation = self._generation
        self.busy_changed.emit(True)
        self._thread_pool.start(task)

    @Slot(object)
    def _task_succeeded(self, result: object) -> None:
        if not self._callbacks_are_current():
            return
        operation = self._active_operation
        snapshot = self._snapshot
        if operation is None or snapshot is None:
            return
        if not isinstance(result, BotLifecycleResult):
            self._publish_failure(operation, snapshot)
            return
        try:
            next_snapshot = (
                self._initialization_result_snapshot(snapshot, result)
                if operation is _LifecycleOperation.INITIALIZE
                else self._result_snapshot(operation, snapshot, result)
            )
        except ValueError:
            self._publish_failure(operation, snapshot)
            return
        if not self._is_allowed_result(operation, next_snapshot.state):
            self._publish_failure(operation, snapshot)
            return
        self._publish(next_snapshot)
        self._publish_notification(result)
        self._flush_pending_runtime_result()

    def _initialization_result_snapshot(
        self,
        current: BotControlSnapshot,
        result: BotLifecycleResult,
    ) -> BotControlSnapshot:
        header = result.workspace.header
        if header is None:
            raise ValueError("result workspace requires a header")
        return BotControlSnapshot(
            state=header.runtime_state,
            session=current.session,
            workspace=result.workspace,
            available_actions=self._actions_for(header.runtime_state),
            blocked_reason=result.blocked_reason,
        )

    def _result_snapshot(
        self,
        operation: _LifecycleOperation,
        snapshot: BotControlSnapshot,
        result: BotLifecycleResult,
    ) -> BotControlSnapshot:
        header = result.workspace.header
        if header is None:
            raise ValueError("result workspace requires a header")
        return transition_bot_control(
            snapshot,
            result=result,
            actions=self._actions_for(header.runtime_state),
        )

    @Slot(object)
    def _task_failed(self, error: object) -> None:
        if not self._callbacks_are_current():
            return
        operation = self._active_operation
        snapshot = self._snapshot
        if operation is not None and snapshot is not None:
            self._publish_failure(operation, snapshot)

    @Slot()
    def _task_finished(self) -> None:
        task = self._active_task
        if task is None or self._task_generation is None:
            return
        callbacks_are_current = self._callbacks_are_current()
        snapshot = self._snapshot
        task.signals.succeeded.disconnect(self._task_succeeded)
        task.signals.failed.disconnect(self._task_failed)
        task.signals.finished.disconnect(self._task_finished)
        self._active_task = None
        self._active_operation = None
        self._task_generation = None
        if callbacks_are_current:
            self.busy_changed.emit(False)
        elif (
            not self._closed
            and snapshot is not None
            and snapshot.state is BotRuntimeState.CONFIGURED
        ):
            self._publish(
                replace(
                    snapshot,
                    available_actions=self._actions_for(BotRuntimeState.CONFIGURED),
                )
            )
            self.busy_changed.emit(False)

    def _publish_failure(
        self,
        operation: _LifecycleOperation,
        snapshot: BotControlSnapshot,
    ) -> None:
        self._pending_runtime_result = None
        reason = {
            _LifecycleOperation.INITIALIZE: "Paper Bot recovery failed",
            _LifecycleOperation.START: "Paper Bot could not be started",
            _LifecycleOperation.STOP: "Paper Bot could not be stopped",
            _LifecycleOperation.RECOVER: "Paper Bot recovery failed",
        }[operation]
        blocked = blocked_bot_control(
            snapshot,
            reason=reason,
            actions=self._actions_for(BotRuntimeState.BLOCKED),
        )
        self._publish(blocked)
        self._publish_notification(
            BotLifecycleResult(
                workspace=blocked.workspace,
                blocked_reason=blocked.blocked_reason,
            )
        )

    @Slot(object, int)
    def _runtime_snapshot_received(self, result: object, generation: int) -> None:
        runtime_snapshots = self._runtime_snapshots
        snapshot = self._snapshot
        if (
            self._closed
            or runtime_snapshots is None
            or not runtime_snapshots.is_current(generation)
            or snapshot is None
            or not isinstance(result, BotLifecycleResult)
        ):
            return
        if (
            snapshot.state is BotRuntimeState.STARTING
            and self._active_operation is _LifecycleOperation.START
        ):
            self._pending_runtime_result = (generation, result)
            return
        if snapshot.state is not BotRuntimeState.RUNNING:
            return
        self._publish_runtime_result(snapshot, result)

    def _publish_runtime_result(
        self,
        current: BotControlSnapshot,
        result: BotLifecycleResult,
    ) -> None:
        header = result.workspace.header
        if header is None or header.runtime_state not in {
            BotRuntimeState.RUNNING,
            BotRuntimeState.BLOCKED,
        }:
            return
        try:
            snapshot = BotControlSnapshot(
                state=header.runtime_state,
                session=current.session,
                workspace=result.workspace,
                available_actions=self._actions_for(header.runtime_state),
                blocked_reason=result.blocked_reason,
            )
        except ValueError:
            return
        self._publish(snapshot)
        self._publish_notification(result)
        if snapshot.state is BotRuntimeState.BLOCKED:
            self._invalidate_runtime_snapshots()

    def _flush_pending_runtime_result(self) -> None:
        pending = self._pending_runtime_result
        self._pending_runtime_result = None
        snapshot = self._snapshot
        runtime_snapshots = self._runtime_snapshots
        if (
            pending is None
            or snapshot is None
            or snapshot.state is not BotRuntimeState.RUNNING
            or runtime_snapshots is None
            or not runtime_snapshots.is_current(pending[0])
        ):
            return
        self._publish_runtime_result(snapshot, pending[1])

    def _invalidate_runtime_snapshots(self) -> None:
        self._pending_runtime_result = None
        if self._runtime_snapshots is not None:
            self._runtime_snapshots.invalidate()

    def _actions_for(self, state: BotRuntimeState) -> frozenset[BotControlAction]:
        if state is BotRuntimeState.CONFIGURED and self._start_bot is not None:
            return frozenset({BotControlAction.START})
        if state is BotRuntimeState.RUNNING and self._stop_bot is not None:
            return frozenset({BotControlAction.STOP})
        if state is BotRuntimeState.BLOCKED and self._recover is not None:
            return frozenset({BotControlAction.RECOVER})
        return frozenset()

    def _is_allowed_result(
        self,
        operation: _LifecycleOperation,
        state: BotRuntimeState,
    ) -> bool:
        return (
            state
            in {
                _LifecycleOperation.INITIALIZE: frozenset(
                    {BotRuntimeState.CONFIGURED, BotRuntimeState.BLOCKED}
                ),
                _LifecycleOperation.START: frozenset(
                    {BotRuntimeState.RUNNING, BotRuntimeState.BLOCKED}
                ),
                _LifecycleOperation.STOP: frozenset(
                    {BotRuntimeState.STOPPED, BotRuntimeState.BLOCKED}
                ),
                _LifecycleOperation.RECOVER: frozenset(
                    {
                        BotRuntimeState.CONFIGURED,
                        BotRuntimeState.STOPPED,
                        BotRuntimeState.BLOCKED,
                    }
                ),
            }[operation]
        )

    def _publish(self, snapshot: BotControlSnapshot) -> None:
        self._snapshot = snapshot
        self.snapshot_changed.emit(snapshot)

    def _publish_notification(self, result: BotLifecycleResult) -> None:
        records_before = self._notification_store.records
        self._notification_store.publish(result, occurred_at_utc=self._clock())
        if self._notification_store.records is records_before:
            return
        self.notifications_changed.emit(self._notification_store)

    def _callbacks_are_current(self) -> bool:
        return (
            not self._closed
            and self._active_task is not None
            and self._task_generation == self._generation
        )
