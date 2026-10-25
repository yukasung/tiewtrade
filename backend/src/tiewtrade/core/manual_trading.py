"""Shared manual-account checks and exact available-funds presentation."""

from dataclasses import dataclass

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    AdmissionPolicy,
    BaseSize,
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    SafetyUnavailableError,
)
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.trading_account import AccountUse


class ManualUseRequiredError(SafetyUnavailableError):
    code = "MANUAL_USE_REQUIRED"


@dataclass(frozen=True, slots=True)
class ManualAccountPolicy:
    use: AccountUse | None
    held: Quantity
    reserved: Quantity
    delegate: AdmissionPolicy | None

    def check(self, intent: OrderIntent) -> None:
        if intent.origin is not OrderOrigin.MANUAL:
            raise OrderConflictError("manual origin required")
        if self.held < self.reserved:
            raise SafetyUnavailableError("inconsistent authoritative base reservation")
        reducing = (
            intent.side is ExecutionSide.SELL
            and isinstance(intent.size, BaseSize)
            and not intent.size.quantity > self.held - self.reserved
        )
        if not reducing and self.use is not AccountUse.MANUAL:
            raise ManualUseRequiredError("manual opening requires MANUAL account use")
        if self.delegate is None:
            raise SafetyUnavailableError("shared risk policy is unavailable")
        self.delegate.check(intent)


def available_quote(cash: Money, reservations: tuple[Money, ...]) -> tuple[Money, Money]:
    reserved = Money.of(0, cash.currency)
    for value in reservations:
        reserved += value
    if reserved > cash:
        raise SafetyUnavailableError("quote reservations exceed authoritative cash")
    return reserved, cash - reserved


def available_base(held: Quantity, reservations: tuple[Quantity, ...]) -> tuple[Quantity, Quantity]:
    reserved = Quantity.of(0, held.asset)
    for value in reservations:
        reserved += value
    if reserved > held:
        raise SafetyUnavailableError("base reservations exceed authoritative holding")
    return reserved, held - reserved
