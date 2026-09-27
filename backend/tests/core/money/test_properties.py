"""เทสต์คุณสมบัติ — กฎที่ต้องจริงเสมอ (RQ-11)

**ทุกกฎมีเงื่อนไขกำกับ** ชนิดข้อมูลนี้จำกัดช่วงค่า กฎทางคณิตศาสตร์ที่จริงเสมอ
กับจำนวนจริงจึงไม่จริงเสมอที่นี่ เช่น `(a+b)-b = a` ใช้ไม่ได้เมื่อ `a+b` ล้นช่วง

**ถ้าเทสต์กลุ่มนี้แดง ให้แก้เงื่อนไขของเทสต์ ไม่ใช่แก้โค้ดให้ยอมรับค่าที่เกินช่วง**
"""

from decimal import Decimal, localcontext

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.core.money.conftest import HOSTILE_SETTINGS
from tiewtrade.core.money import Money, MoneyError, OutOfRangeError
from tiewtrade.core.money.limits import STORED_SCALE
from tiewtrade.core.money.validation import ensure_in_range

#: ค่าที่สร้างได้ตามกฎของโมดูล — ทศนิยมไม่เกินที่เก็บได้ และอยู่ในช่วง
storable = st.decimals(
    min_value=Decimal("-99999999999999999999"),
    max_value=Decimal("99999999999999999999"),
    allow_nan=False,
    allow_infinity=False,
    places=STORED_SCALE,
)


def _fits(amount: Decimal) -> bool:
    """อยู่ในช่วงที่เก็บได้หรือไม่ — ใช้เป็นเงื่อนไขของกฎ

    เรียกกฎเดียวกับโค้ดจริง ไม่เขียนเกณฑ์ช่วงค่าขึ้นมาใหม่ในเทสต์
    """
    try:
        ensure_in_range(amount)
    except OutOfRangeError:
        return False
    return True


@given(first=storable, second=storable)
def test_add_then_subtract_returns_the_original(first: Decimal, second: Decimal) -> None:
    """บวกแล้วลบค่าเดิมกลับ ต้องได้ค่าตั้งต้น

    **เงื่อนไข: ผลระหว่างทางต้องอยู่ในช่วง** ถ้า `first + second` ล้น
    จะไม่มีผลลัพธ์ให้ลบกลับตั้งแต่แรก
    """
    assume(_fits(first + second))
    start = Money.of(first, "USDT")
    step = Money.of(second, "USDT")
    assert (start + step) - step == start


@given(values=st.lists(storable, min_size=2, max_size=6))
def test_order_of_addition_does_not_change_the_total(values: list[Decimal]) -> None:
    """ลำดับการบวกไม่เปลี่ยนผลรวม

    **เงื่อนไข: ทุกลำดับต้องมีผลระหว่างทางอยู่ในช่วง** ซึ่งไม่จริงเสมอ —
    `[M, u, -u]` ล้นที่ขั้นแรก ขณะที่ `[u, -u, M]` ไม่ล้น
    """
    forwards = list(values)
    backwards = list(reversed(values))
    for order in (forwards, backwards):
        running = Decimal(0)
        for value in order:
            running += value
            assume(_fits(running))

    def total(order: list[Decimal]) -> Money:
        running = Money.of("0", "USDT")
        for value in order:
            running = running + Money.of(value, "USDT")
        return running

    assert total(forwards) == total(backwards)


#: ค่าบวกที่มากพอจะดันค่าสูงสุดให้ล้น ไม่ใช้ `assume` เพราะค่าสุ่มทั่วไปแทบไม่ล้น
#: การกรองจะทำให้ hypothesis ทิ้งตัวอย่างเกือบทั้งหมด
pushes_over = st.decimals(
    min_value=Decimal("0.000000000000000001"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=STORED_SCALE,
)


@given(addend=pushes_over)
def test_overflow_is_always_a_typed_error(addend: Decimal) -> None:
    """เส้นทางที่ผลระหว่างทางเกินช่วง ต้องได้ข้อผิดพลาดที่ระบุชนิดได้เสมอ

    แยกเป็นกฎของตัวเอง ไม่ใช่ข้อยกเว้นที่ซ่อนอยู่ในกฎอื่น
    สร้างกรณีที่ล้นแน่นอนแทนการสุ่มแล้วกรอง
    """
    ceiling = Money.of("99999999999999999999.999999999999999999", "USDT")
    with pytest.raises(OutOfRangeError):
        ceiling + Money.of(addend, "USDT")

    floor = Money.of("-99999999999999999999.999999999999999999", "USDT")
    with pytest.raises(OutOfRangeError):
        floor - Money.of(addend, "USDT")


@given(value=storable)
def test_text_round_trip_preserves_everything(value: Decimal) -> None:
    """แปลงเป็นข้อความแล้วอ่านกลับ ต้องได้ค่า ชนิด และหน่วยเดิม (RQ-18)"""
    original = Money.of(value, "USDT")
    assert Money.from_parts(original.as_parts()) == original


@given(value=storable)
def test_multiplying_by_one_changes_nothing(value: Decimal) -> None:
    """คูณด้วยหนึ่งได้ค่าเดิม — จับการปัดที่เผลอเกิดขึ้น"""
    money = Money.of(value, "USDT")
    assert money.times("1") == money


@given(value=storable)
def test_multiplying_by_zero_gives_zero(value: Decimal) -> None:
    money = Money.of(value, "USDT")
    assert money.times("0").amount == Decimal(0)


@given(value=storable)
def test_created_values_are_always_storable(value: Decimal) -> None:
    """ค่าที่สร้างได้ต้องอยู่ในช่วงที่เก็บได้เสมอ (RQ-22)"""
    assert _fits(Money.of(value, "USDT").amount)


@settings(max_examples=30)
@given(first=storable, second=storable)
def test_laws_hold_under_hostile_contexts(first: Decimal, second: Decimal) -> None:
    """กฎข้างบนต้องจริงภายใต้ context ภายนอกที่ผิดปกติด้วย

    เป็นการรันคุณสมบัติซ้ำใต้สภาพแวดล้อมที่ต่างกัน ตามที่ validation กำหนด
    """
    assume(_fits(first + second))
    for hostile in HOSTILE_SETTINGS:
        with localcontext(hostile):
            start = Money.of(first, "USDT")
            step = Money.of(second, "USDT")
            assert (start + step) - step == start


def _exact_product(first: Decimal, second: Decimal) -> Decimal:
    """คูณด้วยเลขจำนวนเต็มล้วน เพื่อให้ได้ค่าอ้างอิงที่ไม่ผ่าน context เลย

    ห้ามใช้การคูณของ `Decimal` เป็นค่าอ้างอิง เพราะมันปัดตาม context ของเทสต์เอง
    ซึ่งจะทำให้เทสต์เทียบผลที่ถูกต้องกับค่าที่ถูกปัดแล้ว
    """
    first_sign, first_digits, first_exponent = first.as_tuple()
    second_sign, second_digits, second_exponent = second.as_tuple()
    assert isinstance(first_exponent, int) and isinstance(second_exponent, int)

    coefficient = int("".join(map(str, first_digits))) * int("".join(map(str, second_digits)))
    sign = first_sign ^ second_sign
    digits = tuple(int(digit) for digit in str(coefficient))
    return Decimal((sign, digits, first_exponent + second_exponent))


@given(value=storable, factor=storable)
def test_multiplication_never_rounds_silently(value: Decimal, factor: Decimal) -> None:
    """คูณแล้วต้องได้ผลเป๊ะ หรือไม่ก็ต้องดัง ไม่มีทางปัดเงียบ ๆ (RQ-21)"""
    money = Money.of(value, "USDT")
    try:
        result = money.times(factor)
    except MoneyError:
        return
    assert result.amount == _exact_product(value, factor)
