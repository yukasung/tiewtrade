import ast
import socket
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import UUID

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

from tests.support.qt_interactions import click, table_item
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.bot_control import (
    BotControlSnapshot,
    BotLifecycleResult,
    workspace_with_runtime_state,
)
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    CreatePaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    DataFreshness,
    OpenOrderSnapshot,
    TradingWorkspaceSnapshot,
    configured_workspace_snapshot,
    ready_open_orders_tab,
    ready_position_basket_tab,
)
from tiewtrade.execution.paper_spot import PaperSpotEntryFill
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_spot_history import (
    PaperSpotHistoryContext,
    PaperSpotSQLiteHistory,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.futures_policy import MarginMode, PositionMode
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.ui.main_window import MainWindow


@dataclass(frozen=True, slots=True)
class _SessionCase:
    market_type: str
    timeframe: str
    max_entries: int
    fee_percent: str
    slippage_bps: str
    spot_ratio: str | None
    futures_leverage: int | None


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _SessionCase("spot", "15m", 12, "0.1", "5", "80", None),
            id="spot",
        ),
        pytest.param(
            _SessionCase("futures", "1h", 14, "0.2", "8", None, 4),
            id="futures",
        ),
    ],
)
def test_desktop_fake_snapshots_render_orders_and_basket_without_manual_trading(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
    case: _SessionCase,
) -> None:
    _block_network(monkeypatch)
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    session = (
        CreatePaperSession(create_active=store.create)
        .execute(_setup_values(case))
        .session
    )
    initial_counts = _trade_side_effect_counts(database)
    assert initial_counts == (0, 0)
    start_calls = 0

    def fake_start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        nonlocal start_calls
        start_calls += 1
        return BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                snapshot.workspace,
                BotRuntimeState.RUNNING,
                data_freshness=DataFreshness.FRESH,
            )
        )

    window = MainWindow(
        create_session=lambda values: pytest.fail("create must not run"),
        load_active=store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        start_bot=fake_start,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.overview.isVisible)
    qtbot.waitUntil(
        window.workspace.bot_control_widget.start_button.isEnabled,
        timeout=250,
    )
    click(window.workspace.bot_control_widget.start_button)
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Running")

    window.workspace.show_workspace_snapshot(
        _fake_running_workspace(session, observed_at=datetime(2026, 8, 2, tzinfo=UTC))
    )

    assert start_calls == 1
    assert window.workspace.header_runtime.text() == "Running"
    assert window.workspace.open_orders.table.rowCount() == 1
    assert table_item(window.workspace.open_orders.table, 0, 0).text() == (
        "entry-order-1"
    )
    assert table_item(window.workspace.open_orders.table, 0, 7).text() == "0.00150000"
    assert table_item(window.workspace.open_orders.table, 0, 8).text() == (
        "Partially Filled"
    )
    assert window.workspace.position_basket.table.rowCount() == 1
    assert table_item(window.workspace.position_basket.table, 0, 1).text() == (
        case.market_type.title()
    )
    assert table_item(window.workspace.position_basket.table, 0, 2).text() == "1"
    assert table_item(window.workspace.position_basket.table, 0, 8).text() == (
        "—" if case.market_type == "spot" else "44000.5000"
    )
    assert _manual_order_buttons(window) == ()
    assert _trade_side_effect_counts(database) == initial_counts


def test_spot_partial_fills_keep_one_order_and_basket_entry_across_tabs(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    active_sessions = SQLiteActivePaperSessions(database)
    session = (
        CreatePaperSession(create_active=active_sessions.create)
        .execute(_setup_values(_SessionCase("spot", "5m", 10, "0.1", "5", "80", None)))
        .session
    )
    store = SQLiteTradeHistory(database)
    history = PaperSpotSQLiteHistory(
        PaperSpotHistoryContext(
            session_id=session.config.session_id,
            symbol=session.market_data.symbol,
            timeframe=session.market_data.timeframe,
            preset_version=session.config.preset_version,
            commission_asset="USDT",
        ),
        store,
    )
    observed_at = datetime(2026, 8, 2, tzinfo=UTC)
    fills = (
        PaperSpotEntryFill(
            intent_id="intent-1",
            order_id="entry-order-1",
            fill_id="fill-1",
            price=Decimal("66000.1250"),
            quantity=Decimal("0.00100000"),
            fee=Decimal("0.0660001250"),
            filled_at=observed_at,
        ),
        PaperSpotEntryFill(
            intent_id="intent-1",
            order_id="entry-order-1",
            fill_id="fill-2",
            price=Decimal("66000.1250"),
            quantity=Decimal("0.00050000"),
            fee=Decimal("0.0330000625"),
            filled_at=observed_at + timedelta(seconds=1),
        ),
    )
    for fill in fills:
        assert history.record_entry(
            basket_id=UUID("00000000-0000-0000-0000-000000000135"),
            entry_number=1,
            fill=fill,
        )

    basket_id = UUID("00000000-0000-0000-0000-000000000135")
    basket = store.get_basket(basket_id)
    durable_fills = store.list_fills(basket_id)
    assert basket is not None
    assert basket.entry_count == 1
    assert len(durable_fills) == 2
    assert {fill.order_id for fill in durable_fills} == {"entry-order-1"}
    initial_counts = _trade_side_effect_counts(database)
    assert initial_counts == (1, 2)

    window = MainWindow(
        create_session=lambda values: pytest.fail("create must not run"),
        load_active=active_sessions.get_active,
        list_baskets=store.list_baskets,
        list_fills=store.list_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.overview.isVisible)
    window.workspace.show_workspace_snapshot(
        _fake_running_workspace(session, observed_at=observed_at)
    )

    assert window.workspace.open_orders.table.rowCount() == 1
    assert table_item(window.workspace.open_orders.table, 0, 0).text() == (
        durable_fills[0].order_id
    )
    assert window.workspace.position_basket.table.rowCount() == 1
    assert table_item(window.workspace.position_basket.table, 0, 2).text() == "1"
    window.workspace.tabs.setCurrentWidget(window.trade_history)
    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 1)
    qtbot.waitUntil(lambda: window.trade_history.fill_table.rowCount() == 2)
    assert table_item(window.trade_history.basket_table, 0, 5).text() == "1"
    assert _trade_side_effect_counts(database) == initial_counts


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _SessionCase(
                market_type="spot",
                timeframe="15m",
                max_entries=12,
                fee_percent="0.1",
                slippage_bps="5",
                spot_ratio="80",
                futures_leverage=None,
            ),
            id="spot",
        ),
        pytest.param(
            _SessionCase(
                market_type="futures",
                timeframe="1h",
                max_entries=14,
                fee_percent="0.2",
                slippage_bps="8",
                spot_ratio=None,
                futures_leverage=4,
            ),
            id="futures",
        ),
    ],
)
def test_desktop_paper_session_create_overview_and_restart_restore(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
    case: _SessionCase,
) -> None:
    _block_network(monkeypatch)
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    first_store = SQLiteActivePaperSessions(database)
    initial_side_effect_counts = _trade_side_effect_counts(database)
    assert initial_side_effect_counts == (0, 0)
    expected_session_id = UUID("00000000-0000-0000-0000-000000000115")
    expected_created_at = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
    create_use_case = CreatePaperSession(
        create_active=first_store.create,
        session_ids=lambda: expected_session_id,
        clock=lambda: expected_created_at,
    )
    create_calls = 0

    def create_from_form(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        nonlocal create_calls
        create_calls += 1
        return create_use_case.execute(values)

    first_window = MainWindow(
        create_session=create_from_form,
        load_active=first_store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(first_window)
    first_window.show()
    qtbot.waitUntil(first_window.setup.create_button.isEnabled)

    assert first_window.findChildren(QPushButton, "manualBuyButton") == []
    assert first_window.findChildren(QPushButton, "manualSellButton") == []
    assert first_window.workspace.chart_state.text() == "Chart is not available yet"
    assert first_window.workspace.open_orders.state_label.text() == "No open orders"
    assert first_window.workspace.position_basket.state_label.text() == (
        "No open Position or Basket"
    )
    assert _trade_side_effect_counts(database) == initial_side_effect_counts

    first_window.workspace.tabs.setCurrentWidget(first_window.trade_history)
    qtbot.waitUntil(
        lambda: first_window.trade_history.basket_state.text() == "No trade history"
    )
    assert first_window.workspace.header_runtime.text() == "No Session"
    assert first_window.workspace.header_read_state.text() == "Empty"
    first_window.workspace.tabs.setCurrentIndex(0)

    _enter_form_values(first_window, case)
    click(first_window.setup.create_button)
    qtbot.waitUntil(first_window.overview.isVisible)

    durable_session = SQLiteActivePaperSessions(
        SQLiteDatabase(database_path)
    ).get_active()
    assert durable_session is not None
    assert create_calls == 1
    assert durable_session.config.session_id == expected_session_id
    assert durable_session.created_at_utc == expected_created_at
    _assert_durable_session_matches_case(
        durable_session,
        case,
        expected_session_id=expected_session_id,
        expected_created_at=expected_created_at,
    )
    _assert_overview_matches_case(
        first_window,
        case,
        expected_session_id=expected_session_id,
        expected_created_at=expected_created_at,
    )
    assert _active_session_count(database) == 1
    assert _trade_side_effect_counts(database) == initial_side_effect_counts

    first_window.resize(1199, 700)
    qtbot.waitUntil(lambda: first_window.workspace.compact_mode)
    assert first_window.workspace.bot_control_button.isVisible()

    first_window.workspace.tabs.setCurrentWidget(first_window.trade_history)
    assert first_window.workspace.tabs.currentWidget() is first_window.trade_history
    first_window.workspace.tabs.setCurrentIndex(0)

    second_create_use_case = CreatePaperSession(
        create_active=SQLiteActivePaperSessions(SQLiteDatabase(database_path)).create,
        session_ids=lambda: UUID("00000000-0000-0000-0000-000000000116"),
        clock=lambda: expected_created_at,
    )

    second_outcome = second_create_use_case.execute(_setup_values(case))

    assert second_outcome.created is False
    assert second_outcome.session == durable_session
    _assert_durable_session_matches_case(
        second_outcome.session,
        case,
        expected_session_id=expected_session_id,
        expected_created_at=expected_created_at,
    )
    assert _active_session_count(database) == 1
    assert _trade_side_effect_counts(database) == initial_side_effect_counts

    first_window.close()
    qtbot.waitUntil(first_window.isHidden)

    restarted_store = SQLiteActivePaperSessions(SQLiteDatabase(database_path))
    restarted_session = restarted_store.get_active()
    assert restarted_session is not None
    _assert_durable_session_matches_case(
        restarted_session,
        case,
        expected_session_id=expected_session_id,
        expected_created_at=expected_created_at,
    )

    def create_must_not_run(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        pytest.fail("restart must restore the active Paper Session without create")

    restarted_window = MainWindow(
        create_session=create_must_not_run,
        load_active=restarted_store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(restarted_window)
    restarted_window.show()
    qtbot.waitUntil(restarted_window.overview.isVisible)

    _assert_overview_matches_case(
        restarted_window,
        case,
        expected_session_id=expected_session_id,
        expected_created_at=expected_created_at,
    )
    assert _active_session_count(database) == 1
    assert _trade_side_effect_counts(database) == initial_side_effect_counts

    restored_history_side_effect_counts = _trade_side_effect_counts(database)
    restarted_window.workspace.tabs.setCurrentWidget(restarted_window.trade_history)
    qtbot.waitUntil(
        lambda: restarted_window.trade_history.basket_state.text() == "No trade history"
    )
    assert restarted_window.overview.isVisible()
    assert _trade_side_effect_counts(database) == restored_history_side_effect_counts


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _SessionCase("spot", "15m", 12, "0.1", "5", "80", None),
            id="spot",
        ),
        pytest.param(
            _SessionCase("futures", "1h", 14, "0.2", "8", None, 4),
            id="futures",
        ),
    ],
)
def test_desktop_fake_lifecycle_has_no_trade_storage_side_effects(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
    case: _SessionCase,
) -> None:
    _block_network(monkeypatch)
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    durable = (
        CreatePaperSession(create_active=store.create)
        .execute(_setup_values(case))
        .session
    )
    initial_counts = _trade_side_effect_counts(database)
    start_entered = Event()
    release_start = Event()
    stop_entered = Event()
    release_stop = Event()

    def fake_start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        start_entered.set()
        assert release_start.wait(timeout=1)
        return BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                snapshot.workspace,
                BotRuntimeState.RUNNING,
                data_freshness=DataFreshness.FRESH,
            )
        )

    def fake_stop(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        stop_entered.set()
        assert release_stop.wait(timeout=1)
        return BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                snapshot.workspace,
                BotRuntimeState.STOPPED,
            )
        )

    window = MainWindow(
        create_session=lambda values: pytest.fail("create must not run"),
        load_active=lambda: durable,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        start_bot=fake_start,
        stop_bot=fake_stop,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(
        lambda: window.workspace.bot_control_widget.start_button.isEnabled()
    )

    click(window.workspace.bot_control_widget.start_button)
    qtbot.waitUntil(start_entered.is_set)
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Starting")
    release_start.set()
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Running")

    assert window.workspace.bot_control_widget.stop_button.text() == "Stop Session"
    assert window.findChildren(QPushButton, "manualBuyButton") == []
    assert window.findChildren(QPushButton, "manualSellButton") == []
    assert _trade_side_effect_counts(database) == initial_counts

    click(window.workspace.bot_control_widget.stop_button)
    confirmation = window.findChild(QMessageBox)
    assert confirmation is not None
    assert confirmation.defaultButton().text() == "Cancel"
    confirm_button = next(
        button for button in confirmation.buttons() if button.text() == "Stop Session"
    )
    click(confirm_button)
    qtbot.waitUntil(stop_entered.is_set)
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Stopping")
    release_stop.set()
    qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Stopped")

    assert _trade_side_effect_counts(database) == initial_counts


def test_desktop_session_storage_unavailable_fails_closed(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    unavailable_path = tmp_path / "unavailable-session-storage"
    unavailable_path.mkdir()
    unavailable_store = SQLiteActivePaperSessions(SQLiteDatabase(unavailable_path))
    create_calls = 0

    def create_must_not_run(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        nonlocal create_calls
        create_calls += 1
        raise AssertionError("create must not run while session storage is unavailable")

    window = MainWindow(
        create_session=create_must_not_run,
        load_active=unavailable_store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.unavailable_panel.isVisible)

    assert create_calls == 0
    assert window.unavailable_message.text() == "Session storage is unavailable"
    assert str(unavailable_path) not in window.unavailable_message.text()
    assert "sqlite" not in window.unavailable_message.text().casefold()
    assert not window.setup.isVisible()
    assert not window.overview.isVisible()

    window.workspace.tabs.setCurrentWidget(window.trade_history)
    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "No trade history"
    )
    assert window.workspace.tabs.currentWidget() is window.trade_history
    assert window.unavailable_panel.isVisible()


def test_desktop_session_sqlite_write_failure_after_setup_fails_closed(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    database_path = tmp_path / "tiewtrade.sqlite3"
    durable_database = SQLiteDatabase(database_path)
    durable_database.migrate()
    failed_store = SQLiteActivePaperSessions(_CommitFailingDatabase(database_path))
    create_use_case = CreatePaperSession(create_active=failed_store.create)
    window = MainWindow(
        create_session=create_use_case.execute,
        load_active=failed_store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    _enter_form_values(
        window,
        _SessionCase(
            market_type="spot",
            timeframe="15m",
            max_entries=12,
            fee_percent="0.1",
            slippage_bps="5",
            spot_ratio="80",
            futures_leverage=None,
        ),
    )
    click(window.setup.create_button)
    qtbot.waitUntil(window.unavailable_panel.isVisible)

    assert window.unavailable_message.text() == "Session storage is unavailable"
    assert window.setup.available_capital.text() == "200000"
    assert window.setup.timeframe.currentData() == "15m"
    assert window.setup.max_entries.value() == 12
    assert window.setup.spot_ratio.text() == "80"
    assert window.setup.fee_percent.text() == "0.1"
    assert window.setup.slippage_bps.text() == "5"
    assert not window.overview.isVisible()
    assert SQLiteActivePaperSessions(durable_database).get_active() is None


def test_desktop_session_validation_failure_after_setup_preserves_input(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    create_use_case = CreatePaperSession(create_active=store.create)
    window = MainWindow(
        create_session=create_use_case.execute,
        load_active=store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    _enter_form_values(
        window,
        _SessionCase(
            market_type="spot",
            timeframe="15m",
            max_entries=12,
            fee_percent="0.1",
            slippage_bps="5",
            spot_ratio="80",
            futures_leverage=None,
        ),
    )
    window.setup.available_capital.setText("0")
    click(window.setup.create_button)
    qtbot.waitUntil(
        lambda: (
            window.setup.available_capital_error.text()
            == "Available Capital must be positive"
        )
    )

    assert window.setup.isVisible()
    assert window.setup.available_capital.text() == "0"
    assert window.setup.timeframe.currentData() == "15m"
    assert window.setup.max_entries.value() == 12
    assert window.setup.spot_ratio.text() == "80"
    assert window.setup.fee_percent.text() == "0.1"
    assert window.setup.slippage_bps.text() == "5"
    assert not window.overview.isVisible()
    assert store.get_active() is None


def test_desktop_session_setup_sources_exclude_runtime_and_sensitive_imports() -> None:
    ui_source_paths = tuple(sorted(Path("src/tiewtrade/ui").rglob("*.py")))
    session_setup_source_paths = (
        Path("src/tiewtrade/application/paper_session_setup.py"),
    )
    desktop_composition_path = Path("src/tiewtrade/desktop_main.py")
    ui_forbidden_prefixes = (
        "aiohttp",
        "keyring",
        "tiewtrade.application.paper_futures_session",
        "tiewtrade.application.paper_spot_market_data",
        "tiewtrade.application.paper_spot_session",
        "tiewtrade.application.public_market_data_runtime",
        "tiewtrade.execution",
        "tiewtrade.integrations.binance",
        "tiewtrade.integrations.credentials",
        "tiewtrade.integrations.keyring",
        "tiewtrade.integrations.private_api",
        "tiewtrade.strategies",
        "tiewtrade.trading.entry_pair",
    )
    composition_forbidden_prefixes = (
        "aiohttp",
        "keyring",
        "tiewtrade.application.paper_futures_session",
        "tiewtrade.application.paper_spot_market_data",
        "tiewtrade.application.paper_spot_session",
        "tiewtrade.application.public_market_data_runtime",
        "tiewtrade.integrations.binance",
        "tiewtrade.integrations.credentials",
        "tiewtrade.integrations.keyring",
        "tiewtrade.integrations.private_api",
        "tiewtrade.execution",
        "tiewtrade.market_data.candle_pipeline",
        "tiewtrade.market_data.candle_source",
        "tiewtrade.market_data.completed_candle_stream",
        "tiewtrade.market_data.runtime",
        "tiewtrade.strategies.rsi_step_grid.strategy",
        "tiewtrade.trading.entry_pair",
    )
    desktop_forbidden_prefixes = (
        "aiohttp",
        "keyring",
        "tiewtrade.application.live",
        "tiewtrade.execution.live",
        "tiewtrade.integrations.credentials",
        "tiewtrade.integrations.keyring",
        "tiewtrade.integrations.private_api",
        "tiewtrade.live",
    )

    assert ui_source_paths
    assert not _forbidden_imports(
        ui_source_paths,
        forbidden_prefixes=ui_forbidden_prefixes,
        restrict_market_data_to_config=True,
    )
    assert not _forbidden_imports(
        session_setup_source_paths,
        forbidden_prefixes=composition_forbidden_prefixes,
        restrict_market_data_to_config=False,
    )
    desktop_imports = _imported_modules(desktop_composition_path)
    assert not {
        module
        for module in desktop_imports
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in desktop_forbidden_prefixes
        )
    }
    assert not _sensitive_terms(
        ui_source_paths + session_setup_source_paths + (desktop_composition_path,)
    )


def test_desktop_session_setup_smoke_composes_without_network(
    qapp: QApplication,
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _block_network(monkeypatch)
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    create_use_case = CreatePaperSession(create_active=store.create)
    window = MainWindow(
        create_session=create_use_case.execute,
        load_active=store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)

    window.show()
    qapp.processEvents()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible())

    assert qapp.platformName() == "offscreen"
    assert not window.isVisible()


def _fake_running_workspace(
    session: ConfiguredPaperSession,
    *,
    observed_at: datetime,
) -> TradingWorkspaceSnapshot:
    configured = configured_workspace_snapshot(session, observed_at_utc=observed_at)
    with_facts = replace(
        configured,
        open_orders=ready_open_orders_tab(
            (
                OpenOrderSnapshot(
                    order_id="entry-order-1",
                    created_at_utc=observed_at,
                    symbol="BTCUSDT",
                    side="buy",
                    order_type="limit",
                    price=Decimal("66321.1200"),
                    quantity=Decimal("0.00300000"),
                    filled_quantity=Decimal("0.00150000"),
                    status="partially_filled",
                ),
            ),
            observed_at_utc=observed_at,
        ),
        position_basket=ready_position_basket_tab(
            BasketSnapshot(
                symbol="BTCUSDT",
                market_type=session.config.market_type.value,
                entry_count=1,
                total_quantity=Decimal("0.00150000"),
                average_entry_price=Decimal("66000.1250"),
                current_price=Decimal("66321.1200"),
                take_profit_price=Decimal("67000.0000"),
                unrealized_pnl=Decimal("1.92600000"),
                liquidation_price=(
                    None
                    if session.config.market_type is MarketType.SPOT
                    else Decimal("44000.5000")
                ),
                lifecycle="active_pair",
                updated_at_utc=observed_at,
            ),
            observed_at_utc=observed_at,
        ),
    )
    return workspace_with_runtime_state(
        with_facts,
        BotRuntimeState.RUNNING,
        data_freshness=DataFreshness.FRESH,
    )


def _manual_order_buttons(window: MainWindow) -> tuple[QPushButton, ...]:
    object_names = {"manualBuyButton", "manualSellButton"}
    manual_texts = {"buy", "sell"}
    return tuple(
        button
        for button in window.findChildren(QPushButton)
        if button.objectName() in object_names
        or button.text().strip().casefold() in manual_texts
    )


def _enter_form_values(window: MainWindow, case: _SessionCase) -> None:
    setup = window.setup
    setup.market_type.setCurrentIndex(setup.market_type.findData(case.market_type))
    setup.timeframe.setCurrentIndex(setup.timeframe.findData(case.timeframe))
    setup.available_capital.setText("200000")
    setup.max_entries.setValue(case.max_entries)
    setup.advanced_toggle.click()
    setup.fee_percent.setText(case.fee_percent)
    setup.slippage_bps.setText(case.slippage_bps)
    if case.market_type == "spot":
        assert case.spot_ratio is not None
        setup.spot_ratio.setText(case.spot_ratio)
        return
    assert case.futures_leverage is not None
    setup.leverage.setValue(case.futures_leverage)


def _setup_values(case: _SessionCase) -> PaperSessionSetupValues:
    return PaperSessionSetupValues(
        market_type=case.market_type,
        symbol="BTCUSDT",
        timeframe=case.timeframe,
        available_capital="200000",
        max_entries=str(case.max_entries),
        fee_percent=case.fee_percent,
        slippage_bps=case.slippage_bps,
        spot_trading_capital_percent=case.spot_ratio,
        futures_leverage=(
            None if case.futures_leverage is None else str(case.futures_leverage)
        ),
    )


def _assert_durable_session_matches_case(
    session: ConfiguredPaperSession,
    case: _SessionCase,
    *,
    expected_session_id: UUID,
    expected_created_at: datetime,
) -> None:
    config = session.config

    assert config.session_id == expected_session_id
    assert config.trade_mode is TradeMode.PAPER
    assert config.market_type is MarketType(case.market_type)
    assert config.preset_version == "rsi-step-grid-v1"
    assert config.available_capital == Decimal("200000")
    assert config.entry_policy.max_entries == case.max_entries
    assert config.fee_rate == Decimal(case.fee_percent) / Decimal("100")
    assert config.slippage_bps == Decimal(case.slippage_bps)
    assert session.market_data.symbol == "BTCUSDT"
    assert session.market_data.timeframe == case.timeframe
    assert session.created_at_utc == expected_created_at
    assert session.ended_at_utc is None

    if case.market_type == "spot":
        assert case.spot_ratio is not None
        assert config.spot_policy is not None
        expected_spot_ratio = Decimal(case.spot_ratio) / Decimal("100")
        assert config.spot_policy.trading_capital_ratio == expected_spot_ratio
        assert config.spot_policy.reserve_ratio == Decimal("1") - expected_spot_ratio
        assert config.futures_policy is None
        return

    assert case.futures_leverage is not None
    assert config.spot_policy is None
    assert config.futures_policy is not None
    assert config.futures_policy.version == "paper-futures-v1"
    assert config.futures_policy.leverage == case.futures_leverage
    assert config.futures_policy.position_mode is PositionMode.ONE_WAY
    assert config.futures_policy.margin_mode is MarginMode.CROSS
    assert config.futures_policy.trading_capital_ratio == Decimal("0.5")
    assert config.futures_policy.collateral_buffer_ratio == Decimal("0.5")
    assert config.futures_policy.maintenance_margin_rate == Decimal("0.005")


def _assert_overview_matches_case(
    window: MainWindow,
    case: _SessionCase,
    *,
    expected_session_id: UUID,
    expected_created_at: datetime,
) -> None:
    assert window.workspace.header_symbol.text() == "BTCUSDT"
    assert window.workspace.header_timeframe.text() == case.timeframe
    assert window.workspace.header_mode.text() == "Paper"
    assert window.workspace.header_market_type.text() == case.market_type.title()
    assert window.workspace.header_preset.text() == "RSI Step Grid v1"
    assert window.workspace.header_runtime.text() == "Configured"
    assert window.workspace.header_freshness.text() == "Market data not started"
    assert window.workspace.header_read_state.text() == "Ready"
    assert window.overview.isVisible()
    assert window.workspace.bot_control_widget.state_value.text() == "Configured"
    assert window.workspace.bot_control_widget.start_button.isVisible()
    assert not window.workspace.bot_control_widget.start_button.isEnabled()
    assert (
        window.workspace.bot_control_widget.supporting_text.text()
        == "Runtime integration is not available yet"
    )
    assert window.overview.state_value.text() == (
        "Configured — Market Data Not Started"
    )
    assert window.overview.session_id_value.text() == str(expected_session_id)
    assert window.overview.market_value.text() == case.market_type.title()
    assert window.overview.symbol_value.text() == "BTCUSDT"
    assert window.overview.timeframe_value.text() == case.timeframe
    assert window.overview.preset_value.text() == "RSI Step Grid v1"
    assert window.overview.available_capital_value.text() == "200000 USDT"
    assert window.overview.max_entries_value.text() == str(case.max_entries)
    assert window.overview.fee_value.text() == f"{case.fee_percent}%"
    assert window.overview.slippage_value.text() == f"{case.slippage_bps} bps"
    assert window.overview.created_at_value.text() == expected_created_at.isoformat()

    if case.market_type == "spot":
        assert case.spot_ratio is not None
        reserve_percent = Decimal("100") - Decimal(case.spot_ratio)
        assert window.overview.spot_ratio_value.text() == f"{case.spot_ratio}%"
        assert window.overview.spot_reserve_ratio_value.text() == (
            f"{_decimal_text(reserve_percent)}%"
        )
        assert window.overview.leverage_value.text() == "—"
        assert window.overview.margin_mode_value.text() == "—"
        assert window.overview.position_mode_value.text() == "—"
        assert window.overview.trading_capital_value.text() == "—"
        assert window.overview.collateral_buffer_value.text() == "—"
        return

    assert case.futures_leverage is not None
    assert window.overview.spot_ratio_value.text() == "—"
    assert window.overview.spot_reserve_ratio_value.text() == "—"
    assert window.overview.leverage_value.text() == f"{case.futures_leverage}x"
    assert window.overview.margin_mode_value.text() == "Cross Margin"
    assert window.overview.position_mode_value.text() == "One-way Mode"
    assert window.overview.trading_capital_value.text() == "50%"
    assert window.overview.collateral_buffer_value.text() == "50%"


def _active_session_count(database: SQLiteDatabase) -> int:
    with database.connect() as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM bot_sessions WHERE ended_at_utc IS NULL"
            ).fetchone()[0]
        )


def _trade_side_effect_counts(database: SQLiteDatabase) -> tuple[int, int]:
    with database.connect() as connection:
        basket_count = connection.execute(
            "SELECT COUNT(*) FROM basket_results"
        ).fetchone()[0]
        fill_count = connection.execute("SELECT COUNT(*) FROM trade_fills").fetchone()[
            0
        ]
    return int(basket_count), int(fill_count)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


class _CommitFailingConnection(sqlite3.Connection):
    def commit(self) -> None:
        raise sqlite3.OperationalError("injected commit failure")


class _CommitFailingDatabase(SQLiteDatabase):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, factory=_CommitFailingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _imported_modules(source_path: Path) -> set[str]:
    source = ast.parse(source_path.read_text(encoding="utf-8"))
    return {
        module for node in ast.walk(source) for module in _modules_from_import(node)
    }


def _forbidden_imports(
    source_paths: tuple[Path, ...],
    *,
    forbidden_prefixes: tuple[str, ...],
    restrict_market_data_to_config: bool,
) -> set[str]:
    imported_modules = {
        module
        for source_path in source_paths
        for module in _imported_modules(source_path)
    }
    forbidden = {
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
    }
    forbidden.update(
        module
        for module in imported_modules
        if any(
            part == "runtime" or part.endswith("_runtime") for part in module.split(".")
        )
    )
    if restrict_market_data_to_config:
        forbidden.update(
            module
            for module in imported_modules
            if module.startswith("tiewtrade.market_data")
            and module != "tiewtrade.market_data.config"
        )
    return forbidden


def _modules_from_import(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module is not None:
        return (node.module,)
    return ()


def _sensitive_terms(source_paths: tuple[Path, ...]) -> set[str]:
    forbidden_fragments = (
        "api_key",
        "apikey",
        "api_secret",
        "apisecret",
        "credential",
        "keyring",
        "private_api",
        "privateapi",
        "secret",
    )
    terms: set[str] = set()
    for source_path in source_paths:
        source = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(source):
            for term in _ast_terms(node):
                normalized = term.casefold()
                if any(fragment in normalized for fragment in forbidden_fragments):
                    terms.add(term)
    return terms


def _ast_terms(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    if isinstance(node, ast.arg):
        return (node.arg,)
    if isinstance(node, ast.alias):
        return (node.asname or node.name,)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    return ()


def _block_network(monkeypatch: MonkeyPatch) -> None:
    def fail_network_attempt(*args: object, **kwargs: object) -> None:
        raise AssertionError("Desktop Session Setup must not attempt network access")

    monkeypatch.setattr(socket, "create_connection", fail_network_attempt)
    monkeypatch.setattr(socket, "getaddrinfo", fail_network_attempt)
    monkeypatch.setattr(socket.socket, "connect", fail_network_attempt)
