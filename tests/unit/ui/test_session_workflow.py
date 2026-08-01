import threading
from typing import cast

import pytest
from PySide6.QtCore import QCoreApplication, QThreadPool
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
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
)
from tiewtrade.ui.session_workflow import (
    CreateSession,
    LoadActiveSession,
    SessionWorkflow,
)


class _CallbackTrackingSessionWorkflow(SessionWorkflow):
    succeeded_callback_invocations = 0

    def _task_succeeded(self, result: object) -> None:
        self.succeeded_callback_invocations += 1
        super()._task_succeeded(result)


def _spot_values() -> PaperSessionSetupValues:
    return PaperSessionSetupValues(
        market_type="spot",
        symbol="BTCUSDT",
        timeframe="5m",
        available_capital="200000",
        max_entries="10",
        fee_percent="0.1",
        slippage_bps="5",
        spot_trading_capital_percent="80",
        futures_leverage=None,
    )


def _workflow(
    *,
    create_session: CreateSession,
    load_active: LoadActiveSession,
) -> tuple[SessionWorkflow, QThreadPool]:
    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)
    return (
        SessionWorkflow(
            create_session=create_session,
            load_active=load_active,
            thread_pool=thread_pool,
        ),
        thread_pool,
    )


def _unused_create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
    pytest.fail("create must not run")


def test_load_publishes_loading_then_ready_snapshot_off_ui_thread(
    qtbot: QtBot,
) -> None:
    caller_thread = threading.get_ident()
    worker_threads: list[int] = []
    session = configured_spot_session()

    def load() -> ConfiguredPaperSession:
        worker_threads.append(threading.get_ident())
        return session

    workflow, thread_pool = _workflow(create_session=_unused_create, load_active=load)
    snapshots: list[TradingWorkspaceSnapshot] = []
    workflow.workspace_changed.connect(snapshots.append)

    workflow.start()

    qtbot.waitUntil(
        lambda: (
            [item.read_state for item in snapshots]
            == [WorkspaceReadState.LOADING, WorkspaceReadState.READY]
        )
    )
    assert worker_threads[0] != caller_thread
    assert thread_pool.waitForDone(1_000)


def test_refresh_failure_preserves_last_known_snapshot(qtbot: QtBot) -> None:
    session = configured_spot_session()
    calls = 0

    def load() -> ConfiguredPaperSession:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("SQLite failed at /private/tmp/tiewtrade.sqlite3")
        return session

    workflow, thread_pool = _workflow(create_session=_unused_create, load_active=load)
    snapshots: list[TradingWorkspaceSnapshot] = []
    workflow.workspace_changed.connect(snapshots.append)

    workflow.start()
    qtbot.waitUntil(lambda: snapshots[-1].read_state is WorkspaceReadState.READY)
    ready = snapshots[-1]
    workflow.start()
    qtbot.waitUntil(lambda: snapshots[-1].read_state is WorkspaceReadState.ERROR)
    failed = snapshots[-1]

    assert failed.header == ready.header
    assert failed.orders == ready.orders
    assert failed.basket == ready.basket
    assert failed.data_as_of_utc == ready.data_as_of_utc
    assert failed.message == "Paper Session could not be loaded"
    assert "private/tmp" not in failed.message
    assert thread_pool.waitForDone(1_000)


def test_close_discards_late_workspace_generation(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()

    def delayed_load() -> ConfiguredPaperSession:
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return configured_spot_session()

    workflow, thread_pool = _workflow(
        create_session=_unused_create,
        load_active=delayed_load,
    )
    snapshots: list[TradingWorkspaceSnapshot] = []
    workflow.workspace_changed.connect(snapshots.append)

    workflow.start()
    qtbot.waitUntil(started.is_set)
    workflow.close()
    release.set()

    assert thread_pool.waitForDone(1_000)
    QCoreApplication.processEvents()
    assert [item.read_state for item in snapshots] == [WorkspaceReadState.LOADING]


def test_start_emits_setup_when_no_active_session(qtbot: QtBot) -> None:
    workflow, thread_pool = _workflow(
        create_session=_unused_create,
        load_active=lambda: None,
    )
    setup_events: list[None] = []
    busy_events: list[bool] = []
    workflow.setup_required.connect(lambda: setup_events.append(None))
    workflow.busy_changed.connect(busy_events.append)

    workflow.start()

    qtbot.waitUntil(lambda: setup_events == [None])
    qtbot.waitUntil(lambda: busy_events == [True, False])
    assert thread_pool.waitForDone(1_000)


def test_start_emits_setup_before_idle(qtbot: QtBot) -> None:
    workflow, thread_pool = _workflow(
        create_session=_unused_create,
        load_active=lambda: None,
    )
    events: list[str] = []
    workflow.setup_required.connect(lambda: events.append("setup"))
    workflow.busy_changed.connect(lambda busy: events.append(f"busy:{busy}"))

    workflow.start()

    qtbot.waitUntil(lambda: events == ["busy:True", "setup", "busy:False"])
    assert thread_pool.waitForDone(1_000)


def test_start_emits_existing_durable_session(qtbot: QtBot) -> None:
    existing = configured_spot_session()
    workflow, thread_pool = _workflow(
        create_session=_unused_create,
        load_active=lambda: existing,
    )
    sessions: list[ConfiguredPaperSession] = []
    workflow.session_ready.connect(sessions.append)

    workflow.start()

    qtbot.waitUntil(lambda: sessions == [existing])
    assert thread_pool.waitForDone(1_000)


def test_create_emits_durable_session_and_can_run_again_after_finish(
    qtbot: QtBot,
) -> None:
    created = configured_spot_session()
    calls: list[PaperSessionSetupValues] = []

    def create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        calls.append(values)
        return PaperSessionCreateOutcome(created, True)

    workflow, thread_pool = _workflow(create_session=create, load_active=lambda: None)
    sessions: list[ConfiguredPaperSession] = []
    workflow.session_ready.connect(sessions.append)

    workflow.create(_spot_values())
    qtbot.waitUntil(lambda: sessions == [created])
    workflow.create(_spot_values())

    qtbot.waitUntil(lambda: sessions == [created, created])
    assert len(calls) == 2
    assert thread_pool.waitForDone(1_000)


def test_validation_failure_emits_field_error_and_setup(qtbot: QtBot) -> None:
    def reject(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        raise PaperSessionValidationError(
            "available_capital", "Available Capital must be positive"
        )

    workflow, thread_pool = _workflow(create_session=reject, load_active=lambda: None)
    errors: list[tuple[str, str]] = []
    events: list[str] = []

    def record_validation_error(field: str, message: str) -> None:
        errors.append((field, message))
        events.append("validation")

    workflow.validation_failed.connect(record_validation_error)
    workflow.setup_required.connect(lambda: events.append("setup"))
    workflow.busy_changed.connect(lambda busy: events.append(f"busy:{busy}"))

    workflow.create(_spot_values())

    qtbot.waitUntil(
        lambda: errors == [("available_capital", "Available Capital must be positive")]
    )
    qtbot.waitUntil(
        lambda: events == ["busy:True", "validation", "setup", "busy:False"]
    )
    assert thread_pool.waitForDone(1_000)


@pytest.mark.parametrize(
    ("operation", "expected_message"),
    [
        pytest.param(
            "load-storage",
            "Session storage is unavailable",
            id="load-storage",
        ),
        pytest.param(
            "load-unknown",
            "Paper Session could not be loaded",
            id="load-unknown",
        ),
        pytest.param(
            "load-version",
            "Database was created by a newer version of TiewTrade",
            id="load-version",
        ),
        pytest.param(
            "create-storage",
            "Session storage is unavailable",
            id="create-storage",
        ),
        pytest.param(
            "create-unknown",
            "Paper Session could not be created",
            id="create-unknown",
        ),
        pytest.param(
            "create-version",
            "Database was created by a newer version of TiewTrade",
            id="create-version",
        ),
    ],
)
def test_failures_emit_sanitized_unavailable_copy(
    qtbot: QtBot,
    operation: str,
    expected_message: str,
) -> None:
    error: Exception
    if operation.endswith("storage"):
        error = PaperSessionUnavailableError(
            "SQLite failed at /private/tmp/tiewtrade.sqlite3"
        )
    elif operation.endswith("version"):
        error = DatabaseCompatibilityError()
    else:
        error = RuntimeError("SQLite failed at /private/tmp/tiewtrade.sqlite3")

    def fail_load() -> ConfiguredPaperSession | None:
        raise error

    def fail_create(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        raise error

    workflow, thread_pool = _workflow(
        create_session=fail_create,
        load_active=fail_load,
    )
    messages: list[str] = []
    workflow.unavailable.connect(messages.append)

    if operation.startswith("load"):
        workflow.start()
    else:
        workflow.create(_spot_values())

    qtbot.waitUntil(lambda: messages == [expected_message])
    assert "private/tmp" not in messages[0]
    assert thread_pool.waitForDone(1_000)


@pytest.mark.parametrize(
    ("operation", "expected_message"),
    [
        pytest.param("load", "Paper Session could not be loaded", id="load"),
        pytest.param("create", "Paper Session could not be created", id="create"),
    ],
)
def test_invalid_result_type_fails_closed(
    qtbot: QtBot,
    operation: str,
    expected_message: str,
) -> None:
    workflow, thread_pool = _workflow(
        create_session=cast(CreateSession, lambda values: object()),
        load_active=cast(LoadActiveSession, lambda: object()),
    )
    messages: list[str] = []
    workflow.unavailable.connect(messages.append)

    if operation == "load":
        workflow.start()
    else:
        workflow.create(_spot_values())

    qtbot.waitUntil(lambda: messages == [expected_message])
    assert thread_pool.waitForDone(1_000)


def test_create_with_invalid_nested_session_fails_closed(qtbot: QtBot) -> None:
    invalid_outcome = PaperSessionCreateOutcome(
        session=object(),  # type: ignore[arg-type]
        created=True,
    )
    workflow, thread_pool = _workflow(
        create_session=lambda values: invalid_outcome,
        load_active=lambda: None,
    )
    sessions: list[object] = []
    messages: list[str] = []
    workflow.session_ready.connect(sessions.append)
    workflow.unavailable.connect(messages.append)

    workflow.create(_spot_values())

    qtbot.waitUntil(lambda: messages == ["Paper Session could not be created"])
    assert sessions == []
    assert thread_pool.waitForDone(1_000)


def test_duplicate_create_is_ignored_while_busy(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    created = configured_spot_session()
    calls = 0

    def create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        nonlocal calls
        calls += 1
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return PaperSessionCreateOutcome(created, True)

    workflow, thread_pool = _workflow(create_session=create, load_active=lambda: None)
    sessions: list[ConfiguredPaperSession] = []
    workflow.session_ready.connect(sessions.append)

    workflow.create(_spot_values())
    qtbot.waitUntil(started.is_set)
    workflow.create(_spot_values())

    assert calls == 1
    release.set()
    qtbot.waitUntil(lambda: sessions == [created])
    assert thread_pool.waitForDone(1_000)


def test_finished_clears_active_task_and_disconnects_callbacks(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    existing = configured_spot_session()

    def delayed_load() -> ConfiguredPaperSession | None:
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return existing

    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)
    workflow = _CallbackTrackingSessionWorkflow(
        create_session=_unused_create,
        load_active=delayed_load,
        thread_pool=thread_pool,
    )
    sessions: list[ConfiguredPaperSession] = []
    workflow.session_ready.connect(sessions.append)

    workflow.start()
    qtbot.waitUntil(started.is_set)
    retained_task = workflow._active_task
    assert retained_task is not None
    release.set()

    qtbot.waitUntil(lambda: sessions == [existing])
    qtbot.waitUntil(lambda: workflow._active_task is None)
    assert thread_pool.waitForDone(1_000)
    callback_invocations_after_finish = workflow.succeeded_callback_invocations
    assert callback_invocations_after_finish == 1

    retained_task.signals.succeeded.emit(existing)
    QCoreApplication.processEvents()

    assert workflow.succeeded_callback_invocations == callback_invocations_after_finish
    assert sessions == [existing]


def test_close_ignores_late_result_and_rejects_new_work(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    existing = configured_spot_session()
    load_calls = 0

    def delayed_load() -> ConfiguredPaperSession | None:
        nonlocal load_calls
        load_calls += 1
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return existing

    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)
    workflow = _CallbackTrackingSessionWorkflow(
        create_session=_unused_create,
        load_active=delayed_load,
        thread_pool=thread_pool,
    )
    sessions: list[ConfiguredPaperSession] = []
    setup_events: list[None] = []
    unavailable_messages: list[str] = []
    workflow.session_ready.connect(sessions.append)
    workflow.setup_required.connect(lambda: setup_events.append(None))
    workflow.unavailable.connect(unavailable_messages.append)

    workflow.start()
    qtbot.waitUntil(started.is_set)
    retained_task = workflow._active_task
    assert retained_task is not None
    workflow.close()
    release.set()
    qtbot.waitUntil(lambda: workflow._active_task is None)
    assert thread_pool.waitForDone(1_000)
    callback_invocations_after_finish = workflow.succeeded_callback_invocations
    assert callback_invocations_after_finish == 1

    retained_task.signals.succeeded.emit(existing)
    QCoreApplication.processEvents()

    workflow.start()

    assert sessions == []
    assert setup_events == []
    assert unavailable_messages == []
    assert load_calls == 1
    assert workflow.succeeded_callback_invocations == callback_invocations_after_finish
