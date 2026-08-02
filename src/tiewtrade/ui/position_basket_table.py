from decimal import Decimal

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
    BasketSnapshot,
    PositionBasketTabSnapshot,
    WorkspaceTabState,
)


class PositionBasketTable(QWidget):
    HEADERS = (
        "Symbol",
        "Market Type",
        "Entry Count",
        "Total Quantity",
        "Average Entry Price",
        "Current Price",
        "Basket Take Profit",
        "Unrealized PnL",
        "Liquidation Price",
        "Basket Lifecycle",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("positionBasketTable")
        self.setAccessibleName("Position / Basket")

        self.table = self._table()
        self.state_label = QLabel("No open Position or Basket")
        self.state_label.setObjectName("positionBasketState")
        self.state_label.setAccessibleName("Position / Basket status")
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
        if not isinstance(value, PositionBasketTabSnapshot):
            return
        self._show_basket(value.basket)
        self._show_state(value)

    def _show_basket(self, basket: BasketSnapshot | None) -> None:
        blocker = QSignalBlocker(self.table)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.setRowCount(0 if basket is None else 1)
        if basket is not None:
            for column_index, text in enumerate(self._basket_row(basket)):
                self.table.setItem(0, column_index, self._table_item(text))
        del blocker

    def _show_state(self, snapshot: PositionBasketTabSnapshot) -> None:
        text = self._state_text(snapshot)
        self.state_label.setText(text)
        self.state_label.setVisible(bool(text))

    @staticmethod
    def _basket_row(basket: BasketSnapshot) -> tuple[str, ...]:
        return (
            basket.symbol,
            _enum_text(basket.market_type),
            str(basket.entry_count),
            format(basket.total_quantity, "f"),
            format(basket.average_entry_price, "f"),
            format(basket.current_price, "f"),
            format(basket.take_profit_price, "f"),
            _pnl_text(basket.unrealized_pnl),
            _liquidation_text(basket),
            _enum_text(basket.lifecycle),
        )

    @staticmethod
    def _state_text(snapshot: PositionBasketTabSnapshot) -> str:
        if snapshot.state is WorkspaceTabState.LOADING:
            return "Loading Position / Basket…"
        if snapshot.state is WorkspaceTabState.EMPTY:
            return "No open Position or Basket"
        if snapshot.state is WorkspaceTabState.ERROR:
            return snapshot.message or ""
        if snapshot.state is WorkspaceTabState.STALE:
            data_as_of_utc = snapshot.data_as_of_utc
            if data_as_of_utc is None:
                return "Stale Position / Basket data"
            return (
                "Stale Position / Basket data as of "
                f"{data_as_of_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        return ""

    def _table(self) -> QTableWidget:
        table = QTableWidget(0, len(self.HEADERS))
        table.setObjectName("positionBasketGrid")
        table.setAccessibleName("Position / Basket")
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


def _pnl_text(value: Decimal) -> str:
    label = "Break-even"
    if value > 0:
        label = "Profit"
    elif value < 0:
        label = "Loss"
    return f"{format(value, 'f')} USDT · {label}"


def _liquidation_text(basket: BasketSnapshot) -> str:
    if basket.market_type.casefold() == "spot" or basket.liquidation_price is None:
        return "—"
    return format(basket.liquidation_price, "f")
