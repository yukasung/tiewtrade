import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError
from types import TracebackType
from uuid import UUID

import pytest
from pytest import MonkeyPatch

import tiewtrade.desktop_main as desktop_main
import tiewtrade.ui.desktop as ui_desktop
from tests.support.trade_history_ui import empty_basket_page, empty_fills
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


class _CoordinatedUserVersionCursor:
    def __init__(self, cursor: sqlite3.Cursor, reads: Barrier) -> None:
        self._cursor = cursor
        self._reads = reads

    def fetchone(self) -> sqlite3.Row | tuple[int] | None:
        row = self._cursor.fetchone()
        if row is not None and row[0] == 1:
            try:
                self._reads.wait(timeout=0.5)
            except BrokenBarrierError:
                pass
        return row


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


def _create_v1_database(database: desktop_main.SQLiteDatabase) -> None:
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
    original_database = desktop_main.SQLiteDatabase

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
    ) -> int:
        captured["create_session"] = create_session
        captured["load_active"] = load_active
        captured["list_baskets"] = list_baskets
        captured["list_fills"] = list_fills
        return 0

    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    result = desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3")

    assert result == 0
    create_session = captured["create_session"]
    load_active = captured["load_active"]
    assert callable(create_session)
    assert callable(load_active)
    assert load_active() is None
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
    active = load_active()
    assert isinstance(active, ConfiguredPaperSession)
    assert active.config.session_id == outcome.session.config.session_id


def test_desktop_composition_supplies_migrated_trade_history_queries(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    migration_calls = 0
    original_migrate = desktop_main.SQLiteDatabase.migrate

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    def record_migrate(database: desktop_main.SQLiteDatabase) -> None:
        nonlocal migration_calls
        migration_calls += 1
        original_migrate(database)

    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)
    monkeypatch.setattr(desktop_main.SQLiteDatabase, "migrate", record_migrate)

    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    assert migration_calls == 0

    list_baskets = captured["list_baskets"]
    list_fills = captured["list_fills"]
    assert callable(list_baskets)
    assert callable(list_fills)
    assert list_baskets(TradeHistoryFilter(), PageRequest()).items == ()
    assert migration_calls == 1
    assert list_fills(UUID("00000000-0000-0000-0000-000000000001")) == ()
    assert migration_calls == 2
    assert list_baskets(TradeHistoryFilter(), PageRequest()).items == ()
    assert migration_calls == 3


def test_concurrent_session_load_and_history_query_serialize_v1_migration(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    _create_v1_database(desktop_main.SQLiteDatabase(database_path))
    captured: dict[str, object] = {}
    migration_reads = Barrier(2)
    worker_start = Barrier(2)
    original_connect = desktop_main.SQLiteDatabase.connect

    def coordinated_connect(
        database: desktop_main.SQLiteDatabase,
    ) -> _CoordinatedConnection:
        return _CoordinatedConnection(original_connect(database), migration_reads)

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    monkeypatch.setattr(desktop_main.SQLiteDatabase, "connect", coordinated_connect)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    assert desktop_main.run_desktop(database_path) == 0
    load_active = captured["load_active"]
    list_baskets = captured["list_baskets"]
    assert callable(load_active)
    assert callable(list_baskets)

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

    assert schema_version == 3
    assert "leverage" in basket_columns


def test_failed_database_preparation_can_be_retried_by_later_consumer(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    migration_attempts = 0
    original_migrate = desktop_main.SQLiteDatabase.migrate

    def fail_first_migration(database: desktop_main.SQLiteDatabase) -> None:
        nonlocal migration_attempts
        migration_attempts += 1
        if migration_attempts == 1:
            raise sqlite3.OperationalError("injected migration failure")
        original_migrate(database)

    def capture_desktop(**dependencies: object) -> int:
        captured.update(dependencies)
        return 0

    monkeypatch.setattr(desktop_main.SQLiteDatabase, "migrate", fail_first_migration)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)
    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    load_active = captured["load_active"]
    list_baskets = captured["list_baskets"]
    assert callable(load_active)
    assert callable(list_baskets)

    with pytest.raises(sqlite3.OperationalError, match="injected migration failure"):
        load_active()

    result = list_baskets(TradeHistoryFilter(), PageRequest())

    assert result.items == ()
    assert migration_attempts == 2


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

    assert (
        ui_desktop.run_desktop(
            create_session=lambda values: None,  # type: ignore[arg-type,return-value]
            load_active=lambda: None,
            list_baskets=empty_basket_page,
            list_fills=empty_fills,
        )
        == 0
    )
    assert captured["list_baskets"] is empty_basket_page
    assert captured["list_fills"] is empty_fills
    assert captured["shown"] is True


def test_desktop_composition_defers_database_directory_creation_to_load_worker(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    mkdir_calls: list[Path] = []
    original_mkdir = Path.mkdir

    def capture_desktop(
        *,
        create_session: object,
        load_active: object,
        list_baskets: object,
        list_fills: object,
    ) -> int:
        captured["create_session"] = create_session
        captured["load_active"] = load_active
        captured["list_baskets"] = list_baskets
        captured["list_fills"] = list_fills
        return 0

    def record_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        mkdir_calls.append(path)
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "mkdir", record_mkdir)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    result = desktop_main.run_desktop()

    assert result == 0
    assert mkdir_calls == []

    load_active = captured["load_active"]
    assert callable(load_active)
    assert load_active() is None
    assert (tmp_path / "Library" / "Application Support" / "TiewTrade") in mkdir_calls
