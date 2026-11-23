"""Owner-scoped HTTP contracts for F-20."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from tiewtrade.core.bots import BotStatus
from tiewtrade.core.market_data import Timeframe
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


class StrategyConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: Literal["BTC", "ETH"]
    timeframe: Literal["1m", "3m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"] = "5m"
    capital_per_entry: StrictStr = Field(min_length=1, max_length=128)
    max_entries: StrictInt = Field(default=10, ge=1, le=10)


class StrategyConfigurationView(StrategyConfigurationInput):
    reference: str


class StrategyCatalogView(BaseModel):
    strategy_name: str
    strategies: list[str] = ["rsi-step-grid-ema-single-tp"]
    timeframes: list[Timeframe]
    max_entries_min: int = 1
    max_entries_max: int = 10
    default_max_entries: int = 10
    default_timeframe: Timeframe = Timeframe.M5


class PaperTestConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_name: Literal["paper-green-atr-test"]
    base: Literal["BTC", "ETH"]
    timeframe: Literal["1m", "3m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
    capital_per_entry: StrictStr = Field(min_length=1, max_length=128)


class PaperTestConfigurationView(PaperTestConfigurationInput):
    reference: str


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
    pinned_configuration: StrategyConfigurationInput | PaperTestConfigurationInput | None = None
    basket_target: str | None = None
    basket_triggered: bool = False
    open_entries: int = 0
    replacement: BotReplacementInput | None = None


class BotReceiptView(BaseModel):
    request_id: UUID
    mode: TradingMode
    key: UUID
    run_id: UUID | None
    failure_code: str | None
    pending: bool
