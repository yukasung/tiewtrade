"""secret ของ TOTP ในฐานข้อมูล (F-06 plan.md หัวข้อ 1.2 และ 1.6)

**plaintext ของ secret ออกจากโมดูลนี้ได้ที่เดียว** คือตอนเริ่มตั้งค่า เพราะผู้ใช้
ต้องเอาไปใส่แอป authenticator · หลังจากนั้นไม่มีทางอ่านกลับ (RQ-2)

**สองตารางไม่ใช่ตารางเดียว** `user_totp` คือของที่เปิดใช้แล้ว ส่วน `user_totp_pending`
คือของที่ยังไม่พิสูจน์ · ปัจจัยเดิมทำงานปกติตลอดช่วงที่ยังไม่ยืนยัน จึงทิ้งกลางทาง
ได้โดยไม่เสียอะไร (`plan.md` หัวข้อ 1.6)

**การกันใช้รหัสซ้ำมีสองชั้น** (RQ-4 · `plan.md` หัวข้อ 1.2):

1. ล็อกแถวตั้งแต่ก่อนอ่าน secret จนอนุญาตสำเร็จ — การเปลี่ยน secret จึงเข้าคิว
2. `secret_version` อยู่ในเงื่อนไขของการอนุญาต — ทางเข้าใหม่ที่ลืมล็อกยังถูกปฏิเสธ

**ลำดับการล็อกคือ `auth_throttle` → `user_credentials` → `user_totp`**
(`plan.md` หัวข้อ 1.1) ลำดับคงที่คือสิ่งที่กัน deadlock ไม่ใช่โชค
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, cast
from urllib.parse import quote

from sqlalchemy import CursorResult

from tiewtrade.core.totp import DIGITS, TIME_STEP, base32_secret, matching_step, step_at
from tiewtrade.infra.crypto import KeySource, Sealed, seal, unseal
from tiewtrade.infra.db.session import UserSession

#: ความยาว secret ที่ออกให้ — 160 บิตตามที่ RFC 4226 หัวข้อ 4 ข้อ R6 แนะนำ
SECRET_BYTES = 20

#: ชื่อที่แสดงในแอป authenticator
ISSUER = "TiewTrade"

_PENDING_UPSERT = """
INSERT INTO user_totp_pending (user_id, secret_sealed, key_version)
VALUES (:user_id, :sealed, :key_version)
ON CONFLICT (user_id)
DO UPDATE SET secret_sealed = :sealed, key_version = :key_version
"""

_PENDING_READ = """
SELECT secret_sealed, key_version
FROM user_totp_pending
WHERE user_id = :user_id
"""

_PENDING_DELETE = "DELETE FROM user_totp_pending WHERE user_id = :user_id"

# อ่านใต้ล็อก — ชั้นที่หนึ่งของการกันใช้ซ้ำ (`plan.md` หัวข้อ 1.2)
_ACTIVE_LOCKED = """
SELECT secret_sealed, key_version, secret_version, last_accepted_step
FROM user_totp
WHERE user_id = :user_id
FOR UPDATE
"""

_ACTIVE_EXISTS = "SELECT 1 FROM user_totp WHERE user_id = :user_id"

# ชั้นที่สอง — `secret_version` อยู่ในเงื่อนไข ฉะนั้น secret ที่เปลี่ยนไประหว่างทาง
# ทำให้คำสั่งนี้กระทบศูนย์แถว แม้ลำดับเวลาจะผ่าน
_ACCEPT_STEP = """
UPDATE user_totp
SET last_accepted_step = :step, updated_at = now()
WHERE user_id = :user_id
  AND secret_version = :secret_version
  AND last_accepted_step < :step
"""

# **`last_accepted_step` เป็นช่วงของรหัสที่ยืนยันสำเร็จ ไม่ใช่ศูนย์** มิฉะนั้นรหัส
# ที่ผู้ใช้ใช้ยืนยันการตั้งค่าจะถูกนำไปใช้ซ้ำได้ทันที (RQ-4 · รีวิว 2026-10-03)
_ACTIVATE = """
INSERT INTO user_totp
    (user_id, secret_sealed, key_version, secret_version, last_accepted_step)
VALUES (:user_id, :sealed, :key_version, 1, :step)
ON CONFLICT (user_id)
DO UPDATE SET
    secret_sealed = :sealed,
    key_version = :key_version,
    secret_version = user_totp.secret_version + 1,
    last_accepted_step = :step,
    updated_at = now()
"""

_DISABLE = "DELETE FROM user_totp WHERE user_id = :user_id"


class CodeOutcome(Enum):
    """ผลของการตรวจรหัสหนึ่งครั้ง

    แยก `ALREADY_USED` ออกจาก `WRONG` **เพื่อบอกผู้ใช้ให้ถูก** — คนที่พิมพ์รหัสถูก
    แต่มันถูกใช้ไปแล้วต้องรู้ว่าให้รอรหัสของช่วงใหม่ ไม่ใช่คิดว่าเครื่องตัวเองเพี้ยน
    (validation V-61.2) · เป็นต้นทุนของการไม่มีช่วงผ่อนผันตามคำตอบ Q-6

    **ไม่ใช่การรั่วข้อมูล** เพราะคนที่ถึงจุดนี้ได้ผ่านรหัสผ่านหรือถือ session อยู่แล้ว
    และสิ่งที่บอกคือสถานะของรหัสที่เขาเพิ่งพิมพ์เอง
    """

    ACCEPTED = "ACCEPTED"
    WRONG = "WRONG"
    ALREADY_USED = "ALREADY_USED"


@dataclass(frozen=True, slots=True)
class ActiveSecret:
    """secret ที่เปิดใช้แล้วหนึ่งแถว ที่อ่านมาใต้ล็อก"""

    sealed: Sealed
    secret_version: int
    last_accepted_step: int


def new_secret() -> bytes:
    """secret ใหม่จากแหล่งสุ่มเชิงรหัสลับ"""
    return secrets.token_bytes(SECRET_BYTES)


def otpauth_uri(secret: bytes, *, account: str) -> str:
    """URI ที่แอป authenticator สแกนได้

    อยู่ที่นี่ไม่ใช่ใน `core` เพราะต้อง percent-encode ซึ่งใช้ `urllib.parse`
    และตัวตรวจความบริสุทธิ์ห้าม `urllib` ใน `core` (plan.md หัวข้อ 14.4)

    **ระบุ `algorithm`, `digits` และ `period` ไว้ตรง ๆ** ทั้งที่เป็นค่าปริยาย
    เพราะแอปบางตัวเดาค่าปริยายต่างกัน แล้วรหัสจะไม่ตรงโดยไม่มีใครรู้ว่าเพราะอะไร

    **เครื่องหมาย `:` ระหว่างผู้ออกกับบัญชีต้องเป็นตัวอักษรจริง ไม่ใช่ `%3A`**
    ข้อกำหนด Key Uri Format ยอมรับทั้งสองแบบ แต่ตัวอย่างในข้อกำหนดเองและ URI
    ที่บริการใหญ่ ๆ ใช้จริงเป็นแบบตัวอักษรจริงทั้งหมด — และ Google Authenticator
    สแกนแบบที่เข้ารหัสทั้งก้อนแล้วไม่เกิดอะไรขึ้น (พบตอนตรวจด้วยมือ M-1 2026-10-04)
    · encode ชื่อผู้ออกกับบัญชี **แยกชิ้น** จึงยังกันอักขระพิเศษในอีเมลได้ครบ
    """
    label = f"{quote(ISSUER, safe='')}:{quote(account, safe='')}"
    period = int(TIME_STEP.total_seconds())
    return (
        f"otpauth://totp/{label}"
        f"?secret={base32_secret(secret)}"
        f"&issuer={quote(ISSUER, safe='')}"
        f"&algorithm=SHA1"
        f"&digits={DIGITS}"
        f"&period={period}"
    )


async def stage_secret(session: UserSession, source: KeySource, secret: bytes) -> None:
    """เก็บ secret ที่ยังไม่พิสูจน์ — ทับของเดิมได้ **ไม่กระทบปัจจัยที่เปิดใช้อยู่**"""
    sealed = seal(source, secret, owner=session.user_id)
    await session.execute(
        _PENDING_UPSERT,
        {
            "user_id": str(session.user_id),
            "sealed": sealed.blob,
            "key_version": sealed.key_version,
        },
    )


async def confirm_secret(
    session: UserSession, source: KeySource, *, presented: str, now: datetime
) -> bool:
    """ยืนยัน secret ที่ค้างอยู่แล้วสลับเป็นตัวจริง — คืนว่าสำเร็จหรือไม่

    **ทั้งก้อนอยู่ใน transaction ของผู้เรียก** การสลับ secret, การยกเลิกรหัสสำรอง
    ชุดเก่า, การออกชุดใหม่ และการเพิกถอน session อื่น ต้องสำเร็จหรือล้มเหลวด้วยกัน
    (validation V-11.2)
    """
    pending = await _pending(session)
    if pending is None:
        return False

    secret = unseal(source, pending, owner=session.user_id)
    step = matching_step(secret, presented, at_step=step_at(now))
    if step is None:
        return False

    await session.execute(
        _ACTIVATE,
        {
            "user_id": str(session.user_id),
            "sealed": pending.blob,
            "key_version": pending.key_version,
            "step": step,
        },
    )
    await session.execute(_PENDING_DELETE, {"user_id": str(session.user_id)})
    return True


async def verify(
    session: UserSession, source: KeySource, *, presented: str, now: datetime
) -> CodeOutcome:
    """ตรวจรหัสกับ secret ที่เปิดใช้อยู่ และกันการใช้ซ้ำในคำสั่งเดียวกัน

    ลำดับคือ **ล็อก → ถอด → เทียบ → อนุญาต** และการอนุญาตผูกกับ `secret_version`
    ที่อ่านมาใต้ล็อก ฉะนั้นรหัสจาก secret ที่ถูกยกเลิกไปแล้วใช้ไม่ได้
    แม้ลำดับเวลาจะผ่านเงื่อนไข (validation V-20.1, V-20.2)
    """
    active = await _active_locked(session)
    if active is None:
        return CodeOutcome.WRONG

    secret = unseal(source, active.sealed, owner=session.user_id)
    step = matching_step(secret, presented, at_step=step_at(now))
    if step is None:
        return CodeOutcome.WRONG

    accepted = await session.execute(
        _ACCEPT_STEP,
        {
            "user_id": str(session.user_id),
            "secret_version": active.secret_version,
            "step": step,
        },
    )
    # ศูนย์แถว = รหัสถูกใช้ไปแล้ว **หรือ** secret เปลี่ยนไประหว่างทาง → ปฏิเสธทั้งคู่
    #
    # ใช้ `rowcount` ไม่ใช่ `RETURNING` ด้วยเหตุผลเดียวกับ `sessions.py` ของ F-05:
    # `RETURNING` อ้างคอลัมน์ ซึ่งดึง SELECT policy มาใช้ด้วย
    if cast("CursorResult[Any]", accepted).rowcount:
        return CodeOutcome.ACCEPTED
    # รหัสตรงกับ secret ปัจจุบัน แต่ลำดับนั้นถูกรับไปแล้ว หรือ secret เปลี่ยนระหว่างทาง
    return CodeOutcome.ALREADY_USED


async def is_enabled(session: UserSession) -> bool:
    """ผู้ใช้คนนี้เปิด TOTP แล้วหรือยัง — คำตอบที่ F-24 ใช้ (RQ-12)

    **secret ที่ยังไม่ยืนยันนับว่ายังไม่เปิด** เพราะมันไม่มีผลกับการยืนยันตัวตนเลย
    """
    found = (await session.execute(_ACTIVE_EXISTS, {"user_id": str(session.user_id)})).all()
    return found != []


async def disable(session: UserSession) -> None:
    """ปิด TOTP — ลบทั้งของที่เปิดใช้และของที่ค้างอยู่

    ลบของที่ค้างด้วยเพราะถ้าเหลือไว้ การเปิดใหม่ครั้งถัดไปจะยืนยันด้วย secret เก่า
    ที่ผู้ใช้อาจไม่ได้ถืออยู่แล้วได้
    """
    await session.execute(_DISABLE, {"user_id": str(session.user_id)})
    await session.execute(_PENDING_DELETE, {"user_id": str(session.user_id)})


async def _pending(session: UserSession) -> Sealed | None:
    """secret ที่ค้างอยู่ของผู้ใช้คนนี้"""
    row = (await session.execute(_PENDING_READ, {"user_id": str(session.user_id)})).one_or_none()
    if row is None:
        return None
    blob, key_version = tuple(row)
    if not isinstance(blob, bytes) or not isinstance(key_version, str):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง user_totp_pending")
    return Sealed(key_version=key_version, blob=blob)


async def _active_locked(session: UserSession) -> ActiveSecret | None:
    """secret ที่เปิดใช้อยู่ **ใต้ล็อกของแถว** — ล็อกจนจบ transaction ของผู้เรียก"""
    row = (await session.execute(_ACTIVE_LOCKED, {"user_id": str(session.user_id)})).one_or_none()
    if row is None:
        return None
    blob, key_version, secret_version, last_accepted_step = tuple(row)
    if (
        not isinstance(blob, bytes)
        or not isinstance(key_version, str)
        or not isinstance(secret_version, int)
        or not isinstance(last_accepted_step, int)
    ):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง user_totp")
    return ActiveSecret(
        sealed=Sealed(key_version=key_version, blob=blob),
        secret_version=secret_version,
        last_accepted_step=last_accepted_step,
    )
