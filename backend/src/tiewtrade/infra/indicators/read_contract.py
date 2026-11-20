"""Unsigned public-data read contracts; no session tokens or signing keys."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from tiewtrade.core.indicators import FORMULA_VERSION
from tiewtrade.core.market_data import Timeframe


class DatasetChangedError(ValueError):
    pass


class CursorClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format_version: Literal[1] = 1
    formula_version: str = FORMULA_VERSION
    dataset_revision: str
    source: str
    base: str
    quote: str
    timeframe: Timeframe
    calculation_start: datetime
    calculation_end: datetime
    as_of: datetime
    result_start: datetime
    result_end: datetime
    next_open_at: datetime
    page_size: int = Field(ge=1, le=1000)
    issued_at: datetime
    expires_at: datetime


class PreparedCursorClaims(CursorClaims):
    format_version: Literal[2] = 2  # type: ignore[assignment]
    generation_id: UUID
    codec_version: Literal[2] = 2
    rollout_epoch: UUID
    dataset_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
