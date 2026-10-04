"""ตัวนับการเดาต้องรอดแม้คำขอถูกปฏิเสธ — V-63 ถึง V-69

เทสต์กลุ่มนี้ยิงผ่าน HTTP จริง **เพราะข้อบกพร่องที่มันจับอยู่ตรงรอยต่อระหว่าง
เส้นทางกับ transaction ไม่ได้อยู่ในกฎของถัง** เทสต์ของ F-05
(`tests/infra/auth/test_throttle_rules.py`) เรียก `count_failure()` ตรง ๆ บน
session ที่ commit ตามปกติ จึงเขียวเสมอและมองข้อนี้ไม่เห็นเลย

สิ่งที่พิสูจน์: การปฏิเสธคำขอเป็น **ผลลัพธ์ปกติ** ของเส้นทางยืนยันตัวตน
ไม่ใช่ความล้มเหลวของ transaction · ส่วนความผิดพลาดของระบบยังต้องย้อนตามเดิม
(F-06 `plan.md` หัวข้อ 2 · `validation.md` หัวข้อ 1.12)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import GOOD_PASSWORD, csrf_headers, register, unique_email
from tiewtrade.infra.auth import Bucket, key_of
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session
from tiewtrade.services.api.throttling import AuthRejectedError, throttled

_FAILURES = """
SELECT failures
FROM auth_throttle
WHERE bucket_kind = :kind AND bucket_key = :key
"""


async def failures_now(engine: AsyncEngine, bucket: Bucket, key: str) -> int:
    """จำนวนครั้งที่ฐานข้อมูลบันทึกไว้จริง — ไม่มีแถวนับเป็นศูนย์"""
    async with presented_session(engine, role=DatabaseRole.AUTH) as session:
        row = (await session.execute(_FAILURES, {"kind": bucket.value, "key": key})).one_or_none()
        return 0 if row is None else int(next(iter(row)))


def failures_recorded(bucket: Bucket, key: str) -> int:
    """เหมือน `failures_now` แต่เรียกได้จากเทสต์ที่ไม่ใช่ async

    สร้าง engine ของตัวเองแล้วปล่อยทิ้ง เหมือน `_clear_throttle` ใน `conftest.py`
    เพราะ engine ของแอปอยู่บน event loop ของ `TestClient` ซึ่งใช้ร่วมกันไม่ได้
    """

    async def read() -> int:
        engine = create_engine_for(DatabaseRole.AUTH)
        try:
            return await failures_now(engine, bucket, key)
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest_asyncio.fixture
async def auth_engine() -> AsyncIterator[AsyncEngine]:
    """engine ของบทบาท `auth` สำหรับเทสต์ที่เรียก `throttled()` ตรง ๆ"""
    engine = create_engine_for(DatabaseRole.AUTH)
    try:
        yield engine
    finally:
        await engine.dispose()


def test_a_wrong_password_is_counted(client: TestClient) -> None:
    """V-63 — **เข้าสู่ระบบที่รหัสผ่านผิดต้องถูกนับ** ไม่ใช่หายไปพร้อม transaction

    นี่คือข้อบกพร่องของ F-05 ที่พบตอนเขียนแผนของ F-06: เส้นทางนับแล้วจึงโยน
    `HTTPException` **ข้างใน** `throttled()` ซึ่งอยู่ใน transaction ที่ย้อนทุกอย่าง
    เมื่อมีข้อผิดพลาดหลุดออกมา ผลคือการเดารหัสผ่านไม่ถูกนับเลย
    """
    email = register(client)

    refused = client.post(
        "/auth/login",
        json={"email": email, "password": "ไม่ใช่รหัสผ่านของบัญชีนี้เลย"},
        headers=csrf_headers(client),
    )
    assert refused.status_code == 401

    assert failures_recorded(Bucket.ACCOUNT, key_of(email)) == 1


def test_a_wrong_password_on_an_unknown_email_is_counted(client: TestClient) -> None:
    """V-63 — บัญชีที่ไม่มีอยู่ก็ต้องถูกนับ มิฉะนั้นเดาอีเมลได้ฟรีไม่จำกัด"""
    missing = unique_email()

    refused = client.post(
        "/auth/login",
        json={"email": missing, "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert refused.status_code == 401

    assert failures_recorded(Bucket.ACCOUNT, key_of(missing)) == 1


def test_wrong_passwords_add_up_across_requests(client: TestClient) -> None:
    """V-63 — นับสะสมข้ามคำขอ ไม่ใช่ค้างที่หนึ่ง"""
    email = register(client)

    for _ in range(3):
        client.post(
            "/auth/login",
            json={"email": email, "password": "ไม่ใช่รหัสผ่านของบัญชีนี้เลย"},
            headers=csrf_headers(client),
        )

    assert failures_recorded(Bucket.ACCOUNT, key_of(email)) == 3


def test_a_duplicate_sign_up_is_counted(client: TestClient) -> None:
    """V-64 — **สมัครที่ชนอีเมลเดิมต้องถูกนับ**

    เส้นทางสมัครนับแล้วโยน 409 ข้างใน guard เหมือนกัน จึงมีอาการเดียวกัน
    และโควตาการสมัครต่อ IP ที่ `security.md` หัวข้อ 3 สั่งไว้จึงไม่ทำงาน
    """
    email = register(client)
    before = failures_recorded(Bucket.SIGNUP_IP, key_of("testclient"))

    clash = client.post(
        "/auth/register",
        json={"email": email, "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert clash.status_code == 409

    assert failures_recorded(Bucket.SIGNUP_IP, key_of("testclient")) == before + 1


def test_a_successful_login_still_clears_the_account_bucket(client: TestClient) -> None:
    """สมบัติเดิมของ F-05 ต้องไม่เสียไปจากการแก้ — เข้าสำเร็จล้างถังของบัญชี

    `clear()` ล้างเฉพาะถังของบัญชี ไม่ล้างถังของ IP (บทเรียนรีวิว 2026-10-02)
    """
    email = register(client)
    client.post(
        "/auth/login",
        json={"email": email, "password": "ไม่ใช่รหัสผ่านของบัญชีนี้เลย"},
        headers=csrf_headers(client),
    )
    assert failures_recorded(Bucket.ACCOUNT, key_of(email)) == 1

    ok = client.post(
        "/auth/login",
        json={"email": email, "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert ok.status_code == 200
    assert failures_recorded(Bucket.ACCOUNT, key_of(email)) == 0


async def test_a_bug_in_the_middle_still_rolls_the_counter_back(auth_engine: AsyncEngine) -> None:
    """V-68 — **ความผิดพลาดของระบบยังย้อนตามเดิม** การแก้ต้องไม่กลายเป็น commit ทุกกรณี

    ถ้าจับข้อผิดพลาดกว้างเกินไป สิ่งที่เขียนไว้ก่อนจุดที่พังจะถูก commit ทั้งที่
    คำขอนั้นไม่ได้จบอย่างที่ควร
    """
    key = key_of(unique_email())

    with pytest.raises(RuntimeError):
        async with throttled(auth_engine, [(Bucket.ACCOUNT, key)], now=datetime.now(UTC)) as guard:
            await guard.count_attempt()
            raise RuntimeError("ฐานข้อมูลล่มกลางทาง")

    assert await failures_now(auth_engine, Bucket.ACCOUNT, key) == 0


async def test_a_server_error_still_rolls_the_counter_back(auth_engine: AsyncEngine) -> None:
    """V-68 — **`HTTPException` ที่เป็น 500 ก็ต้องย้อน** ไม่ใช่ถูกนับว่าเป็นการปฏิเสธ

    นี่คือเหตุที่แยกชนิด `AuthRejectedError` ออกมา แทนการจับ `HTTPException` ทุกชนิด
    ซึ่งจะ commit ตอนระบบพังด้วย
    """
    key = key_of(unique_email())

    with pytest.raises(HTTPException):
        async with throttled(auth_engine, [(Bucket.ACCOUNT, key)], now=datetime.now(UTC)) as guard:
            await guard.count_attempt()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "ภายในพัง")

    assert await failures_now(auth_engine, Bucket.ACCOUNT, key) == 0


async def test_a_rejection_keeps_the_counter(auth_engine: AsyncEngine) -> None:
    """คู่ตรงข้ามของ V-68 — การปฏิเสธตามกฎเก็บตัวนับไว้ และโยนชนิดเดิมต่อ

    `throttled()` ไม่แปลงชนิดเอง — ตัวแปลงเป็นคำตอบอยู่ที่ `app.py` ที่เดียว
    """
    key = key_of(unique_email())

    with pytest.raises(AuthRejectedError) as raised:
        async with throttled(auth_engine, [(Bucket.ACCOUNT, key)], now=datetime.now(UTC)) as guard:
            await guard.count_attempt()
            raise AuthRejectedError(status.HTTP_401_UNAUTHORIZED, "ไม่ถูกต้อง")

    assert raised.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert raised.value.detail == "ไม่ถูกต้อง"
    assert raised.value.as_http_exception().status_code == status.HTTP_401_UNAUTHORIZED
    assert await failures_now(auth_engine, Bucket.ACCOUNT, key) == 1


async def test_many_requests_at_once_do_not_all_get_through(auth_engine: AsyncEngine) -> None:
    """V-69 — **ล็อกยังถูกถือไว้ตลอดช่วงที่ตรวจ** ยิงพร้อมกันต้องไม่ผ่านด่านทั้งหมด

    สมบัติเดิมของ F-05 ที่การแก้ตัวนับต้องไม่ทำให้เสียไป: ถ้าปล่อยล็อกก่อนตรวจ
    ทุกคำขอจะเห็นถังว่างแล้วผ่านด่านไปพร้อมกันหมด
    """
    key = key_of(unique_email())
    now = datetime.now(UTC)

    async def attempt() -> bool:
        async with throttled(auth_engine, [(Bucket.ACCOUNT, key)], now=now) as guard:
            if guard.blocked:
                return False
            await guard.count_attempt()
            return True

    results = await asyncio.gather(*(attempt() for _ in range(20)))

    assert not all(results), "ยิง 20 คำขอพร้อมกันแล้วผ่านด่านทั้งหมด — ล็อกไม่ทำงาน"
    assert await failures_now(auth_engine, Bucket.ACCOUNT, key) == sum(results)
