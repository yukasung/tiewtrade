from dataclasses import dataclass, replace
from decimal import Decimal

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders.enums import OrderStatus, OrderType, OwnerType, TimeInForce
from tiewtrade_core.orders.intent import OrderIntent

# Which statuses a status may move to (FR-ORD-03). Terminal statuses map to nothing, so a
# finished order can never change again.
_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_NEW: frozenset(
        {
            OrderStatus.NEW,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED,
            OrderStatus.CANCELED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.NEW: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Order:
    """An order the platform owns, with its lifecycle (FR-ORD-03, data model §6.5).

    Immutable: every transition returns a new ``Order``, the way ``apply_futures_fill``
    returns a new position, so an engine can keep the previous value for an audit trail.

    ``client_order_id`` is assigned before the order is sent and is what makes a retry
    idempotent (NFR-05, FR-LIVE-07). ``exchange_order_id`` arrives from the venue and is
    absent for Paper.
    """

    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    owner_type: OwnerType
    status: OrderStatus = OrderStatus.PENDING_NEW
    filled_quantity: Decimal = ZERO
    average_fill_price: Decimal | None = None
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    reduce_only: bool = False
    exchange_order_id: str | None = None
    reject_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id must not be empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if not 0 <= self.filled_quantity <= self.quantity:
            raise ValueError("filled quantity must be between zero and the order quantity")
        if (self.average_fill_price is None) != (self.filled_quantity == 0):
            raise ValueError("an order has an average fill price exactly when it has filled")
        if self.average_fill_price is not None and self.average_fill_price <= 0:
            raise ValueError("average fill price must be positive")

    @property
    @calc
    def remaining_quantity(self) -> Decimal:
        """What is left to fill.

        Decorated because reading it subtracts: without ``@calc`` the subtraction would run
        in whatever Decimal context the caller happens to be in, so a low precision would
        silently truncate the remainder and a trapped Inexact would raise on a plain
        attribute read.
        """
        return self.quantity - self.filled_quantity

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    def _to(self, status: OrderStatus, **changes: object) -> "Order":
        """Move to ``status``, rejecting a transition the lifecycle does not allow."""
        if status not in _TRANSITIONS[self.status]:
            raise ValueError(f"cannot move an order from {self.status} to {status}")
        return replace(self, status=status, **changes)  # type: ignore[arg-type]

    def accept(self, *, exchange_order_id: str | None = None) -> "Order":
        """The venue acknowledged the order: PENDING_NEW becomes NEW."""
        return self._to(OrderStatus.NEW, exchange_order_id=exchange_order_id)

    def reject(self, reason: str) -> "Order":
        """The venue refused the order. Risk Engine rejections never reach this point:
        they are audit-logged without creating an order at all (data model §6.5)."""
        if not reason:
            raise ValueError("a rejection must carry a reason")
        return self._to(OrderStatus.REJECTED, reject_reason=reason)

    def cancel(self) -> "Order":
        """Cancel the order, keeping whatever it had already filled."""
        return self._to(OrderStatus.CANCELED)

    def expire(self) -> "Order":
        return self._to(OrderStatus.EXPIRED)

    @calc
    def apply_fill(self, quantity: Decimal, price: Decimal) -> "Order":
        """Record a fill, updating the filled quantity and the weighted average price.

        Paper fills the whole order at once (FR-ORD-09), but Live reports partial fills, so
        the lifecycle supports both. Filling the remainder moves the order to FILLED;
        anything less moves it to PARTIALLY_FILLED.
        """
        # The lifecycle is checked before the amounts: a finished order must say that it is
        # finished, not complain that nothing is left to fill.
        if self.status.is_terminal:
            raise ValueError(f"cannot move an order from {self.status} to a fill")
        if quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be positive")
        if quantity > self.remaining_quantity:
            raise ValueError("a fill cannot exceed the remaining quantity")

        filled = self.filled_quantity + quantity
        if self.average_fill_price is None:
            average = price
        else:
            average = (self.average_fill_price * self.filled_quantity + price * quantity) / filled
        status = OrderStatus.FILLED if filled == self.quantity else OrderStatus.PARTIALLY_FILLED
        return self._to(status, filled_quantity=filled, average_fill_price=average)


def order_from_intent(
    intent: OrderIntent,
    *,
    client_order_id: str,
    owner_type: OwnerType,
) -> Order:
    """Turn an approved Order Intent into a sendable Order (FR-ORD-02 then FR-ORD-03).

    The caller supplies the Client Order ID because generating it needs a sequence the core
    does not hold. Call this only after the Risk Engine approves the intent.
    """
    return Order(
        client_order_id=client_order_id,
        symbol=intent.symbol,
        side=intent.side,
        order_type=intent.order_type,
        quantity=intent.quantity,
        owner_type=owner_type,
        price=intent.price,
        stop_price=intent.stop_price,
        time_in_force=intent.time_in_force,
        reduce_only=intent.reduce_only,
    )
