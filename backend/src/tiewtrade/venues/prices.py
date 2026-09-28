"""ราคาและสัญญาของแหล่งราคา (F-33)

ราคาพา **สองเวลา** มาด้วยตามที่เจ้าของกำหนด (Q-10):

- **เวลาของตลาด** — ใช้ตัดสินความเก่าตาม `trading-safety.md` หัวข้อ 6
  เพราะสิ่งที่กฎนั้นห่วงคือราคานั้นเก่าไปแล้วในตลาด
- **เวลาที่ระบบรับ** — ใช้วัดว่าฝั่งเราช้าเอง และใช้เทียบเมื่อนาฬิกาสองฝั่งไม่ตรง

ถ้ามีแต่เวลาที่เรารับ ราคาที่ตลาดค้างส่งมานาน 10 วินาทีจะดูใหม่เอี่ยมทันทีที่เรารับ
ถ้ามีแต่เวลาของตลาด เราจะไม่รู้เลยว่าฝั่งเราเองหน่วง

**เกณฑ์ว่ากี่วินาทีถือว่าเก่าไม่อยู่ในชั้นนี้** ผู้เรียกส่งเข้ามา และยังไม่มีข้อกำหนดตัวเลขนั้น
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from tiewtrade.core.money import InvalidUnitError, Money
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.moments import require_aware
from tiewtrade.venues.symbols import Symbol


@dataclass(frozen=True, slots=True)
class Price:
    """ราคาล่าสุดของคู่เทรดหนึ่ง ณ เวลาหนึ่ง"""

    symbol: Symbol
    amount: Money
    #: เวลาที่ตลาดบอกว่าราคานี้เป็นของเวลาไหน
    venue_time: datetime
    #: เวลาที่ฝั่งเราได้ข้อมูลนี้มา
    received_at: datetime

    def __post_init__(self) -> None:
        if self.amount.currency != self.symbol.quote:
            raise InvalidUnitError(f"ราคาต้องเป็นหน่วยของสินทรัพย์ที่ใช้อ้างราคา {self.symbol.quote}")
        if not self.amount > Money.of(0, self.symbol.quote):
            raise ValueError("ราคาต้องมากกว่าศูนย์")
        require_aware("เวลาของตลาด", self.venue_time)
        require_aware("เวลาที่ระบบรับ", self.received_at)

    def age(self, as_of: datetime) -> timedelta:
        """อายุของราคา **นับจากเวลาของตลาด** ไม่ใช่จากเวลาที่เรารับ (Q-10)

        `as_of` เป็นค่าที่ผู้เรียกส่งเข้ามา ชั้นนี้ไม่อ่านนาฬิกาเอง
        เพื่อให้เทสต์ความเก่าทำได้โดยไม่ต้องรอเวลาจริง
        """
        require_aware("เวลาที่ใช้เทียบ", as_of)
        return as_of - self.venue_time

    def is_stale(self, *, max_age: timedelta, as_of: datetime) -> bool:
        """เก่าเกินเกณฑ์ที่ผู้เรียกกำหนดหรือไม่

        ราคาที่เก่าเกินกำหนดต้องถือว่า **ไม่มีราคา** ตาม `trading-safety.md` หัวข้อ 6
        การตัดสินใจนั้นเป็นของผู้เรียก ชั้นนี้แค่ตอบว่าเก่าหรือยัง
        """
        if max_age < timedelta(0):
            raise ValueError("เกณฑ์ความเก่าติดลบไม่ได้")
        return self.age(as_of) > max_age


#: ต้นทุนของการขอราคาล่าสุด — ตัวเชื่อมของแต่ละตลาดประกาศค่าของตลาดนั้นเอง
#: ค่านี้เป็นค่าตั้งต้นที่ต่ำที่สุดที่มีความหมาย (Q-8)
DEFAULT_LATEST_PRICE_COST = CallCost(weight=1)


@runtime_checkable
class PriceSource(Protocol):
    """แหล่งราคาของตลาดหนึ่ง

    `market-data` พึ่งสัญญานี้ตัวเดียว จึงไม่ถือความสามารถส่งออเดอร์เลย
    ซึ่งตรงกับข้อห้ามใน `database.md` หัวข้อ 5 (Q-2)
    """

    async def latest_price(self, symbol: Symbol) -> Price:
        """ราคาล่าสุดของคู่เทรดนั้น

        **ต้องจองโควตากับตัวกั้นก่อนเรียกตลาดจริงทุกครั้ง** (Q-8)
        ไม่พบคู่เทรด → `VenueRejectedError` พร้อมเหตุผล `UNKNOWN_SYMBOL`
        """
        ...
