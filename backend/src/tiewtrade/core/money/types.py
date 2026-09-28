"""ชนิดข้อมูลเงินและปริมาณ (RQ-1, RQ-8, RQ-15, RQ-17, RQ-23)

สองชนิดนี้ผูกหน่วยติดมาด้วย เงินผูกสกุลเงิน ปริมาณผูกเหรียญ
คนละหน่วยคำนวณหรือเทียบกันไม่ได้ และเงินกับปริมาณคำนวณข้ามกันไม่ได้

ความผิดพลาดเรื่องหน่วยเป็นแบบที่ไม่มีอะไรพัง ตัวเลขออกมาดูปกติแต่ความหมายผิด
การผูกหน่วยทำให้มันดังตั้งแต่ตอนคำนวณ

**ทุกค่าที่มีชีวิตอยู่ผ่านจุดตรวจเดียวกัน** `__post_init__` บังคับ invariant ทั้งชุด
จึงไม่มีทางสร้างค่าที่ผิดกฎได้ แม้เรียก constructor ตรง ๆ โดยไม่ผ่าน `of`

**ตัวเลขเปล่าที่เอามาคูณไม่ใช่ชนิดสาธารณะ** เป็น input ที่ผ่านกฎตรวจชุดเดียวกัน
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import total_ordering
from typing import ClassVar, Self

from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import (
    ArithmeticFailureError,
    InvalidInputTypeError,
    RoundingRequiredError,
    UnitMismatchError,
)
from tiewtrade.core.money.rounding import (
    RoundingDirection,
    needs_rounding,
    round_to_stored_scale,
)
from tiewtrade.core.money.validation import (
    NumberInput,
    ensure_canonical_unit,
    ensure_valid_amount,
    normalise_amount,
    normalise_unit,
)


def _canonical_text(amount: Decimal) -> str:
    """เขียนเป็นข้อความมาตรฐาน (RQ-19)

    ตัดศูนย์ท้ายเฉพาะส่วนทศนิยม ศูนย์เป็น `"0"` และไม่ใช้รูปแบบวิทยาศาสตร์
    """
    text = format(amount.copy_abs(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text == "0":
        return text
    return f"-{text}" if amount.is_signed() else text


@total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class _UnitBound:
    """ฐานร่วมของชนิดที่ผูกหน่วย — เก็บจำนวนกับหน่วย และสร้างแล้วแก้ไม่ได้"""

    #: ชื่อช่องของจำนวนและของหน่วย ตอนแปลงเป็นข้อความ (RQ-20)
    _AMOUNT_KEY: ClassVar[str] = "amount"
    _UNIT_KEY: ClassVar[str] = "unit"

    amount: Decimal
    unit: str

    @guarded
    def __post_init__(self) -> None:
        """จุดตรวจเดียวที่ทุกค่าต้องผ่าน

        เขียนไว้ที่นี่เพื่อให้การสร้างค่าโดยตรงก็เลี่ยงการตรวจไม่ได้
        ไม่ใช่ตรวจซ้ำ ๆ ในแต่ละเมธอดที่คำนวณ ซึ่งจะลืมได้เมื่อเพิ่มเมธอดใหม่

        **ต้องครอบด้วยขอบเขตของโมดูลด้วย** เพราะเป็นทางเข้าที่คนนอกเรียกได้
        โดยไม่ผ่านเมธอดอื่น ถ้าไม่ครอบ การตรวจช่วงค่าจะรันใต้ context ของผู้เรียก
        แล้วขอบล่างจะกลายเป็นค่าอนันต์หรือโยนข้อผิดพลาดของ `Decimal` ออกไป

        ตรวจ invariant ทั้งชุด ไม่ใช่แค่ช่วงค่า มิฉะนั้นการสร้างโดยตรง
        จะข้ามการตรวจชนิด ความละเอียด และรูปแบบหน่วยไปทั้งหมด
        """
        ensure_valid_amount(self.amount)
        ensure_canonical_unit(self.unit)
        if self.amount.is_zero() and self.amount.is_signed():
            # ลบศูนย์เท่ากับศูนย์แต่แสดงผลต่างกัน ต้องเป็นรูปแบบเดียวทุกทางเข้า
            # ไม่ใช่เฉพาะตอนแปลงเป็นข้อความ มิฉะนั้นค่าที่เท่ากันจะมีสองหน้าตา
            object.__setattr__(self, "amount", Decimal(0))

    @classmethod
    def _checked(cls, amount: Decimal, unit: str) -> Self:
        """สร้างค่าใหม่จากผลการคำนวณ

        การตรวจและการทำให้เป็นรูปแบบมาตรฐานอยู่ใน `__post_init__` ทั้งหมด
        """
        return cls(amount, unit)

    @classmethod
    @guarded
    def of(cls, amount: NumberInput, unit: str) -> Self:
        """ทางเข้าหลักสำหรับสร้างค่าจากข้อมูลภายนอก"""
        return cls(normalise_amount(amount), normalise_unit(unit))

    def _same_kind(self, other: object) -> Self:
        """ตรวจว่าอีกฝั่งเป็นชนิดเดียวกันและหน่วยเดียวกัน

        ตรวจที่ runtime เสมอ เพราะหน่วยเป็นข้อมูลที่รู้ค่าตอนรัน มาจาก API
        และฐานข้อมูล การตรวจตอนเขียนโค้ดจึงทดแทนไม่ได้
        """
        if not isinstance(other, type(self)) or type(other) is not type(self):
            raise UnitMismatchError(f"{type(self).__name__} คำนวณกับ {type(other).__name__} ไม่ได้")
        if other.unit != self.unit:
            raise UnitMismatchError(f"หน่วย {self.unit} กับ {other.unit} คำนวณด้วยกันไม่ได้")
        return other

    @guarded
    def __add__(self, other: object) -> Self:
        counterpart = self._same_kind(other)
        return self._checked(self.amount + counterpart.amount, self.unit)

    @guarded
    def __sub__(self, other: object) -> Self:
        counterpart = self._same_kind(other)
        return self._checked(self.amount - counterpart.amount, self.unit)

    def __eq__(self, other: object) -> bool:
        """เทียบเท่ากันข้ามหน่วยต้องดัง ไม่ใช่คืนค่าเท็จเงียบ ๆ

        `__eq__` ที่ dataclass สร้างให้จะคืน `False` เมื่อหน่วยต่างกัน
        ซึ่งเป็นผลลัพธ์ที่อันตรายที่สุด — โค้ดอย่าง `ยอดคงเหลือ == ยอดที่ต้องใช้`
        จะทำงานต่อไปเงียบ ๆ ทั้งที่เทียบคนละสกุล
        """
        return self.amount == self._same_kind(other).amount

    def __hash__(self) -> int:
        """ค่าที่เท่ากันต้องได้ค่าเดียวกัน — รวมชนิดและหน่วยเข้าไปด้วย"""
        return hash((type(self).__name__, self.amount, self.unit))

    @guarded
    def __lt__(self, other: object) -> bool:
        """`total_ordering` สร้างตัวเปรียบเทียบที่เหลือจากตัวนี้กับ `__eq__`"""
        return self.amount < self._same_kind(other).amount

    @guarded
    def times(
        self,
        factor: NumberInput,
        rounding: RoundingDirection | None = None,
    ) -> Self:
        """คูณด้วยตัวเลขเปล่า (RQ-23)

        ผลพอดีคืนค่าเป๊ะ ผลที่ละเอียดเกินความละเอียดที่เก็บได้ปัดได้
        เมื่อระบุทิศทาง ถ้าไม่ระบุให้คืนข้อผิดพลาด

        **ปัดเฉพาะผลคูณ ไม่ปัด operand ก่อนคูณ**
        """
        if rounding is not None and not isinstance(rounding, RoundingDirection):
            # ตรวจที่ทางเข้า ไม่ใช่ตอนจะใช้ มิฉะนั้นค่าที่ผิดชนิดจะผ่านเงียบ ๆ
            # เมื่อผลคูณบังเอิญพอดีจนไม่ต้องปัด
            raise InvalidInputTypeError(
                f"ทิศทางการปัดต้องเป็น RoundingDirection ไม่ใช่ {type(rounding).__name__}"
            )

        product = self.amount * normalise_amount(factor)

        if needs_rounding(product):
            if rounding is None:
                raise RoundingRequiredError("ผลคูณมีทศนิยมเกินที่เก็บได้ ต้องระบุทิศทางการปัด")
            product = round_to_stored_scale(product, rounding)

        return self._checked(product, self.unit)

    @guarded
    def is_multiple_of(self, step: object) -> bool:
        """เป็นจำนวนเท่าของ `step` แบบลงตัวหรือไม่ (F-33)

        มีไว้ให้กฎข้อจำกัดของเหรียญตรวจว่าปริมาณที่สั่งตรงขั้นที่ตลาดยอมหรือไม่
        (`standards/trading-safety.md` หัวข้อ 3) ซึ่งเป็นงานแรกที่ต้องใช้การหาร
        ตามที่ F-02 เขียนนโยบายไว้ล่วงหน้า (F-02 Q-1.3)

        **คืนค่าจริง/เท็จ ไม่คืนผลหารและไม่ปัดอะไรให้** เพราะการปัดต้องเป็น
        การตัดสินใจของผู้เรียกที่ระบุทิศทางชัดเจนทุกครั้ง (RQ-3, RQ-4 ของ F-02)

        `step` ต้องเป็นหน่วยเดียวกันและมากกว่าศูนย์ — ขั้นที่เป็นศูนย์หรือติดลบ
        ไม่มีความหมายในโดเมนนี้ และการปล่อยผ่านจะให้คำตอบที่ดูเหมือนถูก
        """
        divisor = self._same_kind(step)
        if not divisor.amount > 0:
            raise ArithmeticFailureError("ขั้นที่ใช้ตรวจการลงตัวต้องมากกว่าศูนย์")
        return self.amount % divisor.amount == 0

    @guarded
    def as_parts(self) -> dict[str, str]:
        """ส่งค่ากับหน่วยแยกช่องกัน (RQ-20)"""
        return {self._AMOUNT_KEY: _canonical_text(self.amount), self._UNIT_KEY: self.unit}

    @classmethod
    def from_parts(cls, parts: Mapping[str, str]) -> Self:
        """อ่านกลับ พร้อมตรวจหน่วยด้วย (RQ-18, RQ-20)

        ข้อมูลที่อ่านกลับมาจาก API หรือฐานข้อมูลผิดรูปได้ทุกแบบ จึงตรวจชนิด
        ก่อนแตะ ไม่ใช่ปล่อยให้ `AttributeError` รั่วออกไปหาผู้เรียก
        """
        if not isinstance(parts, Mapping):
            raise InvalidInputTypeError(f"ต้องเป็นข้อมูลแบบ mapping ไม่ใช่ {type(parts).__name__}")
        return cls.of(parts.get(cls._AMOUNT_KEY, ""), parts.get(cls._UNIT_KEY, ""))


@dataclass(frozen=True, slots=True, eq=False)
class Money(_UnitBound):
    """จำนวนเงินพร้อมสกุลเงิน เช่น `100 USDT`

    รับค่าลบได้ เพราะชนิดนี้แทนยอดที่เปลี่ยนแปลงได้ ข้อจำกัดอย่าง
    ยอดถือครองห้ามติดลบเป็นกฎของโดเมนที่ใช้ ไม่ใช่ของชนิดพื้นฐาน (RQ-17)
    """

    #: `eq=False` จำเป็นในชนิดลูกด้วย ไม่ใช่แค่ในฐาน
    #: เพราะ dataclass ของลูกจะสร้าง `__eq__` ของตัวเองมาทับของฐาน
    _AMOUNT_KEY: ClassVar[str] = "amount"
    _UNIT_KEY: ClassVar[str] = "currency"

    @property
    def currency(self) -> str:
        return self.unit


@dataclass(frozen=True, slots=True, eq=False)
class Quantity(_UnitBound):
    """ปริมาณสินทรัพย์พร้อมชื่อเหรียญ เช่น `0.5 BTC`"""

    _AMOUNT_KEY: ClassVar[str] = "quantity"
    _UNIT_KEY: ClassVar[str] = "asset"

    @property
    def asset(self) -> str:
        return self.unit
