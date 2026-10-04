"""รอบตรวจ API key — V-13 ถึง V-22.6 (F-07)

**รันกับฐานข้อมูลจริง** เพราะสิ่งที่พิสูจน์คือการจอง เส้นตาย และการแข่งกันของ worker
ซึ่งเป็นพฤติกรรมของฐานข้อมูล ไม่ใช่ของโค้ด Python
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import ApiKeyStatus
from tiewtrade.infra.api_keys.claims import VERIFICATION_DEADLINE
from tiewtrade.infra.crypto import KeySource
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.services.engine.verification import run_round
from tiewtrade.venues.errors import (
    VenueCredentialRejectedError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueUnavailableError,
)

from .conftest import SECRET, ScriptedWallet, as_structure_owner

WORKER = "worker-one"


async def _state(engine: AsyncEngine, user_id: UUID, key_id: UUID) -> dict[str, Any]:
    async with user_session(engine, user_id, role=DatabaseRole.ENGINE) as session:
        row = (
            (
                await session.execute(
                    "SELECT status, failure_code, secret_sealed, attempts, next_attempt_at,"
                    " not_before, verified_at, claimed_by FROM user_api_keys WHERE id = :id",
                    {"id": key_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


async def _age_the_key(migrator: AsyncEngine, key_id: UUID, by: timedelta) -> None:
    """ย้อนเวลาที่สร้างแถว — เลื่อนเวลาแทนการรอจริง

    **ไม่มีบทบาทที่ทำงานจริงบทบาทไหนเขียน `created_at` ได้** ซึ่งเป็นสิ่งที่ต้องการ:
    เวลาที่สร้างแถวต้องเขียนย้อนหลังไม่ได้ · เทสต์จึงต้องออกนอกเส้นทางปกติสองชั้น
    (บทบาทเจ้าของโครงสร้าง **และ** ปลด `FORCE` ชั่วคราว) และการที่ต้องทำสองชั้นนี้
    คือหลักฐานว่าเส้นทางปกติปิดอยู่จริง
    """
    await as_structure_owner(
        migrator,
        "UPDATE user_api_keys SET created_at = created_at - CAST(:age AS interval) WHERE id = :id",
        {"id": key_id, "age": by},
    )


async def _round(
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    keys: KeySource,
    market: ScriptedWallet,
    *,
    worker: str = WORKER,
) -> Any:
    return await run_round(
        engine=engine,
        scan_engine=scan_engine,
        keys=keys,
        wallet_for=market.factory(),  # type: ignore[arg-type]
        worker=worker,
    )


async def test_a_working_key_becomes_active(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-13 — อ่านกระเป๋าได้ → ใช้งานได้"""
    owner, key_id = key_of_a_user

    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.verified == 1
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.ACTIVE.value
    assert state["verified_at"] is not None
    assert state["claimed_by"] is None


async def test_the_worker_unseals_the_right_secret(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """ตัวลงลายเซ็นที่ส่งให้ตลาดต้องถือความลับของแถวนั้นจริง"""
    await _round(engine_engine, scan_engine, venue_keys, market)

    signer = market.signers[0]
    import hashlib
    import hmac

    expected = hmac.new(SECRET.encode(), b"payload", hashlib.sha256).hexdigest()
    assert signer.sign("payload") == expected


async def test_a_bad_credential_is_rejected_and_the_secret_is_deleted(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-14 — key ผิดจริง → ปฏิเสธ และ **ลบ secret ทันที** (Q-7)"""
    owner, key_id = key_of_a_user
    market.outcomes.append(VenueCredentialRejectedError())

    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.rejected == 1
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.REJECTED.value
    assert state["failure_code"] == "VENUE_CREDENTIAL_REJECTED"
    assert state["secret_sealed"] is None


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (VenueUnavailableError(), "VENUE_UNAVAILABLE"),
        (VenueProtocolError(), "VENUE_PROTOCOL"),
    ],
)
async def test_a_temporary_failure_keeps_the_secret(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
    error: Exception,
    code: str,
) -> None:
    """V-15, V-16 — ตรวจไม่ได้ชั่วคราว → **secret ยังอยู่** และลองใหม่ได้"""
    owner, key_id = key_of_a_user
    market.outcomes.append(error)  # type: ignore[arg-type]

    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.deferred == 1
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.UNVERIFIABLE.value
    assert state["failure_code"] == code
    assert state["secret_sealed"] is not None
    assert state["next_attempt_at"] is not None


async def test_a_protocol_mismatch_is_reported_apart_from_a_flaky_network(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """V-16 — "สัญญาไม่ตรง" ต้องแจ้งผู้ดูแลแยกจาก "เน็ตมีปัญหา"

    สองอย่างนี้ต้องการคนละการกระทำ — อย่างหนึ่งรอ อีกอย่างมีคนต้องแก้โค้ด
    """
    market.outcomes.append(VenueProtocolError())

    with caplog.at_level("ERROR"):
        await _round(engine_engine, scan_engine, venue_keys, market)

    assert any("VENUE_PROTOCOL" in record.message for record in caplog.records)

    caplog.clear()
    market.outcomes.append(VenueUnavailableError())
    with caplog.at_level("ERROR"):
        await _round(engine_engine, scan_engine, venue_keys, market)

    assert not caplog.records


async def test_the_market_wait_is_recorded_and_cannot_be_skipped(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """ตลาดสั่งให้รอ → บันทึก `not_before` และรอบถัดไปต้องไม่เรียกตลาดอีก"""
    owner, key_id = key_of_a_user
    market.outcomes.append(VenueRateLimitedError(retry_after=timedelta(minutes=30)))

    await _round(engine_engine, scan_engine, venue_keys, market)
    state = await _state(engine_engine, owner, key_id)
    assert state["not_before"] is not None

    calls_before = market.calls
    await _round(engine_engine, scan_engine, venue_keys, market)
    assert market.calls == calls_before


async def test_a_key_past_the_deadline_is_closed_before_the_market_is_called(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-17 — ครบ 24 ชั่วโมง → ปฏิเสธ ลบ secret และ **ไม่เรียกตลาดเลย**"""
    owner, key_id = key_of_a_user
    await _age_the_key(migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1))

    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.expired == 1
    assert market.calls == 0
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.REJECTED.value
    assert state["failure_code"] == "VERIFICATION_EXPIRED"
    assert state["secret_sealed"] is None


async def test_retrying_does_not_push_the_deadline_back(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-18 — เพดานนับจากเวลาที่เพิ่ม key ไม่ใช่นับใหม่ทุกครั้งที่ลองใหม่"""
    _, key_id = key_of_a_user
    market.outcomes.append(VenueUnavailableError())
    await _round(engine_engine, scan_engine, venue_keys, market)

    await _age_the_key(migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1))
    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.expired == 1


async def test_a_success_that_arrives_after_the_deadline_is_thrown_away(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-19 — ผลสำเร็จที่มาถึงหลังเส้นตายต้องไม่ทำให้ key ใช้งานได้

    แถวยังเป็น `PENDING` ตอนผลกลับมา และ **ไม่มี worker อื่นมาเปลี่ยนสถานะให้ก่อน** —
    สิ่งเดียวที่กันไว้คือเงื่อนไขเวลาในคำสั่งเขียนผล
    """
    owner, key_id = key_of_a_user

    class AgeingMarket(ScriptedWallet):
        """ตลาดที่ "ใช้เวลา" นานจนแถวหมดอายุระหว่างรอคำตอบ"""

        async def holdings(self) -> Any:
            await _age_the_key(
                migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1)
            )
            return await super().holdings()

    market = AgeingMarket(outcomes=[])
    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.verified == 0
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] != ApiKeyStatus.ACTIVE.value


async def test_a_key_deleted_while_being_checked_does_not_come_back(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-20 — ผู้ใช้ลบ key ระหว่างรอบตรวจ แล้วต้องไม่มีแถวกลับมา"""
    owner, key_id = key_of_a_user

    class DeletingMarket(ScriptedWallet):
        async def holdings(self) -> Any:
            from tiewtrade.infra.api_keys import delete_key

            async with user_session(api_engine, owner) as session:
                await delete_key(session, key_id)
            return await super().holdings()

    await _round(engine_engine, scan_engine, venue_keys, DeletingMarket(outcomes=[]))

    async with user_session(api_engine, owner) as session:
        found = (
            await session.execute(
                "SELECT count(*) FROM user_api_keys WHERE id = :id", {"id": key_id}
            )
        ).scalar_one()
    assert found == 0


async def test_a_second_worker_cannot_claim_a_row_that_is_being_checked(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-22, V-22.1 — worker ที่สองหยิบแถวที่ถูกจองอยู่ไม่ได้ และไม่เรียกตลาด"""
    second = ScriptedWallet(outcomes=[])

    class ConcurrentMarket(ScriptedWallet):
        async def holdings(self) -> Any:
            # worker ตัวที่สองมาระหว่างที่ตัวแรกกำลังรอตลาด
            await _round(engine_engine, scan_engine, venue_keys, second, worker="worker-two")
            return await super().holdings()

    await _round(engine_engine, scan_engine, venue_keys, ConcurrentMarket(outcomes=[]))

    assert second.calls == 0


async def test_the_backoff_holds_a_row_back_until_it_is_due(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-22.5 — รอบถัดไปต้องไม่ถึงคิวทันทีหลังล้มเหลวชั่วคราว"""
    market.outcomes.append(VenueUnavailableError())
    await _round(engine_engine, scan_engine, venue_keys, market)

    calls_before = market.calls
    await _round(engine_engine, scan_engine, venue_keys, market)

    assert market.calls == calls_before


async def test_a_user_asking_for_a_retry_brings_the_row_forward(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-31.5 — กดลองใหม่หนึ่งครั้ง = ความพยายามหนึ่งครั้ง แล้วกลับไปใช้ backoff"""
    from tiewtrade.infra.api_keys import request_retry

    owner, key_id = key_of_a_user
    market.outcomes.append(VenueUnavailableError())
    await _round(engine_engine, scan_engine, venue_keys, market)

    async with user_session(api_engine, owner) as session:
        await request_retry(session, key_id)

    market.outcomes.append(VenueUnavailableError())
    before = market.calls
    await _round(engine_engine, scan_engine, venue_keys, market)
    assert market.calls == before + 1

    # ครั้งถัดไปต้องไม่ถึงคิวอีก เพราะคำขอถูกใช้ไปแล้ว
    after = market.calls
    await _round(engine_engine, scan_engine, venue_keys, market)
    assert market.calls == after


async def test_every_outcome_is_written_to_the_audit_log(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-35 — ผลการตรวจทุกแบบลงบันทึก และ **ผู้กระทำคือระบบ**

    `details` ต้องว่าง — รหัสเหตุผลอยู่ในคอลัมน์ของมันเอง ไม่ใช่ยัดลง `details`
    (`plan.md` ข้อ 4.4 · RQ-9.1)
    """
    owner, key_id = key_of_a_user
    market.outcomes.append(VenueUnavailableError())
    await _round(engine_engine, scan_engine, venue_keys, market)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        rows = (
            (
                await session.execute(
                    "SELECT action, actor_kind, actor_id, subject_kind, subject_id, outcome,"
                    " failure_code, details FROM audit_events WHERE owner_user_id = :owner",
                    {"owner": owner},
                )
            )
            .mappings()
            .all()
        )

    deferred = [row for row in rows if row["action"] == "API_KEY_VERIFICATION_DEFERRED"]
    assert len(deferred) == 1
    entry = deferred[0]
    assert entry["actor_kind"] == "SYSTEM"
    assert entry["actor_id"] is None
    assert entry["subject_kind"] == "API_KEY"
    assert entry["subject_id"] == str(key_id)
    assert entry["outcome"] == "FAILED"
    assert entry["failure_code"] == "VENUE_UNAVAILABLE"
    assert entry["details"] == {}


async def test_an_outcome_that_is_thrown_away_is_not_written_to_the_audit_log(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-35 — ผลที่มาถึงหลังเส้นตายถูกทิ้ง จึง **ต้องไม่มีบันทึกว่ามันเกิดขึ้น**

    บันทึกที่ลบไม่ได้ต้องไม่เล่าเรื่องที่ไม่ได้เกิด
    """
    owner, key_id = key_of_a_user

    class AgeingMarket(ScriptedWallet):
        async def holdings(self) -> Any:
            await _age_the_key(
                migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1)
            )
            return await super().holdings()

    await _round(engine_engine, scan_engine, venue_keys, AgeingMarket(outcomes=[]))

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        verified = (
            await session.execute(
                "SELECT count(*) FROM audit_events"
                " WHERE owner_user_id = :owner AND action = 'API_KEY_VERIFIED'",
                {"owner": owner},
            )
        ).scalar_one()

    assert verified == 0
