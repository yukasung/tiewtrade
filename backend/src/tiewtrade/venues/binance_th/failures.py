"""แปลความล้มเหลวของ Binance TH เป็นชนิดกลางของ F-33 (plan.md ข้อ 3)

ที่เดียวที่รู้รหัสของตลาด — ส่วนอื่นของตัวเชื่อมและทุกชั้นข้างนอกเห็นแต่หกชนิดกลาง

**ไม่พาข้อความของตลาดออกไปด้วย** ข้อความของตลาดพา URL, ชื่อ endpoint และบางครั้ง
พาค่าที่ส่งไปด้วย ซึ่ง `trading-safety.md` หัวข้อ 2 และ `security.md` หัวข้อ 4 ห้ามไว้
ชนิดกลางจึงไม่มีช่องรับข้อความอิสระตั้งแต่ต้น (F-33 RQ-8)

**ไม่มีรายการรหัสเต็มที่ตลาดประกาศ** (`mission.md` หัวข้อ 6) ที่นี่จึงแปลเฉพาะรหัสที่
เอกสารยืนยันความหมาย ส่วนที่เหลือเป็น `UNEXPLAINED` ซึ่งต้องให้คนมาดู ไม่ใช่เดาความหมาย
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Final

from tiewtrade.venues.errors import (
    RejectionReason,
    VenueCredentialRejectedError,
    VenueError,
    VenueOutcomeUnknownError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueRejectedError,
    VenueUnavailableError,
)


class Delivery(Enum):
    """คำขอไปถึงไหนก่อนจะล้มเหลว — ตัวเชื่อมจัดกลุ่มข้อผิดพลาดของไลบรารี HTTP มาให้

    มีอยู่เพื่อให้โมดูลนี้ไม่ต้องรู้จักไลบรารีเครือข่าย ชนิดของข้อผิดพลาดจาก
    ไลบรารีเป็นเรื่องของ `transport.py` ที่เดียว
    """

    NOT_SENT = "NOT_SENT"
    """ยังไม่ได้ส่งออกไป หรือส่งไม่ครบ — ต่อไม่ติด, DNS ล้ม, timeout ตอนเชื่อมต่อ"""

    SENT_UNANSWERED = "SENT_UNANSWERED"
    """ส่งครบแล้วแต่ไม่ได้คำตอบที่อ่านได้ — **ไม่รู้ผล**"""


#: รหัสของตลาดที่เอกสารยืนยันว่าหมายถึงไม่มีคู่เทรดนั้น
_UNKNOWN_SYMBOL_CODES: Final[frozenset[int]] = frozenset({-1121})

#: รหัสที่ยืนยันว่าคำขอผิดข้อจำกัดของคู่เทรด (filter ของตลาด หรือทศนิยมเกินที่ยอม)
_CONSTRAINT_CODES: Final[frozenset[int]] = frozenset({-1013, -1111})

#: รหัสที่ยืนยันว่าเป็นเรื่องกุญแจหรือลายเซ็น — ผู้เรียกต้องหยุดบอทที่ใช้กุญแจนั้นทันที
#: (`trading-safety.md` หัวข้อ 2)
_CREDENTIAL_CODES: Final[frozenset[int]] = frozenset({-1022, -2014, -2015})

#: รหัสที่ตลาดใช้บอกว่าเรียกถี่เกินไป
_RATE_LIMIT_CODES: Final[frozenset[int]] = frozenset({-1003})

# **เงินไม่พอยังไม่มีรหัสที่แปลได้** รหัส `-2010` ของตลาดคือ "ออเดอร์ถูกปฏิเสธ" แบบรวม
# ซึ่งครอบหลายสาเหตุ การแปลเป็น `INSUFFICIENT_FUNDS` จึงเป็นการเดาความหมาย
# งานนี้ไม่ส่งออเดอร์ จึงไม่มีคำตอบใดที่พารหัสนั้นมาได้ — งานที่ส่งออเดอร์จริงจะเป็น
# ผู้เพิ่มการแปลนี้จากคำตอบจริงที่เห็น ไม่ใช่จากการเดาที่นี่


def failure_for_delivery(delivery: Delivery) -> VenueError:
    """ความล้มเหลวที่เกิดก่อนได้คำตอบ"""
    if delivery is Delivery.NOT_SENT:
        return VenueUnavailableError()
    return VenueOutcomeUnknownError()


def failure_for_status(
    *,
    status: int,
    market_code: int | None,
    retry_after: timedelta | None = None,
    changes_state: bool,
) -> VenueError:
    """แปลคำตอบที่ไม่สำเร็จเป็นชนิดกลาง — เรียงตามลำดับที่ตรวจใน plan.md ข้อ 3

    `changes_state` บอกว่าคำขอนั้นเปลี่ยนสถานะที่ตลาดหรือไม่ เพราะ `5xx` ของการอ่าน
    คือ "ลองใหม่ได้" แต่ `5xx` ของคำสั่งที่ส่งออกไปแล้วคือ "ไม่รู้ผล"
    งานนี้ยังไม่มีคำขอที่เปลี่ยนสถานะ แต่กฎเขียนไว้ก่อนเพื่อไม่ให้ตีความเอาเองภายหลัง
    """
    if status in (429, 418) or market_code in _RATE_LIMIT_CODES:
        # ไม่มี `Retry-After` ก็เป็นค่าว่าง — **ห้ามเดาเวลาแทนตลาด**
        return VenueRateLimitedError(retry_after)

    if status == 401 or market_code in _CREDENTIAL_CODES:
        return VenueCredentialRejectedError()

    if 500 <= status < 600:
        return VenueOutcomeUnknownError() if changes_state else VenueUnavailableError()

    if market_code in _UNKNOWN_SYMBOL_CODES:
        return VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
    if market_code in _CONSTRAINT_CODES:
        return VenueRejectedError(RejectionReason.CONSTRAINT_NOT_MET)

    # `403` มาถึงที่นี่โดยเจตนา — เอกสารระบุว่าเป็นการถูกไฟร์วอลล์ของตลาด (WAF) ปฏิเสธ
    # ซึ่ง **ไม่ได้พิสูจน์ว่ากุญแจผิด** ถ้าแปลเป็นเรื่องกุญแจ ผู้เรียกจะไปหยุดบอท
    # ด้วยสาเหตุที่ผิด ตาม `trading-safety.md` หัวข้อ 2 ที่สั่งให้หยุดทันทีเมื่อกุญแจถูกปฏิเสธ
    # การปฏิเสธแบบนี้ต้องให้คนมาดู เพราะมักเกิดจากรูปคำขอหรือ IP ไม่ใช่สิทธิ์
    return VenueRejectedError(RejectionReason.UNEXPLAINED)


def retry_after_of(raw: str | None, *, at: datetime) -> timedelta | None:
    """เวลาที่ตลาดบอกให้รอ — ไม่มีก็เป็นค่าว่าง **ห้ามเดาแทนตลาด**"""
    if raw is None:
        return None
    try:
        seconds = int(raw.strip())
    except ValueError:
        # รูปแบบวันที่ตาม HTTP ก็ถูกตามมาตรฐาน แต่แปลงแล้วต้องใช้นาฬิกาของเรา
        # เทียบกับของตลาด ซึ่งเป็นการเดาเวลาที่เราไม่มีสิทธิ์เดา
        return None
    if seconds < 0:
        return None
    try:
        wait = timedelta(seconds=seconds)
        # not_before ต้องอ่านกลับเป็น datetime ได้ ไม่ใช่แค่เก็บ interval ได้
        at + wait
        return wait
    except OverflowError:
        pass
    # ไม่ผูก header/exception ต้นทางไว้กับ error ที่ออกจาก adapter
    raise VenueProtocolError()
