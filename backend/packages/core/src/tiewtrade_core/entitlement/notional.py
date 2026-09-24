"""Workspace Open Notional and the limit check (calculation spec §5.1-§5.2, D-11, C-08).

The limit is measured across **every Portfolio of one Trading Mode in the Workspace**,
not per Portfolio, and Paper and Live are counted separately (FR-PLN-04). One Workspace
is checked by a single writer at a time (ADR-0009), so a caller can read the whole
Workspace, ask these functions, and act without racing itself.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.margin import PendingOrder, combined_notional


@dataclass(frozen=True, slots=True)
class FuturesSymbolExposure:
    """One Futures symbol of one Portfolio. ``quantity`` is signed: + Long, - Short."""

    quantity: Decimal
    mark_price: Decimal
    orders: tuple[PendingOrder, ...] = ()

    def __post_init__(self) -> None:
        if self.mark_price <= 0:
            raise ValueError("mark price must be positive")

    @property
    @calc
    def open_notional(self) -> Decimal:
        """|Q| * MP — the position alone, with no orders counted (§5.1)."""
        return abs(self.quantity) * self.mark_price

    @property
    def projected_notional(self) -> Decimal:
        """The position once its resting orders are counted (§5.2).

        The same formula as the margin requirement of §2.2, undivided (C-08).
        """
        return combined_notional(self.quantity, self.mark_price, self.orders)


@dataclass(frozen=True, slots=True)
class SpotSymbolExposure:
    """One Spot symbol of one Portfolio.

    Spot is Long only (D-10), so resting **buy** orders are what can still add to the
    holding; a sell order only ever reduces it and never reserves headroom.
    """

    quantity: Decimal
    last_price: Decimal
    resting_buy_value: Decimal = ZERO  # sum of qty * limit price of open buy orders

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("a spot holding cannot be negative")
        if self.last_price <= 0:
            raise ValueError("last price must be positive")
        if self.resting_buy_value < 0:
            raise ValueError("resting buy value must not be negative")

    @property
    @calc
    def open_notional(self) -> Decimal:
        """H * LP (§5.1)."""
        return self.quantity * self.last_price

    @property
    @calc
    def projected_notional(self) -> Decimal:
        """H * LP + the value of every resting buy (§5.2)."""
        return self.quantity * self.last_price + self.resting_buy_value


@calc
def open_notional(
    futures: Iterable[FuturesSymbolExposure] = (),
    spot: Iterable[SpotSymbolExposure] = (),
) -> Decimal:
    """Open Notional of a Workspace in one Trading Mode (§5.1, FR-PLN-04).

    Positions only. This is the number shown to the User as usage (FR-PLN-10); the check
    that gates an order uses ``projected_notional``, which also counts resting orders.
    """
    return sum((f.open_notional for f in futures), ZERO) + sum(
        (s.open_notional for s in spot), ZERO
    )


@calc
def projected_notional(
    futures: Iterable[FuturesSymbolExposure] = (),
    spot: Iterable[SpotSymbolExposure] = (),
) -> Decimal:
    """Open Notional with every resting order counted as a reservation (§5.2, C-08).

    Reserving on placement is what stops a User from parking many Limit orders that are
    each within the limit but together far past it. The reservation is released when the
    order is rejected, cancelled, expires or fills, which needs no rule here: the order
    simply stops being in the input.
    """
    return sum((f.projected_notional for f in futures), ZERO) + sum(
        (s.projected_notional for s in spot), ZERO
    )


def within_limit(
    limit: Decimal,
    projected_before: Decimal,
    projected_after: Decimal,
    *,
    reduces: bool = False,
) -> bool:
    """Whether an order may be sent under the Workspace notional limit (FR-PLN-05).

    ``reduces`` says the order can only reduce or close a position — a reduce-only order,
    or one on the opposite side within the position's size. Those pass unconditionally
    (§5.2), and the caller states it rather than the limit inferring it, because the
    projected notional does **not** fall for every such order.

    A protective leg shows why. A Bracket take profit is a reduce-only sell resting far
    above the mark, and §2.2 values the ask side at the order's own price, so it *raises*
    the projected number even though filling it can only shrink the position. Inferring
    "reduces" from the number falling would refuse the very order that protects the
    position. ``margin.order_margin`` documents the same asymmetry.

    Otherwise an order is refused when it would leave the Workspace over the limit and is
    what pushes it up. Drifting over on price alone is not a breach: FR-PLN-05 force-closes
    nothing, and simply refuses opening until the Workspace is back under.

    Comparisons only, with no arithmetic, so this cannot raise in a caller's Decimal
    context (the same reason ``execution.triggers`` avoids arithmetic).
    """
    if limit < 0:
        raise ValueError("limit must not be negative")
    if reduces:
        return True
    if projected_after <= limit:
        return True
    return projected_after <= projected_before
