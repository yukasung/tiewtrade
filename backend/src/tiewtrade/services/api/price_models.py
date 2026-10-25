"""Server-observed price snapshots, never an execution authorization."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from tiewtrade.core.market_catalog import MarketSource


class PriceRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: MarketSource
    base: str
    quote: str
    amount: StrictStr | None
    trade_at: datetime | None
    received_at: datetime | None
    revision: str = Field(pattern=r"^[0-9]+$")
    generation: str = Field(pattern=r"^[0-9]+$")
    readiness: Literal["MISSING", "RECOVERING", "STALE", "READY"]
    reason: str
    valid_until: datetime | None
    unavailable_since: datetime | None
    alert_due: bool


class PricesView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    catalog_revision: str = Field(pattern=r"^[0-9]+$")
    server_time: datetime
    delivery_status: Literal["CONNECTED", "RECOVERING"]
    rows: list[PriceRow]
