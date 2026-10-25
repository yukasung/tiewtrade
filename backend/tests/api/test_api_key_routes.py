"""เส้นทางจัดการ API key — V-4, V-23 ถึง V-31 (F-07)

**เรียกผ่าน HTTP เหมือนหน้าเว็บจริง** เพราะสิ่งที่ต้องพิสูจน์คือพฤติกรรมของเส้นทาง
รวมถึง middleware ที่บังคับการยืนยันซ้ำ ซึ่งการเรียกฟังก์ชันตรง ๆ ข้ามไปทั้งหมด
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, tzinfo
from email.utils import parsedate_to_datetime
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Result

from tests.api.conftest import GOOD_PASSWORD, csrf_headers, database_url_present, register
from tests.api.test_route_policy import route_keys
from tests.api.test_totp_flow import code_now, code_one_step_back, enable_totp, sign_in
from tests.api_key_audit import expected_key_audit_event, read_key_audit_events
from tiewtrade.infra.api_keys import MAX_KEYS_PER_USER, RetryOutcome, records, storage
from tiewtrade.infra.api_keys.storage import RetryDecision
from tiewtrade.infra.auth import Bucket, key_of
from tiewtrade.infra.auth.throttle import API_KEY_ADD_CAPACITY, API_KEY_RETRY_CAPACITY
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import UserSession, user_session
from tiewtrade.services.api import api_key_routes
from tiewtrade.services.api.settings import TOTP_HEADER

pytestmark = pytest.mark.skipif(not database_url_present(), reason="ต้องมีฐานข้อมูล")

KEY = "PUBLICKEY000000ABCD"
SECRET = "secret-that-must-never-come-back"


def _add(client: TestClient, secret_value: bytes, *, label: str = "หลัก") -> Response:
    """เพิ่ม key หนึ่งใบพร้อมยืนยันปัจจัยที่สอง

    **ใช้รหัสของช่วงปัจจุบัน** เพราะ `enable_totp` ใช้รหัสของช่วงก่อนหน้าไปแล้ว
    และ RQ-4 ของ F-06 ห้ามใช้รหัสซ้ำตลอดช่วงที่ยังถูกยอมรับ

    **ฉะนั้นเพิ่ม key ได้ครั้งเดียวต่อช่วงเวลา** ซึ่งเป็นข้อกำหนดที่ถูกต้อง
    (ไม่มีช่วงผ่อนผันของการยืนยันซ้ำ — เจ้าของตัดสิน 2026-10-03) เทสต์ที่ต้องมี
    fixture key จึงใส่แถวผ่านชั้นเก็บโดยตรง แล้วเดินเส้นทางเฉพาะใบที่กำลังพิสูจน์
    """
    answer: Response = client.post(
        "/api-keys",
        json={"label": label, "key": KEY, "secret": SECRET},
        headers=csrf_headers(client) | {TOTP_HEADER: code_now(secret_value)},
    )
    return answer


def _user_id(client: TestClient) -> UUID:
    """รหัสผู้ใช้ของ session ปัจจุบัน"""
    answer = client.get("/auth/me")
    assert answer.status_code == 200, answer.text
    return UUID(answer.json()["user_id"])


def _seed_keys(user_id: UUID, count: int) -> None:
    """ใส่ key ผ่านชั้นเก็บโดยตรง — ใช้เมื่อต้องเตรียมสถานะก่อนทดสอบ

    **ไม่ได้ข้ามกฎใด** ชั้นนี้คือสิ่งที่เส้นทางเรียกอยู่แล้ว ส่วนที่ข้ามคือการยืนยัน
    ปัจจัยที่สอง ซึ่งมีเทสต์ของตัวเองอยู่แล้วและใช้รหัสได้ครั้งเดียวต่อช่วงเวลา
    """
    import asyncio

    from tiewtrade.infra.api_keys import store_key
    from tiewtrade.infra.crypto import KeyPurpose, KeySource
    from tiewtrade.infra.db.session import user_session

    async def run() -> None:
        engine = create_engine_for(DatabaseRole.API)
        keys = KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)
        try:
            for index in range(count):
                async with user_session(engine, user_id) as session:
                    await store_key(
                        session,
                        keys,
                        user_id=user_id,
                        label=f"seeded-{index}",
                        key_public=KEY,
                        secret=SECRET,
                    )
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(run())


def _set_retry_view_state(user_id: UUID, status: str, wait: timedelta | None) -> None:
    """ให้ engine role ตั้งสถานะ/เวลา โดยไม่ใช้เวลาของ process เป็นฐาน."""
    import asyncio

    from tiewtrade.infra.db import user_session

    async def run() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE user_api_keys SET status = :status, "
                    "failure_code = CASE WHEN :status = 'UNVERIFIABLE' THEN 'VENUE_RATE_LIMITED' "
                    "WHEN :status = 'REJECTED' THEN 'VENUE_CREDENTIAL_REJECTED' ELSE NULL END, "
                    "secret_sealed = CASE WHEN :status = 'REJECTED' "
                    "THEN NULL ELSE secret_sealed END, "
                    "key_version = CASE WHEN :status = 'REJECTED' THEN NULL ELSE key_version END, "
                    "verified_at = CASE WHEN :status = 'ACTIVE' "
                    "THEN clock_timestamp() ELSE NULL END, "
                    "not_before = CASE WHEN CAST(:wait AS interval) IS NULL THEN NULL "
                    "ELSE clock_timestamp() + CAST(:wait AS interval) END",
                    {"status": status, "wait": wait},
                )
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(run())


def _retry_job_state(user_id: UUID) -> tuple[datetime | None, int]:
    import asyncio

    from tiewtrade.infra.db import user_session

    async def read() -> tuple[datetime | None, int]:
        engine = create_engine_for(DatabaseRole.API)
        try:
            async with user_session(engine, user_id) as session:
                row = (
                    (
                        await session.execute(
                            "SELECT retry_requested_at, attempts FROM user_api_keys"
                        )
                    )
                    .mappings()
                    .one()
                )
                return row["retry_requested_at"], row["attempts"]
        finally:
            await engine.dispose()

    return asyncio.get_event_loop().run_until_complete(read())


@pytest.mark.parametrize("skew_days", [-7300, 7300])
def test_market_wait_returns_retry_after_without_requesting_work(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    skew_days: int,
) -> None:
    """V-30.4/V-31.3: ตลาดสั่งรอ ต้องมี header แม้โควตาเต็ม และไม่ enqueue."""

    class SkewedClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> SkewedClock:
            return super().now(tz) + timedelta(days=skew_days)

    register(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    _set_retry_view_state(owner, "UNVERIFIABLE", timedelta(hours=1, microseconds=123456))
    (item,) = client.get("/api-keys").json()
    not_before = datetime.fromisoformat(item["not_before"])
    before = _retry_job_state(owner)
    monkeypatch.setattr(api_key_routes, "datetime", SkewedClock)
    refused = client.post(f"/api-keys/{item['id']}/retry", headers=csrf_headers(client))
    assert refused.status_code == 429
    retry_at = parsedate_to_datetime(refused.headers["Retry-After"])
    assert refused.headers["Retry-After"].endswith(" GMT")
    assert timedelta(0) <= retry_at - not_before < timedelta(seconds=1)
    assert _retry_job_state(owner) == before == (None, 0)
    assert KEY not in refused.text
    assert SECRET not in refused.text


@pytest.mark.parametrize("change,expected", [("market", 429), ("active", 409), ("delete", 404)])
def test_retry_header_uses_the_target_after_a_concurrent_change(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    expected: int,
) -> None:
    register(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    _set_retry_view_state(owner, "UNVERIFIABLE", timedelta(seconds=-1))
    (item,) = client.get("/api-keys").json()
    original = UserSession.execute
    changed = False

    async def execute(
        session: UserSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        nonlocal changed
        if statement == storage._REQUEST_RETRY and not changed:
            changed = True
            role = DatabaseRole.API if change == "delete" else DatabaseRole.ENGINE
            engine = create_engine_for(role)
            try:
                async with user_session(engine, owner, role=role) as other:
                    statements = {
                        "market": "UPDATE user_api_keys SET not_before = "
                        "clock_timestamp() + interval '1 hour' WHERE id = :id",
                        "active": "UPDATE user_api_keys SET status = 'ACTIVE', "
                        "failure_code = NULL, "
                        "verified_at = clock_timestamp() WHERE id = :id",
                        "delete": "DELETE FROM user_api_keys WHERE id = :id",
                    }
                    await original(other, statements[change], {"id": UUID(item["id"])})
            finally:
                await engine.dispose()
        return await original(session, statement, parameters)

    monkeypatch.setattr(UserSession, "execute", execute)
    refused = client.post(f"/api-keys/{item['id']}/retry", headers=csrf_headers(client))
    assert changed
    assert refused.status_code == expected
    if change == "market":
        (current,) = client.get("/api-keys").json()
        deadline = datetime.fromisoformat(current["not_before"])
        advertised = parsedate_to_datetime(refused.headers["Retry-After"])
        assert timedelta(0) <= advertised - deadline < timedelta(seconds=1)
    else:
        assert "Retry-After" not in refused.headers
    if change == "delete":
        assert client.get("/api-keys").json() == []
    else:
        assert _retry_job_state(owner) == (None, 0)


def test_missing_market_wait_time_is_a_conflict_not_a_guessed_delay(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    (item,) = client.get("/api-keys").json()

    async def changed_target(*args: object) -> RetryDecision:
        return RetryDecision(RetryOutcome.MUST_WAIT)

    monkeypatch.setattr(api_key_routes, "request_retry", changed_target)
    refused = client.post(f"/api-keys/{item['id']}/retry", headers=csrf_headers(client))
    assert refused.status_code == 409
    assert "Retry-After" not in refused.headers
    assert _retry_job_state(owner) == (None, 0)


@pytest.mark.parametrize("skew_days", [-7300, 7300])
@pytest.mark.parametrize("wait,expected", [(None, True), (0, True), (-1, True), (3600, False)])
def test_retry_view_uses_database_time_and_market_wait(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    skew_days: int,
    wait: int | None,
    expected: bool,
) -> None:
    """RQ-11.4: UI flag ต้องตรงกับเวลาของ DB แม้ process เดินเร็วหรือช้า."""

    class SkewedClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> SkewedClock:
            return super().now(tz) + timedelta(days=skew_days)

    register(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    _set_retry_view_state(owner, "UNVERIFIABLE", None if wait is None else timedelta(seconds=wait))
    for module in (records, storage, api_key_routes):
        monkeypatch.setattr(module, "datetime", SkewedClock)
    answer = client.get("/api-keys")
    assert answer.status_code == 200
    (item,) = answer.json()
    assert item["may_retry"] is expected
    assert KEY not in answer.text
    assert SECRET not in answer.text


@pytest.mark.parametrize("status", ["PENDING", "ACTIVE", "REJECTED"])
def test_retry_view_stays_disabled_for_other_states(client: TestClient, status: str) -> None:
    register(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    _set_retry_view_state(owner, status, timedelta(seconds=-1))
    answer = client.get("/api-keys")
    assert answer.status_code == 200
    (item,) = answer.json()
    assert item["may_retry"] is False


@pytest.mark.parametrize("label", ["seeded-0", " seeded-0 "])
def test_existing_key_returns_safe_conflict_and_rolls_back_key_work(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    label: str,
) -> None:
    """F-08 cap1 rejects a second key without echoing label/credentials or auditing success."""
    import asyncio

    register(client)
    second_factor, _ = enable_totp(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    before = client.get("/api-keys").json()

    async def stats() -> tuple[int, int]:
        engine = create_engine_for(DatabaseRole.API)
        try:
            async with user_session(engine, owner) as session:
                added_events = (
                    await session.execute(
                        "SELECT count(*) FROM audit_events WHERE action = 'API_KEY_ADDED' "
                        "AND outcome = 'SUCCEEDED'"
                    )
                ).scalar_one()
                tokens = (
                    await session.execute(
                        "SELECT tokens_left FROM api_throttle WHERE bucket_kind = :kind "
                        "AND bucket_key = :key",
                        {"kind": Bucket.API_KEY_ADD.value, "key": key_of(str(owner))},
                    )
                ).scalar_one()
                return added_events, tokens
        finally:
            await engine.dispose()

    with caplog.at_level(logging.DEBUG):
        refused = client.post(
            "/api-keys",
            json={"label": label, "key": KEY + "-NEW", "secret": SECRET},
            headers=csrf_headers(client) | {TOTP_HEADER: code_now(second_factor)},
        )
    assert refused.status_code == 409
    assert refused.json() == {"detail": "เพิ่ม key ได้ไม่เกิน 1 อันต่อผู้ใช้"}
    assert client.get("/api-keys").json() == before
    assert asyncio.get_event_loop().run_until_complete(stats()) == (0, API_KEY_ADD_CAPACITY - 1)
    assert KEY not in refused.text + caplog.text
    assert SECRET not in refused.text + caplog.text
    assert "seeded-0" not in refused.text + caplog.text


def test_adding_a_key_requires_the_second_factor(client: TestClient) -> None:
    """V-23 — ไม่ส่งรหัส → ถูกปฏิเสธ ไม่ใช่เพิ่มสำเร็จ"""
    register(client)
    enable_totp(client)

    refused = client.post(
        "/api-keys",
        json={"label": "หลัก", "key": KEY, "secret": SECRET},
        headers=csrf_headers(client),
    )

    assert refused.status_code == 403, refused.text


def test_an_account_without_a_second_factor_cannot_add_a_key(client: TestClient) -> None:
    """V-25 — บัญชีที่ยังไม่เปิด TOTP เพิ่ม key ไม่ได้

    ผลที่ยอมรับแล้วของ RQ-7.1 — หน้าเว็บต้องบอกทางออก ไม่ใช่ขึ้นข้อผิดพลาดกลาง ๆ
    """
    register(client)

    refused = client.post(
        "/api-keys",
        json={"label": "หลัก", "key": KEY, "secret": SECRET},
        headers=csrf_headers(client) | {TOTP_HEADER: "000000"},
    )

    assert refused.status_code == 403, refused.text


def test_adding_a_key_then_listing_it_shows_only_the_last_four_digits(
    client: TestClient,
) -> None:
    """V-4, Q-5 — คำตอบไม่มี secret และไม่มี key เต็ม"""
    register(client)
    secret, _ = enable_totp(client)

    added = _add(client, secret)
    assert added.status_code == 201, added.text

    listed = client.get("/api-keys")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 1
    assert body[0]["public_tail"] == "ABCD"
    assert body[0]["status"] == "PENDING"

    everything = listed.text + added.text
    assert SECRET not in everything
    assert KEY not in everything


@pytest.mark.parametrize("ending", [False, True])
def test_no_route_hands_back_the_secret(client: TestClient, ending: bool) -> None:
    """V-4 — เดินทุกเส้นทางของ key แล้วต้องไม่มีคำตอบไหนพาความลับออกมา"""
    email = register(client)
    secret, recovery = enable_totp(client)
    added = _add(client, secret)
    key_id = added.json()["id"]

    import asyncio
    import base64

    async def read_sealed() -> bytes:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, _user_id(client), role=DatabaseRole.ENGINE) as session:
                return bytes(
                    (
                        await session.execute(
                            "SELECT secret_sealed FROM user_api_keys WHERE id = :id",
                            {"id": UUID(key_id)},
                        )
                    ).scalar_one()
                )
        finally:
            await engine.dispose()

    sealed = asyncio.get_event_loop().run_until_complete(read_sealed())
    forbidden = (SECRET, KEY, sealed.hex(), base64.b64encode(sealed).decode(), repr(sealed))
    routes = {
        item for item in route_keys() if (item[1] in {"/auth/logout", "/auth/logout-all"}) is ending
    }
    assert routes
    for method, template in sorted(
        routes,
        key=lambda item: (
            item[1] in {"/auth/logout", "/auth/logout-all"},
            item[0] == "DELETE",
            item,
        ),
    ):
        if client.get("/auth/me").status_code != 200:
            sign_in(client, email)
            renewed = client.post(
                "/auth/totp/login",
                json={"recovery_code": recovery.pop()},
                headers=csrf_headers(client),
            )
            assert renewed.status_code == 200
        assert client.get("/auth/me").status_code == 200
        path = (
            template.replace("{key_id}", key_id)
            .replace("{command_id}", key_id)
            .replace("{request_id}", key_id)
            .replace("{order_id}", key_id)
            .replace("{key}", key_id)
            .replace("{base}", "BTC")
            .replace("{quote}", "USDT")
        )
        assert "{" not in path, f"missing canary path value for {template}"
        if method == "WEBSOCKET":
            with client.websocket_connect(
                path, headers={"origin": "http://localhost:5173"}
            ) as socket:
                frame = socket.receive_text()
                for item in forbidden:
                    assert item not in frame
            continue
        response = client.request(
            method,
            path,
            headers=csrf_headers(client),
            params={"base": "BTC", "quote": "USDT", "timeframe": "1m"}
            if template
            in {
                "/market-data/candles",
                "/market-data/candles/pages",
                "/market-data/indicators",
                "/market-data/chart/history",
                "/market-data/chart/live",
            }
            else {"action": "NEW"}
            if template == "/paper/order-requests/by-key/{key}"
            else {"episode_id": key_id}
            if template == "/paper/orders"
            else None,
            **({"json": {}} if method == "POST" else {}),
        )
        if method == "GET":
            if template.startswith("/admin/supported-symbols"):
                assert response.status_code == 403
                assert response.json() == {"detail": "CATALOG_NOT_AUTHORIZED"}
            elif template.startswith("/market-data/chart/"):
                assert (
                    response.status_code == 404
                )  # Disabled by default; refusal must also be secret-free.
            elif template == "/paper-wallet/commands/{command_id}":
                assert response.status_code == 404
                assert response.json() == {"detail": "PAPER_COMMAND_NOT_FOUND"}
            elif template in {
                "/paper/order-requests/by-key/{key}",
                "/paper/order-requests/{request_id}",
            }:
                assert response.status_code == 404
                assert response.json() == {"detail": "MANUAL_REQUEST_NOT_FOUND"}
            elif template == "/paper/orders/{order_id}":
                assert response.status_code == 404
                assert response.json() == {"detail": "PAPER_ORDER_NOT_FOUND"}
            elif template == "/market-data/indicators" and response.status_code == 503:
                # Empty indicator data must fail closed without exposing secrets.
                # Accept only this documented error, independent of prior fixtures.
                assert response.json() == {"detail": "INDICATOR_DATA_NOT_READY"}
            else:
                assert response.status_code == 200, (method, template, response.status_code)
        elif method == "DELETE":
            if template.startswith("/admin/supported-symbols"):
                assert response.status_code in (403, 429)
            else:
                assert response.status_code == 204
        elif template == "/api-keys/{key_id}/retry":
            assert response.status_code == 409
        else:
            assert response.status_code in (200, 204, 400, 403, 409, 422, 429), (method, template)
        for value in forbidden:
            assert value not in response.text, (method, template)


@pytest.mark.parametrize(
    "body",
    [
        *(
            {"label": label, "key": KEY, "secret": SECRET}
            for label in ("\x00หลัก", "หลัก\x00รอง", "หลัก\x00")
        ),
        {"label": "หลัก", "key": KEY, "secret": SECRET * 10},
        {"label": "หลัก", "key": KEY * 20, "secret": SECRET},
        {"label": "หลัก", "key": KEY + "ทดสอบ", "secret": SECRET},
        {"label": "หลัก", "key": KEY + "\r\ninjected", "secret": SECRET},
        {"label": "หลัก", "key": KEY + "\x00", "secret": SECRET},
        {"label": "หลัก", "key": KEY + "\x7f", "secret": SECRET},
        {"label": "หลัก", "key": KEY, "secret": {"nested": SECRET}},
        {"label": "หลัก", "key": [KEY], "secret": SECRET},
        {"label": {SECRET: KEY}, "key": KEY, "secret": SECRET},
        {"key": KEY, "secret": SECRET},
        [{"key": KEY, "secret": SECRET}],
    ],
)
def test_invalid_key_input_never_returns_or_logs_credentials(
    client: TestClient, caplog: pytest.LogCaptureFixture, body: object
) -> None:
    """V-4/V-7 — validation ต้องไม่สะท้อน input แม้ข้อผิดพลาดอยู่ในช่องอื่น"""
    register(client)
    second_factor, _ = enable_totp(client)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        refused = client.post(
            "/api-keys",
            json=body,
            headers=csrf_headers(client) | {TOTP_HEADER: code_now(second_factor)},
        )

    assert refused.status_code == 422
    assert SECRET not in refused.text + caplog.text
    assert KEY not in refused.text + caplog.text
    if isinstance(body, dict) and isinstance(body.get("label"), str) and "\x00" in body["label"]:
        assert body["label"] not in refused.text + caplog.text
    assert refused.json() == {"detail": "API_KEY_REJECTED_INPUT"}
    assert client.get("/api-keys").json() == []


def test_malformed_json_never_returns_or_logs_credentials(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """V-7 — JSON ผิดรูปต้องไม่พาค่าดิบออกมากับข้อผิดพลาดของ parser"""
    register(client)
    second_factor, _ = enable_totp(client)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        refused = client.post(
            "/api-keys",
            content=f'{{"label":"หลัก","key":"{KEY}","secret":"{SECRET}"',
            headers=csrf_headers(client)
            | {TOTP_HEADER: code_now(second_factor), "Content-Type": "application/json"},
        )

    assert refused.status_code == 422
    assert SECRET not in refused.text + caplog.text
    assert KEY not in refused.text + caplog.text
    assert refused.json() == {"detail": "API_KEY_REJECTED_INPUT"}
    assert client.get("/api-keys").json() == []


def test_the_cap_is_enforced_through_the_route(client: TestClient) -> None:
    """V-29 — เกินเพดานแล้วเส้นทางปฏิเสธด้วยรหัสที่ถูกต้อง"""
    register(client)
    secret, _ = enable_totp(client)
    _seed_keys(_user_id(client), MAX_KEYS_PER_USER)

    refused = _add(client, secret, label="เกิน")

    assert refused.status_code == 409, refused.text


def test_pressing_retry_too_fast_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V-30 — ถังของการกดลองใหม่ทำงานจริงผ่านเส้นทาง (RQ-11)

    ใช้ปุ่มลองใหม่พิสูจน์เรื่องนี้เพราะมันไม่ต้องยืนยันซ้ำ จึงกดติดกันได้จริง
    ส่วนถังของการเพิ่ม key ใช้ตรรกะเดียวกันและมีเทสต์ของชั้นถังเอง
    """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    seen = [
        client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client)).status_code
        for _ in range(API_KEY_RETRY_CAPACITY + 2)
    ]

    assert 429 in seen, seen
    # Only the original authorized ADD work may run; throttled retries add no attempt.
    assert _worker_calls_for_owner(_user_id(client), monkeypatch) == 1


def test_a_retry_on_a_pending_key_is_refused(client: TestClient) -> None:
    """Q-7 — ปุ่มลองใหม่มีเฉพาะแถวที่ตรวจไม่ได้ชั่วคราว"""
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    refused = client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client))

    assert refused.status_code == 409, refused.text


def test_retrying_needs_no_second_factor(client: TestClient) -> None:
    """V-26 — กดลองใหม่ไม่ต้องยืนยันซ้ำ (เจ้าของตัดสิน 2026-10-04)

    ที่พิสูจน์คือ **ไม่ถูกปฏิเสธเพราะไม่ได้ยืนยันซ้ำ** — คำตอบจะเป็น 409 เพราะสถานะ
    ยังเป็น "กำลังตรวจ" ซึ่งเป็นคนละเรื่องกับการยืนยันตัวตน
    """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    answer = client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client))

    assert answer.status_code != 403, answer.text


def test_another_users_key_is_not_found(client: TestClient) -> None:
    """V-28 — ลบของคนอื่นได้ "ไม่พบ" ไม่ใช่ "ไม่มีสิทธิ์" """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    client.post("/auth/logout", headers=csrf_headers(client))
    client.get("/auth/csrf")
    register(client, password=GOOD_PASSWORD)

    answer = client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client))

    assert answer.status_code == 404, answer.text


def test_deleting_own_key_works(client: TestClient) -> None:
    """V-12 — ลบของตัวเองได้ และหายจากรายการ"""
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    deleted = client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client))

    assert deleted.status_code == 204, deleted.text
    assert client.get("/api-keys").json() == []


def test_the_retry_quota_counts_per_user_not_per_key(client: TestClient) -> None:
    """V-30.1 — ถังนับต่อผู้ใช้ รวมทุก key (RQ-11.1)

    ถ้านับต่อ key การเพิ่ม key ใบใหม่จะกลายเป็นวิธีได้โควตาใหม่
    """
    register(client)
    secret, _ = enable_totp(client)
    first = _add(client, secret).json()["id"]
    for _ in range(API_KEY_RETRY_CAPACITY + 1):
        client.post(f"/api-keys/{first}/retry", headers=csrf_headers(client))

    # Cap1 permits replacement after deletion; replacing a key must not reset
    # the owner's retry quota or create a fresh per-key bucket.
    assert client.delete(f"/api-keys/{first}", headers=csrf_headers(client)).status_code == 204
    _seed_keys(_user_id(client), 1)
    second = client.get("/api-keys").json()[0]["id"]
    assert second != first

    refused = client.post(f"/api-keys/{second}/retry", headers=csrf_headers(client))

    assert refused.status_code == 429, refused.text


def test_being_throttled_says_when_to_come_back(client: TestClient) -> None:
    """V-30.4 — คำตอบ 429 บอกเวลาที่ลองได้อีกครั้ง (RQ-11.3)

    **ต่างจากข้อความของ F-06 โดยตั้งใจ** — ที่นั่นคนที่ถูกปฏิเสธอาจกำลังเดารหัส
    ส่วนที่นี่เขาถือความลับของตัวเองอยู่แล้ว
    """
    register(client)
    secret, _ = enable_totp(client)
    key_id = _add(client, secret).json()["id"]

    answer = None
    for _ in range(API_KEY_RETRY_CAPACITY + 2):
        answer = client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client))

    assert answer is not None
    assert answer.status_code == 429, answer.text
    assert int(answer.headers["Retry-After"]) > 0


def test_a_successful_request_also_spends_quota(client: TestClient) -> None:
    """V-30.2 — นับทุกครั้งที่กด ไม่ใช่เฉพาะที่ล้มเหลว (RQ-11.2)

    นับเฉพาะที่ล้มเหลวแปลว่าลองคำรับรองได้ไม่จำกัดตราบใดที่เดาถูก
    """
    register(client)
    owner = _user_id(client)
    _seed_keys(owner, 1)
    _set_retry_view_state(owner, "UNVERIFIABLE", None)
    (item,) = client.get("/api-keys").json()
    key_id = item["id"]

    seen = [
        client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client)).status_code
        for _ in range(API_KEY_RETRY_CAPACITY + 1)
    ]

    assert seen == [202] * API_KEY_RETRY_CAPACITY + [429], seen


def test_user_key_actions_have_complete_audit_entries(client: TestClient) -> None:
    """V-35: add/retry/delete ผ่าน HTTP ไม่ใช้ store helper แทน audit ของ route."""
    import asyncio

    register(client)
    second_factor, _ = enable_totp(client)
    owner = _user_id(client)
    added = _add(client, second_factor)
    assert added.status_code == 201
    key_id = UUID(added.json()["id"])
    _set_retry_view_state(owner, "UNVERIFIABLE", None)
    assert client.post(f"/api-keys/{key_id}/retry", headers=csrf_headers(client)).status_code == 202
    assert client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client)).status_code == 204

    async def read() -> list[dict[str, object]]:
        engine = create_engine_for(DatabaseRole.API)
        try:
            return await read_key_audit_events(engine, owner, key_id, role=DatabaseRole.API)
        finally:
            await engine.dispose()

    rows = asyncio.get_event_loop().run_until_complete(read())
    assert rows == [
        expected_key_audit_event(
            owner, key_id, action=action, actor_kind="USER", outcome="SUCCEEDED"
        )
        for action in (
            "API_KEY_ADDED",
            "API_KEY_RETRY_REQUESTED",
            "API_KEY_DELETED",
        )
    ]
    assert KEY not in repr(rows)
    assert SECRET not in repr(rows)


@pytest.mark.parametrize("kind", ["wrong-totp", "recovery-grant"])
def test_api_key_add_rejects_wrong_totp_and_recovery_grant(client: TestClient, kind: str) -> None:
    email = register(client)
    secret, recovery = enable_totp(client)
    headers = csrf_headers(client)
    if kind == "wrong-totp":
        accepted = {code_now(secret), code_one_step_back(secret)}
        wrong = next(f"{number:06d}" for number in range(3) if f"{number:06d}" not in accepted)
        headers[TOTP_HEADER] = wrong
    else:
        sign_in(client, email)
        signed = client.post(
            "/auth/totp/login", json={"recovery_code": recovery[0]}, headers=csrf_headers(client)
        )
        assert signed.status_code == 200
        headers = csrf_headers(client)
    response = client.post(
        "/api-keys", json={"label": "private", "key": KEY, "secret": SECRET}, headers=headers
    )
    assert response.status_code == 403
    assert client.get("/api-keys").json() == []
    assert SECRET not in response.text and KEY not in response.text


def _worker_calls_for_owner(owner: UUID, monkeypatch: pytest.MonkeyPatch) -> int:
    """Run the real scan/claim/write path with an owner-isolated view of the test work queue."""
    import asyncio

    from tests.services.engine.conftest import ScriptedWallet
    from tiewtrade.infra.crypto import KeyPurpose, KeySource
    from tiewtrade.services.engine import verification

    market = ScriptedWallet(outcomes=[])
    from tiewtrade.infra.api_keys import claims

    scoped_scan = claims._DUE_HINTS.replace(
        "WHERE status", f"WHERE user_id = '{owner}'::uuid AND status", 1
    )
    assert scoped_scan != claims._DUE_HINTS

    async def run() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
        try:
            for _ in range(2):
                await verification.run_round(
                    engine=engine,
                    scan_engine=scan,
                    keys=KeySource.from_environment(KeyPurpose.VENUE_API_SECRET),
                    wallet_for=cast(verification.WalletFactory, market.factory()),
                    worker="quota-validation",
                )
        finally:
            await engine.dispose()
            await scan.dispose()

    with monkeypatch.context() as filtering:
        filtering.setattr(claims, "_DUE_HINTS", scoped_scan)
        asyncio.get_event_loop().run_until_complete(run())
    return market.calls


def test_add_quota_exhaustion_creates_no_worker_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    from tiewtrade.services.api.throttling import spend_token

    register(client)
    secret, _ = enable_totp(client)
    owner = _user_id(client)

    async def exhaust() -> None:
        engine = create_engine_for(DatabaseRole.API)
        try:
            for _ in range(API_KEY_ADD_CAPACITY):
                await spend_token(engine, owner, Bucket.API_KEY_ADD)
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(exhaust())
    response = _add(client, secret)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert client.get("/api-keys").json() == []
    assert _worker_calls_for_owner(owner, monkeypatch) == 0
