"""การจองแถวและการเขียนผล — ฝั่งที่ `engine` เรียก (F-07 `plan.md` ข้อ 7.5)

**ล็อกของฐานข้อมูลใช้ที่นี่ไม่ได้** มันหมดอายุเมื่อ transaction จบ แต่รอบตรวจ
**ต้องไม่เปิด transaction คร่อมการเรียกตลาด** (ถือล็อกข้ามการรอเครือข่ายคือการให้
ตลาดกำหนดว่าเราถือล็อกนานแค่ไหน) การจองจึงเป็นคอลัมน์ที่มีอายุของตัวเอง
และหมดอายุเองเมื่อ worker ตาย ไม่ต้องมีใครไปปลด

**เงื่อนไข "ถึงคิว" อยู่ในคำสั่งจอง ไม่ใช่ในผลของการ scan** ผล scan เป็นเพียงคำใบ้
พอ worker อีกตัวตรวจเสร็จและบันทึกว่าตลาดสั่งให้รอ ผลเก่าก็ล้าสมัยทันที

**ทุกคำสั่งเขียนผลผูกกับการจองของตัวเอง** ฉะนั้นผลของรอบที่ช้าจะเขียนทับผลของรอบใหม่
ไม่ได้ แม้ worker ตัวเก่าจะยังมีชีวิตและคำตอบเพิ่งกลับมา

**เวลาใช้ `clock_timestamp()` ไม่ใช่ `now()`** เพราะ `now()` คือเวลาที่ transaction
เริ่ม ซึ่งทำให้แถวที่หมดอายุระหว่างรอตลาดกลายเป็น "ยังไม่หมดอายุ" ได้
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID, uuid4

from tiewtrade.infra.db.session import ScanSession, UserSession

#: อายุของแถวที่ยังไม่ผ่านการตรวจ — ครบแล้วถูกปฏิเสธและ secret ถูกลบ (Q-7)
#:
#: **นับจากเวลาที่ผู้ใช้เพิ่ม key ไม่ใช่นับใหม่ทุกครั้งที่ลองใหม่** การนับใหม่
#: ทำให้แถวที่ลองใหม่เรื่อย ๆ ไม่มีวันหมดอายุ ซึ่งเท่ากับไม่มีเพดาน
VERIFICATION_DEADLINE: Final = timedelta(hours=24)

#: อายุของการจองหนึ่งครั้ง — ต้องยาวกว่า timeout ของการเรียกตลาดแบบมีระยะเผื่อ
CLAIM_LEASE: Final = timedelta(minutes=2)

#: ช่วงรอก่อนลองใหม่ ตามจำนวนครั้งที่พยายามไปแล้ว — **ตัวเลขอยู่ที่เดียว**
BACKOFF_STEPS: Final[tuple[timedelta, ...]] = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
)

#: รหัสของการหมดเวลาตรวจ — ต้องตรงกับที่ migration `0009` ประกาศไว้
EXPIRED_CODE: Final = "VERIFICATION_EXPIRED"

_UNFINISHED = ("PENDING", "UNVERIFIABLE")

#: หาแถวที่ "น่าจะ" ถึงคิว — **คำใบ้เท่านั้น** เงื่อนไขจริงอยู่ในคำสั่งจอง
_DUE_HINTS = """
SELECT id, user_id
FROM user_api_keys
WHERE status IN ('PENDING', 'UNVERIFIABLE')
ORDER BY created_at
LIMIT :limit
"""

#: แถวที่หมดอายุแล้ว — **คำสั่งของตัวเอง ไม่ใช่มาจองแล้วค่อยพบว่าหมดอายุ**
_EXPIRE = """
UPDATE user_api_keys
SET status = 'REJECTED',
    failure_code = :code,
    secret_sealed = NULL,
    key_version = NULL,
    claimed_by = NULL,
    claim_id = NULL,
    claim_expires_at = NULL
WHERE id = :id
  AND status IN ('PENDING', 'UNVERIFIABLE')
  AND clock_timestamp() >= created_at + :deadline
RETURNING id
"""

#: จองแถว — **เงื่อนไขถึงคิวครบทุกข้ออยู่ที่นี่** (`plan.md` ข้อ 7.5)
_CLAIM = """
UPDATE user_api_keys
SET claimed_by = :worker,
    claim_id = :claim,
    claim_expires_at = clock_timestamp() + :lease,
    last_attempt_at = clock_timestamp(),
    attempts = attempts + 1
WHERE id = :id
  AND status IN ('PENDING', 'UNVERIFIABLE')
  AND clock_timestamp() < created_at + :deadline
  AND (claim_expires_at IS NULL OR claim_expires_at < clock_timestamp())
  AND (not_before IS NULL OR not_before <= clock_timestamp())
  AND (
        next_attempt_at IS NULL
     OR retry_requested_at > last_attempt_at
     OR next_attempt_at <= clock_timestamp()
  )
RETURNING id, key_public, secret_sealed, key_version, attempts, status
"""

#: ส่วนท้ายที่ทุกคำสั่งเขียนผลต้องมี — เจ้าของการจอง **และยังไม่หมดอายุ ณ ตอนเขียน**
_OWNED_AND_IN_TIME = """
  AND claimed_by = :worker
  AND claim_id = :claim
  AND clock_timestamp() < claim_expires_at
  AND clock_timestamp() < created_at + :deadline
"""

_MARK_ACTIVE = f"""
UPDATE user_api_keys
SET status = 'ACTIVE',
    failure_code = NULL,
    verified_at = clock_timestamp(),
    next_attempt_at = NULL,
    not_before = NULL,
    claimed_by = NULL,
    claim_id = NULL,
    claim_expires_at = NULL
WHERE id = :id
{_OWNED_AND_IN_TIME}
RETURNING id
"""

_MARK_REJECTED = f"""
UPDATE user_api_keys
SET status = 'REJECTED',
    failure_code = :code,
    secret_sealed = NULL,
    key_version = NULL,
    next_attempt_at = NULL,
    claimed_by = NULL,
    claim_id = NULL,
    claim_expires_at = NULL
WHERE id = :id
{_OWNED_AND_IN_TIME}
RETURNING id
"""

_MARK_DEFERRED = f"""
UPDATE user_api_keys
SET status = 'UNVERIFIABLE',
    failure_code = :code,
    next_attempt_at = clock_timestamp() + :backoff,
    -- **เวลาที่ตลาดสั่งให้รอ คิดจากนาฬิกาของฐานข้อมูล** ไม่ใช่นาฬิกาของ worker
    -- ตัวหลังเดินไม่ตรงกันได้ แล้วเราจะยิงตลาดก่อนเวลาที่มันสั่ง
    not_before = CASE
        WHEN CAST(:retry_after AS interval) IS NULL THEN NULL
        ELSE clock_timestamp() + CAST(:retry_after AS interval)
    END,
    claimed_by = NULL,
    claim_id = NULL,
    claim_expires_at = NULL
WHERE id = :id
{_OWNED_AND_IN_TIME}
RETURNING id
"""


@dataclass(frozen=True, slots=True)
class DueKey:
    """แถวที่ "น่าจะ" ถึงคิว — ยังไม่ได้จอง"""

    id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ClaimedKey:
    """แถวที่จองได้แล้ว พร้อมของที่ต้องใช้ตรวจ

    **ถือค่าที่ปิดผนึกไว้ ไม่ใช่ค่าดิบ** — การเปิดผนึกเป็นหน้าที่ของผู้เรียก
    ซึ่งอยู่ใน `engine` และถือกุญแจอยู่แล้ว
    """

    id: UUID
    user_id: UUID
    claim_id: UUID
    key_public: str
    secret_sealed: bytes
    key_version: str
    attempts: int


def backoff_for(attempts: int) -> timedelta:
    """ช่วงรอหลังความพยายามครั้งที่ `attempts` — ยาวขึ้นจนถึงขั้นสุดท้ายแล้วคงที่"""
    index = min(max(attempts, 1), len(BACKOFF_STEPS)) - 1
    return BACKOFF_STEPS[index]


async def due_hints(session: ScanSession, *, limit: int = 100) -> tuple[DueKey, ...]:
    """แถวที่ยังไม่จบ **ข้ามผู้ใช้** — บทบาทนี้อ่านความลับไม่ได้ (migration `0009`)"""
    result = await session.execute(_DUE_HINTS, {"limit": limit})
    return tuple(DueKey(id=row["id"], user_id=row["user_id"]) for row in result.mappings().all())


async def expire_if_overdue(session: UserSession, key_id: UUID) -> bool:
    """ปิดแถวที่หมดอายุแล้ว — **ทำก่อนจอง ไม่ใช่หลังเรียกตลาด**"""
    result = await session.execute(
        _EXPIRE, {"id": key_id, "code": EXPIRED_CODE, "deadline": VERIFICATION_DEADLINE}
    )
    return result.first() is not None


async def claim(session: UserSession, key: DueKey, *, worker: str) -> ClaimedKey | None:
    """จองแถวนั้นถ้ามันถึงคิวจริง — `None` เมื่อยังไม่ถึงคิวหรือมีคนจองอยู่"""
    claim_id = uuid4()
    row = (
        (
            await session.execute(
                _CLAIM,
                {
                    "id": key.id,
                    "worker": worker,
                    "claim": claim_id,
                    "lease": CLAIM_LEASE,
                    "deadline": VERIFICATION_DEADLINE,
                },
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    return ClaimedKey(
        id=key.id,
        user_id=key.user_id,
        claim_id=claim_id,
        key_public=row["key_public"],
        secret_sealed=bytes(row["secret_sealed"]),
        key_version=row["key_version"],
        attempts=row["attempts"],
    )


def _ownership(claimed: ClaimedKey, worker: str) -> dict[str, object]:
    return {
        "id": claimed.id,
        "worker": worker,
        "claim": claimed.claim_id,
        "deadline": VERIFICATION_DEADLINE,
    }


async def mark_active(session: UserSession, claimed: ClaimedKey, *, worker: str) -> bool:
    """ตรวจผ่าน — คืน `False` เมื่อการจองหมดอายุหรือแถวหมดอายุไปแล้ว

    **คืน `False` ไม่ใช่ความผิดพลาด** มันคือกรณีที่ผลมาถึงช้ากว่าเส้นตาย
    ซึ่ง `requirements.md` สั่งให้ทิ้งผลนั้น
    """
    result = await session.execute(_MARK_ACTIVE, _ownership(claimed, worker))
    return result.first() is not None


async def mark_rejected(
    session: UserSession, claimed: ClaimedKey, *, worker: str, code: str
) -> bool:
    """key ใช้ไม่ได้จริง — **ลบค่าที่ปิดผนึกทันที** (Q-7)"""
    result = await session.execute(_MARK_REJECTED, _ownership(claimed, worker) | {"code": code})
    return result.first() is not None


async def mark_deferred(
    session: UserSession,
    claimed: ClaimedKey,
    *,
    worker: str,
    code: str,
    retry_after: timedelta | None = None,
) -> bool:
    """ตรวจไม่ได้ชั่วคราว — **ห้ามลบ secret** และตั้งช่วงรอครั้งถัดไป

    `retry_after` คือช่วงที่ **ตลาด** สั่งให้รอ ซึ่งกลายเป็น `not_before` ที่ผู้ใช้
    กดข้ามไม่ได้ · ต่างจาก `next_attempt_at` ที่เป็นช่วงรอของเราเองและปุ่มลองใหม่ข้ามได้
    """
    arguments = _ownership(claimed, worker) | {
        "code": code,
        "backoff": backoff_for(claimed.attempts),
        "retry_after": retry_after,
    }
    result = await session.execute(_MARK_DEFERRED, arguments)
    return result.first() is not None


__all__ = [
    "BACKOFF_STEPS",
    "CLAIM_LEASE",
    "EXPIRED_CODE",
    "VERIFICATION_DEADLINE",
    "ClaimedKey",
    "DueKey",
    "backoff_for",
    "claim",
    "due_hints",
    "expire_if_overdue",
    "mark_active",
    "mark_deferred",
    "mark_rejected",
]
