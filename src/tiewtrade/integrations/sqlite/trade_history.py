import sqlite3
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
    FillSource,
    TradeFill,
)


class TradeHistoryError(RuntimeError):
    pass


class TradeHistoryConflictError(TradeHistoryError):
    pass


class TradeHistoryUnavailableError(TradeHistoryError):
    pass


class SQLiteTradeHistory:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def record_open_basket(self, basket: BasketResult, fill: TradeFill) -> bool:
        _validate_fill_ownership(basket, fill)

        def operation(connection: sqlite3.Connection) -> bool:
            if _check_duplicate_fill(connection, fill):
                return False
            if _find_basket(connection, basket.basket_id) is not None:
                raise TradeHistoryConflictError("Basket already exists")
            connection.execute(
                """
                INSERT INTO basket_results (
                    basket_id, session_id, trade_mode, market_type, symbol,
                    timeframe, strategy_preset_version, opened_at_utc,
                    closed_at_utc, entry_count, invested_notional,
                    gross_realized_pnl, trading_fees, funding_fee,
                    net_realized_pnl, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _basket_values(basket),
            )
            _insert_fill(connection, fill)
            return True

        return self._run_write(operation)

    def record_entry_fill(self, basket: BasketResult, fill: TradeFill) -> bool:
        _validate_fill_ownership(basket, fill)

        def operation(connection: sqlite3.Connection) -> bool:
            if _check_duplicate_fill(connection, fill):
                return False
            current = _require_basket(connection, basket.basket_id)
            _validate_immutable_identity(current, basket)
            if current.status is not BasketStatus.OPEN:
                raise TradeHistoryConflictError("closed Basket cannot receive a Fill")
            if basket.status is not BasketStatus.OPEN:
                raise TradeHistoryConflictError("Entry Fill requires an OPEN Basket")
            _validate_entry_count(connection, current, basket, fill)
            _insert_fill(connection, fill)
            _update_basket(connection, basket)
            return True

        return self._run_write(operation)

    def record_closed_basket(self, basket: BasketResult, fill: TradeFill) -> bool:
        _validate_fill_ownership(basket, fill)

        def operation(connection: sqlite3.Connection) -> bool:
            if _check_duplicate_fill(connection, fill):
                return False
            current = _require_basket(connection, basket.basket_id)
            _validate_immutable_identity(current, basket)
            if current.status is not BasketStatus.OPEN:
                raise TradeHistoryConflictError("Basket is already closed")
            if basket.status is not BasketStatus.CLOSED:
                raise TradeHistoryConflictError("Close Fill requires a CLOSED Basket")
            _insert_fill(connection, fill)
            _update_basket(connection, basket)
            return True

        return self._run_write(operation)

    def get_basket(self, basket_id: UUID) -> BasketResult | None:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            return _find_basket(connection, basket_id)
        except sqlite3.Error as error:
            raise TradeHistoryUnavailableError(
                "Trade History SQLite read failed"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def list_fills(self, basket_id: UUID) -> tuple[TradeFill, ...]:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            rows = connection.execute(
                """
                SELECT * FROM trade_fills
                WHERE basket_id = ?
                ORDER BY filled_at_utc, fill_id
                """,
                (str(basket_id),),
            ).fetchall()
            return tuple(_fill_from_row(row) for row in rows)
        except sqlite3.Error as error:
            raise TradeHistoryUnavailableError(
                "Trade History SQLite read failed"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def _run_write(
        self,
        operation: Callable[[sqlite3.Connection], bool],
    ) -> bool:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            connection.execute("BEGIN IMMEDIATE")
            result = operation(connection)
            connection.commit()
            return result
        except TradeHistoryError:
            if connection is not None:
                connection.rollback()
            raise
        except sqlite3.Error as error:
            if connection is not None:
                connection.rollback()
            raise TradeHistoryUnavailableError(
                "Trade History SQLite write failed"
            ) from error
        finally:
            if connection is not None:
                connection.close()


def _validate_fill_ownership(basket: BasketResult, fill: TradeFill) -> None:
    if basket.basket_id != fill.basket_id:
        raise TradeHistoryConflictError("Fill belongs to a different Basket")
    if basket.session_id != fill.session_id:
        raise TradeHistoryConflictError("Fill belongs to a different Session")


def _validate_immutable_identity(
    current: BasketResult,
    proposed: BasketResult,
) -> None:
    fields = (
        "basket_id",
        "session_id",
        "trade_mode",
        "market_type",
        "symbol",
        "timeframe",
        "strategy_preset_version",
        "opened_at_utc",
    )
    for field in fields:
        if getattr(current, field) != getattr(proposed, field):
            raise TradeHistoryConflictError(
                f"Basket identity field {field} cannot change"
            )


def _validate_entry_count(
    connection: sqlite3.Connection,
    current: BasketResult,
    proposed: BasketResult,
    fill: TradeFill,
) -> None:
    row = connection.execute(
        """
        SELECT entry_number
        FROM trade_fills
        WHERE basket_id = ? AND order_id = ?
        ORDER BY filled_at_utc, fill_id
        LIMIT 1
        """,
        (str(fill.basket_id), fill.order_id),
    ).fetchone()
    prior_entry_number = row["entry_number"] if row is not None else None
    if prior_entry_number is not None:
        if fill.entry_number != prior_entry_number:
            raise TradeHistoryConflictError(
                "Partial Fills for one Order must use the same entry_number"
            )
        if proposed.entry_count != current.entry_count:
            raise TradeHistoryConflictError(
                "Partial Fill must not increment Basket entry_count"
            )
        return

    expected_entry_number = current.entry_count + 1
    if fill.entry_number != expected_entry_number:
        raise TradeHistoryConflictError("new Entry Fill has an unexpected entry_number")
    if proposed.entry_count != expected_entry_number:
        raise TradeHistoryConflictError(
            "new Entry Fill must increment Basket entry_count once"
        )


def _find_basket(
    connection: sqlite3.Connection,
    basket_id: UUID,
) -> BasketResult | None:
    row = connection.execute(
        "SELECT * FROM basket_results WHERE basket_id = ?",
        (str(basket_id),),
    ).fetchone()
    return _basket_from_row(row) if row is not None else None


def _require_basket(
    connection: sqlite3.Connection,
    basket_id: UUID,
) -> BasketResult:
    basket = _find_basket(connection, basket_id)
    if basket is None:
        raise TradeHistoryConflictError("Basket does not exist")
    return basket


def _find_fill(
    connection: sqlite3.Connection,
    fill_id: str,
) -> TradeFill | None:
    row = connection.execute(
        "SELECT * FROM trade_fills WHERE fill_id = ?",
        (fill_id,),
    ).fetchone()
    return _fill_from_row(row) if row is not None else None


def _check_duplicate_fill(
    connection: sqlite3.Connection,
    fill: TradeFill,
) -> bool:
    existing = _find_fill(connection, fill.fill_id)
    if existing is None:
        return False
    if existing != fill:
        raise TradeHistoryConflictError(
            f"fill_id {fill.fill_id!r} has conflicting payload"
        )
    return True


def _update_basket(
    connection: sqlite3.Connection,
    basket: BasketResult,
) -> None:
    cursor = connection.execute(
        """
        UPDATE basket_results
        SET session_id = ?, trade_mode = ?, market_type = ?, symbol = ?,
            timeframe = ?, strategy_preset_version = ?, opened_at_utc = ?,
            closed_at_utc = ?, entry_count = ?, invested_notional = ?,
            gross_realized_pnl = ?, trading_fees = ?, funding_fee = ?,
            net_realized_pnl = ?, status = ?
        WHERE basket_id = ?
        """,
        (*_basket_values(basket)[1:], str(basket.basket_id)),
    )
    if cursor.rowcount != 1:
        raise TradeHistoryConflictError("Basket does not exist")


def _basket_values(basket: BasketResult) -> tuple[object, ...]:
    return (
        str(basket.basket_id),
        str(basket.session_id),
        basket.trade_mode.value,
        basket.market_type.value,
        basket.symbol,
        basket.timeframe,
        basket.strategy_preset_version,
        _utc_text(basket.opened_at_utc),
        _utc_text(basket.closed_at_utc) if basket.closed_at_utc is not None else None,
        basket.entry_count,
        _decimal_text(basket.invested_notional),
        _decimal_text(basket.gross_realized_pnl),
        _decimal_text(basket.trading_fees),
        _decimal_text(basket.funding_fee),
        _decimal_text(basket.net_realized_pnl),
        basket.status.value,
    )


def _insert_fill(connection: sqlite3.Connection, fill: TradeFill) -> None:
    connection.execute(
        """
        INSERT INTO trade_fills (
            fill_id, basket_id, session_id, order_id, exchange_trade_id, side,
            entry_number, filled_at_utc, price, quantity, notional, commission,
            commission_asset, realized_pnl, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fill.fill_id,
            str(fill.basket_id),
            str(fill.session_id),
            fill.order_id,
            fill.exchange_trade_id,
            fill.side.value,
            fill.entry_number,
            _utc_text(fill.filled_at_utc),
            _decimal_text(fill.price),
            _decimal_text(fill.quantity),
            _decimal_text(fill.notional),
            _decimal_text(fill.commission),
            fill.commission_asset,
            _decimal_text(fill.realized_pnl),
            fill.source.value,
        ),
    )


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _utc_text(value: datetime) -> str:
    return value.isoformat()


def _basket_from_row(row: sqlite3.Row) -> BasketResult:
    return BasketResult(
        basket_id=UUID(row["basket_id"]),
        session_id=UUID(row["session_id"]),
        trade_mode=TradeMode(row["trade_mode"]),
        market_type=MarketType(row["market_type"]),
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        strategy_preset_version=row["strategy_preset_version"],
        opened_at_utc=datetime.fromisoformat(row["opened_at_utc"]),
        closed_at_utc=(
            datetime.fromisoformat(row["closed_at_utc"])
            if row["closed_at_utc"] is not None
            else None
        ),
        entry_count=row["entry_count"],
        invested_notional=Decimal(row["invested_notional"]),
        gross_realized_pnl=Decimal(row["gross_realized_pnl"]),
        trading_fees=Decimal(row["trading_fees"]),
        funding_fee=Decimal(row["funding_fee"]),
        net_realized_pnl=Decimal(row["net_realized_pnl"]),
        status=BasketStatus(row["status"]),
    )


def _fill_from_row(row: sqlite3.Row) -> TradeFill:
    return TradeFill(
        fill_id=row["fill_id"],
        basket_id=UUID(row["basket_id"]),
        session_id=UUID(row["session_id"]),
        order_id=row["order_id"],
        exchange_trade_id=row["exchange_trade_id"],
        side=FillSide(row["side"]),
        entry_number=row["entry_number"],
        filled_at_utc=datetime.fromisoformat(row["filled_at_utc"]),
        price=Decimal(row["price"]),
        quantity=Decimal(row["quantity"]),
        notional=Decimal(row["notional"]),
        commission=Decimal(row["commission"]),
        commission_asset=row["commission_asset"],
        realized_pnl=Decimal(row["realized_pnl"]),
        source=FillSource(row["source"]),
    )
