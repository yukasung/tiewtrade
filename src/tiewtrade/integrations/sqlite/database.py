import sqlite3
from pathlib import Path


class UnsupportedDatabaseSchemaError(ValueError):
    def __init__(self, database_version: int, supported_version: int) -> None:
        super().__init__("database schema is newer than supported")
        self.database_version = database_version
        self.supported_version = supported_version


class SQLiteDatabase:
    _SCHEMA_VERSION = 3
    _BUSY_TIMEOUT_MS = 5_000

    def __init__(self, path: Path) -> None:
        self._path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self._BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> None:
        connection = self.connect()
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > self._SCHEMA_VERSION:
                raise UnsupportedDatabaseSchemaError(version, self._SCHEMA_VERSION)
            if version == self._SCHEMA_VERSION:
                return

            with connection:
                if version == 0:
                    _create_schema(connection)
                elif version == 1:
                    connection.execute(
                        """
                        ALTER TABLE basket_results
                        ADD COLUMN leverage INTEGER
                        CHECK (leverage IS NULL OR leverage BETWEEN 1 AND 5)
                        """
                    )
                if version in {0, 1, 2}:
                    _create_bot_sessions_schema(connection)
                connection.execute(f"PRAGMA user_version = {self._SCHEMA_VERSION}")
        finally:
            connection.close()


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS basket_results (
            basket_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            trade_mode TEXT NOT NULL,
            market_type TEXT NOT NULL,
            leverage INTEGER CHECK (
                leverage IS NULL OR leverage BETWEEN 1 AND 5
            ),
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


def _create_bot_sessions_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_sessions (
            session_id TEXT PRIMARY KEY,
            trade_mode TEXT NOT NULL CHECK (trade_mode = 'paper'),
            market_type TEXT NOT NULL CHECK (
                market_type IN ('spot', 'futures')
            ),
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            preset_version TEXT NOT NULL,
            available_capital TEXT NOT NULL,
            max_entries INTEGER NOT NULL CHECK (
                max_entries BETWEEN 2 AND 20 AND max_entries % 2 = 0
            ),
            fee_rate TEXT NOT NULL,
            slippage_bps TEXT NOT NULL,
            spot_trading_capital_ratio TEXT,
            futures_policy_version TEXT,
            futures_leverage INTEGER,
            futures_trading_capital_ratio TEXT,
            futures_collateral_buffer_ratio TEXT,
            futures_maintenance_margin_rate TEXT,
            futures_margin_mode TEXT,
            futures_position_mode TEXT,
            created_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            CHECK (
                (
                    market_type = 'spot'
                    AND spot_trading_capital_ratio IS NOT NULL
                    AND futures_policy_version IS NULL
                )
                OR
                (
                    market_type = 'futures'
                    AND spot_trading_capital_ratio IS NULL
                    AND futures_policy_version IS NOT NULL
                )
            )
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS bot_sessions_single_active_idx
        ON bot_sessions ((1))
        WHERE ended_at_utc IS NULL
        """
    )
