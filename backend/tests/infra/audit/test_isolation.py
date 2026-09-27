"""การแยกข้อมูลผู้ใช้และสิทธิ์ของบันทึก — V-10 ถึง V-15"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, NotPermittedError, user_session
from tiewtrade.infra.db.errors import SQLSTATE_INSUFFICIENT_PRIVILEGE, sqlstate_of
from tiewtrade.infra.users import create_user

_RUNTIME_ROLES = tuple(role.role_name for role in DatabaseRole if role is not DatabaseRole.MIGRATOR)


async def test_owner_sees_only_own_events(api_engine: AsyncEngine) -> None:
    """V-10 — เห็นเฉพาะบันทึกของตัวเอง"""
    mine, other = uuid4(), uuid4()
    await create_user(api_engine, mine)
    await create_user(api_engine, other)

    async with user_session(api_engine, mine) as session:
        owners = list((await session.execute("SELECT owner_user_id FROM audit_events")).scalars())

    assert owners == [mine]


async def test_without_identity_reads_nothing_and_writes_nothing(api_engine: AsyncEngine) -> None:
    """V-11 — ไม่ระบุผู้ใช้ → อ่านศูนย์แถว และเขียนไม่ได้"""
    await create_user(api_engine, uuid4())

    async with api_engine.connect() as connection:
        count: int = (
            await connection.execute(text("SELECT count(*) FROM audit_events"))
        ).scalar_one()
    assert count == 0

    stranger = uuid4()
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(
                text(
                    "INSERT INTO audit_events"
                    " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
                    "  subject_id, mode, outcome, details)"
                    " VALUES (gen_random_uuid(), CAST(:owner AS uuid), 'USER',"
                    "  CAST(:owner AS uuid), 'USER_CREATED', 'USER', :subject,"
                    "  'NOT_APPLICABLE', 'SUCCEEDED', '{}'::jsonb)"
                ),
                {"owner": str(stranger), "subject": str(stranger)},
            )
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


async def test_cannot_write_event_for_another_user(api_engine: AsyncEngine) -> None:
    """V-12 — เขียนบันทึกให้เป็นของผู้ใช้อื่นไม่ได้ บังคับด้วย WITH CHECK"""
    owner, victim = uuid4(), uuid4()
    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "INSERT INTO audit_events"
                " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
                "  subject_id, mode, outcome, details)"
                " VALUES (gen_random_uuid(), CAST(:victim AS uuid), 'USER',"
                "  CAST(:victim AS uuid), 'USER_CREATED', 'USER', :subject,"
                "  'NOT_APPLICABLE', 'SUCCEEDED', '{}'::jsonb)",
                {"victim": str(victim), "subject": str(victim)},
            )


async def test_no_runtime_role_can_update_delete_or_truncate(
    migrator_engine: AsyncEngine,
) -> None:
    """V-13 — อ่านสิทธิ์จริงจากฐานข้อมูล ไม่ใช่เชื่อว่า migration ทำถูก

    ตรวจเฉพาะบทบาทที่ใช้ตอนทำงานปกติ เพราะเจ้าของตารางมีสิทธิ์ของตัวเองโดยธรรมชาติ
    และให้สิทธิ์คืนตัวเองได้เสมอ — สิ่งที่กันเจ้าของตารางคือ trigger
    ซึ่งพิสูจน์ไว้ใน `test_append_only.py` แล้ว
    """
    async with migrator_engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT grantee, privilege_type FROM information_schema.table_privileges"
                    " WHERE table_name = 'audit_events' AND grantee = ANY(:roles)"
                ),
                {"roles": list(_RUNTIME_ROLES)},
            )
        ).all()

    granted = {(grantee, privilege) for grantee, privilege in (tuple(row) for row in rows)}
    forbidden = {
        (role, privilege)
        for role, privilege in granted
        if privilege in {"UPDATE", "DELETE", "TRUNCATE"}
    }
    assert not forbidden, f"มีบทบาทที่ได้สิทธิ์แก้หรือลบบันทึก: {forbidden}"


async def test_scan_role_has_no_access_at_all(scan_engine: AsyncEngine) -> None:
    """V-14 — บทบาทกวาดรายการไม่มีสิทธิ์อะไรเลยกับตารางนี้ รวมการอ่าน"""
    async with scan_engine.connect() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text("SELECT count(*) FROM audit_events"))
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


async def test_table_owner_is_under_policy(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    """V-15 — เจ้าของตารางก็อยู่ใต้ policy เมื่ออ่านผ่านตารางแม่"""
    await create_user(api_engine, uuid4())
    async with migrator_engine.connect() as connection:
        count: int = (
            await connection.execute(text("SELECT count(*) FROM audit_events"))
        ).scalar_one()
    assert count == 0
