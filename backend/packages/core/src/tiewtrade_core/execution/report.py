from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tiewtrade_core.market import LiquidityRole


class ReportKind(StrEnum):
    """What a venue said about an order (architecture §4.3, Decided C-19).

    These are the outcomes that change an order's status. ``ACCEPTED`` and ``REJECTED``
    answer the submission; ``FILLED`` reports a trade, whole or partial; ``CANCELED`` and
    ``EXPIRED`` end the order without a trade.
    """

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """What comes back from a venue about one order (architecture §4.3, Decided C-19).

    The Execution Adapter port returns nothing, because an outcome can arrive long after
    the call: this is how it arrives instead. Paper produces reports synchronously inside
    the engine (architecture §7.1); Live receives them from the User Data Stream and
    publishes them on ``exec.report.{portfolio}`` (§6.2). Both shapes are the same, so the
    engine applies them the same way whichever side of P-03/P-04 it is on.

    The report carries no timestamp. Time comes from the event that produced it, which the
    engine already holds, and the core reads no clock (ADR-0001).

    ``quantity``, ``price`` and ``liquidity`` are present exactly when ``kind`` is
    ``FILLED``, so a report cannot claim a trade without saying what traded.
    """

    client_order_id: str
    kind: ReportKind
    quantity: Decimal | None = None
    price: Decimal | None = None
    liquidity: LiquidityRole | None = None
    exchange_order_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id must not be empty")
        if self.kind is ReportKind.FILLED:
            if self.quantity is None or self.price is None or self.liquidity is None:
                raise ValueError("a fill report must carry quantity, price and liquidity")
            if self.quantity <= 0 or self.price <= 0:
                raise ValueError("fill quantity and price must be positive")
        elif self.quantity is not None or self.price is not None or self.liquidity is not None:
            raise ValueError(f"a {self.kind} report must not carry trade details")
        if self.kind is ReportKind.REJECTED and not self.reason:
            raise ValueError("a rejection must carry a reason")
