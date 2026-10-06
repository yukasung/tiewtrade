"""การจัดประเภทของทุกเส้นทาง — V-27 ถึง V-31 และ V-10 ที่ระดับแอป

**เดินทุกเส้นทางที่แอปประกาศจริง** ไม่ใช่เทสต์ตามรายการที่เขียนไว้ เพราะสิ่งที่ต้องกัน
คือการเพิ่ม endpoint ใหม่โดยไม่คิดเรื่องสิทธิ์ — และเทสต์ที่อ่านรายการเดียวกับโค้ด
จะเขียวตลอดไม่ว่ารายการนั้นจะครบหรือไม่
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tests.api.test_route_policy import route_keys
from tiewtrade.infra.crypto import KeyConfigurationError, KeyPurpose
from tiewtrade.services.api.app import app
from tiewtrade.services.api.authentication import (
    SECOND_FACTOR_REQUIRED,
    UNCLASSIFIED_ROUTE,
    SecondFactor,
)
from tiewtrade.services.api.routing_policy import (
    ROUTE_RULES,
    RouteRule,
    accepts_recovery_grant,
    needs_reverification,
)
from tiewtrade.services.api.settings import TOTP_HEADER


def test_every_route_of_the_app_is_classified() -> None:
    """V-27 — **ทุกเส้นทางใน `app.routes` ต้องมีแถวในตาราง** ไม่มีรายการยกเว้น

    เส้นทางที่ FastAPI สร้างให้เองก็อยู่ในตารางด้วย เพราะรายการยกเว้นคือที่ที่
    เส้นทางจริงแอบเข้าไปอยู่ได้
    """
    keys = route_keys()

    assert keys, "ไม่พบเส้นทางของระบบเลย ซึ่งแปลว่าด่านนี้อ่านผิดที่"
    missing = keys - set(ROUTE_RULES)
    assert not missing, f"เส้นทางที่ยังไม่ถูกจัดประเภท: {sorted(missing)}"


def all_app_paths() -> set[tuple[str, str]]:
    """ทุก path ที่แอปประกาศ **รวมเส้นทางที่ FastAPI สร้างให้เอง**

    ต้องรวมสองแหล่ง: เส้นทางเอกสารไม่ใช่ `APIRoute` จึงไม่โผล่ใน `_api_routes()`
    ส่วนเส้นทางของ router ที่รวมเข้ามาไม่โผล่ตรง ๆ ใน `app.routes` เพราะ FastAPI
    รุ่นนี้ห่อมันไว้ (ดู `_api_routes()` ของ F-05)
    """
    return route_keys()


def test_the_table_has_no_route_that_does_not_exist() -> None:
    """ตารางที่มีเส้นทางผีอยู่คือตารางที่ไม่มีใครกล้าลบอะไรออก"""
    extra = set(ROUTE_RULES) - all_app_paths()

    assert not extra, f"ตารางมีเส้นทางที่ไม่มีอยู่จริง: {sorted(extra)}"


def test_an_unclassified_path_is_refused_at_runtime(client: TestClient) -> None:
    """V-28 — **ชั้นที่สอง** แยกจาก V-27 · path ที่ไม่มีแถวถูกปฏิเสธตอนรัน

    เทสต์ของ V-27 เห็นเฉพาะเส้นทางที่แอปประกาศ ส่วนคำขอจริงมาที่ path อะไรก็ได้
    """
    refused = client.get("/ไม่มีเส้นทางนี้")

    assert refused.status_code == 403
    assert refused.json()["detail"] == UNCLASSIFIED_ROUTE


def test_a_risk_reducing_route_can_never_require_reverification() -> None:
    """V-29 — **บังคับ RQ-7 (ก) ก่อนที่เส้นทางลดความเสี่ยงจะมีอยู่จริง**

    ตรวจสองทาง: ไม่มีแถวใดในตารางที่ตั้งทั้งสองธง และการตั้งทั้งสองธงพร้อมกัน
    เป็นไปไม่ได้ตั้งแต่ตอนประกาศ
    """
    both = [path for path, rule in ROUTE_RULES.items() if rule.risk_reducing and rule.reverify]
    assert not both, f"คำสั่งลดความเสี่ยงถูกบังคับยืนยันซ้ำ: {sorted(both)}"

    with pytest.raises(ValueError, match="ลดความเสี่ยง"):
        RouteRule(risk_reducing=True, reverify=True)


def test_a_recovery_grant_is_only_accepted_where_a_second_factor_is_required() -> None:
    """สิทธิ์กู้บัญชีแทนรหัส TOTP ได้ ไม่ใช่แทนการตรวจสิทธิ์ทั้งหมด"""
    with pytest.raises(ValueError, match="สิทธิ์กู้บัญชี"):
        RouteRule(accepts_recovery_grant=True)


def test_the_reset_and_restart_exceptions_are_not_risk_reducing() -> None:
    """V-31 — ตรึงไว้ว่า **ข้อยกเว้นที่อนุมัติไว้ ≠ คำสั่งลดความเสี่ยง** (RQ-7 ข)

    รีเซ็ตเพดานขาดทุนและเปิดบอทกลับยังไม่มีเส้นทางในระบบ · เทสต์นี้จึงตรึง *กฎ*
    ไว้แทน: ธงสองตัวนี้แยกกัน และเส้นทางที่ไม่ต้องยืนยันซ้ำไม่ได้กลายเป็น
    คำสั่งลดความเสี่ยงโดยอัตโนมัติ — งานหลังจะหยิบ `risk_reducing` ไปใช้เป็นเกณฑ์
    ตัดสินประเภทออเดอร์ ฉะนั้นมันต้องหมายถึงสิ่งเดียวเสมอ
    """
    not_reverifying = {path for path, rule in ROUTE_RULES.items() if not rule.reverify}
    risk_reducing = {path for path, rule in ROUTE_RULES.items() if rule.risk_reducing}

    assert not_reverifying, "ไม่มีเส้นทางที่ไม่ต้องยืนยันซ้ำเลย ซึ่งแปลว่าเทสต์อ่านผิด"
    assert risk_reducing == set(), "ยังไม่ควรมีเส้นทางลดความเสี่ยงในระบบ"
    assert not_reverifying - risk_reducing == not_reverifying


def test_the_routes_that_require_reverification_are_pinned() -> None:
    """ตรึงรายการเส้นทางที่ต้องยืนยันซ้ำ — การเพิ่มต้องเห็นในรีวิว

    สามเส้นทางแรกเปลี่ยนหรือถอนปัจจัยที่สอง · **F-07 เพิ่ม `/api-keys`** ซึ่งเป็น
    เส้นทางแรกที่เพิ่มความเสี่ยงทางการเงิน (`security.md` หัวข้อ 1)
    · ที่ยังไม่มีคือเปิด Live (F-24) และขยายเพดานขาดทุน
    """
    assert {key for key, rule in ROUTE_RULES.items() if rule.reverify} == {
        ("POST", "/auth/totp/replace"),
        ("POST", "/auth/totp/disable"),
        ("POST", "/auth/totp/recovery-codes"),
        ("POST", "/api-keys"),
    }


def test_only_the_two_recovery_routes_accept_a_grant() -> None:
    """สิทธิ์กู้บัญชีใช้ได้สองเส้นทางเท่านั้น (Q-3.1) — **ไม่ใช่สิทธิ์ทั่วไป**

    การขอชุดรหัสสำรองใหม่ไม่รับสิทธิ์กู้ เพราะรหัสสำรองต้องไม่ต่ออายุตัวเองได้
    """
    assert {key for key, rule in ROUTE_RULES.items() if rule.accepts_recovery_grant} == {
        ("POST", "/auth/totp/replace"),
        ("POST", "/auth/totp/disable"),
    }


def test_reverification_is_enforced_at_the_single_decision_point(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V-61.1 — กลไกยืนยันซ้ำทำงานจริงกับเส้นทางที่ไม่ได้ประกาศไว้ว่าต้องยืนยัน

    ทำเครื่องหมายเส้นทางที่มีอยู่ว่าต้องยืนยันซ้ำชั่วคราว เพื่อทดสอบ *กลไก*
    แยกจากเส้นทางจริงที่ใช้มัน (`POST /api-keys` ของ F-07 มีเทสต์ของตัวเอง)
    """
    register(client)
    monkeypatch.setitem(ROUTE_RULES, ("GET", "/auth/me"), RouteRule(reverify=True))
    assert needs_reverification("GET", "/auth/me") is True

    refused = client.get("/auth/me")

    assert refused.status_code == 403
    assert refused.json()["detail"] == SECOND_FACTOR_REQUIRED


def test_a_wrong_code_does_not_pass_reverification(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """รหัสผิดต้องไม่ผ่าน และข้อความต้องเหมือนกรณีไม่ส่งรหัสมาเลย (RQ-11)"""
    register(client)
    monkeypatch.setitem(ROUTE_RULES, ("GET", "/auth/me"), RouteRule(reverify=True))

    refused = client.get("/auth/me", headers={TOTP_HEADER: "000000"})

    assert refused.status_code == 403
    assert refused.json()["detail"] == SECOND_FACTOR_REQUIRED


def test_the_documentation_routes_still_need_a_session(client: TestClient) -> None:
    """พฤติกรรมของ F-05 ต้องไม่เปลี่ยน — เส้นทางเอกสารไม่ใช่สาธารณะ (V-30)"""
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(path).status_code == 401, path


@pytest.mark.parametrize("purpose", list(KeyPurpose))
def test_the_app_does_not_start_without_a_sealing_key(
    monkeypatch: pytest.MonkeyPatch, purpose: KeyPurpose
) -> None:
    """V-10 ที่ระดับแอป — **กุญแจไม่ครบ = กระบวนการไม่เริ่ม**"""
    monkeypatch.delenv(purpose.environment_variable, raising=False)

    with pytest.raises(KeyConfigurationError), TestClient(app):
        pass  # pragma: no cover - lifespan ต้องดังก่อนถึงบรรทัดนี้


def test_the_second_factor_of_a_request_is_remembered(client: TestClient) -> None:
    """ค่าปริยายของ `second_factor` คือ `None` — ผู้เรียกเดิมไม่ต้องแก้

    และชนิดของมันมีสองค่า เพราะสิทธิ์กู้บัญชีเป็นทางผ่านที่ต่างจากรหัส TOTP
    """
    register(client)
    assert client.get("/auth/me").status_code == 200
    assert {factor.value for factor in SecondFactor} == {"TOTP_CODE", "RECOVERY_GRANT"}
    assert accepts_recovery_grant("GET", "/auth/me") is False


def test_changing_the_table_does_not_need_a_change_in_two_places() -> None:
    """รายการที่ F-05 ใช้ **คำนวณจากตารางเดียว** จึงไม่มีสองที่ให้ไม่ตรงกัน (V-30)"""
    from tiewtrade.services.api.routing_policy import PUBLIC_ROUTES, RENEWING_ROUTES

    assert {key for key, rule in ROUTE_RULES.items() if rule.public} == PUBLIC_ROUTES
    assert {key for key, rule in ROUTE_RULES.items() if rule.renews} == RENEWING_ROUTES


def test_csrf_still_applies_to_public_routes(client: TestClient) -> None:
    """พฤติกรรมของ F-05 ต้องไม่เปลี่ยน — เส้นทางสาธารณะยังตรวจ CSRF"""
    response = client.post("/auth/login", json={"email": "a@b.co", "password": "x" * 20})

    assert response.status_code == 403

    with_token = client.post(
        "/auth/login",
        json={"email": "a@b.co", "password": "x" * 20},
        headers=csrf_headers(client),
    )
    assert with_token.status_code == 401
