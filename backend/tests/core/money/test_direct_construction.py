"""เส้นทางที่ไม่ผ่าน `of` ต้องถูกตรวจเท่ากัน

บั๊กทั้งหมดในไฟล์นี้หลุดด่านชุดแรกมาได้ เพราะเทสต์เดิมสร้างค่าผ่าน `of`
อย่างเดียว ทั้งที่ constructor เป็นทางเข้าสาธารณะเหมือนกัน
พบจากการรีวิวโค้ด 2026-09-27
"""

from decimal import Context, Decimal, localcontext

import pytest

from tests.core.money.conftest import HOSTILE_SETTINGS
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


class TestConstructorIsGuarded:
    """การสร้างโดยตรงต้องผ่านการตรวจชุดเดียวกับ `of`"""

    def test_out_of_range_rejected(self) -> None:
        with pytest.raises(OutOfRangeError):
            Money(Decimal("1E+25"), "USDT")

    def test_too_many_places_rejected(self) -> None:
        with pytest.raises(TooManyDecimalPlacesError):
            Money(Decimal("0.1234567890123456789012"), "USDT")

    def test_non_finite_rejected(self) -> None:
        """ต้องได้ข้อผิดพลาดของโมดูล ไม่ใช่ `InvalidOperation` ของ `Decimal`"""
        with pytest.raises(NotFiniteValueError):
            Money(Decimal("NaN"), "USDT")

    def test_uncanonical_unit_rejected(self) -> None:
        with pytest.raises(InvalidUnitError):
            Money(Decimal(1), "us dt")

    def test_lower_case_unit_rejected(self) -> None:
        """constructor รับเฉพาะหน่วยที่อยู่ในรูปมาตรฐานแล้ว การแปลงเป็นหน้าที่ของ `of`"""
        with pytest.raises(InvalidUnitError):
            Money(Decimal(1), "usdt")

    def test_non_decimal_amount_rejected(self) -> None:
        with pytest.raises(InvalidInputTypeError):
            Money("1", "USDT")  # type: ignore[arg-type]

    @pytest.mark.parametrize("outside", HOSTILE_SETTINGS)
    def test_range_check_survives_hostile_context(self, outside: Context) -> None:
        """ขอบล่างเคยกลายเป็นค่าอนันต์เมื่อ `Emax` แคบ ทำให้ค่าที่ล้นผ่านได้

        การตรวจช่วงต้องรันใต้ขอบเขตของโมดูล ไม่ใช่ของผู้เรียก
        """
        with localcontext(outside), pytest.raises(OutOfRangeError):
            Money(Decimal("-1E+25"), "USDT")


class TestEqualityAcrossUnits:
    """เทียบเท่ากันข้ามหน่วยต้องดัง ไม่ใช่คืนค่าเท็จเงียบ ๆ"""

    def test_equality_across_currencies(self) -> None:
        with pytest.raises(MoneyError):
            _ = Money.of("1", "USDT") == Money.of("1", "THB")

    def test_inequality_across_currencies(self) -> None:
        with pytest.raises(MoneyError):
            _ = Money.of("1", "USDT") != Money.of("1", "THB")

    def test_equality_across_types(self) -> None:
        with pytest.raises(MoneyError):
            _ = Money.of("1", "USDT") == Quantity.of("1", "BTC")

    def test_same_unit_still_compares(self) -> None:
        assert Money.of("1", "USDT") == Money.of("1", "USDT")
        assert Money.of("1", "USDT") != Money.of("2", "USDT")

    def test_equal_values_hash_the_same(self) -> None:
        assert hash(Money.of("1.0", "USDT")) == hash(Money.of("1", "USDT"))


class TestZeroWrittenWithManyPlaces:
    """ศูนย์เขียนได้หลายรูปแบบ ทุกรูปแบบมีทศนิยมจริงศูนย์ตำแหน่ง"""

    @pytest.mark.parametrize("raw", ["0", "0.0", "0." + "0" * 20, "0E-25", "-0.000"])
    def test_accepted_and_canonical(self, raw: str) -> None:
        assert Money.of(raw, "USDT").as_parts()["amount"] == "0"


class TestUnitCharacters:
    """หน่วยต้องไม่ชนกันหลังแปลงเป็นตัวพิมพ์ใหญ่"""

    @pytest.mark.parametrize(
        "unit",
        [
            pytest.param("\u0131", id="dotless-i"),  # upper() ได้ I
            pytest.param("\u00df", id="eszett"),  # upper() ได้ SS
            pytest.param("BTC\u0660", id="arabic-indic-zero"),  # isalnum() ผ่าน
            pytest.param("\uff55\uff53\uff44\uff54", id="fullwidth"),  # หน้าตาเหมือน usdt
        ],
    )
    def test_non_ascii_units_rejected(self, unit: str) -> None:
        """ตัว i ไม่มีจุดของตุรกีกลายเป็น I และ eszett ของเยอรมันกลายเป็น SS

        ถ้าปล่อยผ่าน หน่วยสองตัวที่ต่างกันจะชนกันหลังแปลงเป็นตัวพิมพ์ใหญ่
        """
        with pytest.raises(InvalidUnitError):
            Money.of("1", unit)

    def test_ascii_units_accepted(self) -> None:
        assert Money.of("1", "usdt").unit == "USDT"
        assert Quantity.of("1", "btc").unit == "BTC"
