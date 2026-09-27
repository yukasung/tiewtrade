"""บันทึกอยู่รอดแม้ผู้ใช้หายไป — V-32

`trading-safety.md` หัวข้อ 9 ห้ามลบบันทึกย้อนหลัง ส่วน `security.md` หัวข้อ 5
บอกว่าต้องลบข้อมูลผู้ใช้ได้เมื่อผู้ใช้ขอ สองข้อนี้อยู่ด้วยกันได้เมื่อบันทึกอ้างผู้ใช้
ด้วยรหัสอย่างเดียว และ **ไม่ผูกความสัมพันธ์แบบลบต่อกัน** (RQ-17, Q-5)

คำตอบเรื่องการลบข้อมูลตามคำขอยังค้างที่ NC-11 เทสต์นี้ยืนยันแค่ว่างานนี้
ไม่ได้ปิดประตูทางนั้นไว้
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import CURRENT_USER_SETTING, user_session
from tiewtrade.infra.users import create_user


async def test_audit_events_survive_deleting_the_user_row(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    """V-32 — ลบแถวผู้ใช้แล้วบันทึกยังอยู่ครบ"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    # ลบแถวผู้ใช้ด้วยเจ้าของตาราง (ตาราง users ไม่ได้เปิดกลไก append-only)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config(:setting, :user_id, true)"),
            {"setting": CURRENT_USER_SETTING, "user_id": str(user_id)},
        )
        deleted = await connection.execute(
            text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)}
        )
    assert deleted.rowcount == 1, "ลบแถวผู้ใช้ไม่สำเร็จ เทสต์นี้จึงไม่ได้ทดสอบอะไร"

    async with user_session(api_engine, user_id) as session:
        result = await session.execute(
            "SELECT count(*) FROM audit_events WHERE owner_user_id = :id", {"id": str(user_id)}
        )
        remaining: int = result.scalar_one()

    assert remaining == 1, "บันทึกหายไปพร้อมกับแถวผู้ใช้ — ห้ามผูกแบบลบต่อกัน"


async def test_no_foreign_key_ties_events_to_users(migrator_engine: AsyncEngine) -> None:
    """V-32 — ยืนยันที่โครงสร้าง ไม่ใช่แค่ที่พฤติกรรม"""
    async with migrator_engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT conname FROM pg_constraint"
                " WHERE conrelid = 'audit_events'::regclass AND contype = 'f'"
            )
        )
        foreign_keys: list[str] = list(result.scalars())
    assert foreign_keys == [], "มี foreign key ที่ผูกบันทึกไว้กับตารางผู้ใช้"
