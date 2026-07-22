from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.spot_policy import SpotTradingPolicy


@dataclass(frozen=True, slots=True)
class SpotCapitalPlan:
    available_capital: Decimal
    trading_capital: Decimal
    reserve: Decimal
    entry_notional: Decimal

    @classmethod
    def from_available(
        cls,
        available: Decimal,
        spot_policy: SpotTradingPolicy,
        entry_policy: EntryPolicy,
    ) -> "SpotCapitalPlan":
        if available <= 0:
            raise ValueError("available capital must be positive")

        trading_capital = available * spot_policy.trading_capital_ratio
        reserve = available - trading_capital
        return cls(
            available_capital=available,
            trading_capital=trading_capital,
            reserve=reserve,
            entry_notional=trading_capital / Decimal(entry_policy.max_entries),
        )
