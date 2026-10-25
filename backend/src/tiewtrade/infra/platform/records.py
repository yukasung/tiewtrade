"""Typed persistence records for the supported-symbol catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from tiewtrade.core.market_catalog import CatalogSnapshot


class PlatformRole(Enum):
    ADMIN = "PLATFORM_ADMIN"
    OWNER = "PLATFORM_OWNER"


class CatalogStatus(Enum):
    REQUESTED = "REQUESTED"
    PREPARING = "PREPARING"
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"
    FAILED = "FAILED"


class CatalogAction(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"


class CatalogReason(Enum):
    LIQUIDITY_REVIEWED = "ADMIN_LIQUIDITY_REVIEWED"
    RISK_REVIEW = "ADMIN_RISK_REVIEW"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    base: str
    quote: str
    status: CatalogStatus
    revision: int
    updated_at: datetime
    effect: CatalogEffect | None = None


@dataclass(frozen=True, slots=True)
class CatalogEffect:
    status: str
    attempts: int
    bots_stopped: int
    commands_rejected: int
    orders_canceled: int
    orders_unresolved: int
    error_code: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogView:
    snapshot: CatalogSnapshot
    entries: tuple[CatalogEntry, ...]
    mutations_enabled: bool


@dataclass(frozen=True, slots=True)
class CatalogCommand:
    id: UUID
    action: CatalogAction
    base: str
    quote: str
    state: str
    revision: int | None
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ImpactPreview:
    base: str
    quote: str
    bots: int
    open_entry_orders: int
    protective_orders: int
    reduce_risk_orders: int
    positions: int
    complete: bool
    snapshot_at: datetime


@dataclass(frozen=True, slots=True)
class ConstraintEvidence:
    venue_symbol: str
    observed_at: datetime
    source_document: str
    digest: str
