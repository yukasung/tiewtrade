"""ขอบของโมดูลต้องคืนข้อผิดพลาดชนิดของตัวเองเสมอ (RQ-14, P-8)

ผู้เรียกดักข้อผิดพลาดที่คาดได้ด้วย `MoneyError` ชนิดเดียว ถ้ามี `AttributeError`
หรือข้อผิดพลาดของ `Decimal` รั่วออกไป สัญญานั้นก็ไม่จริง

พบจากการรีวิว `specs/reviews/2026-09-27-money-types-uncommitted.md`
"""

from collections.abc import Callable
from decimal import Decimal, DecimalException

import pytest

from tiewtrade.core.money import (
    InvalidInputTypeError,
    InvalidUnitError,
    Money,
    MoneyError,
    Quantity,
    RoundingDirection,
)
from tiewtrade.core.money.context import guarded


class TestRoundingDirectionArgument:
    """ทิศทางการปัดผิดชนิดต้องดังทันที ไม่ใช่ดังเฉพาะตอนบังเอิญต้องปัด"""

    def test_rejected_when_product_needs_rounding(self) -> None:
        with pytest.raises(InvalidInputTypeError):
            Money.of("1E-18", "USDT").times("0.1", "SIDEWAYS")  # type: ignore[arg-type]

    def test_rejected_even_when_product_is_exact(self) -> None:
        """เดิมกรณีนี้ผ่านเงียบ ๆ เพราะไม่มีการปัดจึงไม่มีใครแตะค่าที่ผิดชนิด

        พฤติกรรมที่ขึ้นกับว่าบังเอิญต้องปัดหรือไม่ ทำให้บั๊กโผล่ตอนข้อมูลเปลี่ยน
        """
        with pytest.raises(InvalidInputTypeError):
            Money.of("2", "USDT").times("3", "SIDEWAYS")  # type: ignore[arg-type]

    def test_valid_direction_still_works(self) -> None:
        result = Money.of("1E-18", "USDT").times("0.1", RoundingDirection.AWAY_FROM_ZERO)
        assert result.amount == Decimal("1E-18")

    def test_none_still_means_no_rounding_allowed(self) -> None:
        assert Money.of("2", "USDT").times("3").amount == Decimal(6)


class TestFromPartsWithMalformedInput:
    """ข้อมูลที่อ่านกลับมาจาก API หรือฐานข้อมูลอาจผิดรูปได้ทุกแบบ"""

    @pytest.mark.parametrize(
        "parts",
        [
            pytest.param([], id="list"),
            pytest.param("x", id="string"),
            pytest.param(None, id="none"),
            pytest.param(42, id="number"),
        ],
    )
    def test_non_mapping_rejected(self, parts: object) -> None:
        with pytest.raises(MoneyError):
            Money.from_parts(parts)  # type: ignore[arg-type]

    def test_missing_unit_rejected(self) -> None:
        with pytest.raises(InvalidUnitError):
            Money.from_parts({"amount": "1"})

    def test_missing_amount_rejected(self) -> None:
        with pytest.raises(MoneyError):
            Money.from_parts({"currency": "USDT"})

    def test_quantity_has_the_same_guarantee(self) -> None:
        with pytest.raises(MoneyError):
            Quantity.from_parts([])  # type: ignore[arg-type]


class TestNegativeZeroFromDirectConstruction:
    """ลบศูนย์ต้องเป็นศูนย์รูปแบบเดียว ไม่ว่าสร้างทางไหน (RQ-16, Q-4.5)"""

    def test_money_built_directly(self) -> None:
        assert not Money(Decimal("-0"), "USDT").amount.is_signed()

    def test_quantity_built_directly(self) -> None:
        assert not Quantity(Decimal("-0"), "BTC").amount.is_signed()

    def test_money_built_through_of(self) -> None:
        assert not Money.of("-0", "USDT").amount.is_signed()

    def test_both_paths_agree(self) -> None:
        assert Money(Decimal("-0"), "USDT") == Money.of("-0", "USDT")

    def test_arithmetic_producing_negative_zero(self) -> None:
        """คูณศูนย์ด้วยค่าลบให้ลบศูนย์ ซึ่งต้องถูกทำให้เป็นศูนย์เช่นกัน"""
        assert not Money.of("0", "USDT").times("-1").amount.is_signed()


class TestDecimalErrorsFromArithmetic:
    """V-2.1 — ข้อผิดพลาดของ `Decimal` จากการคำนวณต้องไม่รั่ว

    ต่างจากกรณีอ่านข้อความผิดรูป ซึ่ง `_to_decimal` แปลงไว้แล้วโดยเฉพาะ
    กรณีนี้ทดสอบเส้นทางการคำนวณจริง
    """

    def test_signal_raised_inside_a_guarded_call_is_translated(self) -> None:
        """จำลองสัญญาณของ `Decimal` ที่เกิดภายในขอบเขตของโมดูล

        ใช้การจำลองเพราะ input ที่ถูกต้องตามกฎของโมดูลไม่สามารถทำให้เกิด
        สัญญาณเหล่านี้ได้ — ห้ามลดความเข้มของ context หรือขยายขอบเขตค่า
        ที่อนุมัติแล้วเพื่อสร้างกรณีทดสอบ
        """

        @guarded
        def inner() -> None:
            raise DecimalException("สัญญาณจากการคำนวณ")

        with pytest.raises(MoneyError):
            inner()

    def test_arithmetic_at_the_boundary_raises_module_errors(self) -> None:
        """เส้นทางคำนวณจริงที่ชนขอบ ต้องได้ข้อผิดพลาดของโมดูลเท่านั้น"""
        biggest = Money.of("99999999999999999999.999999999999999999", "USDT")
        smallest = Money.of("0.000000000000000001", "USDT")

        operations: list[Callable[[], object]] = [
            lambda: biggest + smallest,
            lambda: biggest.times("10"),
            lambda: biggest.times("1.5", RoundingDirection.AWAY_FROM_ZERO),
        ]
        for operation in operations:
            with pytest.raises(MoneyError):
                operation()
