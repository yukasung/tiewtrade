from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TopOfBook:
    """Best bid and ask supplied by the caller (FR-ORD-13).

    The core does not judge whether a snapshot is sane: it computes from what it is
    given. A stale or volatile snapshot can arrive crossed or locked, so the three
    predicates below let the Paper adapter drop it before asking for a fill.
    """

    best_bid: Decimal
    best_ask: Decimal

    def __post_init__(self) -> None:
        if self.best_bid <= 0 or self.best_ask <= 0:
            raise ValueError("best bid and ask must be positive")

    @property
    def is_crossed(self) -> bool:
        """Bid above ask — the book is inverted."""
        return self.best_bid > self.best_ask

    @property
    def is_locked(self) -> bool:
        """Bid equal to ask — no spread."""
        return self.best_bid == self.best_ask

    @property
    def is_abnormal(self) -> bool:
        """Crossed or locked. Callers filtering snapshots should test this, not ``is_crossed``."""
        return self.is_crossed or self.is_locked
