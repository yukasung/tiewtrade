from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from tiewtrade.application.paper_spot_session import PaperSpotSession
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_spot_history import (
    PaperSpotHistoryContext,
    PaperSpotSQLiteHistory,
)
from tiewtrade.integrations.sqlite.persistent_paper_spot_session import (
    PersistenceState,
    PersistentPaperSpotSQLiteSession,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.replay.csv_candles import load_candles_csv
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules
from tiewtrade.trading.trade_history import BasketStatus, FillSide

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "btcusdt_5m_tracer.csv"
SESSION_ID = UUID("00000000-0000-0000-0000-000000000080")
BASKET_ID = uuid5(SESSION_ID, "basket:1")


def test_replayed_paper_spot_history_is_idempotent_after_sqlite_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "paper-spot-history.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    store = SQLiteTradeHistory(database)
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    preset = RsiStepGridPreset.v1()
    history = PaperSpotSQLiteHistory(
        PaperSpotHistoryContext(
            session_id=SESSION_ID,
            symbol=market_data.symbol,
            timeframe=market_data.timeframe,
            preset_version=preset.version,
            commission_asset="USDT",
        ),
        store,
    )

    first_basket = None
    first_fills = ()
    for replay_number in range(2):
        persistent = PersistentPaperSpotSQLiteSession(
            paper_spot_session(market_data, preset),
            history,
        )
        for candle in load_candles_csv(FIXTURE_PATH, market_data):
            snapshot = persistent.process_completed_candle(
                candle,
                received_at=candle.close_time,
            )
            assert snapshot.persistence_state is PersistenceState.READY
        current_basket = store.get_basket(BASKET_ID)
        current_fills = store.list_fills(BASKET_ID)
        if replay_number == 0:
            assert current_basket is not None
            assert current_basket.net_realized_pnl == Decimal("13.84062222")
            assert [fill.side for fill in current_fills] == [
                FillSide.BUY,
                FillSide.SELL,
            ]
            first_basket = current_basket
            first_fills = current_fills
        else:
            assert current_basket == first_basket
            assert current_fills == first_fills

    reopened_database = SQLiteDatabase(database_path)
    reopened_database.migrate()
    reopened = SQLiteTradeHistory(reopened_database)
    basket = reopened.get_basket(BASKET_ID)
    fills = reopened.list_fills(BASKET_ID)

    assert basket is not None
    assert basket.basket_id == BASKET_ID
    assert basket.status is BasketStatus.CLOSED
    assert basket.net_realized_pnl == Decimal("13.84062222")
    assert len(fills) == 2
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
    assert fills[0].entry_number == 1
    assert fills[1].entry_number is None


def paper_spot_session(
    market_data: MarketDataConfig,
    preset: RsiStepGridPreset,
) -> PaperSpotSession:
    return PaperSpotSession(
        SessionConfig(
            session_id=SESSION_ID,
            preset_version=preset.version,
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("1000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=4),
            spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
        ),
        market_data,
        SymbolRules(
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        preset,
    )
