from decimal import Decimal

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.market import LeverageBracket, LeverageBrackets


@calc
def _price_for_bracket(
    quantity: Decimal,
    entry_price: Decimal,
    wallet_balance: Decimal,
    other_maintenance_margin: Decimal,
    other_unrealized_pnl: Decimal,
    tier: LeverageBracket,
) -> Decimal:
    size = abs(quantity)
    side = 1 if quantity > 0 else -1
    numerator = (
        wallet_balance
        - other_maintenance_margin
        + other_unrealized_pnl
        + tier.maintenance_amount
        - side * size * entry_price
    )
    denominator = size * tier.maintenance_margin_rate - side * size
    return numerator / denominator


@calc
def liquidation_price(
    quantity: Decimal,
    entry_price: Decimal,
    wallet_balance: Decimal,
    brackets: LeverageBrackets,
    *,
    other_maintenance_margin: Decimal = ZERO,
    other_unrealized_pnl: Decimal = ZERO,
) -> Decimal | None:
    """Liquidation Price for One-way mode (calculation spec §2.5, Verify C-02).

    Solves ``Margin Balance = Maintenance Margin`` for the Mark Price of this position,
    holding every other position constant. Within one bracket:

        LP = (WB - TMM1 + UPNL1 + cum - side * |Q| * EP) / (|Q| * MMR - side * |Q|)

    Isolated: pass the isolated wallet as ``wallet_balance`` and leave the ``other_*``
    arguments at zero. Cross: pass the cross wallet balance plus the maintenance margin
    and unrealized PnL of all other cross positions.

    ``Margin Balance - Maintenance Margin`` is strictly monotonic in the price (MMR < 1)
    and continuous across brackets (``cum`` makes MM continuous), so at most one price
    solves it. Each bracket is solved and the answer is the positive price whose notional
    falls inside the bracket that produced it. Every bracket is checked because the
    solution can lie in a lower bracket than the one at the current notional.

    Returns None when there is no position or no positive price solves the equation.
    That happens in two opposite situations, which callers distinguish with
    ``MarginState.is_liquidatable`` (the authoritative condition, calculation spec §2.4):

    - the position is never liquidated by price moves (a Long whose margin covers a fall
      to zero), or
    - the account is already liquidatable at every price (e.g. cross losses on other
      positions exceed the wallet).
    """
    if quantity == 0:
        return None
    size = abs(quantity)
    for tier in brackets.tiers:
        price = _price_for_bracket(
            quantity,
            entry_price,
            wallet_balance,
            other_maintenance_margin,
            other_unrealized_pnl,
            tier,
        )
        if price > 0 and brackets.for_notional(size * price).bracket == tier.bracket:
            return price
    return None
