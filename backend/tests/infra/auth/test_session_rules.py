"""กฎของ session — V-5, V-5.1, V-5.2, V-11 ถึง V-15

**รูปของคำสั่งเป็นส่วนหนึ่งของการออกแบบ** เทสต์ในไฟล์นี้จึงพิสูจน์จำนวนแถวที่ถูกลบจริง
ไม่ใช่พิสูจน์ว่าโค้ด "เรียกฟังก์ชันลบ"
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import issue_session_for, make_account
from tiewtrade.infra.auth import (
    ABSOLUTE_LIFETIME,
    IDLE_LIFETIME,
    end_all,
    end_one,
    end_others,
    owner_of_presented,
    renew,
    renewed_idle_deadline,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import presented_session, user_session


def test_the_lifetimes_are_the_ones_the_owner_decided() -> None:
    """V-5.2 — ไม่ใช้งาน 12 ชั่วโมง และเพดานรวม 7 วัน"""
    assert timedelta(hours=12) == IDLE_LIFETIME
    assert timedelta(days=7) == ABSOLUTE_LIFETIME


def test_renewal_never_passes_the_absolute_cap() -> None:
    """V-6 (ฝั่งโค้ด) — ค่าที่คิดได้ต้องไม่เกินเพดาน จึงไม่ถูกฐานข้อมูลปฏิเสธโดยไม่จำเป็น"""
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    cap = now + timedelta(hours=3)
    assert renewed_idle_deadline(now, cap) == cap
    far = now + timedelta(days=5)
    assert renewed_idle_deadline(now, far) == now + IDLE_LIFETIME


async def test_a_session_is_found_by_the_token_its_holder_presents(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-15 — อ่าน session ได้โดยไม่เกิด `infinite recursion` จาก policy"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)
    async with presented_session(
        api_engine, token_hash=token_hash, role=DatabaseRole.API
    ) as session:
        owner = await owner_of_presented(session)
    assert owner is not None
    assert owner.user_id == user_id


async def test_renewing_moves_the_idle_deadline_forward(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-5.1 — ต่ออายุแล้วเลื่อนจริง (เกณฑ์ทางบวกคู่กับกรณีที่ต่อไม่ได้)"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(
        auth_engine, user_id, now=datetime.now(UTC) - timedelta(hours=2)
    )

    async with presented_session(
        api_engine, token_hash=token_hash, role=DatabaseRole.API
    ) as session:
        before = await owner_of_presented(session)
        assert before is not None
        moved = await renew(
            session,
            token_hash=token_hash,
            idle_expires_at=renewed_idle_deadline(datetime.now(UTC), before.absolute_expires_at),
        )
        after = await owner_of_presented(session)

    assert moved == 1
    assert after is not None
    assert after.idle_expires_at > before.idle_expires_at


async def test_an_expired_session_cannot_be_found_or_renewed(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-5 — หมดอายุแล้วอ่านไม่พบและต่ออายุไม่ได้ — ฐานข้อมูลเป็นผู้ตัดสิน"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id, expired=True)

    async with presented_session(
        api_engine, token_hash=token_hash, role=DatabaseRole.API
    ) as session:
        assert await owner_of_presented(session) is None
        assert (
            await renew(
                session, token_hash=token_hash, idle_expires_at=datetime.now(UTC) + IDLE_LIFETIME
            )
            == 0
        )


async def test_logging_out_removes_only_the_session_in_hand(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-11 — ออกจากระบบเครื่องเดียว ลบใบที่ถือ ใบอื่นของผู้ใช้เดิมยังอยู่"""
    user_id, _ = await make_account(auth_engine)
    mine = await issue_session_for(auth_engine, user_id)
    other = await issue_session_for(auth_engine, user_id)

    async with presented_session(api_engine, token_hash=mine, role=DatabaseRole.API) as session:
        assert await end_one(session, token_hash=mine) == 1

    async with presented_session(api_engine, token_hash=other, role=DatabaseRole.API) as session:
        assert await owner_of_presented(session) is not None


async def test_logging_out_everywhere_removes_more_than_one_row(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-12 — ออกทุกเครื่องลบได้มากกว่าหนึ่งแถวจริง

    นี่คือเทสต์ที่กันการเผลอใส่ `WHERE` ซึ่งจะทำให้ลบได้แถวเดียวเงียบ ๆ (RQ-19)
    """
    user_id, _ = await make_account(auth_engine)
    first = await issue_session_for(auth_engine, user_id)
    await issue_session_for(auth_engine, user_id)
    await issue_session_for(auth_engine, user_id)

    async with presented_session(api_engine, token_hash=first, role=DatabaseRole.API) as session:
        assert await end_all(session) == 3


async def test_logging_out_everywhere_leaves_other_users_alone(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-13 — ไม่แตะ session ของผู้ใช้อื่น"""
    mine_id, _ = await make_account(auth_engine)
    theirs_id, _ = await make_account(auth_engine)
    mine = await issue_session_for(auth_engine, mine_id)
    theirs = await issue_session_for(auth_engine, theirs_id)

    async with presented_session(api_engine, token_hash=mine, role=DatabaseRole.API) as session:
        assert await end_all(session) == 1

    async with presented_session(api_engine, token_hash=theirs, role=DatabaseRole.API) as session:
        assert await owner_of_presented(session) is not None


async def test_a_session_that_is_gone_cannot_end_its_siblings(
    api_engine: AsyncEngine, auth_engine: AsyncEngine
) -> None:
    """V-14 — โทเคนที่ถูกเพิกถอนแล้วแตะใบพี่น้องไม่ได้

    การเพิกถอนคือการลบแถว จึงไม่มีใบที่ policy ใช้ยืนยันความเป็นเจ้าของอีก
    """
    user_id, _ = await make_account(auth_engine)
    revoked = await issue_session_for(auth_engine, user_id)
    survivor = await issue_session_for(auth_engine, user_id)

    async with presented_session(api_engine, token_hash=revoked, role=DatabaseRole.API) as session:
        assert await end_one(session, token_hash=revoked) == 1

    async with presented_session(api_engine, token_hash=revoked, role=DatabaseRole.API) as session:
        assert await end_all(session) == 0

    async with presented_session(api_engine, token_hash=survivor, role=DatabaseRole.API) as session:
        assert await owner_of_presented(session) is not None


async def test_changing_the_password_keeps_the_current_device(auth_engine: AsyncEngine) -> None:
    """V-36.1 — เพิกถอนเครื่องอื่น แต่เครื่องที่กำลังใช้ยังอยู่"""
    user_id, _ = await make_account(auth_engine)
    current = await issue_session_for(auth_engine, user_id)
    await issue_session_for(auth_engine, user_id)
    await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await end_others(session, keep_token_hash=current) == 2
        remaining = (
            await session.execute(
                "SELECT token_hash FROM sessions WHERE user_id = :u", {"u": str(user_id)}
            )
        ).all()
    assert [row[0] for row in remaining] == [current]


@pytest.mark.parametrize("token", ["", "x" * 64])
async def test_an_unknown_token_finds_nothing(api_engine: AsyncEngine, token: str) -> None:
    """โทเคนที่ไม่มีในระบบต้องไม่พบอะไร และต้องไม่ดังเป็นข้อผิดพลาด"""
    async with presented_session(
        api_engine, token_hash=token or None, role=DatabaseRole.API
    ) as session:
        assert await owner_of_presented(session) is None
