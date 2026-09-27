"""บทบาทและสิทธิ์ — V-1 ถึง V-6 และ RQ-6

ทำไมต้องตรวจเรื่องนี้ที่ระดับฐานข้อมูล: กฎเรื่อง secret และการแยกข้อมูลผู้ใช้
ทั้งสเปกตั้งอยู่บนสิทธิ์ของฐานข้อมูล ถ้าไม่ตรวจ มันก็เป็นแค่ข้อตกลงในทีม
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, NotPermittedError, user_session

ALL_ROLE_NAMES = tuple(role.role_name for role in DatabaseRole)


async def test_every_role_exists_and_none_is_superuser(migrator_engine: AsyncEngine) -> None:
    """V-1 — มีบทบาทครบ และไม่มีตัวไหนเป็น superuser"""
    async with migrator_engine.begin() as connection:
        rows = (
            await connection.execute(
                text("SELECT rolname, rolsuper FROM pg_roles WHERE rolname = ANY(:names)"),
                {"names": list(ALL_ROLE_NAMES)},
            )
        ).all()

    found = dict(tuple(row) for row in rows)
    assert set(found) == set(ALL_ROLE_NAMES), f"บทบาทขาด: {set(ALL_ROLE_NAMES) - set(found)}"
    assert not any(found.values()), f"มีบทบาทที่เป็น superuser: {found}"


async def test_only_migrator_owns_tables(migrator_engine: AsyncEngine) -> None:
    """V-2 — เจ้าของตารางต้องเป็น migrator เท่านั้น"""
    async with migrator_engine.begin() as connection:
        owners: set[str] = set(
            (
                await connection.execute(
                    text("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'")
                )
            ).scalars()
        )
    assert owners == {DatabaseRole.MIGRATOR.role_name}, f"เจ้าของตารางไม่ถูกต้อง: {owners}"


async def test_only_scan_role_bypasses_rls(migrator_engine: AsyncEngine) -> None:
    """V-3 — บทบาทเดียวที่ข้าม RLS ได้คือบทบาทกวาดรายการ"""
    async with migrator_engine.begin() as connection:
        result = await connection.execute(
            text("SELECT rolname FROM pg_roles WHERE rolbypassrls AND rolname = ANY(:names)"),
            {"names": list(ALL_ROLE_NAMES)},
        )
        bypassing: set[str] = set(result.scalars())
    assert bypassing == {DatabaseRole.ENGINE_SCAN.role_name}


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO users (id) VALUES (gen_random_uuid())",
        "UPDATE users SET created_at = now()",
        "DELETE FROM users",
    ],
)
async def test_scan_role_cannot_write_user_data(scan_engine: AsyncEngine, statement: str) -> None:
    """V-4 — บทบาทที่ข้าม RLS เขียนข้อมูลผู้ใช้ไม่ได้เลย (Q-3 เงื่อนไข ข)"""
    async with scan_engine.connect() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement))
    assert "permission denied" in str(caught.value).lower() or "42501" in str(caught.value)


@pytest.mark.parametrize(
    "statement",
    [
        "ALTER TABLE users ADD COLUMN sneaky text",
        "ALTER TABLE users DISABLE TRIGGER ALL",
        "DROP TABLE users",
    ],
)
async def test_runtime_role_cannot_change_structure(
    api_engine: AsyncEngine, statement: str
) -> None:
    """V-5 — บทบาทที่ใช้ตอนทำงานปกติแก้โครงสร้างและปิด trigger ไม่ได้ (RQ-5.1)"""
    async with api_engine.connect() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement))
    message = str(caught.value).lower()
    assert "must be owner" in message or "permission denied" in message or "42501" in message


async def test_public_has_no_privileges(migrator_engine: AsyncEngine) -> None:
    """V-6 — ค่าเริ่มต้นคือปฏิเสธ: PUBLIC ไม่มีสิทธิ์อะไรเลย"""
    async with migrator_engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT has_schema_privilege('public', 'public', 'USAGE') AS schema_usage,
                           has_table_privilege('public', 'users', 'SELECT') AS table_select
                    """
                )
            )
        ).one()
    schema_usage, table_select = tuple(row)
    assert not schema_usage, "PUBLIC ยังใช้ schema ได้"
    assert not table_select, "PUBLIC ยังอ่านตาราง users ได้"


async def test_api_can_write_secret_but_cannot_read_it_back(
    api_engine: AsyncEngine, secret_table: str
) -> None:
    """RQ-6 — `api` เขียนค่าที่เข้ารหัสแล้วได้ แต่อ่านกลับไม่ได้ที่ระดับฐานข้อมูล"""
    owner = uuid4()
    async with user_session(api_engine, owner) as session:
        await session.execute(
            f"INSERT INTO {secret_table} (id, owner_id, secret_ciphertext)"
            " VALUES (:id, :owner, :ciphertext)",
            {"id": str(uuid4()), "owner": str(owner), "ciphertext": "encrypted-value"},
        )

    async with user_session(api_engine, owner) as session:
        # อ่านคอลัมน์ที่ได้สิทธิ์ ยังอ่านได้
        rows = (await session.execute(f"SELECT id, owner_id FROM {secret_table}")).all()
        assert len(rows) == 1

        with pytest.raises(NotPermittedError):
            await session.execute(f"SELECT secret_ciphertext FROM {secret_table}")


async def test_scan_role_cannot_read_secret_column(
    api_engine: AsyncEngine, scan_engine: AsyncEngine, secret_table: str
) -> None:
    """Q-3 เงื่อนไข ก — บทบาทที่ข้าม RLS อ่านคอลัมน์ secret ไม่ได้"""
    owner = uuid4()
    async with user_session(api_engine, owner) as session:
        await session.execute(
            f"INSERT INTO {secret_table} (id, owner_id, secret_ciphertext)"
            " VALUES (:id, :owner, :ciphertext)",
            {"id": str(uuid4()), "owner": str(owner), "ciphertext": "encrypted-value"},
        )

    async with scan_engine.connect() as connection:
        # เห็นแถวข้ามผู้ใช้ได้ เพราะเป็นบทบาทกวาดรายการ
        count: int = (
            await connection.execute(text(f"SELECT count(*) FROM {secret_table}"))
        ).scalar_one()
        assert count == 1

        with pytest.raises(Exception) as caught:
            await connection.execute(text(f"SELECT secret_ciphertext FROM {secret_table}"))
    assert "permission denied" in str(caught.value).lower() or "42501" in str(caught.value)
