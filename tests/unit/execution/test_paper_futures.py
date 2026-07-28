from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.execution.paper_futures import PaperFuturesExecutor
from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.strategy import EntryIntent
from tiewtrade.trading.basket import Basket, BasketCloseReason
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_long_entry_uses_next_open_adverse_slippage_and_target_notional() -> None:
    executor = make_executor(leverage=3, fee_rate="0.001", slippage_bps="10")
    intent = long_intent()
    fill_candle = candle(minute=5, open="100")

    fill = executor.fill_entry(intent, fill_candle)

    assert fill is not None
    assert intent.signal_candle.open_time != fill_candle.open_time
    assert fill.side is PositionSide.LONG
    assert fill.price == Decimal("100.1")
    assert fill.quantity == Decimal("299.7")
    assert fill.fee == fill.price * fill.quantity * Decimal("0.001")
    assert fill.filled_at == fill_candle.open_time


def test_short_entry_uses_adverse_downward_slippage() -> None:
    executor = make_executor(leverage=3, fee_rate="0.001", slippage_bps="10")

    fill = executor.fill_entry(short_intent(), candle(minute=5, open="100"))

    assert fill is not None
    assert fill.side is PositionSide.SHORT
    assert fill.price == Decimal("99.9")
    assert fill.quantity == Decimal("300.3")
    assert fill.fee == Decimal("29.99997")


def test_short_entry_returns_none_when_quantized_price_is_zero() -> None:
    executor = make_executor(slippage_bps="9999.9")

    assert executor.fill_entry(short_intent(), candle(minute=5, open="100")) is None


def test_entry_below_min_notional_returns_none() -> None:
    executor = make_executor(min_notional="50000", leverage=1)

    assert executor.fill_entry(long_intent(), candle(open="100")) is None


def test_entry_rejects_a_candle_from_another_symbol() -> None:
    current = replace(candle(minute=5, open="100"), symbol="ETHUSDT")

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        make_executor().fill_entry(long_intent(), current)


def test_repeating_the_same_entry_produces_the_same_fill_identity() -> None:
    executor = make_executor(leverage=3)
    intent = long_intent()
    current = candle(minute=5, open="100")

    first = executor.fill_entry(intent, current)
    second = executor.fill_entry(intent, current)

    assert first is not None
    assert first == second
    assert first.order_id == "entry:intent-long"
    assert first.fill_id == (
        "paper:00000000-0000-0000-0000-000000000107:entry:intent-long:fill"
    )


def test_long_take_profit_uses_adverse_downward_price() -> None:
    executor = make_executor(slippage_bps="10")
    basket = long_basket(entry_price="100", take_profit="106")
    current = candle(open="105", high="107", low="104")

    fill = executor.fill_take_profit(basket, current)

    assert fill is not None
    assert fill.side is PositionSide.LONG
    assert fill.close_reason is BasketCloseReason.TAKE_PROFIT
    assert fill.price == Decimal("105.8")
    assert fill.quantity == Decimal("2")
    assert fill.fee == Decimal("0.2116")
    assert fill.filled_at == current.close_time
    assert fill.order_id == ("take_profit:00000000-0000-0000-0000-000000000108")
    assert fill.fill_id == (
        "paper:00000000-0000-0000-0000-000000000107:"
        "take_profit:00000000-0000-0000-0000-000000000108:fill"
    )
    assert fill == executor.fill_take_profit(basket, current)


def test_short_take_profit_uses_adverse_upward_price() -> None:
    executor = make_executor(slippage_bps="10")
    basket = short_basket(entry_price="100", take_profit="94")
    current = candle(open="95", high="96", low="93")

    fill = executor.fill_take_profit(basket, current)

    assert fill is not None
    assert fill.side is PositionSide.SHORT
    assert fill.close_reason is BasketCloseReason.TAKE_PROFIT
    assert fill.price == Decimal("94.1")
    assert fill.quantity == Decimal("2")
    assert fill.fee == Decimal("0.1882")
    assert fill.order_id == ("take_profit:00000000-0000-0000-0000-000000000108")
    assert fill.fill_id == (
        "paper:00000000-0000-0000-0000-000000000107:"
        "take_profit:00000000-0000-0000-0000-000000000108:fill"
    )


def test_take_profit_returns_none_until_the_target_is_touched() -> None:
    executor = make_executor()

    assert (
        executor.fill_take_profit(
            long_basket(entry_price="100", take_profit="106"),
            candle(open="100", high="105", low="99"),
        )
        is None
    )
    assert (
        executor.fill_take_profit(
            short_basket(entry_price="100", take_profit="94"),
            candle(open="100", high="101", low="95"),
        )
        is None
    )


def test_take_profit_rejects_a_candle_from_another_symbol() -> None:
    current = replace(
        candle(open="105", high="107", low="104"),
        symbol="ETHUSDT",
    )

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        make_executor().fill_take_profit(
            long_basket(entry_price="100", take_profit="106"),
            current,
        )


def test_liquidation_wins_over_take_profit_and_uses_gap_aware_price() -> None:
    executor = make_executor(slippage_bps="10")
    basket = long_basket(entry_price="100", take_profit="106")
    current = candle(open="70", high="110", low="60")

    liquidation = executor.fill_liquidation(
        basket,
        current,
        liquidation_price=Decimal("80"),
    )
    take_profit = executor.fill_take_profit(basket, current)

    assert liquidation is not None
    assert liquidation.close_reason is BasketCloseReason.LIQUIDATION
    assert liquidation.price == Decimal("69.9")
    assert liquidation.quantity == Decimal("2")
    assert liquidation.fee == Decimal("0.1398")
    assert liquidation.filled_at == current.close_time
    assert liquidation.order_id == ("liquidation:00000000-0000-0000-0000-000000000108")
    assert liquidation.fill_id == (
        "paper:00000000-0000-0000-0000-000000000107:"
        "liquidation:00000000-0000-0000-0000-000000000108:fill"
    )
    assert liquidation == executor.fill_liquidation(
        basket,
        current,
        liquidation_price=Decimal("80"),
    )
    assert take_profit is not None


def test_short_liquidation_uses_gap_aware_adverse_price() -> None:
    executor = make_executor(slippage_bps="10")
    basket = short_basket(entry_price="100", take_profit="94")
    current = candle(open="130", high="140", low="100")

    fill = executor.fill_liquidation(
        basket,
        current,
        liquidation_price=Decimal("120"),
    )

    assert fill is not None
    assert fill.side is PositionSide.SHORT
    assert fill.close_reason is BasketCloseReason.LIQUIDATION
    assert fill.price == Decimal("130.2")
    assert fill.quantity == Decimal("2")
    assert fill.fee == Decimal("0.2604")
    assert fill.order_id == ("liquidation:00000000-0000-0000-0000-000000000108")
    assert fill.fill_id == (
        "paper:00000000-0000-0000-0000-000000000107:"
        "liquidation:00000000-0000-0000-0000-000000000108:fill"
    )
    assert fill == executor.fill_liquidation(
        basket,
        current,
        liquidation_price=Decimal("120"),
    )


def test_liquidation_rejects_a_candle_from_another_symbol() -> None:
    current = replace(
        candle(open="70", high="110", low="60"),
        symbol="ETHUSDT",
    )

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        make_executor().fill_liquidation(
            long_basket(entry_price="100", take_profit="106"),
            current,
            liquidation_price=Decimal("80"),
        )


@pytest.mark.parametrize(
    "liquidation_price",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_liquidation_rejects_invalid_liquidation_price(
    liquidation_price: Decimal,
) -> None:
    executor = make_executor()

    with pytest.raises(ValueError, match="liquidation_price"):
        executor.fill_liquidation(
            long_basket(entry_price="100", take_profit="106"),
            candle(open="100", high="110", low="90"),
            liquidation_price=liquidation_price,
        )


def test_liquidation_returns_none_for_empty_basket() -> None:
    executor = make_executor()
    empty_basket = Basket(
        basket_id=UUID("00000000-0000-0000-0000-000000000108"),
        policy=EntryPolicy(max_entries=2),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.LONG,
    )

    assert (
        executor.fill_liquidation(
            empty_basket,
            candle(open="70", high="110", low="60"),
            liquidation_price=Decimal("80"),
        )
        is None
    )


def test_liquidation_returns_none_until_the_price_is_touched() -> None:
    executor = make_executor()

    assert (
        executor.fill_liquidation(
            long_basket(entry_price="100", take_profit="106"),
            candle(open="100", high="110", low="90"),
            liquidation_price=Decimal("80"),
        )
        is None
    )
    assert (
        executor.fill_liquidation(
            short_basket(entry_price="100", take_profit="94"),
            candle(open="100", high="110", low="90"),
            liquidation_price=Decimal("120"),
        )
        is None
    )


def test_executor_rejects_non_paper_or_non_futures_configuration() -> None:
    session = futures_session()
    rules = symbol_rules()

    with pytest.raises(ValueError, match="Paper Futures"):
        PaperFuturesExecutor(replace(session, trade_mode=TradeMode.LIVE), rules)

    spot_session = SessionConfig(
        session_id=session.session_id,
        preset_version=session.preset_version,
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=session.available_capital,
        fee_rate=session.fee_rate,
        slippage_bps=session.slippage_bps,
        entry_policy=session.entry_policy,
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.8")),
    )
    with pytest.raises(ValueError, match="Paper Futures"):
        PaperFuturesExecutor(spot_session, rules)


def make_executor(
    *,
    leverage: int = 1,
    fee_rate: str = "0.001",
    min_notional: str = "5",
    slippage_bps: str = "0",
) -> PaperFuturesExecutor:
    return PaperFuturesExecutor(
        futures_session(
            leverage=leverage,
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
        ),
        symbol_rules(min_notional=min_notional),
    )


def futures_session(
    *, leverage: int = 1, fee_rate: str = "0.001", slippage_bps: str = "0"
) -> SessionConfig:
    return SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000107"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.FUTURES,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("40000"),
        fee_rate=Decimal(fee_rate),
        slippage_bps=Decimal(slippage_bps),
        entry_policy=EntryPolicy(max_entries=2),
        spot_policy=None,
        futures_policy=FuturesTradingPolicy.v1(leverage=leverage),
    )


def symbol_rules(*, min_notional: str = "5") -> SymbolRules:
    return SymbolRules(
        symbol="BTCUSDT",
        tick_size=Decimal("0.1"),
        step_size=Decimal("0.1"),
        min_notional=Decimal(min_notional),
    )


def candle(
    *,
    open: str,
    high: str | None = None,
    low: str | None = None,
    minute: int = 0,
) -> Candle:
    open_price = Decimal(open)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=open_price,
        high=Decimal(high) if high is not None else open_price,
        low=Decimal(low) if low is not None else open_price,
        close=open_price,
        volume=Decimal("1"),
    )


def long_intent() -> EntryIntent:
    return entry_intent(PositionSide.LONG)


def short_intent() -> EntryIntent:
    return entry_intent(PositionSide.SHORT)


def entry_intent(side: PositionSide) -> EntryIntent:
    session = futures_session()
    return EntryIntent(
        intent_id=f"intent-{side}",
        session_id=session.session_id,
        preset_version=session.preset_version,
        entry_number=1,
        signal_candle=candle(open="100"),
        atr=Decimal("2"),
        side=side,
    )


def long_basket(*, entry_price: str, take_profit: str) -> Basket:
    return basket(
        position_side=PositionSide.LONG,
        entry_price=entry_price,
        take_profit=take_profit,
    )


def short_basket(*, entry_price: str, take_profit: str) -> Basket:
    return basket(
        position_side=PositionSide.SHORT,
        entry_price=entry_price,
        take_profit=take_profit,
    )


def basket(
    *, position_side: PositionSide, entry_price: str, take_profit: str
) -> Basket:
    result = Basket(
        basket_id=UUID("00000000-0000-0000-0000-000000000108"),
        policy=EntryPolicy(max_entries=2),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=position_side,
    )
    result.add_entry(
        price=Decimal(entry_price),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
        position_side=position_side,
    )
    assert result.take_profit_price == Decimal(take_profit)
    return result
