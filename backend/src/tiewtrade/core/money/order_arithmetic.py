"""Exact budget/step primitives for order sizing (F-15 plan section 3)."""

from decimal import Decimal

from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import InvalidInputTypeError, UnitMismatchError
from tiewtrade.core.money.limits import STORED_SCALE
from tiewtrade.core.money.position_arithmetic import _coefficient
from tiewtrade.core.money.rounding import RoundingDirection, rounded_quotient
from tiewtrade.core.money.types import Money, Quantity


@guarded
def align_quantity(quantity: Quantity, step: Quantity) -> Quantity:
    """Return a nonnegative quantity rounded down to an explicit asset step."""
    if type(quantity) is not Quantity or type(step) is not Quantity:
        raise InvalidInputTypeError("Quantity and step required")
    if quantity.asset != step.asset:
        raise UnitMismatchError("quantity and step assets differ")
    if quantity.amount < 0 or step.amount <= 0:
        raise InvalidInputTypeError("nonnegative quantity and positive step required")
    count = rounded_quotient(
        _coefficient(quantity), _coefficient(step), RoundingDirection.TOWARD_ZERO
    )
    return Quantity(Decimal(count * _coefficient(step)).scaleb(-STORED_SCALE), quantity.asset)


@guarded
def quantity_for_budget(budget: Money, price: Money, step: Quantity) -> Quantity:
    """Largest step-aligned quantity whose rounded-up cost does not exceed budget."""
    if type(budget) is not Money or type(price) is not Money or type(step) is not Quantity:
        raise InvalidInputTypeError("Money budget/price and Quantity step required")
    if budget.currency != price.currency:
        raise UnitMismatchError("budget and price currencies differ")
    if budget.amount < 0 or price.amount <= 0 or step.amount <= 0:
        raise InvalidInputTypeError("nonnegative budget and positive price/step required")
    count = rounded_quotient(
        _coefficient(budget) * _coefficient(Quantity.of(1, step.asset)),
        _coefficient(price) * _coefficient(step),
        RoundingDirection.TOWARD_ZERO,
    )
    return Quantity(Decimal(count * _coefficient(step)).scaleb(-STORED_SCALE), step.asset)
