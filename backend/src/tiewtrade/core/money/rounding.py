"""ทิศทางและกลไกการปัดเศษ (RQ-3, RQ-4, RQ-21)

**ห้ามปัดโดยปริยาย** ผู้เรียกต้องระบุทิศทางทุกครั้ง และความละเอียดปลายทาง
กำหนดโดยจุดที่ปัด ไม่ใช่ผู้เรียกเลือกเอง

ไม่ใช้คำว่าขึ้นหรือลง เพราะกำกวมกับค่าลบ — `-2.5` ปัด "ขึ้น" ได้ทั้ง `-2`
(ขาดทุนน้อยลง) และ `-3` (ขาดทุนมากขึ้น) ซึ่งตรงข้ามกันในทางความหมาย
"""

from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_UP, Decimal
from enum import Enum

from tiewtrade.core.money.context import allowing_rounding
from tiewtrade.core.money.limits import SMALLEST_UNIT, STORED_SCALE
from tiewtrade.core.money.validation import real_decimal_places


class RoundingDirection(Enum):
    """ทิศทางการปัดที่โมดูลนี้รองรับ

    เลือกตามความหมายของตัวเลขที่กำลังคิด ไม่ใช่ตามค่าของมัน — ยอดคงเหลือ
    และหนี้ต่างก็ปัดไปทางที่ทำให้ตัวเลขแย่ลง ซึ่งเป็นคนละทิศทางกัน (RQ-4)
    """

    #: เข้าหาศูนย์ — `2.5` เป็น `2`, `-2.5` เป็น `-2`
    TOWARD_ZERO = ROUND_DOWN
    #: ออกห่างจากศูนย์ — `2.5` เป็น `3`, `-2.5` เป็น `-3`
    AWAY_FROM_ZERO = ROUND_UP
    #: ไปทางค่าบวก — `2.5` เป็น `3`, `-2.5` เป็น `-2`
    TOWARD_POSITIVE = ROUND_CEILING
    #: ไปทางค่าลบ — `2.5` เป็น `2`, `-2.5` เป็น `-3`
    TOWARD_NEGATIVE = ROUND_FLOOR


def needs_rounding(amount: Decimal) -> bool:
    """ค่านี้ละเอียดเกินกว่าที่เก็บได้หรือไม่

    คำถามเรื่องความละเอียดที่เก็บได้อยู่ข้างค่ากลางที่นิยามมัน ไม่ใช่ที่ชั้นชนิดข้อมูล
    """
    return real_decimal_places(amount) > STORED_SCALE


def round_to_stored_scale(amount: Decimal, direction: RoundingDirection) -> Decimal:
    """ปัดให้เหลือความละเอียดที่เก็บได้ ตามทิศทางที่ระบุ

    ความละเอียดปลายทางมาจากค่ากลางของระบบ ผู้เรียกเลือกได้แค่ทิศทาง

    ฟังก์ชันนี้ปัดอย่างเดียว ไม่ตรวจช่วงค่า การตรวจช่วงเกิดที่จุดสร้างค่า
    ซึ่งผลที่ปัดแล้วต้องผ่านอยู่แล้ว
    """
    with allowing_rounding():
        return amount.quantize(SMALLEST_UNIT, rounding=direction.value)
