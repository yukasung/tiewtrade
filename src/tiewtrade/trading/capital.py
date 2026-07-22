from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SpotCapitalPlan:
    available_capital: Decimal
    trading_capital: Decimal
    reserve: Decimal
    entry_notional: Decimal

    @classmethod
    def from_available(cls, available: Decimal) -> "SpotCapitalPlan":
        if available <= 0:
            raise ValueError("available capital must be positive")

        trading_capital = available * Decimal("0.80")
        reserve = available - trading_capital
        return cls(
            available_capital=available,
            trading_capital=trading_capital,
            reserve=reserve,
            entry_notional=trading_capital / Decimal("10"),
        )
