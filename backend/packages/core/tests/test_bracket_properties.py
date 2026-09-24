from decimal import Decimal as D

from hypothesis import assume, given
from hypothesis import strategies as st

from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders import (
    Bracket,
    BracketRole,
    Order,
    OrderType,
    OwnerType,
    on_entry_fill,
    on_leg_fill,
    on_position_closed,
)

TP, SL = BracketRole.TAKE_PROFIT, BracketRole.STOP_LOSS

quantities = st.decimals(min_value="0.001", max_value="200", places=3)
prices = st.decimals(min_value="1", max_value="200000", places=2)
sides = st.sampled_from([OrderSide.BUY, OrderSide.SELL])
roles = st.sampled_from([TP, SL])


def entry(quantity: D, side: OrderSide = OrderSide.BUY) -> Order:
    return Order(
        client_order_id="tt1-p1-1",
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        owner_type=OwnerType.BOT,
    )


def leg(role: BracketRole, quantity: D, side: OrderSide, stop_price: D) -> Order:
    return Order(
        client_order_id=f"tt1-p1-{role.lower()}",
        symbol="BTCUSDT",
        side=OrderSide.SELL if side is OrderSide.BUY else OrderSide.BUY,
        order_type=OrderType.TAKE_PROFIT_MARKET if role is TP else OrderType.STOP_MARKET,
        quantity=quantity,
        owner_type=OwnerType.BOT,
        stop_price=stop_price,
        reduce_only=True,
    )


@given(quantity=quantities, fill=quantities, side=sides, stop=prices)
def test_protection_never_covers_more_than_the_entry_has_filled(
    quantity: D, fill: D, side: OrderSide, stop: D
) -> None:
    """FR-ORD-14: the protected quantity is the filled quantity, never the ordered one.

    Protecting more would place a leg larger than the position, which is how a bracket
    turns into a position of its own when it fires.
    """
    assume(fill <= quantity)
    partly = entry(quantity, side).accept().apply_fill(fill, D("60000.0"))

    plan = on_entry_fill(Bracket(entry=partly, stop_loss_price=stop))

    assert all(action.quantity == fill for action in plan.protect)
    assert all(action.quantity <= quantity for action in plan.protect)


@given(quantity=quantities, side=sides, stop=prices)
def test_a_protective_leg_always_closes_the_entry(quantity: D, side: OrderSide, stop: D) -> None:
    """Every leg is sent on the opposite side, so firing can only reduce the position."""
    opened = entry(quantity, side).accept().apply_fill(quantity, D("60000.0"))

    plan = on_entry_fill(Bracket(entry=opened, stop_loss_price=stop, take_profit_price=stop))

    assert all(action.side is not side for action in plan.protect)


@given(quantity=quantities, side=sides, stop=prices)
def test_applying_a_plan_leaves_nothing_more_to_do(quantity: D, side: OrderSide, stop: D) -> None:
    """Placing what the plan asks for reaches a fixed point.

    Without this an engine that re-read its own state after acting would keep replacing
    the same legs at the venue forever.
    """
    opened = entry(quantity, side).accept().apply_fill(quantity, D("60000.0"))
    plan = on_entry_fill(Bracket(entry=opened, stop_loss_price=stop, take_profit_price=stop))

    settled = Bracket(
        entry=opened,
        stop_loss_price=stop,
        take_profit_price=stop,
        stop_loss=leg(SL, quantity, side, stop).accept(),
        take_profit=leg(TP, quantity, side, stop).accept(),
    )

    assert not plan.is_empty  # the legs did need placing
    assert on_entry_fill(settled).is_empty


@given(quantity=quantities, side=sides, stop=prices, filled_leg=roles)
def test_exactly_one_leg_survives_a_leg_fill(
    quantity: D, side: OrderSide, stop: D, filled_leg: BracketRole
) -> None:
    """FR-ORD-15 and R-16: whichever leg fills, the other is always the one cancelled."""
    opened = entry(quantity, side).accept().apply_fill(quantity, D("60000.0"))
    placed = Bracket(
        entry=opened,
        stop_loss_price=stop,
        take_profit_price=stop,
        stop_loss=leg(SL, quantity, side, stop).accept(),
        take_profit=leg(TP, quantity, side, stop).accept(),
    )

    plan = on_leg_fill(placed, filled_leg)

    assert [action.role for action in plan.cancel] == [SL if filled_leg is TP else TP]
    assert not plan.protect


@given(quantity=quantities, fill=quantities, side=sides, stop=prices, filled_leg=roles)
def test_a_protective_fill_never_leaves_the_entry_resting(
    quantity: D, fill: D, side: OrderSide, stop: D, filled_leg: BracketRole
) -> None:
    """C-24: a bracket that has spent its protection leaves nothing able to reopen.

    Whatever is still open after a leg fills could only add to a position no leg covers
    any more, so the plan must account for every open order in the bracket.
    """
    assume(fill < quantity)  # a partial fill, so the entry is still resting
    partly = entry(quantity, side).accept().apply_fill(fill, D("60000.0"))
    placed = Bracket(
        entry=partly,
        stop_loss_price=stop,
        take_profit_price=stop,
        stop_loss=leg(SL, fill, side, stop).accept(),
        take_profit=leg(TP, fill, side, stop).accept(),
    )

    cancelled = {action.client_order_id for action in on_leg_fill(placed, filled_leg).cancel}

    assert partly.is_open  # the premise: there is a remainder that could still fill
    assert partly.client_order_id in cancelled


@given(quantity=quantities, fill=quantities, side=sides, stop=prices)
def test_ending_a_bracket_leaves_nothing_of_it_resting(
    quantity: D, fill: D, side: OrderSide, stop: D
) -> None:
    """R-16 and C-24: nothing of a finished bracket may outlive the position.

    Stated over both the legs and the entry, because either one left behind acts on a
    position that no longer exists: a leg closes what is gone, the entry reopens it.
    """
    assume(fill <= quantity)
    opened = entry(quantity, side).accept().apply_fill(fill, D("60000.0"))
    placed = Bracket(
        entry=opened,
        stop_loss_price=stop,
        take_profit_price=stop,
        stop_loss=leg(SL, fill, side, stop).accept(),
        take_profit=leg(TP, fill, side, stop).accept(),
    )

    plan = on_position_closed(placed)
    cancelled = {action.client_order_id for action in plan.cancel}

    assert {"tt1-p1-stop_loss", "tt1-p1-take_profit"} <= cancelled
    assert opened.is_open == (opened.client_order_id in cancelled)
