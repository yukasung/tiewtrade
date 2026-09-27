"""ตัวเชื่อม Alembic กับฐานข้อมูล (F-03, plan.md ข้อ 2)

**ไม่ใช้ autogenerate** เพราะ autogenerate ไม่รู้จัก RLS policy, GRANT, trigger
และ domain ซึ่งเป็นของที่กลไกทั้งงานนี้ยืนอยู่บน — จะได้ migration ที่ดูเหมือนครบ
แต่ทิ้งกลไกหายไปเงียบ ๆ ทุก revision จึงเขียน SQL ด้วยมือ

URL มาจาก environment ของบทบาท `migrator` ซึ่งแยกจาก URL ของ service (RQ-5.1)

ใช้ driver ตัวเดียวกับที่ระบบใช้จริง (asyncpg) เพื่อไม่ต้องติดตั้ง driver ที่สอง
ซึ่งจะทำให้ migration ทดสอบเส้นทางที่ต่างจากที่ระบบใช้จริง
"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

#: ตัวแปรสภาพแวดล้อมที่เก็บ URL ของบทบาทที่รัน migration
MIGRATION_URL_ENV = "TIEWTRADE_DATABASE_URL_MIGRATOR"


def _migration_url() -> str:
    url = os.environ.get(MIGRATION_URL_ENV, "")
    if not url:
        raise RuntimeError(f"ไม่ได้ตั้ง {MIGRATION_URL_ENV} — migration ต้องรันด้วยบทบาท migrator เท่านั้น")
    return url


def _run(connection: Connection) -> None:
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_migration_url(), hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():  # pragma: no cover - ไม่ใช้โหมดนี้ในโปรเจกต์นี้
    raise RuntimeError("โปรเจกต์นี้ไม่ใช้ offline mode เพราะสิทธิ์และ RLS ต้องตรวจกับฐานข้อมูลจริง")

asyncio.run(_run_online())
