"""Exact single-basket targets; F-21 requirements RQ-11.

Keep the weighted products as integer ratios until the final tick rounding.
Rounding each entry's notional first can move a target across a tick boundary.
"""

from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction

from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import InvalidInputTypeError, UnitMismatchError
from tiewtrade.core.money.limits import STORED_SCALE
from tiewtrade.core.money.position_arithmetic import _coefficient
from tiewtrade.core.money.rounding import RoundingDirection, rounded_quotient
from tiewtrade.core.money.types import Money, Quantity


@guarded
def basket_take_profit(
    entries: Sequence[tuple[Money, Quantity]],
    atr: Money,
    tick: Money,
    *,
    held: Money | None = None,
    entry_costs: Sequence[tuple[Money, Quantity]] | None = None,
) -> Money:
    """Floor once to ticks; optional execution costs avoid rounded average prices.

    Each cost pair is the gross quote notional and gross base quantity for the
    corresponding entry. Weight their exact ratio by its remaining net quantity.
    """
    if type(atr) is not Money or type(tick) is not Money or not entries:
        raise InvalidInputTypeError("entries and Money ATR/tick required")
    if atr.currency != tick.currency:
        raise UnitMismatchError("target currencies differ")
    if atr.amount < 0 or tick.amount <= 0:
        raise InvalidInputTypeError("nonnegative ATR and positive tick required")
    if entry_costs is not None and len(entry_costs) != len(entries):
        raise InvalidInputTypeError("one cost basis per entry required")
    asset: str | None = None
    quantity_sum = 0
    notional_sum = Fraction(0)
    scale = _coefficient(Money.of(1, tick.currency))
    for index, (price, quantity) in enumerate(entries):
        if type(price) is not Money or type(quantity) is not Quantity:
            raise InvalidInputTypeError("Money price and Quantity required")
        if price.currency != tick.currency or (asset is not None and quantity.asset != asset):
            raise UnitMismatchError("basket units differ")
        if price.amount <= 0 or quantity.amount <= 0:
            raise InvalidInputTypeError("positive open entry amounts required")
        asset = quantity.asset
        quantity_sum += _coefficient(quantity)
        price_coefficient = Fraction(_coefficient(price))
        if entry_costs is not None:
            notional, gross = entry_costs[index]
            if type(notional) is not Money or type(gross) is not Quantity:
                raise InvalidInputTypeError("Money notional and Quantity gross required")
            if notional.currency != tick.currency or gross.asset != quantity.asset:
                raise UnitMismatchError("entry cost units differ")
            if notional.amount <= 0 or gross.amount <= 0:
                raise InvalidInputTypeError("positive entry costs required")
            price_coefficient = Fraction(_coefficient(notional) * scale, _coefficient(gross))
        notional_sum += price_coefficient * _coefficient(quantity)
    target_ticks = (notional_sum + 3 * _coefficient(atr) * quantity_sum) / (
        quantity_sum * _coefficient(tick)
    )
    ticks = rounded_quotient(
        target_ticks.numerator,
        target_ticks.denominator,
        RoundingDirection.TOWARD_NEGATIVE,
    )
    candidate = Money(Decimal(ticks * _coefficient(tick)).scaleb(-STORED_SCALE), tick.currency)
    if candidate.amount <= 0:
        raise InvalidInputTypeError("target rounds to zero")
    if held is not None:
        if type(held) is not Money or held.amount <= 0:
            raise InvalidInputTypeError("positive Money held target required")
        if held.currency != tick.currency:
            raise UnitMismatchError("held target currency differs")
        return min(candidate, held)
    return candidate
