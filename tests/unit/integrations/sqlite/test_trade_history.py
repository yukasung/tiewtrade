from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tests.support.trade_history_records import basket_result, trade_fill
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.trade_history import BasketStatus, FillSide


def test_migration_creates_versioned_history_schema_and_indexes(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")

    database.migrate()
    database.migrate()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        index_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        basket_columns = {
            row["name"]: row["type"]
            for row in connection.execute("PRAGMA table_info(basket_results)")
        }
        fill_columns = {
            row["name"]: row["type"]
            for row in connection.execute("PRAGMA table_info(trade_fills)")
        }

    assert version == 1
    assert {"basket_results", "trade_fills"} <= table_names
    assert {
        "basket_results_history_idx",
        "trade_fills_basket_time_idx",
    } <= index_names
    assert basket_columns["basket_id"] == "TEXT"
    assert basket_columns["invested_notional"] == "TEXT"
    assert basket_columns["opened_at_utc"] == "TEXT"
    assert fill_columns["fill_id"] == "TEXT"
    assert fill_columns["price"] == "TEXT"
    assert fill_columns["filled_at_utc"] == "TEXT"


def test_migration_rejects_future_schema_version(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(ValueError, match="newer than supported"):
        database.migrate()


def test_history_round_trips_exact_records_after_reopen(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    history = SQLiteTradeHistory(database)
    opened_at = datetime(2026, 1, 1, 12, 30, 45, 123456, tzinfo=UTC)
    closed_at = datetime(2026, 1, 2, 13, 31, 46, 654321, tzinfo=UTC)
    buy_fill = trade_fill(
        filled_at_utc=opened_at,
        price=Decimal("100.123456789"),
        quantity=Decimal("2.000000001"),
        notional=Decimal("200.246913678123456789"),
        commission=Decimal("0.2000000001"),
    )
    sell_fill = trade_fill(
        fill_id="fill-2",
        order_id="order-2",
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=closed_at,
        price=Decimal("110.123456789"),
        quantity=Decimal("2.000000001"),
        notional=Decimal("220.246913688123456789"),
        commission=Decimal("0.2200000001"),
        realized_pnl=Decimal("20.000000002"),
    )
    basket = basket_result(
        opened_at_utc=opened_at,
        closed_at_utc=closed_at,
        invested_notional=buy_fill.notional,
        gross_realized_pnl=Decimal("20.000000002"),
        trading_fees=Decimal("0.4200000002"),
        net_realized_pnl=Decimal("19.5800000018"),
    )
    open_basket = replace(
        basket,
        closed_at_utc=None,
        gross_realized_pnl=Decimal("0"),
        trading_fees=buy_fill.commission,
        net_realized_pnl=Decimal("-0.2000000001"),
        status=BasketStatus.OPEN,
    )

    history.record_open_basket(open_basket, buy_fill)
    history.record_closed_basket(basket, sell_fill)

    reopened = SQLiteTradeHistory(SQLiteDatabase(database_path))

    assert reopened.get_basket(basket.basket_id) == basket
    assert reopened.list_fills(basket.basket_id) == (buy_fill, sell_fill)
