"""ความลับต้องไม่หลุด — V-50 ถึง V-54

บทเรียนจาก F-35: ไลบรารีที่เราใช้เขียน log ของตัวเองได้ การตรวจจึงต้องดู **ของที่
ออกไปจริง** ทั้ง log, traceback และบันทึกที่ลบไม่ได้ ไม่ใช่ดูแค่โค้ดของเรา
"""

from __future__ import annotations

import logging
import traceback
from typing import Final

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import GOOD_PASSWORD, csrf_headers, register, unique_email
from tiewtrade.infra.auth import hash_password, password_matches
from tiewtrade.infra.auth.hashing import StoredHashUnreadableError
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session

#: รหัสผ่านที่ใช้ทดสอบว่าไม่หลุด — ไม่ซ้ำกับค่าอื่นเพื่อให้ค้นเจอแน่ถ้าหลุด
TELLTALE: Final[str] = "ค่าที่ต้องไม่โผล่ที่ไหนเลย-9f3a"


def test_nothing_secret_appears_in_the_log_or_the_body(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """V-51 — รหัสผ่าน โทเคน และ cookie ต้องไม่อยู่ใน log หรือในคำตอบ"""
    email = unique_email()
    with caplog.at_level(logging.DEBUG):
        created = client.post(
            "/auth/register",
            json={"email": email, "password": TELLTALE + "ยาวพอ"},
            headers=csrf_headers(client),
        )
        failed = client.post(
            "/auth/login",
            json={"email": email, "password": "ผิดแน่ ๆ ยาวพอสมควร"},
            headers=csrf_headers(client),
        )

    written = caplog.text + created.text + failed.text
    assert TELLTALE not in written
    assert "password" not in written.lower()
    for cookie in client.cookies.values():
        assert str(cookie) not in caplog.text


def test_a_failing_request_does_not_leak_through_the_traceback(client: TestClient) -> None:
    """V-51 — traceback ของกรณีล้มเหลวต้องไม่พารหัสผ่านไปด้วย

    `raise ... from` เก็บ exception ต้นทางไว้ ซึ่ง `caplog` มองไม่เห็นแต่คนอ่าน
    traceback เห็น — บทเรียนจาก F-35
    """
    email = register(client)
    try:
        client.post(
            "/auth/password",
            json={"current_password": TELLTALE, "new_password": TELLTALE + "ใหม่"},
            headers=csrf_headers(client),
        )
    except Exception as error:  # pragma: no cover - ไม่ควรมีข้อผิดพลาดหลุดมาถึงที่นี่
        written = "".join(traceback.format_exception(error))
        assert TELLTALE not in written
        raise

    assert email


async def test_the_database_never_receives_the_token_itself(client: TestClient) -> None:
    """V-53 — ฐานข้อมูลเก็บแต่แฮช ไม่เคยได้รับโทเคนจริง"""
    register(client)
    token = str(client.cookies.get("tiewtrade_session", ""))
    assert token

    engine = create_engine_for(DatabaseRole.API)
    try:
        async with presented_session(engine, token_hash=token, role=DatabaseRole.API) as session:
            rows = (await session.execute("SELECT count(*) FROM sessions")).one()
    finally:
        await engine.dispose()
    assert rows[0] == 0, "โทเคนจริงใช้ค้นหา session ได้ ซึ่งแปลว่าฐานข้อมูลเก็บค่าดิบ"


def test_a_broken_stored_hash_is_told_apart_from_a_wrong_password() -> None:
    """V-54 — ข้อผิดพลาดของการแฮชไม่พารหัสผ่านออกมา และแยกจาก "รหัสผ่านผิด" """
    with pytest.raises(StoredHashUnreadableError) as caught:
        password_matches("ไม่ใช่แฮชของ argon2", TELLTALE)
    message = str(caught.value) + "".join(traceback.format_exception(caught.value))
    assert TELLTALE not in message

    assert not password_matches(hash_password(GOOD_PASSWORD), TELLTALE)


def test_the_response_of_a_successful_login_carries_only_the_user_id(client: TestClient) -> None:
    """V-50 (ฝั่ง API) — คำตอบไม่พาอีเมลหรืออะไรที่ไม่จำเป็นไปด้วย (RQ-10)

    F-06 เพิ่ม `totp_enabled` **เพราะหน้าเว็บต้องรู้ว่าจะแสดงปุ่มเปิดหรือปิด**
    และเพราะ F-24 ต้องถามคำถามนี้ได้ (RQ-12) — เป็นค่าจริงเท็จที่ไม่ระบุตัวบุคคล
    ฉะนั้นข้อห้ามเดิมยังอยู่ครบ: ไม่มีอีเมล ไม่มีโทเคน ไม่มีแฮช
    """
    email = register(client)
    body = client.get("/auth/me").json()
    assert set(body) == {"user_id", "totp_enabled"}
    assert email not in str(body)
