"""งานเก็บกวาด — และกฎเดียวที่ห้ามละเมิดของมัน

**ห้ามลบแถวที่ยังมีผลจำกัดการเดา** (เงื่อนไขของการอนุมัติ 2026-10-03)
ครึ่งหนึ่งของเทสต์ที่นี่พิสูจน์ว่า **ไม่ได้ลบ** ซึ่งสำคัญกว่าการพิสูจน์ว่าลบได้ —
การเก็บกวาดที่ลบมากเกินไปคือการยกเลิกการคุมอัตราให้ผู้โจมตีฟรี ๆ
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import fresh_bucket_key, make_account
from tiewtrade.infra.auth import challenges
from tiewtrade.infra.auth.cleanup import sweep
from tiewtrade.infra.auth.throttle import (
    ACCOUNT_FAILURES_BEFORE_DELAY,
    SECOND_FACTOR_CAPACITY,
    SECOND_FACTOR_REFILL,
    Bucket,
    claim,
    count_failure,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import presented_session, user_session


#: คีย์ของถังต้องเป็นแฮช 64 ตัวอักษรตาม `CHECK` ของตาราง
async def rows_of(engine: AsyncEngine, bucket: Bucket, key: str) -> int:
    """จำนวนแถวของถังนั้นที่ยังอยู่"""
    async with presented_session(engine, role=DatabaseRole.AUTH) as session:
        found = (
            await session.execute(
                "SELECT 1 FROM auth_throttle WHERE bucket_kind = :k AND bucket_key = :b",
                {"k": bucket.value, "b": key},
            )
        ).all()
    return len(found)


async def swept_at(engine: AsyncEngine, now: datetime) -> None:
    """เก็บกวาดหนึ่งรอบที่เวลานั้น"""
    async with presented_session(engine, role=DatabaseRole.AUTH) as session:
        await sweep(session, now=now)


async def test_a_delaying_bucket_is_never_swept(auth_engine: AsyncEngine) -> None:
    """**ห้ามลบถังที่ยังหน่วงอยู่** — ลบแล้วเท่ากับยกเลิกการหน่วงให้ผู้โจมตี"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.ACCOUNT, key, now=now)
        for _ in range(ACCOUNT_FAILURES_BEFORE_DELAY + 1):
            state = await count_failure(session, Bucket.ACCOUNT, key)
    assert state.next_allowed_at is not None, "ยังไม่ถึงเกณฑ์หน่วง เทสต์จึงยังไม่ได้ทดสอบอะไร"

    # เก็บกวาดโดยที่หน้าต่างผ่านไปแล้ว **แต่เวลาที่ต้องรอยังไม่ถึง**
    await swept_at(auth_engine, state.next_allowed_at - timedelta(seconds=1))

    assert await rows_of(auth_engine, Bucket.ACCOUNT, key) == 1


async def test_a_bucket_inside_its_window_is_never_swept(auth_engine: AsyncEngine) -> None:
    """**ห้ามลบถังที่หน้าต่างยังไม่ผ่าน** — ตัวนับในหน้าต่างนั้นยังมีผล"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.ACCOUNT, key, now=now)
        await count_failure(session, Bucket.ACCOUNT, key)

    await swept_at(auth_engine, now + Bucket.ACCOUNT.window - timedelta(seconds=1))

    assert await rows_of(auth_engine, Bucket.ACCOUNT, key) == 1


async def test_a_bucket_past_its_window_is_swept(auth_engine: AsyncEngine) -> None:
    """หน้าต่างผ่านแล้วและไม่มีเวลาที่ต้องรอ → แถวนั้นให้ผลเท่ากับไม่มีแถว จึงลบได้"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.ACCOUNT, key, now=now)
        await count_failure(session, Bucket.ACCOUNT, key)

    await swept_at(auth_engine, now + Bucket.ACCOUNT.window + timedelta(seconds=1))

    assert await rows_of(auth_engine, Bucket.ACCOUNT, key) == 0


async def test_a_token_bucket_with_a_deficit_is_never_swept(auth_engine: AsyncEngine) -> None:
    """**ห้ามลบถังเติมคืนที่โควตายังไม่เต็ม** — มันยังจำกัดการเดาอยู่

    นี่คือกรณีที่พลาดง่ายที่สุด เพราะถังที่โควตาเหลือศูนย์ดู "เก่า" แต่มันคือถังที่
    กำลังทำงานหนักที่สุด
    """
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.TOTP_ACCOUNT, key, now=now)
        for _ in range(SECOND_FACTOR_CAPACITY):
            state = await count_failure(session, Bucket.TOTP_ACCOUNT, key)
    assert state.tokens_left == 0, "โควตายังไม่หมด เทสต์จึงยังไม่ได้ทดสอบอะไร"

    # เวลาผ่านไปพอเติมคืนได้บางส่วน แต่ยังไม่เต็ม
    await swept_at(auth_engine, now + SECOND_FACTOR_REFILL * (SECOND_FACTOR_CAPACITY - 1))

    assert await rows_of(auth_engine, Bucket.TOTP_ACCOUNT, key) == 1


async def test_a_fully_refilled_token_bucket_is_swept(auth_engine: AsyncEngine) -> None:
    """เวลาผ่านไปพอเติมคืนจนเต็ม → แถวนั้นให้ผลเท่ากับไม่มีแถว จึงลบได้"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.TOTP_ACCOUNT, key, now=now)
        for _ in range(SECOND_FACTOR_CAPACITY):
            await count_failure(session, Bucket.TOTP_ACCOUNT, key)

    # บวกหนึ่งวินาทีเพราะ `refilled_at` มาจากนาฬิกาของฐานข้อมูล ซึ่งช้ากว่านาฬิกา
    # ของเทสต์ได้เสี้ยววินาที — เทสต์ที่แดงสุ่มแย่กว่าเทสต์ที่เผื่อขอบไว้
    await swept_at(
        auth_engine,
        now + SECOND_FACTOR_REFILL * SECOND_FACTOR_CAPACITY + timedelta(seconds=1),
    )

    assert await rows_of(auth_engine, Bucket.TOTP_ACCOUNT, key) == 0


async def test_an_expired_challenge_is_swept_across_users(auth_engine: AsyncEngine) -> None:
    """เก็บกวาด challenge ที่หมดอายุ **ข้ามผู้ใช้** — ของที่ไม่มีใครเก็บได้ค้างตลอดไป"""
    first, _ = await make_account(auth_engine)
    second, _ = await make_account(auth_engine)
    now = datetime.now(UTC)
    long_ago = now - challenges.CHALLENGE_LIFETIME - timedelta(seconds=1)

    for account in (first, second):
        async with user_session(auth_engine, account, role=DatabaseRole.AUTH) as session:
            await challenges.issue(session, credential_updated_at=now, now=long_ago)

    await swept_at(auth_engine, now)

    for account in (first, second):
        async with user_session(auth_engine, account, role=DatabaseRole.AUTH) as session:
            assert (await session.execute("SELECT 1 FROM login_challenges")).all() == []


async def test_a_live_challenge_is_never_swept(auth_engine: AsyncEngine) -> None:
    """**ห้ามลบ challenge ที่ยังใช้ได้** — ผู้ใช้ที่กำลังกรอกรหัสจะถูกเตะออกกลางทาง"""
    account, _ = await make_account(auth_engine)
    now = datetime.now(UTC)

    async with user_session(auth_engine, account, role=DatabaseRole.AUTH) as session:
        issued = await challenges.issue(session, credential_updated_at=now, now=now)

    await swept_at(auth_engine, now)

    async with presented_session(
        auth_engine, token_hash=issued.token_hash, role=DatabaseRole.AUTH
    ) as presented:
        assert await challenges.presented(presented) is not None


async def test_the_sweep_policy_cannot_delete_a_live_challenge_of_another_user(
    auth_engine: AsyncEngine,
) -> None:
    """policy ของการเก็บกวาดแคบจริง — ลบแถวที่ยังไม่หมดอายุของคนอื่นไม่ได้

    ตรวจที่ระดับฐานข้อมูล ไม่ใช่เชื่อว่าโค้ดเก็บกวาดเขียนเงื่อนไขถูก
    """
    owner, _ = await make_account(auth_engine)
    stranger, _ = await make_account(auth_engine)
    now = datetime.now(UTC)
    async with user_session(auth_engine, owner, role=DatabaseRole.AUTH) as session:
        issued = await challenges.issue(session, credential_updated_at=now, now=now)

    async with user_session(auth_engine, stranger, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "DELETE FROM login_challenges WHERE token_hash = :token",
            {"token": issued.token_hash},
        )

    async with presented_session(
        auth_engine, token_hash=issued.token_hash, role=DatabaseRole.AUTH
    ) as presented:
        assert await challenges.presented(presented) is not None, "คนอื่นลบ challenge ที่ยังใช้ได้ได้"


async def test_sweeping_counts_what_it_removed(auth_engine: AsyncEngine) -> None:
    """รายงานจำนวนที่ลบ เพื่อให้คนที่สั่งงานเห็นว่ามันทำอะไรจริง"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.ACCOUNT, key, now=now)

    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        swept = await sweep(session, now=now + Bucket.ACCOUNT.window + timedelta(seconds=1))

    assert swept.throttle_rows >= 1
    assert swept.total == swept.throttle_rows + swept.challenge_rows


@pytest.mark.parametrize(
    "bucket", [b for b in Bucket if b.table == "auth_throttle"], ids=lambda bucket: bucket.value
)
async def test_every_bucket_kind_is_covered(auth_engine: AsyncEngine, bucket: Bucket) -> None:
    """ทุกชนิดถังต้องถูกเก็บกวาด — **ชนิดใหม่ที่ลืมเติมจะค้างตลอดไปแบบเงียบ ๆ**

    เทสต์นี้เดินรายการชนิดจริง ฉะนั้นการเพิ่มชนิดถังในอนาคตโดยไม่คิดเรื่องการเก็บกวาด
    จะแดงที่นี่
    """
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, bucket, key, now=now)
    assert await rows_of(auth_engine, bucket, key) == 1

    # ไกลพอให้ทุกชนิดหมดผล: หน้าต่างที่ยาวที่สุดคือหนึ่งชั่วโมง และการเติมคืนเต็ม
    # ใช้เวลาเท่าความจุคูณช่วงเติม
    await swept_at(auth_engine, now + timedelta(days=1))

    assert await rows_of(auth_engine, bucket, key) == 0


@pytest.mark.parametrize(
    "bucket", [b for b in Bucket if b.table == "api_throttle"], ids=lambda bucket: bucket.value
)
async def test_every_api_bucket_kind_is_covered(api_engine: AsyncEngine, bucket: Bucket) -> None:
    """ถังของ F-07 ก็ต้องถูกเก็บกวาด — **คนละตารางคนละบทบาท แต่กฎเดียวกัน**

    ถ้าชนิดใหม่ถูกเพิ่มในตารางของ `api` แล้วไม่มีใครเก็บกวาด แถวจะค้างตลอดไป
    แบบเงียบ ๆ เหมือนกับที่หนี้ของ `auth_throttle` เคยเป็น
    """
    from uuid import uuid4

    from tiewtrade.infra.auth.cleanup import sweep_api_buckets
    from tiewtrade.infra.users import create_user

    owner = uuid4()
    await create_user(api_engine, owner)
    key = fresh_bucket_key()
    now = datetime.now(UTC)

    async with user_session(api_engine, owner) as session:
        await claim(session, bucket, key, now=now)
        found = (
            await session.execute(
                "SELECT 1 FROM api_throttle WHERE bucket_kind = :k AND bucket_key = :b",
                {"k": bucket.value, "b": key},
            )
        ).all()
    assert len(found) == 1

    async with user_session(api_engine, owner) as session:
        await sweep_api_buckets(session, now=now + timedelta(days=1))

    async with user_session(api_engine, owner) as session:
        left = (
            await session.execute(
                "SELECT 1 FROM api_throttle WHERE bucket_kind = :k AND bucket_key = :b",
                {"k": bucket.value, "b": key},
            )
        ).all()
    assert left == []
