"""ของกลางของเทสต์ทั้งชุด

**กุญแจปิดผนึกตั้งให้ทุกเทสต์** เพราะแอปอ่านกุญแจตอนเปิด (F-06 validation V-10)
ฉะนั้นเทสต์ใดที่เปิดแอปก็ต้องมีกุญแจ — ตั้งเหมือนตั้งค่าอื่น **ไม่ใช่ปิดการตรวจ**
เพราะการปิดจะทำให้ไม่ได้ทดสอบของจริง (เหตุผลเดียวกับที่เทสต์ของ F-05 ล้างสภาพ
ของตัวนับแทนการปิดกฎ)
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Final

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose
from tiewtrade.infra.db import DatabaseRole, create_engine_for

#: กุญแจของเทสต์ — **ค่าคงที่ที่ไม่มีความลับ** และใช้ได้เฉพาะในเทสต์
TEST_SEALING_KEY: Final[str] = "1:" + base64.b64encode(b"T" * KEY_BYTES).decode("ascii")

#: กุญแจของ API key — **ค่าต่างจากของ TOTP โดยตั้งใจ** เพื่อให้เทสต์ที่พิสูจน์ว่า
#: สองงานใช้กุญแจคนละดอกมีของจริงให้เทียบ (F-07 RQ-4)
TEST_VENUE_KEY: Final[str] = "1:" + base64.b64encode(b"V" * KEY_BYTES).decode("ascii")

_DESTRUCTIVE_MIGRATION_MODULES: Final[frozenset[str]] = frozenset(
    {
        "tests/infra/db/test_migrations.py",
        "tests/infra/market_data/test_migration.py",
        "tests/infra/market_data/test_realtime_migration.py",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run destructive schema replay before immutable integration fixtures."""

    items.sort(
        key=lambda item: (
            0 if item.path.as_posix().endswith(tuple(_DESTRUCTIVE_MIGRATION_MODULES)) else 1
        )
    )


@pytest.fixture(autouse=True)
def _sealing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """ตั้งกุญแจปิดผนึกทั้งสองดอกให้ทุกเทสต์

    เทสต์ที่ต้องพิสูจน์ว่า **ไม่มีกุญแจแล้วแอปไม่เริ่ม** ลบค่านี้เองในเทสต์ของมัน
    """
    monkeypatch.setenv(KeyPurpose.TOTP_SECRET.environment_variable, TEST_SEALING_KEY)
    monkeypatch.setenv(KeyPurpose.VENUE_API_SECRET.environment_variable, TEST_VENUE_KEY)
    monkeypatch.setenv(
        KeyPurpose.INDICATOR_CURSOR.environment_variable,
        "1:" + base64.b64encode(b"I" * KEY_BYTES).decode("ascii"),
    )


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
