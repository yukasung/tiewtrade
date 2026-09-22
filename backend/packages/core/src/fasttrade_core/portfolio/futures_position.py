from dataclasses import dataclass
from decimal import Decimal

from fasttrade_core._decimal import ZERO, calc
from fasttrade_core.market import OrderSide
from fasttrade_core.portfolio._fill import require_positive_fill


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

    def open_details(self) -> tuple[Decimal, str]:
        """Entry price and episode of an open position; raises if the position is flat.

        Checked explicitly rather than with ``assert``, which ``python -O`` removes.
        """
        if self.entry_price is None or self.episode_id is None:
            raise ValueError("position is flat")
        return self.entry_price, self.episode_id


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
    require_positive_fill(quantity, price)
    signed_fill = side.sign * quantity

    if position.is_flat:
        return FuturesFillResult(
            position=FuturesPosition(signed_fill, price, new_episode_id),
            realized_pnl=ZERO,
            closed_quantity=ZERO,
            opened_quantity=quantity,
            closed_episode_id=None,
            opened_episode_id=new_episode_id,
        )

    entry_price, episode_id = position.open_details()
    same_direction = (position.quantity > 0) == (signed_fill > 0)
    size = abs(position.quantity)

    if same_direction:
        average_entry = (size * entry_price + quantity * price) / (size + quantity)
        return FuturesFillResult(
            position=FuturesPosition(position.quantity + signed_fill, average_entry, episode_id),
            realized_pnl=ZERO,
            closed_quantity=ZERO,
            opened_quantity=quantity,
            closed_episode_id=None,
            opened_episode_id=None,
        )

    closing = min(quantity, size)
    side_of_position = 1 if position.quantity > 0 else -1
    realized = closing * (price - entry_price) * side_of_position
    remaining = quantity - closing

    if closing < size:
        return FuturesFillResult(
            position=FuturesPosition(position.quantity + signed_fill, entry_price, episode_id),
            realized_pnl=realized,
            closed_quantity=closing,
            opened_quantity=ZERO,
            closed_episode_id=None,
            opened_episode_id=None,
        )

    if remaining == 0:
        return FuturesFillResult(
            position=FLAT,
            realized_pnl=realized,
            closed_quantity=closing,
            opened_quantity=ZERO,
            closed_episode_id=episode_id,
            opened_episode_id=None,
        )

    return FuturesFillResult(
        position=FuturesPosition(side.sign * remaining, price, new_episode_id),
        realized_pnl=realized,
        closed_quantity=closing,
        opened_quantity=remaining,
        closed_episode_id=episode_id,
        opened_episode_id=new_episode_id,
    )
