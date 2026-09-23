from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum

from tiewtrade_core._decimal import calc


class Rounding(Enum):
    DOWN = ROUND_FLOOR  # toward -infinity
    UP = ROUND_CEILING  # toward +infinity


@calc
def round_to_increment(value: Decimal, increment: Decimal, rounding: Rounding) -> Decimal:
    """Round ``value`` to a multiple of ``increment`` (tickSize / stepSize, calculation spec §6).

    Works for any positive increment, not only powers of ten.
    """
    if increment <= 0:
        raise ValueError("increment must be positive")
    units = (value / increment).to_integral_value(rounding=rounding.value)
    return (units * increment).quantize(increment)


@calc
def is_multiple_of(value: Decimal, increment: Decimal) -> bool:
    return value % increment == 0
