import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import create_autospec
from uuid import UUID

import pytest

from tests.support.trade_history_records import BASKET_ID, basket_result, trade_fill
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.trade_history import (
    SQLiteTradeHistory,
    TradeHistoryConflictError,
    TradeHistoryUnavailableError,
)
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
    TradeFill,
)


@pytest.fixture
def history(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    return SQLiteTradeHistory(database)


def open_basket() -> BasketResult:
    return basket_result(
        closed_at_utc=None,
        invested_notional=Decimal("200"),
        gross_realized_pnl=Decimal("0"),
        trading_fees=Decimal("0.2"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("-0.2"),
        status=BasketStatus.OPEN,
    )


def test_exact_duplicate_fill_is_a_no_op(history: SQLiteTradeHistory) -> None:
    basket = open_basket()
    fill = trade_fill()

    assert history.record_open_basket(basket, fill) is True
    assert history.record_open_basket(basket, fill) is False
    assert history.get_basket(basket.basket_id) == basket
    assert history.list_fills(basket.basket_id) == (fill,)


def test_open_basket_requires_open_status(history: SQLiteTradeHistory) -> None:
    basket = basket_result(status=BasketStatus.CLOSED)

    with pytest.raises(TradeHistoryConflictError, match="OPEN"):
        history.record_open_basket(basket, trade_fill())

    assert history.get_basket(basket.basket_id) is None


def test_same_fill_id_with_different_payload_is_a_conflict(
    history: SQLiteTradeHistory,
) -> None:
    basket = open_basket()
    fill = trade_fill()
    history.record_open_basket(basket, fill)
    conflicting = replace(
        fill,
        price=Decimal("101"),
        notional=Decimal("202"),
    )

    with pytest.raises(TradeHistoryConflictError, match="fill_id"):
        history.record_open_basket(basket, conflicting)

    assert history.get_basket(basket.basket_id) == basket
    assert history.list_fills(basket.basket_id) == (fill,)


@pytest.mark.parametrize(
    ("market_type", "leverage"),
    [
        (MarketType.SPOT, None),
        (MarketType.FUTURES, 3),
    ],
)
def test_partial_fills_share_order_and_entry_without_incrementing_entry_count(
    history: SQLiteTradeHistory,
    market_type: MarketType,
    leverage: int | None,
) -> None:
    first = trade_fill()
    opened = replace(
        open_basket(),
        market_type=market_type,
        leverage=leverage,
    )
    history.record_open_basket(opened, first)
    second = trade_fill(
        fill_id="fill-partial-2",
        order_id=first.order_id,
        entry_number=first.entry_number,
        filled_at_utc=first.filled_at_utc + timedelta(seconds=1),
        price=Decimal("101"),
        quantity=Decimal("0.5"),
        notional=Decimal("50.5"),
        commission=Decimal("0.0505"),
    )
    updated = replace(
        opened,
        invested_notional=Decimal("250.5"),
        trading_fees=Decimal("0.2505"),
        net_realized_pnl=Decimal("-0.2505"),
    )

    assert history.record_entry_fill(updated, second) is True
    assert history.get_basket(opened.basket_id) == updated
    assert history.list_fills(opened.basket_id) == (first, second)


def closed_basket(opened: BasketResult) -> BasketResult:
    return replace(
        opened,
        closed_at_utc=datetime(2026, 1, 2, tzinfo=UTC),
        gross_realized_pnl=Decimal("20"),
        trading_fees=Decimal("0.42"),
        net_realized_pnl=Decimal("19.58"),
        status=BasketStatus.CLOSED,
    )


def sell_fill() -> TradeFill:
    return trade_fill(
        fill_id="fill-sell",
        order_id="order-sell",
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=datetime(2026, 1, 2, tzinfo=UTC),
        price=Decimal("110"),
        notional=Decimal("220"),
        commission=Decimal("0.22"),
        realized_pnl=Decimal("19.58"),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", UUID("00000000-0000-0000-0000-000000000999")),
        ("trade_mode", TradeMode.LIVE),
        ("market_type", MarketType.FUTURES),
        ("symbol", "ETHUSDT"),
        ("timeframe", "15m"),
        ("strategy_preset_version", "rsi-step-grid-v2"),
        ("opened_at_utc", datetime(2026, 1, 2, tzinfo=UTC)),
    ],
)
def test_entry_rejects_changed_basket_identity(
    history: SQLiteTradeHistory,
    field: str,
    value: object,
) -> None:
    opened = open_basket()
    history.record_open_basket(opened, trade_fill())
    second = trade_fill(fill_id="fill-2", order_id="order-2", entry_number=2)
    identity_changes = {field: value}
    if field == "market_type":
        identity_changes["leverage"] = 3
    proposed = replace(
        opened,
        **{
            **identity_changes,
            "entry_count": 2,
            "invested_notional": opened.invested_notional + second.notional,
            "trading_fees": opened.trading_fees + second.commission,
            "net_realized_pnl": (
                opened.gross_realized_pnl
                - opened.trading_fees
                - second.commission
                - opened.funding_fee
            ),
        },
    )

    with pytest.raises(TradeHistoryConflictError):
        history.record_entry_fill(proposed, second)


@pytest.mark.parametrize("field", ["basket_id", "session_id"])
def test_fill_rejects_different_basket_or_session(
    history: SQLiteTradeHistory,
    field: str,
) -> None:
    basket = open_basket()
    fill = replace(
        trade_fill(),
        **{field: UUID("00000000-0000-0000-0000-000000000999")},
    )

    with pytest.raises(TradeHistoryConflictError):
        history.record_open_basket(basket, fill)

    assert history.get_basket(basket.basket_id) is None


@pytest.mark.parametrize("operation", ["entry", "close"])
def test_unknown_basket_rejects_entry_and_close(
    history: SQLiteTradeHistory,
    operation: str,
) -> None:
    with pytest.raises(TradeHistoryConflictError, match="does not exist"):
        if operation == "entry":
            history.record_entry_fill(
                replace(open_basket(), entry_count=2),
                trade_fill(
                    fill_id="fill-2",
                    order_id="order-2",
                    entry_number=2,
                ),
            )
        else:
            history.record_closed_basket(
                closed_basket(open_basket()),
                sell_fill(),
            )

    assert history.list_fills(BASKET_ID) == ()


def test_closed_basket_rejects_new_entry(history: SQLiteTradeHistory) -> None:
    opened = open_basket()
    first = trade_fill()
    closed = closed_basket(opened)
    exit_trade = sell_fill()
    history.record_open_basket(opened, first)
    history.record_closed_basket(closed, exit_trade)
    next_fill = trade_fill(fill_id="fill-3", order_id="order-3", entry_number=2)
    proposed = replace(closed, status=BasketStatus.OPEN, closed_at_utc=None)

    with pytest.raises(TradeHistoryConflictError, match="closed"):
        history.record_entry_fill(proposed, next_fill)

    assert history.get_basket(BASKET_ID) == closed
    assert history.list_fills(BASKET_ID) == (first, exit_trade)


def test_exact_duplicate_close_after_closed_is_a_no_op(
    history: SQLiteTradeHistory,
) -> None:
    opened = open_basket()
    first = trade_fill()
    closed = closed_basket(opened)
    exit_trade = sell_fill()
    history.record_open_basket(opened, first)

    assert history.record_closed_basket(closed, exit_trade) is True
    assert history.record_closed_basket(closed, exit_trade) is False
    assert history.list_fills(BASKET_ID) == (first, exit_trade)


def test_open_basket_rolls_back_when_fill_insert_fails(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    history = SQLiteTradeHistory(database)
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_trade_fill
            BEFORE INSERT ON trade_fills
            BEGIN
                SELECT RAISE(ABORT, 'forced fill failure');
            END
            """
        )

    with pytest.raises(TradeHistoryUnavailableError):
        history.record_open_basket(open_basket(), trade_fill())

    assert history.get_basket(BASKET_ID) is None
    assert history.list_fills(BASKET_ID) == ()


def test_entry_fill_rolls_back_when_basket_update_fails(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    history = SQLiteTradeHistory(database)
    opened = open_basket()
    first = trade_fill()
    history.record_open_basket(opened, first)
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_basket_update
            BEFORE UPDATE ON basket_results
            BEGIN
                SELECT RAISE(ABORT, 'forced Basket failure');
            END
            """
        )
    second = trade_fill(fill_id="fill-2", order_id="order-2", entry_number=2)
    proposed = replace(
        opened,
        entry_count=2,
        invested_notional=opened.invested_notional + second.notional,
        trading_fees=opened.trading_fees + second.commission,
        net_realized_pnl=(
            opened.gross_realized_pnl
            - opened.trading_fees
            - second.commission
            - opened.funding_fee
        ),
    )

    with pytest.raises(TradeHistoryUnavailableError):
        history.record_entry_fill(proposed, second)

    assert history.get_basket(BASKET_ID) == opened
    assert history.list_fills(BASKET_ID) == (first,)


def test_read_wraps_connection_close_failure() -> None:
    database = create_autospec(SQLiteDatabase, instance=True)
    connection = create_autospec(sqlite3.Connection, instance=True)
    database.connect.return_value = connection
    connection.execute.return_value.fetchone.return_value = None
    connection.close.side_effect = sqlite3.OperationalError("forced close failure")
    history = SQLiteTradeHistory(database)

    with pytest.raises(TradeHistoryUnavailableError, match="close") as raised:
        history.get_basket(BASKET_ID)

    assert isinstance(raised.value.__cause__, sqlite3.OperationalError)


def test_rollback_failure_does_not_escape_as_raw_sqlite_error() -> None:
    database = create_autospec(SQLiteDatabase, instance=True)
    connection = create_autospec(sqlite3.Connection, instance=True)
    database.connect.return_value = connection
    connection.execute.side_effect = [
        None,
        sqlite3.OperationalError("forced write failure"),
    ]
    connection.rollback.side_effect = sqlite3.OperationalError(
        "forced rollback failure"
    )
    history = SQLiteTradeHistory(database)

    with pytest.raises(TradeHistoryUnavailableError, match="write") as raised:
        history.record_open_basket(open_basket(), trade_fill())

    assert isinstance(raised.value.__cause__, sqlite3.OperationalError)


def test_read_closes_connection_when_row_mapping_fails() -> None:
    database = create_autospec(SQLiteDatabase, instance=True)
    connection = create_autospec(sqlite3.Connection, instance=True)
    database.connect.return_value = connection
    connection.execute.return_value.fetchone.return_value = {"basket_id": "not-a-uuid"}
    history = SQLiteTradeHistory(database)

    with pytest.raises(ValueError):
        history.get_basket(BASKET_ID)

    connection.close.assert_called_once_with()


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

    assert version == 2
    assert {"basket_results", "trade_fills"} <= table_names
    assert {
        "basket_results_history_idx",
        "trade_fills_basket_time_idx",
    } <= index_names
    assert basket_columns["basket_id"] == "TEXT"
    assert basket_columns["invested_notional"] == "TEXT"
    assert basket_columns["opened_at_utc"] == "TEXT"
    assert basket_columns["leverage"] == "INTEGER"
    assert fill_columns["fill_id"] == "TEXT"
    assert fill_columns["price"] == "TEXT"
    assert fill_columns["filled_at_utc"] == "TEXT"


def test_migration_rejects_future_schema_version(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 3")

    with pytest.raises(ValueError, match="newer than supported"):
        database.migrate()


def test_migration_from_v1_preserves_spot_basket_with_null_leverage(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    legacy = basket_result()
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TABLE basket_results (
                basket_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                trade_mode TEXT NOT NULL,
                market_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                strategy_preset_version TEXT NOT NULL,
                opened_at_utc TEXT NOT NULL,
                closed_at_utc TEXT,
                entry_count INTEGER NOT NULL,
                invested_notional TEXT NOT NULL,
                gross_realized_pnl TEXT NOT NULL,
                trading_fees TEXT NOT NULL,
                funding_fee TEXT NOT NULL,
                net_realized_pnl TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO basket_results VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                str(legacy.basket_id),
                str(legacy.session_id),
                legacy.trade_mode.value,
                legacy.market_type.value,
                legacy.symbol,
                legacy.timeframe,
                legacy.strategy_preset_version,
                legacy.opened_at_utc.isoformat(),
                legacy.closed_at_utc.isoformat(),
                legacy.entry_count,
                str(legacy.invested_notional),
                str(legacy.gross_realized_pnl),
                str(legacy.trading_fees),
                str(legacy.funding_fee),
                str(legacy.net_realized_pnl),
                legacy.status.value,
            ),
        )
        connection.execute("PRAGMA user_version = 1")

    database.migrate()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        leverage = connection.execute(
            "SELECT leverage FROM basket_results WHERE basket_id = ?",
            (str(legacy.basket_id),),
        ).fetchone()[0]
    assert version == 2
    assert leverage is None
    assert SQLiteTradeHistory(database).get_basket(legacy.basket_id) == legacy


def test_futures_leverage_round_trips_and_is_immutable(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    history = SQLiteTradeHistory(database)
    futures_open = replace(
        open_basket(),
        market_type=MarketType.FUTURES,
        leverage=3,
    )
    first = trade_fill()
    history.record_open_basket(futures_open, first)

    reopened = SQLiteTradeHistory(SQLiteDatabase(database_path))

    assert reopened.get_basket(futures_open.basket_id) == futures_open
    second = trade_fill(
        fill_id="fill-2",
        order_id="order-2",
        entry_number=2,
        filled_at_utc=first.filled_at_utc + timedelta(minutes=1),
    )
    changed = replace(
        futures_open,
        leverage=4,
        entry_count=2,
        invested_notional=Decimal("400"),
        trading_fees=Decimal("0.4"),
        net_realized_pnl=Decimal("-0.4"),
    )
    with pytest.raises(TradeHistoryConflictError, match="leverage"):
        reopened.record_entry_fill(changed, second)


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
