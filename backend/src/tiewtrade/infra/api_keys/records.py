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

#: จำนวน key สูงสุดต่อผู้ใช้ (Q-3 — เจ้าของตัดสิน 2026-10-04)
#:
#: ตรงกับเพดานกระเป๋าที่ `mission.md` หัวข้อ 5 ตัดสินไว้ (บัญชีหลัก 1 + บัญชีย่อย 5)
#: แต่ **ยังไม่ผูกกับกระเป๋า** — F-08 เป็นผู้ผูก
MAX_KEYS_PER_USER: Final[int] = 6

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

    @property
    def may_retry(self) -> bool:
        """ผู้ใช้กดลองใหม่ได้หรือไม่ — เฉพาะแถวที่ตรวจไม่ได้ชั่วคราว"""
        return self.status is ApiKeyStatus.UNVERIFIABLE
