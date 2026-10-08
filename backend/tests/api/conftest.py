"""เครื่องมือร่วมของเทสต์เส้นทางยืนยันตัวตน (F-05)

ใช้ฐานข้อมูลจริงเหมือนเทสต์ของ F-03 และ F-04 เพราะสิ่งที่ต้องพิสูจน์คือ
**ฐานข้อมูลปฏิเสธเอง** ไม่ใช่โค้ดเลี่ยงไม่ทำ (validation V-1, V-2, V-7)
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Final
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session
from tiewtrade.services.api.app import app
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER

#: รหัสผ่านที่ผ่านกฎทุกข้อและไม่อยู่ในรายการที่ห้าม
GOOD_PASSWORD: Final[str] = "รหัสผ่านที่ยาวพอใช้งานจริง"


@pytest.fixture(autouse=True)
def _api_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """เปิดการสมัครและปิดธง `Secure` เฉพาะในเทสต์

    ปิดธง `Secure` เพราะไคลเอนต์ของเทสต์ใช้ `http://` จึงไม่ส่ง cookie ที่มีธงนั้นกลับมา
    ค่าเริ่มต้นของจริงยังเป็นเปิด และมีเทสต์แยกยืนยัน (V-21)
    """
    monkeypatch.setenv("TIEWTRADE_PRICE_ORIGINS", "http://localhost:5173")
    # Preserve CI/explicit role credentials and database selection. Only supply a
    # local default when no API endpoint was configured by the test environment.
    monkeypatch.setenv(
        "TIEWTRADE_REDIS_URL_API",
        os.environ.get(
            "TIEWTRADE_REDIS_URL_API",
            os.environ.get("TIEWTRADE_TEST_REDIS_URL", "redis://127.0.0.1:56379/0"),
        ),
    )
    monkeypatch.setenv("TIEWTRADE_SIGNUP_OPEN", "1")
    monkeypatch.setenv("TIEWTRADE_COOKIE_SECURE", "0")


@pytest_asyncio.fixture(autouse=True)
async def _clear_throttle() -> None:
    """ล้างตัวนับอัตราการเรียกก่อนทุกเทสต์

    โควตาการสมัครต่อ IP เป็นกฎจริงที่ต้องคงไว้ (5 ครั้ง/ชั่วโมง) แต่เทสต์ทุกข้อ
    มาจาก IP เดียวกัน จึงต้องล้างสภาพเหมือนที่ล้างสภาพอื่นของฐานข้อมูล
    **ไม่ใช่ปิดกฎหรือเพิ่มเพดานให้หลวมเฉพาะตอนเทสต์** ซึ่งจะทำให้ไม่ได้ทดสอบของจริง
    """
    engine = create_engine_for(DatabaseRole.AUTH)
    try:
        async with presented_session(engine, role=DatabaseRole.AUTH) as session:
            await session.execute("DELETE FROM auth_throttle")
    finally:
        await engine.dispose()


def clear_api_throttle() -> None:
    """ล้างถังของเส้นทาง API key — **ล้างสภาพ ไม่ใช่ปิดกฎ**

    ใช้ในเทสต์ที่ต้องทำรายการหลายครั้งติดกันเพื่อพิสูจน์เรื่องอื่น (เช่นเพดานจำนวน key)
    เทสต์ที่พิสูจน์ตัวการคุมอัตราเองไม่เรียกตัวนี้
    """
    import asyncio

    async def run() -> None:
        engine = create_engine_for(DatabaseRole.API)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DELETE FROM api_throttle"))
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(run())


@pytest.fixture
def client() -> Iterator[TestClient]:
    """ไคลเอนต์ที่เปิด lifespan จริง จึงมี engine ของทั้งสองบทบาท"""
    with TestClient(app) as started:
        started.get("/auth/csrf")
        yield started


def csrf_headers(client: TestClient) -> dict[str, str]:
    """header กัน CSRF จาก cookie ปัจจุบัน

    อ่านใหม่ทุกครั้งโดยเจตนา เพราะเซิร์ฟเวอร์ออกโทเคนใหม่ตอนสมัครและตอนเข้าสู่ระบบ
    ซึ่งเป็นพฤติกรรมที่ต้องการ: โทเคนกัน CSRF ไม่อยู่ยาวข้าม session
    """
    return {CSRF_HEADER: str(client.cookies.get(CSRF_COOKIE, ""))}


def unique_email() -> str:
    """อีเมลที่ไม่ซ้ำกับเทสต์อื่น — ฐานข้อมูลของเทสต์ใช้ร่วมกันทั้งชุด"""
    return f"f05-{uuid4().hex}@example.com"


def register(client: TestClient, *, email: str | None = None, password: str = GOOD_PASSWORD) -> str:
    """สมัครผู้ใช้ใหม่แล้วคืนอีเมลที่ใช้ — ไคลเอนต์จะถือ session ของผู้ใช้นั้นต่อ"""
    used = email if email is not None else unique_email()
    response = client.post(
        "/auth/register",
        json={"email": used, "password": password},
        headers=csrf_headers(client),
    )
    assert response.status_code == 201, response.text
    return used


def session_cookie(client: TestClient) -> str:
    """โทเคน session ที่ไคลเอนต์ถืออยู่"""
    from tiewtrade.services.api.settings import SESSION_COOKIE

    return str(client.cookies.get(SESSION_COOKIE, ""))


def database_url_present() -> bool:
    """ตั้ง URL ของทั้งสองบทบาทไว้หรือยัง"""
    return bool(os.environ.get("TIEWTRADE_DATABASE_URL_AUTH"))


def cookies_now(client: TestClient) -> dict[str, str]:
    """สำเนา cookie ของไคลเอนต์ — ใช้แทน "อีกเครื่องหนึ่ง"

    ใช้วิธีนี้แทนการเปิด `TestClient` ตัวที่สอง เพราะ lifespan ตัวที่สองจะสร้าง
    engine บน event loop ใหม่ แล้ว driver ของฐานข้อมูลจะพังด้วย
    "attached to a different loop" — ไม่ใช่ข้อจำกัดของระบบ แต่ของเครื่องมือทดสอบ
    """
    return {name: str(value) for name, value in client.cookies.items()}


def use_cookies(client: TestClient, saved: dict[str, str]) -> None:
    """สวมรอยกลับไปเป็นเครื่องที่บันทึก cookie ไว้"""
    client.cookies.clear()
    for name, value in saved.items():
        client.cookies.set(name, value)


def sign_in_as_another_device(client: TestClient, email: str, password: str) -> dict[str, str]:
    """เข้าสู่ระบบอีกครั้งเหมือนมาจากเครื่องใหม่ — คืน cookie ของเครื่องนั้น"""
    client.cookies.clear()
    client.get("/auth/csrf")
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    return cookies_now(client)
