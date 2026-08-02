from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget
from pytestqt.qtbot import QtBot

from tiewtrade.application.trading_workspace import (
    OpenOrderSnapshot,
    empty_open_orders_tab,
    failed_open_orders_tab,
    loading_open_orders_tab,
    ready_open_orders_tab,
    stale_open_orders_tab,
)
from tiewtrade.ui.open_orders_table import OpenOrdersTable

OBSERVED_AT = datetime(2026, 8, 2, 1, 2, 4, tzinfo=UTC)


def _order() -> OpenOrderSnapshot:
    return OpenOrderSnapshot(
        order_id="order-1",
        created_at_utc=datetime(2026, 8, 2, 1, 2, 3, tzinfo=UTC),
        symbol="BTCUSDT",
        side="buy",
        order_type="limit",
        price=Decimal("66321.1200"),
        quantity=Decimal("0.00300000"),
        filled_quantity=Decimal("0.00100000"),
        status="partially_filled",
    )


def _row(table: QTableWidget, row: int) -> tuple[str, ...]:
    values: list[str] = []
    for column in range(table.columnCount()):
        item = table.item(row, column)
        assert item is not None
        values.append(item.text())
    return tuple(values)


def test_open_orders_table_renders_all_authoritative_columns(qtbot: QtBot) -> None:
    widget = OpenOrdersTable()
    qtbot.addWidget(widget)

    widget.show_snapshot(
        ready_open_orders_tab((_order(),), observed_at_utc=OBSERVED_AT)
    )

    assert widget.headers == (
        "Order ID",
        "Created Time",
        "Symbol",
        "Side",
        "Type",
        "Price",
        "Quantity",
        "Filled Quantity",
        "Status",
    )
    assert _row(widget.table, 0) == (
        "order-1",
        "2026-08-02 01:02:03 UTC",
        "BTCUSDT",
        "Buy",
        "Limit",
        "66321.1200",
        "0.00300000",
        "0.00100000",
        "Partially Filled",
    )
    assert widget.state_label.text() == ""
    assert widget.state_label.accessibleName() == "Open Orders status"


def test_open_orders_states_preserve_or_clear_rows_as_authoritative(
    qtbot: QtBot,
) -> None:
    widget = OpenOrdersTable()
    qtbot.addWidget(widget)
    ready = ready_open_orders_tab((_order(),), observed_at_utc=OBSERVED_AT)

    for snapshot, expected_state in (
        (loading_open_orders_tab(ready), "Loading Open Orders…"),
        (
            failed_open_orders_tab(ready, "Open orders are unavailable"),
            "Open orders are unavailable",
        ),
        (
            stale_open_orders_tab(ready),
            "Stale Open Orders data as of 2026-08-02 01:02:04 UTC",
        ),
    ):
        widget.show_snapshot(snapshot)
        assert widget.table.rowCount() == 1
        assert widget.state_label.text() == expected_state
        assert not widget.state_label.isHidden()

    widget.show_snapshot(empty_open_orders_tab())

    assert widget.table.rowCount() == 0
    assert widget.state_label.text() == "No open orders"


def test_open_orders_table_is_read_only_and_ignores_wrong_snapshot_type(
    qtbot: QtBot,
) -> None:
    widget = OpenOrdersTable()
    qtbot.addWidget(widget)
    widget.show_snapshot(
        ready_open_orders_tab((_order(),), observed_at_utc=OBSERVED_AT)
    )

    widget.show_snapshot(object())

    assert widget.table.rowCount() == 1
    assert widget.table.accessibleName() == "Open Orders"
    assert widget.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert (
        widget.table.selectionBehavior()
        == QAbstractItemView.SelectionBehavior.SelectRows
    )
    assert (
        widget.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
