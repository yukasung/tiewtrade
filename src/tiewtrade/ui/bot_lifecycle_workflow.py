from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from enum import Enum

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

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
from tiewtrade.ui.background_task import BackgroundTask

LifecycleAction = Callable[[BotControlSnapshot], BotLifecycleResult]


class _LifecycleOperation(Enum):
    START = "start"
    STOP = "stop"
    RECOVER = "recover"


class BotLifecycleWorkflow(QObject):
    snapshot_changed = Signal(object)
    busy_changed = Signal(bool)

    def __init__(
        self,
        *,
        start_bot: LifecycleAction | None,
        stop_bot: LifecycleAction | None,
        recover: LifecycleAction | None,
        thread_pool: QThreadPool | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._start_bot = start_bot
        self._stop_bot = stop_bot
        self._recover = recover
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._clock = clock
        self._snapshot: BotControlSnapshot | None = None
        self._active_task: BackgroundTask | None = None
        self._active_operation: _LifecycleOperation | None = None
        self._task_generation: int | None = None
        self._generation = 0
        self._closed = False

    @property
    def snapshot(self) -> BotControlSnapshot:
        if self._snapshot is None:
            raise RuntimeError("Bot Lifecycle Workflow has not been configured")
        return self._snapshot

    def configure(self, session: ConfiguredPaperSession) -> None:
        if self._closed:
            return
        active_task = self._active_task is not None
        self._generation += 1
        self._publish(
            configured_bot_control(
                session,
                observed_at_utc=self._clock(),
                actions=(
                    frozenset()
                    if active_task
                    else self._actions_for(BotRuntimeState.CONFIGURED)
                ),
            )
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
        self._start_task(_LifecycleOperation.RECOVER, self._recover, snapshot)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
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
            next_snapshot = self._result_snapshot(operation, snapshot, result)
        except ValueError:
            self._publish_failure(operation, snapshot)
            return
        if not self._is_allowed_result(operation, next_snapshot.state):
            self._publish_failure(operation, snapshot)
            return
        self._publish(next_snapshot)

    def _result_snapshot(
        self,
        operation: _LifecycleOperation,
        snapshot: BotControlSnapshot,
        result: BotLifecycleResult,
    ) -> BotControlSnapshot:
        header = result.workspace.header
        if header is None:
            raise ValueError("result workspace requires a header")
        if (
            operation is _LifecycleOperation.RECOVER
            and header.runtime_state is BotRuntimeState.BLOCKED
        ):
            return BotControlSnapshot(
                state=BotRuntimeState.BLOCKED,
                session=snapshot.session,
                workspace=result.workspace,
                available_actions=self._actions_for(BotRuntimeState.BLOCKED),
                blocked_reason=result.blocked_reason,
            )
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
        reason = {
            _LifecycleOperation.START: "Paper Bot could not be started",
            _LifecycleOperation.STOP: "Paper Bot could not be stopped",
            _LifecycleOperation.RECOVER: "Paper Bot recovery failed",
        }[operation]
        if snapshot.state is BotRuntimeState.BLOCKED:
            blocked = BotControlSnapshot(
                state=BotRuntimeState.BLOCKED,
                session=snapshot.session,
                workspace=snapshot.workspace,
                available_actions=self._actions_for(BotRuntimeState.BLOCKED),
                blocked_reason=reason,
            )
        else:
            blocked = blocked_bot_control(
                snapshot,
                reason=reason,
                actions=self._actions_for(BotRuntimeState.BLOCKED),
            )
        self._publish(blocked)

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

    def _callbacks_are_current(self) -> bool:
        return (
            not self._closed
            and self._active_task is not None
            and self._task_generation == self._generation
        )
