"""สิทธิ์ของฐานข้อมูลเป็นตัวกัน ไม่ใช่ความระวังของโค้ด — V-1 ถึง V-10.3

ทุกข้อในไฟล์นี้พิสูจน์ว่า **ฐานข้อมูลปฏิเสธเอง** ไม่ใช่ว่าโค้ดของเราเลี่ยงไม่ทำ
ถ้าเทสต์เหล่านี้ผ่านเพราะโค้ดไม่เรียก แปลว่าไม่ได้พิสูจน์อะไรเลย
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import (
    GOOD_PASSWORD,
    account_with_session,
    make_account,
    unique_email,
)
from tiewtrade.infra.auth import deadlines_for_new_session, hash_password, new_token
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import InfraError, NotPermittedError
from tiewtrade.infra.db.session import presented_session, user_session

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


async def test_api_cannot_issue_a_session(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-1 — บทบาทที่รับคำขอทั่วไปออก session ใหม่ไม่ได้

    นี่คือสิ่งที่ทำให้บั๊กแบบ SQL injection ใน endpoint ปกติปลอม session ไม่ได้
    """
    user_id, _ = await make_account(auth_engine)
    _, token_hash = new_token()
    deadlines = deadlines_for_new_session(datetime.now(UTC))
    async with user_session(api_engine, user_id, role=DatabaseRole.API) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "INSERT INTO sessions (token_hash, user_id, idle_expires_at,"
                " absolute_expires_at) VALUES (:h, :u, :i, :a)",
                {
                    "h": token_hash,
                    "u": str(user_id),
                    "i": deadlines.idle_expires_at,
                    "a": deadlines.absolute_expires_at,
                },
            )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("user_id", "11111111-1111-1111-1111-111111111111"),
        ("token_hash", "0" * 64),
        ("started_at", datetime(2020, 1, 1, tzinfo=UTC)),
        ("absolute_expires_at", datetime(2099, 1, 1, tzinfo=UTC)),
    ],
    ids=["เจ้าของ", "แฮชโทเคน", "เวลาเริ่ม", "เพดานรวม"],
)
async def test_api_cannot_change_the_columns_that_matter(
    api_engine: AsyncEngine, auth_engine: AsyncEngine, column: str, value: object
) -> None:
    """V-2 — เปลี่ยนเจ้าของ แฮชโทเคน เวลาเริ่ม หรือเพดานรวมไม่ได้

    ถ้าเปลี่ยนเจ้าของได้ ผู้ที่ถือ session ของตัวเองจะยึดบัญชีคนอื่นได้ทั้งที่ออก
    session ใหม่ไม่ได้
    """
    _, token_hash = await account_with_session(auth_engine)
    async with presented_session(
        api_engine, token_hash=token_hash, role=DatabaseRole.API
    ) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                f"UPDATE sessions SET {column} = :value WHERE token_hash = :h",
                {"value": value, "h": token_hash},
            )


async def test_api_sees_only_the_session_whose_token_it_holds(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-3 — รู้แฮชของคนอื่นก็อ่านไม่ได้ ถ้าไม่ได้ตั้งเป็นโทเคนที่ถือ"""
    _, mine = await account_with_session(auth_engine)
    _, theirs = await account_with_session(auth_engine)
    async with presented_session(api_engine, token_hash=mine, role=DatabaseRole.API) as session:
        rows = (
            await session.execute(
                "SELECT token_hash FROM sessions WHERE token_hash = :h", {"h": theirs}
            )
        ).all()
        assert rows == []


async def test_without_the_variable_nothing_is_visible_and_nothing_is_deleted(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-4 — ไม่ตั้งตัวแปรเลย → อ่านศูนย์แถวและลบศูนย์แถว (พลาดแบบปิดประตู)"""
    await account_with_session(auth_engine)
    async with presented_session(api_engine, role=DatabaseRole.API) as session:
        assert (await session.execute("SELECT count(*) FROM sessions")).one()[0] == 0
        result = await session.execute("DELETE FROM sessions")
        assert result.rowcount == 0  # type: ignore[attr-defined]


async def test_api_cannot_renew_past_the_absolute_cap(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-6 — เลื่อนเวลาหมดอายุเกินเพดานรวมไม่ได้ และ **ฐานข้อมูลเป็นผู้ปฏิเสธ**

    ปฏิเสธด้วยข้อผิดพลาด ไม่ใช่เงียบ ๆ แล้วไม่แก้แถว — เงื่อนไข `WITH CHECK`
    ของ policy ทำให้ PostgreSQL แจ้งว่าแถวใหม่ผิด policy
    """
    _, token_hash = await account_with_session(auth_engine)
    beyond = datetime.now(UTC) + timedelta(days=365)
    async with presented_session(
        api_engine, token_hash=token_hash, role=DatabaseRole.API
    ) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "UPDATE sessions SET idle_expires_at = :i WHERE token_hash = :h",
                {"i": beyond, "h": token_hash},
            )

    async with presented_session(api_engine, token_hash=token_hash, role=DatabaseRole.API) as after:
        stored = (
            await after.execute(
                "SELECT idle_expires_at FROM sessions WHERE token_hash = :h", {"h": token_hash}
            )
        ).one()[0]
        assert stored < beyond, "เวลาหมดอายุถูกเลื่อนเกินเพดานรวมได้"


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT email FROM user_credentials",
        "INSERT INTO user_credentials (user_id, email, password_hash) VALUES (:u, :e, :p)",
        "UPDATE user_credentials SET password_hash = :p",
        "DELETE FROM user_credentials",
    ],
    ids=["อ่าน", "เพิ่ม", "แก้", "ลบ"],
)
async def test_api_cannot_touch_credentials_at_all(
    api_engine: AsyncEngine, auth_engine: AsyncEngine, statement: str
) -> None:
    """V-7 — บทบาทที่รับคำขอทั่วไปแตะข้อมูลเข้าสู่ระบบไม่ได้เลยทุกคำสั่ง"""
    user_id, _ = await make_account(auth_engine)
    async with user_session(api_engine, user_id, role=DatabaseRole.API) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                statement,
                {"u": str(user_id), "e": unique_email(), "p": hash_password(GOOD_PASSWORD)},
            )


async def test_auth_reads_credentials_one_email_at_a_time(auth_engine: AsyncEngine) -> None:
    """V-8 — `SELECT` ครั้งเดียว dump ทั้งตารางไม่ได้ · ไม่ตั้งอีเมลก็ได้ศูนย์แถว"""
    _, email = await make_account(auth_engine)
    await make_account(auth_engine)

    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as blind:
        assert (await blind.execute("SELECT count(*) FROM user_credentials")).one()[0] == 0

    async with presented_session(auth_engine, email=email, role=DatabaseRole.AUTH) as seeing:
        rows = (await seeing.execute("SELECT email FROM user_credentials")).all()
        assert [row[0] for row in rows] == [email]


async def test_auth_cannot_change_the_email_or_renew_sessions(auth_engine: AsyncEngine) -> None:
    """V-10.3 — งานนี้ไม่เปลี่ยนอีเมล และการต่ออายุเป็นงานของบทบาทที่รับคำขอทั่วไป"""
    user_id, _ = await make_account(auth_engine)
    _, token_hash = await account_with_session(auth_engine)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "UPDATE user_credentials SET email = :e WHERE user_id = :u",
                {"e": unique_email(), "u": str(user_id)},
            )

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as another:
        with pytest.raises(NotPermittedError):
            await another.execute(
                "UPDATE sessions SET last_seen_at = now() WHERE token_hash = :h",
                {"h": token_hash},
            )


async def test_every_runtime_role_is_covered_by_the_append_only_rule(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-9 — กฎ "เพิ่มได้อย่างเดียว" ครอบ **ทุกบทบาทใน `DatabaseRole`** ไม่ใช่รายชื่อที่จำไว้

    `RUNTIME_ROLES` ใน migration แรกเป็นรายการที่เขียนมือ และห้ามแก้ migration ที่รันแล้ว
    บทบาทที่เพิ่มภายหลังจึงต้องถูกถอนสิทธิ์ใน migration ของตัวเอง — เทสต์นี้คือสิ่งที่
    ทำให้บทบาทที่เจ็ดในอนาคตลืมไม่ได้
    """
    covered = {DatabaseRole.API: api_engine, DatabaseRole.AUTH: auth_engine}
    assert covered.keys() >= {DatabaseRole.API, DatabaseRole.AUTH}

    # แยก session ต่อหนึ่งคำสั่ง เพราะคำสั่งที่ถูกปฏิเสธทำให้ transaction นั้นใช้ต่อไม่ได้
    for role, engine in covered.items():
        for statement in (
            "UPDATE audit_events SET action = 'USER_CREATED'",
            "DELETE FROM audit_events",
        ):
            async with user_session(engine, uuid4(), role=role) as session:
                with pytest.raises(NotPermittedError):
                    await session.execute(statement)
