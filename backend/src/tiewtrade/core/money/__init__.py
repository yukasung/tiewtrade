"""ชนิดข้อมูลเงินและการคำนวณพื้นฐาน (F-02)

ชั้นล่างสุดที่ทุกการคำนวณเงินในระบบยืนอยู่บน
ข้อกำหนดอยู่ใน `specs/features/2026-09-27-money-types/requirements.md`
"""

from tiewtrade.core.money.errors import (
    ArithmeticFailureError,
    InvalidInputTypeError,
    InvalidNumberFormatError,
    InvalidUnitError,
    MoneyError,
    NotFiniteValueError,
    OutOfRangeError,
    RoundingRequiredError,
    TooManyDecimalPlacesError,
    UnitMismatchError,
)
from tiewtrade.core.money.indicator_arithmetic import (
    Scalar,
    divide_money,
    percentage_share,
    weighted_mean_money,
)
from tiewtrade.core.money.indicator_batch import (
    AverageState,
    BatchAction,
    IndicatorBatchInput,
    IndicatorBatchResult,
    IndicatorBatchState,
    advance_indicator_batch,
    reset_indicator_batch,
)
from tiewtrade.core.money.position_arithmetic import allocate_money, money_for_quantity
from tiewtrade.core.money.rounding import RoundingDirection
from tiewtrade.core.money.types import Money, Quantity

__all__ = [
    "ArithmeticFailureError",
    "AverageState",
    "BatchAction",
    "IndicatorBatchInput",
    "IndicatorBatchResult",
    "IndicatorBatchState",
    "InvalidInputTypeError",
    "InvalidNumberFormatError",
    "InvalidUnitError",
    "Money",
    "MoneyError",
    "NotFiniteValueError",
    "OutOfRangeError",
    "Quantity",
    "RoundingDirection",
    "RoundingRequiredError",
    "Scalar",
    "TooManyDecimalPlacesError",
    "UnitMismatchError",
    "advance_indicator_batch",
    "allocate_money",
    "divide_money",
    "money_for_quantity",
    "percentage_share",
    "reset_indicator_batch",
    "weighted_mean_money",
]
