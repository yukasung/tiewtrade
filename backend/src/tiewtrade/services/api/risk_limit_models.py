"""Strict risk input/output contracts shared by middleware and owner routes."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskScope
from tiewtrade.infra.risk_limits.records import MAX_RISK_REVISION, RiskAction, RiskSubmission


class RiskExpectedScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: StrictInt = Field(ge=0, le=MAX_RISK_REVISION)
    expected_wallet_id: UUID | None = None
    expected_episode_id: UUID | None = None


class RiskLimitMutation(RiskExpectedScope):
    amount: StrictStr = Field(min_length=1, max_length=256)


class RiskRequestView(BaseModel):
    receipt_id: UUID
    mode: Literal["PAPER", "LIVE"]
    action: Literal["SET", "DECREASE", "INCREASE", "RESET"]
    idempotency_key: UUID
    amount: str | None
    expected_revision: int
    expected_wallet_id: UUID | None
    expected_episode_id: UUID | None
    state: Literal["AUTHORIZATION_ONLY", "REQUEST_PENDING", "APPLIED", "REJECTED"]
    applied_revision: int | None
    failure_code: str | None
    recorded_at: str


class RiskLimitView(BaseModel):
    mode: Literal["PAPER", "LIVE"]
    amount: str | None
    currency: Literal["USDT"] = "USDT"
    revision: int
    wallet_id: UUID | None
    episode_id: UUID | None
    latched: bool
    loss: str | None
    reason: str
    source_revision: int | None
    evaluated_at: str | None
    snapshot_at: str
    stop_id: UUID | None = None
    effects_revision: int | None = None
    target_count: int | None = None
    pending_count: int | None = None
    failed_count: int | None = None
    target_set_complete: bool | None = None
    stop_progress: Literal["STOPPING", "STOPPED", "PROBLEMS"] | None = None
    stop_alert_due: bool = False
    baseline_id: UUID | None = None
    baseline_source_revision: int | None = None
    baseline_at: str | None = None
    current_allowance: str | None = None
    adjusted_realized: str | None = None
    price_watermark: int | None = None
    input_ready_at: str | None = None
    unavailable_since: str | None = None
    pause_alert_due: bool = False


class RiskEffectView(BaseModel):
    target_kind: Literal["REQUEST", "COMMAND", "ORDER"]
    target_id: UUID
    order_id: UUID
    state: Literal[
        "PENDING", "CANCEL_PENDING", "CANCELED", "FILLED", "REJECTED", "ALREADY_TERMINAL", "FAILED"
    ]
    attempt: int
    details: dict[str, str]
    recorded_at: str


class RiskEffectPage(BaseModel):
    stop_id: UUID
    mode: Literal["PAPER", "LIVE"]
    effects_revision: int
    snapshot_at: str
    next_cursor: str | None
    items: list[RiskEffectView]


def risk_submission(
    *,
    owner: UUID,
    mode: TradingMode,
    key: UUID,
    body: RiskExpectedScope,
    increase: bool = False,
) -> RiskSubmission:
    scope = RiskScope(UUID(str(owner)), mode, body.expected_wallet_id, body.expected_episode_id)
    if isinstance(body, RiskLimitMutation):
        amount = Money.of(body.amount, "USDT")
        action = (
            RiskAction.INCREASE
            if increase
            else RiskAction.SET
            if body.expected_revision == 0
            else RiskAction.DECREASE
        )
    else:
        amount = None
        action = RiskAction.RESET
    return RiskSubmission(scope, action, key, body.expected_revision, amount)
