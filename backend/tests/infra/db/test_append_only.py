"""ตารางที่แก้ย้อนหลังไม่ได้ — V-15 ถึง V-21

ตรวจ **สองชั้น คูณ สามคำสั่ง แยกกันทีละกรณี**:

- ชั้นสิทธิ์ — ทดสอบด้วยบทบาทที่ใช้ตอนทำงานปกติ
- ชั้น trigger — ทดสอบด้วยเจ้าของตาราง ซึ่งมีสิทธิ์ครบจึงผ่านชั้นแรกมาได้

ถ้าทดสอบด้วยบทบาทเดียว จะไม่รู้ว่าชั้นที่สองทำงานหรือไม่ และวันที่มีคน `GRANT` ผิด
เราจะเพิ่งรู้ว่าไม่มีชั้นที่สองมาตั้งแต่ต้น
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import AppendOnlyViolationError, NotPermittedError, user_session
from tiewtrade.infra.db.errors import (
    SQLSTATE_APPEND_ONLY,
    SQLSTATE_INSUFFICIENT_PRIVILEGE,
    sqlstate_of,
)


async def _insert_row(engine: AsyncEngine, table: str) -> None:
    owner = uuid4()
    async with user_session(engine, owner) as session:
        await session.execute(
            f"INSERT INTO {table} (id, note) VALUES (:id, :note)",
            {"id": str(uuid4()), "note": "บันทึกแล้วห้ามแก้"},
        )


async def test_insert_still_works(api_engine: AsyncEngine, append_only_table: str) -> None:
    """V-18 — เพิ่มได้ตามปกติ ไม่ใช่ล็อกทั้งตาราง"""
    await _insert_row(api_engine, append_only_table)
    async with api_engine.connect() as connection:
        count: int = (
            await connection.execute(text(f"SELECT count(*) FROM {append_only_table}"))
        ).scalar_one()
    assert count == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE {table} SET note = 'แก้แล้ว'",
        "DELETE FROM {table}",
        "TRUNCATE {table}",
    ],
    ids=["update", "delete", "truncate"],
)
async def test_privilege_layer_blocks_every_mutation(
    api_engine: AsyncEngine, append_only_table: str, statement: str
) -> None:
    """V-15, V-16, V-17 ชั้นสิทธิ์ — บทบาททำงานปกติทำสามคำสั่งนี้ไม่ได้

    ตารางนี้ได้สิทธิ์ครบทั้งสี่คำสั่งก่อนเปิดกลไก ฉะนั้นการถูกปฏิเสธที่นี่
    คือผลของกลไก ไม่ใช่ผลของการไม่เคยได้สิทธิ์
    """
    await _insert_row(api_engine, append_only_table)
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table=append_only_table)))
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE {table} SET note = 'แก้แล้ว'",
        "DELETE FROM {table}",
        "TRUNCATE {table}",
    ],
    ids=["update", "delete", "truncate"],
)
async def test_trigger_layer_blocks_even_the_table_owner(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine, append_only_table: str, statement: str
) -> None:
    """V-15, V-16, V-17 ชั้น trigger — เจ้าของตารางที่มีสิทธิ์ครบก็ยังทำไม่ได้"""
    await _insert_row(api_engine, append_only_table)
    async with migrator_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table=append_only_table)))
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY


async def test_ordinary_tables_are_untouched(api_engine: AsyncEngine, mutable_table: str) -> None:
    """V-19 — กลไกไม่ลามไปทุกตาราง ตารางทั่วไปยังแก้และลบได้ (ขอบเขตที่เจ้าของระบุ)"""
    await _insert_row(api_engine, mutable_table)
    async with api_engine.begin() as connection:
        await connection.execute(text(f"UPDATE {mutable_table} SET note = 'แก้ได้'"))
        await connection.execute(text(f"DELETE FROM {mutable_table}"))
        await connection.execute(text(f"TRUNCATE {mutable_table}"))


async def test_listing_matches_reality(
    migrator_engine: AsyncEngine, append_only_table: str, mutable_table: str
) -> None:
    """V-20 — รายชื่อตารางที่เปิดกลไกอ่านออกได้ และตรงกับความจริง"""
    async with migrator_engine.begin() as connection:
        listed: set[str] = set(
            (
                await connection.execute(
                    text("SELECT table_name FROM tiewtrade_append_only_tables")
                )
            ).scalars()
        )
    assert append_only_table in listed
    assert mutable_table not in listed


async def test_errors_are_typed_not_free_text(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine, append_only_table: str
) -> None:
    """V-21 — ข้อผิดพลาดเป็นชนิดที่ระบุได้ ผู้เรียกดักได้โดยไม่อ่านข้อความ (RQ-14)"""
    await _insert_row(api_engine, append_only_table)

    async with user_session(api_engine, uuid4()) as session:
        with pytest.raises(NotPermittedError) as privilege_error:
            await session.execute(f"DELETE FROM {append_only_table}")
    assert privilege_error.value.code == "NOT_PERMITTED"

    # ชั้น trigger ผ่านทางเจ้าของตาราง — ต้องได้ชนิดที่บอกว่าเป็นตารางแก้ย้อนหลังไม่ได้
    async with migrator_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(f"DELETE FROM {append_only_table}"))
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY
    from tiewtrade.infra.db.errors import translate_database_error

    translated = translate_database_error(caught.value)
    assert isinstance(translated, AppendOnlyViolationError)
    assert translated.code == "APPEND_ONLY_VIOLATION"
