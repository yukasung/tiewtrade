"""พาร์ทิชัน — V-7, V-15.1, V-15.2, V-33, V-33.1, V-33.2

สองเรื่องที่ทดสอบที่นี่คือสองเรื่องที่ต่างกัน:

1. พาร์ทิชันที่สร้างผ่านฟังก์ชันที่กำหนด **ปิดตายทันที** ทั้ง RLS และ append-only
2. แถวที่ตกลงพาร์ทิชันปลายทางแล้ว **สร้างพาร์ทิชันของเดือนนั้นย้อนหลังไม่ได้**
   และต้องล้มเหลวพร้อมบอกสาเหตุ ไม่ใช่ล้มเหลวเงียบ
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import CURRENT_USER_SETTING, user_session
from tiewtrade.infra.db.errors import (
    SQLSTATE_APPEND_ONLY,
    SQLSTATE_INSUFFICIENT_PRIVILEGE,
    sqlstate_of,
)
from tiewtrade.infra.users import create_user

#: เดือนที่ไกลพอจะไม่มีพาร์ทิชันเจาะจง — แถวของเดือนนี้จะตกพาร์ทิชันปลายทาง
FAR_FUTURE_MONTH = date(2099, 7, 1)
FAR_FUTURE_TIME = datetime(2099, 7, 1, tzinfo=UTC)

#: เดือนที่ยังไม่มีแถวใด ๆ — ใช้ทดสอบการสร้างพาร์ทิชันใหม่
UNUSED_MONTH = date(2090, 1, 1)


async def test_monthly_and_default_partitions_exist(migrator_engine: AsyncEngine) -> None:
    """V-33 — แบ่งรายเดือนจริง และมีพาร์ทิชันปลายทาง"""
    async with migrator_engine.connect() as connection:
        rows: set[str] = set(
            (
                await connection.execute(
                    text(
                        "SELECT inhrelid::regclass::text FROM pg_inherits"
                        " WHERE inhparent = 'audit_events'::regclass"
                    )
                )
            ).scalars()
        )
    assert "audit_events_default" in rows
    monthly = {name for name in rows if name != "audit_events_default"}
    assert len(monthly) == 12, f"ควรมีพาร์ทิชันรายเดือน 12 เดือน ได้ {len(monthly)}"


async def test_partition_read_directly_is_still_under_policy(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    """V-15.1 — อ่านพาร์ทิชันตรง ๆ ก็อยู่ใต้ policy ไม่ใช่เฉพาะผ่านตารางแม่"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with migrator_engine.connect() as connection:
        partition: str = (
            await connection.execute(
                text(
                    "SELECT inhrelid::regclass::text FROM pg_inherits"
                    " WHERE inhparent = 'audit_events'::regclass"
                    "   AND inhrelid::regclass::text = 'audit_events_'"
                    "       || to_char(now(), 'YYYY_MM')"
                )
            )
        ).scalar_one()

        without_identity: int = (
            await connection.execute(text(f"SELECT count(*) FROM {partition}"))
        ).scalar_one()

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config(:setting, :user_id, true)"),
            {"setting": CURRENT_USER_SETTING, "user_id": str(user_id)},
        )
        with_identity: int = (
            await connection.execute(text(f"SELECT count(*) FROM {partition}"))
        ).scalar_one()

    assert without_identity == 0, "อ่านพาร์ทิชันตรง ๆ โดยไม่ตั้ง identity แล้วเห็นข้อมูล"
    assert with_identity == 1


async def test_new_partition_is_locked_down_immediately(migrator_engine: AsyncEngine) -> None:
    """V-7, V-15.2 — พาร์ทิชันที่สร้างใหม่ได้ทั้ง RLS และ append-only ทันที"""
    async with migrator_engine.begin() as connection:
        created: str = (
            await connection.execute(
                text(
                    "SELECT tiewtrade_create_monthly_partition("
                    " 'audit_events'::regclass, CAST(:month AS date), 'owner_user_id')::text"
                ),
                {"month": UNUSED_MONTH},
            )
        ).scalar_one()

    try:
        async with migrator_engine.connect() as connection:
            listed: set[str] = set(
                (
                    await connection.execute(
                        text("SELECT table_name FROM tiewtrade_append_only_tables")
                    )
                ).scalars()
            )
            has_policy: bool = (
                await connection.execute(
                    text(
                        "SELECT count(*) > 0 FROM pg_policy"
                        " WHERE polrelid = CAST(:name AS regclass)"
                    ),
                    {"name": created},
                )
            ).scalar_one()
            forced: bool = (
                await connection.execute(
                    text(
                        "SELECT relforcerowsecurity FROM pg_class"
                        " WHERE oid = CAST(:name AS regclass)"
                    ),
                    {"name": created},
                )
            ).scalar_one()

        assert created in listed, "พาร์ทิชันใหม่ไม่ได้เข้ากลไก append-only"
        assert has_policy, "พาร์ทิชันใหม่ไม่มี policy"
        assert forced, "พาร์ทิชันใหม่ไม่ได้บังคับ RLS กับเจ้าของตาราง"

        async with migrator_engine.begin() as connection:
            with pytest.raises(Exception) as caught:
                await connection.execute(text(f"TRUNCATE {created}"))
        assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {created}"))


async def test_row_landing_in_default_blocks_creating_that_month_loudly(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    """V-33.1 — ลำดับทั้งสามขั้นในเทสต์เดียว

    เขียนเข้าพาร์ทิชันปลายทาง → สร้างพาร์ทิชันของเดือนนั้น → **ต้องล้มเหลวพร้อมบอกสาเหตุ**
    แล้วข้อมูลเดิมต้องยังอ่านได้ครบและยังปิดตายเหมือนเดิม
    """
    user_id = uuid4()
    await create_user(api_engine, user_id)

    # ขั้นที่ 1 — เขียนแถวของเดือนที่ไม่มีพาร์ทิชันเจาะจง
    # ต้องใช้เจ้าของตารางเพราะบทบาททำงานปกติเขียน recorded_at เองไม่ได้ (F-03 RQ-10.1)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config(:setting, :user_id, true)"),
            {"setting": CURRENT_USER_SETTING, "user_id": str(user_id)},
        )
        await connection.execute(
            text(
                "INSERT INTO audit_events"
                " (id, recorded_at, owner_user_id, actor_kind, actor_id, action,"
                "  subject_kind, subject_id, mode, outcome, details)"
                " VALUES (gen_random_uuid(), CAST(:month AS timestamptz), :owner, 'USER', :owner,"
                "  'USER_CREATED', 'USER', :subject, 'NOT_APPLICABLE', 'SUCCEEDED', '{}'::jsonb)"
            ),
            {
                "month": FAR_FUTURE_TIME,
                "owner": str(user_id),
                "subject": str(user_id),
            },
        )

    # ขั้นที่ 2 — สร้างพาร์ทิชันของเดือนนั้น ต้องล้มเหลวพร้อมบอกสาเหตุ
    async with migrator_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(
                text(
                    "SELECT tiewtrade_create_monthly_partition("
                    " 'audit_events'::regclass, CAST(:month AS date), 'owner_user_id')"
                ),
                {"month": FAR_FUTURE_MONTH},
            )
    assert sqlstate_of(caught.value) == "TT002", "ต้องล้มเหลวด้วยรหัสของเราเอง ไม่ใช่ข้อผิดพลาดดิบ"
    assert "พาร์ทิชันปลายทาง" in str(caught.value), "ข้อความไม่ได้บอกสาเหตุที่คนอ่านเข้าใจได้"

    # ขั้นที่ 3 — ข้อมูลยังครบ และยังปิดตาย
    async with user_session(api_engine, user_id) as session:
        result = await session.execute(
            "SELECT count(*) FROM audit_events WHERE owner_user_id = :id", {"id": str(user_id)}
        )
        seen: int = result.scalar_one()
    assert seen == 2, "แถวที่อยู่ในพาร์ทิชันปลายทางต้องยังอ่านผ่านตารางแม่ได้"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config(:setting, :user_id, true)"),
            {"setting": CURRENT_USER_SETTING, "user_id": str(user_id)},
        )
        with pytest.raises(Exception) as caught:
            await connection.execute(
                text("DELETE FROM audit_events_default WHERE owner_user_id = :id"),
                {"id": str(user_id)},
            )
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY


async def test_no_tool_moves_rows_out_of_default(api_engine: AsyncEngine) -> None:
    """V-33.2 — ย้ายแถวออกจากพาร์ทิชันปลายทางด้วยบทบาททำงานปกติก็ไม่ได้"""
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text("DELETE FROM audit_events_default"))
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE
