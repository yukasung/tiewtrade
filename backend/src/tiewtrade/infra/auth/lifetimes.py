"""อายุของ session — ตัวเลขอยู่ที่เดียว (F-05 requirements.md Q-2)

เจ้าของตัดสิน: **ไม่ใช้งาน 12 ชั่วโมงหมดอายุ · เพดานรวม 7 วัน · ต่ออายุเมื่อใช้งาน**
และ **การ poll ราคาไม่นับเป็นการใช้งาน** — มีแต่คำขอที่เกิดจากการกดของผู้ใช้ที่ต่ออายุ

ความเสี่ยงที่รับไว้: โทเคนที่ถูกขโมยและถูกใช้ต่อเรื่อย ๆ อยู่ได้ถึงเพดานรวม
และทำสิ่งที่ `security.md` ไม่ได้บังคับยืนยัน TOTP ซ้ำได้ — เทรดมือ, เปิดบอทกลับ,
รีเซ็ตเพดานขาดทุน

**เก็บเวลาหมดอายุเป็นค่าในแถว ไม่ใช่ตัวเลขในเงื่อนไขของ policy** ฐานข้อมูลจึงเทียบกับ
`now()` อย่างเดียว และตัวเลขนโยบายอยู่ในไฟล์นี้ที่เดียว
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

#: หมดอายุเมื่อไม่ใช้งานครบเท่านี้ — เลื่อนได้เมื่อผู้ใช้ทำอะไร
IDLE_LIFETIME: Final[timedelta] = timedelta(hours=12)

#: เพดานรวมนับจากเวลาที่ออก session — **เลื่อนไม่ได้** และฐานข้อมูลบังคับเอง
ABSOLUTE_LIFETIME: Final[timedelta] = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class Deadlines:
    """เส้นตายสองเส้นของ session หนึ่งใบ"""

    idle_expires_at: datetime
    absolute_expires_at: datetime


def deadlines_for_new_session(now: datetime) -> Deadlines:
    """เส้นตายของ session ที่ออกใหม่"""
    return Deadlines(
        idle_expires_at=now + IDLE_LIFETIME,
        absolute_expires_at=now + ABSOLUTE_LIFETIME,
    )


def renewed_idle_deadline(now: datetime, absolute_expires_at: datetime) -> datetime:
    """เส้นตายเพราะไม่ใช้งานหลังต่ออายุ — **ไม่เกินเพดานรวม**

    ฐานข้อมูลบังคับข้อนี้ด้วย `WITH CHECK` อยู่แล้ว ที่นี่คิดค่าที่ไม่ชนเงื่อนไขนั้น
    เพื่อไม่ให้การต่ออายุปกติถูกปฏิเสธ
    """
    return min(now + IDLE_LIFETIME, absolute_expires_at)
