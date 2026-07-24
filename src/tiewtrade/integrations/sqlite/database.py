import sqlite3
from pathlib import Path


class SQLiteDatabase:
    _SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> None:
        connection = self.connect()
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > self._SCHEMA_VERSION:
                raise ValueError("database schema is newer than supported")
            if version == self._SCHEMA_VERSION:
                return

            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS basket_results (
                        basket_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        trade_mode TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        strategy_preset_version TEXT NOT NULL,
                        opened_at_utc TEXT NOT NULL,
                        closed_at_utc TEXT,
                        entry_count INTEGER NOT NULL CHECK (entry_count > 0),
                        invested_notional TEXT NOT NULL,
                        gross_realized_pnl TEXT NOT NULL,
                        trading_fees TEXT NOT NULL,
                        funding_fee TEXT NOT NULL,
                        net_realized_pnl TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('open', 'closed'))
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trade_fills (
                        fill_id TEXT PRIMARY KEY,
                        basket_id TEXT NOT NULL REFERENCES basket_results(basket_id),
                        session_id TEXT NOT NULL,
                        order_id TEXT NOT NULL,
                        exchange_trade_id TEXT,
                        side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                        entry_number INTEGER,
                        filled_at_utc TEXT NOT NULL,
                        price TEXT NOT NULL,
                        quantity TEXT NOT NULL,
                        notional TEXT NOT NULL,
                        commission TEXT NOT NULL,
                        commission_asset TEXT NOT NULL,
                        realized_pnl TEXT NOT NULL,
                        source TEXT NOT NULL CHECK (
                            source IN ('paper_executor', 'binance')
                        ),
                        UNIQUE (source, order_id, exchange_trade_id)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS basket_results_history_idx
                    ON basket_results (opened_at_utc DESC, basket_id DESC)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS trade_fills_basket_time_idx
                    ON trade_fills (basket_id, filled_at_utc, fill_id)
                    """
                )
                connection.execute(f"PRAGMA user_version = {self._SCHEMA_VERSION}")
        finally:
            connection.close()
