"""กฎตรวจค่าที่ทุกชนิดในโมดูลนี้ใช้ร่วมกัน (RQ-16, RQ-22, RQ-24)

เงิน ปริมาณ และตัวเลขเปล่าที่เอามาคูณ ใช้กฎชุดเดียวกันทั้งหมด
ต่างกันแค่ตัวที่มีหน่วยกับตัวที่ไม่มี

**การตรวจต้องไม่ผ่านการปัด** (P-5) `normalize()` และ `quantize()` ปัดตาม context
ก่อนตัดศูนย์ท้าย ทำให้ค่าที่ต้องปฏิเสธผ่านได้ โมดูลนี้จึงอ่าน coefficient
และ exponent ตรง ๆ แล้วตัดศูนย์ท้ายเอง
"""

from decimal import Decimal, DecimalException

from tiewtrade.core.money.errors import (
    InvalidInputTypeError,
    InvalidNumberFormatError,
    InvalidUnitError,
    NotFiniteValueError,
    OutOfRangeError,
    TooManyDecimalPlacesError,
)
from tiewtrade.core.money.limits import MAX_ABS, STORED_SCALE

#: ชนิดที่รับเป็นค่าตัวเลขได้ — `bool` ต้องถูกปฏิเสธแม้เป็น subclass ของ `int`
NumberInput = str | int | Decimal

#: อักขระที่ใช้เป็นหน่วยได้
#:
#: จำกัดไว้แค่นี้เพราะ `isalnum()` ยอมรับตัวเลขและตัวอักษรของทุกภาษา
#: และ `upper()` ของบางตัวให้ผลชนกับหน่วยอื่น — ตัว i ไม่มีจุดของตุรกี
#: กลายเป็น I และ eszett ของเยอรมันกลายเป็น SS
#: ซึ่งเปิดช่องให้คำนวณข้ามหน่วยโดยไม่มีอะไรเตือน
_UNIT_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


def _reject_unsupported_type(value: object) -> None:
    """ปฏิเสธชนิดที่ไม่รองรับ

    ตรวจ `bool` ก่อน `int` เพราะ `bool` เป็น subclass ของ `int`
    ถ้าไม่ตรวจแยก `True` จะกลายเป็นเงินหนึ่งหน่วยเงียบ ๆ (P-7)

    ชนิดทศนิยมลอยตัวถูกปฏิเสธโดยการไม่อยู่ในรายการที่อนุญาต
    ไม่ใช่โดยการอ้างชื่อชนิดนั้น เพราะด่านความบริสุทธิ์ของ `core`
    ปฏิเสธการอ้างชื่อนั้นในโค้ด (P-12)
    """
    if isinstance(value, bool):
        raise InvalidInputTypeError("ค่าตรรกะใช้แทนจำนวนเงินไม่ได้")
    if not isinstance(value, (str, int, Decimal)):
        raise InvalidInputTypeError(f"ชนิด {type(value).__name__} ใช้เป็นค่าตัวเลขไม่ได้")


def _to_decimal(value: NumberInput) -> Decimal:
    """แปลงเป็น `Decimal` แบบไม่สูญเสียค่า"""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value)
    except DecimalException as cause:
        raise InvalidNumberFormatError(f"อ่านค่า {value!r} เป็นตัวเลขไม่ได้") from cause


def real_decimal_places(value: Decimal) -> int:
    """นับทศนิยมจริง โดยตัดศูนย์ท้ายแบบไม่ปัด

    `1.0000000000000000000` มีทศนิยมจริง 0 ตำแหน่ง เพราะศูนย์ท้ายไม่เปลี่ยนค่า
    ส่วน `1.2345678901234567890123` มี 22 ตำแหน่ง

    ห้ามใช้ `normalize()` เพราะมันปัดตาม context ก่อนตัดศูนย์ ทำให้ค่าที่
    ทศนิยมจริงเกินกำหนดแต่ยาวกว่าความละเอียดของ context กลายเป็นค่าที่ผ่านได้
    """
    _, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):
        raise NotFiniteValueError("ค่าไม่ใช่จำนวนจำกัด")

    if exponent >= 0:
        return 0

    # ศูนย์เขียนได้หลายรูปแบบ เช่น `0E-20` ซึ่ง coefficient คือ `(0,)`
    # ตัวเดียว การไล่ตัดศูนย์ท้ายจะตัดได้แค่หลักเดียวแล้วหยุด
    # ทั้งที่ค่าจริงคือศูนย์ ซึ่งมีทศนิยมจริงศูนย์ตำแหน่ง
    if not any(digits):
        return 0

    places = -exponent
    for digit in reversed(digits):
        if digit != 0 or places == 0:
            break
        places -= 1
    return places


def ensure_valid_amount(amount: Decimal) -> None:
    """ตรวจ invariant ทั้งชุดของค่าที่สร้างเสร็จแล้ว

    แยกจาก `normalise_amount` เพราะจุดสร้างค่าต้องตรวจได้โดยไม่ต้องแปลงชนิด
    ใช้ที่ `__post_init__` ของชนิดข้อมูล ซึ่งเป็นประตูที่เลี่ยงไม่ได้
    """
    if not isinstance(amount, Decimal):
        raise InvalidInputTypeError(f"จำนวนต้องเป็น Decimal ไม่ใช่ {type(amount).__name__}")
    if not amount.is_finite():
        raise NotFiniteValueError(f"ค่า {amount} ไม่ใช่จำนวนจำกัด")

    places = real_decimal_places(amount)
    if places > STORED_SCALE:
        raise TooManyDecimalPlacesError(f"ทศนิยมจริง {places} ตำแหน่ง เกินที่เก็บได้ {STORED_SCALE} ตำแหน่ง")
    ensure_in_range(amount)


def ensure_canonical_unit(unit: str) -> None:
    """ตรวจว่าหน่วยอยู่ในรูปมาตรฐานแล้ว"""
    if normalise_unit(unit) != unit:
        raise InvalidUnitError(f"หน่วย {unit!r} ยังไม่อยู่ในรูปมาตรฐาน")


def normalise_amount(value: NumberInput) -> Decimal:
    """ตรวจและแปลงค่าตัวเลขให้อยู่ในรูปมาตรฐาน

    คืนค่าที่ผ่านกฎทุกข้อแล้ว และแปลงลบศูนย์ให้เป็นศูนย์รูปแบบเดียว
    """
    _reject_unsupported_type(value)
    amount = _to_decimal(value)

    if not amount.is_finite():
        raise NotFiniteValueError(f"ค่า {amount} ไม่ใช่จำนวนจำกัด")

    places = real_decimal_places(amount)
    if places > STORED_SCALE:
        raise TooManyDecimalPlacesError(f"ทศนิยมจริง {places} ตำแหน่ง เกินที่เก็บได้ {STORED_SCALE} ตำแหน่ง")

    ensure_in_range(amount)

    if amount.is_zero():
        # ลบศูนย์เท่ากับศูนย์ แต่แสดงผลต่างกัน จึงต้องทำให้เป็นรูปแบบเดียว
        return Decimal(0)
    return amount


def ensure_in_range(amount: Decimal) -> None:
    """ตรวจว่าค่าอยู่ในช่วงที่เก็บได้

    เขียนเทียบตรงไปตรงมาได้ เพราะทางเข้าสาธารณะทุกทางถูกครอบด้วย context
    ของโมดูลแล้ว เครื่องหมายลบและการเทียบจึงทำงานที่ความละเอียด 80 หลักเสมอ
    """
    if not -MAX_ABS < amount < MAX_ABS:
        raise OutOfRangeError(f"ค่า {amount} อยู่นอกช่วงที่เก็บได้")


def normalise_unit(unit: object) -> str:
    """ตรวจและแปลงหน่วยให้อยู่ในรูปมาตรฐาน

    หน่วยคือสกุลเงินหรือชื่อเหรียญ เก็บเป็นตัวพิมพ์ใหญ่ เทียบเท่ากันเมื่อตรงกันทุกตัว

    **โมดูลนี้ไม่รู้จักรายการเหรียญที่ระบบรองรับ** การจำกัดรายชื่อเป็นกฎธุรกิจ
    ซึ่งอยู่ในงานอื่น ถ้าเอามาไว้ที่นี่ `core` จะไม่บริสุทธิ์อีกต่อไป
    """
    if not isinstance(unit, str):
        raise InvalidUnitError(f"หน่วยต้องเป็นข้อความ ไม่ใช่ {type(unit).__name__}")
    if not unit or not all(character in _UNIT_CHARACTERS for character in unit):
        raise InvalidUnitError(f"หน่วย {unit!r} ผิดรูปแบบ")
    return unit.upper()
