"""Owner-scoped HTTP contracts for F-20."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from tiewtrade.core.bots import BotStatus
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.protections import ProtectionState


class BotReplacementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    run_revision: StrictInt = Field(ge=1)
    stop_id: UUID | None = None
    stop_revision: StrictInt | None = Field(default=None, ge=1)
    summary_revision: StrictInt = Field(ge=0)
    reconciliation_revision: StrictInt = Field(ge=0)


class BotStartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_config_ref: StrictStr = Field(min_length=1, max_length=128)
    replacement: BotReplacementInput | None = None


class BotPositionView(BaseModel):
    base: str
    quote: str
    quantity: str


class BotProtectionView(BaseModel):
    protection_id: UUID
    base: str
    quantity: str
    state: ProtectionState
    conflicted: bool
    failure_code: str | None


class BotStatusView(BaseModel):
    mode: TradingMode
    snapshot_at: datetime
    pending_request_id: UUID | None
    run_id: UUID | None
    status: BotStatus | None
    revision: int | None
    strategy_name: str | None
    strategy_version: int | None
    configuration_version: int | None
    stop_reason: (
        Literal[
            "USER", "SYSTEM", "LOSS_LIMIT", "PLATFORM", "PROTECTION_SETUP_FAILED", "CATALOG_REMOVED"
        ]
        | None
    )
    can_start: bool
    unavailable_reason: str | None
    exposure_available: bool
    positions: list[BotPositionView]
    protections: list[BotProtectionView]
    protections_more: bool
    readiness_reason: str | None


class BotReceiptView(BaseModel):
    request_id: UUID
    mode: TradingMode
    key: UUID
    run_id: UUID | None
    failure_code: str | None
    pending: bool
