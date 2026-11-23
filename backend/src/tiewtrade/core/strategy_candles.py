"""Authoritative candle capabilities supplied to pure strategies (F-21)."""

from dataclasses import dataclass

from tiewtrade.core.market_data import Candle
from tiewtrade.core.money import Money


@dataclass(frozen=True, slots=True)
class StrategyCandleInput:
    candle: Candle
    contiguous_count: int
    source_revision: str
    backfilled: bool
    exit_on_candle: bool
    guard_revision: int
    open_entries: int
    price_tick: Money
    basket_triggered: bool = False
    arm_validated: bool = False
    closure_proof: tuple[str, int, str] | None = None

    def __post_init__(self) -> None:
        if (
            type(self.candle) is not Candle
            or type(self.source_revision) is not str
            or not self.source_revision
        ):
            raise ValueError("candle and source revision required")
        for value in (self.contiguous_count, self.guard_revision, self.open_entries):
            if type(value) is not int or value < 0:
                raise ValueError("nonnegative candle counters required")
        if any(
            type(value) is not bool
            for value in (
                self.backfilled,
                self.exit_on_candle,
                self.basket_triggered,
                self.arm_validated,
            )
        ):
            raise ValueError("explicit candle readiness flags required")
        if (
            type(self.price_tick) is not Money
            or self.price_tick.currency != self.candle.quote
            or self.price_tick.amount <= 0
        ):
            raise ValueError("positive quote price tick required")
