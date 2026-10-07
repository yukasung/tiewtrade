"""ขอบเขตของทุกเส้นทาง — V-16, V-17, V-21.1

**เดินทุกเส้นทางที่แอปประกาศจริง** ไม่ใช่เทสต์ตามรายการที่เขียนไว้ เพราะสิ่งที่ต้องกัน
คือการเพิ่ม endpoint ใหม่โดยไม่คิดเรื่องสิทธิ์
"""

from __future__ import annotations

from typing import Final

from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from tiewtrade.services.api.app import app
from tiewtrade.services.api.routing_policy import PUBLIC_ROUTES, RENEWING_ROUTES

#: เส้นทางที่ FastAPI สร้างให้เอง (เอกสารและ schema) — ไม่ใช่เส้นทางของระบบ
GENERATED: Final[frozenset[str]] = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
)


def route_keys() -> set[tuple[str, str]]:
    """(เมธอด, แม่แบบ) ของทุกเส้นทางที่แอปประกาศ — รวมที่ FastAPI สร้างให้เอง

    ตารางกฎมีกุญแจเป็นคู่ตั้งแต่ F-07 เพราะ path เดียวมีได้หลายเมธอดที่กฎต่างกัน
    (`routing_policy.py`) ด่านที่เทียบแค่ path จึงมองไม่เห็นเมธอดที่ลืมจัดประเภท
    """
    found = {
        (method, route.path)
        for route in _api_routes()
        for method in sorted(route.methods or set())
        if method != "HEAD"
    }
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if isinstance(path, str) and methods:
            found |= {(method, path) for method in sorted(methods) if method != "HEAD"}
    return found


def _api_routes(routes: list[BaseRoute] | None = None) -> list[APIRoute]:
    """ทุกเส้นทางของแอป รวมที่อยู่ใน router ที่ถูกรวมเข้ามา

    FastAPI บางรุ่นเก็บ router ที่รวมเข้ามาเป็นวัตถุชั้นเดียว จึงต้องเดินลงไปด้วย
    มิฉะนั้นด่านนี้จะตรวจไม่เจอเส้นทางที่เพิ่มใหม่เลย
    """
    found: list[APIRoute] = []
    for route in app.routes if routes is None else routes:
        if isinstance(route, APIRoute):
            found.append(route)
        # FastAPI รุ่นนี้ห่อ router ที่รวมเข้ามาเป็นวัตถุชั้นเดียว และเก็บตัวจริงไว้ใน
        # `original_router` — ถ้าไม่เดินลงไป ด่านนี้จะเห็นแค่เส้นทางที่ประกาศบน app
        for attribute in ("routes", "original_router"):
            nested = getattr(route, attribute, None)
            if isinstance(nested, list):
                found.extend(_api_routes(nested))
            elif nested is not None and hasattr(nested, "routes"):
                found.extend(_api_routes(list(nested.routes)))
    return found


def test_every_route_is_classified_as_public_or_protected() -> None:
    """V-16, V-17 — ทุกเส้นทางต้องอยู่ในรายการสาธารณะ หรือถูกคุ้มครองโดยปริยาย

    รายการสาธารณะคือสิ่งที่ต้องเห็นใน diff ตอนรีวิว การเพิ่มเส้นทางเข้ารายการนั้น
    จึงเป็นการตัดสินใจ ไม่ใช่ผลข้างเคียง
    """
    keys = {key for key in route_keys() if key[1] not in GENERATED}
    assert keys, "ไม่พบเส้นทางของระบบเลย ซึ่งแปลว่าด่านนี้อ่านผิดที่"
    assert keys >= PUBLIC_ROUTES, "รายการสาธารณะมีเส้นทางที่ไม่มีอยู่จริง"
    # F-06 เพิ่ม `/auth/totp/login` เป็นเส้นทางที่ห้า **เพราะต้องเป็นสาธารณะ**:
    # ตอนขั้นที่สอง ผู้ใช้ยังไม่มี session มีแต่ challenge — และ challenge ใช้เรียก
    # เส้นทางอื่นไม่ได้เลย ฉะนั้นเส้นทางนี้ไม่ได้เปิดช่องให้ใครทำอะไรโดยไม่มีปัจจัยใด
    assert (
        frozenset(
            {
                ("GET", "/health"),
                ("GET", "/auth/csrf"),
                ("POST", "/auth/register"),
                ("POST", "/auth/login"),
                ("POST", "/auth/totp/login"),
            }
        )
        == PUBLIC_ROUTES
    ), "รายการสาธารณะเปลี่ยน — ต้องเป็นการตัดสินใจที่เห็นในรีวิว ไม่ใช่ผลข้างเคียง"


def test_routes_that_renew_the_session_are_declared_and_few() -> None:
    """V-21.1 — ค่าเริ่มต้นคือไม่ต่ออายุ เส้นทางที่ต่ออายุต้องประกาศตัวเอง

    ถ้าเส้นทางอ่านข้อมูลที่หน้าเว็บเรียกเป็นรอบ ๆ หลุดเข้ารายการนี้ เปิดหน้าจอทิ้งไว้
    จะเท่ากับ session ไม่หมดอายุเลย (Q-2)
    """
    keys = route_keys()
    assert keys >= RENEWING_ROUTES
    # F-06 เพิ่มห้าเส้นทาง และ F-07 เพิ่มสาม — ทั้งหมดเป็น **การกระทำของผู้ใช้**
    # จึงนับเป็นการใช้งาน · **`GET /api-keys` ไม่อยู่ในรายการนี้** เพราะหน้าเว็บเรียก
    # เป็นรอบ ๆ เพื่อดูสถานะการตรวจ ซึ่งถ้านับเป็นการใช้งานจะทำให้เปิดหน้าจอทิ้งไว้
    # แล้ว session ไม่มีวันหมดอายุ (Q-2)
    assert (
        frozenset(
            {
                ("POST", "/auth/logout"),
                ("POST", "/auth/logout-all"),
                ("POST", "/auth/password"),
                ("POST", "/auth/totp/setup"),
                ("POST", "/auth/totp/confirm"),
                ("POST", "/auth/totp/replace"),
                ("POST", "/auth/totp/disable"),
                ("POST", "/auth/totp/recovery-codes"),
                ("POST", "/api-keys"),
                ("DELETE", "/api-keys/{key_id}"),
                ("POST", "/api-keys/{key_id}/retry"),
                ("POST", "/trading-account/use"),
            }
        )
        == RENEWING_ROUTES
    )


def test_no_route_is_both_public_and_renewing() -> None:
    """เส้นทางสาธารณะไม่มี session ให้ต่ออายุ ถ้าอยู่ทั้งสองรายการแปลว่าสับสน"""
    assert frozenset() == PUBLIC_ROUTES & RENEWING_ROUTES
