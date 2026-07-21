from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaperSpotSessionConfig:
    session_id: UUID
    account_profile_id: UUID
    preset_version: str
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
