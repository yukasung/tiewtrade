"""การตรวจข้อจำกัดของเหรียญ — V-15.1, V-15.2, V-16 ถึง V-18

กฎที่ตรวจมาจาก `standards/trading-safety.md` หัวข้อ 3 สามข้อ
และ **การตรวจไม่ปัดค่าให้** — ค่าที่ไม่ตรงขั้นถูกรายงานว่าไม่ผ่าน (F-33 Q-7)
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tiewtrade.core.money import ArithmeticFailureError, Money, MoneyError, Quantity
from tiewtrade.core.trading_limits import ConstraintViolation, unmet_constraints

MINIMUM_QUANTITY = Quantity.of("0.001", "BTC")
QUANTITY_STEP = Quantity.of("0.0001", "BTC")
MINIMUM_NOTIONAL = Money.of("10", "USDT")


def _check(quantity: str, notional: str) -> tuple[ConstraintViolation, ...]:
    return unmet_constraints(
        quantity=Quantity.of(quantity, "BTC"),
        notional=Money.of(notional, "USDT"),
        minimum_quantity=MINIMUM_QUANTITY,
        quantity_step=QUANTITY_STEP,
        minimum_notional=MINIMUM_NOTIONAL,
    )


def test_all_constraints_met() -> None:
    """0.0015 BTC เป็น 15 เท่าของขั้น 0.0001 และไม่น้อยกว่าขั้นต่ำ 0.001 — ผ่านทุกข้อ"""
    assert _check("0.0015", "120") == ()


def test_quantity_below_minimum() -> None:
    """0.0009 น้อยกว่าขั้นต่ำ 0.001 แต่ยังเป็น 9 เท่าของขั้น — ไม่ผ่านข้อเดียว"""
    assert _check("0.0009", "120") == (ConstraintViolation.BELOW_MINIMUM_QUANTITY,)


def test_quantity_not_on_step() -> None:
    """0.00125 ไม่เป็นจำนวนเท่าของ 0.0001 — 0.00125 / 0.0001 = 12.5"""
    assert _check("0.00125", "120") == (ConstraintViolation.QUANTITY_NOT_ON_STEP,)


def test_notional_below_minimum() -> None:
    """มูลค่า 9.99 น้อยกว่าขั้นต่ำ 10 อยู่ 0.01"""
    assert _check("0.0015", "9.99") == (ConstraintViolation.BELOW_MINIMUM_NOTIONAL,)


def test_all_three_violations_reported_together() -> None:
    """ผิดทั้งสามข้อต้องได้ครบสามข้อ ไม่ใช่หยุดที่ข้อแรก

    ผู้ใช้ที่แก้ทีละข้อตามที่ระบบบอกจะต้องลองใหม่สามรอบโดยไม่จำเป็น
    """
    assert set(_check("0.00005", "1")) == {
        ConstraintViolation.BELOW_MINIMUM_QUANTITY,
        ConstraintViolation.QUANTITY_NOT_ON_STEP,
        ConstraintViolation.BELOW_MINIMUM_NOTIONAL,
    }


def test_exactly_at_the_boundaries_passes() -> None:
    """ค่าที่เท่ากับขั้นต่ำพอดีต้องผ่าน — ขอบเป็น "ไม่น้อยกว่า" ไม่ใช่ "มากกว่า" """
    assert _check("0.001", "10") == ()


def test_step_that_is_not_a_power_of_ten() -> None:
    """ขั้น 0.5 — กรณีที่การนับจำนวนทศนิยมตอบไม่ได้ แต่การเทียบขั้นตอบได้"""
    step = Quantity.of("0.5", "SOL")
    passing = unmet_constraints(
        quantity=Quantity.of("2.5", "SOL"),
        notional=Money.of("100", "USDT"),
        minimum_quantity=Quantity.of("0.5", "SOL"),
        quantity_step=step,
        minimum_notional=MINIMUM_NOTIONAL,
    )
    failing = unmet_constraints(
        quantity=Quantity.of("2.6", "SOL"),
        notional=Money.of("100", "USDT"),
        minimum_quantity=Quantity.of("0.5", "SOL"),
        quantity_step=step,
        minimum_notional=MINIMUM_NOTIONAL,
    )
    assert passing == ()
    assert failing == (ConstraintViolation.QUANTITY_NOT_ON_STEP,)


def test_checking_does_not_change_the_value() -> None:
    """V-18 — ไม่ปัดค่าให้ ค่าที่ส่งเข้าไปต้องไม่ถูกเปลี่ยน"""
    quantity = Quantity.of("0.00125", "BTC")
    before = quantity.as_parts()
    unmet_constraints(
        quantity=quantity,
        notional=Money.of("120", "USDT"),
        minimum_quantity=MINIMUM_QUANTITY,
        quantity_step=QUANTITY_STEP,
        minimum_notional=MINIMUM_NOTIONAL,
    )
    assert quantity.as_parts() == before


def test_unit_mismatch_is_rejected() -> None:
    """หน่วยไม่ตรงกันต้องดัง ไม่ใช่เทียบข้ามหน่วยเงียบ ๆ"""
    with pytest.raises(MoneyError):
        unmet_constraints(
            quantity=Quantity.of("1", "ETH"),
            notional=Money.of("120", "USDT"),
            minimum_quantity=MINIMUM_QUANTITY,
            quantity_step=QUANTITY_STEP,
            minimum_notional=MINIMUM_NOTIONAL,
        )


def test_step_must_be_positive() -> None:
    """V-15.2 — ขั้นที่เป็นศูนย์ไม่มีความหมาย และต้องไม่ให้คำตอบที่ดูเหมือนถูก"""
    with pytest.raises(ArithmeticFailureError):
        Quantity.of("1", "BTC").is_multiple_of(Quantity.of(0, "BTC"))


def test_multiple_of_at_eighteen_decimal_places() -> None:
    """V-15.2 — หน่วยที่เล็กที่สุดที่ระบบเก็บได้ต้องยังตรวจการลงตัวได้"""
    smallest = Quantity.of("0.000000000000000001", "BTC")
    assert Quantity.of("0.000000000000000002", "BTC").is_multiple_of(smallest)
    assert Quantity.of("0.000000000000000001", "BTC").is_multiple_of(smallest)


@settings(max_examples=200)
@given(multiplier=st.integers(min_value=1, max_value=10**6))
def test_multiples_of_the_step_never_fail_the_quantity_rules(multiplier: int) -> None:
    """คุณสมบัติ — ปริมาณที่เป็นจำนวนเท่าของขั้นและไม่น้อยกว่าขั้นต่ำ
    **ต้องไม่มีข้อที่ไม่ผ่านด้านปริมาณ**

    ตรวจเฉพาะด้านปริมาณ เพราะปริมาณที่ถูกต้องยังอาจไม่ผ่านมูลค่าขั้นต่ำได้
    ซึ่งเป็นข้อจำกัดคนละข้อ (แก้หลังรีวิว 2026-09-28)
    """
    quantity = QUANTITY_STEP.times(multiplier)
    violations = unmet_constraints(
        quantity=quantity,
        notional=Money.of("1000000", "USDT"),
        minimum_quantity=Quantity.of(0, "BTC"),
        quantity_step=QUANTITY_STEP,
        minimum_notional=Money.of(0, "USDT"),
    )
    assert ConstraintViolation.QUANTITY_NOT_ON_STEP not in violations
    assert ConstraintViolation.BELOW_MINIMUM_QUANTITY not in violations


@settings(max_examples=200)
@given(
    multiplier=st.integers(min_value=1, max_value=10**6),
    offset=st.integers(min_value=1, max_value=9),
)
def test_values_between_steps_always_fail_the_step_rule(multiplier: int, offset: int) -> None:
    """คุณสมบัติ — ค่าที่อยู่ระหว่างขั้นต้องไม่ผ่านข้อของขั้นเสมอ

    บวกเศษที่เล็กกว่าขั้นเข้าไป ค่าที่ได้จึงอยู่ระหว่างสองขั้นพอดี
    """
    remainder = Quantity.of(f"0.0000{offset}", "BTC")
    quantity = QUANTITY_STEP.times(multiplier) + remainder
    violations = unmet_constraints(
        quantity=quantity,
        notional=Money.of("1000000", "USDT"),
        minimum_quantity=Quantity.of(0, "BTC"),
        quantity_step=QUANTITY_STEP,
        minimum_notional=Money.of(0, "USDT"),
    )
    assert ConstraintViolation.QUANTITY_NOT_ON_STEP in violations


@settings(max_examples=100)
@given(shortfall=st.integers(min_value=1, max_value=10**4))
def test_notional_below_minimum_always_fails_only_the_notional_rule(shortfall: int) -> None:
    """คุณสมบัติของมูลค่าแยกจากปริมาณ — มูลค่าที่น้อยกว่าขั้นต่ำต้องไม่ผ่านข้อของมูลค่าเสมอ"""
    notional = MINIMUM_NOTIONAL - Money.of("0.01", "USDT").times(shortfall)
    violations = unmet_constraints(
        quantity=QUANTITY_STEP.times(20),
        notional=notional,
        minimum_quantity=Quantity.of(0, "BTC"),
        quantity_step=QUANTITY_STEP,
        minimum_notional=MINIMUM_NOTIONAL,
    )
    assert violations == (ConstraintViolation.BELOW_MINIMUM_NOTIONAL,)
