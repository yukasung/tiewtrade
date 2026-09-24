"""Bracket lifecycle: Entry with its protective Take Profit and Stop Loss (FR-ORD-14/15).

Nothing here sends anything. Each event returns a ``BracketPlan`` describing what the
Order Manager should place, resize or cancel, the way ``resting_fill_report`` returns a
report rather than emitting one. The Execution Adapter is the only thing that talks to a
venue, and the core must not know whether that venue is Paper or Binance (FR-ORD-04).

A Bracket is not an entity of its own: the data model records it as ``bracket_id`` plus
``bracket_role`` on the orders that belong to it (data model §6.5). ``Bracket`` here is
the same grouping held in memory, so the caller reads the rows it already owns and gets
a plan back without the core keeping any state (C-20).

Live placement failure and its fail-safe (FR-ORD-16) are deliberately absent: retrying
within a few seconds needs a clock, which the core does not have, and Paper has no such
failure at all (FR-ORD-17).
"""

from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core._decimal import calc
from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders.enums import BracketRole, OrderType
from tiewtrade_core.orders.order import Order

# The order type each protective leg is sent as. Both fill as Market once touched
# (FR-ORD-12), so the leg carries a stop price and never a limit price.
_LEG_TYPE: dict[BracketRole, OrderType] = {
    BracketRole.TAKE_PROFIT: OrderType.TAKE_PROFIT_MARKET,
    BracketRole.STOP_LOSS: OrderType.STOP_MARKET,
}

_PROTECTIVE = (BracketRole.TAKE_PROFIT, BracketRole.STOP_LOSS)


@dataclass(frozen=True, slots=True)
class ProtectLeg:
    """Place a protective leg, or resize one that is already at the venue (FR-ORD-14).

    ``replaces`` carries the Client Order ID of the leg this supersedes, and is None when
    the leg is new. Resizing is expressed as one action rather than a cancel followed by a
    place, because the two venues achieve it differently and choosing between them is the
    Order Manager's business (FR-ORD-04). Splitting it here would also describe a moment
    where the filled quantity has no protection at all, which FR-ORD-14 does not allow.
    """

    role: BracketRole
    side: OrderSide
    quantity: Decimal
    stop_price: Decimal
    order_type: OrderType
    replaces: str | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("a protective leg must cover a positive quantity")
        if self.stop_price <= 0:
            raise ValueError("stop price must be positive")


@dataclass(frozen=True, slots=True)
class CancelLeg:
    """Cancel a protective leg that is still resting at the venue (FR-ORD-15, R-16)."""

    role: BracketRole
    client_order_id: str


@dataclass(frozen=True, slots=True)
class BracketPlan:
    """What the Order Manager should do next. An empty plan means nothing is needed."""

    protect: tuple[ProtectLeg, ...] = ()
    cancel: tuple[CancelLeg, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.protect and not self.cancel


@dataclass(frozen=True, slots=True)
class Bracket:
    """An Entry order with the protection requested for it (FR-ORD-14, FR-ORD-15).

    The requested prices and the placed legs live in one value because a Bracket exists
    from the moment the Entry is sent, before either leg is at the venue: protection is
    placed on the first Entry fill, not on submission. A leg is None until then, and its
    price says what to place when the moment comes.

    A Bracket needs at least one protective price. An Entry with neither is an ordinary
    order and has no reason to be wrapped.
    """

    entry: Order
    take_profit_price: Decimal | None = None
    stop_loss_price: Decimal | None = None
    take_profit: Order | None = None
    stop_loss: Order | None = None

    def __post_init__(self) -> None:
        if self.take_profit_price is None and self.stop_loss_price is None:
            raise ValueError("a bracket must request a take profit, a stop loss, or both")
        for role in _PROTECTIVE:
            price = self.price_for(role)
            if price is not None and price <= 0:
                raise ValueError(f"{role} price must be positive")
            leg = self.leg(role)
            if leg is None:
                continue
            if price is None:
                raise ValueError(f"a {role} leg was placed without a requested price")
            self._check_leg(role, leg)

    def _check_leg(self, role: BracketRole, leg: Order) -> None:
        """A placed leg must be able to close the Entry and nothing more.

        These are the properties the plans below assume, so they are checked once here
        rather than re-derived at every event.
        """
        if leg.symbol != self.entry.symbol:
            raise ValueError(f"a {role} leg must be on the same symbol as the entry")
        if leg.side is self.entry.side:
            raise ValueError(f"a {role} leg must close the entry, not add to it")
        if not leg.reduce_only:
            raise ValueError(f"a {role} leg must be reduce-only")
        if leg.order_type is not _LEG_TYPE[role]:
            raise ValueError(f"a {role} leg must be a {_LEG_TYPE[role]} order")
        if leg.quantity > self.entry.quantity:
            raise ValueError(f"a {role} leg cannot cover more than the entry")

    @property
    def closing_side(self) -> OrderSide:
        """The side a protective leg is sent on: the opposite of the Entry's."""
        return OrderSide.SELL if self.entry.side is OrderSide.BUY else OrderSide.BUY

    def price_for(self, role: BracketRole) -> Decimal | None:
        """The price requested for a protective leg, or None if that leg was not asked for."""
        if role is BracketRole.TAKE_PROFIT:
            return self.take_profit_price
        if role is BracketRole.STOP_LOSS:
            return self.stop_loss_price
        raise ValueError("the entry leg has no protective price")

    def leg(self, role: BracketRole) -> Order | None:
        """The placed order for a protective leg, or None while it is not at the venue."""
        if role is BracketRole.TAKE_PROFIT:
            return self.take_profit
        if role is BracketRole.STOP_LOSS:
            return self.stop_loss
        raise ValueError("the entry is not a protective leg")


def _order_for(bracket: Bracket, role: BracketRole) -> Order | None:
    return bracket.entry if role is BracketRole.ENTRY else bracket.leg(role)


def _cancel_open(bracket: Bracket, roles: tuple[BracketRole, ...]) -> tuple[CancelLeg, ...]:
    """Cancel whichever of ``roles`` is still resting, in the order given."""
    return tuple(
        CancelLeg(role=role, client_order_id=order.client_order_id)
        for role in roles
        if (order := _order_for(bracket, role)) is not None and order.is_open
    )


@calc
def on_entry_fill(bracket: Bracket) -> BracketPlan:
    """Protection after the Entry has filled, in whole or in part (FR-ORD-14).

    Protection starts at the **first** Entry fill and covers the **filled quantity only**,
    so an Entry that is still resting is never protected for size it does not hold. Every
    later fill resizes both legs to the new cumulative filled quantity, which is why this
    is called on each fill and not only the first.

    A leg already at the venue for the right quantity produces nothing, so calling this
    again after a repeated event is harmless.

    Raises when the Entry has not filled at all — there is nothing to protect yet and a
    zero-quantity leg is not a meaningful order — and when a leg is already finished,
    because a filled leg means the protection is spent and the Bracket is over
    (``on_leg_fill``), not that it should be resized.
    """
    protected = bracket.entry.filled_quantity
    if protected == 0:
        raise ValueError("the entry has not filled, so there is nothing to protect")

    actions: list[ProtectLeg] = []
    for role in _PROTECTIVE:
        price = bracket.price_for(role)
        if price is None:
            continue
        leg = bracket.leg(role)
        if leg is not None and not leg.is_open:
            raise ValueError(f"the {role} leg is already {leg.status}")
        if leg is not None and leg.quantity == protected:
            continue
        actions.append(
            ProtectLeg(
                role=role,
                side=bracket.closing_side,
                quantity=protected,
                stop_price=price,
                order_type=_LEG_TYPE[role],
                replaces=None if leg is None else leg.client_order_id,
            )
        )
    return BracketPlan(protect=tuple(actions))


def on_leg_fill(bracket: Bracket, filled: BracketRole) -> BracketPlan:
    """One protective leg filled, so the other is cancelled (FR-ORD-15, R-16).

    TP and SL are two independent orders on Futures rather than an OCO pair, so nothing at
    the venue cancels the survivor. Leaving it resting is R-16: it would later close a
    position the user no longer holds.

    A protective fill ends the whole Bracket, so an Entry that has not filled completely is
    cancelled with it (C-24). The remainder is not merely idle: after a stop loss fires, a
    buy Entry sits above a market that has just fallen through it, which fills at once and
    reopens the position the stop just closed — with no protection left, since the leg that
    would have covered it is spent. FR-ORD-14 places protection once and resizes it, so
    there is no second round of legs to cover a second entry. The resulting state, an Entry
    cancelled after a partial fill, is the one FR-ORD-15 already describes.
    """
    if filled not in _PROTECTIVE:
        raise ValueError("only a protective leg fills a bracket")
    if bracket.leg(filled) is None:
        raise ValueError(f"the {filled} leg was never placed, so it cannot have filled")

    survivor = (
        BracketRole.STOP_LOSS if filled is BracketRole.TAKE_PROFIT else BracketRole.TAKE_PROFIT
    )
    return BracketPlan(cancel=_cancel_open(bracket, (survivor, BracketRole.ENTRY)))


def on_entry_finished(bracket: Bracket) -> BracketPlan:
    """The Entry was cancelled, expired or rejected before filling completely (FR-ORD-15).

    Protection for a quantity that did fill stays exactly as it is: the position is real
    whether or not the rest of the Entry ever arrives. Only an Entry that filled nothing
    leaves the legs protecting a position that does not exist, and those are cancelled.
    """
    if bracket.entry.is_open:
        raise ValueError("the entry is still open")
    if bracket.entry.filled_quantity > 0:
        return BracketPlan()
    return BracketPlan(cancel=_cancel_open(bracket, _PROTECTIVE))


def on_position_closed(bracket: Bracket) -> BracketPlan:
    """The position was closed some other way, so the whole Bracket is wound up (R-16, C-24).

    Manual close, liquidation or a trade made outside the platform all end the position
    without either leg filling. The legs are reduce-only and would not open a new position,
    but they would sit in the user's open orders as protection for something that is gone.

    A partly filled Entry is cancelled with them, for the reason a protective fill cancels
    it in ``on_leg_fill``: the remainder would reopen the position, and the legs that were
    to cover it are gone. FR-ORD-14 places protection at the *first* Entry fill and resizes
    it from there, so once those legs are cancelled there is no second set to protect a
    position the Entry brings back.
    """
    return BracketPlan(cancel=_cancel_open(bracket, (*_PROTECTIVE, BracketRole.ENTRY)))
