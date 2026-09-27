"""เทสต์การคำนวณด้วยตัวเลขจริง — V-11 ถึง V-16

**คำตอบทุกตัวคำนวณมือขึ้นมาเอง** ที่มาเขียนกำกับไว้ในแต่ละกรณี (RQ-12)
"""

from decimal import Decimal

import pytest

from tests.core.money.conftest import (
    MAX_STORABLE,
    MIN_STORABLE,
    NEGATIVE_SMALLEST,
    SMALLEST,
)
from tiewtrade.core.money import (
    InvalidInputTypeError,
    Money,
    NotFiniteValueError,
    OutOfRangeError,
    Quantity,
    RoundingDirection,
    RoundingRequiredError,
    UnitMismatchError,
)


class TestAddAndSubtract:
    def test_addition_by_hand(self) -> None:
        """12.34 + 7.66 = 20.00 — บวกทศนิยมสองตำแหน่งตรงไปตรงมา"""
        total = Money.of("12.34", "USDT") + Money.of("7.66", "USDT")
        assert total.amount == Decimal("20")

    def test_ten_tenths_make_one(self) -> None:
        """บวก 0.1 สิบครั้งต้องได้ 1 พอดี ซึ่งทศนิยมลอยตัวทำไม่ได้"""
        total = Money.of("0", "USDT")
        for _ in range(10):
            total = total + Money.of("0.1", "USDT")
        assert total.amount == Decimal(1)

    def test_subtraction_can_go_negative(self) -> None:
        """5 - 8 = -3 ชนิดนี้แทนยอดที่เปลี่ยนแปลงได้ จึงติดลบได้"""
        assert (Money.of("5", "USDT") - Money.of("8", "USDT")).amount == Decimal(-3)

    def test_addition_at_the_ceiling_overflows(self) -> None:
        """ค่าสูงสุดบวกหน่วยเล็กที่สุดได้ 10^20 พอดี ซึ่งเก็บไม่ได้ (V-13.2)"""
        with pytest.raises(OutOfRangeError):
            Money.of(MAX_STORABLE, "USDT") + Money.of(SMALLEST, "USDT")

    def test_subtraction_at_the_floor_overflows(self) -> None:
        with pytest.raises(OutOfRangeError):
            Money.of(MIN_STORABLE, "USDT") - Money.of(SMALLEST, "USDT")


class TestUnitMismatch:
    """V-9 — ทุกการคำนวณข้ามหน่วยต้องคืนข้อผิดพลาดที่ระบุชนิดได้"""

    def test_money_across_currencies(self) -> None:
        with pytest.raises(UnitMismatchError):
            Money.of("1", "USDT") + Money.of("1", "THB")

    def test_quantity_across_assets(self) -> None:
        with pytest.raises(UnitMismatchError):
            Quantity.of("1", "BTC") + Quantity.of("1", "ETH")

    def test_money_with_quantity(self) -> None:
        with pytest.raises(UnitMismatchError):
            Money.of("1", "USDT") + Quantity.of("1", "BTC")

    def test_comparison_across_units(self) -> None:
        with pytest.raises(UnitMismatchError):
            _ = Money.of("1", "USDT") < Money.of("1", "THB")


class TestMultiplication:
    def test_exact_product_by_hand(self) -> None:
        """2.5 x 4 = 10 ลงตัว ไม่ต้องปัด และห้ามมีการปัดเกิดขึ้น (V-11)"""
        assert Money.of("2.5", "USDT").times("4").amount == Decimal(10)

    def test_exact_product_keeps_all_places(self) -> None:
        """0.000000000000000001 x 1 คงทศนิยม 18 ตำแหน่งไว้ครบ"""
        assert Money.of(SMALLEST, "USDT").times("1").amount == Decimal("1E-18")

    def test_product_needing_rounding_without_direction(self) -> None:
        """1E-18 x 0.1 = 1E-19 ซึ่งมี 19 ตำแหน่ง เกินที่เก็บได้ (V-12)"""
        with pytest.raises(RoundingRequiredError):
            Money.of(SMALLEST, "USDT").times("0.1")

    @pytest.mark.parametrize(
        ("direction", "expected"),
        [
            (RoundingDirection.TOWARD_ZERO, "0"),
            (RoundingDirection.AWAY_FROM_ZERO, "1E-18"),
            (RoundingDirection.TOWARD_POSITIVE, "1E-18"),
            (RoundingDirection.TOWARD_NEGATIVE, "0"),
        ],
    )
    def test_positive_product_each_direction(
        self, direction: RoundingDirection, expected: str
    ) -> None:
        """1E-19 อยู่ระหว่าง 0 กับ 1E-18 — ทิศทางเป็นตัวตัดสินว่าไปทางไหน"""
        result = Money.of(SMALLEST, "USDT").times("0.1", direction)
        assert result.amount == Decimal(expected)

    @pytest.mark.parametrize(
        ("direction", "expected"),
        [
            (RoundingDirection.TOWARD_ZERO, "0"),
            (RoundingDirection.AWAY_FROM_ZERO, "-1E-18"),
            (RoundingDirection.TOWARD_POSITIVE, "0"),
            (RoundingDirection.TOWARD_NEGATIVE, "-1E-18"),
        ],
    )
    def test_negative_product_each_direction(
        self, direction: RoundingDirection, expected: str
    ) -> None:
        """ด้านลบต้องตรวจแยก เพราะคำว่าขึ้นและลงกลับความหมายกับค่าลบ (V-16)"""
        result = Money.of(NEGATIVE_SMALLEST, "USDT").times("0.1", direction)
        assert result.amount == Decimal(expected)

    def test_operands_are_not_rounded_before_multiplying(self) -> None:
        """ตัวตั้งที่มี 18 ตำแหน่งต้องเข้าการคูณครบทุกหลัก (V-14)

        1E-18 x 1000000 = 1E-12 ซึ่งพอดี ไม่ต้องปัด
        ถ้า operand ถูกปัดก่อนคูณ ผลจะกลายเป็น 0
        """
        assert Money.of(SMALLEST, "USDT").times("1000000").amount == Decimal("1E-12")

    def test_product_out_of_range(self) -> None:
        """10^19 x 100 = 10^21 ซึ่งเกินช่วงตั้งแต่ผลดิบ (V-13)"""
        with pytest.raises(OutOfRangeError):
            Money.of("10000000000000000000", "USDT").times("100")

    def test_rounding_pushes_product_over_the_ceiling(self) -> None:
        """ผลคูณยังไม่ล้น แต่ปัดออกห่างจากศูนย์แล้วล้น (V-13.1)

        9999999999.999999999999999999 x 10000000000.000000000000000001
        เท่ากับ 10^20 - 10^-36 ซึ่งน้อยกว่าเพดานอยู่นิดเดียว
        ปัดเหลือ 18 ตำแหน่งออกห่างจากศูนย์จะได้ 10^20 พอดี ซึ่งเก็บไม่ได้
        """
        big = Money.of("9999999999.999999999999999999", "USDT")
        with pytest.raises(OutOfRangeError):
            big.times("10000000000.000000000000000001", RoundingDirection.AWAY_FROM_ZERO)

    def test_same_product_rounded_toward_zero_fits(self) -> None:
        """ผลเดียวกันปัดเข้าหาศูนย์ได้ค่าสูงสุดที่เก็บได้ จึงต้องสำเร็จ"""
        big = Money.of("9999999999.999999999999999999", "USDT")
        result = big.times("10000000000.000000000000000001", RoundingDirection.TOWARD_ZERO)
        assert result.amount == MAX_STORABLE

    def test_scalar_follows_the_same_rules(self) -> None:
        """ตัวเลขเปล่าใช้กฎตรวจค่าชุดเดียวกัน (V-10)"""
        with pytest.raises(NotFiniteValueError):
            Money.of("1", "USDT").times("NaN")
        with pytest.raises(InvalidInputTypeError):
            Money.of("1", "USDT").times(True)
