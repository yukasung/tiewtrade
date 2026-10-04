"""ตารางของ F-06 — V-47 ถึง V-53 และข้อที่ผูกกับ RLS โดยตรง

**อ่านโครงสร้างจริงจากฐานข้อมูล ไม่ใช่เชื่อ migration** และ **ยิงด้วยบทบาทจริง**
เพราะสิ่งที่ต้องพิสูจน์คือฐานข้อมูลปฏิเสธเอง ไม่ใช่โค้ดเลี่ยงไม่ทำ
(แบบแผนเดียวกับเทสต์ของ F-03 และ F-05)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import issue_session_for, make_account
from tiewtrade.infra.auth import renew
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import presented_session, user_session

NEW_TABLES = (
    "user_totp",
    "user_totp_pending",
    "user_recovery_codes",
    "login_challenges",
    "recovery_grants",
)

SEALED = b"\x00" * 28


async def _sealed_secret(auth_engine: AsyncEngine, user_id: UUID) -> None:
    """ใส่ secret ที่เปิดใช้แล้วหนึ่งแถว — ใช้เป็นจุดเริ่มของหลายเทสต์"""
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "INSERT INTO user_totp"
            " (user_id, secret_sealed, key_version, secret_version, last_accepted_step)"
            " VALUES (:user_id, :sealed, '1', 1, 0)",
            {"user_id": str(user_id), "sealed": SEALED},
        )


@pytest.mark.parametrize("table", NEW_TABLES)
async def test_every_new_table_has_row_level_security_forced(
    auth_engine: AsyncEngine, table: str
) -> None:
    """V-47 — เปิดและ **บังคับ** RLS ทุกตาราง · อ่านจาก `pg_class` ไม่ใช่จาก migration

    อ่านด้วยบทบาทธรรมดาได้เพราะแค็ตตาล็อกของระบบอ่านได้ทุกบทบาท — และการอ่าน
    โครงสร้างจริงคือสิ่งที่ทำให้ "ลืมเปิด RLS ในตารางถัดไป" ดังทันที
    """
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        row = (
            await session.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :name",
                {"name": table},
            )
        ).one()

    enabled, forced = tuple(row)
    assert enabled is True, f"{table} ยังไม่เปิด RLS"
    assert forced is True, f"{table} ยังไม่บังคับ RLS กับเจ้าของตาราง"


@pytest.mark.parametrize("table", NEW_TABLES)
async def test_the_api_role_cannot_touch_the_new_tables(
    api_engine: AsyncEngine, table: str
) -> None:
    """V-48 — บทบาทที่รับคำขอจากเว็บ **ไม่มีสิทธิ์ใด ๆ** บนตารางปัจจัยยืนยันตัวตน

    ตรวจทีละคำสั่ง ไม่ใช่ตรวจรวม เพราะการให้สิทธิ์ผิดมักผิดทีละคำสั่ง
    """
    statements = (
        f"SELECT * FROM {table}",
        f"DELETE FROM {table}",
        f"UPDATE {table} SET user_id = user_id",
    )
    for statement in statements:
        async with user_session(api_engine, uuid4(), role=DatabaseRole.API) as session:
            with pytest.raises(InfraError):
                await session.execute(statement)


@pytest.mark.parametrize("table", NEW_TABLES)
async def test_reading_without_a_current_user_sees_nothing(
    auth_engine: AsyncEngine, table: str
) -> None:
    """V-49 — ไม่ระบุผู้ใช้แล้วอ่านศูนย์แถว จึงพลาดแบบปิดประตู"""
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        rows = (await session.execute(f"SELECT 1 FROM {table}")).all()

    assert rows == []


async def test_the_owner_of_a_secret_cannot_be_changed(auth_engine: AsyncEngine) -> None:
    """V-50 — ไม่ให้สิทธิ์ `UPDATE` บน `user_id` จึงย้ายเจ้าของแถวไม่ได้"""
    user_id, _ = await make_account(auth_engine)
    await _sealed_secret(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute("UPDATE user_totp SET user_id = :other", {"other": str(uuid4())})


async def test_a_user_can_only_have_one_active_secret(auth_engine: AsyncEngine) -> None:
    """V-51 — บังคับด้วย `PRIMARY KEY` ที่ระดับฐานข้อมูล ไม่ใช่เงื่อนไขในโค้ด"""
    user_id, _ = await make_account(auth_engine)
    await _sealed_secret(auth_engine, user_id)

    with pytest.raises(InfraError):
        await _sealed_secret(auth_engine, user_id)


async def test_a_secret_of_another_user_is_invisible(auth_engine: AsyncEngine) -> None:
    """policy ตามเจ้าของ — ขอข้อมูลของคนอื่นต้องได้ "ไม่พบ" (`security.md` หัวข้อ 2)"""
    owner, _ = await make_account(auth_engine)
    await _sealed_secret(auth_engine, owner)
    stranger, _ = await make_account(auth_engine)

    async with user_session(auth_engine, stranger, role=DatabaseRole.AUTH) as session:
        rows = (await session.execute("SELECT user_id FROM user_totp")).all()

    assert rows == []


async def test_a_challenge_cannot_be_updated_by_anyone(auth_engine: AsyncEngine) -> None:
    """`plan.md` หัวข้อ 6.4 — ไม่มีสิทธิ์ `UPDATE` ให้ใครเลย จึงต่ออายุไม่ได้"""
    user_id, _ = await make_account(auth_engine)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute("UPDATE login_challenges SET expires_at = now()")


async def test_an_expired_challenge_is_invisible_to_its_token_but_still_deletable(
    auth_engine: AsyncEngine,
) -> None:
    """V-26.4 — แถวที่หมดอายุต้องมองไม่เห็นจากโทเคน **แต่ยังลบได้หลังระบุตัวตนแล้ว**

    ถ้ามี policy ของโทเคนอย่างเดียว คำสั่งลบที่อ้างคอลัมน์จะดึง SELECT policy มาใช้
    แล้วแถวที่หมดอายุจะลบไม่ได้เลย — กลายเป็นขยะที่ไม่มีใครเก็บได้
    (`plan.md` หัวข้อ 1.5)
    """
    user_id, _ = await make_account(auth_engine)
    token_hash = f"{uuid4().hex}{uuid4().hex}"
    expired = datetime.now(UTC) - timedelta(seconds=1)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "INSERT INTO login_challenges"
            " (token_hash, user_id, credential_updated_at, expires_at)"
            " VALUES (:token, :user_id, now(), :expires)",
            {"token": token_hash, "user_id": str(user_id), "expires": expired},
        )

    async with presented_session(
        auth_engine, token_hash=token_hash, role=DatabaseRole.AUTH
    ) as seen:
        assert (await seen.execute("SELECT 1 FROM login_challenges")).all() == []

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "DELETE FROM login_challenges WHERE token_hash = :token", {"token": token_hash}
        )
        remaining = (
            await session.execute(
                "SELECT 1 FROM login_challenges WHERE token_hash = :token",
                {"token": token_hash},
            )
        ).all()
        assert remaining == [], "ลบ challenge ที่หมดอายุไม่ได้"


async def test_a_grant_dies_with_its_session(auth_engine: AsyncEngine) -> None:
    """V-41.5 — `ON DELETE CASCADE` เอาสิทธิ์ไปด้วยเมื่อ session ถูกเพิกถอน"""
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "INSERT INTO recovery_grants (session_token_hash, user_id) VALUES (:token, :user_id)",
            {"token": token_hash, "user_id": str(user_id)},
        )
        assert (await session.execute("SELECT 1 FROM recovery_grants")).all() != []
        await session.execute(
            "DELETE FROM sessions WHERE token_hash = :token", {"token": token_hash}
        )
        assert (await session.execute("SELECT 1 FROM recovery_grants")).all() == []


async def test_a_grant_for_an_expired_session_cannot_even_be_created(
    auth_engine: AsyncEngine,
) -> None:
    """เข้มกว่าที่คาด — `WITH CHECK` ของ policy ไม่ยอมให้ออกสิทธิ์ให้ session ที่ตายแล้ว"""
    user_id, _ = await make_account(auth_engine)
    dead = await issue_session_for(auth_engine, user_id, expired=True)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "INSERT INTO recovery_grants (session_token_hash, user_id)"
                " VALUES (:token, :user_id)",
                {"token": dead, "user_id": str(user_id)},
            )


async def test_a_grant_stops_working_when_its_session_expires(
    auth_engine: AsyncEngine, api_engine: AsyncEngine
) -> None:
    """V-41.5.1 — **session ที่หมดอายุแต่ยังไม่ถูกลบ ต้องไม่ให้สิทธิ์**

    `ON DELETE CASCADE` ไม่ครอบกรณีนี้เลย เพราะทำงานตอนลบ ไม่ใช่ตอนหมดอายุ
    และ F-05 ไม่ลบแถวที่หมดอายุทิ้ง — ข้อนี้จึงต้องมาจากเงื่อนไขใน policy

    ย่นอายุด้วยเส้นทางต่ออายุของบทบาท `api` เพราะบทบาท `auth` ไม่มีสิทธิ์ `UPDATE`
    บน `sessions` เลย และ `FORCE ROW LEVEL SECURITY` ปิดทางแก้แถวตรง ๆ ทุกบทบาท
    """
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "INSERT INTO recovery_grants (session_token_hash, user_id) VALUES (:token, :user_id)",
            {"token": token_hash, "user_id": str(user_id)},
        )
        assert (await session.execute("SELECT 1 FROM recovery_grants")).all() != []

    async with presented_session(
        api_engine, token_hash=token_hash, role=DatabaseRole.API
    ) as presented:
        moved = await renew(
            presented,
            token_hash=token_hash,
            idle_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        assert moved == 1, "ย่นอายุ session ไม่สำเร็จ เทสต์จึงยังไม่ได้ทดสอบอะไร"

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert (await session.execute("SELECT 1 FROM recovery_grants")).all() == []


async def test_a_window_bucket_cannot_carry_token_columns(auth_engine: AsyncEngine) -> None:
    """ถังหน้าต่างคงที่ของ F-05 ต้องไม่มีโควตาคงเหลือ — `CHECK` ปฏิเสธเอง"""
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "INSERT INTO auth_throttle (bucket_kind, bucket_key, tokens_left, refilled_at)"
                " VALUES ('ACCOUNT', :key, 4, now())",
                {"key": uuid4().hex * 2},
            )


async def test_a_token_bucket_must_carry_token_columns(auth_engine: AsyncEngine) -> None:
    """ถัง token bucket ที่ไม่มีโควตาคงเหลือเขียนลงไปไม่ได้ — ชนิดที่ไม่ครบคือชนิดที่พัง"""
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "INSERT INTO auth_throttle (bucket_kind, bucket_key) VALUES ('TOTP_ACCOUNT', :key)",
                {"key": uuid4().hex * 2},
            )


async def test_an_unknown_bucket_kind_is_refused(auth_engine: AsyncEngine) -> None:
    """ชนิดถังที่ไม่ได้ประกาศเขียนลงฐานข้อมูลไม่ได้เลย"""
    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "INSERT INTO auth_throttle (bucket_kind, bucket_key) VALUES ('ยังไม่ประกาศ', :key)",
                {"key": uuid4().hex * 2},
            )


async def test_a_grant_stops_working_when_the_absolute_deadline_passes(
    auth_engine: AsyncEngine,
) -> None:
    """V-41.5.1 — **เส้นตายรวมก็ต้องตัดสิทธิ์** ไม่ใช่เฉพาะเส้นตายไม่ใช้งาน

    เทสต์คู่กันตรวจเส้นตายไม่ใช้งานไปแล้ว · ข้อนี้ตรวจอีกเส้นหนึ่ง เพราะ policy
    เขียนเงื่อนไขไว้สองเส้น และเส้นที่ไม่มีเทสต์คือเส้นที่ลบทิ้งได้โดยไม่มีใครรู้
    """
    user_id, _ = await make_account(auth_engine)
    token_hash = await issue_session_for(auth_engine, user_id)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await session.execute(
            "INSERT INTO recovery_grants (session_token_hash, user_id) VALUES (:t, :u)",
            {"t": token_hash, "u": str(user_id)},
        )
        assert (await session.execute("SELECT 1 FROM recovery_grants")).all() != []

    # ดันเพดานอายุรวมให้ผ่านไปแล้ว — ต้องทำด้วยบทบาทเจ้าของโครงสร้าง เพราะ
    # ไม่มีบทบาทใดได้สิทธิ์ `UPDATE` บน `absolute_expires_at` ซึ่งเป็นสิ่งที่ต้องการ
    await _expire_absolute(auth_engine, token_hash)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert (await session.execute("SELECT 1 FROM recovery_grants")).all() == []


async def _expire_absolute(auth_engine: AsyncEngine, token_hash: str) -> None:
    """ย้อนเพดานอายุรวมของ session หนึ่งใบให้ผ่านไปแล้ว

    ใช้บทบาท `migrator` ที่เป็นเจ้าของตาราง **และปิด RLS ชั่วคราว** เพราะ
    `FORCE ROW LEVEL SECURITY` ครอบเจ้าของด้วย · เป็นของเทสต์เท่านั้น —
    ไม่มีเส้นทางของระบบที่ทำแบบนี้ได้ ซึ่งเป็นสิ่งที่ต้องการ
    """
    from tiewtrade.infra.db import create_engine_for

    engine = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with engine.begin() as connection:
            from sqlalchemy import text

            await connection.execute(text("ALTER TABLE sessions DISABLE ROW LEVEL SECURITY"))
            await connection.execute(
                text(
                    # ต้องย้อนทั้งสองเส้น เพราะ `sessions_idle_within_absolute`
                    # บังคับว่าเส้นตายไม่ใช้งานต้องไม่เกินเพดานรวม
                    "UPDATE sessions"
                    " SET absolute_expires_at = now() - interval '1 second',"
                    "     idle_expires_at = now() - interval '2 seconds'"
                    " WHERE token_hash = :t"
                ),
                {"t": token_hash},
            )
            await connection.execute(text("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY"))
    finally:
        await engine.dispose()
