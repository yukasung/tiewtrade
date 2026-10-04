"""รหัสสำรอง, challenge และสิทธิ์กู้บัญชี — V-26.x, V-32 ถึง V-41.x

เทสต์ที่เกี่ยวกับการใช้ครั้งเดียว **ยิงขนานกันจริง** เพราะ "ใช้ครั้งเดียว" ที่พิสูจน์
ด้วยการเรียกเรียงกันไม่ได้พิสูจน์อะไรเลย
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import issue_session_for, make_account
from tiewtrade.infra.auth import challenges, recovery_codes, recovery_grants
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import presented_session, user_session

#: ค่าที่ใช้เป็น "รุ่นของรหัสผ่าน" — เป็นแค่ค่าที่เก็บ ไม่มีผลกับ policy
VERSION_AT = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)


def real_now() -> datetime:
    """เวลาจริง — **เทสต์ที่พึ่งการมองเห็นต้องใช้ค่านี้**

    policy ของ `login_challenges` เทียบ `expires_at` กับ `now()` ของฐานข้อมูล
    ฉะนั้นเวลาคงที่ที่เลยไปแล้วจะทำให้แถวมองไม่เห็น และเทสต์จะแดงด้วยเหตุผลที่ผิด
    """
    return datetime.now(UTC)


async def issued_for(auth_engine: AsyncEngine, user_id: UUID) -> tuple[str, ...]:
    """ออกชุดรหัสสำรองให้ผู้ใช้คนนั้น"""
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        return (await recovery_codes.issue_set(session)).codes


async def spend_once(auth_engine: AsyncEngine, user_id: UUID, code: str) -> int | None:
    """ใช้รหัสสำรองหนึ่งครั้งใน transaction ของตัวเอง — เหมือนคำขอหนึ่งคำขอ"""
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        return await recovery_codes.spend(session, code)


async def test_a_set_is_issued_once_and_counted(auth_engine: AsyncEngine) -> None:
    """ออกชุดแล้วจำนวนที่เหลือตรงกับจำนวนที่ออก และทุกใบต่างกัน"""
    user_id, _ = await make_account(auth_engine)

    codes = await issued_for(auth_engine, user_id)

    assert len(codes) == recovery_codes.CODES_PER_SET
    assert len(set(codes)) == len(codes), "ออกรหัสซ้ำกัน"
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await recovery_codes.remaining(session) == len(codes)


async def test_a_code_works_once(auth_engine: AsyncEngine) -> None:
    """V-32 — ใช้สำเร็จแล้วใช้ซ้ำไม่ได้ และจำนวนที่เหลือลดลงหนึ่ง"""
    user_id, _ = await make_account(auth_engine)
    codes = await issued_for(auth_engine, user_id)

    assert await spend_once(auth_engine, user_id, codes[0]) == len(codes) - 1
    assert await spend_once(auth_engine, user_id, codes[0]) is None


async def test_a_wrong_code_is_refused(auth_engine: AsyncEngine) -> None:
    """รหัสที่ไม่ตรงใบใดเลยต้องได้ `None` และไม่กินโควตาของใบอื่น"""
    user_id, _ = await make_account(auth_engine)
    codes = await issued_for(auth_engine, user_id)

    assert await spend_once(auth_engine, user_id, "ไม่ใช่รหัสสำรองของใคร") is None
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await recovery_codes.remaining(session) == len(codes)


async def test_two_requests_with_the_same_code_leave_one_winner(
    auth_engine: AsyncEngine,
) -> None:
    """V-33 — ยิงใบเดียวกันพร้อมกัน สำเร็จได้ใบเดียว"""
    user_id, _ = await make_account(auth_engine)
    codes = await issued_for(auth_engine, user_id)

    results = await asyncio.gather(*(spend_once(auth_engine, user_id, codes[0]) for _ in range(5)))

    assert sum(1 for outcome in results if outcome is not None) == 1


async def test_the_stored_form_is_not_the_code(auth_engine: AsyncEngine) -> None:
    """V-34 — เก็บแฮช ไม่เก็บค่าจริง"""
    user_id, _ = await make_account(auth_engine)
    codes = await issued_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        stored = [
            str(next(iter(row)))
            for row in (await session.execute("SELECT code_hash FROM user_recovery_codes")).all()
        ]

    assert all(code not in "".join(stored) for code in codes)


async def test_issuing_a_new_set_revokes_the_old_one(auth_engine: AsyncEngine) -> None:
    """V-37 — **ชุดเก่าทั้งชุดใช้ไม่ได้ทันทีเมื่อออกชุดใหม่** (RQ-15)"""
    user_id, _ = await make_account(auth_engine)
    old = await issued_for(auth_engine, user_id)

    fresh = await issued_for(auth_engine, user_id)

    assert await spend_once(auth_engine, user_id, old[0]) is None
    assert await spend_once(auth_engine, user_id, fresh[0]) is not None


async def test_revoking_leaves_nothing_usable(auth_engine: AsyncEngine) -> None:
    """V-35 และ V-36 ที่ระดับโมดูล — ยกเลิกทั้งชุดแล้วไม่เหลือใบที่ใช้ได้"""
    user_id, _ = await make_account(auth_engine)
    codes = await issued_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await recovery_codes.revoke_all(session)
        assert await recovery_codes.remaining(session) == 0

    assert await spend_once(auth_engine, user_id, codes[0]) is None


async def test_codes_of_another_user_do_not_work(auth_engine: AsyncEngine) -> None:
    """policy ตามเจ้าของ — รหัสของคนอื่นใช้กับบัญชีเราไม่ได้"""
    owner, _ = await make_account(auth_engine)
    codes = await issued_for(auth_engine, owner)
    stranger, _ = await make_account(auth_engine)

    assert await spend_once(auth_engine, stranger, codes[0]) is None


async def test_a_challenge_is_visible_only_to_its_token(auth_engine: AsyncEngine) -> None:
    """โทเคนที่พามาเป็นตัวเปิดแถว และโทเคนอื่นเห็นศูนย์แถว"""
    user_id, _ = await make_account(auth_engine)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        issued = await challenges.issue(session, credential_updated_at=VERSION_AT, now=real_now())

    async with presented_session(
        auth_engine, token_hash=issued.token_hash, role=DatabaseRole.AUTH
    ) as mine:
        found = await challenges.presented(mine)
    assert found is not None
    assert found.user_id == user_id

    async with presented_session(
        auth_engine, token_hash=f"{uuid4().hex}{uuid4().hex}", role=DatabaseRole.AUTH
    ) as other:
        assert await challenges.presented(other) is None


async def test_an_expired_challenge_is_invisible(auth_engine: AsyncEngine) -> None:
    """หมดอายุแล้วมองไม่เห็น — ฐานข้อมูลตัดสินด้วย policy ไม่ใช่โค้ด"""
    user_id, _ = await make_account(auth_engine)
    long_ago = real_now() - challenges.CHALLENGE_LIFETIME - timedelta(seconds=1)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        issued = await challenges.issue(session, credential_updated_at=VERSION_AT, now=long_ago)

    async with presented_session(
        auth_engine, token_hash=issued.token_hash, role=DatabaseRole.AUTH
    ) as mine:
        assert await challenges.presented(mine) is None


async def test_a_spent_challenge_is_gone(auth_engine: AsyncEngine) -> None:
    """ใช้แล้วลบ ไม่ใช่ตั้งธง — จึงไม่มีสถานะ "ใช้แล้วแต่ยังอยู่" ให้พลาด"""
    user_id, _ = await make_account(auth_engine)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        issued = await challenges.issue(session, credential_updated_at=VERSION_AT, now=real_now())
        await challenges.spend(session, token_hash=issued.token_hash)

    async with presented_session(
        auth_engine, token_hash=issued.token_hash, role=DatabaseRole.AUTH
    ) as mine:
        assert await challenges.presented(mine) is None


async def test_the_challenge_carries_the_password_version(auth_engine: AsyncEngine) -> None:
    """V-26.2 ชั้นที่สอง — รุ่นของรหัสผ่านเดินทางไปกับ challenge เพื่อให้เทียบตอนใช้ได้"""
    user_id, _ = await make_account(auth_engine)
    version = VERSION_AT - timedelta(days=1)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        issued = await challenges.issue(session, credential_updated_at=version, now=real_now())

    async with presented_session(
        auth_engine, token_hash=issued.token_hash, role=DatabaseRole.AUTH
    ) as mine:
        found = await challenges.presented(mine)

    assert found is not None
    assert found.credential_updated_at == version


async def test_ending_all_challenges_removes_expired_ones_too(auth_engine: AsyncEngine) -> None:
    """V-26.4 ที่ระดับโมดูล — การลบต้องครอบแถวที่หมดอายุ มิฉะนั้นมันค้างตลอดไป"""
    user_id, _ = await make_account(auth_engine)
    long_ago = real_now() - challenges.CHALLENGE_LIFETIME - timedelta(seconds=1)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await challenges.issue(session, credential_updated_at=VERSION_AT, now=long_ago)
        await challenges.issue(session, credential_updated_at=VERSION_AT, now=real_now())
        await challenges.end_all(session)
        left = (await session.execute("SELECT 1 FROM login_challenges")).all()

    assert left == []


async def test_a_grant_works_once(auth_engine: AsyncEngine) -> None:
    """V-41.3 — สิทธิ์กู้ใช้ครั้งเดียว"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await recovery_grants.grant(session, session_token_hash=token_hash)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await recovery_grants.spend(session, session_token_hash=token_hash) is True
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await recovery_grants.spend(session, session_token_hash=token_hash) is False


async def test_two_requests_spending_one_grant_leave_one_winner(
    auth_engine: AsyncEngine,
) -> None:
    """V-41.3 — ยิงพร้อมกันสำเร็จได้ใบเดียว"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await recovery_grants.grant(session, session_token_hash=token_hash)

    async def spend() -> bool:
        async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
            return await recovery_grants.spend(session, session_token_hash=token_hash)

    results = await asyncio.gather(*(spend() for _ in range(5)))

    assert sum(results) == 1


async def test_a_session_without_a_grant_has_no_right(auth_engine: AsyncEngine) -> None:
    """V-41.1 — session ที่ไม่ได้มาจากรหัสสำรองต้องไม่มีสิทธิ์นี้"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await recovery_grants.spend(session, session_token_hash=token_hash) is False
