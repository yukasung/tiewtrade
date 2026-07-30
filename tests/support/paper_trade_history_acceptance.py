from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from tiewtrade.application.paper_futures_session import (
    PaperFuturesSession,
    PaperFuturesSessionSnapshot,
)
from tiewtrade.application.paper_spot_session import PaperSpotSession
from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceCoordinator,
)
from tiewtrade.integrations.sqlite.paper_futures_history import (
    PaperFuturesHistoryContext,
    PaperFuturesSQLiteHistory,
)
from tiewtrade.integrations.sqlite.paper_spot_history import (
    PaperSpotHistoryContext,
    PaperSpotSQLiteHistory,
)
from tiewtrade.integrations.sqlite.persistent_paper_futures_session import (
    create_persistent_paper_futures_session,
)
from tiewtrade.integrations.sqlite.persistent_paper_spot_session import (
    create_persistent_paper_spot_session,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.replay.csv_candles import load_candles_csv
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules
from tiewtrade.trading.trade_history import BasketResult, BasketStatus, TradeFill

SPOT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000401")
FUTURES_SESSION_ID = UUID("00000000-0000-0000-0000-000000000402")
OPEN_SPOT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000403")

_MARKET_DATA = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
_PRESET = RsiStepGridPreset.v1()
_FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "btcusdt_5m_tracer.csv"


@dataclass(frozen=True, slots=True)
class OpenSpotHistory:
    basket: BasketResult
    fill: TradeFill


def build_spot_session(session_id: UUID) -> PaperSpotSession:
    return PaperSpotSession(
        SessionConfig(
            session_id=session_id,
            preset_version=_PRESET.version,
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("1000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=4),
            spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
        ),
        _MARKET_DATA,
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        _PRESET,
    )


def build_futures_session(session_id: UUID) -> PaperFuturesSession:
    return PaperFuturesSession(
        SessionConfig(
            session_id=session_id,
            preset_version=_PRESET.version,
            market_type=MarketType.FUTURES,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("200000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=10),
            spot_policy=None,
            futures_policy=FuturesTradingPolicy.v1(leverage=3),
        ),
        _MARKET_DATA,
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        _PRESET,
    )


def spot_history(
    session_id: UUID,
    store: SQLiteTradeHistory,
) -> PaperSpotSQLiteHistory:
    return PaperSpotSQLiteHistory(
        PaperSpotHistoryContext(
            session_id=session_id,
            symbol=_MARKET_DATA.symbol,
            timeframe=_MARKET_DATA.timeframe,
            preset_version=_PRESET.version,
            commission_asset="USDT",
        ),
        store,
    )


def futures_history(
    session_id: UUID,
    store: SQLiteTradeHistory,
) -> PaperFuturesSQLiteHistory:
    return PaperFuturesSQLiteHistory(
        PaperFuturesHistoryContext(
            session_id=session_id,
            symbol=_MARKET_DATA.symbol,
            timeframe=_MARKET_DATA.timeframe,
            preset_version=_PRESET.version,
            commission_asset="USDT",
            leverage=3,
        ),
        store,
    )


def spot_candles() -> tuple[Candle, ...]:
    return tuple(load_candles_csv(_FIXTURE_PATH, _MARKET_DATA))


def futures_candles() -> tuple[Candle, ...]:
    candles: list[Candle] = []
    close = Decimal("100")
    for index in range(15):
        candles.append(_futures_candle(index, close=close))
        close -= Decimal("1")
    for index in range(15, 40):
        close += Decimal("1")
        candles.append(_futures_candle(index, close=close))
    return tuple(candles)


def run_closed_spot(store: SQLiteTradeHistory) -> UUID:
    persistent = create_persistent_paper_spot_session(
        build_spot_session(SPOT_SESSION_ID),
        spot_history(SPOT_SESSION_ID, store),
    )
    for candle in spot_candles():
        snapshot = persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )
        assert snapshot.persistence_state is PersistenceState.READY
        if snapshot.session.closed_basket is not None:
            return snapshot.session.closed_basket.basket_id
    raise AssertionError("deterministic Paper Spot candles did not close a Basket")


def run_spot_until_entry(store: SQLiteTradeHistory) -> OpenSpotHistory:
    persistent = create_persistent_paper_spot_session(
        build_spot_session(OPEN_SPOT_SESSION_ID),
        spot_history(OPEN_SPOT_SESSION_ID, store),
    )
    for candle in spot_candles():
        snapshot = persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )
        assert snapshot.persistence_state is PersistenceState.READY
        if snapshot.session.entry_fill is None:
            continue

        basket_id = snapshot.session.basket_id
        assert basket_id is not None
        basket = store.get_basket(basket_id)
        assert basket is not None
        fills = store.list_fills(basket_id)
        assert basket.status is BasketStatus.OPEN
        assert len(fills) == 1
        return OpenSpotHistory(basket=basket, fill=fills[0])
    raise AssertionError(
        "deterministic Paper Spot candles did not persist an Entry Fill"
    )


def run_closed_futures(store: SQLiteTradeHistory) -> UUID:
    persistent: SessionPersistenceCoordinator[PaperFuturesSessionSnapshot] = (
        create_persistent_paper_futures_session(
            build_futures_session(FUTURES_SESSION_ID),
            futures_history(FUTURES_SESSION_ID, store),
        )
    )
    for candle in futures_candles():
        snapshot = persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )
        assert snapshot.persistence_state is PersistenceState.READY
        if snapshot.session.closed_basket is not None:
            return snapshot.session.closed_basket.basket_id
    raise AssertionError("deterministic Paper Futures candles did not close a Basket")


def _futures_candle(index: int, *, close: Decimal) -> Candle:
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
