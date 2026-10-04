"""secret ของ TOTP และการกันใช้รหัสซ้ำ — V-11.x, V-16 ถึง V-20.x

**ยิงขนานกันจริงในเทสต์ที่เกี่ยวกับการแข่งกัน** ไม่ใช่เรียงกัน เพราะสิ่งที่ต้องพิสูจน์
คือฐานข้อมูลตัดสินถูกเมื่อมีหลายคำขอ ไม่ใช่โค้ดเรียกตามลำดับที่เราเขียน
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import make_account
from tiewtrade.core.totp import TIME_STEP, code_for, step_at
from tiewtrade.infra.auth import totp
from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import user_session

NOW = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch) -> KeySource:
    """กุญแจของเทสต์ — หนึ่งรุ่น"""
    key = base64.b64encode(b"A" * KEY_BYTES).decode("ascii")
    monkeypatch.setenv(KeyPurpose.TOTP_SECRET.environment_variable, f"1:{key}")
    return KeySource.from_environment(KeyPurpose.TOTP_SECRET)


async def enabled_account(
    auth_engine: AsyncEngine, source: KeySource, *, now: datetime = NOW
) -> tuple[UUID, bytes]:
    """ผู้ใช้ที่เปิด TOTP แล้วหนึ่งคน — คืนรหัสผู้ใช้กับ secret ที่ผูกไว้"""
    user_id, _ = await make_account(auth_engine)
    secret = totp.new_secret()
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await totp.stage_secret(session, source, secret)
        confirmed = await totp.confirm_secret(
            session, source, presented=code_for(secret, step_at(now)), now=now
        )
    assert confirmed, "ตั้งค่าไม่สำเร็จ เทสต์จึงยังไม่ได้ทดสอบอะไร"
    return user_id, secret


async def verify_once(
    auth_engine: AsyncEngine,
    source: KeySource,
    user_id: UUID,
    presented: str,
    *,
    now: datetime = NOW,
) -> bool:
    """ตรวจรหัสหนึ่งครั้งใน transaction ของตัวเอง — เหมือนคำขอหนึ่งคำขอ"""
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        return await totp.verify(session, source, presented=presented, now=now)


async def test_a_staged_secret_does_not_enable_anything(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-11 — secret ที่ยังไม่ยืนยันไม่มีผลกับการยืนยันตัวตนเลย"""
    user_id, _ = await make_account(auth_engine)
    secret = totp.new_secret()

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await totp.stage_secret(session, source, secret)
        assert await totp.is_enabled(session) is False
        assert (
            await totp.verify(session, source, presented=code_for(secret, step_at(NOW)), now=NOW)
            is False
        )


async def test_confirming_enables_it(auth_engine: AsyncEngine, source: KeySource) -> None:
    """RQ-3 — เปิดใช้ได้เมื่อผู้ใช้กรอกรหัสจาก secret ใหม่ได้ถูกต้องแล้วเท่านั้น"""
    user_id, _ = await enabled_account(auth_engine, source)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        assert await totp.is_enabled(session) is True


async def test_confirming_with_a_wrong_code_changes_nothing(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-14 — รหัสผิดต้องไม่เปิดใช้ และ secret ยังค้างอยู่ให้ลองใหม่ได้"""
    user_id, _ = await make_account(auth_engine)
    secret = totp.new_secret()

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await totp.stage_secret(session, source, secret)
        assert await totp.confirm_secret(session, source, presented="000000", now=NOW) is False
        assert await totp.is_enabled(session) is False
        # ลองใหม่ด้วยรหัสที่ถูกต้องได้ทันที โดยไม่ต้องตั้งค่าใหม่
        assert await totp.confirm_secret(
            session, source, presented=code_for(secret, step_at(NOW)), now=NOW
        )


async def test_the_code_used_to_confirm_cannot_be_reused(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-20.4 — **รหัสที่ใช้ยืนยันการตั้งค่าใช้ซ้ำทันทีไม่ได้**

    ถ้าตั้ง `last_accepted_step` เป็นศูนย์ตอนสลับ secret ข้อนี้จะแดง
    """
    user_id, secret = await enabled_account(auth_engine, source)
    used = code_for(secret, step_at(NOW))

    assert await verify_once(auth_engine, source, user_id, used) is False


async def test_a_code_is_accepted_once(auth_engine: AsyncEngine, source: KeySource) -> None:
    """V-16 — รหัสเดียวกันใช้สองครั้ง ครั้งที่สองถูกปฏิเสธ"""
    user_id, secret = await enabled_account(auth_engine, source)
    later = NOW + TIME_STEP
    code = code_for(secret, step_at(later))

    assert await verify_once(auth_engine, source, user_id, code, now=later) is True
    assert await verify_once(auth_engine, source, user_id, code, now=later) is False


async def test_a_used_code_is_refused_in_the_next_step(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-17 — **รหัสของช่วง T ที่ใช้แล้ว ถูกปฏิเสธในช่วง T+1 ในฐานะรหัสช่วงก่อนหน้า**

    กรณีที่รีวิวรอบแรกจับได้ และเป็นเหตุที่เก็บ "ช่วงล่าสุดที่รับแล้ว" ไม่ใช่รายการ
    รหัสที่ใช้แล้ว
    """
    user_id, secret = await enabled_account(auth_engine, source)
    at_t = NOW + TIME_STEP
    code = code_for(secret, step_at(at_t))

    assert await verify_once(auth_engine, source, user_id, code, now=at_t) is True
    assert await verify_once(auth_engine, source, user_id, code, now=at_t + TIME_STEP) is False


async def test_two_requests_with_the_same_code_leave_one_winner(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-19 — ยิงรหัสเดียวกันพร้อมกัน สำเร็จได้ใบเดียว"""
    user_id, secret = await enabled_account(auth_engine, source)
    later = NOW + TIME_STEP
    code = code_for(secret, step_at(later))

    results = await asyncio.gather(
        *(verify_once(auth_engine, source, user_id, code, now=later) for _ in range(5))
    )

    assert sum(results) == 1, f"สำเร็จ {sum(results)} ครั้งจากรหัสเดียว"


async def test_a_code_of_a_replaced_secret_is_refused(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-20.1 — **รหัสจาก secret ที่ถูกยกเลิกแล้วใช้ไม่ได้ แม้ลำดับเวลาจะผ่าน**

    ใช้ลำดับที่ใหม่กว่าของ secret เก่าโดยเจตนา เพื่อให้เงื่อนไขเรื่องลำดับเวลา
    ผ่านไปได้ — สิ่งที่ต้องปฏิเสธคือ `secret_version` ไม่ใช่เวลา
    """
    user_id, old_secret = await enabled_account(auth_engine, source)
    far_later = NOW + TIME_STEP * 10

    new_secret = totp.new_secret()
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await totp.stage_secret(session, source, new_secret)
        assert await totp.confirm_secret(
            session, source, presented=code_for(new_secret, step_at(far_later)), now=far_later
        )

    even_later = far_later + TIME_STEP
    assert (
        await verify_once(
            auth_engine, source, user_id, code_for(old_secret, step_at(even_later)), now=even_later
        )
        is False
    )
    assert (
        await verify_once(
            auth_engine, source, user_id, code_for(new_secret, step_at(even_later)), now=even_later
        )
        is True
    )


async def test_replacing_a_secret_while_verifying_leaves_no_mixed_state(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-20.2 — เปลี่ยน secret แข่งกับการตรวจรหัส ต้องมีฝ่ายหนึ่งชนะ ไม่มีสถานะผสม"""
    user_id, old_secret = await enabled_account(auth_engine, source)
    later = NOW + TIME_STEP
    new_secret = totp.new_secret()

    async def replace() -> None:
        async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
            await totp.stage_secret(session, source, new_secret)
            await totp.confirm_secret(
                session, source, presented=code_for(new_secret, step_at(later)), now=later
            )

    async def verify_old() -> bool:
        return await verify_once(
            auth_engine, source, user_id, code_for(old_secret, step_at(later)), now=later
        )

    _, used_old = await asyncio.gather(replace(), verify_old())

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        # ไม่ว่าฝ่ายไหนชนะ secret ใหม่ต้องใช้ได้หลังจากนี้ และของเก่าต้องใช้ไม่ได้
        assert await totp.is_enabled(session) is True
    after = later + TIME_STEP
    assert (
        await verify_once(
            auth_engine, source, user_id, code_for(new_secret, step_at(after)), now=after
        )
        is True
    )
    assert (
        await verify_once(
            auth_engine, source, user_id, code_for(old_secret, step_at(after)), now=after
        )
        is False
    ), f"secret เก่ายังใช้ได้หลังเปลี่ยน (รหัสเก่าในรอบแข่ง: {used_old})"


async def test_a_pending_secret_does_not_disturb_the_active_one(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-11.1 — **เริ่มเปลี่ยนเครื่องแล้วทิ้งกลางทาง ปัจจัยเดิมยังใช้ได้ครบ**

    นี่คือเหตุผลทั้งหมดที่สถานะรอยืนยันอยู่ในตารางแยก
    """
    user_id, secret = await enabled_account(auth_engine, source)
    later = NOW + TIME_STEP

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await totp.stage_secret(session, source, totp.new_secret())

    assert await verify_once(
        auth_engine, source, user_id, code_for(secret, step_at(later)), now=later
    )


async def test_disabling_removes_both_the_active_and_the_pending_secret(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """ปิดแล้วต้องไม่เหลือของค้างที่ทำให้เปิดใหม่ด้วย secret เก่าได้"""
    user_id, secret = await enabled_account(auth_engine, source)
    pending = totp.new_secret()
    later = NOW + TIME_STEP

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        await totp.stage_secret(session, source, pending)
        await totp.disable(session)
        assert await totp.is_enabled(session) is False
        # ของที่ค้างหายไปด้วย จึงยืนยันด้วยรหัสของมันไม่ได้
        assert (
            await totp.confirm_secret(
                session, source, presented=code_for(pending, step_at(later)), now=later
            )
            is False
        )

    assert (
        await verify_once(auth_engine, source, user_id, code_for(secret, step_at(later)), now=later)
        is False
    )


async def test_the_uri_carries_everything_an_app_needs(source: KeySource) -> None:
    """RQ-1 — ระบุค่าทุกตัวไว้ตรง ๆ เพราะแอปบางตัวเดาค่าปริยายต่างกัน"""
    secret = totp.new_secret()

    uri = totp.otpauth_uri(secret, account="someone@example.com")

    # **`:` เป็นตัวอักษรจริง** ส่วนอีเมลถูก encode — รูปแบบเดียวกับที่บริการใหญ่ ๆ ใช้
    assert uri.startswith("otpauth://totp/TiewTrade:someone%40example.com?")
    assert "%3A" not in uri
    assert "algorithm=SHA1" in uri
    assert "digits=6" in uri
    assert f"period={int(TIME_STEP.total_seconds())}" in uri
    assert "=" not in uri.split("secret=")[1].split("&")[0]


async def test_a_stale_clock_cannot_rewind_the_accepted_step(
    auth_engine: AsyncEngine, source: KeySource
) -> None:
    """V-20 — ลำดับเดินหน้าเท่านั้น ฉะนั้นรหัสของช่วงที่ย้อนกลับไปใช้ไม่ได้"""
    user_id, secret = await enabled_account(auth_engine, source)
    ahead = NOW + TIME_STEP * 5
    assert await verify_once(
        auth_engine, source, user_id, code_for(secret, step_at(ahead)), now=ahead
    )

    behind = ahead - timedelta(minutes=2)
    assert (
        await verify_once(
            auth_engine, source, user_id, code_for(secret, step_at(behind)), now=behind
        )
        is False
    )
