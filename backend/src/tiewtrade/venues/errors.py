"""ข้อผิดพลาดกลางของชั้นแยก venue (F-33)

ห้าชนิดตามที่เจ้าของตัดสิน (requirements.md Q-5) — **"ไม่รู้ผล" เป็นหนึ่งในห้า**
และต้องดักแยกจากชนิดอื่นได้ด้วยชนิดอย่างเดียว ไม่ต้องอ่านข้อความ

**ไม่มีชนิดไหนรับข้อความอิสระจากผู้เรียกหรือจากตลาด** ข้อความสร้างจากรหัสของเราเอง
เพราะข้อความของตลาดพา URL, ชื่อ endpoint และบางครั้งพาค่าที่ส่งไปด้วย
ซึ่ง `trading-safety.md` หัวข้อ 2 และ `security.md` หัวข้อ 4 ห้ามไว้ (RQ-8)

รหัสใน `code` เอาไปใส่ `failure_code` ของ audit log ได้ตรง ๆ (RQ-15)
**การประกาศรหัสเหล่านี้ลง migration ของ F-04 เป็นงานของงานแรกที่ลงบันทึกความล้มเหลว
ของ venue** ไม่ใช่งานนี้ (plan.md ข้อ 4.1)
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import ClassVar, Final


class VenueError(Exception):
    """ฐานร่วมของข้อผิดพลาดจากตลาด — ผู้เรียกดักตัวนี้ตัวเดียวได้"""

    code: ClassVar[str] = "VENUE_ERROR"


class RejectionReason(Enum):
    """เหตุผลกลางที่ตลาดปฏิเสธ — แปลจากรหัสของตลาดแล้ว

    มีเท่าที่กฎที่อนุมัติแล้วบังคับ การเพิ่มเหตุผลใหม่ต้องเพิ่มพร้อมงานที่มีผู้ใช้จริง
    (F-33 RQ-13)
    """

    UNKNOWN_SYMBOL = "UNKNOWN_SYMBOL"
    CONSTRAINT_NOT_MET = "CONSTRAINT_NOT_MET"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"


class VenueRejectedError(VenueError):
    """ตลาดตอบมาแล้วว่าไม่รับคำขอนั้น — **รู้ผลแน่ชัดว่าไม่เกิดอะไรที่ตลาด**"""

    code: ClassVar[str] = "VENUE_REJECTED"

    def __init__(self, reason: RejectionReason) -> None:
        super().__init__(f"ตลาดปฏิเสธคำขอ ({reason.value})")
        self.reason: Final[RejectionReason] = reason


class VenueOutcomeUnknownError(VenueError):
    """ส่งออกไปแล้วแต่ไม่รู้ผล — timeout, เน็ตหลุดกลางทาง, ตลาดไม่ตอบ

    **ห้ามเดาและห้ามส่งซ้ำ** ต้องไปถามสถานะด้วยรหัสของเรา
    (`trading-safety.md` หัวข้อ 4, 7, 10)

    แยกจาก `VenueUnavailableError` เด็ดขาด เพราะ "ต่อไม่ได้เลย" ลองใหม่ได้
    ส่วน "ส่งไปแล้วไม่รู้ว่าเข้าหรือไม่" ลองใหม่ไม่ได้
    """

    code: ClassVar[str] = "VENUE_OUTCOME_UNKNOWN"

    def __init__(self) -> None:
        super().__init__("ส่งคำขอออกไปแล้วแต่ไม่รู้ผล ต้องไปถามสถานะด้วยรหัสของเรา")


class VenueRateLimitedError(VenueError):
    """ตลาดบอกให้รอ หรือตัวกั้นของเราปฏิเสธการจอง

    `retry_after` เป็นค่าว่างเมื่อไม่มีใครบอกเวลามา — **ห้ามเดาเวลาแทนตลาด**
    (`trading-safety.md` หัวข้อ 7)
    """

    code: ClassVar[str] = "VENUE_RATE_LIMITED"

    def __init__(self, retry_after: timedelta | None = None) -> None:
        super().__init__("ถูกจำกัดอัตราการเรียก")
        self.retry_after: Final[timedelta | None] = retry_after


class VenueUnavailableError(VenueError):
    """ต่อตลาดไม่ได้ หรือตลาดปิดให้บริการชั่วคราว — ยังไม่ได้ส่งอะไรออกไป"""

    code: ClassVar[str] = "VENUE_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("ตลาดใช้งานไม่ได้ชั่วคราว")


class VenueCredentialRejectedError(VenueError):
    """ตลาดปฏิเสธกุญแจของผู้ใช้ — ต้องหยุดบอทที่ใช้กุญแจนั้นทันที

    `trading-safety.md` หัวข้อ 2: "key ที่ Binance ปฏิเสธต้องหยุดบอทที่ใช้ key นั้นทันที
    และแจ้งผู้ใช้"
    """

    code: ClassVar[str] = "VENUE_CREDENTIAL_REJECTED"

    def __init__(self) -> None:
        super().__init__("ตลาดปฏิเสธกุญแจของผู้ใช้")
