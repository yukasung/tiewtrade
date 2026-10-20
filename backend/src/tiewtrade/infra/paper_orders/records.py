"""Immutable identities for owner-bound replay evidence."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tiewtrade.infra.market_data.order_book_storage import StoredExecutionInput


@dataclass(frozen=True, slots=True)
class SavedExecutionInput:
    evidence_id: UUID
    recorded_at: datetime
    episode_id: UUID
    record: StoredExecutionInput
    digest: str


@dataclass(frozen=True, slots=True)
class OrderSourceInitialization:
    episode_id: UUID
    wallet_id: UUID
    initialization_id: UUID
    source_proof: str
    position_proof: str
    initialized_at: datetime
