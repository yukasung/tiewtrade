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
    paths = {route.path for route in _api_routes()} - GENERATED
    assert paths, "ไม่พบเส้นทางของระบบเลย ซึ่งแปลว่าด่านนี้อ่านผิดที่"
    assert paths >= PUBLIC_ROUTES, "รายการสาธารณะมีเส้นทางที่ไม่มีอยู่จริง"
    # F-06 เพิ่ม `/auth/totp/login` เป็นเส้นทางที่ห้า **เพราะต้องเป็นสาธารณะ**:
    # ตอนขั้นที่สอง ผู้ใช้ยังไม่มี session มีแต่ challenge — และ challenge ใช้เรียก
    # เส้นทางอื่นไม่ได้เลย ฉะนั้นเส้นทางนี้ไม่ได้เปิดช่องให้ใครทำอะไรโดยไม่มีปัจจัยใด
    assert (
        frozenset(
            {
                "/health",
                "/auth/csrf",
                "/auth/register",
                "/auth/login",
                "/auth/totp/login",
            }
        )
        == PUBLIC_ROUTES
    ), "รายการสาธารณะเปลี่ยน — ต้องเป็นการตัดสินใจที่เห็นในรีวิว ไม่ใช่ผลข้างเคียง"


def test_routes_that_renew_the_session_are_declared_and_few() -> None:
    """V-21.1 — ค่าเริ่มต้นคือไม่ต่ออายุ เส้นทางที่ต่ออายุต้องประกาศตัวเอง

    ถ้าเส้นทางอ่านข้อมูลที่หน้าเว็บเรียกเป็นรอบ ๆ หลุดเข้ารายการนี้ เปิดหน้าจอทิ้งไว้
    จะเท่ากับ session ไม่หมดอายุเลย (Q-2)
    """
    paths = {route.path for route in _api_routes()}
    assert paths >= RENEWING_ROUTES
    # F-06 เพิ่มห้าเส้นทางที่เป็น **การกระทำของผู้ใช้** จึงนับเป็นการใช้งาน
    # — ไม่มีเส้นทางอ่านข้อมูลที่หน้าเว็บเรียกเป็นรอบ ๆ อยู่ในรายการนี้ (Q-2)
    assert (
        frozenset(
            {
                "/auth/logout",
                "/auth/logout-all",
                "/auth/password",
                "/auth/totp/setup",
                "/auth/totp/confirm",
                "/auth/totp/replace",
                "/auth/totp/disable",
                "/auth/totp/recovery-codes",
            }
        )
        == RENEWING_ROUTES
    )


def test_no_route_is_both_public_and_renewing() -> None:
    """เส้นทางสาธารณะไม่มี session ให้ต่ออายุ ถ้าอยู่ทั้งสองรายการแปลว่าสับสน"""
    assert frozenset() == PUBLIC_ROUTES & RENEWING_ROUTES
