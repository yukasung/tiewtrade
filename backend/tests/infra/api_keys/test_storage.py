"""ชั้นเก็บ API key — V-8 (ฝั่งหลังบ้าน), V-29, V-31 และเส้นทางของค่าดิบ

**รันกับฐานข้อมูลจริง** เพราะสิ่งที่พิสูจน์คือสิทธิ์ เพดานใต้ล็อก และ RLS
"""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import (
    MAX_KEYS_PER_USER,
    ApiKeyError,
    ApiKeyStatus,
    RetryOutcome,
    TooManyKeysError,
    delete_key,
    request_retry,
    store_key,
    summaries_for,
)
from tiewtrade.infra.crypto import KeyPurpose, KeySource, Sealed, SealingError, unseal
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.users import create_user

SECRET = "secret-that-must-never-come-back"
PUBLIC = "PUBLICKEY000000ABCD"


@pytest.mark.parametrize("bad_key", ["ทดสอบ", "bad\r\nheader", "bad\x00", "bad\x7f"])
async def test_malformed_identifier_is_rejected_before_database_access(
    venue_keys: KeySource,
    bad_key: str,
) -> None:
    # ไม่มี session ที่เรียกได้: ถ้าแตะฐานข้อมูลก่อนตรวจ input เทสต์จะล้ม
    with pytest.raises(ApiKeyError) as refused:
        await store_key(
            cast(UserSession, None),
            venue_keys,
            user_id=uuid4(),
            label="valid",
            key_public=bad_key,
            secret=SECRET,
        )
    assert bad_key not in str(refused.value)
    assert SECRET not in str(refused.value)


async def _store(
    engine: AsyncEngine, keys: KeySource, user_id: UUID, *, label: str = "หลัก"
) -> UUID:
    async with user_session(engine, user_id) as session:
        return await store_key(
            session,
            keys,
            user_id=user_id,
            label=label,
            key_public=PUBLIC,
            secret=SECRET,
        )


async def test_what_the_screen_sees_has_only_the_last_four_digits(
    api_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """Q-5 — แสดงได้แค่ 4 หลักท้ายของ API key และไม่มีช่องของ secret เลย"""
    owner = uuid4()
    await create_user(api_engine, owner)
    await _store(api_engine, venue_keys, owner)

    async with user_session(api_engine, owner) as session:
        summaries = await summaries_for(session, owner)

    assert len(summaries) == 1
    assert summaries[0].public_tail == "ABCD"
    assert summaries[0].status is ApiKeyStatus.PENDING
    # ไม่มีช่องไหนในสิ่งที่หน้าจอเห็นที่พา key เต็มหรือ secret ออกมา
    assert PUBLIC not in repr(summaries[0])
    assert SECRET not in repr(summaries[0])


async def test_the_engine_can_unseal_what_the_api_sealed(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """V-3 — ค่าที่ `api` ปิดผนึกไว้ `engine` เปิดได้และได้ค่าเดิม"""
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _store(api_engine, venue_keys, owner)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        row = (
            (
                await session.execute(
                    "SELECT secret_sealed, key_version FROM user_api_keys WHERE id = :id",
                    {"id": key_id},
                )
            )
            .mappings()
            .one()
        )

    opened = unseal(
        venue_keys,
        Sealed(key_version=row["key_version"], blob=bytes(row["secret_sealed"])),
        owner=owner,
    )
    assert opened.decode() == SECRET


async def test_a_sealed_secret_does_not_open_for_another_user(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """V-10 — ค่าที่ปิดผนึกผูกกับเจ้าของ การย้ายแถวจึงไม่ใช่การสวมรอย"""
    owner, stranger = uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, stranger)
    key_id = await _store(api_engine, venue_keys, owner)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        row = (
            (
                await session.execute(
                    "SELECT secret_sealed, key_version FROM user_api_keys WHERE id = :id",
                    {"id": key_id},
                )
            )
            .mappings()
            .one()
        )

    with pytest.raises(SealingError):
        unseal(
            venue_keys,
            Sealed(key_version=row["key_version"], blob=bytes(row["secret_sealed"])),
            owner=stranger,
        )


async def test_the_totp_key_cannot_open_an_api_secret(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """V-9 — สองงานใช้กุญแจคนละดอก และสลับกันแล้วเปิดไม่ออก (RQ-4)"""
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _store(api_engine, venue_keys, owner)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        row = (
            (
                await session.execute(
                    "SELECT secret_sealed, key_version FROM user_api_keys WHERE id = :id",
                    {"id": key_id},
                )
            )
            .mappings()
            .one()
        )

    totp_keys = KeySource.from_environment(KeyPurpose.TOTP_SECRET)
    with pytest.raises(SealingError):
        unseal(
            totp_keys,
            Sealed(key_version=row["key_version"], blob=bytes(row["secret_sealed"])),
            owner=owner,
        )


async def test_storing_with_the_wrong_purpose_is_refused(
    api_engine: AsyncEngine,
) -> None:
    """RQ-4 — กุญแจของงานอื่นใช้ที่นี่ไม่ได้ และถูกปฏิเสธก่อนแตะฐานข้อมูล"""
    owner = uuid4()
    await create_user(api_engine, owner)
    totp_keys = KeySource.from_environment(KeyPurpose.TOTP_SECRET)

    async with user_session(api_engine, owner) as session:
        with pytest.raises(ApiKeyError):
            await store_key(
                session,
                totp_keys,
                user_id=owner,
                label="หลัก",
                key_public=PUBLIC,
                secret=SECRET,
            )


@pytest.mark.parametrize(
    ("label", "key_public", "secret"),
    [
        *((label, PUBLIC, SECRET) for label in ("\x00หลัก", "หลัก\x00รอง", "หลัก\x00")),
        ("", PUBLIC, SECRET),
        ("   ", PUBLIC, SECRET),
        ("ชื่อ" * 20, PUBLIC, SECRET),
        ("หลัก", "", SECRET),
        ("หลัก", PUBLIC, ""),
        ("หลัก", PUBLIC, "x" * 300),
    ],
)
async def test_input_is_refused_before_it_reaches_the_database(
    api_engine: AsyncEngine,
    venue_keys: KeySource,
    label: str,
    key_public: str,
    secret: str,
) -> None:
    """RQ-13 — ค่าที่ผิดถูกปฏิเสธก่อนถึงฐานข้อมูล (ข้อเดียวกับ F-03 RQ-9.1)"""
    owner = uuid4()
    await create_user(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        with pytest.raises(ApiKeyError):
            await store_key(
                session,
                venue_keys,
                user_id=owner,
                label=label,
                key_public=key_public,
                secret=secret,
            )


async def test_error_messages_never_carry_the_value(
    api_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """RQ-2 — ข้อความข้อผิดพลาดบอกชื่อช่อง ไม่บอกค่าที่กรอก"""
    owner = uuid4()
    await create_user(api_engine, owner)
    overlong = "s" * 300

    async with user_session(api_engine, owner) as session:
        with pytest.raises(ApiKeyError) as caught:
            await store_key(
                session,
                venue_keys,
                user_id=owner,
                label="หลัก",
                key_public=PUBLIC,
                secret=overlong,
            )

    assert overlong not in str(caught.value)


async def test_the_cap_holds(api_engine: AsyncEngine, venue_keys: KeySource) -> None:
    """V-29 — เพิ่มได้ถึงเพดาน แล้วอันถัดไปถูกปฏิเสธ"""
    owner = uuid4()
    await create_user(api_engine, owner)
    for index in range(MAX_KEYS_PER_USER):
        await _store(api_engine, venue_keys, owner, label=f"key-{index}")

    with pytest.raises(TooManyKeysError):
        await _store(api_engine, venue_keys, owner, label="เกิน")


async def test_the_cap_holds_against_requests_that_arrive_together(
    api_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """V-29 — ยิงพร้อมกันเกินเพดานแล้วต้องได้เท่าเพดานพอดี

    เทสต์นี้คือเหตุผลที่การตรวจเพดานอยู่ใต้ล็อก — ถ้าตรวจแล้วค่อยเขียน
    คำขอที่มาพร้อมกันจะอ่านจำนวนเดิมทั้งหมดแล้วเขียนทั้งหมด
    """
    owner = uuid4()
    await create_user(api_engine, owner)
    attempts = MAX_KEYS_PER_USER + 4

    results = await asyncio.gather(
        *(_store(api_engine, venue_keys, owner, label=f"key-{index}") for index in range(attempts)),
        return_exceptions=True,
    )

    stored = [outcome for outcome in results if isinstance(outcome, UUID)]
    refused = [outcome for outcome in results if isinstance(outcome, TooManyKeysError)]
    assert len(stored) == MAX_KEYS_PER_USER
    assert len(refused) == attempts - MAX_KEYS_PER_USER


async def test_deleting_someone_elses_key_reports_not_found(
    api_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """V-28 — ลบของคนอื่นได้ "ไม่พบ" ไม่ใช่ "ไม่มีสิทธิ์" และของเขายังอยู่"""
    owner, stranger = uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, stranger)
    theirs = await _store(api_engine, venue_keys, stranger)

    async with user_session(api_engine, owner) as session:
        assert await delete_key(session, theirs) is False

    async with user_session(api_engine, stranger) as session:
        assert len(await summaries_for(session, stranger)) == 1


async def test_deleting_own_key_frees_the_label(
    api_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """Q-6 — เปลี่ยน key คือลบแล้วเพิ่มใหม่ ฉะนั้นชื่อเดิมต้องกลับมาใช้ได้"""
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _store(api_engine, venue_keys, owner, label="หลัก")

    async with user_session(api_engine, owner) as session:
        assert await delete_key(session, key_id) is True

    await _store(api_engine, venue_keys, owner, label="หลัก")


async def test_retry_is_refused_for_a_key_that_is_still_pending(
    api_engine: AsyncEngine, venue_keys: KeySource
) -> None:
    """Q-7 — ปุ่มลองใหม่มีเฉพาะแถวที่ตรวจไม่ได้ชั่วคราว"""
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _store(api_engine, venue_keys, owner)

    async with user_session(api_engine, owner) as session:
        decision = await request_retry(session, key_id)

    assert decision.outcome is RetryOutcome.NOT_RETRYABLE


async def test_retry_for_a_missing_key_is_not_found(api_engine: AsyncEngine) -> None:
    """V-28 — รหัสที่ไม่มีอยู่ และของคนอื่น ได้คำตอบเดียวกัน"""
    owner = uuid4()
    await create_user(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        decision = await request_retry(session, uuid4())

    assert decision.outcome is RetryOutcome.NOT_FOUND
