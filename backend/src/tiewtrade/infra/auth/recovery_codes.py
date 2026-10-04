"""รหัสสำรองสำหรับกู้บัญชีเมื่อเสียเครื่อง (F-06 requirements.md Q-3)

**ใช้ครั้งเดียวจริง และฐานข้อมูลเป็นผู้ตัดสิน** ไม่ใช่โค้ดที่นี่ — คำสั่งที่ทำเครื่องหมาย
ว่าใช้แล้วมีเงื่อนไข `used_at IS NULL` ฉะนั้นคำขอสองใบที่ยิงรหัสเดียวกันพร้อมกัน
สำเร็จได้ใบเดียว (validation V-33)

**เก็บแฮช ไม่เก็บค่าจริง** และใช้ argon2 ตัวเดียวกับรหัสผ่าน จึงไม่มีค่าความแรง
ชุดที่สองให้ต้องดูแล (`plan.md` หัวข้อ 6.3)

**ยกเลิกทั้งชุดเป็นก้อนเดียวกับการสลับ secret** (RQ-15) — ถ้าชุดเก่าที่รั่วยังใช้ได้
การเปลี่ยน secret และการเพิกถอน session ก็ไม่ได้ตัดทางผู้ถือรหัสนั้น

**ราคาที่ต้องรู้:** การตรวจต้องเทียบกับทุกใบที่ยังไม่ใช้ และ argon2 หนึ่งครั้งใช้เวลา
ราว 100 มิลลิวินาที ฉะนั้นเวลาที่ใช้ตรวจโตตามจำนวนใบ — เป็นเหตุที่จำนวนใบไม่มาก
และเป็นข้อที่ถังของรหัสสำรองต้องคุม
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult

from tiewtrade.infra.auth.hashing import hash_password, password_matches
from tiewtrade.infra.db.session import UserSession

#: จำนวนใบที่ออกต่อชุด — **ค่าที่เสนอ รอเจ้าของยืนยัน**
#:
#: ตัวเลขนี้ต่อรองระหว่างสองอย่าง: มากเกินไปทำให้การตรวจรหัสผิดหนึ่งครั้งใช้เวลา
#: เท่ากับ argon2 คูณจำนวนใบ (เป็นช่องถล่มเซิร์ฟเวอร์) ส่วนน้อยเกินไปทำให้ผู้ใช้
#: หมดทางกู้เร็ว · แปดใบคือราว 0.8 วินาทีในกรณีแย่สุด
CODES_PER_SET = 8

#: จำนวนอักขระต่อใบ — **ค่าที่เสนอ รอเจ้าของยืนยัน**
#:
#: สิบอักขระจากชุด 32 ตัวให้ความยาวราว 50 บิต ซึ่งเดาไม่ได้ในทางปฏิบัติ
#: และยังสั้นพอที่คนจดใส่กระดาษแล้วพิมพ์กลับได้
CODE_LENGTH = 10

#: ชุดอักขระที่ไม่มีคู่ที่คนอ่านสลับกันได้ — ตัด `I`, `L`, `O`, `U`, `0`, `1`
#:
#: ตัด `U` ออกด้วยเพราะรวมกับอักษรอื่นแล้วสะกดเป็นคำที่ไม่ควรโผล่ในรหัสที่ผู้ใช้เห็น
_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"

_INSERT = """
INSERT INTO user_recovery_codes (id, user_id, code_hash)
VALUES (:id, :user_id, :code_hash)
"""

_REVOKE_ALL = "DELETE FROM user_recovery_codes WHERE user_id = :user_id"

_UNUSED = """
SELECT id, code_hash
FROM user_recovery_codes
WHERE user_id = :user_id AND used_at IS NULL
ORDER BY created_at
"""

_SPEND = """
UPDATE user_recovery_codes
SET used_at = now()
WHERE id = :id AND used_at IS NULL
"""


@dataclass(frozen=True, slots=True)
class IssuedCodes:
    """ชุดที่ออกใหม่ — **ค่าจริงส่งให้ผู้ใช้ครั้งเดียว ไม่มีที่ไหนเก็บไว้**"""

    codes: tuple[str, ...]


def new_code() -> str:
    """รหัสสำรองหนึ่งใบ — สุ่มจากแหล่งสุ่มเชิงรหัสลับ"""
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


async def issue_set(session: UserSession) -> IssuedCodes:
    """ยกเลิกชุดเก่าทั้งชุดแล้วออกชุดใหม่ — **ในคำสั่งเดียวกันทาง transaction**

    ลำดับคือลบก่อนแล้วเพิ่ม ฉะนั้นไม่มีช่วงที่สองชุดใช้ได้พร้อมกัน (RQ-15)
    """
    await revoke_all(session)
    codes = tuple(new_code() for _ in range(CODES_PER_SET))
    for code in codes:
        await session.execute(
            _INSERT,
            {
                "id": str(uuid4()),
                "user_id": str(session.user_id),
                "code_hash": hash_password(code),
            },
        )
    return IssuedCodes(codes=codes)


async def revoke_all(session: UserSession) -> None:
    """ยกเลิกทุกใบของผู้ใช้คนนี้ รวมใบที่ใช้ไปแล้ว"""
    await session.execute(_REVOKE_ALL, {"user_id": str(session.user_id)})


async def spend(session: UserSession, presented: str) -> int | None:
    """ใช้รหัสสำรองหนึ่งใบ — คืนจำนวนใบที่เหลือ หรือ `None` เมื่อไม่ตรงใบใดเลย

    **เทียบกับทุกใบที่ยังไม่ใช้เสมอ ไม่หยุดเมื่อเจอ** เพื่อให้เวลาที่ใช้ตรวจ
    ไม่บอกว่ารหัสตรงกับใบที่เท่าไร — เหตุผลเดียวกับที่ `hashing.py` ของ F-05
    ใช้เวลาเท่ากันเมื่อไม่พบอีเมล
    """
    rows = (await session.execute(_UNUSED, {"user_id": str(session.user_id)})).all()
    matched: UUID | None = None
    for row in rows:
        code_id, code_hash = tuple(row)
        if not isinstance(code_id, UUID) or not isinstance(code_hash, str):
            raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง user_recovery_codes")
        if password_matches(code_hash, presented) and matched is None:
            matched = code_id

    if matched is None:
        return None

    spent = await session.execute(_SPEND, {"id": str(matched)})
    # ศูนย์แถว = มีคำขออื่นใช้ใบนี้ไปแล้วระหว่างทาง → ปฏิเสธ (validation V-33)
    if not cast("CursorResult[Any]", spent).rowcount:
        return None
    return len(rows) - 1


async def remaining(session: UserSession) -> int:
    """จำนวนใบที่ยังใช้ได้ — หน้าเว็บต้องแสดงค่านี้ (Q-3.3)"""
    rows = (await session.execute(_UNUSED, {"user_id": str(session.user_id)})).all()
    return len(rows)
