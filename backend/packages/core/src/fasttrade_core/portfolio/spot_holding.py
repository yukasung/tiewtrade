from dataclasses import dataclass
from decimal import Decimal

from fasttrade_core._decimal import ZERO, calc


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
    if quantity <= 0 or price <= 0:
        raise ValueError("fill quantity and price must be positive")
    received = quantity * (1 - fee_rate)
    fee_value = quantity * fee_rate * price
    if holding.quantity == 0:
        return SpotBuyResult(
            SpotHolding(received, price, new_episode_id),
            received,
            quantity * price,
            fee_value,
            new_episode_id,
        )
    assert holding.average_cost is not None
    total = holding.quantity + received
    cost = (holding.quantity * holding.average_cost + received * price) / total
    return SpotBuyResult(
        SpotHolding(total, cost, holding.episode_id),
        received,
        quantity * price,
        fee_value,
        None,
    )


@calc
def apply_spot_sell(
    holding: SpotHolding, quantity: Decimal, price: Decimal, fee_rate: Decimal
) -> SpotSellResult:
    """Sell with the fee deducted from the received Quote Asset (Verify C-06)."""
    if quantity <= 0 or price <= 0:
        raise ValueError("fill quantity and price must be positive")
    if quantity > holding.quantity:
        raise ValueError("cannot sell more than the holding")
    # Guaranteed by SpotHolding.__post_init__ for a non-empty holding.
    assert holding.average_cost is not None
    assert holding.episode_id is not None
    gross = quantity * price
    fee = gross * fee_rate
    realized = quantity * (price - holding.average_cost)
    left = holding.quantity - quantity
    if left == 0:
        return SpotSellResult(NO_HOLDING, realized, gross - fee, fee, holding.episode_id)
    return SpotSellResult(
        SpotHolding(left, holding.average_cost, holding.episode_id),
        realized,
        gross - fee,
        fee,
        None,
    )
