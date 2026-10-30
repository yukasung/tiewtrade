"""Exact cross-unit arithmetic used by Spot position accounting (F-14)."""

from decimal import Decimal

from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import InvalidInputTypeError, UnitMismatchError
from tiewtrade.core.money.limits import STORED_SCALE
from tiewtrade.core.money.rounding import RoundingDirection, rounded_quotient
from tiewtrade.core.money.types import Money, Quantity
from tiewtrade.core.money.validation import ensure_canonical_unit


def _coefficient(value: Money | Quantity) -> int:
    return int(value.amount.scaleb(STORED_SCALE))


def _rounding(value: object) -> RoundingDirection:
    if not isinstance(value, RoundingDirection):
        raise InvalidInputTypeError("explicit rounding direction required")
    return value


@guarded
def money_for_quantity(
    unit_price: Money,
    quantity: Quantity,
    *,
    asset: str,
    rounding: RoundingDirection,
) -> Money:
    """Multiply a quote-currency unit price by a base-asset quantity exactly once."""
    if type(unit_price) is not Money or type(quantity) is not Quantity:
        raise InvalidInputTypeError("Money price and Quantity required")
    ensure_canonical_unit(asset)
    if quantity.asset != asset:
        raise UnitMismatchError("quantity asset does not match the priced asset")
    direction = _rounding(rounding)
    coefficient = rounded_quotient(
        _coefficient(unit_price) * _coefficient(quantity),
        _coefficient(Quantity.of(1, asset)),
        direction,
    )
    return Money(Decimal(coefficient).scaleb(-STORED_SCALE), unit_price.currency)


@guarded
def price_for_notional(
    total: Money,
    quantity: Quantity,
    *,
    asset: str,
    rounding: RoundingDirection,
) -> Money:
    """Divide exact quote notional by positive base quantity with one explicit rounding."""
    if type(total) is not Money or type(quantity) is not Quantity:
        raise InvalidInputTypeError("Money total and Quantity required")
    ensure_canonical_unit(asset)
    if quantity.asset != asset or quantity.amount <= 0 or total.amount <= 0:
        raise InvalidInputTypeError("positive matching-asset quantity and notional required")
    direction = _rounding(rounding)
    coefficient = rounded_quotient(
        _coefficient(total) * _coefficient(Quantity.of(1, asset)),
        _coefficient(quantity),
        direction,
    )
    return Money(Decimal(coefficient).scaleb(-STORED_SCALE), total.currency)


@guarded
def allocate_money(
    total: Money,
    part: Quantity,
    whole: Quantity,
    *,
    rounding: RoundingDirection,
) -> Money:
    """Allocate ``total`` in proportion to same-asset quantities with one explicit rounding."""
    if type(total) is not Money or type(part) is not Quantity or type(whole) is not Quantity:
        raise InvalidInputTypeError("Money total and Quantity ratio required")
    if part.asset != whole.asset:
        raise UnitMismatchError("allocation quantities use different assets")
    if whole.amount <= 0 or part.amount < 0 or part.amount > whole.amount:
        raise InvalidInputTypeError("allocation requires 0 <= part <= positive whole")
    direction = _rounding(rounding)
    coefficient = rounded_quotient(
        _coefficient(total) * _coefficient(part),
        _coefficient(whole),
        direction,
    )
    return Money(Decimal(coefficient).scaleb(-STORED_SCALE), total.currency)
