from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.portfolio._fill import require_positive_fill


@dataclass(frozen=True, slots=True)
class SpotHolding:
    """Base Asset held by a Spot Portfolio (Long only, D-10) with its Average Cost.

    Average Cost excludes fees (C-07); fees are recorded separately so Realized PnL
    stays gross and fees are never counted twice (calculation spec §3.1).
    """

    quantity: Decimal
    average_cost: Decimal | None
    episode_id: str | None

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("spot holding cannot be negative")
        empty = self.quantity == 0
        if empty != (self.average_cost is None) or empty != (self.episode_id is None):
            raise ValueError("an empty holding has no cost or episode; a non-empty one has both")

    def open_details(self) -> tuple[Decimal, str]:
        """Average cost and episode of a non-empty holding; raises if it is empty.

        Checked explicitly rather than with ``assert``, which ``python -O`` removes.
        """
        if self.average_cost is None or self.episode_id is None:
            raise ValueError("holding is empty")
        return self.average_cost, self.episode_id


NO_HOLDING = SpotHolding(quantity=ZERO, average_cost=None, episode_id=None)


@dataclass(frozen=True, slots=True)
class SpotBuyResult:
    holding: SpotHolding
    received_quantity: Decimal  # after the fee paid in the Base Asset
    quote_spent: Decimal
    fee_quote_value: Decimal  # fee in Base Asset valued at the fill price, for the ledger
    opened_episode_id: str | None


@dataclass(frozen=True, slots=True)
class SpotSellResult:
    holding: SpotHolding
    realized_pnl: Decimal  # gross
    quote_received: Decimal  # after the fee paid in the Quote Asset
    fee: Decimal
    closed_episode_id: str | None


@calc
def apply_spot_buy(
    holding: SpotHolding,
    quantity: Decimal,
    price: Decimal,
    fee_rate: Decimal,
    *,
    new_episode_id: str,
) -> SpotBuyResult:
    """Buy with the fee deducted from the received Base Asset (Verify C-06)."""
    require_positive_fill(quantity, price)
    received = quantity * (1 - fee_rate)
    fee_value = quantity * fee_rate * price
    if holding.quantity == 0:
        return SpotBuyResult(
            holding=SpotHolding(received, price, new_episode_id),
            received_quantity=received,
            quote_spent=quantity * price,
            fee_quote_value=fee_value,
            opened_episode_id=new_episode_id,
        )
    average_cost, episode_id = holding.open_details()
    total = holding.quantity + received
    new_cost = (holding.quantity * average_cost + received * price) / total
    return SpotBuyResult(
        holding=SpotHolding(total, new_cost, episode_id),
        received_quantity=received,
        quote_spent=quantity * price,
        fee_quote_value=fee_value,
        opened_episode_id=None,
    )


@calc
def apply_spot_sell(
    holding: SpotHolding, quantity: Decimal, price: Decimal, fee_rate: Decimal
) -> SpotSellResult:
    """Sell with the fee deducted from the received Quote Asset (Verify C-06)."""
    require_positive_fill(quantity, price)
    if quantity > holding.quantity:
        raise ValueError("cannot sell more than the holding")
    average_cost, episode_id = holding.open_details()
    gross = quantity * price
    fee = gross * fee_rate
    left = holding.quantity - quantity
    return SpotSellResult(
        holding=SpotHolding(left, average_cost, episode_id) if left else NO_HOLDING,
        realized_pnl=quantity * (price - average_cost),
        quote_received=gross - fee,
        fee=fee,
        closed_episode_id=None if left else episode_id,
    )
