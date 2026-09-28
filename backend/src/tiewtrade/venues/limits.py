"""ต้นทุนของการเรียกและตัวกั้นอัตรา (F-33 Q-8)

`trading-safety.md` หัวข้อ 7 สั่งให้นับและจำกัดอัตราการเรียก **ในระดับทั้งระบบ
ไม่ใช่ต่างคนต่างเรียก** ซึ่งต้องมีที่เก็บสภาพร่วมกัน (Redis หรือฐานข้อมูล)
แต่ `venues` พึ่ง `infra` ไม่ได้ (RQ-3)

ชั้นนี้จึงให้แค่ **สัญญา** ของตัวกั้นกับตัวที่ไม่ทำอะไร ตัวจริงอยู่ใน service
ที่พึ่ง `infra` ได้ (F-35 หรือ F-10) — ตัวกั้นที่ไม่มีสภาพร่วมกันคือตัวกั้นที่ไม่จริง
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CallCost:
    """ต้นทุนของการเรียกหนึ่งครั้ง

    สองช่องเพราะตลาดมีเพดานสองแบบ — `mission.md` หัวข้อ 6 บันทึกไว้ว่า Binance TH
    จำกัด 6,000 weight/นาที **และ** 6,000 ออเดอร์/นาที เพดานสองแบบต้องนับสองอย่าง

    **หน่วยของ `weight` คือหน่วยที่ตลาดประกาศ ไม่ใช่หน่วยที่เราคิดขึ้น**
    ชั้นกลางไม่รู้ว่า 1 weight เท่ากับอะไร รู้แค่ว่าต้องนับรวมก่อนเรียก
    ตัวเชื่อมของแต่ละตลาดเป็นผู้ประกาศต้นทุนจากเอกสารของตลาดนั้น
    """

    weight: int
    orders: int = 0

    def __post_init__(self) -> None:
        # ตรวจชนิดก่อนตรวจช่วงค่า เพราะ `NaN` เทียบกับตัวเลขแล้วได้เท็จเสมอ
        # จึงผ่านการตรวจช่วงค่าไปได้ทั้งที่นับโควตาไม่ได้
        # และ `bool` เป็น subclass ของ `int` จึงต้องตัดออกก่อน
        for label, value in (("weight", self.weight), ("orders", self.orders)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{label} ของต้นทุนต้องเป็นจำนวนเต็ม ได้ {type(value).__name__}")

        if self.weight < 1:
            raise ValueError("ต้นทุนของการเรียกต้องไม่น้อยกว่า 1 weight")
        if self.orders < 0:
            raise ValueError("จำนวนออเดอร์ของการเรียกติดลบไม่ได้")


@runtime_checkable
class RateLimitGuard(Protocol):
    """ตัวกั้นอัตราการเรียก — **จองก่อนเรียกจริงทุกครั้ง**

    จองไม่ได้ต้องโยน `VenueRateLimitedError` **ไม่ใช่รอเงียบ ๆ ข้างใน**
    เพราะผู้เรียกต้องเป็นคนตัดสินว่าจะรอ จะทิ้งงาน หรือจะแจ้งผู้ใช้
    การรอเงียบ ๆ ทำให้คำสั่งลดความเสี่ยงค้างอยู่ในคิวโดยไม่มีใครรู้
    """

    async def reserve(self, cost: CallCost) -> None:
        """จองโควตาสำหรับการเรียกที่มีต้นทุนเท่านี้"""
        ...


class NoRateLimit:
    """ตัวกั้นที่ไม่ทำอะไร — สำหรับเทสต์และสำหรับตลาดจำลองที่ไม่มีเพดาน

    **ห้ามใช้กับตลาดจริง** ตัวจริงต้องนับรวมทั้งระบบ (Q-8)
    """

    async def reserve(self, cost: CallCost) -> None:
        """ไม่ทำอะไร"""
        return None
