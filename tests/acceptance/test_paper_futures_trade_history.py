from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from tiewtrade.application.paper_futures_session import PaperFuturesSession
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_futures_history import (
    PaperFuturesHistoryContext,
    PaperFuturesSQLiteHistory,
)
from tiewtrade.integrations.sqlite.persistent_paper_futures_session import (
    create_persistent_paper_futures_session,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules
from tiewtrade.trading.trade_history import BasketStatus, FillSide

SESSION_ID = UUID("00000000-0000-0000-0000-000000000108")


def test_paper_futures_history_survives_restart_and_duplicate_replay(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "history.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    store = SQLiteTradeHistory(database)
    context = PaperFuturesHistoryContext(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
        commission_asset="USDT",
        leverage=3,
    )
    persistent = create_persistent_paper_futures_session(
        build_session(),
        PaperFuturesSQLiteHistory(context, store),
    )
    entry_snapshot = None
    close_snapshot = None
    for candle in configured_candles():
        current = persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        ).session
        if current.entry_fill is not None:
            entry_snapshot = current
        if current.closed_basket is not None:
            close_snapshot = current

    assert entry_snapshot is not None
    assert entry_snapshot.entry_fill is not None
    assert close_snapshot is not None
    assert close_snapshot.exit_fill is not None
    assert close_snapshot.closed_basket is not None
    basket_id = close_snapshot.closed_basket.basket_id

    reopened_database = SQLiteDatabase(database_path)
    reopened_database.migrate()
    reopened = SQLiteTradeHistory(reopened_database)
    basket = reopened.get_basket(basket_id)
    fills = reopened.list_fills(basket_id)

    assert basket is not None
    assert basket.status is BasketStatus.CLOSED
    assert basket.trade_mode is TradeMode.PAPER
    assert basket.market_type is MarketType.FUTURES
    assert basket.leverage == 3
    assert basket.invested_notional == (
        entry_snapshot.entry_fill.price * entry_snapshot.entry_fill.quantity
    )
    assert basket.gross_realized_pnl == (
        close_snapshot.closed_basket.gross_realized_pnl
    )
    assert basket.trading_fees == close_snapshot.closed_basket.trading_fees
    assert basket.funding_fee == Decimal("0.00")
    assert basket.funding_fee.as_tuple().exponent == -2
    assert basket.net_realized_pnl == close_snapshot.closed_basket.net_realized_pnl
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
    assert [fill.commission for fill in fills] == [
        entry_snapshot.entry_fill.fee,
        close_snapshot.exit_fill.fee,
    ]

    replay_history = PaperFuturesSQLiteHistory(context, reopened)
    assert not replay_history.record_entry(
        basket_id=basket_id,
        entry_number=1,
        fill=entry_snapshot.entry_fill,
    )
    assert not replay_history.record_close(
        basket_id=basket_id,
        fill=close_snapshot.exit_fill,
        closed=close_snapshot.closed_basket,
    )
    assert reopened.get_basket(basket_id) == basket
    assert reopened.list_fills(basket_id) == fills


def build_session() -> PaperFuturesSession:
    return PaperFuturesSession(
        SessionConfig(
            session_id=SESSION_ID,
            preset_version="rsi-step-grid-v1",
            market_type=MarketType.FUTURES,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("200000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=10),
            spot_policy=None,
            futures_policy=FuturesTradingPolicy.v1(leverage=3),
        ),
        MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        RsiStepGridPreset.v1(),
    )


def configured_candles() -> list[Candle]:
    candles: list[Candle] = []
    close = Decimal("100")
    for index in range(15):
        candles.append(configured_candle(index, close=close))
        close -= Decimal("1")
    for index in range(15, 40):
        close += Decimal("1")
        candles.append(configured_candle(index, close=close))
    return candles


def configured_candle(index: int, *, close: Decimal) -> Candle:
    open_price = close - Decimal("0.5")
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5),
        open=open_price,
        high=max(open_price, close) + Decimal("1"),
        low=min(open_price, close) - Decimal("1"),
        close=close,
        volume=Decimal("1"),
    )
