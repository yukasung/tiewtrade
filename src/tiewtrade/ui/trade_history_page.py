from datetime import date
from uuid import UUID

from PySide6.QtCore import QDate, QSignalBlocker, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.trade_history import BasketHistoryPage
from tiewtrade.market_data.config import SUPPORTED_V1_TIMEFRAME_CHOICES
from tiewtrade.trading.trade_history import TradeFill
from tiewtrade.ui.trade_history_presenter import (
    TradeHistoryFilterValues,
    basket_rows,
    fill_rows,
    page_state,
    pnl_text,
)


class TradeHistoryPage(QWidget):
    apply_filters_requested = Signal(object)
    reset_requested = Signal()
    page_requested = Signal(int)
    basket_selected = Signal(object)
    baskets_retry_requested = Signal()
    fills_retry_requested = Signal()

    BASKET_HEADERS = (
        "Opened At",
        "Mode",
        "Market",
        "Symbol",
        "Timeframe",
        "Entries",
        "Notional",
        "Gross PnL",
        "Fees",
        "Funding Fee",
        "Net PnL",
        "Status",
    )
    FILL_HEADERS = (
        "Filled At",
        "Side",
        "Entry #",
        "Price",
        "Quantity",
        "Notional",
        "Commission",
        "Realized PnL",
        "Source",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tradeHistoryPage")
        self.setAccessibleName("Trade History")
        self._current_page = 1
        self._has_basket_result = False
        self._fill_result_basket_id: UUID | None = None
        self._baskets_loading = False
        self._previous_page_available = False
        self._next_page_available = False

        self.symbol = self._combo(
            "historySymbol", (("All", None), ("BTCUSDT", "BTCUSDT"))
        )
        self.timeframe = self._combo(
            "historyTimeframe",
            (("All", None),)
            + tuple((value, value) for value in SUPPORTED_V1_TIMEFRAME_CHOICES),
        )
        self.market = self._combo(
            "historyMarket",
            (("All", None), ("Spot", "spot"), ("Futures", "futures")),
        )
        self.mode = self._combo(
            "historyMode",
            (("All", None), ("Paper", "paper"), ("Live", "live")),
        )
        self.status = self._combo(
            "historyStatus",
            (("All", None), ("Open", "open"), ("Closed", "closed")),
        )

        self.from_date_enabled = QCheckBox("From Date (UTC)")
        self.from_date_enabled.setObjectName("fromDateEnabled")
        self.from_date = self._date_edit("fromDate", "From Date (UTC)")
        self.to_date_enabled = QCheckBox("To Date (UTC)")
        self.to_date_enabled.setObjectName("toDateEnabled")
        self.to_date = self._date_edit("toDate", "To Date (UTC)")
        self.from_date_enabled.toggled.connect(self.from_date.setEnabled)
        self.to_date_enabled.toggled.connect(self.to_date.setEnabled)

        self.filter_error = QLabel()
        self.filter_error.setObjectName("filterError")
        self.filter_error.setWordWrap(True)
        self.filter_error.setVisible(False)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("secondaryButton")
        self.apply_button = QPushButton("Apply Filters")
        self.apply_button.setObjectName("primaryButton")
        self.reset_button.clicked.connect(self._reset_filters)
        self.apply_button.clicked.connect(self._apply_filters)

        self.total_net_pnl_label = QLabel("Total Net PnL")
        self.total_net_pnl_label.setObjectName("summaryLabel")
        self.total_net_pnl_label.setVisible(False)
        self.total_net_pnl = QLabel()
        self.total_net_pnl.setObjectName("summaryValue")
        self.total_net_pnl.setAccessibleName("Total Net PnL")
        self.total_net_pnl.setVisible(False)
        self.total_items = QLabel()
        self.total_items.setObjectName("supportingText")

        self.basket_table = self._table(
            "basketHistoryTable", "Basket History", self.BASKET_HEADERS
        )
        self.basket_table.itemSelectionChanged.connect(self._emit_basket_selection)
        self.basket_state = self._state_label("basketState", "Basket History status")
        self.retry_baskets_button = self._retry_button("retryBasketsButton")
        self.retry_baskets_button.clicked.connect(self.baskets_retry_requested)

        self.previous_button = QPushButton("Previous")
        self.previous_button.setObjectName("secondaryButton")
        self.previous_button.setEnabled(False)
        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setObjectName("pageLabel")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("secondaryButton")
        self.next_button.setEnabled(False)
        self.previous_button.clicked.connect(self._request_previous_page)
        self.next_button.clicked.connect(self._request_next_page)

        self.fill_table = self._table(
            "tradeFillsTable", "Trade Fills", self.FILL_HEADERS
        )
        self.fill_state = self._state_label("fillState", "Trade Fills status")
        self.retry_fills_button = self._retry_button("retryFillsButton")
        self.retry_fills_button.clicked.connect(self.fills_retry_requested)

        self._build_layout()

    @property
    def basket_headers(self) -> tuple[str, ...]:
        return self.BASKET_HEADERS

    @property
    def fill_headers(self) -> tuple[str, ...]:
        return self.FILL_HEADERS

    def filter_values(self) -> TradeHistoryFilterValues:
        return TradeHistoryFilterValues(
            symbol=self._combo_value(self.symbol),
            timeframe=self._combo_value(self.timeframe),
            market_type=self._combo_value(self.market),
            trade_mode=self._combo_value(self.mode),
            status=self._combo_value(self.status),
            from_date=(
                self._python_date(self.from_date.date())
                if self.from_date_enabled.isChecked()
                else None
            ),
            to_date=(
                self._python_date(self.to_date.date())
                if self.to_date_enabled.isChecked()
                else None
            ),
        )

    @Slot(bool)
    def set_baskets_loading(self, loading: bool) -> None:
        self._baskets_loading = loading
        self._set_filter_controls_enabled(not loading)
        if not loading:
            self.previous_button.setEnabled(self._previous_page_available)
            self.next_button.setEnabled(self._next_page_available)
            return
        if not self._has_basket_result:
            self._clear_basket_result()
        self._set_basket_state("Loading trade history…")
        self.retry_baskets_button.setVisible(False)
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)

    @Slot(object)
    def show_baskets(self, result: BasketHistoryPage) -> None:
        rows = basket_rows(result.items)
        blocker = QSignalBlocker(self.basket_table)
        self.basket_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row.values):
                item = self._table_item(value)
                item.setData(Qt.ItemDataRole.UserRole, row.basket_id)
                self.basket_table.setItem(row_index, column_index, item)
        if rows:
            self.basket_table.setCurrentCell(0, 0)
            self.basket_table.selectRow(0)
        del blocker

        self._has_basket_result = True
        self._clear_fill_result()
        self.total_net_pnl_label.setVisible(True)
        self.total_net_pnl.setText(pnl_text(result.net_realized_pnl))
        self.total_net_pnl.setVisible(True)
        self.total_items.setText(f"{result.total_items} total Baskets")
        self.retry_baskets_button.setVisible(False)
        if rows:
            self.basket_state.clear()
            self.basket_state.setVisible(False)
        else:
            self._set_basket_state("No trade history")
        self._show_page_state(result.page, result.page_size, result.total_items)

    @Slot(object)
    def show_baskets_empty(self, result: BasketHistoryPage) -> None:
        self.show_baskets(result)

    @Slot(str)
    def show_baskets_unavailable(self, message: str) -> None:
        if self._has_basket_result:
            self._set_basket_state(f"Stale · {message}")
        else:
            self._clear_basket_result()
            self._set_basket_state(message)
        self.retry_baskets_button.setVisible(True)

    @Slot(str)
    def show_filter_error(self, message: str) -> None:
        self.filter_error.setText(message)
        self.filter_error.setVisible(True)

    @Slot(bool)
    def set_fills_loading(self, loading: bool) -> None:
        if not loading:
            return
        if self._fill_result_basket_id != self._selected_basket_id():
            self._clear_fill_result()
        self._set_fill_state("Loading trade fills…")
        self.retry_fills_button.setVisible(False)

    @Slot(object, object)
    def show_fills(self, basket_id: UUID, fills: tuple[TradeFill, ...]) -> None:
        rows = fill_rows(fills)
        blocker = QSignalBlocker(self.fill_table)
        self.fill_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row.values):
                self.fill_table.setItem(
                    row_index, column_index, self._table_item(value)
                )
        del blocker
        self._fill_result_basket_id = basket_id
        self.fill_state.clear()
        self.fill_state.setVisible(False)
        self.retry_fills_button.setVisible(False)

    @Slot(object)
    def show_fills_empty(self, basket_id: UUID) -> None:
        self._clear_table(self.fill_table)
        self._fill_result_basket_id = basket_id
        self._set_fill_state("No fills for this Basket")
        self.retry_fills_button.setVisible(False)

    @Slot(object, str)
    def show_fills_unavailable(self, basket_id: UUID, message: str) -> None:
        if self._fill_result_basket_id == basket_id:
            self._set_fill_state(f"Stale · {message}")
        else:
            self._clear_fill_result()
            self._set_fill_state(message)
        self.retry_fills_button.setVisible(True)

    @Slot()
    def _apply_filters(self) -> None:
        self.filter_error.clear()
        self.filter_error.setVisible(False)
        self.apply_filters_requested.emit(self.filter_values())

    @Slot()
    def _reset_filters(self) -> None:
        for combo in (
            self.symbol,
            self.timeframe,
            self.market,
            self.mode,
            self.status,
        ):
            combo.setCurrentIndex(0)
        self.from_date_enabled.setChecked(False)
        self.to_date_enabled.setChecked(False)
        self.filter_error.clear()
        self.filter_error.setVisible(False)
        self.reset_requested.emit()

    @Slot()
    def _emit_basket_selection(self) -> None:
        row = self.basket_table.currentRow()
        if row < 0:
            return
        item = self.basket_table.item(row, 0)
        if item is None:
            return
        basket_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(basket_id, UUID):
            self.basket_selected.emit(basket_id)

    @Slot()
    def _request_previous_page(self) -> None:
        self.page_requested.emit(self._current_page - 1)

    @Slot()
    def _request_next_page(self) -> None:
        self.page_requested.emit(self._current_page + 1)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        heading = QLabel("Trade History")
        heading.setObjectName("pageTitle")
        description = QLabel(
            "Review recorded Basket results and execution-level Trade Fills."
        )
        description.setObjectName("supportingText")
        root.addWidget(heading)
        root.addWidget(description)
        root.addWidget(self._build_filter_card())

        basket_heading = QHBoxLayout()
        basket_heading.setSpacing(12)
        basket_title = QLabel("Basket History")
        basket_title.setObjectName("sectionTitle")
        basket_heading.addWidget(basket_title)
        basket_heading.addWidget(self.total_items)
        basket_heading.addStretch()
        basket_heading.addWidget(self.total_net_pnl_label)
        basket_heading.addWidget(self.total_net_pnl)
        root.addLayout(basket_heading)
        root.addWidget(self.basket_table, 1)
        root.addLayout(self._state_row(self.basket_state, self.retry_baskets_button))

        pagination = QHBoxLayout()
        pagination.addStretch()
        pagination.addWidget(self.previous_button)
        pagination.addWidget(self.page_label)
        pagination.addWidget(self.next_button)
        pagination.addStretch()
        root.addLayout(pagination)

        fill_title = QLabel("Trade Fills")
        fill_title.setObjectName("sectionTitle")
        root.addWidget(fill_title)
        root.addWidget(self.fill_table, 1)
        root.addLayout(self._state_row(self.fill_state, self.retry_fills_button))

    def _build_filter_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("filterCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        for column in range(4):
            layout.setColumnStretch(column, 1)

        for column, (label, field) in enumerate(
            (
                ("Symbol", self.symbol),
                ("Timeframe", self.timeframe),
                ("Market", self.market),
                ("Mode", self.mode),
                ("Status", self.status),
            )
        ):
            layout.addWidget(self._field_label(label, field), 0, column)
            layout.addWidget(field, 1, column)

        layout.addWidget(self.from_date_enabled, 2, 0)
        layout.addWidget(self.from_date, 3, 0, 1, 2)
        layout.addWidget(self.to_date_enabled, 2, 2)
        layout.addWidget(self.to_date, 3, 2, 1, 2)
        actions = QHBoxLayout()
        actions.addWidget(self.reset_button)
        actions.addWidget(self.apply_button)
        layout.addLayout(actions, 3, 4)
        layout.addWidget(self.filter_error, 4, 0, 1, 5)
        return card

    def _show_page_state(
        self, current_page: int, page_size: int, total_items: int
    ) -> None:
        state = page_state(
            page=current_page, page_size=page_size, total_items=total_items
        )
        self._current_page = state.current_page
        self.page_label.setText(f"Page {state.current_page} of {state.total_pages}")
        self.page_label.setVisible(True)
        self._previous_page_available = state.previous_enabled
        self._next_page_available = state.next_enabled
        self.previous_button.setEnabled(
            state.previous_enabled and not self._baskets_loading
        )
        self.next_button.setEnabled(state.next_enabled and not self._baskets_loading)

    def _clear_pagination(self) -> None:
        self._current_page = 1
        self._previous_page_available = False
        self._next_page_available = False
        self.page_label.clear()
        self.page_label.setVisible(False)
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _clear_fill_result(self) -> None:
        self._clear_table(self.fill_table)
        self._fill_result_basket_id = None
        self.fill_state.clear()
        self.fill_state.setVisible(False)
        self.retry_fills_button.setVisible(False)

    def _set_filter_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.symbol,
            self.timeframe,
            self.market,
            self.mode,
            self.status,
            self.from_date_enabled,
            self.to_date_enabled,
            self.reset_button,
            self.apply_button,
        ):
            widget.setEnabled(enabled)
        self.from_date.setEnabled(enabled and self.from_date_enabled.isChecked())
        self.to_date.setEnabled(enabled and self.to_date_enabled.isChecked())

    def _set_basket_state(self, message: str) -> None:
        self.basket_state.setText(message)
        self.basket_state.setVisible(True)

    def _set_fill_state(self, message: str) -> None:
        self.fill_state.setText(message)
        self.fill_state.setVisible(True)

    @staticmethod
    def _combo(
        object_name: str, choices: tuple[tuple[str, str | None], ...]
    ) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(object_name)
        for label, value in choices:
            combo.addItem(label, value)
        return combo

    @staticmethod
    def _date_edit(object_name: str, accessible_name: str) -> QDateEdit:
        field = QDateEdit(QDate.currentDate())
        field.setObjectName(object_name)
        field.setAccessibleName(accessible_name)
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        field.setEnabled(False)
        return field

    @staticmethod
    def _table(
        object_name: str, accessible_name: str, headers: tuple[str, ...]
    ) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setObjectName(object_name)
        table.setAccessibleName(accessible_name)
        table.setHorizontalHeaderLabels(list(headers))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _table_item(value: str) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item

    @staticmethod
    def _state_label(object_name: str, accessible_name: str) -> QLabel:
        label = QLabel()
        label.setObjectName(object_name)
        label.setAccessibleName(accessible_name)
        label.setProperty("stateMessage", True)
        label.setWordWrap(True)
        label.setVisible(False)
        return label

    @staticmethod
    def _retry_button(object_name: str) -> QPushButton:
        button = QPushButton("Try Again")
        button.setObjectName(object_name)
        button.setProperty("retryButton", True)
        button.setVisible(False)
        return button

    @staticmethod
    def _state_row(message: QLabel, retry: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(message)
        row.addStretch()
        row.addWidget(retry)
        return row

    @staticmethod
    def _field_label(text: str, field: QWidget) -> QLabel:
        label = QLabel(text)
        label.setObjectName("filterLabel")
        label.setBuddy(field)
        return label

    @staticmethod
    def _combo_value(combo: QComboBox) -> str | None:
        value = combo.currentData()
        return None if value is None else str(value)

    @staticmethod
    def _python_date(value: QDate) -> date:
        return date(value.year(), value.month(), value.day())

    @staticmethod
    def _clear_table(table: QTableWidget) -> None:
        blocker = QSignalBlocker(table)
        table.clearSelection()
        table.setCurrentCell(-1, -1)
        table.setRowCount(0)
        del blocker

    def _clear_basket_result(self) -> None:
        self._has_basket_result = False
        self._clear_table(self.basket_table)
        self._clear_fill_result()
        self.total_net_pnl_label.setVisible(False)
        self.total_net_pnl.clear()
        self.total_net_pnl.setVisible(False)
        self.total_items.clear()
        self.retry_fills_button.setVisible(False)
        self._clear_pagination()

    def _selected_basket_id(self) -> UUID | None:
        row = self.basket_table.currentRow()
        if row < 0:
            return None
        item = self.basket_table.item(row, 0)
        if item is None:
            return None
        basket_id = item.data(Qt.ItemDataRole.UserRole)
        return basket_id if isinstance(basket_id, UUID) else None
