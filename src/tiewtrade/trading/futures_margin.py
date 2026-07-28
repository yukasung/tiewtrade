from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide


@dataclass(frozen=True, slots=True)
class FuturesMarginSnapshot:
    account_equity: Decimal
    maintenance_margin: Decimal
    liquidation_price: Decimal | None


class FuturesMarginModel:
    def __init__(self, policy: FuturesTradingPolicy) -> None:
        self._policy = policy

    def liquidation_price(
        self,
        *,
        side: PositionSide,
        average_entry_price: Decimal,
        quantity: Decimal,
        available_capital: Decimal,
        accumulated_entry_fees: Decimal,
    ) -> Decimal | None:
        self._require_position_side(side)
        self._validate_inputs(
            average_entry_price,
            quantity,
            available_capital,
            accumulated_entry_fees,
        )
        wallet = available_capital - accumulated_entry_fees
        rate = self._policy.maintenance_margin_rate
        if side is PositionSide.LONG:
            threshold = (average_entry_price * quantity - wallet) / (
                quantity * (Decimal("1") - rate)
            )
            return threshold if threshold > 0 else None
        return (wallet + average_entry_price * quantity) / (
            quantity * (Decimal("1") + rate)
        )

    def snapshot(
        self,
        *,
        side: PositionSide,
        average_entry_price: Decimal,
        quantity: Decimal,
        available_capital: Decimal,
        accumulated_entry_fees: Decimal,
        current_price: Decimal,
    ) -> FuturesMarginSnapshot:
        if not current_price.is_finite() or current_price <= 0:
            raise ValueError("current_price must be finite and positive")
        liquidation_price = self.liquidation_price(
            side=side,
            average_entry_price=average_entry_price,
            quantity=quantity,
            available_capital=available_capital,
            accumulated_entry_fees=accumulated_entry_fees,
        )
        if side is PositionSide.LONG:
            unrealized_pnl = (current_price - average_entry_price) * quantity
        else:
            unrealized_pnl = (average_entry_price - current_price) * quantity
        account_equity = available_capital - accumulated_entry_fees + unrealized_pnl
        maintenance_margin = (
            abs(current_price * quantity) * self._policy.maintenance_margin_rate
        )
        return FuturesMarginSnapshot(
            account_equity=account_equity,
            maintenance_margin=maintenance_margin,
            liquidation_price=liquidation_price,
        )

    @staticmethod
    def _require_position_side(side: PositionSide) -> None:
        if not isinstance(side, PositionSide):
            raise ValueError("side must be a PositionSide")

    @staticmethod
    def _validate_inputs(
        average_entry_price: Decimal,
        quantity: Decimal,
        available_capital: Decimal,
        accumulated_entry_fees: Decimal,
    ) -> None:
        if not average_entry_price.is_finite() or average_entry_price <= 0:
            raise ValueError("average_entry_price must be finite and positive")
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("quantity must be finite and positive")
        if not available_capital.is_finite() or available_capital <= 0:
            raise ValueError("available_capital must be finite and positive")
        if not accumulated_entry_fees.is_finite() or accumulated_entry_fees < 0:
            raise ValueError("accumulated_entry_fees must be finite and non-negative")
        if accumulated_entry_fees >= available_capital:
            raise ValueError(
                "accumulated_entry_fees must remain below available capital"
            )
