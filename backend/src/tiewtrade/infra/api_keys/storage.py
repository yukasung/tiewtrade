"""เก็บ อ่าน ลบ และขอให้ตรวจใหม่ — **ฝั่งที่ `api` เรียกเท่านั้น** (F-07 `plan.md` ข้อ 8)

**ที่นี่ปิดผนึก secret แล้วทิ้งค่าดิบทันที** `api` ถือค่าดิบได้ชั่วขณะเดียวคือตอนผู้ใช้
กรอก (`tech-stack.md` หัวข้อ 8) ฉะนั้นค่าดิบต้องไม่เดินทางต่อไปไหน ไม่ถูกคืนกลับ
และไม่ถูกเก็บไว้ที่ใด

**การอ่านกลับทำไม่ได้อยู่แล้วที่ระดับสิทธิ์** — บทบาท `api` ไม่มี `SELECT` บน
คอลัมน์ที่เก็บค่าที่ปิดผนึก (migration `0009`) ฉะนั้นถึงโค้ดที่นี่จะพลาด
ฐานข้อมูลก็ยังปฏิเสธ

**เพดานจำนวน key ตรวจใต้ล็อก** ไม่ใช่ตรวจแล้วค่อยเขียน เพราะคำขอที่มาพร้อมกัน
จะอ่านจำนวนเดิมทั้งคู่แล้วเขียนทั้งคู่ · ล็อกเป็น advisory lock ที่ผูกกับผู้ใช้
เพราะบทบาท `api` ไม่มีสิทธิ์ล็อกแถวในตาราง `users` (migration `0002` ให้แค่ `SELECT`)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import RowMapping

from tiewtrade.infra.api_keys.records import (
    MAX_CREDENTIAL_LENGTH,
    MAX_KEYS_PER_USER,
    MAX_LABEL_LENGTH,
    ApiKeyError,
    ApiKeyStatus,
    ApiKeySummary,
    TooManyKeysError,
    accepted_label_text,
    accepted_public_identifier,
    public_tail,
)
from tiewtrade.infra.crypto import KeyPurpose, KeySource, seal
from tiewtrade.infra.db.session import UserSession

#: หมายเลขกลุ่มของ advisory lock ของงานนี้ — คนละกลุ่มกับงานอื่นที่จะมาทีหลัง
#:
#: ใช้แบบสองจำนวนเต็มเพื่อให้กลุ่มของแต่ละงานไม่ชนกันเอง และ **คำนวณหมายเลขของ
#: ผู้ใช้ในฝั่ง Python** ไม่ใช่เรียกฟังก์ชันแฮชภายในของฐานข้อมูล ซึ่งไม่มีสัญญาว่า
#: จะให้ค่าเดิมข้ามรุ่น
_LOCK_CLASS: Final[int] = 70_07

_LOCK = "SELECT pg_advisory_xact_lock(:class_id, :object_id)"

_COUNT = "SELECT count(*) FROM user_api_keys WHERE user_id = :user_id"

_INSERT = """
INSERT INTO user_api_keys
    (id, user_id, label, key_public, secret_sealed, key_version, status)
VALUES
    (:id, :user_id, :label, :key_public, :secret_sealed, :key_version, 'PENDING')
"""

#: **ไม่เลือก `secret_sealed` และ `key_version`** — บทบาทนี้อ่านไม่ได้ และคำสั่งที่
#: ขอจะถูกฐานข้อมูลปฏิเสธทั้งคำสั่ง
#: UI flag และ UPDATE ใช้กฎเดียวกัน · ผู้ชี้ขาดเวลาคือฐานข้อมูลเสมอ (RQ-11.4)
_RETRY_ELIGIBILITY = """
status = 'UNVERIFIABLE'
AND (not_before IS NULL OR not_before <= clock_timestamp())
"""

_SUMMARIES = f"""
SELECT id, label, key_public, status, failure_code,
       created_at, verified_at, not_before, next_attempt_at,
       ({_RETRY_ELIGIBILITY}) AS may_retry
FROM user_api_keys
WHERE user_id = :user_id
ORDER BY created_at
"""

_DELETE = "DELETE FROM user_api_keys WHERE id = :id RETURNING id"

#: อ่านสถานะและเวลาที่ตลาดสั่งให้รอ ก่อนตัดสินใจเรื่องปุ่มลองใหม่
_RETRY_TARGET = f"""
SELECT status, not_before, ({_RETRY_ELIGIBILITY}) AS may_retry
FROM user_api_keys
WHERE id = :id
"""

#: **เขียนช่องเดียว** ซึ่งเป็นช่องเดียวที่บทบาทนี้มีสิทธิ์เขียน (migration `0009`)
#:
#: เงื่อนไข `not_before` อยู่ในคำสั่งด้วย **ไม่ใช่เพราะที่นี่เป็นด่านหลัก** —
#: ด่านหลักคือคำสั่งจองของ worker (`plan.md` ข้อ 7.5) ที่นี่มีไว้ให้ผู้ใช้รู้ตัวเร็วขึ้น
#: และเพื่อไม่ให้แถวที่ตลาดสั่งให้รอถูกทำเครื่องหมายว่ามีคนขอแล้ว
_REQUEST_RETRY = f"""
UPDATE user_api_keys
SET retry_requested_at = clock_timestamp()
WHERE id = :id
  AND ({_RETRY_ELIGIBILITY})
RETURNING id
"""


class RetryOutcome(Enum):
    """ผลของการกดปุ่มลองใหม่ — แยกให้ชั้นบนเลือกข้อความได้เอง"""

    #: รับคำขอแล้ว รอบตรวจถัดไปจะหยิบแถวนี้ขึ้นมา
    ACCEPTED = "ACCEPTED"
    #: ไม่พบ key นั้นของผู้ใช้คนนี้ (RLS ทำให้ของคนอื่นเป็น "ไม่พบ" เหมือนกัน)
    NOT_FOUND = "NOT_FOUND"
    #: สถานะนี้กดลองใหม่ไม่ได้ — ตรวจผ่านแล้ว หรือถูกปฏิเสธถาวรแล้ว
    NOT_RETRYABLE = "NOT_RETRYABLE"
    #: ตลาดสั่งให้รอ — **ข้ามไม่ได้** ผู้เรียกบอกเวลาที่กดได้ให้ผู้ใช้
    MUST_WAIT = "MUST_WAIT"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """ผลและเวลาที่กดได้ ถ้ายังกดไม่ได้"""

    outcome: RetryOutcome
    not_before: datetime | None = None


def _accepted_label(label: str) -> str:
    """ชื่อที่ผู้ใช้ตั้ง — ตัดช่องว่างหัวท้ายแล้วตรวจความยาว

    ปฏิเสธที่นี่ **ก่อนถึงฐานข้อมูล** ตามข้อเดียวกับ F-03 RQ-9.1: ข้อความข้อผิดพลาด
    ของ PostgreSQL อ้างค่าที่ผิดได้ ซึ่งเป็นทางที่ค่าของผู้ใช้ไปโผล่ใน log
    """
    cleaned = accepted_label_text(label).strip()
    if not cleaned:
        raise ApiKeyError("ต้องตั้งชื่อให้ key")
    if len(cleaned) > MAX_LABEL_LENGTH:
        raise ApiKeyError(f"ชื่อ key ยาวเกิน {MAX_LABEL_LENGTH} ตัวอักษร")
    return cleaned


def _accepted_credential(value: str, *, field: str) -> str:
    """ค่าที่ผู้ใช้กรอก — **ข้อความข้อผิดพลาดบอกชื่อช่อง ไม่บอกค่า**"""
    cleaned = value.strip()
    if not cleaned:
        raise ApiKeyError(f"ต้องกรอก{field}")
    if len(cleaned) > MAX_CREDENTIAL_LENGTH:
        raise ApiKeyError(f"{field}ยาวเกินกว่าที่ตลาดออกให้")
    return cleaned


def _lock_arguments(user_id: UUID) -> dict[str, int]:
    """หมายเลขล็อกของผู้ใช้คนหนึ่ง — คงที่ข้ามกระบวนการและข้ามรุ่นของฐานข้อมูล"""
    return {"class_id": _LOCK_CLASS, "object_id": user_id.int % (2**31)}


async def store_key(
    session: UserSession,
    keys: KeySource,
    *,
    user_id: UUID,
    label: str,
    key_public: str,
    secret: str,
) -> UUID:
    """ปิดผนึก secret แล้วบันทึกแถวสถานะ "กำลังตรวจ"

    **ค่าดิบตายที่นี่** — ออกจากฟังก์ชันนี้ไปแล้วไม่มีใครในกระบวนการนี้อ่านมันได้อีก
    และแถวที่บันทึกไว้ `api` ก็อ่านกลับไม่ได้

    คืนรหัสของแถว ไม่ใช่ตัวแถว เพราะผู้เรียกไม่มีเหตุต้องรู้อะไรมากกว่านั้น
    """
    if keys.purpose is not KeyPurpose.VENUE_API_SECRET:
        raise ApiKeyError("ต้องใช้กุญแจของ API key เท่านั้น ไม่ใช่กุญแจของงานอื่น")

    accepted_label = _accepted_label(label)
    accepted_public = accepted_public_identifier(key_public)
    accepted_secret = _accepted_credential(secret, field="secret")

    await session.execute(_LOCK, _lock_arguments(user_id))
    stored = (await session.execute(_COUNT, {"user_id": user_id})).scalar_one()
    if stored >= MAX_KEYS_PER_USER:
        raise TooManyKeysError(f"เพิ่ม key ได้ไม่เกิน {MAX_KEYS_PER_USER} อันต่อผู้ใช้")

    sealed = seal(keys, accepted_secret.encode(), owner=user_id)
    key_id = uuid4()
    await session.execute(
        _INSERT,
        {
            "id": key_id,
            "user_id": user_id,
            "label": accepted_label,
            "key_public": accepted_public,
            "secret_sealed": sealed.blob,
            "key_version": sealed.key_version,
        },
    )
    return key_id


def _summary_of(mapping: RowMapping) -> ApiKeySummary:
    """แปลงแถวหนึ่งเป็นสิ่งที่หน้าจอเห็น — **ตัด key เต็มทิ้งตรงนี้**"""
    return ApiKeySummary(
        id=mapping["id"],
        label=mapping["label"],
        public_tail=public_tail(mapping["key_public"]),
        status=ApiKeyStatus(mapping["status"]),
        created_at=mapping["created_at"],
        failure_code=mapping["failure_code"],
        verified_at=mapping["verified_at"],
        not_before=mapping["not_before"],
        next_attempt_at=mapping["next_attempt_at"],
        may_retry=mapping["may_retry"],
    )


async def summaries_for(session: UserSession, user_id: UUID) -> tuple[ApiKeySummary, ...]:
    """รายการ key ของผู้ใช้คนนี้ — RLS เป็นผู้กันของคนอื่นออก ไม่ใช่เงื่อนไขในคำสั่ง"""
    result = await session.execute(_SUMMARIES, {"user_id": user_id})
    return tuple(_summary_of(row) for row in result.mappings().all())


async def delete_key(session: UserSession, key_id: UUID) -> bool:
    """ลบ key ของผู้ใช้คนนี้ — คืน `False` เมื่อไม่พบ ซึ่งรวมกรณีเป็นของคนอื่น

    **ไม่แยกว่า "ไม่มี" หรือ "ของคนอื่น"** ตาม `security.md` หัวข้อ 2
    """
    result = await session.execute(_DELETE, {"id": key_id})
    return result.first() is not None


async def request_retry(session: UserSession, key_id: UUID) -> RetryDecision:
    """ขอให้ตรวจแถวนี้ใหม่ — เขียนได้ช่องเดียวที่บทบาทนี้มีสิทธิ์เขียน

    **ไม่ต้องยืนยันปัจจัยที่สองซ้ำ** (เจ้าของตัดสิน 2026-10-04) เพราะ secret
    เข้าระบบไปแล้วตอนเพิ่ม ซึ่งผ่านการยืนยันไปแล้ว การลองใหม่ไม่ได้เพิ่มความเสี่ยงใหม่
    """
    target = (await session.execute(_RETRY_TARGET, {"id": key_id})).mappings().first()
    if target is None:
        return RetryDecision(RetryOutcome.NOT_FOUND)

    status = ApiKeyStatus(target["status"])
    if status is not ApiKeyStatus.UNVERIFIABLE:
        return RetryDecision(RetryOutcome.NOT_RETRYABLE)

    updated = await session.execute(_REQUEST_RETRY, {"id": key_id})
    if updated.first() is None:
        # UPDATE ใช้สถานะปัจจุบันแล้ว · เวลาที่อ่านก่อนหน้าจึงอาจล้าสมัย
        target = (await session.execute(_RETRY_TARGET, {"id": key_id})).mappings().first()
        if target is None:
            return RetryDecision(RetryOutcome.NOT_FOUND)
        if ApiKeyStatus(target["status"]) is not ApiKeyStatus.UNVERIFIABLE or target["may_retry"]:
            return RetryDecision(RetryOutcome.NOT_RETRYABLE)
        return RetryDecision(RetryOutcome.MUST_WAIT, not_before=target["not_before"])
    return RetryDecision(RetryOutcome.ACCEPTED)
