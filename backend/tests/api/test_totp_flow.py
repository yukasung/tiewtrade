"""วงจรของปัจจัยที่สองจากมุมผู้เรียก — V-5, V-12, V-13, V-21 ถึง V-26, V-40 ถึง V-46

ยิงผ่าน HTTP จริงกับฐานข้อมูลจริง เพราะสิ่งที่ต้องพิสูจน์คือพฤติกรรมที่ผู้ใช้สัมผัส
ไม่ใช่การเรียกฟังก์ชันภายใน
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from tests.api.conftest import (
    GOOD_PASSWORD,
    cookies_now,
    csrf_headers,
    register,
    unique_email,
    use_cookies,
)
from tiewtrade.core.totp import code_for, step_at
from tiewtrade.infra.auth import totp
from tiewtrade.infra.crypto import KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import UserSession, user_session
from tiewtrade.services.api import totp_routes
from tiewtrade.services.api.app import app
from tiewtrade.services.api.settings import (
    CHALLENGE_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    TOTP_HEADER,
)


def secret_of(uri: str) -> bytes:
    """secret ที่อยู่ใน otpauth URI — เทสต์ทำตัวเหมือนแอป authenticator"""
    import base64

    encoded = uri.split("secret=")[1].split("&")[0]
    return base64.b32decode(encoded + "=" * (-len(encoded) % 8))


def code_now(secret: bytes) -> str:
    """รหัสของช่วงเวลาปัจจุบัน"""
    return code_for(secret, step_at(datetime.now(UTC)))


def code_one_step_back(secret: bytes) -> str:
    """รหัสของช่วงก่อนหน้า — ยังอยู่ในหน้าต่างที่ระบบยอมรับ (Q-8)

    **ใช้ตอนเปิดใช้โดยเจตนา** เพราะ RQ-4 กันการใช้รหัสซ้ำตลอดช่วงที่ยังถูกยอมรับ
    ฉะนั้นถ้ายืนยันด้วยรหัสของช่วงปัจจุบัน รหัสนั้นจะใช้ทำอย่างอื่นในช่วงเดียวกัน
    ไม่ได้อีก — ซึ่งถูกต้องตามข้อกำหนด แต่ทำให้เทสต์ต้องรอ 30 วินาที
    การยืนยันด้วยช่วงก่อนหน้าเลี่ยงการรอโดยไม่ได้ปิดกฎใด
    """
    return code_for(secret, step_at(datetime.now(UTC)) - 1)


def headers_from(saved: dict[str, str]) -> dict[str, str]:
    """header กัน CSRF จาก cookie ที่บันทึกไว้

    อ่านจากค่าที่บันทึกไว้ ไม่ใช่เรียก `/auth/csrf` ใหม่ เพราะการสวมรอย cookie
    กลับเข้าไปแล้วขอใบใหม่ทำให้ไคลเอนต์ของเทสต์มี cookie ชื่อเดียวกันสองใบ
    """
    return {CSRF_HEADER: saved[CSRF_COOKIE]}


def enable_totp(client: TestClient, *, password: str = GOOD_PASSWORD) -> tuple[bytes, list[str]]:
    """เปิด TOTP ให้ผู้ใช้ที่ไคลเอนต์ถือ session อยู่ — คืน secret กับรหัสสำรอง"""
    started = client.post(
        "/auth/totp/setup", json={"password": password}, headers=csrf_headers(client)
    )
    assert started.status_code == 200, started.text
    secret = secret_of(started.json()["otpauth_uri"])

    confirmed = client.post(
        "/auth/totp/confirm",
        json={"code": code_one_step_back(secret)},
        headers=csrf_headers(client),
    )
    assert confirmed.status_code == 200, confirmed.text
    return secret, confirmed.json()["recovery_codes"]


def audit_count(user_id: str, action: str) -> int:
    """จำนวนบันทึกของชนิดนั้นที่ผู้ใช้คนนั้นมี — อ่านจากฐานข้อมูลจริง

    อ่านตรงเพราะยังไม่มี endpoint ให้ดู audit log และสิ่งที่ต้องพิสูจน์คือ
    **มันถูกเขียนลงไปจริง** ไม่ใช่ว่ามีโค้ดเรียกตัวเขียน

    ต้องอ่านในฐานะผู้ใช้คนนั้น เพราะ `audit_events` อยู่ใต้ RLS ตามเจ้าของ —
    ไม่ระบุผู้ใช้แล้วได้ศูนย์แถวเสมอ ซึ่งจะทำให้เทสต์เขียวแบบหลอกได้ง่ายมาก
    """
    import asyncio
    from uuid import UUID

    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.infra.db.session import user_session

    async def read() -> int:
        engine = create_engine_for(DatabaseRole.AUTH)
        try:
            async with user_session(engine, UUID(user_id), role=DatabaseRole.AUTH) as session:
                row = (
                    await session.execute(
                        "SELECT count(*) FROM audit_events WHERE action = :a",
                        {"a": action},
                    )
                ).one()
                return int(next(iter(row)))
        finally:
            await engine.dispose()

    return asyncio.run(read())


def sign_in(client: TestClient, email: str, *, password: str = GOOD_PASSWORD) -> dict[str, object]:
    """ขั้นแรกของการเข้าสู่ระบบจากเครื่องเปล่า"""
    client.cookies.clear()
    client.get("/auth/csrf")
    response = client.post(
        "/auth/login", json={"email": email, "password": password}, headers=csrf_headers(client)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_setup_needs_the_current_password(client: TestClient) -> None:
    """V-12 — session อย่างเดียวไม่พอ (RQ-3.1)"""
    register(client)

    refused = client.post(
        "/auth/totp/setup", json={"password": "ไม่ใช่รหัสผ่านของบัญชีนี้"}, headers=csrf_headers(client)
    )

    assert refused.status_code == 401


def test_setup_cannot_replace_an_enabled_authenticator(client: TestClient) -> None:
    """Q-4 — session กับรหัสผ่านไม่พอสำหรับเปลี่ยนเครื่องที่เปิดอยู่แล้ว"""
    register(client)
    secret, _ = enable_totp(client)
    refused = client.post(
        "/auth/totp/setup", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
    )
    assert refused.status_code == 409, refused.text
    # เครื่องเดิมยังยืนยันซ้ำได้ และไม่มี secret ใหม่ถูกแจก
    assert "otpauth_uri" not in refused.json()
    headers = csrf_headers(client) | {TOTP_HEADER: code_now(secret)}
    assert (
        client.post(
            "/auth/totp/recovery-codes", json={"password": GOOD_PASSWORD}, headers=headers
        ).status_code
        == 200
    )


@pytest.fixture
def roaming_client() -> Iterator[tuple[TestClient, list[str]]]:
    """เปลี่ยน IP จริงใน ASGI โดยคง session และ lifespan เดิม"""
    address = ["192.0.2.1"]

    async def from_address(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope = dict(scope, client=(address[0], 50000))
        await app(scope, receive, send)

    with TestClient(from_address) as client:
        client.get("/auth/csrf")
        yield client, address


def test_setup_cannot_race_initial_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q-4 + plan 1.1 — confirm กับ setup ต้องใช้ล็อกบัญชีเดียวกัน"""
    register(client)
    started = client.post(
        "/auth/totp/setup", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
    )
    secret = secret_of(started.json()["otpauth_uri"])
    activated, checked, release = Event(), Event(), Event()
    original_confirm = totp.confirm_secret
    original_enabled = totp.is_enabled

    async def paused_confirm(
        session: UserSession, keys: KeySource, *, presented: str, now: datetime
    ) -> bool:
        passed = await original_confirm(session, keys, presented=presented, now=now)
        activated.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return passed

    async def observed_enabled(session: UserSession) -> bool:
        enabled = await original_enabled(session)
        if activated.is_set():
            checked.set()
        return enabled

    monkeypatch.setattr(totp, "confirm_secret", paused_confirm)
    monkeypatch.setattr(totp, "is_enabled", observed_enabled)
    headers = csrf_headers(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        confirming = pool.submit(
            client.post,
            "/auth/totp/confirm",
            json={"code": code_one_step_back(secret)},
            headers=headers,
        )
        try:
            assert activated.wait(timeout=5), "confirm ไม่ถึงจุดสลับ secret"
            setting_up = pool.submit(
                client.post,
                "/auth/totp/setup",
                json={"password": GOOD_PASSWORD},
                headers=headers,
            )
            # โค้ดเดิมอ่านสถานะก่อน confirm commit; โค้ดที่ล็อกถูกต้องจะรอ
            checked.wait(timeout=1)
        finally:
            release.set()
        assert confirming.result(timeout=5).status_code == 200
        assert setting_up.result(timeout=5).status_code == 409


@pytest.mark.parametrize(
    "target",
    ["/auth/totp/replace", "/auth/totp/disable", "/auth/totp/recovery-codes", "/auth/totp/confirm"],
)
@pytest.mark.parametrize("source", ["login", "reverify"])
def test_second_factor_quota_is_shared_over_http(
    roaming_client: tuple[TestClient, list[str]], target: str, source: str
) -> None:
    """V-62.2 — ใช้โควตาหมดผ่าน HTTP แล้วย้ายจุดตรวจจริง"""
    from tiewtrade.infra.auth.throttle import SECOND_FACTOR_CAPACITY

    client, address = roaming_client
    email = register(client)
    secret, _ = enable_totp(client)
    signed_in = cookies_now(client)
    if source == "login":
        sign_in(client, email)
    for _ in range(SECOND_FACTOR_CAPACITY):
        if source == "login":
            response = client.post(
                "/auth/totp/login", json={"code": "invalid"}, headers=csrf_headers(client)
            )
        else:
            response = client.post(
                "/auth/totp/recovery-codes",
                json={"password": GOOD_PASSWORD},
                headers=csrf_headers(client) | {TOTP_HEADER: "invalid"},
            )
        assert response.status_code == 403, response.text
    use_cookies(client, signed_in)
    address[0] = "192.0.2.2"  # ถัง IP ใหม่ยังเต็ม ต้องหยุดด้วยถังบัญชี
    response = client.post(
        target,
        json={"code": "invalid"} if target.endswith("/confirm") else {"password": GOOD_PASSWORD},
        headers=csrf_headers(client) | {TOTP_HEADER: code_now(secret)},
    )
    assert response.status_code == 429, response.text


def test_stale_challenge_cleanup_survives_http_rejection(client: TestClient) -> None:
    """การปฏิเสธรุ่นรหัสผ่านเก่าต้องไม่ย้อนการลบ challenge ทิ้ง"""
    email = register(client)
    account = UUID(client.get("/auth/me").json()["user_id"])
    secret, _ = enable_totp(client)
    sign_in(client, email)

    async def challenge_rows(*, make_stale: bool = False) -> int:
        engine = create_engine_for(DatabaseRole.AUTH)
        try:
            async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
                if make_stale:
                    # จำลองชั้นลบตรง ๆ หลุด เพื่อพิสูจน์ด่านตรวจรุ่นแยกจากกัน
                    await session.execute(
                        "UPDATE user_credentials SET updated_at = "
                        "updated_at + interval '1 second' WHERE user_id = :id",
                        {"id": str(account)},
                    )
                return int(
                    (await session.execute("SELECT count(*) FROM login_challenges")).scalar_one()
                )
        finally:
            await engine.dispose()

    assert asyncio.run(challenge_rows(make_stale=True)) == 1
    response = client.post(
        "/auth/totp/login", json={"code": code_now(secret)}, headers=csrf_headers(client)
    )
    assert response.status_code == 403, response.text
    assert asyncio.run(challenge_rows()) == 0, "การลบ challenge ถูก rollback หลัง HTTP 403"


def test_a_stolen_session_cannot_bind_its_own_authenticator(client: TestClient) -> None:
    """V-13 — คนที่มีแต่ session ขโมยมา เดินวงจรตั้งค่าให้จบไม่ได้

    จำลองด้วย cookie ที่คัดลอกไว้ **โดยไม่รู้รหัสผ่าน** ซึ่งเป็นสภาพของผู้โจมตีจริง
    """
    register(client)
    stolen = cookies_now(client)

    use_cookies(client, stolen)
    refused = client.post(
        "/auth/totp/setup", json={"password": "เดารหัสผ่านไม่ได้"}, headers=headers_from(stolen)
    )

    assert refused.status_code == 401


def test_enabling_returns_recovery_codes_once(client: TestClient) -> None:
    """RQ-3 และ Q-3.2 — เปิดใช้สำเร็จแล้วได้รหัสสำรองชุดใหม่ทันที"""
    register(client)

    _, codes = enable_totp(client)

    assert len(codes) == len(set(codes))
    assert codes

    me = client.get("/auth/me")
    assert me.json()["totp_enabled"] is True


def test_the_confirmed_secret_is_never_returned_again(client: TestClient) -> None:
    """V-5 — ไม่มี endpoint คืน secret ที่ยืนยันแล้ว"""
    register(client)
    secret, _ = enable_totp(client)
    encoded = secret.hex()

    for response in (client.get("/auth/me"), client.get("/health")):
        assert encoded not in response.text
        assert secret not in response.content


def test_a_password_alone_no_longer_signs_in(client: TestClient) -> None:
    """V-21 — ผู้ใช้ที่เปิด TOTP **ไม่ได้ cookie ของ session จากขั้นแรก**"""
    email = register(client)
    enable_totp(client)

    body = sign_in(client, email)

    assert body["second_step_required"] is True
    assert not client.cookies.get(SESSION_COOKIE)
    assert client.cookies.get(CHALLENGE_COOKIE)


def test_the_challenge_cannot_call_anything_else(client: TestClient) -> None:
    """V-22 — challenge ใช้เรียกเส้นทางที่ต้องมีสิทธิ์ไม่ได้เลย"""
    email = register(client)
    enable_totp(client)
    sign_in(client, email)

    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/logout", headers=csrf_headers(client)).status_code == 401


def test_the_second_step_completes_the_sign_in(client: TestClient) -> None:
    """ขั้นที่สองออก session จริง และ challenge หายไป"""
    email = register(client)
    secret, _ = enable_totp(client)
    sign_in(client, email)

    done = client.post(
        "/auth/totp/login", json={"code": code_now(secret)}, headers=csrf_headers(client)
    )

    assert done.status_code == 200, done.text
    assert client.cookies.get(SESSION_COOKIE)
    assert client.get("/auth/me").status_code == 200


def test_a_wrong_second_step_does_not_sign_in(client: TestClient) -> None:
    """รหัสผิดต้องไม่ได้ session และ challenge ยังอยู่ให้ลองใหม่"""
    email = register(client)
    enable_totp(client)
    sign_in(client, email)

    refused = client.post("/auth/totp/login", json={"code": "000000"}, headers=csrf_headers(client))

    assert refused.status_code == 403
    assert not client.cookies.get(SESSION_COOKIE)
    assert client.cookies.get(CHALLENGE_COOKIE), "challenge หายไปทั้งที่คำขอล้มเหลว (V-24.1)"


def test_sending_both_kinds_of_code_is_refused(client: TestClient) -> None:
    """คำขอกำกวมต้องไม่ได้ประโยชน์จากการเดาสองทางในโควตาเดียว"""
    email = register(client)
    secret, codes = enable_totp(client)
    sign_in(client, email)

    refused = client.post(
        "/auth/totp/login",
        json={"code": code_now(secret), "recovery_code": codes[0]},
        headers=csrf_headers(client),
    )

    assert refused.status_code == 403


def test_a_recovery_code_signs_in_and_reports_what_is_left(client: TestClient) -> None:
    """Q-3.1 ช่อง ก — รหัสสำรองใช้เข้าสู่ระบบได้ และบอกจำนวนที่เหลือ"""
    email = register(client)
    _, codes = enable_totp(client)
    sign_in(client, email)

    done = client.post(
        "/auth/totp/login", json={"recovery_code": codes[0]}, headers=csrf_headers(client)
    )

    assert done.status_code == 200, done.text
    assert done.json()["recovery_codes_left"] == len(codes) - 1
    assert client.get("/auth/me").status_code == 200


def test_the_last_recovery_code_still_reaches_a_new_device(client: TestClient) -> None:
    """V-40 — **เหลือใบเดียว → login → ผูกเครื่องใหม่ → ได้ชุดใหม่ ในรอบเดียว**

    กับดักที่ข้อนี้กัน: ใช้ใบสุดท้าย login แล้วถูกขออีกใบตอนเปลี่ยน secret
    """
    email = register(client)
    _, codes = enable_totp(client)

    # ใช้ไปจนเหลือใบเดียว
    for code in codes[:-1]:
        sign_in(client, email)
        assert (
            client.post(
                "/auth/totp/login", json={"recovery_code": code}, headers=csrf_headers(client)
            ).status_code
            == 200
        )

    sign_in(client, email)
    last = client.post(
        "/auth/totp/login", json={"recovery_code": codes[-1]}, headers=csrf_headers(client)
    )
    assert last.status_code == 200
    assert last.json()["recovery_codes_left"] == 0

    # **ไม่ขอรหัสสำรองใบที่สอง** — สิทธิ์กู้บัญชีของ session นี้พาไปถึงเครื่องใหม่ได้
    replaced = client.post(
        "/auth/totp/replace", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
    )
    assert replaced.status_code == 200, replaced.text
    fresh = secret_of(replaced.json()["otpauth_uri"])

    confirmed = client.post(
        "/auth/totp/confirm",
        json={"code": code_one_step_back(fresh)},
        headers=csrf_headers(client),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["recovery_codes"], "ไม่ได้ชุดรหัสสำรองใหม่หลังผูกเครื่องใหม่"


def test_a_recovery_grant_works_once(client: TestClient) -> None:
    """V-41.3 ที่ระดับเส้นทาง — สิทธิ์กู้บัญชีใช้ได้ครั้งเดียว"""
    email = register(client)
    _, codes = enable_totp(client)
    sign_in(client, email)
    client.post("/auth/totp/login", json={"recovery_code": codes[0]}, headers=csrf_headers(client))

    assert (
        client.post(
            "/auth/totp/replace", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
        ).status_code
        == 200
    )
    second = client.post(
        "/auth/totp/replace", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
    )

    assert second.status_code == 403, "สิทธิ์กู้บัญชีถูกใช้ได้สองครั้ง"


def test_replacing_needs_a_second_factor(client: TestClient) -> None:
    """เส้นทางที่เปลี่ยนปัจจัยที่สองต้องยืนยันซ้ำ — รหัสผ่านอย่างเดียวไม่พอ"""
    register(client)
    secret, _ = enable_totp(client)

    refused = client.post(
        "/auth/totp/replace", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
    )
    assert refused.status_code == 403

    allowed = client.post(
        "/auth/totp/replace",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: code_now(secret)},
    )
    assert allowed.status_code == 200, allowed.text


def test_replacing_keeps_the_old_factor_until_it_is_confirmed(client: TestClient) -> None:
    """V-11.1 ที่ระดับเส้นทาง — ทิ้งกลางทางแล้วเครื่องเดิมยังใช้เข้าสู่ระบบได้"""
    email = register(client)
    secret, codes = enable_totp(client)

    # เข้าสู่ระบบด้วยรหัสสำรองเพื่อได้สิทธิ์กู้บัญชี แล้วเริ่มเปลี่ยนเครื่องด้วยสิทธิ์นั้น
    # — ทางนี้ไม่กินช่วงเวลาของ TOTP จึงเหลือรหัสของช่วงปัจจุบันไว้ให้ขั้นที่สอง
    sign_in(client, email)
    assert (
        client.post(
            "/auth/totp/login", json={"recovery_code": codes[0]}, headers=csrf_headers(client)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/totp/replace", json={"password": GOOD_PASSWORD}, headers=csrf_headers(client)
        ).status_code
        == 200
    )

    sign_in(client, email)
    done = client.post(
        "/auth/totp/login", json={"code": code_now(secret)}, headers=csrf_headers(client)
    )

    assert done.status_code == 200, done.text


def test_disabling_needs_a_second_factor_and_clears_everything(client: TestClient) -> None:
    """Q-4 — ปิดได้ด้วยรหัสผ่าน + รหัสปัจจุบัน และรหัสสำรองใช้ไม่ได้อีก"""
    email = register(client)
    secret, _ = enable_totp(client)

    done = client.post(
        "/auth/totp/disable",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: code_now(secret)},
    )
    assert done.status_code == 200, done.text
    assert client.get("/auth/me").json()["totp_enabled"] is False

    # รหัสผ่านอย่างเดียวเข้าได้แล้ว และรหัสสำรองเก่าไม่มีที่ใช้
    body = sign_in(client, email)
    assert body["second_step_required"] is False
    assert client.cookies.get(SESSION_COOKIE)


def test_disabling_is_refused_while_live_trading_is_on(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V-60 — **ปิด TOTP ขณะที่ Live เปิดอยู่ไม่ได้** (Q-4)

    ยังไม่มี Live ในระบบ จึงแทนค่าของรอยต่อที่ **F-24 ต้องมาแทนที่ด้วยของจริง**
    """
    register(client)
    secret, _ = enable_totp(client)

    async def live(_: object) -> bool:
        return True

    monkeypatch.setattr(totp_routes, "live_trading_enabled", live)
    refused = client.post(
        "/auth/totp/disable",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: code_now(secret)},
    )

    assert refused.status_code == 409
    assert client.get("/auth/me").json()["totp_enabled"] is True


def test_reissuing_recovery_codes_revokes_the_old_set(client: TestClient) -> None:
    """V-37 ที่ระดับเส้นทาง — ขอชุดใหม่แล้วชุดเก่าใช้ไม่ได้"""
    email = register(client)
    secret, old = enable_totp(client)

    issued = client.post(
        "/auth/totp/recovery-codes",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: code_now(secret)},
    )
    assert issued.status_code == 200, issued.text
    fresh = issued.json()["recovery_codes"]
    assert set(fresh).isdisjoint(old)

    sign_in(client, email)
    refused = client.post(
        "/auth/totp/login", json={"recovery_code": old[0]}, headers=csrf_headers(client)
    )
    assert refused.status_code == 403


def test_enabling_revokes_the_other_devices(client: TestClient) -> None:
    """V-42 — เปิด TOTP ครั้งแรกแล้ว session อื่นทั้งหมดถูกเพิกถอน (Q-3.4)"""
    email = register(client)
    first_device = cookies_now(client)

    client.cookies.clear()
    client.get("/auth/csrf")
    assert (
        client.post(
            "/auth/login",
            json={"email": email, "password": GOOD_PASSWORD},
            headers=csrf_headers(client),
        ).status_code
        == 200
    )
    second_device = cookies_now(client)

    use_cookies(client, second_device)
    result = client.post(
        "/auth/totp/setup", json={"password": GOOD_PASSWORD}, headers=headers_from(second_device)
    )
    assert result.status_code == 200
    secret = secret_of(result.json()["otpauth_uri"])
    confirmed = client.post(
        "/auth/totp/confirm",
        json={"code": code_one_step_back(secret)},
        headers=headers_from(second_device),
    )
    assert confirmed.json()["ended"] >= 1

    use_cookies(client, first_device)
    assert client.get("/auth/me").status_code == 401, "เครื่องเก่ายังใช้ได้หลังเปิด TOTP"


def test_a_challenge_dies_when_the_password_changes(client: TestClient) -> None:
    """V-26.1 — challenge ที่ออกด้วยรหัสผ่านเก่าใช้ต่อไม่ได้ (RQ-22 ของ F-05)"""
    email = register(client, email=unique_email())
    secret, _ = enable_totp(client)
    signed_in = cookies_now(client)

    # เครื่องที่สองเริ่มขั้นแรกไว้ แล้วยังไม่กรอกรหัส
    client.cookies.clear()
    client.get("/auth/csrf")
    assert (
        client.post(
            "/auth/login",
            json={"email": email, "password": GOOD_PASSWORD},
            headers=csrf_headers(client),
        ).status_code
        == 200
    )
    waiting = cookies_now(client)

    # เจ้าของเปลี่ยนรหัสผ่านจากเครื่องแรก
    use_cookies(client, signed_in)
    changed = client.post(
        "/auth/password",
        json={"current_password": GOOD_PASSWORD, "new_password": "รหัสผ่านใหม่ที่ยาวพอใช้งาน"},
        headers=headers_from(signed_in),
    )
    assert changed.status_code == 200, changed.text

    use_cookies(client, waiting)
    refused = client.post(
        "/auth/totp/login", json={"code": code_now(secret)}, headers=headers_from(waiting)
    )

    assert refused.status_code == 403, "challenge ของรหัสผ่านเก่ายังผ่านได้"


@pytest.mark.parametrize("target", ["/auth/totp/replace", "/auth/totp/disable"])
def test_recovery_grant_survives_exhausted_totp_quota(
    roaming_client: tuple[TestClient, list[str]], target: str
) -> None:
    """สิทธิ์กู้ไม่ใช่การเดารหัส TOTP — ถัง TOTP หมดต้องไม่ขวางสิทธิ์นี้"""
    from tiewtrade.infra.auth.throttle import SECOND_FACTOR_CAPACITY

    client, address = roaming_client
    email = register(client)
    _, codes = enable_totp(client)
    for _ in range(SECOND_FACTOR_CAPACITY):
        refused = client.post(
            "/auth/totp/recovery-codes",
            json={"password": GOOD_PASSWORD},
            headers=csrf_headers(client) | {TOTP_HEADER: "invalid"},
        )
        assert refused.status_code == 403
    address[0] = "192.0.2.2"
    sign_in(client, email)
    recovered = client.post(
        "/auth/totp/login", json={"recovery_code": codes[0]}, headers=csrf_headers(client)
    )
    assert recovered.status_code == 200, recovered.text
    changed = client.post(target, json={"password": GOOD_PASSWORD}, headers=csrf_headers(client))
    assert changed.status_code == 200, changed.text


def test_a_recovery_login_revokes_the_other_devices(client: TestClient) -> None:
    """V-43 — **เข้าสู่ระบบด้วยรหัสสำรองแล้ว session เครื่องอื่นต้องถูกเพิกถอน** (Q-3.4)

    การใช้รหัสสำรองหมายถึง "อุปกรณ์เดิมหายไป" ซึ่งเป็นสัญญาณเดียวกับที่ F-05 ใช้
    ตอนเปลี่ยนรหัสผ่าน · ถ้าไม่เพิกถอน ผู้โจมตีที่ถือ session อยู่จะยังอยู่ต่อได้
    ทั้งที่เจ้าของเพิ่งใช้ทางกู้บัญชี
    """
    email = register(client)
    _, codes = enable_totp(client)
    first_device = cookies_now(client)

    sign_in(client, email)
    done = client.post(
        "/auth/totp/login", json={"recovery_code": codes[0]}, headers=csrf_headers(client)
    )
    assert done.status_code == 200, done.text

    use_cookies(client, first_device)
    assert client.get("/auth/me").status_code == 401, "เครื่องเก่ายังใช้ได้หลังกู้บัญชี"


def test_a_recovery_login_records_the_revocation(client: TestClient) -> None:
    """V-46 — การเพิกถอนของการกู้บัญชีต้องลง `ALL_SESSIONS_ENDED` พร้อมจำนวน"""
    email = register(client)
    _, codes = enable_totp(client)
    account = str(client.get("/auth/me").json()["user_id"])
    before = audit_count(account, "ALL_SESSIONS_ENDED")

    sign_in(client, email)
    assert (
        client.post(
            "/auth/totp/login", json={"recovery_code": codes[0]}, headers=csrf_headers(client)
        ).status_code
        == 200
    )

    assert audit_count(account, "ALL_SESSIONS_ENDED") == before + 1


def test_a_reused_code_says_to_wait_for_a_new_one(client: TestClient) -> None:
    """V-61.2 — **รหัสที่ถูกใช้ไปแล้วต้องบอกให้รอรหัสใหม่** ไม่ใช่ตอบเหมือนรหัสผิด

    เป็นต้นทุนของการไม่มีช่วงผ่อนผัน (Q-6) ที่เจ้าของรับไว้: ทำสองรายการติดกัน
    ต้องรอรหัสของช่วงใหม่ · ถ้าตอบเหมือนรหัสผิด ผู้ใช้จะพิมพ์ซ้ำจนโควตาหมด
    """
    register(client)
    secret, _ = enable_totp(client)
    code = code_now(secret)

    first = client.post(
        "/auth/totp/recovery-codes",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: code},
    )
    assert first.status_code == 200, first.text

    again = client.post(
        "/auth/totp/recovery-codes",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: code},
    )

    assert again.status_code == 403
    assert "รอรหัส" in again.json()["detail"], again.text
    # และต้อง **ต่างจาก** ข้อความของรหัสผิด
    wrong = client.post(
        "/auth/totp/recovery-codes",
        json={"password": GOOD_PASSWORD},
        headers={**csrf_headers(client), TOTP_HEADER: "000000"},
    )
    assert wrong.json()["detail"] != again.json()["detail"]


def test_a_successful_check_does_not_refill_the_quota(client: TestClient) -> None:
    """V-62.5 — **ยืนยันสำเร็จจริงแล้วโควตาไม่กลับมา**

    เทสต์เดิมพิสูจน์ข้อนี้ไม่ได้ เพราะมันเรียก `clear()` แทนการยืนยันให้สำเร็จ
    (พบตอนตรวจคำรับรอง 2026-10-04) · ที่นี่ใช้เส้นทางจริง: ทำให้โควตาพร่องด้วย
    รหัสผิด แล้วยืนยันสำเร็จ แล้วตรวจว่าโควตาที่เหลือไม่ถูกคืน
    """
    register(client)
    secret, _ = enable_totp(client)

    # ใช้โควตาไปสองครั้งด้วยรหัสผิด
    for _ in range(2):
        assert (
            client.post(
                "/auth/totp/recovery-codes",
                json={"password": GOOD_PASSWORD},
                headers={**csrf_headers(client), TOTP_HEADER: "000000"},
            ).status_code
            == 403
        )

    # ยืนยันสำเร็จจริงหนึ่งครั้ง
    assert (
        client.post(
            "/auth/totp/recovery-codes",
            json={"password": GOOD_PASSWORD},
            headers={**csrf_headers(client), TOTP_HEADER: code_now(secret)},
        ).status_code
        == 200
    )

    # โควตาที่เหลือต้องยังพร่องอยู่ — ความจุ 4 ใช้ไป 2 เหลือ 2 ครั้งก่อนถูกกั้น
    refused_after = 0
    for _ in range(3):
        if (
            client.post(
                "/auth/totp/recovery-codes",
                json={"password": GOOD_PASSWORD},
                headers={**csrf_headers(client), TOTP_HEADER: "000000"},
            ).status_code
            == 429
        ):
            refused_after += 1
    assert refused_after >= 1, "ยืนยันสำเร็จแล้วโควตากลับมาเต็ม — ขัด Q-7"
