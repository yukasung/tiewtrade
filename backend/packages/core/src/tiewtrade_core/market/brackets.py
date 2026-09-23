from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from tiewtrade_core._decimal import calc


@dataclass(frozen=True, slots=True)
class LeverageBracket:
    """One tier of a symbol's Leverage Bracket (calculation spec §2.3)."""

    bracket: int
    notional_floor: Decimal
    notional_cap: Decimal
    maintenance_margin_rate: Decimal
    maintenance_amount: Decimal  # "cum"
    max_leverage: int

    def contains(self, notional: Decimal) -> bool:
        # Verify (C-02): floor inclusive, cap exclusive is assumed until golden tests confirm.
        return self.notional_floor <= notional < self.notional_cap


@dataclass(frozen=True, slots=True)
class LeverageBrackets:
    """Ordered, contiguous brackets of one symbol."""

    tiers: tuple[LeverageBracket, ...]

    def __post_init__(self) -> None:
        if not self.tiers:
            raise ValueError("at least one bracket is required")
        ordered = sorted(self.tiers, key=lambda t: t.notional_floor)
        if ordered[0].notional_floor != 0:
            raise ValueError("first bracket must start at notional 0")
        for lower, upper in pairwise(ordered):
            if lower.notional_cap != upper.notional_floor:
                raise ValueError("brackets must be contiguous")
        object.__setattr__(self, "tiers", tuple(ordered))

    @calc
    def for_notional(self, notional: Decimal) -> LeverageBracket:
        """Bracket for ``notional``; the last bracket also covers anything above its cap."""
        if notional < 0:
            raise ValueError("notional must not be negative")
        for tier in self.tiers:
            if tier.contains(notional):
                return tier
        return self.tiers[-1]

    @calc
    def maintenance_margin(self, notional: Decimal) -> Decimal:
        tier = self.for_notional(notional)
        return notional * tier.maintenance_margin_rate - tier.maintenance_amount
