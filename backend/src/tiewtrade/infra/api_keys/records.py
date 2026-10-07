"""ชนิดข้อมูลของ API key หนึ่งใบ — **ไม่มีช่องไหนพาความลับออกมา**

สิ่งที่ชั้นบนเห็นคือ `ApiKeySummary` ซึ่งมีแค่ **4 หลักท้ายของ API key**
ไม่มี key เต็ม ไม่มี secret ไม่ว่าเต็มหรือบางส่วน (`trading-safety.md` หัวข้อ 2 ·
`mission.md` หัวข้อ 8 ข้อ 2 — เจ้าของตัดสิน 2026-10-04)

**ชนิดนี้สร้างจากแถวที่ `api` อ่านได้เท่านั้น** ซึ่งไม่มีคอลัมน์ความลับอยู่แล้ว
ฉะนั้นถึงมีคนเผลอส่งทั้งแถวมา ก็ไม่มีความลับให้หลุด
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import ClassVar, Final
from uuid import UUID

from tiewtrade.infra.db.errors import InfraError

#: One credential per user, including every status (F-08 single-account RQ-2).
MAX_KEYS_PER_USER: Final[int] = 1

#: จำนวนหลักท้ายของ API key ที่แสดงได้
PUBLIC_TAIL_LENGTH: Final[int] = 4

#: ความยาวที่ยอมรับของชื่อที่ผู้ใช้ตั้ง — ปฏิเสธก่อนถึงฐานข้อมูล (RQ-13)
MAX_LABEL_LENGTH: Final[int] = 40

#: ความยาวที่ยอมรับของค่าที่ผู้ใช้กรอก
#:
#: มีไว้ปฏิเสธของที่ใหญ่เกินจริงตั้งแต่ต้นทาง ไม่ใช่กันผู้ใช้ — key ของตลาดยาวราว 64 ตัว
MAX_CREDENTIAL_LENGTH: Final[int] = 256


class ApiKeyError(InfraError):
    """คำขอเกี่ยวกับ API key ที่รับไม่ได้ — **ข้อความห้ามพาค่าที่กรอกมาด้วย**"""

    code: ClassVar[str] = "API_KEY_REJECTED_INPUT"


class TooManyKeysError(ApiKeyError):
    """เพิ่มเกินเพดานต่อผู้ใช้"""

    code: ClassVar[str] = "API_KEY_LIMIT_REACHED"


def accepted_label_text(value: str) -> str:
    """ปฏิเสธ NUL ที่ PostgreSQL text เก็บไม่ได้ โดยไม่สะท้อนค่าที่กรอก."""
    if "\x00" in value:
        raise ApiKeyError("ชื่อ key มีอักขระที่เก็บไม่ได้")
    return value


def accepted_public_identifier(value: str) -> str:
    """ตรวจค่าที่จะใช้เป็น HTTP header ก่อนเก็บหรือใช้ โดยไม่สะท้อนค่าใน error."""
    cleaned = value.strip()
    if not cleaned or len(cleaned) > MAX_CREDENTIAL_LENGTH:
        raise ApiKeyError("API key ว่างหรือยาวเกินที่ยอมรับ")
    if any(not 32 <= ord(character) <= 126 for character in cleaned):
        raise ApiKeyError("API key มีอักขระที่ใช้ใน HTTP header ไม่ได้")
    return cleaned


class ApiKeyStatus(Enum):
    """สถานะที่ผู้ใช้เห็น — **สี่สถานะ** (Q-7 เจ้าของตัดสิน 2026-10-04)

    **`REJECTED` กับ `UNVERIFIABLE` ต้องแยกกันเสมอ** เพราะคนใช้ต้องทำคนละอย่าง:
    อันแรกไปแก้ที่ตลาด อันหลังแค่รอหรือกดลองใหม่ · การรวมสองอันนี้เข้าด้วยกัน
    จะสอนให้ผู้ใช้ไปสร้าง key ใหม่ทุกครั้งที่เน็ตสะดุด
    """

    #: ยังไม่เคยตรวจหรือกำลังรอรอบตรวจ
    PENDING = "PENDING"
    #: ตรวจแล้วใช้งานได้
    ACTIVE = "ACTIVE"
    #: ตลาดบอกว่าใช้ไม่ได้จริง หรือหมดเวลาตรวจ — **secret ถูกลบไปแล้ว**
    REJECTED = "REJECTED"
    #: ตรวจไม่ได้ชั่วคราว — ลองใหม่ได้ และ secret ยังอยู่
    UNVERIFIABLE = "UNVERIFIABLE"

    @property
    def is_final(self) -> bool:
        """สถานะนี้จบแล้วหรือยัง — แถวที่ยังไม่จบคือแถวที่ worker ต้องมอง"""
        return self in (ApiKeyStatus.ACTIVE, ApiKeyStatus.REJECTED)


def public_tail(key_public: str) -> str:
    """4 หลักท้ายของ API key — **ส่วนเดียวที่แสดงได้**

    ไม่เติมอะไรให้ยาวขึ้นและไม่ตัดให้สั้นลงกว่านี้ — ผู้เรียกเป็นคนตัดสินใจว่าจะ
    แสดงอย่างไร ส่วนที่นี่ตอบแค่ว่า "ส่วนที่เปิดเผยได้คืออะไร"
    """
    return key_public[-PUBLIC_TAIL_LENGTH:]


@dataclass(frozen=True, slots=True)
class ApiKeySummary:
    """สิ่งที่หน้าจอได้เห็นของ key หนึ่งใบ

    **ไม่มีช่องสำหรับ key เต็มและไม่มีช่องสำหรับ secret** — ความลับไม่หลุดเพราะ
    ไม่มีที่ให้มันอยู่ ไม่ใช่เพราะผู้เรียกจำได้ว่าอย่าส่งออกไป
    """

    id: UUID
    label: str
    public_tail: str
    status: ApiKeyStatus
    created_at: datetime
    failure_code: str | None = None
    verified_at: datetime | None = None
    not_before: datetime | None = None
    next_attempt_at: datetime | None = None

    #: คำนวณจากสถานะและ market wait ด้วยเวลาฐานข้อมูล · DTO ที่ไม่ได้อ่านจาก DB ปิดไว้
    may_retry: bool = False
