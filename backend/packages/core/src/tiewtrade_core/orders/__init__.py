"""Order Intent, Order lifecycle, Bracket and Client Order ID (FR-ORD).

The ``ExecutionAdapter`` port lives in ``tiewtrade_core.execution`` beside the Paper
adapter that implements it, as architecture §4.2 lays out. Deciding which protective leg
fires at a given price lives there too, in ``triggers``; ``bracket`` here owns what
happens to the legs afterwards.
"""

from tiewtrade_core.orders.bracket import (
    Bracket,
    BracketPlan,
    CancelLeg,
    ProtectLeg,
    on_entry_fill,
    on_entry_finished,
    on_leg_fill,
    on_position_closed,
)
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
    "Bracket",
    "BracketPlan",
    "BracketRole",
    "CancelLeg",
    "Order",
    "OrderIntent",
    "OrderStatus",
    "OrderType",
    "OwnerType",
    "ProtectLeg",
    "TimeInForce",
    "build_client_order_id",
    "is_platform_client_order_id",
    "on_entry_fill",
    "on_entry_finished",
    "on_leg_fill",
    "on_position_closed",
    "order_from_intent",
]
