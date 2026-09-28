"""ยอดในกระเป๋าและสัญญาของแหล่งกระเป๋า (F-33)

**ยอดรวมของสองช่องเป็นการคำนวณ จึงไม่มีที่นี่** (`backend.md` หัวข้อ 3)
ผู้เรียกที่ต้องการยอดรวมบวกเองด้วย `Quantity` ซึ่งเป็นที่เดียวที่เลขคณิตของปริมาณอยู่

**ทุกยอดเป็น `Quantity` ไม่ใช่ `Money`** เพราะกระเป๋าถือสินทรัพย์ ไม่ได้ถือเงิน
`0.5 BTC` กับ `100 USDT` เป็นของชนิดเดียวกันในมุมของกระเป๋า การตีมูลค่าเป็นสกุลเงิน
ต้องใช้ราคาประกอบ ซึ่งเป็นงาน F-14 ถ้าเก็บบางสินทรัพย์เป็น `Money` ผู้เรียกจะต้อง
เขียนสองทางสำหรับเรื่องเดียวกัน และจะมีจุดที่ต้องเดาว่าสินทรัพย์ไหนนับเป็นสกุลเงิน

**หนึ่งตัวที่ทำตามสัญญานี้ผูกกับกระเป๋าหนึ่งใบตอนสร้าง** จึงไม่มีพารามิเตอร์ชี้กระเป๋า
เหตุผล: การส่งตัวชี้กระเป๋าเข้ามาทุกครั้งจะบังคับให้ออกแบบว่ากุญแจของผู้ใช้เดินทางอย่างไร
ซึ่งเป็นงาน F-07 และ F-35 ที่ยังไม่ได้ตัดสิน (T-03) และตรงกับกฎ "หนึ่งกระเป๋า
หนึ่งผู้เขียน" (`architecture.md` หัวข้อ 4)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from tiewtrade.core.money import InvalidUnitError, Quantity
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.moments import require_aware


@dataclass(frozen=True, slots=True)
class Holding:
    """ยอดของสินทรัพย์หนึ่งตัว แยกส่วนที่ใช้ได้กับส่วนที่ถูกจองไว้กับออเดอร์ที่ค้างอยู่"""

    available: Quantity
    reserved: Quantity

    def __post_init__(self) -> None:
        if self.available.asset != self.reserved.asset:
            raise InvalidUnitError(
                f"ยอดของสินทรัพย์เดียวกันต้องหน่วยเดียวกัน"
                f" ได้ {self.available.asset} กับ {self.reserved.asset}"
            )
        zero = Quantity.of(0, self.available.asset)
        if self.available < zero or self.reserved < zero:
            raise ValueError("ยอดในกระเป๋าติดลบไม่ได้")

    @property
    def asset(self) -> str:
        """ชื่อสินทรัพย์ของยอดนี้"""
        return self.available.asset


@dataclass(frozen=True, slots=True)
class WalletHoldings:
    """ยอดทั้งกระเป๋า ณ เวลาที่อ่านมา

    พา `received_at` และรายการสินทรัพย์มาด้วย เพื่อให้ผู้เรียกบันทึก audit log
    ได้ครบโดยไม่ต้องจำว่าถามอะไรไป (RQ-15)
    """

    received_at: datetime
    holdings: tuple[Holding, ...]

    def __post_init__(self) -> None:
        require_aware("เวลาที่ระบบรับ", self.received_at)

        # คัดลอกเป็น tuple **ก่อน** ตรวจ เพราะผู้เรียกส่ง list เข้ามาได้
        # ถ้าเก็บ list ที่ผู้เรียกถืออยู่ไว้ตรง ๆ การเพิ่มหรือลบสมาชิกภายหลัง
        # จะเปลี่ยนค่าที่อยู่ในชนิดที่ประกาศว่าแก้ไม่ได้ และเปลี่ยนผลของการตรวจที่ผ่านไปแล้ว
        object.__setattr__(self, "holdings", tuple(self.holdings))

        assets = [holding.asset for holding in self.holdings]
        if len(assets) != len(set(assets)):
            raise ValueError("สินทรัพย์หนึ่งตัวมีได้ยอดเดียวในหนึ่งกระเป๋า")

    @property
    def assets(self) -> tuple[str, ...]:
        """รายชื่อสินทรัพย์ที่มียอดอยู่ — ใช้บันทึกว่า "กับอะไร" ใน audit log"""
        return tuple(holding.asset for holding in self.holdings)

    def holding(self, asset: str) -> Holding | None:
        """ยอดของสินทรัพย์นั้น หรือ `None` เมื่อกระเป๋าไม่มีสินทรัพย์นั้นเลย"""
        for candidate in self.holdings:
            if candidate.asset == asset:
                return candidate
        return None


#: ต้นทุนของการอ่านยอดทั้งกระเป๋า — ตัวเชื่อมของแต่ละตลาดประกาศค่าของตลาดนั้นเอง
DEFAULT_HOLDINGS_COST = CallCost(weight=1)


@runtime_checkable
class WalletSource(Protocol):
    """กระเป๋าหนึ่งใบของตลาดหนึ่ง"""

    async def holdings(self) -> WalletHoldings:
        """ยอดทั้งกระเป๋า

        **ต้องจองโควตากับตัวกั้นก่อนเรียกตลาดจริงทุกครั้ง** (Q-8)
        กุญแจใช้ไม่ได้ → `VenueCredentialRejectedError`
        """
        ...
