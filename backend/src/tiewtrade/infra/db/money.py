"""แปลงค่าเงินและปริมาณเข้าออกฐานข้อมูล — ไม่ปัด ไม่ใช้ทศนิยมลอยตัว

ชั้นนี้ **ไม่ตัดสินใจเรื่องการปัดเศษเลย** (RQ-9.1) ค่าที่เก็บไม่ได้ต้องถูกปฏิเสธ
การปัดเป็นการตัดสินใจของผู้เรียกผ่าน `RoundingDirection` ของ F-02 ก่อนมาถึงที่นี่
ถ้าชั้นนี้ปัดให้เอง ผู้ใช้จะเห็นยอดที่ไม่ตรงกับที่สั่งโดยไม่มีใครรู้ว่าเกิดที่ไหน

หน่วยเก็บคู่กับจำนวนเสมอ เพราะชนิดข้อมูลของ F-02 ผูกหน่วยติดมาด้วย
การเก็บแค่จำนวนคือการทิ้งข้อมูลที่ทำให้ค่านั้นมีความหมาย
"""

from __future__ import annotations

from decimal import Decimal

from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db.errors import ValueRejectedError

# ชื่อช่องของ `as_parts` ต่างกันตามชนิด เพราะ F-02 ตั้งใจให้คำศัพท์ตรงกับสิ่งที่ค่านั้นแทน
# เงินใช้ "amount"/"currency" ปริมาณใช้ "quantity"/"asset" — ที่นี่จึงอ้างชื่อตามชนิด
# ไม่ใช่เดาว่าเหมือนกัน
_MONEY_AMOUNT_KEY = "amount"
_MONEY_UNIT_KEY = "currency"
_QUANTITY_AMOUNT_KEY = "quantity"
_QUANTITY_UNIT_KEY = "asset"


def money_to_columns(value: Money) -> tuple[Decimal, str]:
    """แตกจำนวนเงินเป็นคู่คอลัมน์ (จำนวน, สกุลเงิน)"""
    parts = value.as_parts()
    return Decimal(parts[_MONEY_AMOUNT_KEY]), parts[_MONEY_UNIT_KEY]


def quantity_to_columns(value: Quantity) -> tuple[Decimal, str]:
    """แตกปริมาณเป็นคู่คอลัมน์ (จำนวน, เหรียญ)"""
    parts = value.as_parts()
    return Decimal(parts[_QUANTITY_AMOUNT_KEY]), parts[_QUANTITY_UNIT_KEY]


def money_from_columns(amount: object, unit: object) -> Money:
    """ประกอบจำนวนเงินกลับจากค่าที่อ่านมาจากฐานข้อมูล

    ชนิดที่ไม่รองรับถูกปฏิเสธที่จุดตรวจของ F-02 ไม่ใช่ที่นี่ เพื่อไม่ให้มีจุดตรวจสองที่
    """
    return Money.of(_as_number_input(amount), _as_unit(unit))


def quantity_from_columns(amount: object, unit: object) -> Quantity:
    """ประกอบปริมาณกลับจากค่าที่อ่านมาจากฐานข้อมูล"""
    return Quantity.of(_as_number_input(amount), _as_unit(unit))


def _as_number_input(value: object) -> Decimal | str | int:
    """ปฏิเสธชนิดที่เก็บเป็นเงินไม่ได้ตั้งแต่ขอบของชั้นนี้

    ไม่แปลงชนิดให้เอง — การแปลงทศนิยมลอยตัวเป็นข้อความคือการรับค่าที่ F-02
    ตั้งใจปฏิเสธ แล้วความคลาดเคลื่อนของทศนิยมลอยตัวจะเข้ามาเงียบ ๆ
    กฎเรื่องความละเอียด ช่วงค่า และรูปแบบ ยังเป็นของ F-02 ที่เดียว ที่นี่ตรวจแค่ชนิด
    """
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise ValueRejectedError(f"ชนิด {type(value).__name__} ใช้เป็นค่าเงินในฐานข้อมูลไม่ได้")
    return value


def _as_unit(value: object) -> str:
    """หน่วยต้องเป็นข้อความ กฎรูปแบบอยู่ที่ `normalise_unit` ของ F-02"""
    if not isinstance(value, str):
        raise ValueRejectedError(f"ชนิด {type(value).__name__} ใช้เป็นหน่วยไม่ได้")
    return value
