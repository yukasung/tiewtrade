"""สิทธิ์กู้บัญชีหนึ่งครั้ง (F-06 plan.md หัวข้อ 1.8 · requirements.md Q-3.3)

มีไว้เพื่อให้เส้นทาง "ใช้รหัสสำรองใบสุดท้าย → เข้าสู่ระบบ → ผูกเครื่องใหม่"
เดินจบได้โดยไม่ขอรหัสสำรองใบที่สอง ซึ่งเป็นกับดักที่ทำให้ผู้ใช้ติดอยู่กลางทาง

**ขอบเขตของสิทธิ์นี้แคบโดยเจตนา** (เจ้าของอนุมัติ 2026-10-03):

- ผูกกับ session ใบที่เพิ่งออกใบเดียว — ใบอื่นหยิบไปใช้ไม่ได้
- **ใช้ได้ที่การเปลี่ยน secret และการปิด TOTP เท่านั้น** ไม่ใช่สิทธิ์ทั่วไป
- ใช้ครั้งเดียว และฐานข้อมูลเป็นผู้ตัดสินด้วยเงื่อนไข `used_at IS NULL`
- **ไม่แทนรหัสผ่าน** — เส้นทางที่รับสิทธิ์นี้ยังต้องการรหัสผ่านปัจจุบัน (Q-4)
  สิทธิ์นี้แทนเฉพาะ **รหัส TOTP** ที่ผู้ใช้ให้ไม่ได้เพราะไม่มีเครื่องแล้ว

**ต้องตรวจอายุของ session จริง** ไม่พึ่ง `ON DELETE CASCADE` อย่างเดียว เพราะ
`CASCADE` ทำงานตอน **ลบ** แถว ไม่ใช่ตอน session **หมดอายุ** และ F-05 ไม่ลบแถว
ที่หมดอายุทิ้ง — เงื่อนไขนั้นอยู่ใน policy ของตาราง (`plan.md` หัวข้อ 6.5)
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult

from tiewtrade.infra.db.session import UserSession

_GRANT = """
INSERT INTO recovery_grants (session_token_hash, user_id)
VALUES (:token_hash, :user_id)
"""

# ไม่มีเงื่อนไขเรื่องอายุของ session ในคำสั่ง เพราะ policy ของตารางตรวจให้แล้ว
# การเขียนซ้ำที่นี่จะกลายเป็นกฎสองที่ที่วันหนึ่งจะไม่ตรงกัน
_USABLE = """
SELECT 1
FROM recovery_grants
WHERE session_token_hash = :token_hash AND used_at IS NULL
"""

_SPEND = """
UPDATE recovery_grants
SET used_at = now()
WHERE session_token_hash = :token_hash AND used_at IS NULL
"""


async def grant(session: UserSession, *, session_token_hash: str) -> None:
    """ออกสิทธิ์ให้ session ที่เพิ่งออกด้วยรหัสสำรอง

    เรียกใน transaction เดียวกับการออก session — ถ้าแยก จะมีช่วงที่ผู้ใช้ได้ session
    แต่ยังไม่มีสิทธิ์ แล้วเส้นทางผูกเครื่องใหม่จะขอรหัสสำรองใบที่สอง
    """
    await session.execute(
        _GRANT,
        {"token_hash": session_token_hash, "user_id": str(session.user_id)},
    )


async def spend(session: UserSession, *, session_token_hash: str) -> bool:
    """ใช้สิทธิ์หนึ่งครั้ง — คืนว่าใช้ได้หรือไม่

    ศูนย์แถวหมายถึงไม่มีสิทธิ์ ใช้ไปแล้ว หรือ session หมดอายุ — **ทั้งสามกรณี
    มีผลเหมือนกันคือใช้ไม่ได้** จึงไม่แยกให้ผู้เรียก
    """
    used = await session.execute(_SPEND, {"token_hash": session_token_hash})
    return bool(cast("CursorResult[Any]", used).rowcount)


async def usable(session: UserSession, *, session_token_hash: str) -> bool:
    """มีสิทธิ์ที่ยังใช้ได้อยู่หรือไม่ — **ไม่ใช้มัน**

    แยกจาก `spend()` เพราะจุดที่ *ตัดสินสิทธิ์* กับจุดที่ *ทำการกระทำ* อยู่คนละที่:
    middleware ตัดสินว่าคำขอนี้ผ่านหรือไม่ แต่ถ้ามันใช้สิทธิ์ทิ้งตรงนั้น คำขอที่
    ล้มเหลวทีหลัง (เช่นรหัสผ่านผิด) จะเผาสิทธิ์ใบเดียวที่ผู้ใช้มีไปฟรี ๆ
    การใช้จึงเกิดใน transaction เดียวกับการกระทำ ที่ endpoint
    """
    found = (await session.execute(_USABLE, {"token_hash": session_token_hash})).all()
    return found != []
