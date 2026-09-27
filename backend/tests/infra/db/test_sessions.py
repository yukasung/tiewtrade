"""ทางเข้าฐานข้อมูล — ลืมระบุผู้ใช้ไม่ได้ และใช้บทบาทผิดไม่ได้

สองกรณีนี้คือกรณีที่ plan.md ระบุให้ต้อง "แดงเมื่อควรแดง":
เส้นทางที่แตะข้อมูลผู้ใช้ต้องปฏิเสธ `ScanSession` และ connection ดิบ **ก่อน query**
ไม่ใช่ปล่อยให้ query วิ่งไปแล้วหวังว่า RLS จะกันให้ เพราะบทบาทกวาดรายการข้าม RLS
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import (
    DatabaseConfigurationError,
    DatabaseRole,
    DatabaseRoleError,
    ScanSession,
    SessionKindError,
    create_engine_for,
    database_url,
    require_user_session,
    scan_session_bypassing_rls,
    user_session,
)
from tiewtrade.infra.users import create_user, fetch_user


async def test_scan_session_cannot_enter_user_path(
    api_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    """เส้นทางของผู้ใช้ปฏิเสธ session ที่ข้าม RLS ก่อนถึง query"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with scan_session_bypassing_rls(scan_engine) as scan:
        assert isinstance(scan, ScanSession)
        with pytest.raises(SessionKindError):
            await fetch_user(scan, user_id)


async def test_raw_connection_cannot_enter_user_path(api_engine: AsyncEngine) -> None:
    """connection ดิบก็เข้าไม่ได้ ไม่ใช่กันแค่ ScanSession"""
    async with api_engine.connect() as connection:
        with pytest.raises(SessionKindError):
            await fetch_user(connection, uuid4())


def test_guard_rejects_anything_that_is_not_a_user_session() -> None:
    """ตัวตรวจกลางอยู่ที่เดียว — ทุก repository ใช้ตัวเดียวกัน"""
    with pytest.raises(SessionKindError):
        require_user_session(object())


async def test_user_path_refuses_the_bypassing_role(scan_engine: AsyncEngine) -> None:
    """ขอ session ของผู้ใช้ด้วยบทบาทที่ข้าม RLS ต้องไม่ได้"""
    with pytest.raises(DatabaseRoleError):
        async with user_session(scan_engine, uuid4(), role=DatabaseRole.ENGINE_SCAN):
            pass


async def test_wrong_url_is_caught_before_touching_user_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ตั้ง URL สลับกัน (API ชี้ไปบทบาทที่ข้าม RLS) ต้องดังก่อนอ่านข้อมูลผู้ใช้

    นี่คือความผิดที่เงียบที่สุดของการแยกบทบาท — ถ้าไม่ตรวจ งานรายผู้ใช้จะวิ่งอยู่บน
    บทบาทที่ไม่มีใครกรองแถวให้ โดยไม่มีอะไรเตือน
    """
    monkeypatch.setenv(DatabaseRole.API.url_variable, database_url(DatabaseRole.ENGINE_SCAN))
    engine = create_engine_for(DatabaseRole.API)
    try:
        with pytest.raises(DatabaseRoleError):
            async with user_session(engine, uuid4()):
                pass
    finally:
        await engine.dispose()


async def test_scan_path_refuses_a_role_that_does_not_bypass(api_engine: AsyncEngine) -> None:
    """กลับกัน — ทางกวาดรายการต้องไม่ยอมรับบทบาทที่อยู่ใต้ RLS

    เพราะงานกวาดที่วิ่งใต้ RLS จะเห็นศูนย์แถวเสมอ แล้วจะกลายเป็น "ไม่มีงานให้ทำ"
    อย่างเงียบ ๆ ซึ่งแย่กว่าการดังทันที
    """
    with pytest.raises(DatabaseRoleError):
        async with scan_session_bypassing_rls(api_engine):
            pass


def test_missing_configuration_names_the_variable_but_not_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V-39 — ไม่ได้ตั้งค่า ต้องแดงพร้อมบอกชื่อตัวแปร ไม่ใช่ข้ามเทสต์"""
    secret_url = database_url(DatabaseRole.API)
    monkeypatch.delenv(DatabaseRole.API.url_variable, raising=False)
    assert os.environ.get(DatabaseRole.API.url_variable) is None

    with pytest.raises(DatabaseConfigurationError) as caught:
        database_url(DatabaseRole.API)

    message = str(caught.value)
    assert DatabaseRole.API.url_variable in message
    assert secret_url not in message
    assert "dev_api" not in message, "รหัสผ่านหลุดอยู่ในข้อความข้อผิดพลาด"
