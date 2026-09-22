from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from fasttrade_core._decimal import calc
from fasttrade_core.market.enums import MarketType, Venue
from fasttrade_core.market.rounding import is_multiple_of


class FilterViolation(StrEnum):
    """Symbol filter checks; values match the API ``FILTER_VIOLATION.filter`` param."""

    TICK = "tick"
    STEP = "step"
    MIN_QTY = "min_qty"
    MAX_QTY = "max_qty"
    MIN_NOTIONAL = "min_notional"


@dataclass(frozen=True, slots=True)
class SymbolFilters:
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    max_qty: Decimal | None
    min_notional: Decimal

    def __post_init__(self) -> None:
        if self.tick_size <= 0 or self.step_size <= 0:
            raise ValueError("tick_size and step_size must be positive")

    @calc
    def violations(self, quantity: Decimal, price: Decimal) -> list[FilterViolation]:
        """Return every filter the order breaks (FR-MKT-04). Empty list means valid."""
        found: list[FilterViolation] = []
        if not is_multiple_of(price, self.tick_size):
            found.append(FilterViolation.TICK)
        if not is_multiple_of(quantity, self.step_size):
            found.append(FilterViolation.STEP)
        if quantity < self.min_qty:
            found.append(FilterViolation.MIN_QTY)
        if self.max_qty is not None and quantity > self.max_qty:
            found.append(FilterViolation.MAX_QTY)
        if quantity * price < self.min_notional:
            found.append(FilterViolation.MIN_NOTIONAL)
        return found


@dataclass(frozen=True, slots=True)
class Symbol:
    venue: Venue
    market_type: MarketType
    name: str
    base_asset: str
    quote_asset: str
    filters: SymbolFilters
