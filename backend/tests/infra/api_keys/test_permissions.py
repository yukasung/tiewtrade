"""สิทธิ์ของตาราง `user_api_keys` — V-1, V-2, V-3 และรูปร่างที่ฐานข้อมูลบังคับ

**ทั้งไฟล์รันกับ PostgreSQL จริงด้วยบทบาทจริง** เพราะสิ่งที่พิสูจน์คือสิทธิ์รายคอลัมน์
กับ RLS ซึ่งเป็นความสามารถของ PostgreSQL เอง — ของปลอมพิสูจน์อะไรไม่ได้เลย
(`validation.md` หัวข้อ "สิทธิ์ฐานข้อมูล")

สิ่งที่ไฟล์นี้ปกป้องคือข้อที่ทั้ง F-07 ตั้งอยู่บน: **`api` เก็บความลับลงไปได้
แต่อ่านกลับไม่ได้** ถ้าข้อนี้พัง การแยก process ทั้งหมดก็ไม่เหลือความหมาย
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, NotPermittedError, user_session
from tiewtrade.infra.db.errors import (
    SQLSTATE_INSUFFICIENT_PRIVILEGE,
    DuplicateValueError,
    sqlstate_of,
)
from tiewtrade.infra.users import create_user

#: ค่าที่ปิดผนึกจำลอง — ไม่ใช่ความลับจริง และไม่ต้องเปิดผนึกได้
SEALED = b"sealed-bytes-for-tests"


async def _add_key(engine: AsyncEngine, user_id: UUID, *, label: str = "key") -> UUID:
    """เพิ่มแถวแบบที่ `api` ทำจริง — ผ่านบทบาทและ policy เดียวกับของจริง"""
    key_id = uuid4()
    async with user_session(engine, user_id) as session:
        await session.execute(
            "INSERT INTO user_api_keys"
            " (id, user_id, label, key_public, secret_sealed, key_version, status)"
            " VALUES (:id, :user_id, :label, :public, :sealed, '1', 'PENDING')",
            {
                "id": key_id,
                "user_id": user_id,
                "label": label,
                "public": "PUBLIC1234",
                "sealed": SEALED,
            },
        )
    return key_id


#: คอลัมน์ที่ `api` ต้องเขียนได้แต่อ่านกลับไม่ได้
#:
#: **ต้องตรวจทีละคอลัมน์** ไม่ใช่ตรวจแค่ `SELECT *` — ตอนลองเปิดสิทธิ์ `secret_sealed`
#: เพื่อพิสูจน์ว่าเทสต์จับได้จริง พบว่า `SELECT *` ยังแดงอยู่เพราะ `key_version`
#: ยังอ่านไม่ได้ นั่นแปลว่ามันผ่านด้วยเหตุผลที่ไม่ใช่สิ่งที่ตั้งใจตรวจ
SECRET_COLUMNS = ("secret_sealed", "key_version")


@pytest.mark.parametrize("column", SECRET_COLUMNS)
async def test_api_can_store_a_secret_it_cannot_read_back(
    api_engine: AsyncEngine, column: str
) -> None:
    """V-1 — `api` เขียนค่าที่ปิดผนึกลงไปได้ **แต่อ่านคอลัมน์นั้นไม่ได้**

    นี่คือ "รับมาเพื่อเข้ารหัสทันทีแล้วส่งต่อ" ของ `tech-stack.md` หัวข้อ 8
    ในรูปของสิทธิ์ฐานข้อมูล ไม่ใช่ในรูปของวินัยการเขียนโค้ด
    """
    owner = uuid4()
    await create_user(api_engine, owner)
    await _add_key(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(f"SELECT {column} FROM user_api_keys")


async def test_api_select_star_fails_rather_than_returning_the_secret(
    api_engine: AsyncEngine,
) -> None:
    """V-1 — `SELECT *` ของ `api` ต้อง **ล้ม** ไม่ใช่คืนความลับมาเงียบ ๆ

    เขียนเป็นเทสต์แยกเพราะ `SELECT *` คือรูปที่คนเขียนผิดได้ง่ายที่สุด
    และถ้ามันผ่าน ความลับจะไหลออกโดยไม่มีใครเห็นว่าเกิดอะไรขึ้น
    """
    owner = uuid4()
    await create_user(api_engine, owner)
    await _add_key(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("SELECT * FROM user_api_keys")


async def test_api_reads_the_columns_the_screen_needs(api_engine: AsyncEngine) -> None:
    """V-1 — สิ่งที่หน้าจอต้องใช้ยังอ่านได้ตามปกติ

    มีไว้พิสูจน์ว่าเทสต์สองข้อบนไม่ได้ผ่านเพราะบทบาทนี้อ่านอะไรไม่ได้เลย
    """
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _add_key(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        result = await session.execute(
            "SELECT id, label, key_public, status, not_before, next_attempt_at FROM user_api_keys"
        )
        rows = [dict(row) for row in result.mappings().all()]

    assert [row["id"] for row in rows] == [key_id]
    assert rows[0]["status"] == "PENDING"
    assert rows[0]["key_public"] == "PUBLIC1234"


async def test_scan_role_cannot_read_the_secret(scan_engine: AsyncEngine) -> None:
    """V-2 — บทบาทที่ข้าม RLS ได้ **ต้องไม่เห็นความลับของใครเลย**

    บทบาทนี้มีไว้หาแถวที่ต้องตรวจข้ามผู้ใช้ (F-03 Q-3) ถ้ามันอ่านความลับได้
    ก็เท่ากับเปิดความลับของผู้ใช้ทุกคนให้ process เดียว ซึ่งลบความหมายของ
    การแยกบทบาททั้งหมดทิ้ง
    """
    for column in SECRET_COLUMNS:
        async with scan_engine.connect() as connection:
            with pytest.raises(Exception) as caught:
                await connection.execute(text(f"SELECT {column} FROM user_api_keys"))
        assert sqlstate_of(caught.value) == SQLSTATE_INSUFFICIENT_PRIVILEGE


async def test_scan_role_reads_what_it_needs_across_users(
    api_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    """V-2 — แต่ยังหาแถวที่ต้องตรวจข้ามผู้ใช้ได้ ซึ่งเป็นงานของมัน"""
    first, second = uuid4(), uuid4()
    await create_user(api_engine, first)
    await create_user(api_engine, second)
    await _add_key(api_engine, first)
    await _add_key(api_engine, second)

    async with scan_engine.connect() as connection:
        seen: list[UUID] = list(
            (
                await connection.execute(
                    text("SELECT user_id FROM user_api_keys WHERE status = 'PENDING'")
                )
            ).scalars()
        )

    assert {first, second} <= set(seen)


async def test_engine_reads_and_the_secret_survives_the_round_trip(
    api_engine: AsyncEngine, engine_engine: AsyncEngine
) -> None:
    """V-3 — `engine` อ่านค่าที่ปิดผนึกได้ และได้ค่าเดิมที่ `api` เขียนไว้"""
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _add_key(api_engine, owner)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        stored = (
            await session.execute(
                "SELECT secret_sealed FROM user_api_keys WHERE id = :id", {"id": key_id}
            )
        ).scalar_one()

    assert bytes(stored) == SEALED


async def test_api_cannot_write_the_verdict(api_engine: AsyncEngine) -> None:
    """V-31.2 — ผลการตรวจเป็นของ `engine` เท่านั้น

    ถ้า `api` เขียนสถานะได้ คำขอจากอินเทอร์เน็ตก็ประกาศว่า key ผ่านการตรวจได้
    โดยไม่เคยถามตลาดเลย
    """
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _add_key(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "UPDATE user_api_keys SET status = 'ACTIVE' WHERE id = :id", {"id": key_id}
            )


async def test_api_may_ask_for_a_retry(api_engine: AsyncEngine) -> None:
    """V-31.1 — ปุ่มลองใหม่เขียนช่องเดียวของมันได้จริงด้วยบทบาทจริง

    เทสต์นี้มีไว้จับความไม่ตรงกันระหว่าง "สิ่งที่ endpoint เขียน" กับ "สิ่งที่บทบาท
    มีสิทธิ์เขียน" ซึ่งเป็นความผิดพลาดที่เงียบจนกว่าจะมีผู้ใช้จริงมากดปุ่ม
    """
    owner = uuid4()
    await create_user(api_engine, owner)
    key_id = await _add_key(api_engine, owner)

    async with user_session(api_engine, owner) as session:
        await session.execute(
            "UPDATE user_api_keys SET retry_requested_at = clock_timestamp() WHERE id = :id",
            {"id": key_id},
        )
        requested = (
            await session.execute(
                "SELECT retry_requested_at FROM user_api_keys WHERE id = :id", {"id": key_id}
            )
        ).scalar_one()

    assert requested is not None


async def test_other_users_key_is_not_found(api_engine: AsyncEngine) -> None:
    """V-28 — ขอ key ของคนอื่นได้ "ไม่พบ" ไม่ใช่ "ไม่มีสิทธิ์" (RQ-10)"""
    owner, stranger = uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, stranger)
    hidden = await _add_key(api_engine, stranger)

    async with user_session(api_engine, owner) as session:
        found = list(
            (
                await session.execute("SELECT id FROM user_api_keys WHERE id = :id", {"id": hidden})
            ).scalars()
        )

    assert found == []


async def test_label_is_unique_per_user_in_the_database(api_engine: AsyncEngine) -> None:
    """V-31 — ชื่อซ้ำถูกปฏิเสธโดยฐานข้อมูล ไม่ใช่ด้วยเงื่อนไขในโค้ดอย่างเดียว"""
    owner = uuid4()
    await create_user(api_engine, owner)
    await _add_key(api_engine, owner, label="หลัก")

    with pytest.raises(DuplicateValueError):
        await _add_key(api_engine, owner, label="หลัก")


async def test_two_users_may_use_the_same_label(api_engine: AsyncEngine) -> None:
    """ชื่อซ้ำ **ข้ามผู้ใช้** ต้องได้ — ชื่อเป็นของผู้ใช้ ไม่ใช่ของระบบ"""
    first, second = uuid4(), uuid4()
    await create_user(api_engine, first)
    await create_user(api_engine, second)

    await _add_key(api_engine, first, label="หลัก")
    await _add_key(api_engine, second, label="หลัก")
