from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SpotTradingPolicy:
    trading_capital_ratio: Decimal

    def __post_init__(self) -> None:
        if not Decimal("0") < self.trading_capital_ratio < Decimal("1"):
            raise ValueError("trading_capital_ratio must be between 0 and 1")

    @property
    def reserve_ratio(self) -> Decimal:
        return Decimal("1") - self.trading_capital_ratio
