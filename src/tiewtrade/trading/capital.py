from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
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
        if not available.is_finite() or available <= 0:
            raise ValueError("available capital must be finite and positive")

        trading_capital = available * spot_policy.trading_capital_ratio
        reserve = available - trading_capital
        return cls(
            available_capital=available,
            trading_capital=trading_capital,
            reserve=reserve,
            entry_notional=trading_capital / Decimal(entry_policy.max_entries),
        )


@dataclass(frozen=True, slots=True)
class FuturesCapitalPlan:
    available_capital: Decimal
    trading_capital: Decimal
    collateral_buffer: Decimal
    initial_margin_per_entry: Decimal
    target_notional_per_entry: Decimal

    @classmethod
    def from_available(
        cls,
        available: Decimal,
        futures_policy: FuturesTradingPolicy,
        entry_policy: EntryPolicy,
    ) -> "FuturesCapitalPlan":
        if not available.is_finite() or available <= 0:
            raise ValueError("available capital must be finite and positive")

        trading_capital = available * futures_policy.trading_capital_ratio
        collateral_buffer = available * futures_policy.collateral_buffer_ratio
        initial_margin = trading_capital / Decimal(entry_policy.max_entries)
        return cls(
            available_capital=available,
            trading_capital=trading_capital,
            collateral_buffer=collateral_buffer,
            initial_margin_per_entry=initial_margin,
            target_notional_per_entry=(
                initial_margin * Decimal(futures_policy.leverage)
            ),
        )
