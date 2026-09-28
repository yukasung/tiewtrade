"""คู่เทรดและข้อจำกัดของเหรียญ (F-33)

`Symbol` เก็บ **สองส่วนแยกกัน** ไม่เก็บเป็นข้อความเดียวอย่าง `BTCUSDT`
เพราะรูปแบบที่ติดกันเป็นคำเดียวเป็นของตลาด การแยกสองส่วนทำให้ตัวเชื่อมแต่ละตลาด
ประกอบชื่อของตัวเองได้ และโค้ดข้างนอกไม่ต้องรู้ว่าตลาดเขียนชื่อคู่เทรดแบบไหน (RQ-2)

`SymbolConstraints` เก็บ **ตัวเลขที่ตลาดรายงาน** ส่วน **การตรวจว่าคำสั่งผ่านหรือไม่
อยู่ใน `tiewtrade.core.trading_limits`** เพราะเป็นการคำนวณ ซึ่ง `backend.md` หัวข้อ 3
สั่งให้อยู่ใน `core` ที่เดียว — ชนิดนี้จึงไม่มีเมธอดตรวจของตัวเอง เพื่อไม่ให้มีสองที่
ที่ดูเหมือนตรวจได้ทั้งคู่ (plan.md ข้อ 1.1)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from tiewtrade.core.money import InvalidUnitError, Money, Quantity


@cache
def _canonical_asset(name: str) -> str:
    """ชื่อสินทรัพย์ในรูปมาตรฐาน ตามกฎของ F-02

    สร้าง `Quantity` ศูนย์หน่วยนั้นเพื่อ **ใช้กฎชื่อหน่วยที่เดียว** ไม่เขียนกฎรูปแบบ
    ขึ้นใหม่ที่นี่ ซึ่งจะกลายเป็นกฎชุดที่สองที่วันหนึ่งจะไม่ตรงกับของเดิม

    **คืนชื่อที่ปรับเป็นมาตรฐานแล้ว ไม่ใช่แค่ตรวจแล้วทิ้ง** ไม่เช่นนั้น `btc` กับ `BTC`
    จะกลายเป็นสองสินทรัพย์คนละตัวในสายตาของ `Symbol` ทั้งที่ F-02 ถือว่าเป็นตัวเดียวกัน

    จำผลไว้เพราะ `Symbol` เป็นชนิดที่สร้างบ่อยและใช้เป็นคีย์ของ dict
    ชื่อสินทรัพย์มีจำนวนจำกัดและกฎไม่เปลี่ยนระหว่างการรันหนึ่งครั้ง
    """
    return Quantity.of(0, name).asset


@dataclass(frozen=True, slots=True)
class Symbol:
    """คู่เทรดหนึ่งคู่ — สินทรัพย์ฐานกับสินทรัพย์ที่ใช้อ้างราคา เช่น `BTC` กับ `USDT`"""

    base: str
    quote: str

    def __post_init__(self) -> None:
        """ตรวจตั้งแต่ตอนสร้าง (RQ-9)

        กฎชื่อสินทรัพย์มาจาก F-02 ที่เดียว ผ่าน `_canonical_asset`
        และเก็บชื่อในรูปมาตรฐานที่ได้กลับมา เพื่อให้คู่เทรดที่ต่างกันแค่ตัวพิมพ์
        เป็นคู่เดียวกันจริง ๆ ทั้งตอนเทียบและตอนใช้เป็นคีย์
        """
        object.__setattr__(self, "base", _canonical_asset(self.base))
        object.__setattr__(self, "quote", _canonical_asset(self.quote))
        if self.base == self.quote:
            raise InvalidUnitError(f"คู่เทรดต้องเป็นสินทรัพย์สองตัวที่ต่างกัน ได้ {self.base}")

    def __str__(self) -> str:
        """รูปแบบกลางที่อ่านออก — ใช้ในข้อความและ log ไม่ใช่ใช้คุยกับตลาด

        คั่นด้วย `/` โดยเจตนา เพื่อให้ไม่มีทางเผลอนำไปใช้เป็นชื่อคู่เทรดของตลาดไหน
        """
        return f"{self.base}/{self.quote}"


@dataclass(frozen=True, slots=True)
class SymbolConstraints:
    """ข้อจำกัดของคู่เทรดหนึ่งคู่ ตามที่ตลาดรายงาน

    สามข้อตาม `trading-safety.md` หัวข้อ 3 — **ไม่มากไม่น้อยกว่านั้น** (RQ-13)
    ข้อจำกัดอื่นอย่างขั้นของราคาจะเพิ่มตอนมีผู้ใช้จริง ซึ่งเกิดพร้อมสัญญาออเดอร์
    หลัง NC-08 ปิด

    `quantity_step` แทน "จำนวนทศนิยม" ที่กฎเขียนไว้ เพราะสิ่งที่ต้องตรวจจริงคือ
    ปริมาณต้องเป็นจำนวนเท่าของขั้นที่ตลาดยอม ซึ่งครอบกรณีที่ขั้นไม่ใช่กำลังสิบด้วย
    """

    symbol: Symbol
    minimum_quantity: Quantity
    quantity_step: Quantity
    minimum_notional: Money

    def __post_init__(self) -> None:
        if self.minimum_quantity.asset != self.symbol.base:
            raise InvalidUnitError(f"ปริมาณขั้นต่ำต้องเป็นหน่วยของสินทรัพย์ฐาน {self.symbol.base}")
        if self.quantity_step.asset != self.symbol.base:
            raise InvalidUnitError(f"ขั้นของปริมาณต้องเป็นหน่วยของสินทรัพย์ฐาน {self.symbol.base}")
        if self.minimum_notional.currency != self.symbol.quote:
            raise InvalidUnitError(f"มูลค่าขั้นต่ำต้องเป็นหน่วยของสินทรัพย์ที่ใช้อ้างราคา {self.symbol.quote}")

        zero_quantity = Quantity.of(0, self.symbol.base)
        zero_notional = Money.of(0, self.symbol.quote)
        if not self.quantity_step > zero_quantity:
            raise ValueError("ขั้นของปริมาณต้องมากกว่าศูนย์")
        if self.minimum_quantity < zero_quantity:
            raise ValueError("ปริมาณขั้นต่ำติดลบไม่ได้")
        if self.minimum_notional < zero_notional:
            raise ValueError("มูลค่าขั้นต่ำติดลบไม่ได้")
