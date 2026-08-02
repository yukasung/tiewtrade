import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Event, Thread
from types import TracebackType
from typing import cast
from uuid import UUID

import pytest
from pytest import MonkeyPatch

import tiewtrade.desktop_main as desktop_main
import tiewtrade.ui.desktop as ui_desktop
from tests.support.paper_session_setup import configured_spot_session
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.bot_control import (
    BotControlAction,
    BotControlSnapshot,
    BotLifecycleResult,
    configured_bot_control,
    workspace_with_runtime_state,
)
from tiewtrade.application.database_compatibility import DatabaseCompatibilityError
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.application.trade_history import (
    BasketHistoryPage,
    PageRequest,
    TradeHistoryFilter,
)
from tiewtrade.application.trading_workspace import BotRuntimeState, DataFreshness
from tiewtrade.integrations.binance.public_market_data import BinancePublicMarketData
from tiewtrade.integrations.sqlite.database import (
    SQLiteDatabase,
    UnsupportedDatabaseSchemaError,
)
from tiewtrade.integrations.sqlite.paper_runtime_lifecycle import (
    SQLitePaperRuntimeLifecycle,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.symbol_rules import SymbolRules
from tiewtrade.ui.bot_lifecycle_workflow import LifecycleAction, RuntimeSnapshotRelay
from tiewtrade.ui.session_workflow import CreateSession, LoadActiveSession
from tiewtrade.ui.theme import DARK_THEME
from tiewtrade.ui.trade_history_workflow import ListBaskets, ListFills


class _CoordinatedUserVersionCursor:
    def __init__(self, cursor: sqlite3.Cursor, reads: Barrier) -> None:
        self._cursor = cursor
        self._reads = reads

    def fetchone(self) -> sqlite3.Row | tuple[int] | None:
        row = self._cursor.fetchone()
        if row is None:
            return None
        typed_row = cast(sqlite3.Row | tuple[int], row)
        if typed_row[0] == 1:
            try:
                self._reads.wait(timeout=0.5)
            except BrokenBarrierError:
                pass
        return typed_row


class _CoordinatedConnection:
    def __init__(self, connection: sqlite3.Connection, reads: Barrier) -> None:
        self._connection = connection
        self._reads = reads

    def execute(
        self,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> sqlite3.Cursor | _CoordinatedUserVersionCursor:
        cursor = self._connection.execute(sql, parameters)
        if sql.strip().casefold() == "pragma user_version":
            return _CoordinatedUserVersionCursor(cursor, self._reads)
        return cursor

    def __enter__(self) -> "_CoordinatedConnection":
        self._connection.__enter__()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return self._connection.__exit__(exception_type, exception, traceback)

    def close(self) -> None:
        self._connection.close()


def _create_v1_database(database: SQLiteDatabase) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TABLE basket_results (
                basket_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                trade_mode TEXT NOT NULL,
                market_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                strategy_preset_version TEXT NOT NULL,
                opened_at_utc TEXT NOT NULL,
                closed_at_utc TEXT,
                entry_count INTEGER NOT NULL,
                invested_notional TEXT NOT NULL,
                gross_realized_pnl TEXT NOT NULL,
                trading_fees TEXT NOT NULL,
                funding_fee TEXT NOT NULL,
                net_realized_pnl TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        connection.execute("PRAGMA user_version = 1")


def test_desktop_configures_decimal_context_before_composition(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    events: list[str] = []
    original_database = SQLiteDatabase

    def capture_database(path: Path) -> object:
        events.append("database")
        return original_database(path)

    monkeypatch.setattr(
        desktop_main,
        "configure_decimal_context",
        lambda: events.append("decimal"),
        raising=False,
    )
    monkeypatch.setattr(desktop_main, "SQLiteDatabase", capture_database)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", lambda **kwargs: 0)

    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    assert events == ["decimal", "database"]


def test_desktop_composition_supplies_migrated_create_and_load_operations(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def capture_desktop(
        *,
        create_session: object,
        load_active: object,
        list_baskets: object,
        list_fills: object,
        **dependencies: object,
    ) -> int:
        captured["create_session"] = create_session
        captured["load_active"] = load_active
        captured["list_baskets"] = list_baskets
        captured["list_fills"] = list_fills
        return 0

    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    result = desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3")

    assert result == 0
    create_session = cast(CreateSession, captured["create_session"])
    load_active_session = cast(LoadActiveSession, captured["load_active"])
    assert load_active_session() is None
    outcome = create_session(
        PaperSessionSetupValues(
            market_type="spot",
            symbol="BTCUSDT",
            timeframe="5m",
            available_capital="200000",
            max_entries="10",
            fee_percent="0",
            slippage_bps="0",
            spot_trading_capital_percent="80",
            futures_leverage=None,
        )
    )

    assert isinstance(outcome, PaperSessionCreateOutcome)
    assert outcome.created is True
    active = load_active_session()
    assert isinstance(active, ConfiguredPaperSession)
    assert active.config.session_id == outcome.session.config.session_id


def test_desktop_composition_supplies_migrated_trade_history_queries(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    migration_calls = 0
    original_migrate = SQLiteDatabase.migrate

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    def record_migrate(database: SQLiteDatabase) -> None:
        nonlocal migration_calls
        migration_calls += 1
        original_migrate(database)

    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)
    monkeypatch.setattr(SQLiteDatabase, "migrate", record_migrate)

    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    assert migration_calls == 0

    list_baskets = cast(ListBaskets, captured["list_baskets"])
    list_fills = cast(ListFills, captured["list_fills"])
    assert list_baskets(TradeHistoryFilter(), PageRequest()).items == ()
    assert migration_calls == 1
    assert list_fills(UUID("00000000-0000-0000-0000-000000000001")) == ()
    assert migration_calls == 2
    assert list_baskets(TradeHistoryFilter(), PageRequest()).items == ()
    assert migration_calls == 3


def test_desktop_composes_concrete_paper_runtime_actions(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    controllers: list[object] = []

    class FakePaperRuntimeController:
        def __init__(self, **dependencies: object) -> None:
            self.dependencies = dependencies
            self.snapshot_callback = cast(
                Callable[[object], None], dependencies["snapshot_callback"]
            )
            self.result: BotLifecycleResult | None = None
            self.stop_calls = 0
            controllers.append(self)

        @property
        def current_result(self) -> BotLifecycleResult:
            assert self.result is not None
            return self.result

        def inspect_startup(
            self,
            session: ConfiguredPaperSession,
        ) -> BotLifecycleResult:
            workspace = configured_bot_control(
                session,
                observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
            ).workspace
            self.result = BotLifecycleResult(workspace=workspace)
            self.snapshot_callback(workspace)
            return self.result

        def start(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            workspace = workspace_with_runtime_state(
                configured_bot_control(
                    session,
                    observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
                ).workspace,
                BotRuntimeState.RUNNING,
                data_freshness=DataFreshness.FRESH,
            )
            self.result = BotLifecycleResult(workspace=workspace)
            self.snapshot_callback(workspace)
            return self.result

        def stop(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            self.stop_calls += 1
            assert self.result is not None
            self.result = BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    self.result.workspace,
                    BotRuntimeState.STOPPED,
                )
            )
            self.snapshot_callback(self.result.workspace)
            return self.result

        def recover(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            workspace = configured_bot_control(
                session,
                observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
            ).workspace
            self.result = BotLifecycleResult(workspace=workspace)
            self.snapshot_callback(workspace)
            return self.result

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    monkeypatch.setattr(
        desktop_main,
        "PaperRuntimeController",
        FakePaperRuntimeController,
        raising=False,
    )
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0

    initialize_bot = cast(LifecycleAction, captured["initialize_bot"])
    start_bot = cast(LifecycleAction, captured["start_bot"])
    shutdown_runtime = cast(Callable[[], None], captured["shutdown_runtime"])
    session = configured_spot_session()
    start_snapshot = configured_bot_control(
        session,
        observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
    )

    initialized = initialize_bot(start_snapshot)

    assert initialized.workspace.header is not None
    assert initialized.workspace.header.runtime_state is BotRuntimeState.CONFIGURED
    assert len(controllers) == 1

    result = start_bot(start_snapshot)

    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.RUNNING
    assert len(controllers) == 2
    controller = cast(FakePaperRuntimeController, controllers[1])
    assert isinstance(controller.dependencies["lifecycle"], SQLitePaperRuntimeLifecycle)
    assert isinstance(controller.dependencies["trade_history"], SQLiteTradeHistory)
    rules = controller.dependencies["symbol_rules"]
    assert isinstance(rules, SymbolRules)
    assert rules.symbol == "BTCUSDT"
    assert rules.tick_size == Decimal("0.01")
    assert controller.dependencies["source_factory"] is BinancePublicMarketData
    assert isinstance(captured["runtime_snapshots"], RuntimeSnapshotRelay)

    shutdown_runtime()

    assert controller.stop_calls == 1


def test_runtime_shutdown_during_start_stops_controller_after_readiness(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    started = Event()
    release_start = Event()
    controllers: list[object] = []

    class SlowPaperRuntimeController:
        def __init__(self, **dependencies: object) -> None:
            del dependencies
            self.result: BotLifecycleResult | None = None
            self.stop_calls = 0
            controllers.append(self)

        @property
        def current_result(self) -> BotLifecycleResult:
            assert self.result is not None
            return self.result

        def start(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            started.set()
            if not release_start.wait(timeout=2):
                raise TimeoutError("test did not release start")
            self.result = BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    configured_bot_control(
                        session,
                        observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
                    ).workspace,
                    BotRuntimeState.RUNNING,
                    data_freshness=DataFreshness.FRESH,
                )
            )
            return self.result

        def stop(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            self.stop_calls += 1
            assert self.result is not None
            self.result = BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    self.result.workspace,
                    BotRuntimeState.STOPPED,
                )
            )
            return self.result

    monkeypatch.setattr(
        desktop_main,
        "PaperRuntimeController",
        SlowPaperRuntimeController,
    )
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    actions = desktop_main._PaperRuntimeActions(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        runtime_snapshots=RuntimeSnapshotRelay(),
        prepare_database=lambda: None,
    )
    session = configured_spot_session()
    errors: list[BaseException] = []

    def start_runtime() -> None:
        try:
            actions.start(
                configured_bot_control(
                    session,
                    observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
                )
            )
        except BaseException as error:
            errors.append(error)

    worker = Thread(target=start_runtime)
    worker.start()
    assert started.wait(timeout=1)

    shutdown_worker = Thread(target=actions.shutdown)
    shutdown_worker.start()

    controller = cast(SlowPaperRuntimeController, controllers[0])
    assert controller.stop_calls == 0
    assert shutdown_worker.is_alive()

    release_start.set()
    worker.join(timeout=1)
    shutdown_worker.join(timeout=1)

    assert not worker.is_alive()
    assert not shutdown_worker.is_alive()
    assert errors == []
    assert controller.stop_calls == 1


@pytest.mark.parametrize("operation", ["stop", "recover"])
def test_runtime_shutdown_waits_for_active_lifecycle_operation_without_duplicate(
    operation: str,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    operation_started = Event()
    release_operation = Event()
    controllers: list[object] = []

    class BlockingPaperRuntimeController:
        def __init__(self, **dependencies: object) -> None:
            del dependencies
            self.result: BotLifecycleResult | None = None
            self.stop_calls = 0
            self.recover_calls = 0
            controllers.append(self)

        @property
        def current_result(self) -> BotLifecycleResult:
            assert self.result is not None
            return self.result

        def start(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            self.result = BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    configured_bot_control(
                        session,
                        observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
                    ).workspace,
                    BotRuntimeState.RUNNING,
                    data_freshness=DataFreshness.FRESH,
                )
            )
            return self.result

        def stop(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            self.stop_calls += 1
            if operation == "stop":
                operation_started.set()
                if not release_operation.wait(timeout=2):
                    raise TimeoutError("test did not release Stop")
            assert self.result is not None
            self.result = BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    self.result.workspace,
                    BotRuntimeState.STOPPED,
                )
            )
            return self.result

        def recover(self, session: ConfiguredPaperSession) -> BotLifecycleResult:
            self.recover_calls += 1
            operation_started.set()
            if not release_operation.wait(timeout=2):
                raise TimeoutError("test did not release Recover")
            assert self.result is not None
            self.result = BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    self.result.workspace,
                    BotRuntimeState.BLOCKED,
                ),
                blocked_reason="Paper Bot recovery failed",
            )
            return self.result

    monkeypatch.setattr(
        desktop_main,
        "PaperRuntimeController",
        BlockingPaperRuntimeController,
    )
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    actions = desktop_main._PaperRuntimeActions(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        runtime_snapshots=RuntimeSnapshotRelay(),
        prepare_database=lambda: None,
    )
    session = configured_spot_session()
    configured = configured_bot_control(
        session,
        observed_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
    )
    running_result = actions.start(configured)
    running = BotControlSnapshot(
        state=BotRuntimeState.RUNNING,
        session=session,
        workspace=running_result.workspace,
        available_actions=frozenset({BotControlAction.STOP}),
    )
    if operation == "stop":
        lifecycle_snapshot = running
        lifecycle_action = actions.stop
    else:
        blocked_workspace = workspace_with_runtime_state(
            running.workspace,
            BotRuntimeState.BLOCKED,
        )
        lifecycle_snapshot = BotControlSnapshot(
            state=BotRuntimeState.BLOCKED,
            session=session,
            workspace=blocked_workspace,
            available_actions=frozenset({BotControlAction.RECOVER}),
            blocked_reason="Paper Bot recovery failed",
        )
        lifecycle_action = actions.recover

    action_worker = Thread(target=lambda: lifecycle_action(lifecycle_snapshot))
    action_worker.start()
    assert operation_started.wait(timeout=1)
    shutdown_worker = Thread(target=actions.shutdown)
    shutdown_worker.start()

    assert shutdown_worker.is_alive()

    release_operation.set()
    action_worker.join(timeout=1)
    shutdown_worker.join(timeout=1)

    controller = cast(BlockingPaperRuntimeController, controllers[0])
    assert not action_worker.is_alive()
    assert not shutdown_worker.is_alive()
    assert controller.recover_calls == (1 if operation == "recover" else 0)
    assert controller.stop_calls == 1


def test_runtime_symbol_rules_derive_symbol_from_session_market_data() -> None:
    session = configured_spot_session()
    session = replace(
        session,
        market_data=replace(session.market_data, symbol="ETHUSDT"),
    )

    rules = desktop_main._symbol_rules_for(session)

    assert rules.symbol == "ETHUSDT"


def test_concurrent_session_load_and_history_query_serialize_v1_migration(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    _create_v1_database(SQLiteDatabase(database_path))
    captured: dict[str, object] = {}
    migration_reads = Barrier(2)
    worker_start = Barrier(2)
    original_connect = SQLiteDatabase.connect

    def coordinated_connect(
        database: SQLiteDatabase,
    ) -> _CoordinatedConnection:
        return _CoordinatedConnection(original_connect(database), migration_reads)

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    monkeypatch.setattr(SQLiteDatabase, "connect", coordinated_connect)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    assert desktop_main.run_desktop(database_path) == 0
    load_active = cast(LoadActiveSession, captured["load_active"])
    list_baskets = cast(ListBaskets, captured["list_baskets"])

    def load_session() -> ConfiguredPaperSession | None:
        worker_start.wait()
        return load_active()

    def query_history() -> BasketHistoryPage:
        worker_start.wait()
        return list_baskets(TradeHistoryFilter(), PageRequest())

    with ThreadPoolExecutor(max_workers=2) as pool:
        load_result = pool.submit(load_session)
        history_result = pool.submit(query_history)

        assert load_result.result() is None
        assert history_result.result().items == ()

    with sqlite3.connect(database_path) as connection:
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        basket_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(basket_results)")
        }

    assert schema_version == 5
    assert "leverage" in basket_columns


def test_failed_database_preparation_can_be_retried_by_later_consumer(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    migration_attempts = 0
    original_migrate = SQLiteDatabase.migrate

    def fail_first_migration(database: SQLiteDatabase) -> None:
        nonlocal migration_attempts
        migration_attempts += 1
        if migration_attempts == 1:
            raise sqlite3.OperationalError("injected migration failure")
        original_migrate(database)

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    monkeypatch.setattr(SQLiteDatabase, "migrate", fail_first_migration)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)
    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    load_active = cast(LoadActiveSession, captured["load_active"])
    list_baskets = cast(ListBaskets, captured["list_baskets"])

    with pytest.raises(sqlite3.OperationalError, match="injected migration failure"):
        load_active()

    result = list_baskets(TradeHistoryFilter(), PageRequest())

    assert result.items == ()
    assert migration_attempts == 2


def test_newer_schema_is_translated_at_desktop_composition_boundary(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def reject_newer_schema(database: SQLiteDatabase) -> None:
        raise UnsupportedDatabaseSchemaError(
            database_version=4,
            supported_version=3,
        )

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    monkeypatch.setattr(SQLiteDatabase, "migrate", reject_newer_schema)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)
    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    load_active = cast(LoadActiveSession, captured["load_active"])

    with pytest.raises(DatabaseCompatibilityError) as caught:
        load_active()

    assert isinstance(caught.value.__cause__, UnsupportedDatabaseSchemaError)


def test_ui_desktop_forwards_required_trade_history_dependencies(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeApplication:
        @classmethod
        def instance(cls) -> "FakeApplication":
            return cls()

        def exec(self) -> int:
            return 0

    class FakeMainWindow:
        def __init__(self, **dependencies: object) -> None:
            captured.update(dependencies)

        def setStyleSheet(self, style_sheet: str) -> None:
            captured["style_sheet"] = style_sheet

        def show(self) -> None:
            captured["shown"] = True

    monkeypatch.setattr(ui_desktop, "QApplication", FakeApplication)
    monkeypatch.setattr(ui_desktop, "MainWindow", FakeMainWindow)
    runtime_snapshots = RuntimeSnapshotRelay()

    def shutdown_runtime() -> None:
        pass

    assert (
        ui_desktop.run_desktop(
            create_session=lambda values: None,  # type: ignore[arg-type,return-value]
            load_active=lambda: None,
            list_baskets=empty_basket_page,
            list_fills=empty_fills,
            runtime_snapshots=runtime_snapshots,
            shutdown_runtime=shutdown_runtime,
        )
        == 0
    )
    assert captured["list_baskets"] is empty_basket_page
    assert captured["list_fills"] is empty_fills
    assert captured["runtime_snapshots"] is runtime_snapshots
    assert captured["shutdown_runtime"] is shutdown_runtime
    assert captured["style_sheet"] == DARK_THEME
    assert captured["shown"] is True


def test_desktop_composition_defers_database_directory_creation_to_load_worker(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    mkdir_calls: list[tuple[Path, int, bool, bool]] = []
    original_mkdir = Path.mkdir

    def capture_desktop(
        *,
        create_session: object,
        load_active: object,
        list_baskets: object,
        list_fills: object,
        **dependencies: object,
    ) -> int:
        captured["create_session"] = create_session
        captured["load_active"] = load_active
        captured["list_baskets"] = list_baskets
        captured["list_fills"] = list_fills
        return 0

    def record_mkdir(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        mkdir_calls.append((path, mode, parents, exist_ok))
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "mkdir", record_mkdir)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    result = desktop_main.run_desktop()

    assert result == 0
    assert mkdir_calls == []

    load_active = cast(LoadActiveSession, captured["load_active"])
    assert load_active() is None
    assert (
        tmp_path / "Library" / "Application Support" / "TiewTrade",
        0o777,
        True,
        True,
    ) in mkdir_calls
