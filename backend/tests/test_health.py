"""`GET /health` ต้องตอบได้ (RQ-1, RQ-17)"""

from fastapi.testclient import TestClient

from services.api.app import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["server_time"]


def test_openapi_schema_describes_health() -> None:
    """สัญญา API ต้องมีจริง เพราะหน้าบ้านสร้างชนิดข้อมูลจากไฟล์นี้ (RQ-13)"""
    schema = client.get("/openapi.json").json()
    assert "/health" in schema["paths"]
