"""`GET /health` ต้องตอบได้ (F-01 RQ-1, RQ-17)

**เปิด lifespan ทุกครั้ง** ตั้งแต่ F-05 แอปสร้าง engine ของฐานข้อมูลตอนเปิด และ
middleware ตัวตนใช้ engine นั้นทุกคำขอ — ไคลเอนต์ที่ไม่เปิด lifespan จึงใช้ไม่ได้
ซึ่งเป็นผลที่ต้องการ: แอปที่ไม่มีทางต่อฐานข้อมูลไม่ควรตอบคำขอได้เลย
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tiewtrade.services.api.app import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as started:
        yield started


def test_health_returns_ok(client: TestClient) -> None:
    """เส้นทางนี้เปิดสาธารณะ จึงเรียกได้โดยไม่ต้องเข้าสู่ระบบ"""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == app.version
    assert body["server_time"]


def test_openapi_schema_describes_every_route_the_frontend_uses() -> None:
    """สัญญา API ต้องมีจริง เพราะหน้าบ้านสร้างชนิดข้อมูลจากไฟล์นี้ (F-01 RQ-13)

    อ่านจาก `app.openapi()` ไม่ใช่จาก `GET /openapi.json` เพราะตั้งแต่ F-05
    เส้นทางที่ไม่อยู่ในรายการสาธารณะต้องมี session — รวมหน้าเอกสารและไฟล์สัญญา
    ซึ่งเป็นผลที่ต้องการ: พื้นที่ API ของระบบเทรดไม่ควรอ่านได้โดยไม่เข้าสู่ระบบ
    ส่วนการสร้างชนิดข้อมูลของหน้าบ้านใช้ไฟล์ที่ export ไว้อยู่แล้ว
    """
    schema = app.openapi()
    for path in ("/health", "/auth/register", "/auth/login", "/auth/logout", "/auth/me"):
        assert path in schema["paths"], f"{path} ไม่อยู่ในสัญญา API"


def test_the_documentation_routes_are_not_public(client: TestClient) -> None:
    """เส้นทางเอกสารที่ FastAPI สร้างให้ต้องอยู่ใต้การยืนยันตัวตนเหมือนเส้นทางอื่น"""
    for path in ("/openapi.json", "/docs"):
        assert client.get(path).status_code == 401, f"{path} เปิดสาธารณะอยู่"
