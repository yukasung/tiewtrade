"""เส้นทางจัดการ API key — V-4, V-23 ถึง V-31 (F-07)

**เรียกผ่าน HTTP เหมือนหน้าเว็บจริง** เพราะสิ่งที่ต้องพิสูจน์คือพฤติกรรมของเส้นทาง
รวมถึง middleware ที่บังคับการยืนยันซ้ำ ซึ่งการเรียกฟังก์ชันตรง ๆ ข้ามไปทั้งหมด
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from tests.api.conftest import GOOD_PASSWORD, csrf_headers, database_url_present, register
from tests.api.test_totp_flow import code_now, enable_totp
from tiewtrade.infra.api_keys import MAX_KEYS_PER_USER
from tiewtrade.infra.auth.throttle import API_KEY_RETRY_CAPACITY
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.api.settings import TOTP_HEADER

pytestmark = pytest.mark.skipif(not database_url_present(), reason="ต้องมีฐานข้อมูล")

KEY = "PUBLICKEY000000ABCD"
SECRET = "secret-that-must-never-come-back"


def _add(client: TestClient, secret_value: bytes, *, label: str = "หลัก") -> Response:
    """เพิ่ม key หนึ่งใบพร้อมยืนยันปัจจัยที่สอง

    **ใช้รหัสของช่วงปัจจุบัน** เพราะ `enable_totp` ใช้รหัสของช่วงก่อนหน้าไปแล้ว
    และ RQ-4 ของ F-06 ห้ามใช้รหัสซ้ำตลอดช่วงที่ยังถูกยอมรับ

    **ฉะนั้นเพิ่ม key ได้ครั้งเดียวต่อช่วงเวลา** ซึ่งเป็นข้อกำหนดที่ถูกต้อง
    (ไม่มีช่วงผ่อนผันของการยืนยันซ้ำ — เจ้าของตัดสิน 2026-10-03) เทสต์ที่ต้องมี
    key หลายใบจึงใส่แถวผ่านชั้นเก็บโดยตรง แล้วเดินเส้นทางเฉพาะใบที่กำลังพิสูจน์
    """
    answer: Response = client.post(
        "/api-keys",
        json={"label": label, "key": KEY, "secret": SECRET},
        headers=csrf_headers(client) | {TOTP_HEADER: code_now(secret_value)},
    )
    return answer


def _user_id(client: TestClient) -> UUID:
    """รหัสผู้ใช้ของ session ปัจจุบัน"""
    answer = client.get("/auth/me")
    assert answer.status_code == 200, answer.text
    return UUID(answer.json()["user_id"])


def _seed_keys(user_id: UUID, count: int) -> None:
    """ใส่ key ผ่านชั้นเก็บโดยตรง — ใช้เมื่อเทสต์ต้องมีหลายใบ

    **ไม่ได้ข้ามกฎใด** ชั้นนี้คือสิ่งที่เส้นทางเรียกอยู่แล้ว ส่วนที่ข้ามคือการยืนยัน
    ปัจจัยที่สอง ซึ่งมีเทสต์ของตัวเองอยู่แล้วและใช้รหัสได้ครั้งเดียวต่อช่วงเวลา
    """
    import asyncio

    from tiewtrade.infra.api_keys import store_key
    from tiewtrade.infra.crypto import KeyPurpose, KeySource
    from tiewtrade.infra.db.session import user_session

    async def run() -> None:
        engine = create_engine_for(DatabaseRole.API)
        keys = KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)
        try:
            for index in range(count):
                async with user_session(engine, user_id) as session:
                    await store_key(
                        session,
                        keys,
                        user_id=user_id,
                        label=f"seeded-{index}",
                        key_public=KEY,
                        secret=SECRET,
                    )
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(run())


def test_adding_a_key_requires_the_second_factor(client: TestClient) -> None:
    """V-23 — ไม่ส่งรหัส → ถูกปฏิเสธ ไม่ใช่เพิ่มสำเร็จ"""
    register(client)
    enable_totp(client)

    refused = client.post(
        "/api-keys",
        json={"label": "หลัก", "key": KEY, "secret": SECRET},
        headers=csrf_headers(client),
    )

    assert refused.status_code == 403, refused.text


def test_an_account_without_a_second_factor_cannot_add_a_key(client: TestClient) -> None:
    """V-25 — บัญชีที่ยังไม่เปิด TOTP เพิ่ม key ไม่ได้

    ผลที่ยอมรับแล้วของ RQ-7.1 — หน้าเว็บต้องบอกทางออก ไม่ใช่ขึ้นข้อผิดพลาดกลาง ๆ
    """
    register(client)

    refused = client.post(
        "/api-keys",
        json={"label": "หลัก", "key": KEY, "secret": SECRET},
        headers=csrf_headers(client) | {TOTP_HEADER: "000000"},
    )

    assert refused.status_code == 403, refused.text


def test_adding_a_key_then_listing_it_shows_only_the_last_four_digits(
    client: TestClient,
) -> None:
    """V-4, Q-5 — คำตอบไม่มี secret และไม่มี key เต็ม"""
    register(client)
    secret, _ = enable_totp(client)

    added = _add(client, secret)
    assert added.status_code == 201, added.text

    listed = client.get("/api-keys")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 1
    assert body[0]["public_tail"] == "ABCD"
    assert body[0]["status"] == "PENDING"

    everything = listed.text + added.text
    assert SECRET not in everything
    assert KEY not in everything


def test_no_route_hands_back_the_secret(client: TestClient) -> None:
    """V-4 — เดินทุกเส้นทางของ key แล้วต้องไม่มีคำตอบไหนพาความลับออกมา"""
    register(client)
    secret, _ = enable_totp(client)
    added = _add(client, secret)
    key_id = added.json()["id"]

    answers = [
        client.get("/api-keys").text,
        client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client)).text,
        client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client)).text,
    ]

    for answer in answers:
        assert SECRET not in answer
        assert KEY not in answer


def test_the_cap_is_enforced_through_the_route(client: TestClient) -> None:
    """V-29 — เกินเพดานแล้วเส้นทางปฏิเสธด้วยรหัสที่ถูกต้อง"""
    register(client)
    secret, _ = enable_totp(client)
    _seed_keys(_user_id(client), MAX_KEYS_PER_USER)

    refused = _add(client, secret, label="เกิน")

    assert refused.status_code == 409, refused.text


def test_pressing_retry_too_fast_is_refused(client: TestClient) -> None:
    """V-30 — ถังของการกดลองใหม่ทำงานจริงผ่านเส้นทาง (RQ-11)

    ใช้ปุ่มลองใหม่พิสูจน์เรื่องนี้เพราะมันไม่ต้องยืนยันซ้ำ จึงกดติดกันได้จริง
    ส่วนถังของการเพิ่ม key ใช้ตรรกะเดียวกันและมีเทสต์ของชั้นถังเอง
    """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    seen = [
        client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client)).status_code
        for _ in range(API_KEY_RETRY_CAPACITY + 2)
    ]

    assert 429 in seen, seen


def test_a_retry_on_a_pending_key_is_refused(client: TestClient) -> None:
    """Q-7 — ปุ่มลองใหม่มีเฉพาะแถวที่ตรวจไม่ได้ชั่วคราว"""
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    refused = client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client))

    assert refused.status_code == 409, refused.text


def test_retrying_needs_no_second_factor(client: TestClient) -> None:
    """V-26 — กดลองใหม่ไม่ต้องยืนยันซ้ำ (เจ้าของตัดสิน 2026-10-04)

    ที่พิสูจน์คือ **ไม่ถูกปฏิเสธเพราะไม่ได้ยืนยันซ้ำ** — คำตอบจะเป็น 409 เพราะสถานะ
    ยังเป็น "กำลังตรวจ" ซึ่งเป็นคนละเรื่องกับการยืนยันตัวตน
    """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    answer = client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client))

    assert answer.status_code != 403, answer.text


def test_another_users_key_is_not_found(client: TestClient) -> None:
    """V-28 — ลบของคนอื่นได้ "ไม่พบ" ไม่ใช่ "ไม่มีสิทธิ์" """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    client.post("/auth/logout", headers=csrf_headers(client))
    client.get("/auth/csrf")
    register(client, password=GOOD_PASSWORD)

    answer = client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client))

    assert answer.status_code == 404, answer.text


def test_deleting_own_key_works(client: TestClient) -> None:
    """V-12 — ลบของตัวเองได้ และหายจากรายการ"""
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    deleted = client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client))

    assert deleted.status_code == 204, deleted.text
    assert client.get("/api-keys").json() == []
