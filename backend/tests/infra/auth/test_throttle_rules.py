"""ตัวนับอัตราการเรียก — V-40 ถึง V-45

**ตัวนับอยู่ในฐานข้อมูล** จึงนับร่วมกันข้ามกระบวนการ และ **การหน่วงบังคับข้ามคำขอ
ที่ยิงพร้อมกัน** ด้วยการล็อกแถว ไม่ใช่การตอบช้าทีละคำขอ
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth import (
    Bucket,
    claim,
    clear,
    count_failure,
    delay_after,
    key_of,
)
from tiewtrade.infra.auth.throttle import (
    ACCOUNT_FAILURES_BEFORE_DELAY,
    ACCOUNT_MAX_DELAY,
    IP_FAILURES_BEFORE_BLOCK,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _fresh_key() -> str:
    """คีย์ที่ไม่ซ้ำกับเทสต์อื่น — ตารางตัวนับใช้ร่วมกันทั้งชุด"""
    return key_of(uuid4().hex)


def test_the_delay_grows_and_then_stops_at_the_ceiling() -> None:
    """V-40 — หน่วงเพิ่มเป็นสองเท่าแต่ไม่เกินเพดาน และไม่ล็อกบัญชี

    เพดานมีไว้เพื่อให้คนกลั่นแกล้งหน่วงเจ้าของบัญชีได้มากสุดเท่านั้น ซึ่งยังกดหยุดบอทได้
    """
    assert delay_after(ACCOUNT_FAILURES_BEFORE_DELAY - 1, Bucket.ACCOUNT) == timedelta(0)
    assert delay_after(ACCOUNT_FAILURES_BEFORE_DELAY, Bucket.ACCOUNT) == timedelta(seconds=1)
    assert delay_after(ACCOUNT_FAILURES_BEFORE_DELAY + 2, Bucket.ACCOUNT) == timedelta(seconds=4)
    assert delay_after(ACCOUNT_FAILURES_BEFORE_DELAY + 20, Bucket.ACCOUNT) == ACCOUNT_MAX_DELAY


async def test_an_account_starts_being_delayed_after_the_threshold(
    auth_engine: AsyncEngine,
) -> None:
    """V-40 — ครั้งที่ 4 ยังไม่หน่วง ครั้งที่ 5 เริ่มหน่วง"""
    key = _fresh_key()
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        for _ in range(ACCOUNT_FAILURES_BEFORE_DELAY - 1):
            state = await count_failure(session, Bucket.ACCOUNT, key)
        assert state.next_allowed_at is None
        state = await count_failure(session, Bucket.ACCOUNT, key)
        assert state.next_allowed_at is not None
        assert state.blocked_at(datetime.now(UTC))


async def test_a_successful_login_clears_the_account_but_not_the_ip(
    auth_engine: AsyncEngine,
) -> None:
    """V-41 — ล้างตัวนับของบัญชี **แต่ไม่ล้างของ IP**

    ถ้าล้างของ IP ด้วย ผู้โจมตีใช้บัญชีตัวเองเข้าสู่ระบบสำเร็จเพื่อล้างตัวนับ
    แล้วเดาบัญชีอื่นต่อได้
    """
    account, address = _fresh_key(), _fresh_key()
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await count_failure(session, Bucket.ACCOUNT, account)
        await count_failure(session, Bucket.IP, address)
        await clear(session, Bucket.ACCOUNT, account)

        after_account = await claim(session, Bucket.ACCOUNT, account, now=datetime.now(UTC))
        after_ip = await claim(session, Bucket.IP, address, now=datetime.now(UTC))

    assert after_account.failures == 0
    assert after_ip.failures == 1


async def test_the_window_resets_the_counter_when_time_passes(auth_engine: AsyncEngine) -> None:
    """V-42 — ตัวนับหมดตามหน้าต่างเวลา โดยไม่ต้องรอจริง"""
    key = _fresh_key()
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await count_failure(session, Bucket.IP, key)
        later = datetime.now(UTC) + Bucket.IP.window + timedelta(seconds=1)
        state = await claim(session, Bucket.IP, key, now=later)
    assert state.failures == 0


async def test_an_ip_is_blocked_after_enough_failures(auth_engine: AsyncEngine) -> None:
    """V-42 — ถัง IP ปฏิเสธเมื่อครบเกณฑ์"""
    key = _fresh_key()
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        for _ in range(IP_FAILURES_BEFORE_BLOCK):
            state = await count_failure(session, Bucket.IP, key)
    assert state.blocked_at(datetime.now(UTC))


async def test_many_requests_at_once_create_exactly_one_bucket(auth_engine: AsyncEngine) -> None:
    """V-43.1 — ยิงพร้อมกันบนตารางว่างต้องได้ถังเดียว ไม่ใช่หลายแถวหรือข้อผิดพลาด

    `SELECT ... FOR UPDATE` ล็อกได้เฉพาะแถวที่มีอยู่ จึงใช้ `INSERT ... ON CONFLICT`
    เป็นตัวสร้างและล็อกในคำสั่งเดียว
    """
    key = _fresh_key()

    async def attempt() -> int:
        async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
            state = await count_failure(session, Bucket.ACCOUNT, key)
            return state.failures

    results = await asyncio.gather(*(attempt() for _ in range(10)))

    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        rows = (
            await session.execute(
                "SELECT failures FROM auth_throttle WHERE bucket_kind = :k AND bucket_key = :b",
                {"k": Bucket.ACCOUNT.value, "b": key},
            )
        ).all()

    assert len(rows) == 1, "ยิงพร้อมกันแล้วได้หลายแถว ซึ่งทำให้ตัวนับนับไม่ครบ"
    assert rows[0][0] == 10, f"นับได้ {rows[0][0]} ครั้งจาก 10 คำขอ"
    assert sorted(results) == list(range(1, 11))


async def test_two_engines_share_the_same_counter(auth_engine: AsyncEngine) -> None:
    """V-44 — ตัวนับอยู่ในฐานข้อมูล ไม่ใช่ในกระบวนการ

    ใช้ engine คนละตัวแทนสองกระบวนการ — ถ้าตัวนับอยู่ในหน่วยความจำของกระบวนการ
    ตัวที่สองจะเริ่มนับจากศูนย์ แล้วการเดารหัสผ่านก็หลบได้ด้วยการยิงไปอีกกระบวนการ
    """
    key = _fresh_key()
    other = create_engine_for(DatabaseRole.AUTH)
    try:
        async with presented_session(auth_engine, role=DatabaseRole.AUTH) as first:
            await count_failure(first, Bucket.ACCOUNT, key)
        async with presented_session(other, role=DatabaseRole.AUTH) as second:
            state = await count_failure(second, Bucket.ACCOUNT, key)
    finally:
        await other.dispose()
    assert state.failures == 2


async def test_the_counter_stores_hashes_not_the_values(auth_engine: AsyncEngine) -> None:
    """V-45 — ไม่มีอีเมลหรือ IP เป็นตัวอักษรอยู่ในตาราง"""
    email = "someone@example.com"
    key = key_of(email)
    assert email not in key
    assert len(key) == 64

    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await count_failure(session, Bucket.ACCOUNT, key)
        rows = (
            await session.execute(
                "SELECT bucket_key FROM auth_throttle WHERE bucket_key = :b", {"b": key}
            )
        ).all()
    assert rows[0][0] == key


async def test_claiming_a_bucket_twice_does_not_double_count(auth_engine: AsyncEngine) -> None:
    """การล็อกถังไม่ใช่การนับ — นับเฉพาะเมื่อเรียก `count_failure`"""
    key = _fresh_key()
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await claim(session, Bucket.ACCOUNT, key, now=NOW)
        state = await claim(session, Bucket.ACCOUNT, key, now=NOW)
    assert state.failures == 0
