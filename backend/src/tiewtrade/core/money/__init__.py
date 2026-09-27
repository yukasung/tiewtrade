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
from tiewtrade.core.money.rounding import RoundingDirection
from tiewtrade.core.money.types import Money, Quantity

__all__ = [
    "ArithmeticFailureError",
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
    "TooManyDecimalPlacesError",
    "UnitMismatchError",
]
