"""รอบตรวจ API key — V-13 ถึง V-22.6 (F-07)

**รันกับฐานข้อมูลจริง** เพราะสิ่งที่พิสูจน์คือการจอง เส้นตาย และการแข่งกันของ worker
ซึ่งเป็นพฤติกรรมของฐานข้อมูล ไม่ใช่ของโค้ด Python
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_key_audit import expected_key_audit_event, read_key_audit_events
from tiewtrade.infra.api_keys import (
    ApiKeyStatus,
    RetryOutcome,
    claims,
    delete_key,
    request_retry,
    store_key,
)
from tiewtrade.infra.api_keys.claims import VERIFICATION_DEADLINE, DueKey, claim, due_hints
from tiewtrade.infra.crypto import KeySource
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine import verification
from tiewtrade.services.engine.verification import run_round
from tiewtrade.venues import live_wallet_factory
from tiewtrade.venues.errors import (
    RejectionReason,
    VenueCredentialRejectedError,
    VenueError,
    VenueOutcomeUnknownError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueRejectedError,
    VenueUnavailableError,
)

from .conftest import SECRET, ScriptedWallet, as_structure_owner

WORKER = "worker-one"


@pytest.mark.parametrize(
    "status,headers,extra_fields",
    [
        pytest.param(200, {"x-mbx-used-weight-1m": "-1"}, {}, id="negative-weight"),
        pytest.param(
            429, {"Retry-After": "999999999999999999999999999999"}, {}, id="oversized-wait"
        ),
        pytest.param(429, {"Retry-After": "315360000000"}, {}, id="unrepresentable-deadline"),
        pytest.param(
            200,
            {"x-mbx-used-weight-999999999999999999999999999999m": "1"},
            {},
            id="oversized-window",
        ),
        pytest.param(200, {}, {"permissions": ["SPOT"]}, id="unknown-permission-report"),
        pytest.param(200, {}, {"newMetadata": None}, id="unknown-account-field"),
    ],
)
async def test_malformed_responses_do_not_stop_other_users_verification(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    caplog: pytest.LogCaptureFixture,
    status: int,
    headers: dict[str, str],
    extra_fields: dict[str, object],
) -> None:
    from datetime import UTC, datetime

    import httpx

    owner, bad_id = key_of_a_user
    before = await _state(engine_engine, owner, bad_id)
    healthy_owner = uuid4()
    await create_user(api_engine, healthy_owner)
    async with user_session(api_engine, healthy_owner) as session:
        healthy_id = await store_key(
            session,
            venue_keys,
            user_id=healthy_owner,
            label="healthy",
            key_public="HEALTHYKEY",
            secret=SECRET,
        )
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        key = request.headers["X-MBX-APIKEY"]
        calls.append(key)
        return httpx.Response(
            status if key != "HEALTHYKEY" else 200,
            json={"balances": []} | (extra_fields if key != "HEALTHYKEY" else {}),
            headers=headers if key != "HEALTHYKEY" else {},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        factory = live_wallet_factory(
            client=client, clock=lambda: datetime.now(UTC), timeout=timedelta(seconds=1)
        )
        result = await run_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            keys=venue_keys,
            wallet_for=factory,
            worker=WORKER,
        )
    assert result.deferred == result.verified == 1
    assert len(calls) == 2
    bad = await _state(engine_engine, owner, bad_id)
    assert bad["status"] == "UNVERIFIABLE"
    assert bad["failure_code"] == "VENUE_PROTOCOL"
    assert bad["secret_sealed"] == before["secret_sealed"]
    assert bad["key_version"] == before["key_version"]
    assert bad["claimed_by"] is None
    assert (await _state(engine_engine, healthy_owner, healthy_id))["status"] == "ACTIVE"
    assert await read_key_audit_events(engine_engine, owner, bad_id, role=DatabaseRole.ENGINE) == [
        expected_key_audit_event(
            owner,
            bad_id,
            action="API_KEY_VERIFICATION_DEFERRED",
            actor_kind="SYSTEM",
            outcome="FAILED",
            failure_code="VENUE_PROTOCOL",
        )
    ]
    assert any(
        record.levelname == "ERROR" and "VENUE_PROTOCOL" in record.message
        for record in caplog.records
    )
    assert SECRET not in caplog.text
    assert "HEALTHYKEY" not in caplog.text
    assert "PUBLICKEY000000ABCD" not in caplog.text


@pytest.mark.parametrize("waiting_kind", ["backoff", "market", "manual", "lease"])
async def test_stale_scan_hint_cannot_claim_a_key_that_is_now_waiting(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
    waiting_kind: str,
) -> None:
    """scan เป็นเพียง hint: atomic claim ต้องปฏิเสธเวลารอ/lease ที่เขียนทีหลัง."""
    owner, key_id = key_of_a_user
    async with scan_session_bypassing_rls(scan_engine) as scanning:
        (hint,) = await due_hints(scanning)
    if waiting_kind == "lease":
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert await claim(session, hint, worker="other-worker")
    else:
        errors = {
            "backoff": VenueUnavailableError(),
            "market": VenueRateLimitedError(timedelta(hours=1)),
            "manual": VenueRejectedError(RejectionReason.UNEXPLAINED),
        }
        market.outcomes.append(errors[waiting_kind])
        assert (await _round(engine_engine, scan_engine, venue_keys, market)).deferred == 1
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await claim(session, hint, worker="stale-worker") is None
    assert (await _state(engine_engine, owner, key_id))["attempts"] == 1
    assert market.calls == (0 if waiting_kind == "lease" else 1)


@pytest.mark.parametrize(
    "waiting_kind,limit",
    [("backoff", 2), ("market", 2), ("lease", 2), ("manual", 2), ("backoff", 100)],
)
async def test_waiting_batch_cannot_hide_new_or_expired_keys(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    waiting_kind: str,
    limit: int,
) -> None:
    """V-22.7: งานเก่าเต็ม batch ต้องไม่บัง PENDING ใหม่หรือการลบ secret หมดอายุ."""
    waiting: list[tuple[UUID, UUID]] = []
    owner = uuid4()
    for index in range(limit):
        if index % 6 == 0:
            owner = uuid4()
            await create_user(api_engine, owner)
        async with user_session(api_engine, owner) as session:
            key_id = await store_key(
                session,
                venue_keys,
                user_id=owner,
                label=f"waiting-{index}",
                key_public="WAITINGKEY",
                secret=SECRET,
            )
        waiting.append((owner, key_id))

    settings = {
        "backoff": "status = 'UNVERIFIABLE', failure_code = 'VENUE_UNAVAILABLE', "
        "next_attempt_at = clock_timestamp() + interval '1 hour'",
        "market": "status = 'UNVERIFIABLE', failure_code = 'VENUE_RATE_LIMITED', "
        "next_attempt_at = clock_timestamp() - interval '1 minute', "
        "not_before = clock_timestamp() + interval '1 hour'",
        "lease": "claimed_by = 'busy-worker', claim_id = :claim_id, "
        "claim_expires_at = clock_timestamp() + interval '1 hour'",
        "manual": "status = 'UNVERIFIABLE', failure_code = 'VENUE_REJECTED', "
        "next_attempt_at = NULL",
    }[waiting_kind]
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET created_at = clock_timestamp() - interval '1 hour', "
        "last_attempt_at = clock_timestamp(), attempts = 1, " + settings + " WHERE id = ANY(:ids)",
        {"ids": [key_id for _, key_id in waiting], "claim_id": uuid4()},
    )
    fresh_owner = uuid4()
    await create_user(api_engine, fresh_owner)
    async with user_session(api_engine, fresh_owner) as session:
        fresh = await store_key(
            session,
            venue_keys,
            user_id=fresh_owner,
            label="fresh",
            key_public="FRESHKEY",
            secret=SECRET,
        )
        expired = await store_key(
            session,
            venue_keys,
            user_id=fresh_owner,
            label="expired",
            key_public="EXPIREDKEY",
            secret=SECRET,
        )
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET created_at = clock_timestamp() - interval '25 hours', "
        "last_attempt_at = clock_timestamp(), attempts = 1, " + settings + " WHERE id = :id",
        {"id": expired, "claim_id": uuid4()},
    )
    result = await _round(engine_engine, scan_engine, venue_keys, market, limit=limit)
    assert result.verified == 1
    assert result.expired == 1
    assert result.skipped == 0
    assert market.calls == 1
    assert (await _state(engine_engine, fresh_owner, fresh))["status"] == "ACTIVE"
    assert (await _state(engine_engine, fresh_owner, expired))["secret_sealed"] is None
    await _assert_expiration_audit(engine_engine, fresh_owner, expired)
    for waiting_owner, key_id in waiting:
        state = await _state(engine_engine, waiting_owner, key_id)
        assert state["attempts"] == 1
        assert state["secret_sealed"] is not None
    again = await _round(engine_engine, scan_engine, venue_keys, market, limit=limit)
    assert again.verified == again.deferred == again.expired == again.skipped == 0
    assert market.calls == 1


@pytest.mark.parametrize("status,code", [(403, None), (400, -1021), (400, -99999)])
async def test_unexplained_rejection_keeps_secret_until_manual_retry(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    caplog: pytest.LogCaptureFixture,
    status: int,
    code: int | None,
) -> None:
    """V-15.1: HTTP จริงที่ถูกปฏิเสธไม่พิสูจน์ว่า key ผิด และไม่ส่งซ้ำเอง."""
    from datetime import UTC, datetime

    import httpx

    owner, key_id = key_of_a_user
    calls: list[httpx.Request] = []
    before = await _state(engine_engine, owner, key_id)

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(status, json={"code": code, "msg": SECRET})
        return httpx.Response(200, json={"balances": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        wallet_for = live_wallet_factory(
            client=client, clock=lambda: datetime.now(UTC), timeout=timedelta(seconds=1)
        )

        async def run() -> Any:
            return await run_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                keys=venue_keys,
                wallet_for=wallet_for,
                worker=WORKER,
            )

        result = await run()
        assert result.deferred == 1
        state = await _state(engine_engine, owner, key_id)
        assert state["status"] == "UNVERIFIABLE"
        assert state["failure_code"] == "VENUE_REJECTED"
        assert state["secret_sealed"] == before["secret_sealed"]
        assert state["key_version"] == before["key_version"]
        assert state["next_attempt_at"] is None
        assert state["claimed_by"] is None
        assert any(
            record.levelname == "ERROR" and "VENUE_REJECTED" in record.message
            for record in caplog.records
        )
        assert SECRET not in caplog.text
        assert "PUBLICKEY000000ABCD" not in caplog.text
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            event = (
                (
                    await session.execute(
                        "SELECT action, outcome, failure_code, details FROM audit_events "
                        "WHERE subject_id = :id",
                        {"id": str(key_id)},
                    )
                )
                .mappings()
                .one()
            )
        assert dict(event) == {
            "action": "API_KEY_VERIFICATION_DEFERRED",
            "outcome": "FAILED",
            "failure_code": "VENUE_REJECTED",
            "details": {},
        }
        # ค่าเก่าที่ถึงคิวแล้วก็ห้ามเปิดทางส่งซ้ำ เมื่อยังไม่มี manual request
        await as_structure_owner(
            migrator_engine,
            "UPDATE user_api_keys SET next_attempt_at = clock_timestamp() - interval '1 minute' "
            "WHERE id = :id",
            {"id": key_id},
        )
        for _ in range(2):
            assert (await run()).skipped == 1
        assert len(calls) == 1
        async with user_session(api_engine, owner) as session:
            assert (await request_retry(session, key_id)).outcome is RetryOutcome.ACCEPTED
        assert (await run()).verified == 1
        assert len(calls) == 2
        assert (await _state(engine_engine, owner, key_id))["status"] == "ACTIVE"


async def test_manual_only_rejection_still_expires_after_24_hours(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    owner, key_id = key_of_a_user
    market.outcomes.append(VenueRejectedError(RejectionReason.UNEXPLAINED))
    assert (await _round(engine_engine, scan_engine, venue_keys, market)).deferred == 1
    await _age_the_key(migrator_engine, key_id, VERIFICATION_DEADLINE)
    assert (await _round(engine_engine, scan_engine, venue_keys, market)).expired == 1
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == "REJECTED"
    assert state["failure_code"] == "VERIFICATION_EXPIRED"
    assert state["secret_sealed"] is None
    assert state["key_version"] is None
    assert market.calls == 1


async def test_interrupted_manual_retry_recovers_its_expired_claim(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-22.3: งาน manual ที่อนุญาตแล้วคืนได้เมื่อ worker ตาย ไม่เริ่ม retry ใหม่."""
    owner, key_id = key_of_a_user
    market.outcomes.append(VenueRejectedError(RejectionReason.UNEXPLAINED))
    assert (await _round(engine_engine, scan_engine, venue_keys, market)).deferred == 1
    async with user_session(api_engine, owner) as session:
        assert (await request_retry(session, key_id)).outcome is RetryOutcome.ACCEPTED
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await claim(session, DueKey(id=key_id, user_id=owner), worker="dead-worker")
    # scan ข้าม live lease ก่อน LIMIT แล้ว · ไม่เรียกตลาดหรือเปลี่ยน attempts
    live = await _round(engine_engine, scan_engine, venue_keys, market)
    assert live.skipped == live.verified == live.deferred == live.expired == 0
    assert market.calls == 1
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET claim_expires_at = clock_timestamp() - interval '1 second' "
        "WHERE id = :id",
        {"id": key_id},
    )
    assert (await _round(engine_engine, scan_engine, venue_keys, market)).verified == 1
    assert market.calls == 2
    assert (await _state(engine_engine, owner, key_id))["status"] == "ACTIVE"


@pytest.mark.parametrize("bad_key", ["ทดสอบ", "bad\r\nheader", "bad\x7f"])
async def test_legacy_malformed_key_does_not_block_a_healthy_key(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
    caplog: pytest.LogCaptureFixture,
    bad_key: str,
) -> None:
    """ข้อมูลก่อนเพิ่ม validation ต้องไม่ฆ่า worker หรือถูกส่งถึงตลาด (RQ-13/V-7)."""
    from uuid import uuid4

    owner, bad_id = key_of_a_user
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET key_public = :value WHERE id = :id",
        {"value": bad_key, "id": bad_id},
    )
    healthy_owner = uuid4()
    await create_user(api_engine, healthy_owner)
    async with user_session(api_engine, healthy_owner) as session:
        healthy_id = await store_key(
            session,
            venue_keys,
            user_id=healthy_owner,
            label="healthy",
            key_public="HEALTHYKEY",
            secret=SECRET,
        )
    result = await _round(engine_engine, scan_engine, venue_keys, market)
    assert result.deferred == 1
    assert result.verified == 1
    assert market.calls == 1
    bad = await _state(engine_engine, owner, bad_id)
    assert bad["status"] == "UNVERIFIABLE"
    assert bad["failure_code"] == "VENUE_PROTOCOL"
    assert bad["secret_sealed"] is not None
    assert bad["claimed_by"] is None
    assert (await _state(engine_engine, healthy_owner, healthy_id))["status"] == "ACTIVE"
    assert bad_key not in caplog.text
    assert SECRET not in caplog.text


async def _state(engine: AsyncEngine, user_id: UUID, key_id: UUID) -> dict[str, Any]:
    async with user_session(engine, user_id, role=DatabaseRole.ENGINE) as session:
        row = (
            (
                await session.execute(
                    "SELECT status, failure_code, secret_sealed, attempts, next_attempt_at,"
                    " not_before, verified_at, claimed_by, key_version, claim_id,"
                    " claim_expires_at, last_attempt_at FROM user_api_keys WHERE id = :id",
                    {"id": key_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


async def _assert_expiration_audit(engine: AsyncEngine, owner: UUID, key_id: UUID) -> None:
    assert await read_key_audit_events(engine, owner, key_id, role=DatabaseRole.ENGINE) == [
        expected_key_audit_event(
            owner,
            key_id,
            action="API_KEY_REJECTED",
            actor_kind="SYSTEM",
            outcome="REJECTED",
            failure_code="VERIFICATION_EXPIRED",
        )
    ]


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
    limit: int = 100,
) -> Any:
    return await run_round(
        engine=engine,
        scan_engine=scan_engine,
        keys=keys,
        wallet_for=market.factory(),  # type: ignore[arg-type]
        worker=worker,
        limit=limit,
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


@pytest.mark.parametrize("after_call", [False, True])
async def test_expiration_is_rolled_back_when_the_audit_cannot_be_written(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
    after_call: bool,
) -> None:
    """RQ-9 — ห้ามปิดสถานะโดยไม่มี audit ทั้งก่อนและหลังเรียกตลาด"""
    owner, key_id = key_of_a_user

    class AgeingMarket(ScriptedWallet):
        async def holdings(self) -> Any:
            await _age_the_key(
                migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1)
            )
            return await super().holdings()

    async def unavailable_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("tiewtrade.services.engine.verification.record_event", unavailable_audit)
    if not after_call:
        await _age_the_key(migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1))
    market = AgeingMarket(outcomes=[]) if after_call else ScriptedWallet(outcomes=[])

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await _round(engine_engine, scan_engine, venue_keys, market)

    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.PENDING.value
    assert state["secret_sealed"] is not None
    assert state["key_version"] is not None
    assert state["failure_code"] is None


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
    api_engine: AsyncEngine,
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

    owner, key_id = key_of_a_user
    async with user_session(api_engine, owner) as session:
        assert (await request_retry(session, key_id)).outcome is RetryOutcome.ACCEPTED
    caplog.clear()
    market.outcomes.append(VenueUnavailableError())
    with caplog.at_level("ERROR"):
        result = await _round(engine_engine, scan_engine, venue_keys, market)

    assert result.deferred == 1
    assert market.calls == 2, "unavailable outcome must actually be called"
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

    await _assert_expiration_audit(engine_engine, owner, key_id)
    again = await _round(engine_engine, scan_engine, venue_keys, market)
    assert again.expired == 0
    await _assert_expiration_audit(engine_engine, owner, key_id)


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


async def _assert_late_completion_is_rejected(
    engine: AsyncEngine,
    migrator: AsyncEngine,
    owner: UUID,
    key_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as claiming:
        claimed = await claim(claiming, DueKey(id=key_id, user_id=owner), worker=WORKER)
    assert claimed is not None
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as completion:
        started = (await completion.execute("SELECT transaction_timestamp()")).scalar_one()
        deadline = started + timedelta(microseconds=1)
        await as_structure_owner(
            migrator,
            "UPDATE user_api_keys SET created_at = :created WHERE id = :id",
            {"id": key_id, "created": deadline - VERIFICATION_DEADLINE},
        )
        observed = (await completion.execute("SELECT clock_timestamp()")).scalar_one()
        assert started < deadline < observed

        @asynccontextmanager
        async def same_transaction(*args: object, **kwargs: object) -> AsyncIterator[UserSession]:
            yield completion

        with monkeypatch.context() as local:
            local.setattr(verification, "user_session", same_transaction)
            result = await verification._write(engine, claimed, WORKER, verified=True)
        assert result.expired == 1, "late verification must expire, not activate"
        assert result.verified == 0
    state = await _state(engine, owner, key_id)
    assert state["status"] == "REJECTED"
    assert state["secret_sealed"] is None
    assert state["key_version"] is None
    await _assert_expiration_audit(engine, owner, key_id)


async def test_completion_transaction_started_before_deadline_cannot_activate_late(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    key_of_a_user: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V-19.2: transaction เดิมเริ่มก่อนเส้นตายและ UPDATE หลังเส้นตาย ไม่มี sleep."""
    owner, key_id = key_of_a_user
    await _assert_late_completion_is_rejected(
        engine_engine, migrator_engine, owner, key_id, monkeypatch
    )


async def test_transaction_deadline_regression_detects_now_mutant(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    key_of_a_user: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V-19.2: ทำ mutation ในหน่วยความจำเท่านั้น และ regression เดียวกันต้องจับได้."""
    monkeypatch.setattr(
        claims, "_MARK_ACTIVE", claims._MARK_ACTIVE.replace("clock_timestamp()", "now()")
    )
    owner, key_id = key_of_a_user
    with pytest.raises(AssertionError, match="late verification must expire"):
        await _assert_late_completion_is_rejected(
            engine_engine, migrator_engine, owner, key_id, monkeypatch
        )


@pytest.mark.parametrize(
    "error",
    [None, VenueCredentialRejectedError(), VenueUnavailableError(), VenueProtocolError()],
)
async def test_an_outcome_after_the_deadline_closes_the_key(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    error: VenueError | None,
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

    market = AgeingMarket(outcomes=[] if error is None else [error])
    summary = await _round(engine_engine, scan_engine, venue_keys, market)

    assert summary.verified == 0
    assert summary.expired == 1
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.REJECTED.value
    assert state["failure_code"] == "VERIFICATION_EXPIRED"
    assert state["verified_at"] is None
    for column in ("secret_sealed", "key_version", "claimed_by", "claim_id", "claim_expires_at"):
        assert state[column] is None
    await _assert_expiration_audit(engine_engine, owner, key_id)


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


async def test_retries_during_claim_coalesce_into_one_additional_attempt(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-22.1/V-31.6: repeated requests while in flight never overlap or accumulate."""
    owner, key_id = key_of_a_user
    seed = ScriptedWallet(outcomes=[VenueUnavailableError()])
    await _round(engine_engine, scan_engine, venue_keys, seed)
    async with user_session(api_engine, owner) as session:
        assert (await request_retry(session, key_id)).outcome is RetryOutcome.ACCEPTED
    competing = ScriptedWallet(outcomes=[])

    class WaitingMarket(ScriptedWallet):
        async def holdings(self) -> Any:
            assert (await _state(engine_engine, owner, key_id))["claimed_by"] == WORKER
            for _ in range(3):
                async with user_session(api_engine, owner) as session:
                    assert (await request_retry(session, key_id)).outcome is RetryOutcome.ACCEPTED
                await _round(engine_engine, scan_engine, venue_keys, competing, worker="worker-two")
                assert competing.calls == 0
            return await super().holdings()

    waiting = WaitingMarket(outcomes=[VenueUnavailableError()])
    await _round(engine_engine, scan_engine, venue_keys, waiting)
    assert waiting.calls == 1
    followup = ScriptedWallet(outcomes=[VenueUnavailableError()])
    await _round(engine_engine, scan_engine, venue_keys, followup)
    assert followup.calls == 1
    assert (await _state(engine_engine, owner, key_id))["attempts"] == 3
    await _round(engine_engine, scan_engine, venue_keys, followup)
    assert followup.calls == 1
    assert (await _state(engine_engine, owner, key_id))["attempts"] == 3


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


@pytest.mark.parametrize("after_deadline", [False, True])
async def test_a_stale_worker_cannot_replace_a_newer_success(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    after_deadline: bool,
) -> None:
    """V-22.2 — ผลเก่าต้องไม่เขียนทับ ACTIVE หรือลบ secret ของรอบใหม่"""
    owner, key_id = key_of_a_user
    newer = ScriptedWallet(outcomes=[])

    class StaleMarket(ScriptedWallet):
        async def holdings(self) -> Any:
            await as_structure_owner(
                migrator_engine,
                "UPDATE user_api_keys SET claim_expires_at = clock_timestamp()"
                " - interval '1 second' WHERE id = :id",
                {"id": key_id},
            )
            fresh = await _round(engine_engine, scan_engine, venue_keys, newer, worker="worker-two")
            assert fresh.verified == 1
            if after_deadline:
                await _age_the_key(
                    migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1)
                )
            return await super().holdings()

    stale = StaleMarket(outcomes=[VenueUnavailableError()])
    summary = await _round(engine_engine, scan_engine, venue_keys, stale)

    assert summary.skipped == 1
    assert summary.expired == summary.deferred == 0
    assert stale.calls == newer.calls == 1
    state = await _state(engine_engine, owner, key_id)
    assert state["status"] == ApiKeyStatus.ACTIVE.value
    assert state["secret_sealed"] is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        actions = (
            (
                await session.execute(
                    "SELECT action FROM audit_events WHERE subject_id = :id", {"id": str(key_id)}
                )
            )
            .scalars()
            .all()
        )
    assert actions == ["API_KEY_VERIFIED"]


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


@pytest.mark.parametrize(
    "error,expired,action,outcome,failure_code",
    [
        pytest.param(None, False, "API_KEY_VERIFIED", "SUCCEEDED", None, id="verified"),
        pytest.param(
            VenueCredentialRejectedError(),
            False,
            "API_KEY_REJECTED",
            "REJECTED",
            "VENUE_CREDENTIAL_REJECTED",
            id="credential",
        ),
        pytest.param(
            None, True, "API_KEY_REJECTED", "REJECTED", "VERIFICATION_EXPIRED", id="expired"
        ),
        pytest.param(
            VenueUnavailableError(),
            False,
            "API_KEY_VERIFICATION_DEFERRED",
            "FAILED",
            "VENUE_UNAVAILABLE",
            id="unavailable",
        ),
        pytest.param(
            VenueProtocolError(),
            False,
            "API_KEY_VERIFICATION_DEFERRED",
            "FAILED",
            "VENUE_PROTOCOL",
            id="protocol",
        ),
        pytest.param(
            VenueOutcomeUnknownError(),
            False,
            "API_KEY_VERIFICATION_DEFERRED",
            "FAILED",
            "VENUE_OUTCOME_UNKNOWN",
            id="unknown",
        ),
        pytest.param(
            VenueRateLimitedError(timedelta(minutes=1)),
            False,
            "API_KEY_VERIFICATION_DEFERRED",
            "FAILED",
            "VENUE_RATE_LIMITED",
            id="rate",
        ),
        pytest.param(
            VenueRejectedError(RejectionReason.UNEXPLAINED),
            False,
            "API_KEY_VERIFICATION_DEFERRED",
            "FAILED",
            "VENUE_REJECTED",
            id="manual",
        ),
    ],
)
async def test_every_outcome_is_written_to_the_audit_log(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
    error: VenueError | None,
    expired: bool,
    action: str,
    outcome: str,
    failure_code: str | None,
) -> None:
    """V-35: system outcome matrix ตาม plan 4.4 ไม่ตรวจเฉพาะ temporary หนึ่งแบบ."""
    owner, key_id = key_of_a_user
    if expired:
        await _age_the_key(migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(seconds=1))
    if error is not None:
        market.outcomes.append(error)
    await _round(engine_engine, scan_engine, venue_keys, market)
    rows = await read_key_audit_events(engine_engine, owner, key_id, role=DatabaseRole.ENGINE)
    assert rows == [
        expected_key_audit_event(
            owner,
            key_id,
            action=action,
            actor_kind="SYSTEM",
            outcome=outcome,
            failure_code=failure_code,
        )
    ]
    assert market.calls == (0 if expired else 1)
    state = await _state(engine_engine, owner, key_id)
    assert (state["secret_sealed"] is None) == (outcome == "REJECTED")
    assert SECRET not in repr(rows)


async def test_identical_failures_are_audited_on_every_attempt(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    market: ScriptedWallet,
    key_of_a_user: tuple[UUID, UUID],
) -> None:
    """V-35.1 ฝั่งทุกความพยายาม · ไม่เดาความหมายเพดาน ~30 ที่ NC-18 ยังเปิด."""
    owner, key_id = key_of_a_user
    expected = expected_key_audit_event(
        owner,
        key_id,
        action="API_KEY_VERIFICATION_DEFERRED",
        actor_kind="SYSTEM",
        outcome="FAILED",
        failure_code="VENUE_UNAVAILABLE",
    )
    for index in range(4):
        if index:
            await as_structure_owner(
                migrator_engine,
                "UPDATE user_api_keys SET next_attempt_at = clock_timestamp() "
                "- interval '1 second' WHERE id = :id",
                {"id": key_id},
            )
        market.outcomes.append(VenueUnavailableError())
        assert (await _round(engine_engine, scan_engine, venue_keys, market)).deferred == 1
        assert await read_key_audit_events(
            engine_engine, owner, key_id, role=DatabaseRole.ENGINE
        ) == ([expected] * (index + 1))
        assert market.calls == index + 1
    assert (await _state(engine_engine, owner, key_id))["attempts"] == 4


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


async def test_stale_hint_at_minute_two_respects_new_five_minute_backoff(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V-22.5/6: a stale one-minute policy cannot replace the stored five-minute deadline."""
    owner, key_id = key_of_a_user
    async with scan_session_bypassing_rls(scan_engine) as scanning:
        (hint,) = await due_hints(scanning)
    market = ScriptedWallet(outcomes=[VenueUnavailableError(), VenueUnavailableError()])
    await _round(engine_engine, scan_engine, venue_keys, market)
    first = await _state(engine_engine, owner, key_id)
    assert first["attempts"] == 1
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET next_attempt_at = clock_timestamp() - interval '1 second' "
        "WHERE id = :id",
        {"id": key_id},
    )
    await _round(engine_engine, scan_engine, venue_keys, market)
    second = await _state(engine_engine, owner, key_id)
    assert second["attempts"] == 2
    assert (
        timedelta(minutes=5)
        <= second["next_attempt_at"] - second["last_attempt_at"]
        < timedelta(minutes=5, seconds=1)
    )
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET last_attempt_at = clock_timestamp() - interval '2 minutes', "
        "next_attempt_at = clock_timestamp() + interval '3 minutes' WHERE id = :id",
        {"id": key_id},
    )

    async def assert_no_claim() -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert await claim(session, hint, worker="stale-worker") is None

    await assert_no_claim()
    await _round(engine_engine, scan_engine, venue_keys, market)
    assert market.calls == 2
    assert (await _state(engine_engine, owner, key_id))["attempts"] == 2
    mutant = claims._CLAIM.replace(
        "next_attempt_at <= clock_timestamp()",
        "last_attempt_at + interval '1 minute' <= clock_timestamp()",
    )
    assert mutant != claims._CLAIM
    with monkeypatch.context() as mutation:
        mutation.setattr(claims, "_CLAIM", mutant)
        with pytest.raises(AssertionError):
            await assert_no_claim()
    assert (await _state(engine_engine, owner, key_id))["attempts"] == 2


@pytest.mark.parametrize(
    "offset", [timedelta(microseconds=-1), timedelta(0), timedelta(microseconds=1)]
)
async def test_verification_deadline_at_exact_equality(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    key_of_a_user: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
    offset: timedelta,
) -> None:
    """Exact SQL boundary uses one fixed instant throughout the worker statements."""
    from datetime import UTC, datetime

    owner, key_id = key_of_a_user
    instant = datetime(2026, 1, 2, tzinfo=UTC)
    await as_structure_owner(
        migrator_engine,
        "UPDATE user_api_keys SET created_at = :created WHERE id = :id",
        {"id": key_id, "created": instant - VERIFICATION_DEADLINE - offset},
    )
    fixed = "CAST('2026-01-02T00:00:00+00:00' AS timestamptz)"
    for name in ("_DUE_HINTS", "_EXPIRE", "_CLAIM", "_MARK_ACTIVE"):
        statement = getattr(claims, name)
        assert "clock_timestamp()" in statement
        monkeypatch.setattr(claims, name, statement.replace("clock_timestamp()", fixed))
    market = ScriptedWallet(outcomes=[])
    summary = await _round(engine_engine, scan_engine, venue_keys, market)
    state = await _state(engine_engine, owner, key_id)
    if offset < timedelta(0):
        assert summary.verified == market.calls == 1
        assert state["status"] == "ACTIVE"
        assert state["secret_sealed"] is not None
        assert state["verified_at"] == instant
        action, outcome, code = "API_KEY_VERIFIED", "SUCCEEDED", None
    else:
        assert summary.expired == 1
        assert market.calls == 0
        assert state["status"] == "REJECTED"
        assert state["secret_sealed"] is state["key_version"] is None
        action, outcome, code = "API_KEY_REJECTED", "REJECTED", "VERIFICATION_EXPIRED"
    assert await read_key_audit_events(engine_engine, owner, key_id, role=DatabaseRole.ENGINE) == [
        expected_key_audit_event(
            owner, key_id, action=action, actor_kind="SYSTEM", outcome=outcome, failure_code=code
        )
    ]


@settings(
    max_examples=30,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@example(
    events=["unavailable", "protocol", "rejected", "unknown", "rate", "success", "expire", "delete"]
)
@example(events=["unavailable", "expire", "success", "delete"])
@given(
    events=st.lists(
        st.sampled_from(
            [
                "success",
                "credential",
                "unavailable",
                "protocol",
                "unknown",
                "rate",
                "rejected",
                "expire",
                "delete",
            ]
        ),
        min_size=1,
        max_size=8,
    )
)
async def test_generated_outcomes_preserve_state_secret_and_audit_invariants(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    venue_keys: KeySource,
    events: list[str],
) -> None:
    """Each generated history owns a fresh user/key; fixtures are not reset between examples."""
    owner = uuid4()
    await create_user(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        key_id = await store_key(
            session,
            venue_keys,
            user_id=owner,
            label="property",
            key_public="PROPERTYKEY",
            secret=SECRET,
        )
    before = await _state(engine_engine, owner, key_id)
    expected_status, expected_code = "PENDING", None
    expected_audit: list[dict[str, object]] = []
    exists, attempts = True, 0
    market = ScriptedWallet(outcomes=[])
    outcomes = {
        "success": (None, "ACTIVE", None),
        "credential": (VenueCredentialRejectedError(), "REJECTED", "VENUE_CREDENTIAL_REJECTED"),
        "unavailable": (VenueUnavailableError(), "UNVERIFIABLE", "VENUE_UNAVAILABLE"),
        "protocol": (VenueProtocolError(), "UNVERIFIABLE", "VENUE_PROTOCOL"),
        "unknown": (VenueOutcomeUnknownError(), "UNVERIFIABLE", "VENUE_OUTCOME_UNKNOWN"),
        "rate": (VenueRateLimitedError(), "UNVERIFIABLE", "VENUE_RATE_LIMITED"),
        "rejected": (
            VenueRejectedError(RejectionReason.UNEXPLAINED),
            "UNVERIFIABLE",
            "VENUE_REJECTED",
        ),
    }
    try:
        for event in events:
            unfinished = exists and expected_status in ("PENDING", "UNVERIFIABLE")
            if event == "delete":
                async with user_session(api_engine, owner) as session:
                    assert await delete_key(session, key_id) is exists
                exists = False
            elif event == "expire":
                if exists:
                    await _age_the_key(
                        migrator_engine, key_id, VERIFICATION_DEADLINE + timedelta(minutes=1)
                    )
                if unfinished:
                    expected_status, expected_code = "REJECTED", "VERIFICATION_EXPIRED"
                    expected_audit.append(
                        expected_key_audit_event(
                            owner,
                            key_id,
                            action="API_KEY_REJECTED",
                            actor_kind="SYSTEM",
                            outcome="REJECTED",
                            failure_code=expected_code,
                        )
                    )
            elif unfinished:
                if expected_status == "UNVERIFIABLE":
                    async with user_session(api_engine, owner) as session:
                        assert (
                            await request_retry(session, key_id)
                        ).outcome is RetryOutcome.ACCEPTED
                error, expected_status, expected_code = outcomes[event]
                if error is not None:
                    market.outcomes.append(error)
                attempts += 1
                action, audit_outcome = {
                    "ACTIVE": ("API_KEY_VERIFIED", "SUCCEEDED"),
                    "REJECTED": ("API_KEY_REJECTED", "REJECTED"),
                    "UNVERIFIABLE": ("API_KEY_VERIFICATION_DEFERRED", "FAILED"),
                }[expected_status]
                expected_audit.append(
                    expected_key_audit_event(
                        owner,
                        key_id,
                        action=action,
                        actor_kind="SYSTEM",
                        outcome=audit_outcome,
                        failure_code=expected_code,
                    )
                )
            await _round(engine_engine, scan_engine, venue_keys, market)
            assert market.calls == attempts
            if exists:
                state = await _state(engine_engine, owner, key_id)
                assert state["status"] == expected_status
                assert state["failure_code"] == expected_code
                assert state["attempts"] == attempts
                assert state["claim_id"] is state["claimed_by"] is state["claim_expires_at"] is None
                if expected_status == "REJECTED":
                    assert state["secret_sealed"] is state["key_version"] is None
                else:
                    assert state["secret_sealed"] == before["secret_sealed"]
                    assert state["key_version"] == before["key_version"]
            else:
                async with user_session(api_engine, owner) as session:
                    assert (
                        await session.execute(
                            "SELECT count(*) FROM user_api_keys WHERE id = :id", {"id": key_id}
                        )
                    ).scalar_one() == 0
            assert (
                await read_key_audit_events(engine_engine, owner, key_id, role=DatabaseRole.ENGINE)
                == expected_audit
            )
    finally:
        async with user_session(api_engine, owner) as session:
            await delete_key(session, key_id)


def test_automatic_retry_schedule_has_twenty_seven_attempts_within_one_day() -> None:
    """NC-18/V-35.1: independent schedule from approved 1/5/15/60 minutes, excluding manual."""
    elapsed, attempts = timedelta(0), 0
    times = []
    while elapsed < VERIFICATION_DEADLINE:
        times.append(elapsed)
        attempts += 1
        elapsed += claims.backoff_for(attempts)
    assert times == [timedelta(minutes=minute) for minute in [0, 1, 6, *range(21, 1440, 60)]]
    assert attempts == 27
