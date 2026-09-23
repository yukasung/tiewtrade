from decimal import Decimal
from enum import StrEnum

from tiewtrade_core.market import OrderSide


class BracketLeg(StrEnum):
    """Which protective leg of a Bracket fired (FR-ORD-15)."""

    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


def _is_long(position_quantity: Decimal) -> bool:
    """True for a Long, False for a Short; a flat position is rejected.

    Checked explicitly rather than with ``assert``, which ``python -O`` removes.
    """
    if position_quantity == 0:
        raise ValueError("position is flat")
    return position_quantity > 0


def stop_loss_triggered(
    position_quantity: Decimal, last_price: Decimal, stop_price: Decimal
) -> bool:
    """Long fires at ``LP <= SL``, Short at ``LP >= SL`` (calculation spec §4.3).

    Written as a direct comparison per side rather than a signed arithmetic shortcut.
    Subtracting or multiplying here would run in the caller's Decimal context instead of
    the core's, so a caller trapping Inexact could make a plain comparison raise. Touching
    the trigger fires it, unlike a resting limit in ``fills.py``, which needs the price to
    go through.
    """
    if _is_long(position_quantity):
        return last_price <= stop_price
    return last_price >= stop_price


def take_profit_triggered(
    position_quantity: Decimal, last_price: Decimal, take_profit_price: Decimal
) -> bool:
    """Long fires at ``LP >= TP``, Short at ``LP <= TP`` (calculation spec §4.3).

    The mirror of ``stop_loss_triggered``. Do not collapse the two by negating the
    quantity: unary minus on a ``Decimal`` is arithmetic in the caller's context, which is
    what the per-side comparisons exist to avoid.
    """
    if _is_long(position_quantity):
        return last_price >= take_profit_price
    return last_price <= take_profit_price


def triggered_leg(
    position_quantity: Decimal,
    last_price: Decimal,
    *,
    stop_loss_price: Decimal | None,
    take_profit_price: Decimal | None,
) -> BracketLeg | None:
    """The leg that fires at ``last_price``, or None (calculation spec §4.3).

    Stop loss wins when both conditions hold at once, which a correctly placed Bracket
    never produces but a mis-set one or a gapping price can. This matches §4.5, where a
    candle touching both resolves to the stop loss (Decided C-09), and keeps Paper from
    looking better than reality (D-05).

    Cancelling the surviving leg is the Order Manager's job (FR-ORD-15, R-16); this
    function only reports which leg fired.
    """
    _is_long(position_quantity)  # the only flat-position check when both legs are None
    if stop_loss_price is not None and stop_loss_triggered(
        position_quantity, last_price, stop_loss_price
    ):
        return BracketLeg.STOP_LOSS
    if take_profit_price is not None and take_profit_triggered(
        position_quantity, last_price, take_profit_price
    ):
        return BracketLeg.TAKE_PROFIT
    return None


def closing_side(position_quantity: Decimal) -> OrderSide:
    """Side that reduces the position: SELL for a Long, BUY for a Short."""
    return OrderSide.SELL if _is_long(position_quantity) else OrderSide.BUY
