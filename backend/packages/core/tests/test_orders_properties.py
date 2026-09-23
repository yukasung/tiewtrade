from decimal import Decimal as D

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders import (
    MAX_LENGTH,
    Order,
    OrderStatus,
    OrderType,
    OwnerType,
    build_client_order_id,
    is_platform_client_order_id,
)

quantities = st.decimals(min_value="0.001", max_value="200", places=3)
prices = st.decimals(min_value="1", max_value="200000", places=2)
parts = st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=8)
sequences = st.integers(min_value=0, max_value=10**6)


def market_order(quantity: D) -> Order:
    return Order(
        client_order_id="tt1-p1-1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        owner_type=OwnerType.MANUAL,
    )


# --- Client Order ID ----------------------------------------------------


@given(prefix=parts, portfolio_ref=parts, sequence=sequences)
def test_a_built_id_is_always_recognised_as_ours(
    prefix: str, portfolio_ref: str, sequence: int
) -> None:
    built = build_client_order_id(prefix, portfolio_ref, sequence)

    assert is_platform_client_order_id(built, prefix)
    assert len(built) <= MAX_LENGTH


@given(prefix=parts, other=parts, portfolio_ref=parts, sequence=sequences)
def test_an_id_is_never_recognised_under_a_different_prefix(
    prefix: str, other: str, portfolio_ref: str, sequence: int
) -> None:
    """D-14 depends on this: mistaking a user's own order for ours corrupts ownership."""
    assume(prefix != other)
    built = build_client_order_id(prefix, portfolio_ref, sequence)

    assert not is_platform_client_order_id(built, other)


@given(prefix=parts, portfolio_ref=parts, a=sequences, b=sequences)
def test_different_sequences_give_different_ids(
    prefix: str, portfolio_ref: str, a: int, b: int
) -> None:
    assume(a != b)

    assert build_client_order_id(prefix, portfolio_ref, a) != build_client_order_id(
        prefix, portfolio_ref, b
    )


# --- Order lifecycle ----------------------------------------------------


@given(quantity=quantities, price=prices)
def test_filled_and_remaining_always_add_up_to_the_order(quantity: D, price: D) -> None:
    fresh = market_order(quantity)
    assert fresh.filled_quantity + fresh.remaining_quantity == quantity

    part = min(quantity / 2, quantity).quantize(D("0.000001"))
    assume(part > 0)
    partial = fresh.apply_fill(part, price)

    assert partial.filled_quantity + partial.remaining_quantity == quantity


@given(quantity=quantities, price=prices)
def test_one_fill_at_a_single_price_averages_to_that_price(quantity: D, price: D) -> None:
    filled = market_order(quantity).apply_fill(quantity, price)

    assert filled.average_fill_price == price
    assert filled.status is OrderStatus.FILLED


@given(
    quantity=quantities,
    first=prices,
    second=prices,
    split=st.decimals(min_value="0.1", max_value="0.9", places=2),
)
def test_the_average_never_leaves_the_range_of_its_fills(
    quantity: D, first: D, second: D, split: D
) -> None:
    """A weighted average of two prices lies between them, whatever the split."""
    head = (quantity * split).quantize(D("0.000001"))
    assume(0 < head < quantity)

    result = market_order(quantity).apply_fill(head, first).apply_fill(quantity - head, second)

    assert result.average_fill_price is not None
    assert min(first, second) <= result.average_fill_price <= max(first, second)


@given(quantity=quantities, price=prices)
def test_filling_in_two_steps_reaches_the_same_place_as_one(quantity: D, price: D) -> None:
    """At a single price the path does not matter, so splitting a fill cannot drift."""
    head = (quantity / 2).quantize(D("0.000001"))
    assume(0 < head < quantity)

    once = market_order(quantity).apply_fill(quantity, price)
    twice = market_order(quantity).apply_fill(head, price).apply_fill(quantity - head, price)

    assert once.filled_quantity == twice.filled_quantity
    assert once.average_fill_price == twice.average_fill_price
    assert once.status is twice.status


@given(quantity=quantities, price=prices)
def test_a_transition_never_mutates_the_order_it_came_from(quantity: D, price: D) -> None:
    fresh = market_order(quantity)
    before = (fresh.status, fresh.filled_quantity, fresh.average_fill_price)

    fresh.apply_fill(quantity, price)

    assert (fresh.status, fresh.filled_quantity, fresh.average_fill_price) == before


@given(quantity=quantities, price=prices, overfill=quantities)
def test_an_order_can_never_fill_beyond_its_quantity(quantity: D, price: D, overfill: D) -> None:
    assume(overfill > quantity)

    with pytest.raises(ValueError, match="cannot exceed the remaining quantity"):
        market_order(quantity).apply_fill(overfill, price)


@given(quantity=quantities, price=prices)
def test_a_terminal_order_refuses_every_transition(quantity: D, price: D) -> None:
    for done in (
        market_order(quantity).apply_fill(quantity, price),
        market_order(quantity).cancel(),
        market_order(quantity).reject("no"),
        market_order(quantity).expire(),
    ):
        assert done.status.is_terminal
        assert not done.is_open
        for attempt in (
            lambda o: o.accept(),
            lambda o: o.cancel(),
            lambda o: o.expire(),
            lambda o: o.apply_fill(quantity, price),
        ):
            with pytest.raises(ValueError, match="cannot move an order"):
                attempt(done)


@given(quantity=quantities)
def test_open_and_terminal_are_exact_opposites(quantity: D) -> None:
    for status in OrderStatus:
        assert status.is_open is not status.is_terminal
