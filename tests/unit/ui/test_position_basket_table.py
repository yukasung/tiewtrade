from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QTableWidget
from pytestqt.qtbot import QtBot

from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    empty_position_basket_tab,
    failed_position_basket_tab,
    loading_position_basket_tab,
    ready_position_basket_tab,
    stale_position_basket_tab,
)
from tiewtrade.ui.position_basket_table import PositionBasketTable

OBSERVED_AT = datetime(2026, 8, 2, 1, 2, 4, tzinfo=UTC)


def _futures_basket() -> BasketSnapshot:
    return BasketSnapshot(
        symbol="BTCUSDT",
        market_type="futures",
        entry_count=2,
        total_quantity=Decimal("0.00600000"),
        average_entry_price=Decimal("66000.1250"),
        current_price=Decimal("66321.1200"),
        take_profit_price=Decimal("67000.0000"),
        unrealized_pnl=Decimal("1.92600000"),
        liquidation_price=Decimal("44000.5000"),
        lifecycle="active_pair",
        updated_at_utc=OBSERVED_AT,
    )


def _spot_basket() -> BasketSnapshot:
    return BasketSnapshot(
        symbol="BTCUSDT",
        market_type="spot",
        entry_count=1,
        total_quantity=Decimal("0.00300000"),
        average_entry_price=Decimal("66000.0000"),
        current_price=Decimal("66001.0000"),
        take_profit_price=Decimal("67000.0000"),
        unrealized_pnl=Decimal("0.00300000"),
        liquidation_price=Decimal("100.0000"),
        lifecycle="active_pair",
        updated_at_utc=OBSERVED_AT,
    )


def _row(table: QTableWidget, row: int) -> tuple[str, ...]:
    values: list[str] = []
    for column in range(table.columnCount()):
        item = table.item(row, column)
        assert item is not None
        values.append(item.text())
    return tuple(values)


def test_position_basket_renders_application_facts_without_recalculation(
    qtbot: QtBot,
) -> None:
    widget = PositionBasketTable()
    qtbot.addWidget(widget)

    widget.show_snapshot(
        ready_position_basket_tab(_futures_basket(), observed_at_utc=OBSERVED_AT)
    )

    assert widget.headers == (
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
    assert _row(widget.table, 0) == (
        "BTCUSDT",
        "Futures",
        "2",
        "0.00600000",
        "66000.1250",
        "66321.1200",
        "67000.0000",
        "1.92600000 USDT · Profit",
        "44000.5000",
        "Active Pair",
    )
    assert widget.state_label.text() == ""
    assert widget.state_label.accessibleName() == "Position / Basket status"


def test_spot_position_displays_no_liquidation_price(qtbot: QtBot) -> None:
    widget = PositionBasketTable()
    qtbot.addWidget(widget)

    widget.show_snapshot(
        ready_position_basket_tab(_spot_basket(), observed_at_utc=OBSERVED_AT)
    )

    liquidation_price = widget.table.item(0, 8)
    assert liquidation_price is not None
    assert liquidation_price.text() == "—"


def test_position_basket_states_preserve_or_clear_application_facts(
    qtbot: QtBot,
) -> None:
    widget = PositionBasketTable()
    qtbot.addWidget(widget)
    ready = ready_position_basket_tab(_futures_basket(), observed_at_utc=OBSERVED_AT)

    for snapshot, expected_state in (
        (loading_position_basket_tab(ready), "Loading Position / Basket…"),
        (
            failed_position_basket_tab(ready, "Position / Basket data is unavailable"),
            "Position / Basket data is unavailable",
        ),
        (
            stale_position_basket_tab(ready),
            "Stale Position / Basket data as of 2026-08-02 01:02:04 UTC",
        ),
    ):
        widget.show_snapshot(snapshot)
        assert widget.table.rowCount() == 1
        assert widget.state_label.text() == expected_state
        assert not widget.state_label.isHidden()

    widget.show_snapshot(empty_position_basket_tab())

    assert widget.table.rowCount() == 0
    assert widget.state_label.text() == "No open Position or Basket"


def test_position_basket_ignores_wrong_snapshot_type(qtbot: QtBot) -> None:
    widget = PositionBasketTable()
    qtbot.addWidget(widget)
    widget.show_snapshot(
        ready_position_basket_tab(_futures_basket(), observed_at_utc=OBSERVED_AT)
    )

    widget.show_snapshot(object())

    assert widget.table.rowCount() == 1
    assert widget.table.accessibleName() == "Position / Basket"
