import sqlite3
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionUnavailableError,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import (
    FuturesTradingPolicy,
    MarginMode,
    PositionMode,
)
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy

_INSERT_SQL = """
INSERT INTO bot_sessions (
    session_id, trade_mode, market_type, symbol, timeframe, preset_version,
    available_capital, max_entries, fee_rate, slippage_bps,
    spot_trading_capital_ratio, futures_policy_version, futures_leverage,
    futures_trading_capital_ratio, futures_collateral_buffer_ratio,
    futures_maintenance_margin_rate, futures_margin_mode,
    futures_position_mode, created_at_utc, ended_at_utc
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class SQLiteActivePaperSessions:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def create(self, session: ConfiguredPaperSession) -> PaperSessionCreateOutcome:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            connection.execute("BEGIN IMMEDIATE")
            existing = _find_active(connection)
            if existing is not None:
                connection.commit()
                return PaperSessionCreateOutcome(session=existing, created=False)
            connection.execute(_INSERT_SQL, _session_values(session))
            connection.commit()
            return PaperSessionCreateOutcome(session=session, created=True)
        except sqlite3.Error as error:
            _rollback_if_open(connection)
            raise PaperSessionUnavailableError(
                "Active Paper Session write failed"
            ) from error
        except BaseException:
            _rollback_if_open(connection)
            raise
        finally:
            _close_if_open(connection)

    def get_active(self) -> ConfiguredPaperSession | None:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            result = _find_active(connection)
        except sqlite3.Error as error:
            raise PaperSessionUnavailableError(
                "Active Paper Session read failed"
            ) from error
        finally:
            _close_if_open(connection)
        return result


def _session_from_row(row: sqlite3.Row) -> ConfiguredPaperSession:
    if row["symbol"] != "BTCUSDT":
        raise PaperSessionUnavailableError("Active Paper Session read failed")
    if row["preset_version"] != RsiStepGridPreset.v1().version:
        raise PaperSessionUnavailableError("Active Paper Session read failed")
    market_type = MarketType(row["market_type"])
    spot_policy = (
        SpotTradingPolicy(Decimal(row["spot_trading_capital_ratio"]))
        if market_type is MarketType.SPOT
        else None
    )
    futures_policy = (
        FuturesTradingPolicy(
            version=row["futures_policy_version"],
            leverage=row["futures_leverage"],
            trading_capital_ratio=Decimal(row["futures_trading_capital_ratio"]),
            collateral_buffer_ratio=Decimal(row["futures_collateral_buffer_ratio"]),
            maintenance_margin_rate=Decimal(row["futures_maintenance_margin_rate"]),
            margin_mode=MarginMode(row["futures_margin_mode"]),
            position_mode=PositionMode(row["futures_position_mode"]),
        )
        if market_type is MarketType.FUTURES
        else None
    )
    config = SessionConfig(
        session_id=UUID(row["session_id"]),
        preset_version=row["preset_version"],
        market_type=market_type,
        trade_mode=TradeMode(row["trade_mode"]),
        available_capital=Decimal(row["available_capital"]),
        fee_rate=Decimal(row["fee_rate"]),
        slippage_bps=Decimal(row["slippage_bps"]),
        entry_policy=EntryPolicy(row["max_entries"]),
        spot_policy=spot_policy,
        futures_policy=futures_policy,
    )
    return ConfiguredPaperSession(
        config=config,
        market_data=MarketDataConfig(
            symbol=row["symbol"],
            timeframe=row["timeframe"],
        ),
        created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
    )


def _find_active(connection: sqlite3.Connection) -> ConfiguredPaperSession | None:
    row = connection.execute(
        "SELECT * FROM bot_sessions WHERE ended_at_utc IS NULL"
    ).fetchone()
    return None if row is None else _session_from_row(row)


def _session_values(session: ConfiguredPaperSession) -> tuple[object, ...]:
    config = session.config
    spot = config.spot_policy
    futures = config.futures_policy
    return (
        str(config.session_id),
        config.trade_mode.value,
        config.market_type.value,
        session.market_data.symbol,
        session.market_data.timeframe,
        config.preset_version,
        str(config.available_capital),
        config.entry_policy.max_entries,
        str(config.fee_rate),
        str(config.slippage_bps),
        None if spot is None else str(spot.trading_capital_ratio),
        None if futures is None else futures.version,
        None if futures is None else futures.leverage,
        None if futures is None else str(futures.trading_capital_ratio),
        None if futures is None else str(futures.collateral_buffer_ratio),
        None if futures is None else str(futures.maintenance_margin_rate),
        None if futures is None else futures.margin_mode.value,
        None if futures is None else futures.position_mode.value,
        session.created_at_utc.isoformat(),
        None,
    )


def _rollback_if_open(connection: sqlite3.Connection | None) -> None:
    if connection is not None:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass


def _close_if_open(connection: sqlite3.Connection | None) -> None:
    if connection is not None:
        try:
            connection.close()
        except sqlite3.Error:
            pass
