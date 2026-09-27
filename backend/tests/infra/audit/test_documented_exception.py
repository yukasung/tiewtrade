"""ข้อยกเว้นเรื่องอายุข้อมูลต้องเขียนไว้ให้คนเห็น — V-34, V-35

เจ้าของระบุว่าการไม่กำหนดอายุข้อมูลเป็น **ข้อยกเว้นชั่วคราวจากมาตรฐาน**
ไม่ใช่การตีความว่ามาตรฐานอนุญาต (RQ-21) ข้อยกเว้นที่ไม่มีใครเห็นจะกลายเป็น
ของถาวรโดยไม่มีใครตัดสินใจ เทสต์นี้จึงตรวจว่ามันถูกเขียนไว้จริงทั้งสองที่
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

REPO_ROOT = Path(__file__).parents[4]


async def test_table_comment_records_the_exception(migrator_engine: AsyncEngine) -> None:
    """V-34 — หัวตารางบอกว่าเป็นข้อยกเว้นชั่วคราว และชี้ไปที่มาตรฐานข้อที่เกี่ยวข้อง"""
    async with migrator_engine.connect() as connection:
        comment: str = (
            await connection.execute(
                text("SELECT obj_description('audit_events'::regclass, 'pg_class')")
            )
        ).scalar_one()

    assert "ข้อยกเว้นชั่วคราว" in comment
    assert "database.md" in comment
    assert "RQ-21" in comment


def test_roadmap_gates_the_retention_decision() -> None:
    """V-35 — เงื่อนไขก่อนเปิดให้คนนอกใช้อยู่ใน roadmap ไม่ใช่อยู่แต่ในหัวใครคนหนึ่ง"""
    roadmap = (REPO_ROOT / "specs" / "roadmap.md").read_text(encoding="utf-8")
    assert "นโยบายเก็บข้อมูลของ audit log" in roadmap
    assert "ข้อยกเว้นชั่วคราว" in roadmap
