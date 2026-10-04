"""ลบแถวที่ไม่มีผลอะไรแล้วจากตารางของการยืนยันตัวตน — **คนสั่งเอง** (F-06 plan.md 1.5)

ปิดหนี้ที่ `roadmap.md` บันทึกไว้ตั้งแต่ F-05 ว่า `auth_throttle` ไม่มีการลบแถวเก่า
และครอบ `login_challenges` ที่ F-06 เพิ่มเข้ามาด้วย

เรียกใช้:

```sh
uv run python scripts/sweep_auth_tables.py            # ลบจริง
uv run python scripts/sweep_auth_tables.py --dry-run  # บอกว่าจะลบเท่าไรโดยไม่ลบ
```

**ยังไม่มีตัวตั้งเวลาให้** — การตั้งเวลาบนเครื่องจริงเป็นงาน **F-31** พร้อมกับเรื่อง
กุญแจเข้ารหัส (T-03) · ก่อนปล่อยผู้ใช้จริงต้องมีตัวตั้งเวลาเรียกสคริปต์นี้

**ห้ามลบแถวที่ยังมีผลจำกัดการเดา** — เงื่อนไขนี้อยู่ในตัว `sweep()` ไม่ใช่ในสคริปต์
ฉะนั้นทางเรียกอื่นก็ได้กฎเดียวกัน
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from tiewtrade.infra.auth.cleanup import sweep
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session


async def run(*, dry_run: bool) -> int:
    """เก็บกวาดหนึ่งรอบ — คืนจำนวนแถวที่ลบ (หรือที่จะลบเมื่อ `--dry-run`)"""
    engine = create_engine_for(DatabaseRole.AUTH)
    try:
        async with presented_session(engine, role=DatabaseRole.AUTH) as session:
            swept = await sweep(session, now=datetime.now(UTC))
            if dry_run:
                # ยกเลิก transaction ด้วยข้อผิดพลาดของเราเอง เพื่อให้ `--dry-run`
                # ใช้คำสั่งชุดเดียวกับของจริง ไม่ใช่คำสั่งนับที่อาจไม่ตรงกัน
                raise _RehearsalError(swept.throttle_rows, swept.challenge_rows)
            print(  # noqa: T201 - สคริปต์ที่คนสั่งเอง รายงานผลทาง stdout เหมือน F-05
                f"ลบแล้ว: ตัวนับอัตราการเรียก {swept.throttle_rows} แถว,"
                f" challenge {swept.challenge_rows} แถว"
            )
            return swept.total
    except _RehearsalError as rehearsal:
        print(  # noqa: T201
            f"จะลบ: ตัวนับอัตราการเรียก {rehearsal.throttle_rows} แถว,"
            f" challenge {rehearsal.challenge_rows} แถว (ยังไม่ลบ)"
        )
        return rehearsal.throttle_rows + rehearsal.challenge_rows
    finally:
        await engine.dispose()


class _RehearsalError(Exception):
    """พาจำนวนแถวออกมาแล้วย้อน transaction — ใช้เฉพาะ `--dry-run`"""

    def __init__(self, throttle_rows: int, challenge_rows: int) -> None:
        super().__init__("dry run")
        self.throttle_rows = throttle_rows
        self.challenge_rows = challenge_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="บอกว่าจะลบเท่าไรโดยไม่ลบ")
    arguments = parser.parse_args()
    asyncio.run(run(dry_run=arguments.dry_run))


if __name__ == "__main__":
    main()
