"""ตารางทดสอบของกลไกใน F-03 — engine ต่อบทบาทอยู่ที่ tests/infra/conftest.py"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def _create_table(engine: AsyncEngine, ddl: list[str]) -> None:
    async with engine.begin() as connection:
        for statement in ddl:
            await connection.execute(text(statement))


async def _drop_table(engine: AsyncEngine, name: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text(f"DROP TABLE IF EXISTS {name}"))


@pytest_asyncio.fixture
async def append_only_table(migrator_engine: AsyncEngine) -> AsyncIterator[str]:
    """ตารางที่เปิดกลไก append-only

    ให้สิทธิ์ครบทั้งสี่คำสั่ง **ก่อน** เปิดกลไก เพื่อพิสูจน์ว่ากลไกเป็นตัวตัดสิทธิ์จริง
    ไม่ใช่ผ่านเพราะไม่เคยได้สิทธิ์มาตั้งแต่ต้น
    """
    name = f"test_append_only_{uuid4().hex[:10]}"
    await _create_table(
        migrator_engine,
        [
            f"CREATE TABLE {name} (id uuid PRIMARY KEY, note text NOT NULL)",
            f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON {name} TO tiewtrade_api",
            f"SELECT tiewtrade_make_append_only('{name}'::regclass)",
        ],
    )
    try:
        yield name
    finally:
        await _drop_table(migrator_engine, name)


@pytest_asyncio.fixture
async def mutable_table(migrator_engine: AsyncEngine) -> AsyncIterator[str]:
    """ตารางทั่วไปที่ไม่ได้เปิดกลไก — ต้องแก้และลบได้ตามปกติ (V-19)"""
    name = f"test_mutable_{uuid4().hex[:10]}"
    await _create_table(
        migrator_engine,
        [
            f"CREATE TABLE {name} (id uuid PRIMARY KEY, note text NOT NULL)",
            f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON {name} TO tiewtrade_api",
        ],
    )
    try:
        yield name
    finally:
        await _drop_table(migrator_engine, name)


@pytest_asyncio.fixture
async def money_table(migrator_engine: AsyncEngine) -> AsyncIterator[str]:
    """ตารางเงินจำลอง — เก็บจำนวนคู่กับหน่วยตาม plan.md ข้อ 5"""
    name = f"test_money_{uuid4().hex[:10]}"
    await _create_table(
        migrator_engine,
        [
            f"""
            CREATE TABLE {name} (
                id uuid PRIMARY KEY,
                amount tiewtrade_money_amount NOT NULL,
                unit tiewtrade_unit_code NOT NULL
            )
            """,
            f"GRANT SELECT, INSERT ON {name} TO tiewtrade_api",
        ],
    )
    try:
        yield name
    finally:
        await _drop_table(migrator_engine, name)


@pytest_asyncio.fixture
async def secret_table(migrator_engine: AsyncEngine) -> AsyncIterator[str]:
    """ตารางที่มีคอลัมน์ secret — พิสูจน์ "เขียนได้ อ่านกลับไม่ได้" (RQ-6)"""
    name = f"test_secret_{uuid4().hex[:10]}"
    await _create_table(
        migrator_engine,
        [
            f"""
            CREATE TABLE {name} (
                id uuid PRIMARY KEY,
                owner_id uuid NOT NULL,
                secret_ciphertext text NOT NULL
            )
            """,
            f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY",
            f"""
            CREATE POLICY {name}_owner_only ON {name}
                FOR ALL
                USING (owner_id = tiewtrade_current_user_id())
                WITH CHECK (owner_id = tiewtrade_current_user_id())
            """,
            f"GRANT SELECT (id, owner_id) ON {name} TO tiewtrade_api, tiewtrade_engine_scan",
            f"GRANT INSERT (id, owner_id, secret_ciphertext) ON {name} TO tiewtrade_api",
            f"GRANT SELECT (id, owner_id, secret_ciphertext) ON {name} TO tiewtrade_engine",
        ],
    )
    try:
        yield name
    finally:
        await _drop_table(migrator_engine, name)
