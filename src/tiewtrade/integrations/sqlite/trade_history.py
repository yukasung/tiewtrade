import sqlite3
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


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _utc_text(value: datetime) -> str:
    return value.isoformat()


class SQLiteTradeHistory:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def record_open_basket(self, basket: BasketResult, fill: TradeFill) -> None:
        connection = self._database.connect()
        try:
            with connection:
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
        finally:
            connection.close()

    def record_entry_fill(self, basket: BasketResult, fill: TradeFill) -> None:
        self._update_basket_and_record_fill(basket, fill)

    def record_closed_basket(self, basket: BasketResult, fill: TradeFill) -> None:
        self._update_basket_and_record_fill(basket, fill)

    def get_basket(self, basket_id: UUID) -> BasketResult | None:
        connection = self._database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM basket_results WHERE basket_id = ?", (str(basket_id),)
            ).fetchone()
        finally:
            connection.close()
        return _basket_from_row(row) if row is not None else None

    def list_fills(self, basket_id: UUID) -> tuple[TradeFill, ...]:
        connection = self._database.connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM trade_fills
                WHERE basket_id = ?
                ORDER BY filled_at_utc, fill_id
                """,
                (str(basket_id),),
            ).fetchall()
        finally:
            connection.close()
        return tuple(_fill_from_row(row) for row in rows)

    def _update_basket_and_record_fill(
        self, basket: BasketResult, fill: TradeFill
    ) -> None:
        connection = self._database.connect()
        try:
            with connection:
                connection.execute(
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
                _insert_fill(connection, fill)
        finally:
            connection.close()


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
