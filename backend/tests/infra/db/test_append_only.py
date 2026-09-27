"""ตารางที่แก้ย้อนหลังไม่ได้ — V-15 ถึง V-21

ตรวจ **สองชั้น คูณ สามคำสั่ง แยกกันทีละกรณี**:

- ชั้นสิทธิ์ — ทดสอบด้วยบทบาทที่ใช้ตอนทำงานปกติ
- ชั้น trigger — ทดสอบด้วยเจ้าของตาราง ซึ่งมีสิทธิ์ครบจึงผ่านชั้นแรกมาได้

ถ้าทดสอบด้วยบทบาทเดียว จะไม่รู้ว่าชั้นที่สองทำงานหรือไม่ และวันที่มีคน `GRANT` ผิด
เราจะเพิ่งรู้ว่าไม่มีชั้นที่สองมาตั้งแต่ต้น
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
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


# ─────────────────────────────────────────────────────────────
# ตารางที่แบ่งพาร์ทิชัน (เพิ่มตอน F-04)
#
# กลไกรุ่นแรกของ F-03 ครอบเฉพาะตารางธรรมดา migration 0003 ขยายให้ครอบพาร์ทิชัน
# เทสต์กลุ่มนี้พิสูจน์ทั้งว่าครอบแล้วจริง และว่าข้อจำกัดที่เหลืออยู่คืออะไร
# ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def partitioned_append_only_table(migrator_engine: AsyncEngine) -> AsyncIterator[str]:
    """ตารางที่แบ่งพาร์ทิชันและเปิดกลไกผ่านทางที่กำหนดไว้"""
    name = f"test_partitioned_{uuid4().hex[:10]}"
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                f"CREATE TABLE {name} ("
                " id uuid NOT NULL,"
                " owner_user_id uuid NOT NULL,"
                " recorded_at timestamptz NOT NULL DEFAULT now(),"
                " note text NOT NULL,"
                f" CONSTRAINT {name}_pkey PRIMARY KEY (recorded_at, id)"
                ") PARTITION BY RANGE (recorded_at)"
            )
        )
        await connection.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON {name} TO tiewtrade_api")
        )
        await connection.execute(text(f"SELECT tiewtrade_make_append_only('{name}'::regclass)"))
        await connection.execute(
            text(
                "SELECT tiewtrade_create_monthly_partition("
                f" '{name}'::regclass, date_trunc('month', now())::date, 'owner_user_id')"
            )
        )
    try:
        yield name
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {name}"))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE {table} SET note = 'แก้แล้ว'",
        "DELETE FROM {table}",
        "TRUNCATE {table}",
    ],
    ids=["update", "delete", "truncate"],
)
async def test_partition_is_closed_for_runtime_roles(
    api_engine: AsyncEngine, partitioned_append_only_table: str, statement: str
) -> None:
    """สั่งที่พาร์ทิชันตรง ๆ ด้วยบทบาททำงานปกติ ก็ไม่ได้ — สิทธิ์ของพาร์ทิชันถูกตัดด้วย"""
    partition = f"{partitioned_append_only_table}_{datetime.now(UTC):%Y_%m}"
    async with api_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(statement.format(table=partition)))
    assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


async def test_truncate_on_partition_is_closed_for_the_owner_too(
    migrator_engine: AsyncEngine, partitioned_append_only_table: str
) -> None:
    """ช่องที่กลไกรุ่นแรกเปิดไว้ — trigger ระดับ statement ไม่ถูกโคลนไปพาร์ทิชัน"""
    partition = f"{partitioned_append_only_table}_{datetime.now(UTC):%Y_%m}"
    async with migrator_engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(f"TRUNCATE {partition}"))
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY


async def test_partition_made_by_hand_is_protected_automatically(
    migrator_engine: AsyncEngine,
) -> None:
    """V-7.1 — พาร์ทิชันที่สร้างด้วยมือถูกปิดให้เองด้วย event trigger

    ก่อน migration 0006 เทสต์นี้กลับด้าน: พาร์ทิชันที่ไม่ผ่านฟังก์ชันที่กำหนดจะหลุด
    และกฎบังคับด้วยการรีวิวเท่านั้น ตอนนี้กลไกบังคับให้เอง

    **ขอบเขต:** กันความผิดพลาดของคนทำงานปกติ ไม่ใช่รับประกันป้องกัน superuser
    ซึ่งปิด event trigger ได้ (RQ-20)
    """
    name = f"test_manual_part_{uuid4().hex[:8]}"
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                f"CREATE TABLE {name} ("
                " id uuid NOT NULL,"
                " owner_user_id uuid NOT NULL,"
                " recorded_at timestamptz NOT NULL DEFAULT now(),"
                f" CONSTRAINT {name}_pkey PRIMARY KEY (recorded_at, id)"
                ") PARTITION BY RANGE (recorded_at)"
            )
        )
        await connection.execute(
            text(f"SELECT tiewtrade_apply_owner_policy('{name}'::regclass, 'owner_user_id')")
        )
        await connection.execute(text(f"SELECT tiewtrade_make_append_only('{name}'::regclass)"))
        # สร้างพาร์ทิชันด้วยมือ ไม่ผ่าน tiewtrade_create_monthly_partition
        await connection.execute(
            text(
                f"CREATE TABLE {name}_manual PARTITION OF {name}"
                " FOR VALUES FROM ('2080-01-01') TO ('2080-02-01')"
            )
        )
    try:
        await _assert_partition_is_locked_down(migrator_engine, f"{name}_manual")
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {name}"))


async def test_attached_partition_is_protected_automatically(
    migrator_engine: AsyncEngine,
) -> None:
    """V-7.2 — `ATTACH PARTITION` ก็ถูกปิดให้เอง

    เส้นทางนี้ต่างจากการสร้างพาร์ทิชันตรง ๆ เพราะตารางเกิดก่อนแล้วค่อยผูกเข้าไป
    ถ้าดักแต่ `CREATE TABLE` ช่องนี้จะยังเปิดอยู่
    """
    name = f"test_attach_{uuid4().hex[:8]}"
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                f"CREATE TABLE {name} ("
                " id uuid NOT NULL,"
                " owner_user_id uuid NOT NULL,"
                " recorded_at timestamptz NOT NULL DEFAULT now(),"
                f" CONSTRAINT {name}_pkey PRIMARY KEY (recorded_at, id)"
                ") PARTITION BY RANGE (recorded_at)"
            )
        )
        await connection.execute(
            text(f"SELECT tiewtrade_apply_owner_policy('{name}'::regclass, 'owner_user_id')")
        )
        await connection.execute(text(f"SELECT tiewtrade_make_append_only('{name}'::regclass)"))
        await connection.execute(
            text(
                f"CREATE TABLE {name}_loose ("
                " id uuid NOT NULL,"
                " owner_user_id uuid NOT NULL,"
                " recorded_at timestamptz NOT NULL DEFAULT now()"
                ")"
            )
        )
        await connection.execute(
            text(
                f"ALTER TABLE {name} ATTACH PARTITION {name}_loose"
                " FOR VALUES FROM ('2082-01-01') TO ('2082-02-01')"
            )
        )
    try:
        await _assert_partition_is_locked_down(migrator_engine, f"{name}_loose")
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {name}"))
            await connection.execute(text(f"DROP TABLE IF EXISTS {name}_loose"))


async def test_ddl_is_rolled_back_when_protection_cannot_be_applied(
    migrator_engine: AsyncEngine,
) -> None:
    """V-7.3 — ตั้งการป้องกันไม่สำเร็จ → DDL ถูกยกเลิกทั้งคำสั่ง

    ใช้ตารางแม่ที่มี policy รูปแบบที่ตัวคัดลอกยังไม่รองรับ (เฉพาะ `FOR SELECT`)
    ผลที่ต้องได้คือ **ไม่มีพาร์ทิชันเกิดขึ้นเลย** ไม่ใช่เกิดแบบไม่มีการป้องกัน
    """
    name = f"test_rollback_{uuid4().hex[:8]}"
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                f"CREATE TABLE {name} ("
                " id uuid NOT NULL,"
                " owner_user_id uuid NOT NULL,"
                " recorded_at timestamptz NOT NULL DEFAULT now(),"
                f" CONSTRAINT {name}_pkey PRIMARY KEY (recorded_at, id)"
                ") PARTITION BY RANGE (recorded_at)"
            )
        )
        await connection.execute(text(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY"))
        await connection.execute(
            text(
                f"CREATE POLICY only_reading ON {name}"
                " FOR SELECT USING (owner_user_id = tiewtrade_current_user_id())"
            )
        )
        await connection.execute(text(f"SELECT tiewtrade_make_append_only('{name}'::regclass)"))

    try:
        async with migrator_engine.begin() as connection:
            with pytest.raises(Exception) as caught:
                await connection.execute(
                    text(
                        f"CREATE TABLE {name}_child PARTITION OF {name}"
                        " FOR VALUES FROM ('2083-01-01') TO ('2083-02-01')"
                    )
                )
        assert sqlstate_of(caught.value) == "TT003"

        async with migrator_engine.connect() as connection:
            exists: bool = (
                await connection.execute(
                    text("SELECT count(*) > 0 FROM pg_class WHERE relname = :name"),
                    {"name": f"{name}_child"},
                )
            ).scalar_one()
        assert not exists, "พาร์ทิชันเกิดขึ้นทั้งที่ตั้งการป้องกันไม่สำเร็จ"
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {name}"))


async def test_existing_database_can_be_repaired(migrator_engine: AsyncEngine) -> None:
    """V-7.4 — ซ่อมฐานข้อมูลที่มีพาร์ทิชันซึ่งยังไม่ถูกปิดได้

    เป็นเส้นทางของฐานข้อมูลที่ bootstrap ไปก่อนมีกลไกนี้ จำลองด้วยการถอด
    การป้องกันของพาร์ทิชันหนึ่งออก แล้วเรียกฟังก์ชันซ่อม
    """
    async with migrator_engine.begin() as connection:
        partition: str = (
            await connection.execute(
                text(
                    "SELECT inhrelid::regclass::text FROM pg_inherits"
                    " WHERE inhparent = 'audit_events'::regclass"
                    " ORDER BY inhrelid::regclass::text LIMIT 1"
                )
            )
        ).scalar_one()
        await connection.execute(
            text(f"DROP TRIGGER tiewtrade_append_only_statement ON {partition}")
        )

    async with migrator_engine.connect() as connection:
        listed: set[str] = set(
            (
                await connection.execute(
                    text("SELECT table_name FROM tiewtrade_append_only_tables")
                )
            ).scalars()
        )
    assert partition not in listed, "ถอดการป้องกันไม่สำเร็จ เทสต์นี้จึงไม่ได้ทดสอบอะไร"

    async with migrator_engine.begin() as connection:
        repaired: int = (
            await connection.execute(text("SELECT tiewtrade_protect_all_partitions()"))
        ).scalar_one()
    assert repaired >= 1

    await _assert_partition_is_locked_down(migrator_engine, partition)


async def test_event_trigger_is_installed(migrator_engine: AsyncEngine) -> None:
    """V-7.4 — ถ้า event trigger หายไป กลไกนี้ก็หายไปทั้งหมดโดยไม่มีอะไรเตือน"""
    async with migrator_engine.connect() as connection:
        enabled: str | None = (
            await connection.execute(
                text(
                    "SELECT evtenabled::text FROM pg_event_trigger"
                    " WHERE evtname = 'tiewtrade_protect_partitions'"
                )
            )
        ).scalar_one_or_none()
    assert enabled == "O", f"event trigger ไม่ได้ทำงานอยู่ (สถานะ {enabled!r})"


async def _assert_partition_is_locked_down(engine: AsyncEngine, partition: str) -> None:
    """พาร์ทิชันต้องได้ทั้ง append-only และ RLS/policy ครบ ไม่ใช่อย่างใดอย่างหนึ่ง"""
    async with engine.connect() as connection:
        listed: set[str] = set(
            (
                await connection.execute(
                    text("SELECT table_name FROM tiewtrade_append_only_tables")
                )
            ).scalars()
        )
        has_policy: bool = (
            await connection.execute(
                text("SELECT count(*) > 0 FROM pg_policy WHERE polrelid = CAST(:name AS regclass)"),
                {"name": partition},
            )
        ).scalar_one()
        forced: bool = (
            await connection.execute(
                text(
                    "SELECT relforcerowsecurity FROM pg_class WHERE oid = CAST(:name AS regclass)"
                ),
                {"name": partition},
            )
        ).scalar_one()

    assert partition in listed, f"{partition} ไม่ได้เข้ากลไก append-only"
    assert has_policy, f"{partition} ไม่มี policy"
    assert forced, f"{partition} ไม่ได้บังคับ RLS กับเจ้าของตาราง"

    async with engine.begin() as connection:
        with pytest.raises(Exception) as caught:
            await connection.execute(text(f"TRUNCATE {partition}"))
    assert sqlstate_of(caught.value) == SQLSTATE_APPEND_ONLY
