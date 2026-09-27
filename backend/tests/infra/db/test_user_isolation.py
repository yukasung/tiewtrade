"""การแยกข้อมูลผู้ใช้ — V-7 ถึง V-14

กฎที่พิสูจน์ที่นี่คือใจกลางของ `mission.md` หัวข้อ 8 ข้อ 7 — ข้อมูลผู้ใช้แต่ละคน
ต้องแยกขาดจากกันที่ระดับฐานข้อมูล ไม่ใช่เพราะโค้ดใส่เงื่อนไขครบ
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import (
    CURRENT_USER_SETTING,
    DatabaseRole,
    NotPermittedError,
    UserSession,
    user_session,
)
from tiewtrade.infra.db.errors import SQLSTATE_INSUFFICIENT_PRIVILEGE, sqlstate_of
from tiewtrade.infra.users import create_user, fetch_user


async def test_user_sees_only_own_row(api_engine: AsyncEngine) -> None:
    """V-7 — เห็นเฉพาะแถวของผู้ใช้ปัจจุบัน"""
    first, second = uuid4(), uuid4()
    await create_user(api_engine, first)
    await create_user(api_engine, second)

    async with user_session(api_engine, first) as session:
        seen = list((await session.execute("SELECT id FROM users")).scalars())

    assert seen == [first]


async def test_other_users_row_is_not_found_rather_than_forbidden(api_engine: AsyncEngine) -> None:
    """V-8 — ขอแถวของคนอื่นได้ "ไม่พบ" ไม่ใช่ "ไม่มีสิทธิ์" (RQ-16)"""
    owner, stranger = uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, stranger)

    async with user_session(api_engine, owner) as session:
        assert await fetch_user(session, owner) is not None
        assert await fetch_user(session, stranger) is None


async def test_without_identity_reads_zero_rows(api_engine: AsyncEngine) -> None:
    """V-9 — ไม่ระบุผู้ใช้ → อ่านได้ศูนย์แถว ไม่ใช่เห็นทั้งตาราง"""
    await create_user(api_engine, uuid4())

    async with api_engine.connect() as connection:
        count: int = (await connection.execute(text("SELECT count(*) FROM users"))).scalar_one()

    assert count == 0


async def test_without_identity_cannot_write(api_engine: AsyncEngine) -> None:
    """V-10 — ไม่ระบุผู้ใช้ → เขียนไม่ได้ ไม่ใช่เขียนลงเป็นของใครก็ไม่รู้"""
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(
                text("INSERT INTO users (id) VALUES (:id)"), {"id": str(uuid4())}
            )
    # PostgreSQL ใช้ SQLSTATE 42501 เมื่อแถวใหม่ผิด policy — ตรวจด้วยรหัส ไม่ใช่ข้อความ
    # เพราะข้อความของ driver เปลี่ยนได้ทุกเวอร์ชัน
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


async def test_cannot_create_row_for_another_user(api_engine: AsyncEngine) -> None:
    """V-11 — สร้างแถวให้ผู้ใช้อื่นไม่ได้ บังคับด้วย WITH CHECK"""
    owner, victim = uuid4(), uuid4()
    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("INSERT INTO users (id) VALUES (:id)", {"id": str(victim)})


async def test_identity_does_not_leak_to_next_transaction_on_same_connection(
    api_engine: AsyncEngine,
) -> None:
    """V-12 — ค่า identity ไม่ค้างข้ามไปถึงผู้ใช้คนถัดไปที่ได้ connection เดิม

    นี่คือกรณีที่ `SET` ธรรมดาจะพลาด แต่ `SET LOCAL` ไม่พลาด
    ทดสอบบน connection **เดิม** ไม่ใช่ connection ใหม่ เพราะ pool ใช้ของเดิมซ้ำ
    """
    first = uuid4()
    await create_user(api_engine, first)

    async with api_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                text("SELECT set_config(:setting, :user_id, true)"),
                {"setting": CURRENT_USER_SETTING, "user_id": str(first)},
            )
            seen_inside: int = (
                await connection.execute(text("SELECT count(*) FROM users"))
            ).scalar_one()

        # transaction ใหม่บน connection เดิม โดยไม่ตั้ง identity
        async with connection.begin():
            leaked_setting: str | None = (
                await connection.execute(
                    text("SELECT current_setting(:setting, true)"),
                    {"setting": CURRENT_USER_SETTING},
                )
            ).scalar_one()
            seen_after: int = (
                await connection.execute(text("SELECT count(*) FROM users"))
            ).scalar_one()

    assert seen_inside == 1, "ตั้ง identity แล้วต้องเห็นแถวของตัวเอง"
    assert leaked_setting in (None, ""), f"ค่า identity ค้างมา: {leaked_setting!r}"
    assert seen_after == 0, "ค่า identity ค้างข้าม transaction — อันตรายที่สุดของการใช้ pool"


async def test_table_owner_is_also_under_policy(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    """V-13 — FORCE ROW LEVEL SECURITY ทำให้เจ้าของตารางอยู่ใต้ policy ด้วย"""
    await create_user(api_engine, uuid4())

    async with migrator_engine.connect() as connection:
        count: int = (await connection.execute(text("SELECT count(*) FROM users"))).scalar_one()

    assert count == 0, "เจ้าของตารางเห็นข้อมูลผู้ใช้ทั้งหมด — ขัดกับ FORCE ROW LEVEL SECURITY"


async def test_engine_role_user_work_is_under_rls(
    api_engine: AsyncEngine, engine_engine: AsyncEngine
) -> None:
    """V-14 — งานของผู้ใช้รายเดียวใน engine อยู่ใต้ RLS จริง (Q-3)"""
    mine, other = uuid4(), uuid4()
    await create_user(api_engine, mine)
    await create_user(api_engine, other)

    async with user_session(engine_engine, mine, role=DatabaseRole.ENGINE) as session:
        assert isinstance(session, UserSession)
        seen = list((await session.execute("SELECT id FROM users")).scalars())

    assert seen == [mine]
