from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class MarginMode(StrEnum):
    CROSS = "cross"


class PositionMode(StrEnum):
    ONE_WAY = "one_way"


@dataclass(frozen=True, slots=True)
class FuturesTradingPolicy:
    version: str
    leverage: int
    trading_capital_ratio: Decimal
    collateral_buffer_ratio: Decimal
    maintenance_margin_rate: Decimal
    margin_mode: MarginMode
    position_mode: PositionMode

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("version must not be empty")
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
            raise ValueError("leverage must be an integer")
        if not 1 <= self.leverage <= 5:
            raise ValueError("leverage must be between 1 and 5")
        if self.trading_capital_ratio <= 0:
            raise ValueError("trading_capital_ratio must be positive")
        if self.collateral_buffer_ratio <= 0:
            raise ValueError("collateral_buffer_ratio must be positive")
        if self.trading_capital_ratio + self.collateral_buffer_ratio != Decimal("1"):
            raise ValueError("Futures capital ratios must sum to 1")
        if not Decimal("0") < self.maintenance_margin_rate < Decimal("1"):
            raise ValueError("maintenance_margin_rate must be between 0 and 1")
        if self.margin_mode is not MarginMode.CROSS:
            raise ValueError("Paper Futures requires Cross Margin")
        if self.position_mode is not PositionMode.ONE_WAY:
            raise ValueError("Paper Futures requires One-way Mode")

    @classmethod
    def v1(cls, leverage: int) -> "FuturesTradingPolicy":
        return cls(
            version="paper-futures-v1",
            leverage=leverage,
            trading_capital_ratio=Decimal("0.5"),
            collateral_buffer_ratio=Decimal("0.5"),
            maintenance_margin_rate=Decimal("0.005"),
            margin_mode=MarginMode.CROSS,
            position_mode=PositionMode.ONE_WAY,
        )
