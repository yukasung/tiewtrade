from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SpotTradingPolicy:
    trading_capital_ratio: Decimal
    max_entries: int

    def __post_init__(self) -> None:
        if not Decimal("0") < self.trading_capital_ratio < Decimal("1"):
            raise ValueError("trading_capital_ratio must be between 0 and 1")
        if not 2 <= self.max_entries <= 20 or self.max_entries % 2:
            raise ValueError("max_entries must be an even number between 2 and 20")

    @property
    def reserve_ratio(self) -> Decimal:
        return Decimal("1") - self.trading_capital_ratio
