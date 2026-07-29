import ast
import inspect
import threading
from copy import copy
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from PySide6.QtCore import Qt, QThreadPool
from pytestqt.qtbot import QtBot

import tiewtrade.ui.main_window as main_window_module
from tests.support.paper_session_setup import (
    configured_futures_session,
    configured_spot_session,
)
from tests.support.trade_history_records import basket_result, trade_fill
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.application.trade_history import (
    BasketHistoryPage,
    PageRequest,
    TradeHistoryFilter,
)
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.trade_history import TradeFill
from tiewtrade.ui.main_window import MainWindow
from tiewtrade.ui.session_overview import SessionOverviewWidget


def no_active_session() -> ConfiguredPaperSession | None:
    return None


def unused_create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
    pytest.fail("create must not run")


def test_navigation_opens_trade_history_without_active_session(qtbot: QtBot) -> None:
    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Trade History")
    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "No trade history"
    )
    assert window.trade_history.isVisible()


def test_empty_trade_history_preserves_exact_query_summary_and_page_state(
    qtbot: QtBot,
) -> None:
    exact_empty_page = BasketHistoryPage(
        items=(),
        page=1,
        page_size=50,
        total_items=0,
        net_realized_pnl=Decimal("0.000000000000000001"),
    )
    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=lambda filters, request: exact_empty_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "No trade history"
    )
    assert (
        window.trade_history.total_net_pnl.text()
        == "0.000000000000000001 USDT · Profit"
    )
    assert window.trade_history.total_items.text() == "0 total Baskets"
    assert window.trade_history.page_label.text() == "Page 1 of 1"


def test_trade_history_remains_available_when_session_load_fails(
    qtbot: QtBot,
) -> None:
    def fail_load() -> ConfiguredPaperSession | None:
        raise PaperSessionUnavailableError(
            "SQLite failed at /private/tmp/session.sqlite3"
        )

    window = MainWindow(
        create_session=unused_create,
        load_active=fail_load,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.unavailable_panel.isVisible)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Trade History")
    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "No trade history"
    )


def test_navigation_starts_history_query_only_once(qtbot: QtBot) -> None:
    calls = 0

    def count_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        nonlocal calls
        calls += 1
        return empty_basket_page(filters, request)

    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=count_baskets,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: calls == 1)
    qtbot.mouseClick(window.session_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    assert calls == 1


def test_session_load_finishing_does_not_navigate_away_from_history(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    existing = configured_spot_session()
    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(2)

    def delayed_load() -> ConfiguredPaperSession | None:
        started.set()
        if not release.wait(timeout=1):
            raise TimeoutError("test did not release worker")
        return existing

    window = MainWindow(
        create_session=unused_create,
        load_active=delayed_load,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        thread_pool=thread_pool,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(started.is_set)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    release.set()

    qtbot.waitUntil(
        lambda: (
            window.overview.session_id_value.text() == str(existing.config.session_id)
        )
    )
    assert window.current_page_name == "Trade History"
    assert window.trade_history.isVisible()

    qtbot.mouseClick(window.session_button, Qt.MouseButton.LeftButton)
    assert window.current_page_name == "Session Overview"
    assert window.overview.isVisible()


def test_trade_history_basket_and_fill_retries_are_wired_separately(
    qtbot: QtBot,
) -> None:
    basket = basket_result()
    fill = trade_fill()
    basket_calls = 0
    fill_calls = 0

    def fail_baskets_once(
        filters: TradeHistoryFilter,
        request: PageRequest,
    ) -> BasketHistoryPage:
        nonlocal basket_calls
        basket_calls += 1
        if basket_calls == 1:
            raise RuntimeError("private basket failure")
        return BasketHistoryPage(
            items=(basket,),
            page=request.page,
            page_size=request.page_size,
            total_items=1,
            net_realized_pnl=Decimal("0"),
        )

    def fail_fills_once(basket_id: UUID) -> tuple[TradeFill, ...]:
        nonlocal fill_calls
        fill_calls += 1
        if fill_calls == 1:
            raise RuntimeError("private fill failure")
        assert basket_id == basket.basket_id
        return (fill,)

    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=fail_baskets_once,
        list_fills=fail_fills_once,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "Trade History unavailable"
    )

    qtbot.mouseClick(
        window.trade_history.retry_baskets_button,
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(
        lambda: window.trade_history.fill_state.text() == "Trade Fills unavailable"
    )

    qtbot.mouseClick(
        window.trade_history.retry_fills_button,
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(lambda: window.trade_history.fill_table.rowCount() == 1)
    assert basket_calls == 2
    assert fill_calls == 2


def test_trade_history_filter_reset_page_and_selection_requests_are_wired(
    qtbot: QtBot,
) -> None:
    first = basket_result()
    second = basket_result(basket_id=UUID("00000000-0000-0000-0000-000000000202"))
    basket_calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    fill_calls: list[UUID] = []

    def list_baskets(
        filters: TradeHistoryFilter,
        request: PageRequest,
    ) -> BasketHistoryPage:
        basket_calls.append((filters, request))
        return BasketHistoryPage(
            items=(first, second) if request.page == 1 else (second,),
            page=request.page,
            page_size=request.page_size,
            total_items=51,
            net_realized_pnl=Decimal("0"),
        )

    def list_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        fill_calls.append(basket_id)
        return ()

    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=list_baskets,
        list_fills=list_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 2)
    qtbot.waitUntil(lambda: fill_calls == [first.basket_id])

    window.trade_history.basket_table.selectRow(1)
    qtbot.waitUntil(lambda: fill_calls[-1] == second.basket_id)
    window.trade_history.symbol.setCurrentIndex(
        window.trade_history.symbol.findData("BTCUSDT")
    )
    qtbot.mouseClick(window.trade_history.apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(basket_calls) == 2)
    assert basket_calls[-1] == (
        TradeHistoryFilter(symbol="BTCUSDT"),
        PageRequest(page=1, page_size=50),
    )

    qtbot.mouseClick(window.trade_history.reset_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(basket_calls) == 3)
    assert basket_calls[-1] == (
        TradeHistoryFilter(),
        PageRequest(page=1, page_size=50),
    )

    qtbot.waitUntil(window.trade_history.next_button.isEnabled)
    qtbot.mouseClick(window.trade_history.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(basket_calls) == 4)
    assert basket_calls[-1] == (
        TradeHistoryFilter(),
        PageRequest(page=2, page_size=50),
    )


def test_trade_history_filter_validation_is_wired_without_starting_query(
    qtbot: QtBot,
) -> None:
    basket_calls = 0

    def count_baskets(
        filters: TradeHistoryFilter,
        request: PageRequest,
    ) -> BasketHistoryPage:
        nonlocal basket_calls
        basket_calls += 1
        return empty_basket_page(filters, request)

    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=count_baskets,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: basket_calls == 1)
    qtbot.waitUntil(window.trade_history.apply_button.isEnabled)
    window.trade_history.from_date_enabled.setChecked(True)
    window.trade_history.to_date_enabled.setChecked(True)
    window.trade_history.from_date.setDate(date(2026, 1, 2))
    window.trade_history.to_date.setDate(date(2026, 1, 1))

    qtbot.mouseClick(window.trade_history.apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(window.trade_history.filter_error.isVisible)
    assert (
        window.trade_history.filter_error.text()
        == "From Date must not be after To Date"
    )
    assert basket_calls == 1


def test_main_window_delegates_session_task_lifecycle_to_workflow() -> None:
    source = inspect.getsource(main_window_module)
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "SessionWorkflow" in imported_names
    assert "SessionTask" not in imported_names
    assert "_active_create_task" not in source
    assert "_active_load_task" not in source
    assert "_callback_generation" not in source


def test_created_spot_session_replaces_form_with_durable_overview(
    qtbot: QtBot,
) -> None:
    created = configured_spot_session()
    window = MainWindow(
        create_session=lambda values: PaperSessionCreateOutcome(created, True),
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)
    window.setup.available_capital.setText("200000")

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")
    assert window.overview.state_value.text() == (
        "Configured — Market Data Not Started"
    )
    assert window.overview.market_value.text() == "Spot"
    assert window.overview.session_id_value.text() == str(created.config.session_id)
    assert window.overview.timeframe_value.text() == "5m"
    assert window.overview.available_capital_value.text() == "200000 USDT"
    assert window.overview.spot_reserve_ratio_value.text() == "20%"


def test_futures_overview_shows_immutable_policy(qtbot: QtBot) -> None:
    session = configured_futures_session(leverage=3)
    overview = SessionOverviewWidget()
    qtbot.addWidget(overview)

    overview.show_session(session)

    assert overview.market_value.text() == "Futures"
    assert overview.leverage_value.text() == "3x"
    assert overview.margin_mode_value.text() == "Cross Margin"
    assert overview.position_mode_value.text() == "One-way Mode"
    assert overview.trading_capital_value.text() == "50%"
    assert overview.collateral_buffer_value.text() == "50%"


def test_futures_overview_marks_missing_required_policy_unavailable(
    qtbot: QtBot,
) -> None:
    session = _session_with_policy_changes(
        configured_futures_session(), futures_policy=None
    )
    overview = SessionOverviewWidget()
    qtbot.addWidget(overview)

    overview.show_session(session)

    assert overview.leverage_value.text() == "Unavailable"
    assert overview.margin_mode_value.text() == "Unavailable"
    assert overview.position_mode_value.text() == "Unavailable"
    assert overview.trading_capital_value.text() == "Unavailable"
    assert overview.collateral_buffer_value.text() == "Unavailable"


def test_futures_overview_marks_mixed_spot_policy_unavailable(
    qtbot: QtBot,
) -> None:
    session = _session_with_policy_changes(
        configured_futures_session(),
        spot_policy=SpotTradingPolicy(Decimal("0.8")),
    )
    overview = SessionOverviewWidget()
    qtbot.addWidget(overview)

    overview.show_session(session)

    assert overview.leverage_value.text() == "Unavailable"
    assert overview.margin_mode_value.text() == "Unavailable"
    assert overview.position_mode_value.text() == "Unavailable"
    assert overview.trading_capital_value.text() == "Unavailable"
    assert overview.collateral_buffer_value.text() == "Unavailable"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"spot_policy": None}, id="missing-spot-policy"),
        pytest.param(
            {"futures_policy": FuturesTradingPolicy.v1(leverage=3)},
            id="mixed-futures-policy",
        ),
    ],
)
def test_spot_overview_marks_missing_or_mixed_policy_unavailable(
    qtbot: QtBot,
    changes: dict[str, object],
) -> None:
    session = _session_with_policy_changes(configured_spot_session(), **changes)
    overview = SessionOverviewWidget()
    qtbot.addWidget(overview)

    overview.show_session(session)

    assert overview.spot_ratio_value.text() == "Unavailable"
    assert overview.spot_reserve_ratio_value.text() == "Unavailable"


def test_repeated_submit_while_worker_is_running_calls_create_once(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    created = configured_spot_session()
    calls: list[PaperSessionSetupValues] = []

    def create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        calls.append(values)
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return PaperSessionCreateOutcome(created, True)

    window = MainWindow(
        create_session=create,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)
    window.setup.available_capital.setText("200000")

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(started.is_set)
    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    assert len(calls) == 1
    release.set()
    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")


def test_validation_failure_restores_form_and_shows_field_error(qtbot: QtBot) -> None:
    def reject(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        raise PaperSessionValidationError(
            "available_capital", "Available Capital must be positive"
        )

    window = MainWindow(
        create_session=reject,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)
    window.setup.available_capital.setText("0")

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: (
            window.setup.available_capital_error.text()
            == "Available Capital must be positive"
        )
    )
    assert window.current_page_name == "Session Setup"
    assert window.setup.create_button.isEnabled() is True
    assert window.setup.available_capital.text() == "0"


def test_persistence_failure_shows_sanitized_unavailable_state_and_allows_retry(
    qtbot: QtBot,
) -> None:
    def unavailable(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        raise PaperSessionUnavailableError(
            "sqlite3.OperationalError: unable to open /private/tmp/tiewtrade.sqlite3"
        )

    window = MainWindow(
        create_session=unavailable,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(window.unavailable_panel.isVisible)
    assert window.unavailable_message.text() == "Session storage is unavailable"
    assert window.current_page_name == "Unavailable"
    assert "/private/tmp" not in window.unavailable_message.text()
    qtbot.waitUntil(window.unavailable_retry_button.isEnabled)
    qtbot.mouseClick(window.unavailable_retry_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.current_page_name == "Session Setup")
    assert window.setup.create_button.isEnabled() is True


def test_unknown_create_failure_shows_sanitized_unavailable_state(qtbot: QtBot) -> None:
    def fail_create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        raise RuntimeError("sqlite error at /private/tmp/tiewtrade.sqlite3")

    window = MainWindow(
        create_session=fail_create,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(window.unavailable_panel.isVisible)
    assert window.unavailable_message.text() == "Paper Session could not be created"
    assert "/private/tmp" not in window.unavailable_message.text()


def test_existing_create_outcome_opens_existing_session_overview(qtbot: QtBot) -> None:
    existing = configured_spot_session()
    window = MainWindow(
        create_session=lambda values: PaperSessionCreateOutcome(existing, False),
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)
    window.setup.available_capital.setText("200000")

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")
    assert window.overview.session_id_value.text() == str(existing.config.session_id)


def test_existing_active_session_opens_overview_without_create_form(
    qtbot: QtBot,
) -> None:
    existing = configured_spot_session()
    window = MainWindow(
        create_session=lambda values: pytest.fail("must not create"),
        load_active=lambda: existing,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")

    assert window.overview.session_id_value.text() == str(existing.config.session_id)


def test_sqlite_failure_shows_unavailable_without_fake_overview(qtbot: QtBot) -> None:
    def fail_load() -> ConfiguredPaperSession | None:
        raise PaperSessionUnavailableError(
            "Active Paper Session read failed at /private/tmp/tiewtrade.sqlite3"
        )

    window = MainWindow(
        create_session=unused_create,
        load_active=fail_load,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(window.unavailable_panel.isVisible)

    assert window.current_page_name == "Unavailable"
    assert window.unavailable_message.text() == "Session storage is unavailable"
    assert "/private/tmp" not in window.unavailable_message.text()
    assert not window.overview.isVisible()


def test_corrupt_sqlite_session_stays_unavailable_without_persisted_text(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    store.create(configured_spot_session())
    unsupported_symbol = "PRIVATE-PERSISTED-SYMBOL"
    with database.connect() as connection:
        connection.execute(
            "UPDATE bot_sessions SET symbol = ?",
            (unsupported_symbol,),
        )
    window = MainWindow(
        create_session=unused_create,
        load_active=store.get_active,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(window.unavailable_panel.isVisible)

    assert window.current_page_name == "Unavailable"
    assert window.unavailable_message.text() == "Session storage is unavailable"
    assert unsupported_symbol not in window.unavailable_message.text()
    assert not window.overview.isVisible()


def test_retry_after_startup_load_failure_reloads_existing_session(
    qtbot: QtBot,
) -> None:
    existing = configured_spot_session()
    load_calls = 0

    def fail_then_load_existing() -> ConfiguredPaperSession | None:
        nonlocal load_calls
        load_calls += 1
        if load_calls == 1:
            raise PaperSessionUnavailableError(
                "sqlite3.OperationalError: unable to open "
                "/private/tmp/tiewtrade.sqlite3"
            )
        return existing

    window = MainWindow(
        create_session=unused_create,
        load_active=fail_then_load_existing,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(window.unavailable_panel.isVisible)
    qtbot.waitUntil(window.unavailable_retry_button.isEnabled)
    assert load_calls == 1
    assert not window.setup.isVisible()
    assert not window.setup.create_button.isEnabled()

    qtbot.mouseClick(window.unavailable_retry_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")
    assert load_calls == 2
    assert window.overview.session_id_value.text() == str(existing.config.session_id)


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        pytest.param(
            PaperSessionValidationError("available_capital", "invalid persisted value"),
            "Paper Session could not be loaded",
            id="validation",
        ),
        pytest.param(
            PaperSessionUnavailableError(
                "SQLite failed at /private/tmp/tiewtrade.sqlite3"
            ),
            "Session storage is unavailable",
            id="storage",
        ),
        pytest.param(
            RuntimeError("unexpected SQLite failure at /private/tmp/tiewtrade.sqlite3"),
            "Paper Session could not be loaded",
            id="unknown",
        ),
    ],
)
def test_load_failures_stay_fail_closed_with_sanitized_copy(
    qtbot: QtBot,
    error: Exception,
    expected_message: str,
) -> None:
    def fail_load() -> ConfiguredPaperSession | None:
        raise error

    window = MainWindow(
        create_session=unused_create,
        load_active=fail_load,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(window.unavailable_panel.isVisible)

    assert window.current_page_name == "Unavailable"
    assert window.unavailable_message.text() == expected_message
    assert not window.setup.isVisible()
    assert window.setup.available_capital_error.text() == ""
    assert "private/tmp" not in window.unavailable_message.text()


def test_closing_window_ignores_late_worker_result_and_releases_task(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    existing = configured_spot_session()
    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)

    def delayed_load() -> ConfiguredPaperSession | None:
        started.set()
        release.wait(timeout=1)
        return existing

    window = MainWindow(
        create_session=unused_create,
        load_active=delayed_load,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        thread_pool=thread_pool,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(started.is_set)
    page_before_close = window.current_page_name
    overview_before_close = window.overview.session_id_value.text()
    unavailable_before_close = window.unavailable_message.text()

    window.close()
    release.set()
    assert thread_pool.waitForDone(1_000)
    qtbot.wait(20)

    assert not window.isVisible()
    assert window.current_page_name == page_before_close
    assert window.overview.session_id_value.text() == overview_before_close
    assert window.unavailable_message.text() == unavailable_before_close
    assert not window.overview.isVisible()


def test_closing_window_waits_for_workers_after_closing_workflows(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class RecordingThreadPool(QThreadPool):
        def waitForDone(self, msecs: int = -1) -> bool:
            events.append(f"pool:{msecs}")
            return super().waitForDone(msecs)

    thread_pool = RecordingThreadPool()
    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        thread_pool=thread_pool,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    session_close = window._workflow.close
    history_close = window._history_workflow.close

    def close_session_workflow() -> None:
        events.append("session")
        session_close()

    def close_history_workflow() -> None:
        events.append("history")
        history_close()

    monkeypatch.setattr(window._workflow, "close", close_session_workflow)
    monkeypatch.setattr(window._history_workflow, "close", close_history_workflow)

    window.close()

    assert events == ["session", "history", "pool:5000"]


def test_closing_window_ignores_late_trade_history_result(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    thread_pool = QThreadPool()
    thread_pool.setMaxThreadCount(1)

    def delayed_baskets(
        filters: TradeHistoryFilter,
        request: PageRequest,
    ) -> BasketHistoryPage:
        started.set()
        if not release.wait(timeout=1):
            raise TimeoutError("test did not release worker")
        return empty_basket_page(filters, request)

    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=delayed_baskets,
        list_fills=empty_fills,
        thread_pool=thread_pool,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(started.is_set)
    basket_state_before_close = window.trade_history.basket_state.text()

    window.close()
    release.set()
    assert thread_pool.waitForDone(1_000)
    qtbot.wait(20)

    assert not window.isVisible()
    assert window.trade_history.basket_state.text() == basket_state_before_close


def test_main_window_starts_on_setup_without_placeholder_navigation(
    qtbot: QtBot,
) -> None:
    def operation(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        return PaperSessionCreateOutcome(configured_spot_session(), True)

    window = MainWindow(
        create_session=operation,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)

    assert window.current_page_name == "Session Setup"
    assert window.navigation_items == ("Session", "Trade History")


def _session_with_policy_changes(
    session: ConfiguredPaperSession,
    **changes: object,
) -> ConfiguredPaperSession:
    inconsistent_config = copy(session.config)
    for field, value in changes.items():
        object.__setattr__(inconsistent_config, field, value)
    return replace(session, config=inconsistent_config)
