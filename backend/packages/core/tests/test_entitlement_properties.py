from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade_core.entitlement import (
    FuturesSymbolExposure,
    SpotSymbolExposure,
    effective_max_leverage,
    open_notional,
    projected_notional,
    within_leverage,
    within_limit,
)
from tiewtrade_core.margin import PendingOrder
from tiewtrade_core.market import LeverageBrackets, OrderSide

quantities = st.decimals(min_value="0", max_value="500", places=3)
prices = st.decimals(min_value="1", max_value="90000", places=2)
amounts = st.decimals(min_value="0", max_value="1000000", places=2)
signs = st.sampled_from([D(1), D(-1)])
sides = st.sampled_from([OrderSide.BUY, OrderSide.SELL])
leverages = st.integers(min_value=1, max_value=125)


@st.composite
def futures_exposures(draw: st.DrawFn) -> FuturesSymbolExposure:
    price = draw(prices)
    orders = tuple(
        PendingOrder(
            side=draw(sides),
            quantity=draw(st.decimals(min_value="0.001", max_value="50", places=3)),
            assuming_price=price,
            order_price=price,
        )
        for _ in range(draw(st.integers(min_value=0, max_value=3)))
    )
    return FuturesSymbolExposure(draw(signs) * draw(quantities), price, orders)


@given(exposures=st.lists(futures_exposures(), max_size=5))
def test_notional_is_never_negative(exposures: list[FuturesSymbolExposure]) -> None:
    """It is a size. A short must not offset a long, or a Workspace could hide exposure
    from the limit by holding both sides."""
    assert open_notional(futures=exposures) >= 0
    assert projected_notional(futures=exposures) >= 0


@given(exposures=st.lists(futures_exposures(), min_size=1, max_size=5))
def test_reserving_for_orders_never_lowers_the_notional(
    exposures: list[FuturesSymbolExposure],
) -> None:
    """C-08 reserves headroom, so counting orders can only ever ask for more room.

    If it could ask for less, a User could free up limit by placing an order — the exact
    thing the reservation exists to prevent.
    """
    assert projected_notional(futures=exposures) >= open_notional(futures=exposures)


@given(
    quantity=quantities,
    sign=signs,
    price=prices,
    holding=quantities,
    last=prices,
    buys=amounts,
)
def test_a_workspace_totals_its_parts(
    quantity: D, sign: D, price: D, holding: D, last: D, buys: D
) -> None:
    """The Workspace number is the sum of the symbols, with nothing lost in between."""
    futures = FuturesSymbolExposure(sign * quantity, price)
    spot = SpotSymbolExposure(holding, last, resting_buy_value=buys)

    assert projected_notional(futures=[futures], spot=[spot]) == (
        futures.projected_notional + spot.projected_notional
    )


@given(limit=amounts, before=amounts, after=amounts)
def test_an_order_that_does_not_raise_the_notional_is_always_allowed(
    limit: D, before: D, after: D
) -> None:
    """An order that leaves the number where it is never opens or adds (FR-PLN-05)."""
    assert within_limit(limit, projected_before=before, projected_after=min(before, after))


@given(limit=amounts, before=amounts, after=amounts)
def test_a_reducing_order_passes_whatever_the_numbers_say(limit: D, before: D, after: D) -> None:
    """§5.2: reducing or closing passes unconditionally.

    Stated over every combination, including the ones where the projected notional rises,
    because a resting protective leg priced away from the mark does exactly that.
    """
    assert within_limit(limit, projected_before=before, projected_after=after, reduces=True)


@given(limit=amounts, before=amounts, after=amounts)
def test_nothing_may_end_over_the_limit_except_by_not_adding_to_it(
    limit: D, before: D, after: D
) -> None:
    """For an order that opens or adds, the only way past the limit is not pushing it up."""
    allowed = within_limit(limit, projected_before=before, projected_after=after)

    if allowed and after > limit:
        assert after <= before


@given(plan=leverages, notional=amounts)
def test_effective_leverage_never_exceeds_either_cap(
    brackets: LeverageBrackets, plan: int, notional: D
) -> None:
    """§5.3 is a min of two caps, so it is bounded by both and never below 1."""
    effective = effective_max_leverage(plan, brackets, notional)

    assert 1 <= effective <= plan
    assert effective <= brackets.for_notional(notional).max_leverage


@given(plan=leverages, notional=amounts, leverage=leverages)
def test_within_leverage_agrees_with_the_cap_it_is_built_on(
    brackets: LeverageBrackets, plan: int, notional: D, leverage: int
) -> None:
    allowed = within_leverage(leverage, plan, brackets, notional)

    assert allowed == (leverage <= effective_max_leverage(plan, brackets, notional))


@given(sign=signs, quantity=st.decimals(min_value="0.001", max_value="500", places=3), price=prices)
def test_direction_does_not_change_exposure(sign: D, quantity: D, price: D) -> None:
    long = FuturesSymbolExposure(quantity, price)
    short = FuturesSymbolExposure(-quantity, price)

    assert long.open_notional == short.open_notional


@given(holding=st.decimals(min_value="-500", max_value="-0.001", places=3), last=prices)
def test_a_negative_spot_holding_is_refused(holding: D, last: D) -> None:
    """Spot is Long only (D-10)."""
    with pytest.raises(ValueError, match="cannot be negative"):
        SpotSymbolExposure(holding, last)
