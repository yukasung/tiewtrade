"""Order Intent, Order lifecycle and Client Order ID (FR-ORD).

The ``ExecutionAdapter`` port lives in ``tiewtrade_core.execution`` beside the Paper
adapter that implements it, as architecture §4.2 lays out. Brackets (FR-ORD-14,
FR-ORD-15) are not here yet; they land in a follow-up round.
"""

from tiewtrade_core.orders.client_order_id import (
    MAX_LENGTH,
    SEPARATOR,
    build_client_order_id,
    is_platform_client_order_id,
)
from tiewtrade_core.orders.enums import (
    BracketRole,
    OrderStatus,
    OrderType,
    OwnerType,
    TimeInForce,
)
from tiewtrade_core.orders.intent import OrderIntent
from tiewtrade_core.orders.order import Order, order_from_intent

__all__ = [
    "MAX_LENGTH",
    "SEPARATOR",
    "BracketRole",
    "Order",
    "OrderIntent",
    "OrderStatus",
    "OrderType",
    "OwnerType",
    "TimeInForce",
    "build_client_order_id",
    "is_platform_client_order_id",
    "order_from_intent",
]
