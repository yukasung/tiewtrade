from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal


@dataclass(frozen=True, slots=True)
class SymbolRules:
    tick_size: Decimal
    step_size: Decimal
    min_notional: Decimal

    def __post_init__(self) -> None:
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.step_size <= 0:
            raise ValueError("step_size must be positive")
        if self.min_notional <= 0:
            raise ValueError("min_notional must be positive")

    def floor_price(self, value: Decimal) -> Decimal:
        return (value / self.tick_size).to_integral_value(
            rounding=ROUND_DOWN
        ) * self.tick_size

    def ceil_price(self, value: Decimal) -> Decimal:
        return (value / self.tick_size).to_integral_value(
            rounding=ROUND_CEILING
        ) * self.tick_size

    def floor_quantity(self, value: Decimal) -> Decimal:
        return (value / self.step_size).to_integral_value(
            rounding=ROUND_DOWN
        ) * self.step_size

    def meets_min_notional(self, *, price: Decimal, quantity: Decimal) -> bool:
        return price * quantity >= self.min_notional
