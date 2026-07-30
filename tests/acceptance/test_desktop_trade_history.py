import ast
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget
from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

import tiewtrade.desktop_main as desktop_main
import tiewtrade.ui.desktop as ui_desktop
from tests.support.qt_interactions import click, qdate, table_item
from tests.support.trade_history_records import (
    BASKET_ID as SPOT_BASKET_ID,
)
from tests.support.trade_history_records import (
    basket_result,
    trade_fill,
)
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
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.trade_history import (
    SQLiteTradeHistory,
    TradeHistoryUnavailableError,
)
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
)
from tiewtrade.ui.main_window import MainWindow

FUTURES_BASKET_ID = UUID("00000000-0000-0000-0000-000000000202")


def open_trade_history(window: MainWindow) -> None:
    window.workspace.tabs.setCurrentWidget(window.trade_history)


def test_desktop_trade_history_reads_durable_spot_and_futures_records(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(path)
    database.migrate()
    history = SQLiteTradeHistory(database)
    _record_spot_and_futures_history(history)
    window = _composed_window(path, monkeypatch)
    qtbot.addWidget(window)
    window.show()

    open_trade_history(window)

    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 2)
    assert _table_row_text(window.trade_history.basket_table, 0) == (
        "2026-01-03 00:00:00 UTC",
        "Paper",
        "Futures",
        "BTCUSDT",
        "5m",
        "1",
        "200 USDT",
        "30 USDT",
        "0.6 USDT",
        "0.00 USDT",
        "29.4 USDT · Profit",
        "Closed",
    )
    assert (
        table_item(window.trade_history.basket_table, 0, 0).data(
            Qt.ItemDataRole.UserRole
        )
        == FUTURES_BASKET_ID
    )
    assert _table_row_text(window.trade_history.basket_table, 1) == (
        "2026-01-01 00:00:00 UTC",
        "Paper",
        "Spot",
        "BTCUSDT",
        "5m",
        "1",
        "200 USDT",
        "20 USDT",
        "0.42 USDT",
        "0.00 USDT",
        "19.58 USDT · Profit",
        "Closed",
    )
    assert (
        table_item(window.trade_history.basket_table, 1, 0).data(
            Qt.ItemDataRole.UserRole
        )
        == SPOT_BASKET_ID
    )
    assert window.trade_history.total_net_pnl.text() == "48.98 USDT · Profit"
    qtbot.waitUntil(lambda: window.trade_history.fill_table.rowCount() == 2)
    assert _table_rows_text(window.trade_history.fill_table) == (
        (
            "2026-01-03 00:00:00 UTC",
            "Buy",
            "1",
            "100",
            "2",
            "200 USDT",
            "0.2 USDT",
            "0.00 USDT · Break-even",
            "Paper Executor",
        ),
        (
            "2026-01-03 01:00:00 UTC",
            "Sell",
            "—",
            "100",
            "2",
            "200 USDT",
            "0.2 USDT",
            "29.4 USDT · Profit",
            "Paper Executor",
        ),
    )

    window.trade_history.basket_table.selectRow(1)
    qtbot.waitUntil(
        lambda: (
            window.trade_history.fill_table.rowCount() == 2
            and table_item(window.trade_history.fill_table, 0, 0).text()
            == "2026-01-01 00:00:00 UTC"
        )
    )
    assert _table_rows_text(window.trade_history.fill_table) == (
        (
            "2026-01-01 00:00:00 UTC",
            "Buy",
            "1",
            "100",
            "2",
            "200 USDT",
            "0.2 USDT",
            "0.00 USDT · Break-even",
            "Paper Executor",
        ),
        (
            "2026-01-02 00:00:00 UTC",
            "Sell",
            "—",
            "100",
            "2",
            "200 USDT",
            "0.2 USDT",
            "19.58 USDT · Profit",
            "Paper Executor",
        ),
    )


def test_desktop_trade_history_filters_paginates_and_survives_restart(
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(path)
    database.migrate()
    history = SQLiteTradeHistory(database)
    basket_requests: list[tuple[TradeHistoryFilter, PageRequest]] = []
    for index in range(51):
        basket_id = UUID(int=index + 1)
        opened_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
        _record_closed(
            history,
            basket_result(
                basket_id=basket_id,
                opened_at_utc=opened_at,
                closed_at_utc=opened_at + timedelta(hours=1),
                timeframe="15m" if index == 50 else "5m",
                market_type=(MarketType.FUTURES if index == 50 else MarketType.SPOT),
                leverage=3 if index == 50 else None,
                gross_realized_pnl=(Decimal("30") if index == 50 else Decimal("20")),
                trading_fees=(Decimal("0.6") if index == 50 else Decimal("0.42")),
                funding_fee=Decimal("0.00") if index == 50 else Decimal("0"),
                net_realized_pnl=(Decimal("29.4") if index == 50 else Decimal("19.58")),
            ),
        )
    first = _composed_window(
        path,
        monkeypatch,
        basket_requests=basket_requests,
    )
    qtbot.addWidget(first)
    first.show()
    open_trade_history(first)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 50)
    assert table_item(first.trade_history.basket_table, 0, 4).text() == "15m"
    assert first.trade_history.page_label.text() == "Page 1 of 2"
    first_page_opened_at = tuple(
        table_item(first.trade_history.basket_table, row, 0).text() for row in range(50)
    )
    assert first_page_opened_at == tuple(sorted(first_page_opened_at, reverse=True))
    assert first_page_opened_at[0] == "2026-02-20 00:00:00 UTC"
    assert first_page_opened_at[-1] == "2026-01-02 00:00:00 UTC"

    matching_filters = (
        (first.trade_history.symbol, "BTCUSDT"),
        (first.trade_history.timeframe, "15m"),
        (first.trade_history.market, "futures"),
        (first.trade_history.mode, "paper"),
        (first.trade_history.status, "closed"),
    )
    for combo, value in matching_filters:
        combo.setCurrentIndex(combo.findData(value))
    newest_date = (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=50)).date()
    first.trade_history.from_date_enabled.setChecked(True)
    first.trade_history.from_date.setDate(qdate(newest_date))
    first.trade_history.to_date_enabled.setChecked(True)
    first.trade_history.to_date.setDate(qdate(newest_date))
    click(first.trade_history.apply_button)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 1)
    assert table_item(first.trade_history.basket_table, 0, 4).text() == "15m"
    assert table_item(first.trade_history.basket_table, 0, 2).text() == "Futures"
    assert first.trade_history.total_net_pnl.text() == "29.4 USDT · Profit"
    assert basket_requests[-1] == (
        TradeHistoryFilter(
            symbol="BTCUSDT",
            timeframe="15m",
            market_type=MarketType.FUTURES,
            trade_mode=TradeMode.PAPER,
            status=BasketStatus.CLOSED,
            opened_from_utc=datetime(2026, 2, 20, tzinfo=UTC),
            opened_before_utc=datetime(2026, 2, 21, tzinfo=UTC),
        ),
        PageRequest(page=1, page_size=50),
    )

    click(first.trade_history.reset_button)
    for combo, _ in matching_filters:
        assert combo.currentData() is None
    assert not first.trade_history.from_date_enabled.isChecked()
    assert not first.trade_history.from_date.isEnabled()
    assert not first.trade_history.to_date_enabled.isChecked()
    assert not first.trade_history.to_date.isEnabled()
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 50)
    click(first.trade_history.next_button)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 1)
    assert first.trade_history.page_label.text() == "Page 2 of 2"
    assert (
        table_item(first.trade_history.basket_table, 0, 0)
        .text()
        .startswith("2026-01-01")
    )
    first.close()

    restarted = _composed_window(path, monkeypatch)
    qtbot.addWidget(restarted)
    restarted.show()
    open_trade_history(restarted)
    qtbot.waitUntil(lambda: restarted.trade_history.basket_table.rowCount() == 50)
    assert restarted.trade_history.page_label.text() == "Page 1 of 2"
    assert table_item(restarted.trade_history.basket_table, 0, 4).text() == "15m"


def test_trade_history_read_failure_is_fail_closed_and_sanitized(
    qtbot: QtBot,
) -> None:
    basket = basket_result()
    basket_calls = 0

    def succeed_then_fail(
        filters: TradeHistoryFilter,
        page: PageRequest,
    ) -> BasketHistoryPage:
        nonlocal basket_calls
        del filters, page
        basket_calls += 1
        if basket_calls == 1:
            return BasketHistoryPage(
                items=(basket,),
                page=1,
                page_size=50,
                total_items=1,
                net_realized_pnl=basket.net_realized_pnl,
            )
        raise TradeHistoryUnavailableError(
            "SQLite failed at /private/tmp/tiewtrade.sqlite3"
        )

    window = MainWindow(
        create_session=_unused_create,
        load_active=_no_active_session,
        list_baskets=succeed_then_fail,
        list_fills=lambda basket_id: (trade_fill(basket_id=basket_id),),
    )
    qtbot.addWidget(window)
    window.show()
    open_trade_history(window)
    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 1)
    qtbot.waitUntil(lambda: window.trade_history.fill_table.rowCount() == 1)
    assert not window.trade_history.total_net_pnl.isHidden()

    click(window.trade_history.apply_button)
    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "Trade History unavailable"
    )

    assert window.trade_history.basket_table.rowCount() == 0
    assert window.trade_history.fill_table.rowCount() == 0
    assert window.trade_history.total_net_pnl.isHidden()
    assert window.trade_history.total_net_pnl_label.isHidden()
    assert window.trade_history.total_net_pnl.text() == ""
    assert "/private/tmp" not in window.trade_history.basket_state.text()


def test_trade_history_desktop_flow_has_no_forbidden_import_or_network(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    forbidden = (
        "sqlite",
        "strategy",
        "strategies",
        "execution",
        "binance",
        "aiohttp",
    )
    ui_paths = tuple(Path("src/tiewtrade/ui").rglob("*.py"))
    assert ui_paths
    for path in ui_paths:
        tree = ast.parse(path.read_text())
        assert all(
            not any(name in module for name in forbidden)
            for module in _imported_names(tree)
        )

    composition_paths = (
        Path("src/tiewtrade/desktop_main.py"),
        Path("src/tiewtrade/ui/desktop.py"),
        Path("src/tiewtrade/ui/main_window.py"),
    )
    network_dependencies = (
        "binance",
        "aiohttp",
        "httpx",
        "requests",
        "urllib",
        "websocket",
        "socket",
    )
    forbidden_source_references = (
        "tiewtrade.integrations.binance",
        "aiohttp.",
        "httpx.",
        "requests.",
        "urllib.",
        "websocket.",
        "websockets.",
        "socket.",
    )
    assert all(path.is_file() for path in composition_paths)
    for path in composition_paths:
        source = path.read_text()
        imported_names = _imported_names(ast.parse(source))
        assert all(
            not any(name in imported for name in network_dependencies)
            for imported in imported_names
        )
        source_lower = source.casefold()
        assert all(
            reference not in source_lower for reference in forbidden_source_references
        )

    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("network must not run")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    monkeypatch.setattr(socket, "getaddrinfo", fail_network)
    monkeypatch.setattr(socket, "gethostbyname", fail_network)
    window = _composed_window(tmp_path / "tiewtrade.sqlite3", monkeypatch)
    qtbot.addWidget(window)
    window.show()
    assert window.setup.isVisible()
    open_trade_history(window)
    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "No trade history"
    )
    assert window.workspace.tabs.currentWidget() is window.trade_history
    assert window.trade_history.basket_state.text() == "No trade history"


def _record_spot_and_futures_history(history: SQLiteTradeHistory) -> None:
    _record_closed(history, basket_result())
    futures_opened_at = datetime(2026, 1, 3, tzinfo=UTC)
    _record_closed(
        history,
        basket_result(
            basket_id=FUTURES_BASKET_ID,
            session_id=UUID("00000000-0000-0000-0000-000000000201"),
            market_type=MarketType.FUTURES,
            leverage=3,
            opened_at_utc=futures_opened_at,
            closed_at_utc=futures_opened_at + timedelta(hours=1),
            gross_realized_pnl=Decimal("30"),
            trading_fees=Decimal("0.6"),
            funding_fee=Decimal("0.00"),
            net_realized_pnl=Decimal("29.4"),
        ),
    )


def _record_closed(history: SQLiteTradeHistory, closed: BasketResult) -> None:
    assert closed.closed_at_utc is not None
    opened = replace(
        closed,
        closed_at_utc=None,
        gross_realized_pnl=Decimal("0"),
        trading_fees=Decimal("0"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("0"),
        status=BasketStatus.OPEN,
    )
    buy = trade_fill(
        basket_id=opened.basket_id,
        session_id=opened.session_id,
        fill_id=f"{opened.basket_id}-buy",
        order_id=f"{opened.basket_id}-buy-order",
        filled_at_utc=opened.opened_at_utc,
    )
    sell = trade_fill(
        basket_id=closed.basket_id,
        session_id=closed.session_id,
        fill_id=f"{closed.basket_id}-sell",
        order_id=f"{closed.basket_id}-sell-order",
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=closed.closed_at_utc,
        realized_pnl=closed.net_realized_pnl,
    )
    history.record_open_basket(opened, buy)
    history.record_closed_basket(closed, sell)


def _table_rows_text(table: QTableWidget) -> tuple[tuple[str, ...], ...]:
    return tuple(_table_row_text(table, row) for row in range(table.rowCount()))


def _table_row_text(table: QTableWidget, row: int) -> tuple[str, ...]:
    values: list[str] = []
    for column in range(table.columnCount()):
        values.append(table_item(table, row, column).text())
    return tuple(values)


def _imported_names(tree: ast.AST) -> tuple[str, ...]:
    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.append(alias.name.casefold())
                if alias.asname is not None:
                    imported_names.append(alias.asname.casefold())
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").casefold()
            for alias in node.names:
                imported_names.append(f"{module}.{alias.name.casefold()}")
                if alias.asname is not None:
                    imported_names.append(alias.asname.casefold())
    return tuple(imported_names)


def _composed_window(
    path: Path,
    monkeypatch: MonkeyPatch,
    *,
    basket_requests: list[tuple[TradeHistoryFilter, PageRequest]] | None = None,
) -> MainWindow:
    assert QApplication.instance() is not None
    captured_window: MainWindow | None = None

    class NonBlockingApplication:
        @classmethod
        def instance(cls) -> "NonBlockingApplication":
            return cls()

        def exec(self) -> int:
            return 0

    class CapturedMainWindow(MainWindow):
        def __init__(self, **dependencies: object) -> None:
            nonlocal captured_window
            super().__init__(**dependencies)  # type: ignore[arg-type]
            captured_window = self

    if basket_requests is not None:
        original_list_baskets = SQLiteTradeHistory.list_baskets

        def capture_basket_request(
            history: SQLiteTradeHistory,
            filters: TradeHistoryFilter,
            page: PageRequest,
        ) -> BasketHistoryPage:
            basket_requests.append((filters, page))
            return original_list_baskets(history, filters, page)

        monkeypatch.setattr(
            SQLiteTradeHistory,
            "list_baskets",
            capture_basket_request,
        )

    monkeypatch.setattr(ui_desktop, "QApplication", NonBlockingApplication)
    monkeypatch.setattr(ui_desktop, "MainWindow", CapturedMainWindow)
    assert desktop_main.run_desktop(path) == 0
    assert captured_window is not None
    return captured_window


def _no_active_session() -> ConfiguredPaperSession | None:
    return None


def _unused_create(
    values: PaperSessionSetupValues,
) -> PaperSessionCreateOutcome:
    del values
    pytest.fail("create must not run")
