"""เวลาสร้างแถว — V-28 ถึง V-30

เจ้าของระบุว่า **ค่าปริยายของคอลัมน์อย่างเดียวไม่พอ** (Q-9) เพราะค่าปริยายกันแค่กรณี
ที่ไม่ส่งค่ามา ไม่กันกรณีที่ส่งค่าผิดมา งานนี้จึงบังคับด้วยสิทธิ์ระดับคอลัมน์
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import NotPermittedError, user_session
from tiewtrade.infra.users import create_user, fetch_user

#: เวลาในอดีตที่ผู้เรียกพยายามใส่ทับ — ถ้าใส่ได้ ลำดับเหตุการณ์ในระบบก็เชื่อถือไม่ได้
FORGED_TIME = datetime(1999, 1, 1, tzinfo=UTC)


async def test_column_is_timestamptz_and_value_is_utc(api_engine: AsyncEngine) -> None:
    """V-28 — เก็บเป็น TIMESTAMPTZ และค่าที่อ่านกลับผูกกับ UTC"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with api_engine.connect() as connection:
        column_type: str = (
            await connection.execute(
                text(
                    "SELECT data_type FROM information_schema.columns"
                    " WHERE table_name = 'users' AND column_name = 'created_at'"
                )
            )
        ).scalar_one()

    async with user_session(api_engine, user_id) as session:
        row = await fetch_user(session, user_id)

    assert column_type == "timestamp with time zone"
    assert row is not None
    assert row.created_at.tzinfo is not None, "เวลาที่อ่านกลับไม่มี timezone ติดมา"
    assert row.created_at.utcoffset() == timedelta(0), "เวลาที่อ่านกลับไม่ได้อยู่ในเขต UTC"
    assert row.created_at <= datetime.now(UTC)


async def test_runtime_role_cannot_set_created_at(api_engine: AsyncEngine) -> None:
    """V-29 — ใส่เวลาสร้างเองไม่ได้ ถูกปฏิเสธ ไม่ใช่ถูกเมิน"""
    user_id = uuid4()
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "INSERT INTO users (id, created_at) VALUES (:id, :created_at)",
                {"id": str(user_id), "created_at": FORGED_TIME},
            )

    async with api_engine.connect() as connection:
        count: int = (
            await connection.execute(
                text("SELECT count(*) FROM users WHERE id = :id"), {"id": str(user_id)}
            )
        ).scalar_one()
    assert count == 0, "แถวถูกเขียนลงไปทั้งที่คำสั่งควรถูกปฏิเสธ"


async def test_runtime_role_cannot_change_created_at(api_engine: AsyncEngine) -> None:
    """V-30 — แก้เวลาสร้างของแถวเดิมไม่ได้"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with user_session(api_engine, user_id) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "UPDATE users SET created_at = :created_at WHERE id = :id",
                {"id": str(user_id), "created_at": FORGED_TIME},
            )
