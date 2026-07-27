from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from enum import StrEnum
from uuid import UUID

from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.position import PositionSide


class BasketCloseReason(StrEnum):
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")


def _require_positive(value: Decimal, field: str) -> None:
    if value <= 0:
        raise ValueError(f"{field} must be positive")


def _require_non_negative(value: Decimal, field: str) -> None:
    if value < 0:
        raise ValueError(f"{field} must not be negative")


@dataclass(frozen=True, slots=True)
class BasketEntry:
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class ClosedBasket:
    basket_id: UUID
    entry_count: int
    average_entry_price: Decimal
    exit_price: Decimal
    gross_realized_pnl: Decimal
    trading_fees: Decimal
    funding_fee: Decimal
    net_realized_pnl: Decimal
    closed_at: datetime
    position_side: PositionSide = PositionSide.LONG
    close_reason: BasketCloseReason = BasketCloseReason.TAKE_PROFIT

    @property
    def realized_pnl(self) -> Decimal:
        return self.net_realized_pnl


class Basket:
    def __init__(
        self,
        basket_id: UUID,
        policy: EntryPolicy,
        take_profit_atr_multiplier: Decimal,
        position_side: PositionSide = PositionSide.LONG,
    ) -> None:
        _require_positive(
            take_profit_atr_multiplier,
            "take_profit_atr_multiplier",
        )
        self._basket_id = basket_id
        self._policy = policy
        self._take_profit_atr_multiplier = take_profit_atr_multiplier
        self._position_side = position_side
        self._entries: list[BasketEntry] = []
        self._is_closed = False
        self.take_profit_price: Decimal | None = None

    @property
    def basket_id(self) -> UUID:
        return self._basket_id

    @property
    def position_side(self) -> PositionSide:
        return self._position_side

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def is_empty(self) -> bool:
        return not self._entries

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def total_quantity(self) -> Decimal:
        return sum((entry.quantity for entry in self._entries), Decimal("0"))

    @property
    def entry_fees(self) -> Decimal:
        return sum((entry.fee for entry in self._entries), Decimal("0"))

    @property
    def average_entry_price(self) -> Decimal:
        if self.is_empty:
            raise ValueError("basket is empty")
        total_notional = sum(
            (entry.price * entry.quantity for entry in self._entries),
            Decimal("0"),
        )
        return total_notional / self.total_quantity

    def add_entry(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        fee: Decimal,
        filled_at: datetime,
        atr: Decimal,
        tick_size: Decimal,
        position_side: PositionSide = PositionSide.LONG,
    ) -> None:
        _require_utc(filled_at, "filled_at")
        if self.is_closed:
            raise ValueError("basket is closed")
        if self.entry_count >= self._policy.max_entries:
            raise ValueError("basket has reached maximum entries")
        if position_side is not self.position_side:
            raise ValueError("opposite-side Entry is not allowed in One-way Mode")
        _require_positive(price, "price")
        _require_positive(quantity, "quantity")
        _require_non_negative(fee, "fee")
        _require_non_negative(atr, "atr")
        _require_positive(tick_size, "tick_size")

        total_quantity = self.total_quantity + quantity
        total_notional = sum(
            (entry.price * entry.quantity for entry in self._entries),
            Decimal("0"),
        ) + (price * quantity)
        average_entry_price = total_notional / total_quantity
        if self.position_side is PositionSide.LONG:
            raw_target = average_entry_price + (atr * self._take_profit_atr_multiplier)
            rounding = ROUND_DOWN
        else:
            raw_target = average_entry_price - (atr * self._take_profit_atr_multiplier)
            rounding = ROUND_CEILING
        if raw_target <= 0:
            raise ValueError("take profit price must be positive")
        take_profit_price = (raw_target / tick_size).to_integral_value(
            rounding=rounding
        ) * tick_size

        self._entries.append(BasketEntry(price, quantity, fee, filled_at))
        self.take_profit_price = take_profit_price

    def close(
        self,
        *,
        exit_price: Decimal,
        exit_fee: Decimal,
        closed_at: datetime,
        close_reason: BasketCloseReason = BasketCloseReason.TAKE_PROFIT,
    ) -> ClosedBasket:
        _require_utc(closed_at, "closed_at")
        if self.is_closed:
            raise ValueError("basket is closed")
        if self.is_empty:
            raise ValueError("basket is empty")
        _require_positive(exit_price, "exit_price")
        _require_non_negative(exit_fee, "exit_fee")

        if self.position_side is PositionSide.LONG:
            gross_realized_pnl = sum(
                (
                    (exit_price - entry.price) * entry.quantity
                    for entry in self._entries
                ),
                Decimal("0"),
            )
        else:
            gross_realized_pnl = sum(
                (
                    (entry.price - exit_price) * entry.quantity
                    for entry in self._entries
                ),
                Decimal("0"),
            )
        trading_fees = self.entry_fees + exit_fee
        funding_fee = Decimal("0")
        net_realized_pnl = gross_realized_pnl - trading_fees - funding_fee
        closed = ClosedBasket(
            basket_id=self.basket_id,
            entry_count=self.entry_count,
            average_entry_price=self.average_entry_price,
            exit_price=exit_price,
            gross_realized_pnl=gross_realized_pnl,
            trading_fees=trading_fees,
            funding_fee=funding_fee,
            net_realized_pnl=net_realized_pnl,
            closed_at=closed_at,
            position_side=self.position_side,
            close_reason=close_reason,
        )
        self._is_closed = True
        return closed
