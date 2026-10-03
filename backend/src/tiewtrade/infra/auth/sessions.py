"""session ในฐานข้อมูล (F-05 plan.md ข้อ 1.3)

**ฐานข้อมูลไม่เคยเห็นโทเคนจริง** เก็บเฉพาะแฮช SHA-256 ของมัน และทุกสิทธิ์ของบทบาท
`api` ผูกกับการถือโทเคนที่ยังใช้ได้ ไม่ผูกกับค่าผู้ใช้ปัจจุบันที่แอปตั้งเอง (RQ-18)

**รูปของคำสั่งเป็นส่วนหนึ่งของการออกแบบ ไม่ใช่รายละเอียด** (ทดลองกับ PostgreSQL 16 แล้ว)
เพราะ PostgreSQL นำ SELECT policy มาใช้ด้วยเมื่อคำสั่ง **อ้างคอลัมน์**:

- **ออกจากระบบเครื่องเดียว** — `DELETE ... WHERE token_hash = :hash`
  การอ้างคอลัมน์ดึง SELECT policy มาใช้ ซึ่งเห็นแถวเดียว จึงลบได้แถวเดียวพอดี
- **ออกจากระบบทุกเครื่อง** — `DELETE FROM sessions` **ไม่มี `WHERE`**
  ไม่อ้างคอลัมน์ จึงใช้แต่ DELETE policy ที่ครอบแถวพี่น้อง
  **ใส่ `WHERE` แล้วจะลบได้แถวเดียวเงียบ ๆ** (RQ-19)
- **เพิกถอนเครื่องอื่นตอนเปลี่ยนรหัสผ่าน** — `DELETE ... WHERE token_hash <> :keep`
  บนบทบาท `auth` ซึ่ง policy เป็นแบบตามเจ้าของ จึงเห็นแถวพี่น้องและอ้างคอลัมน์ได้
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import CursorResult, Result

from tiewtrade.infra.db.session import PresentedSession, UserSession

#: จำนวนไบต์ของโทเคน — 32 ไบต์คือ 256 บิต (plan.md ข้อ 5)
TOKEN_BYTES: Final[int] = 32

_OWNER_OF_PRESENTED = """
SELECT user_id, idle_expires_at, absolute_expires_at
FROM sessions
WHERE now() < idle_expires_at AND now() < absolute_expires_at
"""

_RENEW = """
UPDATE sessions
SET last_seen_at = now(), idle_expires_at = :idle_expires_at
WHERE token_hash = :token_hash
"""

_ISSUE = """
INSERT INTO sessions (token_hash, user_id, idle_expires_at, absolute_expires_at)
VALUES (:token_hash, :user_id, :idle_expires_at, :absolute_expires_at)
"""

_END_ONE = """
DELETE FROM sessions
WHERE token_hash = :token_hash
"""

#: ไม่มี `WHERE` โดยเจตนา — ดูตารางใน docstring ของโมดูล
_END_ALL = "DELETE FROM sessions"

_END_OTHERS = """
DELETE FROM sessions
WHERE token_hash <> :keep
"""


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """โทเคนที่ออกใหม่ — **ค่านี้ส่งให้เบราว์เซอร์ครั้งเดียว ไม่มีที่ไหนเก็บไว้**"""

    token: str
    token_hash: str
    idle_expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionOwner:
    """เจ้าของ session ที่ยังใช้ได้"""

    user_id: UUID
    idle_expires_at: datetime
    absolute_expires_at: datetime


def new_token() -> tuple[str, str]:
    """โทเคนใหม่กับแฮชของมัน — สุ่มจากแหล่งสุ่มเชิงรหัสลับ"""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    """แฮชของโทเคนในรูปที่ฐานข้อมูลเก็บ"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def owner_of_presented(session: PresentedSession) -> SessionOwner | None:
    """เจ้าของโทเคนที่ผู้เรียกพามา — `None` เมื่อไม่มี หมดอายุ หรือถูกเพิกถอนแล้ว

    ไม่มีเงื่อนไขเรื่องแฮชในคำสั่ง เพราะ **policy เป็นตัวจำกัดแถว** ถ้าเขียนเงื่อนไข
    เองด้วยจะกลายเป็นกฎสองที่ที่วันหนึ่งจะไม่ตรงกัน — ไม่ตั้งตัวแปรก็ได้ศูนย์แถว
    """
    row = (await session.execute(_OWNER_OF_PRESENTED)).one_or_none()
    if row is None:
        return None
    user_id, idle_expires_at, absolute_expires_at = tuple(row)
    if (
        not isinstance(user_id, UUID)
        or not isinstance(idle_expires_at, datetime)
        or not isinstance(absolute_expires_at, datetime)
    ):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง sessions")
    return SessionOwner(
        user_id=user_id,
        idle_expires_at=idle_expires_at,
        absolute_expires_at=absolute_expires_at,
    )


async def issue(
    session: UserSession,
    *,
    token_hash: str,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
) -> None:
    """บันทึก session ใหม่ — ทำได้เฉพาะบทบาท `auth` ตาม policy"""
    await session.execute(
        _ISSUE,
        {
            "token_hash": token_hash,
            "user_id": str(session.user_id),
            "idle_expires_at": idle_expires_at,
            "absolute_expires_at": absolute_expires_at,
        },
    )


async def renew(session: PresentedSession, *, token_hash: str, idle_expires_at: datetime) -> int:
    """เลื่อนเวลาหมดอายุเพราะไม่ใช้งาน — คืนจำนวนแถวที่เลื่อนได้

    ศูนย์หมายถึงเลื่อนไม่ได้ (หมดอายุแล้ว หรือเกินเพดานรวม) ซึ่งฐานข้อมูลเป็นผู้ตัดสิน
    ด้วยเงื่อนไขใน policy ไม่ใช่โค้ดที่นี่
    """
    result = await session.execute(
        _RENEW, {"token_hash": token_hash, "idle_expires_at": idle_expires_at}
    )
    return _rows_affected(result)


async def end_one(session: PresentedSession, *, token_hash: str) -> int:
    """ออกจากระบบเครื่องเดียว — คืนจำนวนแถวที่ลบ"""
    return _rows_affected(await session.execute(_END_ONE, {"token_hash": token_hash}))


async def end_all(session: PresentedSession) -> int:
    """ออกจากระบบทุกเครื่องของผู้ถือโทเคนนี้ — คืนจำนวนแถวที่ลบ"""
    return _rows_affected(await session.execute(_END_ALL))


async def end_others(session: UserSession, *, keep_token_hash: str) -> int:
    """เพิกถอนทุกเครื่องยกเว้นเครื่องที่กำลังใช้ — ใช้ตอนเปลี่ยนรหัสผ่าน"""
    return _rows_affected(await session.execute(_END_OTHERS, {"keep": keep_token_hash}))


def _rows_affected(result: Result[Any]) -> int:
    """จำนวนแถวที่คำสั่งกระทบ

    ใช้ `rowcount` ไม่ใช่ `RETURNING` โดยเจตนา — `RETURNING` อ้างคอลัมน์ ซึ่งจะดึง
    SELECT policy มาใช้ด้วย แล้วการออกจากระบบทุกเครื่องจะลบได้แถวเดียว (RQ-19)
    """
    return cast("CursorResult[Any]", result).rowcount
