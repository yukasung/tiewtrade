"""เทสต์ด้วยตัวเลขจริง — V-3 ถึง V-10, V-21

**คำตอบทุกตัวคำนวณมือขึ้นมาเอง ไม่ได้ลอกจากโค้ดที่กำลังทดสอบ** (RQ-12)
ที่มาของคำตอบเขียนกำกับไว้ในแต่ละกรณี
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from tests.core.money.conftest import MAX_STORABLE, MIN_STORABLE
from tiewtrade.core.money import (
    InvalidInputTypeError,
    InvalidUnitError,
    Money,
    MoneyError,
    NotFiniteValueError,
    OutOfRangeError,
    Quantity,
    TooManyDecimalPlacesError,
)
from tiewtrade.core.money.validation import normalise_amount


class TestNotFinite:
    """V-3 — ค่าที่ไม่ใช่จำนวนจำกัดต้องถูกปฏิเสธตั้งแต่สร้าง"""

    @pytest.mark.parametrize("raw", ["NaN", "sNaN", "Infinity", "-Infinity"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(NotFiniteValueError):
            Money.of(raw, "USDT")


class TestInputTypes:
    """V-4 — รับเฉพาะ str, int, Decimal"""

    @pytest.mark.parametrize("raw", ["1.5", 5, Decimal("2.25")])
    def test_accepted(self, raw: str | int | Decimal) -> None:
        assert Money.of(raw, "USDT").amount == Decimal(str(raw))

    def test_bool_rejected(self) -> None:
        """`bool` เป็น subclass ของ `int` ถ้าไม่ตรวจแยก True จะกลายเป็นเงิน 1 หน่วย"""
        with pytest.raises(InvalidInputTypeError):
            Money.of(True, "USDT")

    def test_binary_floating_point_rejected(self) -> None:
        """ทศนิยมลอยตัวพาความคลาดเคลื่อนเข้ามา เช่นค่าที่เขียนว่า 0.1 ไม่ใช่ 0.1 จริง"""
        with pytest.raises(InvalidInputTypeError):
            Money.of(0.1, "USDT")  # type: ignore[arg-type]

    def test_none_rejected(self) -> None:
        with pytest.raises(InvalidInputTypeError):
            Money.of(None, "USDT")  # type: ignore[arg-type]


class TestDecimalPlaces:
    """V-5, V-5.1 — นับทศนิยมจากค่าจริง และการตรวจต้องไม่ผ่านการปัด"""

    def test_trailing_zeros_do_not_count(self) -> None:
        """`1.` ตามด้วยศูนย์ 19 ตัว มีค่าเท่ากับ 1 พอดี จึงมีทศนิยมจริง 0 ตำแหน่ง"""
        assert Money.of("1." + "0" * 19, "USDT").amount == Decimal(1)

    def test_nineteen_real_places_rejected(self) -> None:
        """ทศนิยมจริง 19 ตำแหน่ง เกินที่เก็บได้ 18 ตำแหน่งอยู่หนึ่งตำแหน่ง"""
        with pytest.raises(TooManyDecimalPlacesError):
            Money.of("0." + "0" * 18 + "1", "USDT")

    def test_eighteen_real_places_accepted(self) -> None:
        assert Money.of("0." + "0" * 17 + "1", "USDT").amount == Decimal("1E-18")

    def test_long_trailing_zeros_beyond_compute_precision(self) -> None:
        """ยาวเกินความละเอียดการคำนวณ แต่ค่าจริงคือ 1 — ต้องรับได้

        `normalize()` ให้ผลเป็น `1` ทั้งกรณีนี้และกรณีถัดไป
        การตรวจที่ผ่านการปัดจึงแยกสองกรณีนี้ไม่ออก
        """
        assert Money.of("1." + "0" * 80, "USDT").amount == Decimal(1)

    def test_nonzero_beyond_compute_precision_rejected(self) -> None:
        """ตำแหน่งที่ 81 ไม่ใช่ศูนย์ ค่าจริงจึงมีทศนิยม 81 ตำแหน่ง"""
        with pytest.raises(TooManyDecimalPlacesError):
            Money.of("1." + "0" * 80 + "1", "USDT")

    def test_same_pair_as_decimal_input(self) -> None:
        """กฎเดียวกันต้องใช้กับ `Decimal` ที่ส่งเข้ามาตรง ๆ ไม่ใช่เฉพาะข้อความ"""
        assert Money.of(Decimal("1." + "0" * 80), "USDT").amount == Decimal(1)
        with pytest.raises(TooManyDecimalPlacesError):
            Money.of(Decimal("1." + "0" * 80 + "1"), "USDT")


class TestRange:
    """V-6 — ช่วงค่าต้องตรงกับ NUMERIC(38,18)"""

    def test_largest_storable_accepted(self) -> None:
        """20 หลักหน้าจุดและ 18 หลังจุด คือค่าที่ใหญ่ที่สุดที่คอลัมน์รับได้"""
        assert Money.of(MAX_STORABLE, "USDT").amount == MAX_STORABLE

    def test_one_above_the_ceiling_rejected(self) -> None:
        """10^20 ต้องใช้หน้าจุด 21 หลัก ซึ่งเกินที่คอลัมน์มี"""
        with pytest.raises(OutOfRangeError):
            Money.of("100000000000000000000", "USDT")

    def test_negative_bound_symmetric(self) -> None:
        assert Money.of(MIN_STORABLE, "USDT").amount == MIN_STORABLE
        with pytest.raises(OutOfRangeError):
            Money.of("-100000000000000000000", "USDT")


class TestZeroAndNegative:
    """V-7, V-8"""

    def test_negative_zero_becomes_zero(self) -> None:
        assert Money.of("-0", "USDT").as_parts()["amount"] == "0"

    def test_negative_amounts_allowed(self) -> None:
        """ชนิดพื้นฐานแทนยอดที่เปลี่ยนแปลงได้ ข้อจำกัดเป็นของโดเมนที่ใช้"""
        assert Money.of("-45.5", "USDT").amount == Decimal("-45.5")
        assert Quantity.of("-0.5", "BTC").amount == Decimal("-0.5")


class TestUnits:
    """V-9 — หน่วยต้องถูกตรวจที่ runtime"""

    def test_unit_is_upper_cased(self) -> None:
        assert Money.of("1", "usdt").currency == "USDT"

    @pytest.mark.parametrize("unit", ["", " ", "us dt", "US-DT", "US_DT"])
    def test_malformed_unit_rejected(self, unit: str) -> None:
        with pytest.raises(InvalidUnitError):
            Money.of("1", unit)


class TestSharedRules:
    """V-10 — ทางเข้าทั้งสามทางใช้กฎตรวจค่าชุดเดียวกัน"""

    @pytest.mark.parametrize(
        "bad", ["NaN", "Infinity", "0." + "0" * 18 + "1", "100000000000000000000"]
    )
    def test_same_rejections_everywhere(self, bad: str) -> None:
        with pytest.raises(MoneyError) as money_error:
            Money.of(bad, "USDT")
        with pytest.raises(MoneyError) as quantity_error:
            Quantity.of(bad, "BTC")
        with pytest.raises(MoneyError) as scalar_error:
            normalise_amount(bad)
        assert type(money_error.value) is type(quantity_error.value) is type(scalar_error.value)


class TestImmutability:
    """V-21 — สร้างแล้วแก้ไม่ได้"""

    def test_amount_cannot_be_reassigned(self) -> None:
        money = Money.of("1", "USDT")
        with pytest.raises(FrozenInstanceError):
            money.amount = Decimal(2)  # type: ignore[misc]
