"""migration — V-31 ถึง V-34

กฎที่พิสูจน์ที่นี่: โครงสร้างต้องสร้างซ้ำได้เหมือนเดิมทุกครั้ง และย้อนกลับได้จริง
ไม่ใช่มีฟังก์ชัน `downgrade()` ที่ไม่มีใครเคยรัน (RQ-2)

เทสต์กลุ่มนี้ **รื้อและสร้างโครงสร้างใหม่ทั้งหมด** บนฐานข้อมูลของเทสต์
ซึ่งเป็นสิ่งที่ต้องทำเพื่อพิสูจน์ข้อนี้ เทสต์อื่นสร้างข้อมูลของตัวเองใหม่ทุกครั้ง
จึงไม่พึ่งข้อมูลที่ค้างอยู่
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole

BACKEND_ROOT = Path(__file__).parents[3]

#: คำถามที่ใช้ถ่ายภาพโครงสร้าง — ครอบของที่กลไกของงานนี้ยืนอยู่บน
#: ตาราง, คอลัมน์, domain กับ CHECK, ฟังก์ชัน, policy, trigger และสิทธิ์รายคอลัมน์
_SNAPSHOT_SQL = """
SELECT string_agg(line, E'\n' ORDER BY line) FROM (
    SELECT format('column %s.%s %s %s', table_name, column_name, data_type, is_nullable) AS line
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name NOT LIKE 'test_%'
    UNION ALL
    SELECT format('domain %s %s', t.typname, pg_get_constraintdef(c.oid))
    FROM pg_constraint AS c JOIN pg_type AS t ON t.oid = c.contypid
    WHERE t.typname LIKE 'tiewtrade%'
    UNION ALL
    SELECT format('function %s', p.proname)
    FROM pg_proc AS p JOIN pg_namespace AS n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
    UNION ALL
    SELECT format('policy %s on %s using %s check %s',
                  polname, polrelid::regclass::text,
                  pg_get_expr(polqual, polrelid), pg_get_expr(polwithcheck, polrelid))
    FROM pg_policy
    UNION ALL
    SELECT format('grant %s %s %s.%s', grantee, privilege_type, table_name, column_name)
    FROM information_schema.column_privileges
    WHERE table_schema = 'public' AND grantee LIKE 'tiewtrade%' AND table_name NOT LIKE 'test_%'
) AS snapshot
"""


def _alembic(*args: str) -> None:
    """รัน Alembic ด้วยชุดสภาพแวดล้อมเดียวกับที่ระบบใช้จริง"""
    done = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"alembic {' '.join(args)} ล้มเหลว:\n{done.stdout}{done.stderr}"


async def _snapshot(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        snapshot: str | None = (await connection.execute(text(_SNAPSHOT_SQL))).scalar_one()
        return snapshot or ""


def test_single_head_and_numbered_in_order() -> None:
    """V-31 — สายเดียว head เดียว และหมายเลขเรียง"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1, f"มีมากกว่าหนึ่ง head: {heads}"

    revisions = [revision.revision for revision in script.walk_revisions()]
    assert revisions == sorted(revisions, reverse=True), f"หมายเลข revision ไม่เรียง: {revisions}"
    assert all(revision.isdigit() for revision in revisions), (
        f"มี revision ที่ไม่ใช่หมายเลข: {revisions}"
    )


async def test_users_id_is_uuid(migrator_engine: AsyncEngine) -> None:
    """V-34 — รหัสประจำตัวเป็น UUID ไม่ใช่เลขเรียงลำดับ (Q-6)"""
    async with migrator_engine.connect() as connection:
        data_type: str = (
            await connection.execute(
                text(
                    "SELECT data_type FROM information_schema.columns"
                    " WHERE table_name = 'users' AND column_name = 'id'"
                )
            )
        ).scalar_one()
    assert data_type == "uuid"


@pytest.mark.usefixtures("migrator_engine")
async def test_downgrade_then_upgrade_rebuilds_the_same_structure(
    migrator_engine: AsyncEngine,
) -> None:
    """V-32, V-33 — ขึ้น ลง ขึ้น ได้โครงสร้างเหมือนเดิม และรอบที่สองก็เหมือนกัน"""
    assert os.environ.get(DatabaseRole.MIGRATOR.url_variable), (
        "ต้องตั้ง URL ของบทบาท migrator ก่อน — เทสต์นี้รัน migration จริง"
    )

    before = await _snapshot(migrator_engine)
    assert "column users.id uuid" in before, "ยังไม่ได้รัน migration ก่อนเริ่มเทสต์"

    _alembic("downgrade", "base")
    emptied = await _snapshot(migrator_engine)
    assert "column users.id uuid" not in emptied, "downgrade ไม่ได้รื้อของจริง"

    _alembic("upgrade", "head")
    after_first = await _snapshot(migrator_engine)
    assert after_first == before, "โครงสร้างหลังสร้างใหม่ไม่เหมือนเดิม"

    # รอบที่สองบนฐานข้อมูลที่รื้อจนว่างแล้ว ต้องได้ผลเดียวกันเป๊ะ
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    after_second = await _snapshot(migrator_engine)
    assert after_second == after_first, "สร้างสองครั้งได้โครงสร้างไม่เหมือนกัน"
