from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RsiStepGridPreset:
    version: str
    rsi_period: int
    rsi_reset_threshold: Decimal
    rsi_entry_threshold: Decimal
    atr_period: int
    take_profit_atr_multiplier: Decimal

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("version must not be empty")
        if self.rsi_period <= 0:
            raise ValueError("rsi_period must be positive")
        if self.atr_period <= 0:
            raise ValueError("atr_period must be positive")
        if not Decimal("0") <= self.rsi_reset_threshold < self.rsi_entry_threshold:
            raise ValueError("reset threshold must be below entry threshold")
        if self.rsi_entry_threshold > Decimal("100"):
            raise ValueError("entry threshold must not exceed 100")
        if self.take_profit_atr_multiplier <= 0:
            raise ValueError("take_profit_atr_multiplier must be positive")

    @classmethod
    def v1(cls) -> "RsiStepGridPreset":
        return cls(
            version="rsi-step-grid-v1",
            rsi_period=14,
            rsi_reset_threshold=Decimal("30"),
            rsi_entry_threshold=Decimal("50"),
            atr_period=14,
            take_profit_atr_multiplier=Decimal("3"),
        )
