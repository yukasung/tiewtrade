"""ของกลางของเทสต์ที่แตะฐานข้อมูล (F-03, F-04)

เทสต์กลุ่มนี้รันกับ **PostgreSQL จริง** เพราะสิ่งที่ทดสอบคือ RLS สิทธิ์ และ trigger
ซึ่งเป็นความสามารถของ PostgreSQL เอง ฐานข้อมูลในหน่วยความจำพิสูจน์อะไรไม่ได้เลย

**ถ้าไม่มีฐานข้อมูล เทสต์ต้องแดง ไม่ใช่ข้าม** การข้ามทำให้ CI เขียวทั้งที่ไม่เคยตรวจอะไร

ย้ายมาอยู่ระดับนี้ตอน F-04 เพื่อให้เทสต์ของ audit log ใช้ engine ชุดเดียวกัน
ไม่ใช่สร้างของตัวเองขึ้นมาอีกชุด

"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for


async def _engine(role: DatabaseRole) -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(role)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def api_engine() -> AsyncIterator[AsyncEngine]:
    async for engine in _engine(DatabaseRole.API):
        yield engine


@pytest_asyncio.fixture
async def engine_engine() -> AsyncIterator[AsyncEngine]:
    async for engine in _engine(DatabaseRole.ENGINE):
        yield engine


@pytest_asyncio.fixture
async def scan_engine() -> AsyncIterator[AsyncEngine]:
    async for engine in _engine(DatabaseRole.ENGINE_SCAN):
        yield engine


@pytest_asyncio.fixture
async def auth_engine() -> AsyncIterator[AsyncEngine]:
    """บทบาทยืนยันตัวตนของ F-05 — บทบาทเดียวที่แตะข้อมูลเข้าสู่ระบบได้"""
    async for engine in _engine(DatabaseRole.AUTH):
        yield engine


@pytest_asyncio.fixture
async def migrator_engine() -> AsyncIterator[AsyncEngine]:
    async for engine in _engine(DatabaseRole.MIGRATOR):
        yield engine
