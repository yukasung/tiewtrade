"""พิสูจน์ว่า hypothesis ติดตั้งและรันได้ เพื่อให้ F-02 ไม่ต้องมาตั้งค่าเอง

F-01 ยังไม่มีสูตรคำนวณให้ทดสอบคุณสมบัติ เทสต์นี้จึงพิสูจน์แค่ว่าเครื่องมือพร้อม
(validation.md หัวข้อ "เทสต์ที่ต้องมี")
"""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st


@given(st.decimals(allow_nan=False, allow_infinity=False, places=8))
def test_decimal_addition_is_commutative(value: Decimal) -> None:
    assert value + Decimal(0) == Decimal(0) + value
