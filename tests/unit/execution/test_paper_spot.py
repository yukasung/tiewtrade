from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.execution.paper_spot import PaperSpotExecutor
from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import EntryIntent
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import (
    MarketType,
    SessionConfig,
    TradeMode,
)
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_entry_fill_uses_session_capital_costs_and_symbol_rules() -> None:
    session = SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("25"),
        entry_policy=EntryPolicy(max_entries=4),
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    )
    executor = PaperSpotExecutor(
        session,
        SymbolRules(
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
    )
    signal_candle = candle_at(0, open_price="100", high="102", low="99", close="101")
    fill_candle = candle_at(5, open_price="101.23", high="103", low="100", close="102")

    fill = executor.fill_entry(intent(session, signal_candle), fill_candle)

    assert fill is not None
    assert fill.price == Decimal("101.48")
    assert fill.quantity == Decimal("1.478")
    assert fill.fee == Decimal("0.14998744")
    assert fill.filled_at == fill_candle.open_time


def test_entry_fill_rejects_quantity_below_minimum_notional() -> None:
    session = SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("100"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("0"),
        entry_policy=EntryPolicy(max_entries=4),
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    )
    executor = PaperSpotExecutor(
        session,
        SymbolRules(
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("20"),
        ),
    )
    signal_candle = candle_at(0, open_price="100", high="102", low="99", close="101")
    fill_candle = candle_at(5, open_price="100", high="102", low="99", close="101")

    assert executor.fill_entry(intent(session, signal_candle), fill_candle) is None


def candle_at(
    minute: int,
    *,
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def intent(session: SessionConfig, signal_candle: Candle) -> EntryIntent:
    return EntryIntent(
        intent_id="intent-1",
        session_id=session.session_id,
        preset_version=RsiStepGridPreset.v1().version,
        entry_number=1,
        signal_candle=signal_candle,
        atr=Decimal("2"),
    )
