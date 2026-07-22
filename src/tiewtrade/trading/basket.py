from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from tiewtrade.trading.entry_policy import EntryPolicy


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
    entry_count: int
    average_entry_price: Decimal
    exit_price: Decimal
    realized_pnl: Decimal
    closed_at: datetime


class Basket:
    def __init__(
        self,
        policy: EntryPolicy,
        take_profit_atr_multiplier: Decimal,
    ) -> None:
        _require_positive(
            take_profit_atr_multiplier,
            "take_profit_atr_multiplier",
        )
        self._policy = policy
        self._take_profit_atr_multiplier = take_profit_atr_multiplier
        self._entries: list[BasketEntry] = []
        self._is_closed = False
        self.take_profit_price: Decimal | None = None

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
    ) -> None:
        _require_utc(filled_at, "filled_at")
        if self.is_closed:
            raise ValueError("basket is closed")
        if self.entry_count >= self._policy.max_entries:
            raise ValueError("basket has reached maximum entries")
        _require_positive(price, "price")
        _require_positive(quantity, "quantity")
        _require_non_negative(fee, "fee")
        _require_non_negative(atr, "atr")
        _require_positive(tick_size, "tick_size")

        self._entries.append(BasketEntry(price, quantity, fee, filled_at))
        raw_target = self.average_entry_price + (
            atr * self._take_profit_atr_multiplier
        )
        self.take_profit_price = (
            (raw_target / tick_size).to_integral_value(rounding=ROUND_DOWN)
            * tick_size
        )

    def close(
        self,
        *,
        exit_price: Decimal,
        exit_fee: Decimal,
        closed_at: datetime,
    ) -> ClosedBasket:
        _require_utc(closed_at, "closed_at")
        if self.is_closed:
            raise ValueError("basket is closed")
        if self.is_empty:
            raise ValueError("basket is empty")
        _require_positive(exit_price, "exit_price")
        _require_non_negative(exit_fee, "exit_fee")

        gross_pnl = sum(
            (
                (exit_price - entry.price) * entry.quantity
                for entry in self._entries
            ),
            Decimal("0"),
        )
        entry_fees = sum((entry.fee for entry in self._entries), Decimal("0"))
        closed = ClosedBasket(
            entry_count=self.entry_count,
            average_entry_price=self.average_entry_price,
            exit_price=exit_price,
            realized_pnl=gross_pnl - entry_fees - exit_fee,
            closed_at=closed_at,
        )
        self._is_closed = True
        return closed
