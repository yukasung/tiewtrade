from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.spot_policy import SpotTradingPolicy


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
    entry_policy: EntryPolicy
    spot_policy: SpotTradingPolicy | None

    def __post_init__(self) -> None:
        if self.available_capital <= 0:
            raise ValueError("available_capital must be positive")
        if self.fee_rate < 0:
            raise ValueError("fee_rate must not be negative")
        if not Decimal("0") <= self.slippage_bps < Decimal("10000"):
            raise ValueError("slippage_bps must be between 0 and 10000")
        if self.market_type is MarketType.SPOT and self.spot_policy is None:
            raise ValueError("spot_policy is required for Spot sessions")
        if self.market_type is MarketType.FUTURES and self.spot_policy is not None:
            raise ValueError("spot_policy is not valid for Futures sessions")
