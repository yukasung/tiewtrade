from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.execution.paper_spot import PaperSpotExecutor
from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import EntryIntent
from tiewtrade.trading.basket import Basket
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
    assert fill.price == Decimal("101.49")
    assert fill.quantity == Decimal("1.477")
    assert fill.fee == Decimal("0.14990073")
    assert fill.filled_at == fill_candle.open_time


def test_entry_fill_rounds_buy_slippage_up_to_the_next_tick() -> None:
    session = SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("0.5"),
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
    fill_candle = candle_at(5, open_price="100", high="102", low="99", close="101")

    fill = executor.fill_entry(intent(session, signal_candle), fill_candle)

    assert fill is not None
    assert fill.price == Decimal("100.01")


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


def test_take_profit_target_touch_uses_sell_floor_price_and_exact_fee() -> None:
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
    rules = SymbolRules(
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )
    basket = Basket(EntryPolicy(max_entries=4), Decimal("1"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("1"),
        tick_size=rules.tick_size,
    )
    touch_candle = candle_at(5, open_price="100", high="101", low="99", close="100")

    fill = PaperSpotExecutor(session, rules).fill_take_profit(basket, touch_candle)

    assert fill is not None
    assert fill.price == Decimal("100.74")
    assert fill.quantity == Decimal("2")
    assert fill.fee == Decimal("0.20148")
    assert fill.filled_at == touch_candle.close_time


def test_take_profit_rejects_a_non_positive_sell_price_after_quantization() -> None:
    session = SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("9999.999"),
        entry_policy=EntryPolicy(max_entries=4),
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    )
    rules = SymbolRules(
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("0.001"),
    )
    basket = Basket(EntryPolicy(max_entries=4), Decimal("1"))
    basket.add_entry(
        price=Decimal("0.01"),
        quantity=Decimal("1"),
        fee=Decimal("0"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("0"),
        tick_size=rules.tick_size,
    )
    touch_candle = candle_at(5, open_price="1", high="1", low="0.01", close="1")

    assert (
        PaperSpotExecutor(session, rules).fill_take_profit(basket, touch_candle) is None
    )


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
