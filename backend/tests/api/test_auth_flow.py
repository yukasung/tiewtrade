"""เส้นทางยืนยันตัวตนจากมุมผู้เรียก — V-18 ถึง V-21, V-31 ถึง V-39, V-48, V-49

เทสต์กลุ่มนี้ยิงผ่าน HTTP จริงกับฐานข้อมูลจริง เพราะสิ่งที่ต้องพิสูจน์คือพฤติกรรม
ที่ผู้ใช้สัมผัส ไม่ใช่การเรียกฟังก์ชันภายใน
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    GOOD_PASSWORD,
    cookies_now,
    csrf_headers,
    register,
    session_cookie,
    sign_in_as_another_device,
    unique_email,
    use_cookies,
)
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE


def test_signing_up_is_closed_unless_it_is_opened(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V-39 — **ค่าเริ่มต้นคือปิด** เปิดด้วยการตั้งค่าโดยเจตนา (Q-1)"""
    monkeypatch.delenv("TIEWTRADE_SIGNUP_OPEN", raising=False)
    refused = client.post(
        "/auth/register",
        json={"email": unique_email(), "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert refused.status_code == 403

    monkeypatch.setenv("TIEWTRADE_SIGNUP_OPEN", "1")
    allowed = client.post(
        "/auth/register",
        json={"email": unique_email(), "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert allowed.status_code == 201


def test_a_new_account_is_signed_in_and_knows_who_it_is(client: TestClient) -> None:
    """V-18 — ตั้งผู้ใช้ปัจจุบันให้ฐานข้อมูลทุกคำขอที่ผ่านการยืนยัน"""
    register(client)
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"]


def test_the_session_cookie_is_locked_down(client: TestClient) -> None:
    """V-21 — `httpOnly` บนใบ session และ **ไม่** `httpOnly` บนใบกัน CSRF"""
    register(client)
    header = "\n".join(
        value for name, value in client.headers.items() if name.lower() == "set-cookie"
    )
    assert header == ""  # header อยู่ที่ response ไม่ใช่ที่ไคลเอนต์

    response = client.post(
        "/auth/register",
        json={"email": unique_email(), "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    cookies = response.headers.get_list("set-cookie")
    session_header = next(value for value in cookies if value.startswith(f"{SESSION_COOKIE}="))
    csrf_header = next(value for value in cookies if value.startswith(f"{CSRF_COOKIE}="))
    assert "HttpOnly" in session_header
    assert "SameSite=strict" in session_header.lower().replace("samesite=strict", "SameSite=strict")
    assert "HttpOnly" not in csrf_header


def test_an_unsafe_request_without_the_csrf_token_is_refused(client: TestClient) -> None:
    """V-20 — สามกรณี: ไม่ส่ง, ส่งผิด, ส่งถูก"""
    register(client)
    assert client.post("/auth/logout").status_code == 403
    assert client.post("/auth/logout", headers={CSRF_HEADER: "wrong-token"}).status_code == 403
    assert client.post("/auth/logout", headers=csrf_headers(client)).status_code == 200


def test_reading_without_a_session_is_refused(client: TestClient) -> None:
    """V-16 — เส้นทางที่ไม่อยู่ในรายการสาธารณะต้องมี session"""
    assert client.get("/auth/me").status_code == 401


def test_logging_out_makes_the_old_cookie_useless(client: TestClient) -> None:
    """V-11 — เก็บโทเคนไว้ก่อน logout แล้วใช้ซ้ำต้องไม่ได้

    การลบ cookie ที่ฝั่งเบราว์เซอร์อย่างเดียวไม่นับว่าผ่านข้อนี้
    """
    register(client)
    stolen = session_cookie(client)
    assert client.post("/auth/logout", headers=csrf_headers(client)).status_code == 200

    client.cookies.set(SESSION_COOKIE, stolen)
    assert client.get("/auth/me").status_code == 401


def test_logging_out_everywhere_ends_every_device(client: TestClient) -> None:
    """V-12 — ลบได้มากกว่าหนึ่งแถวจริง ผ่านเส้นทาง HTTP"""
    email = register(client)
    first_device = cookies_now(client)
    second_device = sign_in_as_another_device(client, email, GOOD_PASSWORD)

    use_cookies(client, first_device)
    ended = client.post("/auth/logout-all", headers=csrf_headers(client)).json()["ended"]
    assert ended == 2, f"ออกทุกเครื่องลบได้ {ended} แถว ซึ่งน้อยกว่าที่มี"

    use_cookies(client, second_device)
    assert client.get("/auth/me").status_code == 401


def test_the_same_email_in_a_different_case_is_the_same_account(client: TestClient) -> None:
    """V-31 — `A@x.com` กับ `a@x.com` เป็นบัญชีเดียวกัน"""
    email = unique_email()
    register(client, email=email)
    client.post("/auth/logout", headers=csrf_headers(client))

    client.get("/auth/csrf")
    signed_in = client.post(
        "/auth/login",
        json={"email": email.upper(), "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert signed_in.status_code == 200

    taken = client.post(
        "/auth/register",
        json={"email": email.upper(), "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert taken.status_code == 409


def test_failing_to_sign_in_never_says_whether_the_account_exists(client: TestClient) -> None:
    """V-33 — ข้อความและรหัสสถานะของสองกรณีต้องเหมือนกัน"""
    email = register(client)
    client.post("/auth/logout", headers=csrf_headers(client))
    client.get("/auth/csrf")

    wrong_password = client.post(
        "/auth/login",
        json={"email": email, "password": "รหัสผ่านที่ไม่ถูกต้องเลย"},
        headers=csrf_headers(client),
    )
    no_account = client.post(
        "/auth/login",
        json={"email": unique_email(), "password": "รหัสผ่านที่ไม่ถูกต้องเลย"},
        headers=csrf_headers(client),
    )
    assert wrong_password.status_code == no_account.status_code == 401
    assert wrong_password.json() == no_account.json()


@pytest.mark.parametrize(
    ("password", "reason"),
    [("สั้นเกิน", "ความยาว"), ("password123456789", "อยู่ในรายการที่ห้าม")],
)
def test_a_new_password_that_breaks_the_rules_is_refused(
    client: TestClient, password: str, reason: str
) -> None:
    """V-22, V-27 — กฎของรหัสผ่านใหม่บังคับที่เส้นทางสมัครด้วย"""
    response = client.post(
        "/auth/register",
        json={"email": unique_email(), "password": password},
        headers=csrf_headers(client),
    )
    assert response.status_code == 422, reason


def test_changing_the_password_requires_the_current_one(client: TestClient) -> None:
    """V-35 — กรอกค่าปัจจุบันผิดแล้วต้องไม่เปลี่ยน"""
    register(client)
    refused = client.post(
        "/auth/password",
        json={"current_password": "ไม่ใช่ค่าปัจจุบันเลย", "new_password": "รหัสผ่านใหม่ที่ยาวพอ"},
        headers=csrf_headers(client),
    )
    assert refused.status_code == 401
    assert client.get("/auth/me").status_code == 200


def test_changing_the_password_ends_other_devices_but_not_this_one(client: TestClient) -> None:
    """V-36, V-36.1 — เครื่องอื่นหลุด เครื่องที่ทำอยู่ยังใช้ได้"""
    email = register(client)
    mine = cookies_now(client)
    other_device = sign_in_as_another_device(client, email, GOOD_PASSWORD)

    use_cookies(client, mine)
    changed = client.post(
        "/auth/password",
        json={"current_password": GOOD_PASSWORD, "new_password": "รหัสผ่านใหม่ที่ยาวพอ"},
        headers=csrf_headers(client),
    )
    assert changed.status_code == 200
    assert changed.json()["ended"] == 1
    assert client.get("/auth/me").status_code == 200

    use_cookies(client, other_device)
    assert client.get("/auth/me").status_code == 401


def test_the_old_password_stops_working_after_the_change(client: TestClient) -> None:
    """รหัสผ่านเก่าต้องใช้ไม่ได้ และค่าใหม่ต้องใช้ได้"""
    email = register(client)
    new_password = "รหัสผ่านใหม่ที่ยาวพอใช้"
    client.post(
        "/auth/password",
        json={"current_password": GOOD_PASSWORD, "new_password": new_password},
        headers=csrf_headers(client),
    )
    client.post("/auth/logout", headers=csrf_headers(client))
    client.get("/auth/csrf")

    with_old = client.post(
        "/auth/login",
        json={"email": email, "password": GOOD_PASSWORD},
        headers=csrf_headers(client),
    )
    assert with_old.status_code == 401

    with_new = client.post(
        "/auth/login",
        json={"email": email, "password": new_password},
        headers=csrf_headers(client),
    )
    assert with_new.status_code == 200
