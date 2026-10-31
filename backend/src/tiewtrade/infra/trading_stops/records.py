"""Typed records for the F-19 durable stop inbox and status views."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tiewtrade.core.orders import TradingMode
from tiewtrade.core.trading_stops import StopAction, StopCause, StopProgress


class StopConflictError(ValueError):
    code = "TRADING_STOP_CONFLICT"


@dataclass(frozen=True, slots=True)
class StopReceipt:
    request_id: UUID
    user_id: UUID
    mode: TradingMode | None
    action: StopAction
    cause: StopCause
    idempotency_key: UUID
    generation: int
    revision: int
    stop_id: UUID
    recorded_at: datetime
    state: str
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class StopStatus:
    mode: TradingMode
    stop_id: UUID | None
    cause: StopCause | None
    generation: int | None
    revision: int
    summary_revision: int
    progress: StopProgress | None
    target_set_complete: bool
    target_count: int
    pending_count: int
    failed_count: int
    platform_stop_id: UUID | None
    platform_reason: str | None
    resume_ready: bool
    reconciliation_revision: int | None
