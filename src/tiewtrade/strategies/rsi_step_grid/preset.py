from dataclasses import dataclass
from decimal import Decimal

_V1_VERSION = "rsi-step-grid-v1"
_V1_RSI_PERIOD = 14
_V1_RSI_RESET_THRESHOLD = Decimal("30")
_V1_RSI_ENTRY_THRESHOLD = Decimal("50")
_V1_ATR_PERIOD = 14
_V1_TAKE_PROFIT_ATR_MULTIPLIER = Decimal("3")


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
        if self.version != _V1_VERSION:
            raise ValueError("unsupported preset version")
        if (
            self.rsi_period != _V1_RSI_PERIOD
            or self.rsi_reset_threshold != _V1_RSI_RESET_THRESHOLD
            or self.rsi_entry_threshold != _V1_RSI_ENTRY_THRESHOLD
            or self.atr_period != _V1_ATR_PERIOD
            or self.take_profit_atr_multiplier != _V1_TAKE_PROFIT_ATR_MULTIPLIER
        ):
            raise ValueError("rsi-step-grid-v1 parameters must remain canonical")

    @classmethod
    def v1(cls) -> "RsiStepGridPreset":
        return cls(
            version=_V1_VERSION,
            rsi_period=_V1_RSI_PERIOD,
            rsi_reset_threshold=_V1_RSI_RESET_THRESHOLD,
            rsi_entry_threshold=_V1_RSI_ENTRY_THRESHOLD,
            atr_period=_V1_ATR_PERIOD,
            take_profit_atr_multiplier=_V1_TAKE_PROFIT_ATR_MULTIPLIER,
        )
