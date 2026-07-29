from pathlib import Path
from uuid import UUID

from pytest import MonkeyPatch

import tiewtrade.desktop_main as desktop_main
import tiewtrade.ui.desktop as ui_desktop
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.application.trade_history import PageRequest, TradeHistoryFilter


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
