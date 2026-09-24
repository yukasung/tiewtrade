from decimal import Decimal as D

import pytest

from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders import (
    Bracket,
    BracketRole,
    Order,
    OrderType,
    OwnerType,
    on_entry_fill,
    on_entry_finished,
    on_leg_fill,
    on_position_closed,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL
TP, SL = BracketRole.TAKE_PROFIT, BracketRole.STOP_LOSS


def entry_order(**changes: object) -> Order:
    fields: dict[str, object] = {
        "client_order_id": "tt1-p1-1",
        "symbol": "BTCUSDT",
        "side": BUY,
        "order_type": OrderType.LIMIT,
        "quantity": D("1.0"),
        "owner_type": OwnerType.BOT,
        "price": D("60000.0"),
    }
    fields.update(changes)
    return Order(**fields)  # type: ignore[arg-type]


def leg_order(role: BracketRole, **changes: object) -> Order:
    """A protective leg as the Order Manager would have placed it."""
    fields: dict[str, object] = {
        "client_order_id": f"tt1-p1-{role.lower()}",
        "symbol": "BTCUSDT",
        "side": SELL,
        "order_type": (OrderType.TAKE_PROFIT_MARKET if role is TP else OrderType.STOP_MARKET),
        "quantity": D("1.0"),
        "owner_type": OwnerType.BOT,
        "stop_price": D("62000.0") if role is TP else D("58000.0"),
        "reduce_only": True,
    }
    fields.update(changes)
    return Order(**fields)  # type: ignore[arg-type]


def bracket(**changes: object) -> Bracket:
    fields: dict[str, object] = {
        "entry": entry_order(),
        "take_profit_price": D("62000.0"),
        "stop_loss_price": D("58000.0"),
    }
    fields.update(changes)
    return Bracket(**fields)  # type: ignore[arg-type]


def filled(order: Order, quantity: str) -> Order:
    return order.accept().apply_fill(D(quantity), D("60000.0"))


# --- construction --------------------------------------------------------


def test_a_bracket_must_request_some_protection() -> None:
    """An entry with neither leg is an ordinary order, not a bracket."""
    with pytest.raises(ValueError, match="must request a take profit"):
        Bracket(entry=entry_order())


@pytest.mark.parametrize("role", [TP, SL])
def test_one_leg_alone_is_a_valid_bracket(role: BracketRole) -> None:
    only = {"take_profit_price": D("62000.0")} if role is TP else {"stop_loss_price": D("58000.0")}

    assert Bracket(entry=entry_order(), **only).price_for(role) is not None  # type: ignore[arg-type]


@pytest.mark.parametrize("price", ["0", "-1"])
def test_a_protective_price_must_be_positive(price: str) -> None:
    with pytest.raises(ValueError, match="price must be positive"):
        Bracket(entry=entry_order(), stop_loss_price=D(price))


def test_a_placed_leg_needs_the_price_it_was_placed_for() -> None:
    """Otherwise a resize would have no price to send."""
    with pytest.raises(ValueError, match="without a requested price"):
        Bracket(
            entry=entry_order(),
            stop_loss_price=D("58000.0"),
            take_profit=leg_order(TP, quantity=D("1.0")),
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"symbol": "ETHUSDT"}, "same symbol"),
        ({"side": BUY}, "must close the entry"),
        ({"reduce_only": False}, "must be reduce-only"),
        ({"order_type": OrderType.MARKET, "stop_price": None}, "must be a STOP_MARKET"),
        ({"quantity": D("2.0")}, "cannot cover more than the entry"),
    ],
)
def test_a_leg_that_cannot_close_the_entry_is_refused(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        bracket(stop_loss=leg_order(SL, **changes))


def test_the_closing_side_is_the_opposite_of_the_entry() -> None:
    assert bracket().closing_side is SELL
    assert bracket(entry=entry_order(side=SELL)).closing_side is BUY


# --- FR-ORD-14: protection starts at the first fill ----------------------


def test_nothing_is_protected_before_the_entry_fills() -> None:
    """Protection covers filled quantity only, so a resting entry has none."""
    with pytest.raises(ValueError, match="nothing to protect"):
        on_entry_fill(bracket(entry=entry_order().accept()))


def test_the_first_fill_places_both_legs_for_the_filled_quantity_only() -> None:
    plan = on_entry_fill(bracket(entry=filled(entry_order(), "0.4")))

    assert [leg.role for leg in plan.protect] == [TP, SL]
    assert {leg.quantity for leg in plan.protect} == {D("0.4")}  # not the full 1.0
    assert all(leg.replaces is None for leg in plan.protect)  # nothing to supersede yet
    assert not plan.cancel


def test_a_placed_leg_is_sent_reduce_only_on_the_closing_side() -> None:
    plan = on_entry_fill(bracket(entry=filled(entry_order(), "0.4")))
    stop = next(leg for leg in plan.protect if leg.role is SL)

    assert stop.side is SELL
    assert stop.stop_price == D("58000.0")
    assert stop.order_type is OrderType.STOP_MARKET


def test_only_the_requested_leg_is_placed() -> None:
    plan = on_entry_fill(Bracket(entry=filled(entry_order(), "0.4"), stop_loss_price=D("58000.0")))

    assert [leg.role for leg in plan.protect] == [SL]


def test_a_further_fill_resizes_both_legs_to_the_cumulative_quantity() -> None:
    """FR-ORD-14: every additional entry fill re-sizes the protection."""
    entry = filled(entry_order(), "0.4").apply_fill(D("0.3"), D("60000.0"))
    placed = bracket(
        entry=entry,
        take_profit=leg_order(TP, quantity=D("0.4")).accept(),
        stop_loss=leg_order(SL, quantity=D("0.4")).accept(),
    )

    plan = on_entry_fill(placed)

    assert {leg.quantity for leg in plan.protect} == {D("0.7")}
    assert [leg.replaces for leg in plan.protect] == [
        "tt1-p1-take_profit",
        "tt1-p1-stop_loss",
    ]


def test_a_resize_is_one_action_so_the_position_is_never_left_unprotected() -> None:
    """A cancel followed by a place would describe a gap FR-ORD-14 does not allow."""
    entry = filled(entry_order(), "0.4").apply_fill(D("0.3"), D("60000.0"))

    lone = Bracket(
        entry=entry,
        stop_loss_price=D("58000.0"),
        stop_loss=leg_order(SL, quantity=D("0.4")).accept(),
    )

    plan = on_entry_fill(lone)

    assert not plan.cancel
    assert len(plan.protect) == 1


def test_legs_already_the_right_size_need_nothing() -> None:
    """So a repeated event cannot churn orders at the venue."""
    placed = bracket(
        entry=filled(entry_order(), "0.4"),
        take_profit=leg_order(TP, quantity=D("0.4")).accept(),
        stop_loss=leg_order(SL, quantity=D("0.4")).accept(),
    )

    assert on_entry_fill(placed).is_empty


def test_a_finished_leg_is_not_resized() -> None:
    """A filled leg means the protection is spent; that is on_leg_fill's business."""
    done = bracket(
        entry=filled(entry_order(), "0.4"),
        stop_loss=leg_order(SL, quantity=D("0.4")).accept().apply_fill(D("0.4"), D("58000.0")),
    )

    with pytest.raises(ValueError, match="already FILLED"):
        on_entry_fill(done)


# --- FR-ORD-15: one leg fills, the other goes ----------------------------


def test_a_filled_take_profit_cancels_the_stop_loss() -> None:
    """R-16: futures legs are not an OCO pair, so the survivor must be cancelled."""
    placed = bracket(
        entry=filled(entry_order(), "1.0"),
        take_profit=leg_order(TP, quantity=D("1.0")).accept(),
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
    )

    plan = on_leg_fill(placed, TP)

    assert [c.role for c in plan.cancel] == [SL]
    assert plan.cancel[0].client_order_id == "tt1-p1-stop_loss"
    assert not plan.protect


def test_a_filled_stop_loss_cancels_the_take_profit() -> None:
    placed = bracket(
        entry=filled(entry_order(), "1.0"),
        take_profit=leg_order(TP, quantity=D("1.0")).accept(),
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
    )

    assert [c.role for c in on_leg_fill(placed, SL).cancel] == [TP]


def test_a_lone_leg_on_a_finished_entry_leaves_nothing_to_cancel() -> None:
    lone = Bracket(
        entry=filled(entry_order(), "1.0"),
        stop_loss_price=D("58000.0"),
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
    )

    assert on_leg_fill(lone, SL).is_empty


def test_a_protective_fill_cancels_an_entry_that_is_still_resting() -> None:
    """C-24: the rest of the entry would reopen the position with nothing protecting it.

    After a stop loss fires, a buy entry sits above a market that has just fallen through
    it, so the remainder fills at once — and the leg that would have covered it is spent.
    """
    partly = bracket(
        entry=filled(entry_order(), "0.4"),
        stop_loss=leg_order(SL, quantity=D("0.4")).accept(),
        take_profit=leg_order(TP, quantity=D("0.4")).accept(),
    )

    plan = on_leg_fill(partly, SL)

    assert [c.role for c in plan.cancel] == [TP, BracketRole.ENTRY]
    assert plan.cancel[1].client_order_id == "tt1-p1-1"


def test_an_entry_that_already_finished_is_not_cancelled_again() -> None:
    done = bracket(
        entry=filled(entry_order(), "1.0"),  # FILLED, so nothing is left resting
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
        take_profit=leg_order(TP, quantity=D("1.0")).accept(),
    )

    assert [c.role for c in on_leg_fill(done, SL).cancel] == [TP]


def test_a_leg_that_was_never_placed_cannot_have_filled() -> None:
    with pytest.raises(ValueError, match="never placed"):
        on_leg_fill(bracket(entry=filled(entry_order(), "1.0")), TP)


def test_the_entry_is_never_the_leg_that_fills() -> None:
    with pytest.raises(ValueError, match="only a protective leg"):
        on_leg_fill(bracket(), BracketRole.ENTRY)


# --- FR-ORD-15: the entry ends early -------------------------------------


def test_a_partly_filled_entry_leaves_its_protection_in_place() -> None:
    """The position is real whether or not the rest of the entry ever arrives."""
    cancelled = filled(entry_order(), "0.4").cancel()
    placed = bracket(entry=cancelled, stop_loss=leg_order(SL, quantity=D("0.4")).accept())

    assert on_entry_finished(placed).is_empty


def test_an_entry_that_filled_nothing_takes_its_protection_with_it() -> None:
    placed = bracket(
        entry=entry_order().accept().expire(),
        take_profit=leg_order(TP, quantity=D("1.0")).accept(),
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
    )

    assert [c.role for c in on_entry_finished(placed).cancel] == [TP, SL]


def test_an_open_entry_has_not_finished() -> None:
    with pytest.raises(ValueError, match="still open"):
        on_entry_finished(bracket(entry=entry_order().accept()))


# --- R-16: the position goes some other way ------------------------------


def test_closing_the_position_elsewhere_cancels_every_resting_leg() -> None:
    """Manual close, liquidation or an outside trade all end the protection."""
    placed = bracket(
        entry=filled(entry_order(), "1.0"),
        take_profit=leg_order(TP, quantity=D("1.0")).accept(),
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
    )

    assert [c.role for c in on_position_closed(placed).cancel] == [TP, SL]


def test_a_leg_that_is_already_finished_is_not_cancelled_again() -> None:
    placed = bracket(
        entry=filled(entry_order(), "1.0"),
        take_profit=leg_order(TP, quantity=D("1.0")).accept().cancel(),
        stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
    )

    assert [c.role for c in on_position_closed(placed).cancel] == [SL]


def test_closing_a_position_with_nothing_placed_asks_for_nothing() -> None:
    assert on_position_closed(bracket(entry=filled(entry_order(), "1.0"))).is_empty


def test_closing_the_position_also_cancels_a_partly_filled_entry() -> None:
    """C-24: otherwise the remainder reopens the position with its legs already gone.

    Regression for the sequence: entry 1.0 fills 0.4, the user closes manually, the plan
    cancels the stop loss, and the remaining 0.6 then fills. Leaving the entry resting
    left ``on_entry_fill`` no way to protect what came back, since resizing a cancelled
    leg is refused.
    """
    partly = bracket(
        entry=filled(entry_order(), "0.4"),
        stop_loss=leg_order(SL, quantity=D("0.4")).accept(),
    )

    plan = on_position_closed(partly)

    assert [c.role for c in plan.cancel] == [SL, BracketRole.ENTRY]
    assert plan.cancel[1].client_order_id == "tt1-p1-1"


def test_closing_the_position_leaves_a_finished_entry_alone() -> None:
    assert [
        c.role
        for c in on_position_closed(
            bracket(
                entry=filled(entry_order(), "1.0"),
                stop_loss=leg_order(SL, quantity=D("1.0")).accept(),
            )
        ).cancel
    ] == [SL]
