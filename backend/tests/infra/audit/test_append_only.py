"""บันทึกแก้ย้อนหลังไม่ได้ รวมกรณีพาร์ทิชัน — V-1 ถึง V-9

ตรวจ **สองชั้น คูณ สามคำสั่ง คูณ สองที่ (ตารางแม่และพาร์ทิชัน)** แยกกันทีละกรณี
กรณีที่พาร์ทิชันคือช่องที่กลไกเดิมของ F-03 ยังไม่ปิด — ถ้าไม่ทดสอบแยก
จะไม่มีอะไรบอกว่าปิดแล้วจริง
"""

from __future__ import annotations

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

MUTATIONS = [
    "UPDATE {table} SET outcome = 'FAILED'",
    "DELETE FROM {table}",
    "TRUNCATE {table}",
]
MUTATION_IDS = ["update", "delete", "truncate"]


async def _seen_by_owner(engine: AsyncEngine, user_id: object) -> int:
    """นับบันทึกของผู้ใช้คนนั้นโดยตั้ง identity ให้ถูก"""
    from uuid import UUID

    assert isinstance(user_id, UUID)
    async with user_session(engine, user_id) as session:
        result = await session.execute(
            "SELECT count(*) FROM audit_events WHERE owner_user_id = :id", {"id": str(user_id)}
        )
        count: int = result.scalar_one()
    return count


async def _current_partition(engine: AsyncEngine) -> str:
    """ชื่อพาร์ทิชันของเดือนนี้ — อ่านจากฐานข้อมูล ไม่คำนวณชื่อเอง"""
    async with engine.connect() as connection:
        name: str = (
            await connection.execute(
                text(
                    "SELECT inhrelid::regclass::text FROM pg_inherits"
                    " WHERE inhparent = 'audit_events'::regclass"
                    "   AND inhrelid::regclass::text = 'audit_events_'"
                    "       || to_char(now(), 'YYYY_MM')"
                )
            )
        ).scalar_one()
    return name


async def test_table_is_listed_as_append_only(migrator_engine: AsyncEngine) -> None:
    """V-1 — ตารางและพาร์ทิชันทุกตัวปรากฏในรายการที่เปิดกลไกไว้"""
    async with migrator_engine.connect() as connection:
        listed: set[str] = set(
            (
                await connection.execute(
                    text("SELECT table_name FROM tiewtrade_append_only_tables")
                )
            ).scalars()
        )
        partitions: set[str] = set(
            (
                await connection.execute(
                    text(
                        "SELECT inhrelid::regclass::text FROM pg_inherits"
                        " WHERE inhparent = 'audit_events'::regclass"
                    )
                )
            ).scalars()
        )

    assert "audit_events" in listed
    assert partitions, "ไม่มีพาร์ทิชันเลย"
    assert partitions <= listed, f"พาร์ทิชันที่ยังไม่ถูกปิด: {partitions - listed}"


@pytest.mark.parametrize("statement", MUTATIONS, ids=MUTATION_IDS)
async def test_privilege_layer_blocks_mutations_on_parent(
    api_engine: AsyncEngine, statement: str
) -> None:
    """V-2, V-3, V-4 ชั้นสิทธิ์ที่ตารางแม่"""
    await create_user(api_engine, uuid4())
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table="audit_events")))
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize("statement", MUTATIONS, ids=MUTATION_IDS)
async def test_trigger_layer_blocks_mutations_on_parent(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine, statement: str
) -> None:
    """V-2, V-3, V-4 ชั้น trigger — เจ้าของตารางที่มีสิทธิ์ครบก็ยังทำไม่ได้

    ต้องตั้ง identity ให้เห็นแถวก่อน ไม่เช่นนั้น `FORCE ROW LEVEL SECURITY` จะซ่อนแถว
    จนไม่มีอะไรให้ trigger จับ แล้วเทสต์จะเขียวเพราะเหตุผลที่ไม่ได้ตั้งใจทดสอบ
    """
    user_id = uuid4()
    await create_user(api_engine, user_id)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config(:setting, :user_id, true)"),
            {"setting": CURRENT_USER_SETTING, "user_id": str(user_id)},
        )
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table="audit_events")))
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY


@pytest.mark.parametrize("statement", MUTATIONS, ids=MUTATION_IDS)
async def test_privilege_layer_blocks_mutations_on_partition_directly(
    api_engine: AsyncEngine, statement: str
) -> None:
    """V-5, V-6 ชั้นสิทธิ์ — สั่งที่พาร์ทิชันตรง ๆ ก็ไม่ได้"""
    await create_user(api_engine, uuid4())
    partition = await _current_partition(api_engine)
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table=partition)))
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize("statement", MUTATIONS, ids=MUTATION_IDS)
async def test_trigger_layer_blocks_mutations_on_partition_directly(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine, statement: str
) -> None:
    """V-5, V-6 ชั้น trigger ที่พาร์ทิชัน — ช่องที่กลไกเดิมของ F-03 ยังไม่ปิด

    `TRUNCATE` สำคัญที่สุดในสามข้อนี้ เพราะ trigger ระดับ statement ของตารางแม่
    ไม่ถูกโคลนไปที่พาร์ทิชัน ถ้าไม่ผูกเองที่พาร์ทิชัน คำสั่งนี้จะผ่าน
    """
    user_id = uuid4()
    await create_user(api_engine, user_id)
    partition = await _current_partition(migrator_engine)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config(:setting, :user_id, true)"),
            {"setting": CURRENT_USER_SETTING, "user_id": str(user_id)},
        )
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table=partition)))
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY


async def test_insert_still_works_through_parent(api_engine: AsyncEngine) -> None:
    """V-8 — เขียนได้ตามปกติ"""
    user_id = uuid4()
    await create_user(api_engine, user_id)
    assert await _seen_by_owner(api_engine, user_id) == 1
