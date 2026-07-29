import socket
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
from tests.support.paper_trade_history_acceptance import (
    run_closed_futures,
    run_closed_spot,
)
from tiewtrade.application.trade_history import PageRequest, TradeHistoryFilter
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.trade_history import (
    BasketStatus,
    FillSide,
    FillSource,
)
from tiewtrade.ui.main_window import MainWindow


def test_paper_execution_history_survives_restart_and_reaches_desktop(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
) -> None:
    path = tmp_path / "paper-trade-history.sqlite3"
    database = SQLiteDatabase(path)
    database.migrate()
    history = SQLiteTradeHistory(database)
    _block_network(monkeypatch)

    spot_basket_id = run_closed_spot(history)
    futures_basket_id = run_closed_futures(history)
    before_restart = history.list_baskets(TradeHistoryFilter(), PageRequest())
    before_fills = {
        basket.basket_id: history.list_fills(basket.basket_id)
        for basket in before_restart.items
    }

    assert len(before_restart.items) == 2
    assert before_restart.net_realized_pnl == Decimal("2273.69035202")
    futures, spot = before_restart.items
    assert futures.basket_id == futures_basket_id
    assert futures.status is BasketStatus.CLOSED
    assert futures.net_realized_pnl == Decimal("2259.8497298")
    assert futures.leverage == 3
    assert futures.funding_fee == Decimal("0.00")
    assert spot.basket_id == spot_basket_id
    assert spot.status is BasketStatus.CLOSED
    assert spot.net_realized_pnl == Decimal("13.84062222")
    for fills in before_fills.values():
        assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
        assert all(fill.source is FillSource.PAPER_EXECUTOR for fill in fills)

    reopened_database = SQLiteDatabase(path)
    reopened_database.migrate()
    reopened = SQLiteTradeHistory(reopened_database)
    after_restart = reopened.list_baskets(TradeHistoryFilter(), PageRequest())
    after_fills = {
        basket.basket_id: reopened.list_fills(basket.basket_id)
        for basket in after_restart.items
    }
    assert after_restart == before_restart
    assert after_fills == before_fills

    window = _composed_window(path, monkeypatch)
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 2)
    assert window.trade_history.total_net_pnl.text() == "2273.69035202 USDT · Profit"
    assert _table_row_text(window.trade_history.basket_table, 0) == (
        "2026-01-01 02:05:00 UTC",
        "Paper",
        "Futures",
        "BTCUSDT",
        "5m",
        "1",
        "29999.9492 USDT",
        "2322.1718 USDT",
        "62.3220702 USDT",
        "0.00 USDT",
        "2259.8497298 USDT · Profit",
        "Closed",
    )
    assert _basket_id(window.trade_history.basket_table, 0) == futures_basket_id
    assert _basket_id(window.trade_history.basket_table, 1) == spot_basket_id
    qtbot.waitUntil(
        lambda: (
            _table_rows_text(window.trade_history.fill_table)
            == (
                (
                    "2026-01-01 02:05:00 UTC",
                    "Buy",
                    "1",
                    "95.6",
                    "313.807",
                    "29999.9492 USDT",
                    "29.9999492 USDT",
                    "0.00 USDT · Break-even",
                    "Paper Executor",
                ),
                (
                    "2026-01-01 02:45:00 UTC",
                    "Sell",
                    "—",
                    "103.0",
                    "313.807",
                    "32322.1210 USDT",
                    "32.3221210 USDT",
                    "2259.8497298 USDT · Profit",
                    "Paper Executor",
                ),
            )
        )
    )

    window.trade_history.basket_table.selectRow(1)
    qtbot.waitUntil(
        lambda: (
            _table_rows_text(window.trade_history.fill_table)
            == (
                (
                    "2026-01-01 02:05:00 UTC",
                    "Buy",
                    "1",
                    "95.02",
                    "1.578",
                    "149.94156 USDT",
                    "0.14994156 USDT",
                    "0.00 USDT · Break-even",
                    "Paper Executor",
                ),
                (
                    "2026-01-01 02:50:00 UTC",
                    "Sell",
                    "—",
                    "103.99",
                    "1.578",
                    "164.09622 USDT",
                    "0.16409622 USDT",
                    "13.84062222 USDT · Profit",
                    "Paper Executor",
                ),
            )
        )
    )


def _block_network(monkeypatch: MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("network must not run")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    monkeypatch.setattr(socket, "getaddrinfo", fail_network)
    monkeypatch.setattr(socket, "gethostbyname", fail_network)


def _composed_window(path: Path, monkeypatch: MonkeyPatch) -> MainWindow:
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

    monkeypatch.setattr(ui_desktop, "QApplication", NonBlockingApplication)
    monkeypatch.setattr(ui_desktop, "MainWindow", CapturedMainWindow)
    assert desktop_main.run_desktop(path) == 0
    assert captured_window is not None
    return captured_window


def _basket_id(table: QTableWidget, row: int) -> UUID:
    item = table.item(row, 0)
    assert item is not None
    basket_id = item.data(Qt.ItemDataRole.UserRole)
    assert isinstance(basket_id, UUID)
    return basket_id


def _table_rows_text(table: QTableWidget) -> tuple[tuple[str, ...], ...]:
    return tuple(_table_row_text(table, row) for row in range(table.rowCount()))


def _table_row_text(table: QTableWidget, row: int) -> tuple[str, ...]:
    values: list[str] = []
    for column in range(table.columnCount()):
        item = table.item(row, column)
        assert item is not None
        values.append(item.text())
    return tuple(values)
