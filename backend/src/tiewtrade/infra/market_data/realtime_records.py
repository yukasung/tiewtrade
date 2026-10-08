"""Typed durable realtime state; no network or session identity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tiewtrade.core.realtime_prices import QuoteObservation


@dataclass(frozen=True, slots=True)
class FeedLease:
    source: str
    generation: int
    owner: UUID
    lease_until: datetime
    connected: bool = False
    last_failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class StoredPrice:
    source: str
    base: str
    quote: str
    observation: QuoteObservation | None = None
    reconciled_generation: int = 0
    revision: int = 1
    effective_readiness: str = "MISSING"
    reason: str | None = None
    unavailable_since: datetime | None = None
    order_ambiguous_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    feed: FeedLease | None
    rows: tuple[StoredPrice, ...]
    server_time: datetime


class WriterLeaseLost(Exception):  # noqa: N818
    """The producer must stop writing and close its upstream."""
