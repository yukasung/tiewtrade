"""ของกลางของเทสต์ยืนยันตัวตนที่แตะฐานข้อมูล (F-05)"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth import (
    create_credential,
    deadlines_for_new_session,
    hash_password,
    issue,
    new_token,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import user_session
from tiewtrade.infra.users import create_user_in

#: รหัสผ่านที่ผ่านกฎและไม่อยู่ในรายการที่ห้าม
GOOD_PASSWORD: Final[str] = "รหัสผ่านที่ยาวพอใช้งานจริง"


def fresh_bucket_key() -> str:
    """คีย์ของถังที่ไม่ซ้ำกับเทสต์อื่น

    ต้องเป็นแฮช 64 ตัวอักษรตาม `CHECK` ของ `auth_throttle` — ใช้ค่าสุ่มแทนการแฮช
    ของจริง เพราะเทสต์ของถังไม่สนใจว่าแฮชมาจากอะไร สนใจแค่ว่าคีย์ไม่ชนกัน
    """
    return f"{uuid4().hex}{uuid4().hex}"


def unique_email() -> str:
    """อีเมลที่ไม่ซ้ำ — ฐานข้อมูลของเทสต์ใช้ร่วมกันทั้งชุด"""
    return f"f05-{uuid4().hex}@example.com"


async def make_account(
    auth_engine: AsyncEngine,
    *,
    email: str | None = None,
    password: str = GOOD_PASSWORD,
) -> tuple[UUID, str]:
    """สร้างผู้ใช้พร้อมข้อมูลเข้าสู่ระบบในก้อนเดียว — คืนรหัสผู้ใช้กับอีเมล"""
    user_id = uuid4()
    used = email if email is not None else unique_email()
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await create_user_in(session, user_id)
        await create_credential(session, user_id, email=used, password_hash=hash_password(password))
    return user_id, used


async def issue_session_for(
    auth_engine: AsyncEngine,
    user_id: UUID,
    *,
    now: datetime | None = None,
    expired: bool = False,
) -> str:
    """ออก session ให้ผู้ใช้ที่มีอยู่แล้ว — คืนแฮชโทเคน

    `expired=True` ออกใบที่หมดอายุไปแล้ว **โดยไม่ต้องแก้แถวทีหลัง** เพราะตารางใช้
    `FORCE ROW LEVEL SECURITY` จึงไม่มีบทบาทไหนแก้แถวข้ามเงื่อนไข policy ได้
    แม้แต่เจ้าของโครงสร้าง — การแก้ด้วย migrator ได้ศูนย์แถวแบบเงียบ ๆ
    """
    moment = now if now is not None else datetime.now(UTC)
    _, token_hash = new_token()
    deadlines = deadlines_for_new_session(moment)
    idle = moment - timedelta(seconds=1) if expired else deadlines.idle_expires_at
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await issue(
            session,
            token_hash=token_hash,
            idle_expires_at=idle,
            absolute_expires_at=deadlines.absolute_expires_at,
        )
    return token_hash


async def account_with_session(auth_engine: AsyncEngine) -> tuple[UUID, str]:
    """ผู้ใช้ใหม่หนึ่งคนที่มี session หนึ่งใบ — คืนรหัสผู้ใช้กับแฮชโทเคน"""
    user_id, _ = await make_account(auth_engine)
    return user_id, await issue_session_for(auth_engine, user_id)
