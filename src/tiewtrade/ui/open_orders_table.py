from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.trading_workspace import (
    OpenOrderSnapshot,
    OpenOrdersTabSnapshot,
    WorkspaceTabState,
)


class OpenOrdersTable(QWidget):
    HEADERS = (
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("openOrdersTable")
        self.setAccessibleName("Open Orders")

        self.table = self._table()
        self.state_label = QLabel("No open orders")
        self.state_label.setObjectName("openOrdersState")
        self.state_label.setAccessibleName("Open Orders status")
        self.state_label.setProperty("stateMessage", True)
        self.state_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.state_label)
        layout.addWidget(self.table, 1)

    @property
    def headers(self) -> tuple[str, ...]:
        return self.HEADERS

    def show_snapshot(self, value: object) -> None:
        if not isinstance(value, OpenOrdersTabSnapshot):
            return
        self._show_orders(value.orders)
        self._show_state(value)

    def _show_orders(self, orders: tuple[OpenOrderSnapshot, ...]) -> None:
        blocker = QSignalBlocker(self.table)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.setRowCount(len(orders))
        for row_index, order in enumerate(orders):
            for column_index, text in enumerate(self._order_row(order)):
                self.table.setItem(row_index, column_index, self._table_item(text))
        del blocker

    def _show_state(self, snapshot: OpenOrdersTabSnapshot) -> None:
        text = self._state_text(snapshot)
        self.state_label.setText(text)
        self.state_label.setVisible(bool(text))

    @staticmethod
    def _order_row(order: OpenOrderSnapshot) -> tuple[str, ...]:
        return (
            order.order_id,
            order.created_at_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            order.symbol,
            _enum_text(order.side),
            _enum_text(order.order_type),
            "—" if order.price is None else format(order.price, "f"),
            format(order.quantity, "f"),
            format(order.filled_quantity, "f"),
            _enum_text(order.status),
        )

    @staticmethod
    def _state_text(snapshot: OpenOrdersTabSnapshot) -> str:
        if snapshot.state is WorkspaceTabState.LOADING:
            return "Loading Open Orders…"
        if snapshot.state is WorkspaceTabState.EMPTY:
            return "No open orders"
        if snapshot.state is WorkspaceTabState.ERROR:
            return snapshot.message or ""
        if snapshot.state is WorkspaceTabState.STALE:
            data_as_of_utc = snapshot.data_as_of_utc
            if data_as_of_utc is None:
                return "Stale Open Orders data"
            return (
                "Stale Open Orders data as of "
                f"{data_as_of_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        return ""

    def _table(self) -> QTableWidget:
        table = QTableWidget(0, len(self.HEADERS))
        table.setObjectName("openOrdersGrid")
        table.setAccessibleName("Open Orders")
        table.setHorizontalHeaderLabels(list(self.HEADERS))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _table_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item


def _enum_text(value: str) -> str:
    return value.replace("_", " ").title()
