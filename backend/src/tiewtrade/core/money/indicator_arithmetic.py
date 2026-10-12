"""Exact indicator arithmetic; F-11 NC-33."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import InvalidInputTypeError, OutOfRangeError, UnitMismatchError
from tiewtrade.core.money.limits import MAX_ABS, STORED_SCALE
from tiewtrade.core.money.rounding import RoundingDirection, rounded_quotient
from tiewtrade.core.money.types import Money, _canonical_text
from tiewtrade.core.money.validation import NumberInput, ensure_valid_amount, normalise_amount


@dataclass(frozen=True, slots=True)
class Scalar:
    amount: Decimal

    @guarded
    def __post_init__(self) -> None:
        ensure_valid_amount(self.amount)
        if self.amount.is_zero():
            object.__setattr__(self, "amount", Decimal(0))

    @classmethod
    @guarded
    def of(cls, value: NumberInput) -> "Scalar":
        return cls(normalise_amount(value))

    def as_text(self) -> str:
        return _canonical_text(self.amount)


def _integer(value: object, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise InvalidInputTypeError("integer outside operation bounds")
    return value


def _money(value: object) -> Money:
    if type(value) is not Money:
        raise InvalidInputTypeError("Money required")
    return value


def _coefficient(value: Decimal) -> int:
    return int(value.scaleb(STORED_SCALE))


def _ratio(numerator: int, denominator: int, rounding: RoundingDirection) -> Decimal:
    if abs(numerator) >= _coefficient(MAX_ABS) * denominator:
        raise OutOfRangeError("indicator result outside stored range")
    coefficient = rounded_quotient(numerator, denominator, rounding)
    return Decimal(coefficient).scaleb(-STORED_SCALE)


@guarded
def divide_money(value: Money, divisor: int, *, rounding: RoundingDirection) -> Money:
    value = _money(value)
    divisor = _integer(divisor, 200)
    return Money(_ratio(_coefficient(value.amount), divisor, rounding), value.currency)


@guarded
def weighted_mean_money(
    terms: Sequence[tuple[Money, int]], *, rounding: RoundingDirection
) -> Money:
    if not 1 <= len(terms) <= 200:
        raise InvalidInputTypeError("bounded terms required")
    currency = _money(terms[0][0]).currency
    numerator = total = 0
    for value, weight in terms:
        value = _money(value)
        weight = _integer(weight, 201)
        if value.currency != currency:
            raise UnitMismatchError("different currencies")
        total += weight
        numerator += _coefficient(value.amount) * weight
    _integer(total, 201)
    return Money(_ratio(numerator, total, rounding), currency)


@guarded
def percentage_share(part: Money, other: Money, *, rounding: RoundingDirection) -> Scalar:
    part, other = _money(part), _money(other)
    if part.currency != other.currency:
        raise UnitMismatchError("different currencies")
    p, o = _coefficient(part.amount), _coefficient(other.amount)
    if p < 0 or o < 0 or p + o == 0:
        raise InvalidInputTypeError("nonnegative nonzero share required")
    return Scalar(_ratio(100 * p * _coefficient(Decimal(1)), p + o, rounding))
