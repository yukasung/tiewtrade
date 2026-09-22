from dataclasses import dataclass
from decimal import Decimal

from fasttrade_core._decimal import ZERO, calc
from fasttrade_core.market import OrderSide


@dataclass(frozen=True, slots=True)
class FuturesPosition:
    """One-way position of one symbol (calculation spec §2.6).

    ``quantity`` is signed (+ Long, - Short). ``episode_id`` identifies the Position
    Episode that owns the results while the position is open (FR-PF-11).
    """

    quantity: Decimal
    entry_price: Decimal | None
    episode_id: str | None

    def __post_init__(self) -> None:
        flat = self.quantity == 0
        if flat != (self.entry_price is None) or flat != (self.episode_id is None):
            raise ValueError("a flat position has no entry price or episode; an open one has both")

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0


FLAT = FuturesPosition(quantity=ZERO, entry_price=None, episode_id=None)


@dataclass(frozen=True, slots=True)
class FuturesFillResult:
    position: FuturesPosition
    realized_pnl: Decimal  # gross, excludes fees and funding
    closed_quantity: Decimal  # part of the fill that reduced / closed the previous position
    opened_quantity: Decimal  # part of the fill that opened or increased a position
    closed_episode_id: str | None  # episode that ended with this fill
    opened_episode_id: str | None  # episode that started with this fill


@calc
def apply_futures_fill(
    position: FuturesPosition,
    side: OrderSide,
    quantity: Decimal,
    price: Decimal,
    *,
    new_episode_id: str,
) -> FuturesFillResult:
    """Apply one fill to a One-way position.

    - Same direction: weighted average entry, same episode.
    - Opposite direction up to the size: realized PnL, entry unchanged; closing to zero
      ends the episode.
    - Opposite direction beyond the size (flip): close the whole position first, then
      open the remainder at the fill price in a new episode.

    ``new_episode_id`` is used only if this fill opens an episode; the caller supplies
    it so the core stays deterministic.
    """
    if quantity <= 0 or price <= 0:
        raise ValueError("fill quantity and price must be positive")
    signed_fill = side.sign * quantity

    if position.is_flat:
        opened = FuturesPosition(signed_fill, price, new_episode_id)
        return FuturesFillResult(opened, ZERO, ZERO, quantity, None, new_episode_id)

    # Guaranteed by FuturesPosition.__post_init__ for an open position.
    assert position.entry_price is not None
    assert position.episode_id is not None
    same_direction = (position.quantity > 0) == (signed_fill > 0)
    size = abs(position.quantity)

    if same_direction:
        entry = (size * position.entry_price + quantity * price) / (size + quantity)
        grown = FuturesPosition(position.quantity + signed_fill, entry, position.episode_id)
        return FuturesFillResult(grown, ZERO, ZERO, quantity, None, None)

    closing = min(quantity, size)
    side_of_position = 1 if position.quantity > 0 else -1
    realized = closing * (price - position.entry_price) * side_of_position
    remaining = quantity - closing

    if closing < size:
        reduced = FuturesPosition(
            position.quantity + signed_fill, position.entry_price, position.episode_id
        )
        return FuturesFillResult(reduced, realized, closing, ZERO, None, None)

    if remaining == 0:
        return FuturesFillResult(FLAT, realized, closing, ZERO, position.episode_id, None)

    flipped = FuturesPosition(side.sign * remaining, price, new_episode_id)
    return FuturesFillResult(
        flipped, realized, closing, remaining, position.episode_id, new_episode_id
    )
