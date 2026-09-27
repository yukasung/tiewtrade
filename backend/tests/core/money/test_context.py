"""เทสต์ว่าผลไม่ขึ้นกับ context ภายนอก — V-1, V-1.1, V-2, V-2.1

**นี่คือข้อกำหนดที่ยากที่สุดของงานนี้** `Decimal` ปัดตาม context ของผู้เรียก
โดยที่โค้ดไม่ต้องสั่งปัดเลย ถ้าโมดูลนี้ไม่บังคับ context ของตัวเอง
ยอดเงินจะเพี้ยนเงียบ ๆ ตามสภาพแวดล้อมที่บังเอิญรันอยู่
"""

from collections.abc import Callable
from decimal import (
    Context,
    Decimal,
    Inexact,
    Rounded,
    getcontext,
    localcontext,
)

import pytest

from tests.core.money.conftest import HOSTILE_CONTEXTS
from tiewtrade.core.money import Money, MoneyError, Quantity, RoundingDirection

#: ผลอ้างอิงที่คำนวณมือไว้ ไม่ได้อ่านจากโค้ดที่กำลังทดสอบ
REFERENCE_RESULTS = {
    # 12345.67 + 0.01 ต่างกันตามความละเอียด: ที่ 6 หลักจะได้ 12345.7
    "addition": "12345.68",
    # 0.000000000000000001 x 1000000 เลื่อนจุดหกตำแหน่ง
    "multiplication": "0.000000000001",
    # ผลรวมของ 0.1 สิบครั้ง
    "repeated": "1",
}


@pytest.mark.parametrize("outside", HOSTILE_CONTEXTS)
def test_results_do_not_depend_on_caller_context(outside: Context) -> None:
    """V-1 — ผลต้องตรงกับค่าอ้างอิงภายใต้ context ภายนอกทุกแบบ"""
    expected = REFERENCE_RESULTS
    with localcontext(outside):
        addition = Money.of("12345.67", "USDT") + Money.of("0.01", "USDT")
        multiplication = Money.of("0.000000000000000001", "USDT").times("1000000")
        repeated = Money.of("0", "USDT")
        for _ in range(10):
            repeated = repeated + Money.of("0.1", "USDT")

    assert addition.amount == Decimal(expected["addition"])
    assert multiplication.amount == Decimal(expected["multiplication"])
    assert repeated.amount == Decimal(expected["repeated"])


@pytest.mark.parametrize("outside", HOSTILE_CONTEXTS)
def test_error_types_do_not_depend_on_caller_context(outside: Context) -> None:
    """V-1 — ชนิดข้อผิดพลาดต้องไม่เปลี่ยนตาม context ภายนอกด้วย"""
    with localcontext(outside):
        with pytest.raises(MoneyError):
            Money.of("100000000000000000000", "USDT")
        with pytest.raises(MoneyError):
            Money.of("0.000000000000000001", "USDT").times("0.1")


def test_precision_alone_is_not_enough() -> None:
    """V-1.1 — เทสต์ที่จะแดงถ้าคัดลอก context ผู้เรียกแล้วแก้แต่ precision

    context ภายนอกดัก `Inexact` ไว้ ถ้าโมดูลคัดลอก context นั้นมา
    การปัดที่ได้รับอนุญาตจะโยนข้อผิดพลาดของ `Decimal` ออกมาแทนที่จะทำงานปกติ
    """
    with localcontext(Context(prec=80, traps=[Inexact, Rounded])):
        result = Money.of("0.000000000000000001", "USDT").times(
            "0.1", RoundingDirection.AWAY_FROM_ZERO
        )
    assert result.amount == Decimal("1E-18")


@pytest.mark.parametrize("outside", HOSTILE_CONTEXTS)
def test_caller_context_is_restored(outside: Context) -> None:
    """V-2 — เทียบค่าตั้งทีละค่า ไม่ใช่เทียบว่าเป็น context ตัวเดิม"""
    with localcontext(outside):
        before = _snapshot(getcontext())
        Money.of("1", "USDT") + Money.of("2", "USDT")
        assert _snapshot(getcontext()) == before


@pytest.mark.parametrize("outside", HOSTILE_CONTEXTS)
def test_caller_context_is_restored_after_failure(outside: Context) -> None:
    """V-2 — ต้องคืนค่าเดิมแม้เส้นทางที่เกิดข้อผิดพลาด"""
    with localcontext(outside):
        before = _snapshot(getcontext())
        with pytest.raises(MoneyError):
            Money.of("1", "USDT") + Money.of("1", "THB")
        assert _snapshot(getcontext()) == before


def _snapshot(context: Context) -> dict[str, object]:
    """เก็บสำเนาของค่าตั้งและ flags ทั้งหมด"""
    return {
        "prec": context.prec,
        "rounding": context.rounding,
        "Emin": context.Emin,
        "Emax": context.Emax,
        "capitals": context.capitals,
        "clamp": context.clamp,
        "traps": dict(context.traps),
        "flags": dict(context.flags),
    }


def test_decimal_errors_do_not_escape() -> None:
    """V-2.1 — ข้อผิดพลาดของ `Decimal` ต้องถูกแปลงเป็นชนิดของโมดูล

    ใช้ข้อความที่อ่านเป็นตัวเลขไม่ได้ ซึ่งทำให้ `Decimal` โยน `InvalidOperation`
    ออกมาในเส้นทางที่ไม่ได้ตั้งใจ ถ้าไม่แปลง ผู้เรียกจะได้ข้อผิดพลาดของ
    ไลบรารีแทนของเรา
    """
    with pytest.raises(MoneyError):
        Money.of("ไม่ใช่ตัวเลข", "USDT")


def test_no_public_operation_touches_the_caller_context() -> None:
    """ไม่มีการเรียกสาธารณะใดตั้ง flag ใน context ของผู้เรียก

    เข้มกว่าการเทียบค่าก่อนหลัง เพราะล้าง flags ก่อนแล้วดูว่ามีอะไรถูกตั้งขึ้นใหม่
    ครอบทุกทางเข้าของโมดูล ไม่ใช่เฉพาะการบวก

    flag ที่ถูกตั้งแปลว่ามีการคำนวณบางอย่างหลุดออกไปทำใน context ของผู้เรียก
    ซึ่งเป็นอาการเดียวกับที่ทำให้ `-MAX_ABS` เคยรั่ว
    """
    operations: dict[str, Callable[[], object]] = {
        "สร้าง": lambda: Money.of("1.5", "USDT"),
        "สร้างค่าขอบ": lambda: Money.of("99999999999999999999.999999999999999999", "USDT"),
        "บวก": lambda: Money.of("1", "USDT") + Money.of("2", "USDT"),
        "ลบ": lambda: Money.of("1", "USDT") - Money.of("2", "USDT"),
        "เทียบค่า": lambda: Money.of("1", "USDT") < Money.of("2", "USDT"),
        "คูณพอดี": lambda: Money.of("2", "USDT").times("3"),
        "คูณแล้วปัด": lambda: Money.of("1E-18", "USDT").times("0.1", RoundingDirection.TOWARD_ZERO),
        "เป็นข้อความ": lambda: Money.of("1.2300", "USDT").as_parts(),
        "อ่านกลับ": lambda: Money.from_parts({"amount": "1.23", "currency": "USDT"}),
        "ปริมาณ": lambda: Quantity.of("0.5", "BTC") + Quantity.of("0.25", "BTC"),
    }

    # context ที่แคบกว่าตารางข้างบน เพื่อให้การคำนวณที่หลุดออกมาดังแน่นอน
    with localcontext(Context(prec=3, Emin=-5, Emax=5)):
        for name, operation in operations.items():
            getcontext().clear_flags()
            operation()
            raised = [flag.__name__ for flag, value in getcontext().flags.items() if value]
            assert not raised, f"{name} ตั้ง flag {raised} ใน context ของผู้เรียก"
