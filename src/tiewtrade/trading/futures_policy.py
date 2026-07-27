from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar


class MarginMode(StrEnum):
    CROSS = "cross"


class PositionMode(StrEnum):
    ONE_WAY = "one_way"


@dataclass(frozen=True, slots=True)
class FuturesTradingPolicy:
    V1_MINIMUM_LEVERAGE: ClassVar[int] = 1
    V1_MAXIMUM_LEVERAGE: ClassVar[int] = 5

    version: str
    leverage: int
    trading_capital_ratio: Decimal
    collateral_buffer_ratio: Decimal
    maintenance_margin_rate: Decimal
    margin_mode: MarginMode
    position_mode: PositionMode

    def __post_init__(self) -> None:
        if self.version != "paper-futures-v1":
            raise ValueError("version must be paper-futures-v1")
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
            raise ValueError("leverage must be an integer")
        if not self.V1_MINIMUM_LEVERAGE <= self.leverage <= self.V1_MAXIMUM_LEVERAGE:
            raise ValueError(
                "leverage must be between "
                f"{self.V1_MINIMUM_LEVERAGE} and {self.V1_MAXIMUM_LEVERAGE}"
            )
        if self.trading_capital_ratio != Decimal("0.5"):
            raise ValueError("trading_capital_ratio must be 0.5")
        if self.collateral_buffer_ratio != Decimal("0.5"):
            raise ValueError("collateral_buffer_ratio must be 0.5")
        if self.maintenance_margin_rate != Decimal("0.005"):
            raise ValueError("maintenance_margin_rate must be 0.005")
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
