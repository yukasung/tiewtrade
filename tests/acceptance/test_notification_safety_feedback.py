import builtins
import socket
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

import tiewtrade.ui.bot_lifecycle_workflow as lifecycle_workflow_module
from tests.support.qt_interactions import click
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.bot_control import (
    BotControlSnapshot,
    BotLifecycleResult,
    workspace_with_runtime_state,
)
from tiewtrade.application.paper_session_setup import (
    CreatePaperSession,
    PaperSessionSetupValues,
)
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    DataFreshness,
    TradingWorkspaceSnapshot,
    stale_workspace_snapshot,
)
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.ui.bot_lifecycle_workflow import RuntimeSnapshotRelay
from tiewtrade.ui.main_window import MainWindow

_NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def test_paper_notification_feedback_shows_blocked_and_recovery_without_side_effects(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    _block_private_or_live_imports(monkeypatch)
    _freeze_notification_clock(monkeypatch)
    database, sessions = _paper_session(tmp_path)
    initial_counts = _sqlite_row_counts(database)
    initialize_calls = 0
    recover_calls = 0

    def initialize_bot(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        nonlocal initialize_calls
        initialize_calls += 1
        return _result(
            snapshot,
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot recovery required",
        )

    def recover_bot(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        nonlocal recover_calls
        recover_calls += 1
        return _result(snapshot, BotRuntimeState.STOPPED)

    window = MainWindow(
        create_session=lambda _values: pytest.fail("create must not run"),
        load_active=sessions.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        initialize_bot=initialize_bot,
        recover_bot=recover_bot,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Blocked")
    assert initialize_calls == 1
    assert window.workspace.bot_control_widget.supporting_text.text() == (
        "Paper Bot recovery required"
    )
    assert window.workspace.notification_button.text() == "Notifications · 1"
    assert window.workspace.notification_button.accessibleName() == (
        "Notifications: 1 unread; highest severity Critical"
    )

    click(window.workspace.notification_button)
    qtbot.waitUntil(window.workspace.notification_drawer.isVisible)
    assert window.workspace.notification_rows[0].text() == (
        "2026-08-02 12:00:00 UTC · Critical · Safety · Paper Bot recovery required"
    )

    click(window.workspace.notification_acknowledge_buttons[0])

    assert _sqlite_row_counts(database) == initial_counts
    assert window.workspace.header_runtime.text() == "Blocked"
    assert window.workspace.notification_button.text() == "Notifications · 0"
    assert (
        window.workspace.notification_button.accessibleName()
        == "Notifications: 0 unread"
    )

    click(window.workspace.bot_control_widget.recover_button)
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Stopped")

    assert recover_calls == 1
    assert window.workspace.notification_rows[0].text() == (
        "2026-08-02 12:00:00 UTC · Info · Recovery · "
        "Paper Bot recovery completed safely"
    )
    assert _sqlite_row_counts(database) == initial_counts


def test_paper_fake_stale_notification_keeps_safe_workspace_state(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    _block_private_or_live_imports(monkeypatch)
    _freeze_notification_clock(monkeypatch)
    _, sessions = _paper_session(tmp_path)
    relay = RuntimeSnapshotRelay()
    callbacks: list[Callable[[BotLifecycleResult], None]] = []
    running_workspaces: list[TradingWorkspaceSnapshot] = []

    def start_bot(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        callbacks.append(relay.new_generation())
        result = _result(
            snapshot,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        )
        running_workspaces.append(result.workspace)
        return result

    window = MainWindow(
        create_session=lambda _values: pytest.fail("create must not run"),
        load_active=sessions.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        start_bot=start_bot,
        runtime_snapshots=relay,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.workspace.bot_control_widget.start_button.isEnabled)

    click(window.workspace.bot_control_widget.start_button)
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Running")
    assert len(callbacks) == 1

    callbacks[0](
        BotLifecycleResult(workspace=stale_workspace_snapshot(running_workspaces[0]))
    )

    qtbot.waitUntil(
        lambda: window.workspace.header_freshness.text() == "Market data is stale"
    )
    assert window.workspace.header_runtime.text() == "Running"
    assert window.workspace.notification_button.text() == "Notifications · 2"
    assert window.workspace.notification_button.accessibleName() == (
        "Notifications: 2 unread; highest severity Warning"
    )

    click(window.workspace.notification_button)
    qtbot.waitUntil(window.workspace.notification_drawer.isVisible)
    assert window.workspace.notification_rows[0].text() == (
        "2026-08-02 12:00:00 UTC · Warning · Market Data · "
        "Market data is stale; new entries are paused"
    )


def _paper_session(tmp_path: Path) -> tuple[SQLiteDatabase, SQLiteActivePaperSessions]:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    sessions = SQLiteActivePaperSessions(database)
    CreatePaperSession(create_active=sessions.create).execute(
        PaperSessionSetupValues(
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
    )
    return database, sessions


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


def _sqlite_row_counts(database: SQLiteDatabase) -> dict[str, int]:
    with database.connect() as connection:
        table_names = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        )
        return {
            table_name: int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
            for table_name in table_names
        }


def _freeze_notification_clock(monkeypatch: MonkeyPatch) -> None:
    class _FixedDateTime:
        @staticmethod
        def now(timezone: object) -> datetime:
            assert timezone is UTC
            return _NOW

    monkeypatch.setattr(lifecycle_workflow_module, "datetime", _FixedDateTime)


def _block_private_or_live_imports(monkeypatch: MonkeyPatch) -> None:
    original_import = builtins.__import__
    forbidden_prefixes = (
        "keyring",
        "tiewtrade.application.live",
        "tiewtrade.execution.live",
        "tiewtrade.integrations.credentials",
        "tiewtrade.integrations.keyring",
        "tiewtrade.integrations.private_api",
        "tiewtrade.live",
    )

    def guarded_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if any(
            name == prefix or name.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        ):
            raise AssertionError(
                "notification feedback must not import private or Live code"
            )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def _block_network(monkeypatch: MonkeyPatch) -> None:
    def fail_network_attempt(*args: object, **kwargs: object) -> None:
        raise AssertionError("notification feedback must not attempt network access")

    monkeypatch.setattr(socket, "create_connection", fail_network_attempt)
    monkeypatch.setattr(socket, "getaddrinfo", fail_network_attempt)
    monkeypatch.setattr(socket.socket, "connect", fail_network_attempt)
