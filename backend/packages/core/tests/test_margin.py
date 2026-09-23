from collections.abc import Callable
from decimal import Decimal as D

import pytest

from tiewtrade_core.margin import (
    FuturesExposure,
    MarginState,
    PendingOrder,
    assuming_price,
    available_balance,
    cross_margin_state,
    isolated_margin_state,
    liquidation_price,
    margin_requirement,
    open_loss,
    order_margin,
)
from tiewtrade_core.market import LeverageBrackets, OrderSide

MarginGap = Callable[..., D]

TOLERANCE = D("1e-30")


# --- exposure ---------------------------------------------------------------


def test_exposure_values(brackets: LeverageBrackets) -> None:
    short = FuturesExposure(D(-2), D(100), D(90), 10, brackets)
    assert short.notional == D(180)
    assert short.unrealized_pnl == D(20)
    assert short.initial_margin == D(18)
    assert short.maintenance_margin == D(180) * D("0.004")


# --- liquidation condition (calculation spec §2.4) --------------------------


@pytest.mark.parametrize(
    ("balance", "maintenance", "liquidatable"),
    [
        (D(10), D(5), False),
        (D(5), D(5), True),  # boundary: equal is liquidated (Verify C-13)
        (D(0), D(5), True),
        (D(-3), D(5), True),  # insolvent accounts cannot escape the condition
        (D(0), D(0), False),  # no position
    ],
)
def test_liquidation_condition(balance: D, maintenance: D, liquidatable: bool) -> None:
    assert MarginState(balance, maintenance).is_liquidatable is liquidatable


def test_margin_ratio_display() -> None:
    assert MarginState(D(10), D(5)).margin_ratio.value == D("0.5")
    insolvent = MarginState(D(-1), D(5)).margin_ratio
    assert insolvent.value is None
    assert insolvent.insolvent is True
    none = MarginState(D(10), D(0)).margin_ratio
    assert none.value is None
    assert none.insolvent is False


def test_cross_state_sums_positions(brackets: LeverageBrackets) -> None:
    long = FuturesExposure(D(1), D(100), D(110), 10, brackets)
    short = FuturesExposure(D(-1), D(50), D(60), 10, brackets)
    state = cross_margin_state(D(100), [long, short])
    assert state.margin_balance == D(100) + D(10) - D(10)
    assert state.maintenance_margin == long.maintenance_margin + short.maintenance_margin


def test_isolated_state(brackets: LeverageBrackets) -> None:
    long = FuturesExposure(D(1), D(100), D(95), 10, brackets)
    state = isolated_margin_state(D(10), long)
    assert state.margin_balance == D(5)


# --- liquidation price (calculation spec §2.5) --------------------------------


def test_isolated_long_liquidation_price(brackets: LeverageBrackets, margin_gap: MarginGap) -> None:
    price = liquidation_price(D(1), D(100), D(10), brackets)
    assert price == D(-90) / D("-0.996")
    assert price is not None
    assert abs(margin_gap(price, D(1), D(100), D(10))) < TOLERANCE


def test_isolated_short_liquidation_price(
    brackets: LeverageBrackets, margin_gap: MarginGap
) -> None:
    price = liquidation_price(D(-1), D(100), D(10), brackets)
    assert price == D(110) / D("1.004")
    assert price is not None
    assert abs(margin_gap(price, D(-1), D(100), D(10))) < TOLERANCE


def test_long_without_liquidation_price_returns_none(brackets: LeverageBrackets) -> None:
    # Fully collateralized long: price would have to reach zero.
    assert liquidation_price(D(1), D(100), D(100), brackets) is None


def test_flat_position_has_no_liquidation_price(brackets: LeverageBrackets) -> None:
    assert liquidation_price(D(0), D(100), D(10), brackets) is None


def test_bracket_is_chosen_at_the_liquidation_notional(
    brackets: LeverageBrackets, margin_gap: MarginGap
) -> None:
    # Notional at entry is in bracket 3, at the liquidation price it falls into bracket 2.
    quantity, entry, wallet = D(3), D(100_000), D(60_000)
    price = liquidation_price(quantity, entry, wallet, brackets)
    assert price is not None
    assert brackets.for_notional(quantity * entry).bracket == 3
    assert brackets.for_notional(quantity * price).bracket == 2
    assert abs(margin_gap(price, quantity, entry, wallet)) < TOLERANCE


def test_solution_in_a_lower_bracket_is_found(
    brackets: LeverageBrackets, margin_gap: MarginGap
) -> None:
    # Regression (Codex review): notional at entry is in bracket 3, whose formula gives a
    # negative price, but the real solution lies in bracket 1 (~1004.016064).
    quantity, entry, wallet = D(1), D(300_000), D(299_000)
    price = liquidation_price(quantity, entry, wallet, brackets)
    assert price == D(-1000) / D("-0.996")
    assert brackets.for_notional(quantity * price).bracket == 1
    assert abs(margin_gap(price, quantity, entry, wallet)) < TOLERANCE


def test_cross_liquidation_price_can_be_above_entry_for_a_long(
    brackets: LeverageBrackets, margin_gap: MarginGap
) -> None:
    # Losses on other cross positions push the long's liquidation price above its entry.
    price = liquidation_price(
        D(1),
        D(100),
        D(100),
        brackets,
        other_maintenance_margin=D(5),
        other_unrealized_pnl=D(-100),
    )
    assert price is not None
    assert price > D(100)
    residual = margin_gap(price, D(1), D(100), D(100), D(5), D(-100))
    assert abs(residual) < TOLERANCE


# --- margin requirement, order margin, available balance (§2.2, §2.7) --------


def test_assuming_price() -> None:
    kwargs = {"last_price": D(100), "mark_price": D(100)}
    assert assuming_price(OrderSide.BUY, limit_price=D(99), **kwargs) == D(99)
    assert assuming_price(OrderSide.SELL, limit_price=D(100), **kwargs) == D("100.15")
    assert assuming_price(OrderSide.SELL, limit_price=D(120), **kwargs) == D(120)
    assert assuming_price(OrderSide.BUY, limit_price=None, **kwargs) == D("100.15")


@pytest.mark.parametrize(
    ("side", "order_price", "expected"),
    [
        (OrderSide.BUY, D(101), D(1)),  # buying above mark
        (OrderSide.BUY, D(99), D(0)),
        (OrderSide.SELL, D(99), D(1)),  # selling below mark
        (OrderSide.SELL, D(101), D(0)),
    ],
)
def test_open_loss(side: OrderSide, order_price: D, expected: D) -> None:
    assert open_loss(side, D(1), D(100), order_price) == expected


def test_margin_requirement_matches_binance_documentation_example() -> None:
    # 10,000 USDT long, buy 0.1 @ 19,000 and sell 0.1 @ 22,000, 2x -> 5,950 USDT
    orders = [
        PendingOrder(OrderSide.BUY, D("0.1"), D(19_000), D(19_000)),
        PendingOrder(OrderSide.SELL, D("0.1"), D(22_000), D(22_000)),
    ]
    assert margin_requirement(D("0.5"), D(20_000), 2, orders) == D(5_950)


def test_closing_order_needs_no_extra_margin() -> None:
    # Review case: long 1 @ MP 100, 10x, sell 1 @ 100 to close -> frozen stays 10.
    close = PendingOrder(OrderSide.SELL, D(1), D("100.15"), D(100))
    assert margin_requirement(D(1), D(100), 10, [close]) == D(10)
    assert order_margin(D(1), D(100), 10, [], close) == D(0)


def test_increasing_order_needs_incremental_margin() -> None:
    add = PendingOrder(OrderSide.BUY, D(1), D(100), D(100))
    assert order_margin(D(1), D(100), 10, [], add) == D(10)


def test_available_balance_ignores_unrealized_profit_until_verified() -> None:
    assert available_balance(D(100), D(50), D(30)) == D(70)
    assert available_balance(D(100), D(-20), D(30)) == D(50)
    assert available_balance(D(10), D(-20), D(30)) == D(0)
