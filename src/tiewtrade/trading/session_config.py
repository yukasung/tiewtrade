from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class TradeMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class MarketType(StrEnum):
    SPOT = "spot"
    FUTURES = "futures"


@dataclass(frozen=True, slots=True)
class SessionConfig:
    session_id: UUID
    account_profile_id: UUID
    preset_version: str
    market_type: MarketType
    trade_mode: TradeMode
    available_capital: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal

    def __post_init__(self) -> None:
        if self.available_capital <= 0:
            raise ValueError("available_capital must be positive")
        if self.fee_rate < 0:
            raise ValueError("fee_rate must not be negative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must not be negative")
