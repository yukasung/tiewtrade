"""Strict HTTP contracts for the F-19 kill switch."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

OwnerStopCause = Literal["USER", "SYSTEM", "LOSS_LIMIT"]


class StopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResumeStopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_stop_id: UUID
    expected_revision: StrictInt = Field(ge=1)
    expected_summary_revision: StrictInt = Field(ge=0)
    expected_reconciliation_revision: StrictInt = Field(ge=0)


class PlatformStopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: StrictStr = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("platform stop reason is blank")
        return value


class StopRequestView(BaseModel):
    request_id: UUID
    stop_id: UUID
    mode: Literal["PAPER", "LIVE", "PLATFORM"]
    action: Literal["STOP", "RESUME"]
    cause: Literal["USER", "SYSTEM", "LOSS_LIMIT", "PLATFORM"]
    generation: int
    revision: int
    state: Literal["REQUEST_PENDING", "APPLIED", "REJECTED"]
    failure_code: str | None
    recorded_at: str


class KillSwitchStatusView(BaseModel):
    mode: Literal["PAPER", "LIVE"]
    stop_id: UUID | None
    cause: Literal["USER", "SYSTEM", "LOSS_LIMIT", "PLATFORM"] | None
    generation: int | None
    revision: int
    summary_revision: int
    progress: Literal["STOPPING", "STOPPED", "PROBLEMS"] | None
    target_set_complete: bool
    target_count: int
    pending_count: int
    failed_count: int
    platform_stop_id: UUID | None
    platform_reason: str | None
    resume_ready: bool
    reconciliation_revision: int | None
    capability: Literal["AVAILABLE", "LIVE_EXECUTION_UNAVAILABLE"]
    active_causes: list[OwnerStopCause] = Field(default_factory=list)


class StopSummaryView(BaseModel):
    status: KillSwitchStatusView
    positions: list[dict[str, str]]
    snapshot_revision: int
    reconciled_at: str | None


class PlatformStatusView(BaseModel):
    stop_id: UUID | None
    revision: int
    summary_revision: int
    reconciliation_revision: int
    reason: str | None
    progress: Literal["STOPPING", "STOPPED", "PROBLEMS"] | None
    discovery_complete: bool
    owner_count: int
    pending_count: int
    failed_count: int
    can_resume: bool
