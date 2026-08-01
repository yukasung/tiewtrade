import threading
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from PySide6.QtCore import QCoreApplication, QThreadPool
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.bot_control import (
    BotControlAction,
    BotControlSnapshot,
    BotLifecycleResult,
    workspace_with_runtime_state,
)
from tiewtrade.application.trading_workspace import BotRuntimeState, DataFreshness
from tiewtrade.ui.bot_lifecycle_workflow import BotLifecycleWorkflow, LifecycleAction

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)


def _workflow(
    *,
    start_bot: LifecycleAction | None,
    stop_bot: LifecycleAction | None,
    recover: LifecycleAction | None,
) -> tuple[BotLifecycleWorkflow, QThreadPool]:
    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)
    return (
        BotLifecycleWorkflow(
            start_bot=start_bot,
            stop_bot=stop_bot,
            recover=recover,
            thread_pool=thread_pool,
            clock=lambda: OBSERVED_AT,
        ),
        thread_pool,
    )


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
    release.set()

    assert thread_pool.waitForDone(1_000)
    QCoreApplication.processEvents()

    assert workflow.snapshot.state is BotRuntimeState.CONFIGURED
    assert workflow.snapshot.session is second
    assert [item.state for item in emitted] == [
        BotRuntimeState.CONFIGURED,
        BotRuntimeState.STARTING,
        BotRuntimeState.CONFIGURED,
    ]
    assert busy_events == [True, False]


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
