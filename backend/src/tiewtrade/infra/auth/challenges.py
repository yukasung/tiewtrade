"""ช่วงระหว่างรหัสผ่านกับปัจจัยที่สอง (F-06 plan.md หัวข้อ 1.3 และ 1.4)

**ตารางแยกจาก `sessions` โดยเจตนา** ฉะนั้นแถวที่ผ่านแค่รหัสผ่านไม่ได้อยู่ในตาราง
ที่ให้สิทธิ์ และ RQ-5 เป็นจริงโดยโครงสร้าง ไม่ใช่เพราะ middleware ขยัน

**ต่ออายุไม่ได้เลย** — ไม่มีสิทธิ์ `UPDATE` ให้บทบาทใด และ "ผ่านแล้ว" คือการลบแถว
พร้อมออก session ใน transaction เดียว ไม่ใช่การตั้งธง

**ตายเมื่อรหัสผ่านเปลี่ยน สองชั้น** (RQ-22 ของ F-05 · `plan.md` หัวข้อ 1.4):

1. การเปลี่ยนรหัสผ่านลบ challenge ทุกใบของผู้ใช้ ใน transaction เดียวกับการเปลี่ยนแฮช
2. ตอนใช้ ต้องเทียบ `credential_updated_at` กับค่าที่อ่าน **ใต้ล็อก** ของแถวข้อมูล
   เข้าสู่ระบบ — คำขอที่กำลังวิ่งอยู่ตอนรหัสผ่านเปลี่ยนจึงแพ้ด้วย

ชั้นที่สองจำเป็นทั้งที่มีชั้นที่หนึ่ง เพราะสองที่นั้นอาจถูกเขียนแยกกันในอนาคต
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from tiewtrade.infra.auth.sessions import hash_token, new_token
from tiewtrade.infra.db.session import PresentedSession, UserSession

#: อายุของ challenge — **ค่าที่เสนอ รอเจ้าของยืนยัน**
#:
#: สั้นพอที่ใบที่ถูกทิ้งไม่ค้างอยู่นาน และยาวพอให้ผู้ใช้หาเครื่อง เปิดแอป
#: และพิมพ์รหัสได้โดยไม่ต้องเริ่มจากรหัสผ่านใหม่
CHALLENGE_LIFETIME: Final[timedelta] = timedelta(minutes=5)

_ISSUE = """
INSERT INTO login_challenges (token_hash, user_id, credential_updated_at, expires_at)
VALUES (:token_hash, :user_id, :credential_updated_at, :expires_at)
"""

# ไม่มีเงื่อนไขเรื่องแฮชหรือเวลาในคำสั่ง เพราะ **policy เป็นตัวจำกัดแถว**
# เขียนเงื่อนไขเองด้วยจะกลายเป็นกฎสองที่ที่วันหนึ่งจะไม่ตรงกัน (แบบแผนของ F-05)
_PRESENTED = """
SELECT user_id, credential_updated_at
FROM login_challenges
"""

_DELETE_ONE = "DELETE FROM login_challenges WHERE token_hash = :token_hash"

#: ลบทุกใบของผู้ใช้ **รวมที่หมดอายุ** — ทำได้เพราะ policy ตามเจ้าของ (plan.md 1.5)
_DELETE_ALL = "DELETE FROM login_challenges WHERE user_id = :user_id"


@dataclass(frozen=True, slots=True)
class IssuedChallenge:
    """challenge ที่ออกใหม่ — **โทเคนจริงส่งให้เบราว์เซอร์ครั้งเดียว**"""

    token: str
    token_hash: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PresentedChallenge:
    """challenge ที่ผู้เรียกพามา และยังไม่หมดอายุตาม policy"""

    user_id: UUID
    credential_updated_at: datetime


async def issue(
    session: UserSession, *, credential_updated_at: datetime, now: datetime
) -> IssuedChallenge:
    """ออก challenge ให้ผู้ใช้ที่ผ่านรหัสผ่านแล้ว

    เก็บ **รุ่นของรหัสผ่าน** ไว้ด้วย เพื่อให้ชั้นที่สองของหัวข้อ 1.4 ทำงานได้
    """
    token, token_hash = new_token()
    expires_at = now + CHALLENGE_LIFETIME
    await session.execute(
        _ISSUE,
        {
            "token_hash": token_hash,
            "user_id": str(session.user_id),
            "credential_updated_at": credential_updated_at,
            "expires_at": expires_at,
        },
    )
    return IssuedChallenge(token=token, token_hash=token_hash, expires_at=expires_at)


async def presented(session: PresentedSession) -> PresentedChallenge | None:
    """challenge ที่โทเคนที่พามาเปิดให้เห็น — `None` เมื่อไม่มีหรือหมดอายุแล้ว

    **ไม่ตั้งตัวแปรก็อ่านศูนย์แถว** จึงพลาดแบบปิดประตู
    """
    row = (await session.execute(_PRESENTED)).one_or_none()
    if row is None:
        return None
    user_id, credential_updated_at = tuple(row)
    if not isinstance(user_id, UUID) or not isinstance(credential_updated_at, datetime):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง login_challenges")
    return PresentedChallenge(user_id=user_id, credential_updated_at=credential_updated_at)


async def spend(session: UserSession, *, token_hash: str) -> None:
    """ลบ challenge ที่ใช้ไปแล้ว — เรียกใน transaction เดียวกับการออก session"""
    await session.execute(_DELETE_ONE, {"token_hash": token_hash})


async def end_all(session: UserSession) -> None:
    """ลบ challenge ทุกใบของผู้ใช้ — ใช้ตอนเปลี่ยนรหัสผ่าน (ชั้นที่หนึ่งของหัวข้อ 1.4)"""
    await session.execute(_DELETE_ALL, {"user_id": str(session.user_id)})


def hash_of(token: str) -> str:
    """แฮชของโทเคน challenge — รูปเดียวกับโทเคนของ session"""
    return hash_token(token)
