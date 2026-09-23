from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders.enums import OrderType, TimeInForce


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """A request to trade, the only thing a Strategy, Bot or the UI may emit (P-01, FR-ORD-01).

    An intent is not an order. It carries no Client Order ID and no status: the Risk Engine
    approves it first (FR-ORD-02), and only then does the Order Manager turn it into an
    ``Order`` that can be sent. Rejected intents never become rows in ``orders`` — they go
    to the audit log (FR-ORD-05, data model §6.5).

    ``price`` is required for LIMIT and forbidden otherwise; ``stop_price`` is required for
    the conditional types and forbidden otherwise, so a self-contradictory intent cannot be
    constructed. Filter checks against the symbol (tick, step, notional) are the Risk
    Engine's job via ``SymbolFilters.violations`` and are deliberately not repeated here.
    """

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    reduce_only: bool = False

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        self._require_matching("price", self.price, self.order_type.needs_price)
        self._require_matching("stop_price", self.stop_price, self.order_type.needs_stop_price)

    def _require_matching(self, name: str, value: Decimal | None, required: bool) -> None:
        if required and value is None:
            raise ValueError(f"{self.order_type} requires {name}")
        if not required and value is not None:
            raise ValueError(f"{self.order_type} must not carry {name}")
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be positive")
