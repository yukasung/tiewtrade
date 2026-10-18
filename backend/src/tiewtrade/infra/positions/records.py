"""Immutable records for the Paper position persistence boundary (F-14)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import PositionAvailability, PositionPair, PositionState
from tiewtrade.infra.db.errors import InfraError


class PositionEventKind(Enum):
    RECORD = "RECORD"
    REPLACE = "REPLACE"
    VOID = "VOID"


class PositionWriteStatus(Enum):
    APPLIED = "APPLIED"
    REPLAYED = "REPLAYED"
    CONFLICTED = "CONFLICTED"


class PositionStorageError(InfraError):
    code = "POSITION_STORAGE_ERROR"


class PositionIntegrityError(PositionStorageError):
    code = "POSITION_INTEGRITY"


@dataclass(frozen=True, slots=True)
class PositionActivity:
    episode_id: UUID
    wallet_id: UUID
    user_id: UUID
    mode: str
    availability: PositionAvailability
    source_sequence: int
    revision: int
    source_proof: str | None
    observed_at: datetime | None
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class PairEconomicEffects:
    pair: PositionPair
    base_delta: Quantity
    quote_cash_delta: Money
    external_asset_effects: tuple[Quantity, ...]


@dataclass(frozen=True, slots=True)
class PositionWriteResult:
    status: PositionWriteStatus
    event_id: UUID
    activity: PositionActivity
    effects: PairEconomicEffects | None = None
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    activity: PositionActivity
    positions: tuple[PositionState, ...]
    snapshot_at: datetime

    def __post_init__(self) -> None:
        if self.snapshot_at.tzinfo is None:
            raise PositionIntegrityError("snapshot time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PositionValuation:
    state: PositionState
    unrealized_pnl: Money | None
    reason: str | None
    price_at: datetime | None
    price_revision: int | None

    def __post_init__(self) -> None:
        if (self.unrealized_pnl is None) == (self.reason is None):
            raise PositionIntegrityError("valuation requires exactly one result or reason")
        if self.unrealized_pnl is not None and (
            self.unrealized_pnl.currency != self.state.pair.quote
        ):
            raise PositionIntegrityError("valuation currency does not match position")
        if self.price_at is not None and self.price_at.tzinfo is None:
            raise PositionIntegrityError("price time must be timezone-aware")
        if self.price_revision is not None and self.price_revision <= 0:
            raise PositionIntegrityError("price revision must be positive")


@dataclass(frozen=True, slots=True)
class ValuedPositionSnapshot:
    activity: PositionActivity
    positions: tuple[PositionValuation, ...]
    snapshot_at: datetime

    def __post_init__(self) -> None:
        if self.snapshot_at.tzinfo is None:
            raise PositionIntegrityError("snapshot time must be timezone-aware")
