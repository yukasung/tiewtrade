import ast
import socket
import sqlite3
from collections.abc import Callable, Collection
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


def test_static_dependency_scanner_expands_from_import_aliases(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "src" / "tiewtrade" / "ui" / "dependency_fixture.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "from tiewtrade.integrations import private_api\n"
        "from tiewtrade.application import live as live_application\n"
        "from ..integrations import private_api as relative_private_api\n",
        encoding="utf-8",
    )

    imported_modules = _imported_modules(source_path)

    assert "tiewtrade.integrations.private_api" in imported_modules
    assert "tiewtrade.application.live" in imported_modules
    assert imported_modules.count("tiewtrade.integrations.private_api") == 2
    assert _forbidden_imports(
        imported_modules,
        (
            "tiewtrade.application.live",
            "tiewtrade.integrations.private_api",
        ),
    ) == {
        "tiewtrade.application.live",
        "tiewtrade.integrations.private_api",
    }


def test_paper_notification_feedback_shows_blocked_and_recovery_without_side_effects(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    _assert_notification_dependencies_are_safe()
    _freeze_notification_clock(monkeypatch)
    database, sessions = _paper_session(tmp_path)
    write_guard = _guard_durable_writes(monkeypatch, database)
    _prove_durable_write_guard_rejects_updates(database, write_guard)
    initial_durable_state = _sqlite_table_contents(database)
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

    assert write_guard.write_attempts == []
    assert _sqlite_table_contents(database) == initial_durable_state
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
    assert write_guard.write_attempts == []
    assert _sqlite_table_contents(database) == initial_durable_state


def test_paper_fake_stale_notification_keeps_safe_workspace_state(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    _assert_notification_dependencies_are_safe()
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


def _sqlite_table_contents(
    database: SQLiteDatabase,
) -> dict[str, tuple[tuple[object, ...], ...]]:
    with database.connect() as connection:
        table_names = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        )
        return {
            table_name: tuple(
                tuple(row)
                for row in connection.execute(
                    f"SELECT * FROM {table_name} ORDER BY rowid"
                )
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


class _DurableWriteGuard:
    def __init__(self) -> None:
        self.write_attempts: list[tuple[str, str | None]] = []

    def authorize(
        self,
        action_code: int,
        parameter_1: str | None,
        parameter_2: str | None,
        database_name: str | None,
        source: str | None,
    ) -> int:
        del parameter_2, database_name, source
        write_actions = {
            sqlite3.SQLITE_INSERT: "INSERT",
            sqlite3.SQLITE_UPDATE: "UPDATE",
            sqlite3.SQLITE_DELETE: "DELETE",
        }
        action = write_actions.get(action_code)
        if action is None:
            return sqlite3.SQLITE_OK
        self.write_attempts.append((action, parameter_1))
        return sqlite3.SQLITE_DENY


def _guard_durable_writes(
    monkeypatch: MonkeyPatch,
    database: SQLiteDatabase,
) -> _DurableWriteGuard:
    original_connect = SQLiteDatabase.connect
    guard = _DurableWriteGuard()

    def guarded_connect(instance: SQLiteDatabase) -> sqlite3.Connection:
        connection = original_connect(instance)
        if instance is database:
            connection.set_authorizer(guard.authorize)
        return connection

    monkeypatch.setattr(SQLiteDatabase, "connect", guarded_connect)
    return guard


def _prove_durable_write_guard_rejects_updates(
    database: SQLiteDatabase,
    guard: _DurableWriteGuard,
) -> None:
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with database.connect() as connection:
            connection.execute("UPDATE bot_sessions SET ended_at_utc = NULL")

    assert guard.write_attempts == [("UPDATE", "bot_sessions")]
    guard.write_attempts.clear()


def _assert_notification_dependencies_are_safe() -> None:
    forbidden_prefixes = (
        "aiohttp",
        "keyring",
        "tiewtrade.application.live",
        "tiewtrade.execution.live",
        "tiewtrade.integrations.credentials",
        "tiewtrade.integrations.keyring",
        "tiewtrade.integrations.private_api",
        "tiewtrade.live",
    )
    source_paths = (
        Path("src/tiewtrade/ui/notification_center.py"),
        Path("src/tiewtrade/ui/bot_lifecycle_workflow.py"),
        Path("src/tiewtrade/ui/trading_workspace.py"),
        Path("src/tiewtrade/ui/main_window.py"),
    )
    imported_modules = {
        module
        for source_path in source_paths
        for module in _imported_modules(source_path)
    }

    assert not _forbidden_imports(imported_modules, forbidden_prefixes)


def _imported_modules(source_path: Path) -> tuple[str, ...]:
    source = ast.parse(source_path.read_text(encoding="utf-8"))
    package = _package_for_source(source_path)
    modules: list[str] = []
    for node in ast.walk(source):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base_module = _import_from_base_module(node, package)
            if base_module is None:
                continue
            modules.append(base_module)
            modules.extend(
                f"{base_module}.{alias.name}"
                for alias in node.names
                if alias.name != "*"
            )
    return tuple(modules)


def _package_for_source(source_path: Path) -> str:
    source_parts = source_path.with_suffix("").parts
    source_index = source_parts.index("src")
    package_parts = source_parts[source_index + 1 : -1]
    if not package_parts:
        raise ValueError("source path must be inside a package below src")
    return ".".join(package_parts)


def _import_from_base_module(node: ast.ImportFrom, package: str) -> str | None:
    if node.level == 0:
        return node.module
    package_parts = package.split(".")
    parent_count = node.level - 1
    if parent_count >= len(package_parts):
        return node.module
    base_parts = package_parts[: len(package_parts) - parent_count]
    if node.module is not None:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _forbidden_imports(
    imported_modules: Collection[str],
    forbidden_prefixes: tuple[str, ...],
) -> set[str]:
    return {
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
    }


def _block_network(monkeypatch: MonkeyPatch) -> None:
    def fail_network_attempt(*args: object, **kwargs: object) -> None:
        raise AssertionError("notification feedback must not attempt network access")

    monkeypatch.setattr(socket, "create_connection", fail_network_attempt)
    monkeypatch.setattr(socket, "getaddrinfo", fail_network_attempt)
    monkeypatch.setattr(socket.socket, "connect", fail_network_attempt)
