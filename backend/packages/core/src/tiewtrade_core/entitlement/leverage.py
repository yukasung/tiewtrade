"""Effective Max Leverage: the Plan capped by Binance's own bracket (§5.3, FR-PLN-06)."""

from decimal import Decimal

from tiewtrade_core._decimal import calc
from tiewtrade_core.market import LeverageBrackets


@calc
def effective_max_leverage(
    plan_max_leverage: int, brackets: LeverageBrackets, notional: Decimal
) -> int:
    """min(Plan Max Leverage, the bracket's max leverage at ``notional``) (§5.3).

    Checked both when the leverage is set and again when an order that opens or adds to a
    position is sent, because the second is the only place a value set outside the
    platform can be caught (FR-PLN-06).

    ``notional`` is the notional the order would produce, not the current one: a larger
    position falls into a higher bracket, where Binance itself allows less leverage.
    """
    if plan_max_leverage < 1:
        raise ValueError("plan max leverage must be at least 1")
    return min(plan_max_leverage, brackets.for_notional(notional).max_leverage)


def within_leverage(
    leverage: int, plan_max_leverage: int, brackets: LeverageBrackets, notional: Decimal
) -> bool:
    """Whether ``leverage`` is allowed (``ENTITLEMENT_LEVERAGE_EXCEEDED``)."""
    if leverage < 1:
        raise ValueError("leverage must be at least 1")
    return leverage <= effective_max_leverage(plan_max_leverage, brackets, notional)
