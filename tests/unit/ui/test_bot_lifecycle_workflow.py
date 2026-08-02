import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from PySide6.QtCore import QCoreApplication, QObject, QThread, QThreadPool, Slot
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.bot_control import (
    BotControlAction,
    BotControlSnapshot,
    BotLifecycleResult,
    workspace_with_runtime_state,
)
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    DataFreshness,
    OpenOrderSnapshot,
    WorkspaceReadState,
    empty_position_basket_tab,
    paper_runtime_workspace_snapshot,
    ready_open_orders_tab,
    ready_position_basket_tab,
)
from tiewtrade.trading.session_config import MarketType
from tiewtrade.ui.bot_lifecycle_workflow import (
    BotLifecycleWorkflow,
    LifecycleAction,
    RuntimeSnapshotRelay,
)

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)


def _workflow(
    *,
    start_bot: LifecycleAction | None,
    stop_bot: LifecycleAction | None,
    recover: LifecycleAction | None,
    runtime_snapshots: RuntimeSnapshotRelay | None = None,
) -> tuple[BotLifecycleWorkflow, QThreadPool]:
    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)
    return (
        BotLifecycleWorkflow(
            start_bot=start_bot,
            stop_bot=stop_bot,
            recover=recover,
            runtime_snapshots=runtime_snapshots,
            thread_pool=thread_pool,
            clock=lambda: OBSERVED_AT,
        ),
        thread_pool,
    )


class _SnapshotThreadRecorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.snapshots: list[BotControlSnapshot] = []
        self.threads: list[QThread] = []

    @Slot(object)
    def record(self, value: object) -> None:
        assert isinstance(value, BotControlSnapshot)
        self.snapshots.append(value)
        self.threads.append(QThread.currentThread())


def _result(
    snapshot: BotControlSnapshot,
    state: BotRuntimeState,
    *,
    data_freshness: DataFreshness | None = None,
    blocked_reason: str | None = None,
) -> BotLifecycleResult:
    return BotLifecycleResult(
        workspace=workspace_with_runtime_state(
            snapshot.workspace,
            state,
            data_freshness=data_freshness,
        ),
        blocked_reason=blocked_reason,
    )


def test_start_emits_starting_then_running_off_ui_thread(qtbot: QtBot) -> None:
    caller_thread = threading.get_ident()
    worker_threads: list[int] = []

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        worker_threads.append(threading.get_ident())
        return _result(
            snapshot,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    emitted: list[BotControlSnapshot] = []
    workflow.snapshot_changed.connect(emitted.append)

    workflow.configure(configured_spot_session())
    workflow.start_bot()

    qtbot.waitUntil(lambda: emitted[-1].state is BotRuntimeState.RUNNING)

    assert [item.state for item in emitted[-2:]] == [
        BotRuntimeState.STARTING,
        BotRuntimeState.RUNNING,
    ]
    assert worker_threads[0] != caller_thread
    assert emitted[-1].available_actions == frozenset()
    assert thread_pool.waitForDone(1_000)


def test_runtime_snapshot_from_worker_is_published_on_qt_thread(
    qtbot: QtBot,
) -> None:
    relay = RuntimeSnapshotRelay()
    callbacks: list[Callable[[BotLifecycleResult], None]] = []

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        callbacks.append(relay.new_generation())
        return _result(
            snapshot,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=None,
        runtime_snapshots=relay,
    )
    recorder = _SnapshotThreadRecorder()
    workflow.snapshot_changed.connect(recorder.record)
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)

    updated_at = datetime(2026, 8, 1, 12, 5, tzinfo=UTC)
    runtime_result = BotLifecycleResult(
        workspace=paper_runtime_workspace_snapshot(
            workflow.snapshot.workspace,
            orders=(_order(),),
            basket=_basket(),
            observed_at_utc=updated_at,
        )
    )
    callback_thread: list[int] = []

    def publish_from_runtime() -> None:
        callback_thread.append(threading.get_ident())
        callbacks[0](runtime_result)

    runtime_thread = threading.Thread(target=publish_from_runtime)
    runtime_thread.start()
    runtime_thread.join(timeout=1)

    qtbot.waitUntil(lambda: workflow.snapshot.workspace.orders == (_order(),))

    assert callback_thread == [runtime_thread.ident]
    assert recorder.threads[-1] is workflow.thread()
    assert workflow.snapshot.workspace.basket == _basket()
    assert workflow.snapshot.workspace.data_as_of_utc == updated_at
    assert thread_pool.waitForDone(1_000)


def test_runtime_snapshot_published_before_start_returns_is_not_lost(
    qtbot: QtBot,
) -> None:
    relay = RuntimeSnapshotRelay()

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        publish = relay.new_generation()
        publish(
            BotLifecycleResult(
                workspace=paper_runtime_workspace_snapshot(
                    snapshot.workspace,
                    orders=(_order(),),
                    basket=_basket(),
                    observed_at_utc=datetime(2026, 8, 1, 12, 5, tzinfo=UTC),
                )
            )
        )
        return _result(
            snapshot,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=None,
        runtime_snapshots=relay,
    )
    workflow.configure(configured_spot_session())
    workflow.start_bot()

    qtbot.waitUntil(lambda: workflow.snapshot.workspace.basket == _basket())

    assert workflow.snapshot.state is BotRuntimeState.RUNNING
    assert workflow.snapshot.workspace.orders == (_order(),)
    assert thread_pool.waitForDone(1_000)


def test_stop_invalidates_late_runtime_callback_and_preserves_basket(
    qtbot: QtBot,
) -> None:
    relay = RuntimeSnapshotRelay()
    callbacks: list[Callable[[BotLifecycleResult], None]] = []
    stop_started = threading.Event()
    release_stop = threading.Event()

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        callbacks.append(relay.new_generation())
        return _result(
            snapshot,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )

    def stop(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        stop_started.set()
        if not release_stop.wait(timeout=2):
            raise TimeoutError("test did not release stop")
        return _result(snapshot, BotRuntimeState.STOPPED)

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=stop,
        recover=None,
        runtime_snapshots=relay,
    )
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)
    callbacks[0](
        BotLifecycleResult(
            workspace=paper_runtime_workspace_snapshot(
                workflow.snapshot.workspace,
                orders=(_order(),),
                basket=_basket(),
                observed_at_utc=datetime(2026, 8, 1, 12, 5, tzinfo=UTC),
            )
        )
    )
    qtbot.waitUntil(lambda: workflow.snapshot.workspace.basket == _basket())

    workflow.stop_bot()
    qtbot.waitUntil(stop_started.is_set)
    stopping_workspace = workflow.snapshot.workspace
    callbacks[0](
        BotLifecycleResult(
            workspace=paper_runtime_workspace_snapshot(
                stopping_workspace,
                orders=(),
                basket=None,
                observed_at_utc=datetime(2026, 8, 1, 12, 10, tzinfo=UTC),
            )
        )
    )
    QCoreApplication.processEvents()

    assert workflow.snapshot.workspace is stopping_workspace
    assert workflow.snapshot.workspace.basket == _basket()

    release_stop.set()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.STOPPED)

    assert workflow.snapshot.workspace.basket == _basket()
    assert thread_pool.waitForDone(1_000)


def test_runtime_callback_from_older_generation_is_ignored(qtbot: QtBot) -> None:
    relay = RuntimeSnapshotRelay()
    callbacks: list[Callable[[BotLifecycleResult], None]] = []

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        callbacks.append(relay.new_generation())
        return _result(
            snapshot,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=None,
        runtime_snapshots=relay,
    )
    first_session = configured_spot_session()
    second_session = replace(
        configured_spot_session(),
        config=replace(
            configured_spot_session().config,
            session_id=UUID("00000000-0000-0000-0000-000000000999"),
        ),
    )
    workflow.configure(first_session)
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)
    first_callback = callbacks[0]

    workflow.configure(second_session)
    configured_workspace = workflow.snapshot.workspace
    first_callback(
        BotLifecycleResult(
            workspace=paper_runtime_workspace_snapshot(
                configured_workspace,
                orders=(_order(),),
                basket=_basket(),
                observed_at_utc=datetime(2026, 8, 1, 12, 5, tzinfo=UTC),
            )
        )
    )
    QCoreApplication.processEvents()

    assert workflow.snapshot.workspace is configured_workspace

    workflow.start_bot()
    qtbot.waitUntil(
        lambda: (
            len(callbacks) == 2 and workflow.snapshot.state is BotRuntimeState.RUNNING
        )
    )
    second_callback = callbacks[1]
    current_workspace = workflow.snapshot.workspace
    first_callback(
        BotLifecycleResult(
            workspace=paper_runtime_workspace_snapshot(
                current_workspace,
                orders=(_order(),),
                basket=_basket(),
                observed_at_utc=datetime(2026, 8, 1, 12, 10, tzinfo=UTC),
            )
        )
    )
    QCoreApplication.processEvents()
    assert workflow.snapshot.workspace is current_workspace

    second_callback(
        BotLifecycleResult(
            workspace=paper_runtime_workspace_snapshot(
                current_workspace,
                orders=(_order(),),
                basket=_basket(),
                observed_at_utc=datetime(2026, 8, 1, 12, 15, tzinfo=UTC),
            )
        )
    )
    qtbot.waitUntil(lambda: workflow.snapshot.workspace.basket == _basket())

    assert workflow.snapshot.session is second_session
    assert thread_pool.waitForDone(1_000)


def test_repeated_start_does_not_submit_a_second_task(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        nonlocal calls
        calls += 1
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return _result(snapshot, BotRuntimeState.RUNNING)

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(started.is_set)
    workflow.start_bot()
    release.set()

    qtbot.waitUntil(
        lambda: calls == 1 and workflow.snapshot.state is BotRuntimeState.RUNNING
    )

    assert thread_pool.waitForDone(1_000)


def test_stop_emits_stopping_then_stopped_and_rejects_repeats(qtbot: QtBot) -> None:
    stop_started = threading.Event()
    release_stop = threading.Event()
    stop_calls = 0

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(snapshot, BotRuntimeState.RUNNING)

    def stop(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        nonlocal stop_calls
        stop_calls += 1
        stop_started.set()
        if not release_stop.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return _result(snapshot, BotRuntimeState.STOPPED)

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=stop, recover=None)
    emitted: list[BotControlSnapshot] = []
    workflow.snapshot_changed.connect(emitted.append)
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)

    workflow.stop_bot()
    qtbot.waitUntil(stop_started.is_set)
    workflow.stop_bot()
    release_stop.set()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.STOPPED)

    assert [item.state for item in emitted[-2:]] == [
        BotRuntimeState.STOPPING,
        BotRuntimeState.STOPPED,
    ]
    assert stop_calls == 1
    assert thread_pool.waitForDone(1_000)


def test_start_result_for_futures_header_is_blocked_with_spot_workspace_preserved(
    qtbot: QtBot,
) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        workspace = workspace_with_runtime_state(
            snapshot.workspace,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )
        assert workspace.header is not None
        return BotLifecycleResult(
            workspace=replace(
                workspace,
                header=replace(workspace.header, market_type=MarketType.FUTURES),
            )
        )

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    workflow.configure(configured_spot_session())
    original = workflow.snapshot.workspace
    workflow.start_bot()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)

    assert workflow.snapshot.blocked_reason == "Paper Bot could not be started"
    assert workflow.snapshot.workspace.orders is original.orders
    assert workflow.snapshot.workspace.basket is original.basket
    assert workflow.snapshot.workspace.data_as_of_utc is original.data_as_of_utc
    assert workflow.snapshot.workspace.read_state is original.read_state
    assert workflow.snapshot.workspace.header is not None
    assert workflow.snapshot.workspace.header.market_type is MarketType.SPOT
    assert thread_pool.waitForDone(1_000)


def test_stop_result_dropping_basket_is_blocked_and_preserves_take_profit(
    qtbot: QtBot,
) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(snapshot, BotRuntimeState.RUNNING)

    def stop(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return BotLifecycleResult(
            workspace=replace(
                workspace_with_runtime_state(
                    snapshot.workspace, BotRuntimeState.STOPPED
                ),
                position_basket=empty_position_basket_tab(),
            )
        )

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=stop, recover=None)
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)
    running = replace(
        workflow.snapshot,
        workspace=replace(
            workflow.snapshot.workspace,
            position_basket=ready_position_basket_tab(
                _basket(), observed_at_utc=OBSERVED_AT
            ),
        ),
    )
    workflow._snapshot = running
    workflow.stop_bot()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)

    assert workflow.snapshot.blocked_reason == "Paper Bot could not be stopped"
    assert workflow.snapshot.workspace.basket is running.workspace.basket
    assert workflow.snapshot.workspace.basket is not None
    assert workflow.snapshot.workspace.basket.take_profit_price == Decimal(
        "66000.123456789012345678"
    )
    assert thread_pool.waitForDone(1_000)


@pytest.mark.parametrize(
    "alter_workspace",
    [
        pytest.param(
            lambda workspace: replace(
                workspace,
                open_orders=ready_open_orders_tab(
                    (_order(),), observed_at_utc=OBSERVED_AT
                ),
            ),
            id="orders",
        ),
        pytest.param(
            lambda workspace: replace(
                workspace,
                data_as_of_utc=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
            ),
            id="data-as-of",
        ),
        pytest.param(
            lambda workspace: replace(workspace, read_state=WorkspaceReadState.LOADING),
            id="read-state",
        ),
    ],
)
def test_start_result_altering_workspace_continuity_maps_to_blocked(
    qtbot: QtBot,
    alter_workspace: object,
) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        workspace = workspace_with_runtime_state(
            snapshot.workspace, BotRuntimeState.RUNNING
        )
        assert callable(alter_workspace)
        return BotLifecycleResult(workspace=alter_workspace(workspace))

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    workflow.configure(configured_spot_session())
    original = workflow.snapshot.workspace
    workflow.start_bot()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)

    assert workflow.snapshot.blocked_reason == "Paper Bot could not be started"
    assert workflow.snapshot.workspace.orders is original.orders
    assert workflow.snapshot.workspace.data_as_of_utc is original.data_as_of_utc
    assert workflow.snapshot.workspace.read_state is original.read_state
    assert thread_pool.waitForDone(1_000)


@pytest.mark.parametrize(
    "start_result",
    [
        pytest.param(None, id="invalid-result"),
        pytest.param(RuntimeError("api_key=secret"), id="exception"),
    ],
)
def test_start_invalid_result_or_exception_maps_to_safe_blocked_reason(
    qtbot: QtBot,
    start_result: object,
) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        if isinstance(start_result, Exception):
            raise start_result
        return start_result  # type: ignore[return-value]

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    workflow.configure(configured_spot_session())
    workflow.start_bot()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)

    assert workflow.snapshot.blocked_reason == "Paper Bot could not be started"
    assert workflow.snapshot.available_actions == frozenset()
    assert "secret" not in workflow.snapshot.blocked_reason
    assert thread_pool.waitForDone(1_000)


@pytest.mark.parametrize("state", [BotRuntimeState.CONFIGURED, BotRuntimeState.STOPPED])
def test_recover_accepts_configured_or_stopped_result(
    qtbot: QtBot, state: BotRuntimeState
) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(
            snapshot,
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot could not be started",
        )

    def recover(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(snapshot, state)

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=recover,
    )
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)
    workflow.recover()

    qtbot.waitUntil(lambda: workflow.snapshot.state is state)

    expected_actions = (
        frozenset({BotControlAction.START})
        if state is BotRuntimeState.CONFIGURED
        else frozenset()
    )
    assert workflow.snapshot.available_actions == expected_actions
    assert thread_pool.waitForDone(1_000)


def test_recover_invalid_result_maps_to_safe_blocked_reason(qtbot: QtBot) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(
            snapshot,
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot could not be started",
        )

    def recover(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return None  # type: ignore[return-value]

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=recover,
    )
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)
    workflow.recover()

    qtbot.waitUntil(
        lambda: workflow.snapshot.blocked_reason == "Paper Bot recovery failed"
    )

    assert workflow.snapshot.available_actions == frozenset({BotControlAction.RECOVER})
    assert thread_pool.waitForDone(1_000)


def test_recover_accepts_blocked_result_with_its_safe_reason(qtbot: QtBot) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(
            snapshot,
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot could not be started",
        )

    def recover(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(
            snapshot,
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot could not be stopped",
        )

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=recover,
    )
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)
    workflow.recover()

    qtbot.waitUntil(
        lambda: workflow.snapshot.blocked_reason == "Paper Bot could not be stopped"
    )

    assert workflow.snapshot.available_actions == frozenset({BotControlAction.RECOVER})
    assert thread_pool.waitForDone(1_000)


def test_repeated_recover_does_not_submit_a_second_task(qtbot: QtBot) -> None:
    recover_started = threading.Event()
    release_recover = threading.Event()
    recover_calls = 0

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(
            snapshot,
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot could not be started",
        )

    def recover(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        nonlocal recover_calls
        recover_calls += 1
        recover_started.set()
        if not release_recover.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return _result(snapshot, BotRuntimeState.STOPPED)

    workflow, thread_pool = _workflow(
        start_bot=start,
        stop_bot=None,
        recover=recover,
    )
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)
    workflow.recover()
    qtbot.waitUntil(recover_started.is_set)
    workflow.recover()
    release_recover.set()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.STOPPED)

    assert recover_calls == 1
    assert thread_pool.waitForDone(1_000)


def test_stop_exception_maps_to_safe_blocked_reason(qtbot: QtBot) -> None:
    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        return _result(snapshot, BotRuntimeState.RUNNING)

    def stop(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        raise RuntimeError("request_id=abc123 payload=order")

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=stop, recover=None)
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)
    workflow.stop_bot()

    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.BLOCKED)

    assert workflow.snapshot.blocked_reason == "Paper Bot could not be stopped"
    assert thread_pool.waitForDone(1_000)


def test_reconfigure_discards_late_callback_from_older_generation(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[UUID] = []

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        calls.append(snapshot.session.config.session_id)
        if len(calls) == 1:
            started.set()
            if not release.wait(timeout=2):
                raise TimeoutError("test did not release worker")
        return _result(snapshot, BotRuntimeState.RUNNING)

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    emitted: list[BotControlSnapshot] = []
    busy_events: list[bool] = []
    workflow.snapshot_changed.connect(emitted.append)
    workflow.busy_changed.connect(busy_events.append)
    first = configured_spot_session()
    second = replace(
        configured_spot_session(),
        config=replace(
            configured_spot_session().config,
            session_id=UUID("00000000-0000-0000-0000-000000000999"),
        ),
    )
    workflow.configure(first)
    workflow.start_bot()
    qtbot.waitUntil(started.is_set)
    workflow.configure(second)
    reconfigured = workflow.snapshot

    assert reconfigured.available_actions == frozenset()
    assert busy_events == [True]
    workflow.start_bot()
    assert calls == [first.config.session_id]

    release.set()
    qtbot.waitUntil(
        lambda: (
            workflow.snapshot.available_actions == frozenset({BotControlAction.START})
        )
    )

    assert thread_pool.waitForDone(1_000)
    QCoreApplication.processEvents()

    assert workflow.snapshot.state is BotRuntimeState.CONFIGURED
    assert workflow.snapshot.session is second
    assert workflow.snapshot.workspace is reconfigured.workspace
    assert [item.state for item in emitted] == [
        BotRuntimeState.CONFIGURED,
        BotRuntimeState.STARTING,
        BotRuntimeState.CONFIGURED,
        BotRuntimeState.CONFIGURED,
    ]
    assert busy_events == [True, False]

    workflow.start_bot()
    qtbot.waitUntil(lambda: workflow.snapshot.state is BotRuntimeState.RUNNING)

    assert calls == [first.config.session_id, second.config.session_id]


def test_close_discards_late_callback_and_busy_false(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return _result(snapshot, BotRuntimeState.RUNNING)

    workflow, thread_pool = _workflow(start_bot=start, stop_bot=None, recover=None)
    emitted: list[BotControlSnapshot] = []
    busy_events: list[bool] = []
    workflow.snapshot_changed.connect(emitted.append)
    workflow.busy_changed.connect(busy_events.append)
    workflow.configure(configured_spot_session())
    workflow.start_bot()
    qtbot.waitUntil(started.is_set)
    workflow.close()
    release.set()

    assert thread_pool.waitForDone(1_000)
    QCoreApplication.processEvents()

    assert [item.state for item in emitted] == [
        BotRuntimeState.CONFIGURED,
        BotRuntimeState.STARTING,
    ]
    assert busy_events == [True]


def _basket() -> BasketSnapshot:
    return BasketSnapshot(
        symbol="BTCUSDT",
        market_type="spot",
        entry_count=2,
        total_quantity=Decimal("1"),
        average_entry_price=Decimal("64000.123456789012345678"),
        current_price=Decimal("65000.123456789012345678"),
        take_profit_price=Decimal("66000.123456789012345678"),
        unrealized_pnl=Decimal("1000"),
        liquidation_price=None,
        lifecycle="open",
        updated_at_utc=OBSERVED_AT,
    )


def _order() -> OpenOrderSnapshot:
    return OpenOrderSnapshot(
        order_id="order-1",
        created_at_utc=OBSERVED_AT,
        symbol="BTCUSDT",
        side="SELL",
        order_type="LIMIT",
        price=Decimal("66000.123456789012345678"),
        quantity=Decimal("1"),
        filled_quantity=Decimal("0"),
        status="NEW",
    )
