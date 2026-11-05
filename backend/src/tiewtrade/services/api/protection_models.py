"""Strict owner-protection inputs and public generated response contracts."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from tiewtrade.services.api.manual_order_models import (
    AmountText,
    ExpectedPaperEpisode,
    ProtectionPricesInput,
)


class ProtectionCreateInput(ExpectedPaperEpisode, ProtectionPricesInput):
    base: Annotated[StrictStr, Field(pattern=r"^[A-Z][A-Z0-9]{0,19}$")]
    quantity: AmountText

    @model_validator(mode="after")
    def distinct_pair(self) -> Self:
        if self.base == "USDT":
            raise ValueError("base and quote must differ")
        return self


class ProtectionReplaceInput(ExpectedPaperEpisode, ProtectionPricesInput):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    quantity: AmountText


class ProtectionCancelInput(ExpectedPaperEpisode):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


class ProtectionView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protection_id: UUID
    wallet_id: UUID
    episode_id: UUID
    mode: Literal["PAPER"] = "PAPER"
    base: str
    quote: Literal["USDT"] = "USDT"
    quantity: str
    protected_quantity: str
    state: str
    revision: int
    take_profit_price: str | None
    stop_loss_price: str | None
    entry_order_id: UUID | None
    exit_order_id: UUID | None = None
    exit_order_state: str | None = None
    exit_command_state: str | None = None
    exit_quantity: str | None = None
    exit_filled_quantity: str | None = None
    conflicted: bool
    failure_code: str | None
    market_ready: bool
    snapshot_at: str


class ProtectionPage(BaseModel):
    protections: list[ProtectionView]
    next_cursor: str | None


class ProtectionRequestView(BaseModel):
    request_id: UUID
    protection_id: UUID
    episode_id: UUID
    mode: Literal["PAPER"] = "PAPER"
    action: Literal["CREATE", "REPLACE", "CANCEL"]
    idempotency_key: UUID
    state: Literal["PENDING", "APPLIED", "REJECTED"]
    failure_code: str | None
    snapshot_at: datetime


class ProtectionRequestPage(BaseModel):
    requests: list[ProtectionRequestView]
    next_cursor: str | None
