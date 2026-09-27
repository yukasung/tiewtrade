"""ข้อผิดพลาดต้องไม่พาความลับออกไป — V-40, RQ-14, RQ-15

`security.md` หัวข้อ 4 ห้ามมี secret, รหัสผ่าน หรือโทเคนใน log ทุกกรณี
ข้อผิดพลาดของ driver พา DETAIL และค่าที่ bind มาด้วยเป็นปกติ ชั้นนี้จึงต้องตัดทิ้ง
และต้องมีเทสต์ เพราะการรั่วแบบนี้ไม่มีอะไรเตือนเลยจนกว่าจะมีคนอ่าน log เจอ
"""

from __future__ import annotations

import traceback
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import (
    DatabaseRole,
    DatabaseUnavailableError,
    InfraError,
    NotPermittedError,
    create_engine_for,
    database_url,
    user_session,
)

#: ค่าจำลองที่ต้องไม่โผล่ที่ไหนเลย
FAKE_PASSWORD = "PASSWORD-THAT-MUST-NEVER-APPEAR"
FAKE_SECRET = "CIPHERTEXT-THAT-MUST-NEVER-APPEAR"


async def test_connection_failure_hides_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """ต่อไม่ได้เพราะรหัสผ่านผิด — ข้อความและ traceback ต้องไม่มีรหัสผ่าน

    เอา URL ที่ตั้งไว้จริงมาเปลี่ยน **เฉพาะรหัสผ่าน** ไม่เขียน host กับพอร์ตตายตัว
    ไม่เช่นนั้นในสภาพแวดล้อมที่พอร์ตต่างกัน (CI ใช้ 5432 เครื่องนักพัฒนาใช้ 55432)
    เทสต์จะกลายเป็นการทดสอบว่า "ต่อไม่ติด" ซึ่งไม่ใช่เรื่องที่ตั้งใจทดสอบ
    """
    wrong_password_url = make_url(database_url(DatabaseRole.API)).set(password=FAKE_PASSWORD)
    monkeypatch.setenv(
        DatabaseRole.API.url_variable, wrong_password_url.render_as_string(hide_password=False)
    )
    engine = create_engine_for(DatabaseRole.API)
    try:
        with pytest.raises(InfraError) as caught:
            async with user_session(engine, uuid4()):
                pass
    finally:
        await engine.dispose()

    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert FAKE_PASSWORD not in str(caught.value)
    assert FAKE_PASSWORD not in rendered, "รหัสผ่านหลุดอยู่ใน traceback"
    assert "tiewtrade_api" not in rendered or "://" not in rendered, "URL เต็มหลุดอยู่ใน traceback"


async def test_query_failure_hides_bound_values(api_engine: AsyncEngine, secret_table: str) -> None:
    """คำสั่งถูกปฏิเสธ — ค่าที่ส่งไปต้องไม่ติดมาในข้อความหรือ traceback

    ใช้กรณีเขียนแถวให้ผู้ใช้อื่น ซึ่ง policy ปฏิเสธ และค่าที่ส่งไปมี ciphertext ปนอยู่
    """
    async with user_session(api_engine, uuid4()) as session:
        with pytest.raises(NotPermittedError) as caught:
            await session.execute(
                f"INSERT INTO {secret_table} (id, owner_id, secret_ciphertext)"
                " VALUES (:id, :owner, :ciphertext)",
                {"id": str(uuid4()), "owner": str(uuid4()), "ciphertext": FAKE_SECRET},
            )

    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert FAKE_SECRET not in str(caught.value)
    assert FAKE_SECRET not in rendered, "ค่าที่ bind หลุดอยู่ใน traceback"
    assert caught.value.__cause__ is None, "ยัง chain ข้อผิดพลาดของ driver ต่อไป"


def test_engine_is_configured_to_hide_parameters() -> None:
    """ปิด echo และปิดการ log ค่าที่ bind ไว้ตั้งแต่ตอนสร้าง engine"""
    engine = create_engine_for(DatabaseRole.API)
    assert engine.echo is False
    assert engine.sync_engine.hide_parameters is True


async def test_unreachable_database_becomes_a_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ฐานข้อมูลต่อไม่ติดต้องได้ชนิดที่ผู้เรียกดักได้ ไม่ใช่ข้อผิดพลาดของ socket

    พอร์ตที่ไม่มีใครฟังทำให้ driver โยน `ConnectionRefusedError` ซึ่งไม่ใช่ข้อผิดพลาด
    ของ SQLAlchemy ถ้าไม่แปลง ผู้เรียกที่เตรียมรับ "ฐานข้อมูลล่ม" จะรับไม่ได้เลย
    """
    closed_port_url = make_url(database_url(DatabaseRole.API)).set(port=1)
    monkeypatch.setenv(
        DatabaseRole.API.url_variable, closed_port_url.render_as_string(hide_password=False)
    )
    engine = create_engine_for(DatabaseRole.API)
    try:
        with pytest.raises(DatabaseUnavailableError):
            async with user_session(engine, uuid4()):
                pass
    finally:
        await engine.dispose()


async def test_server_side_logging_of_values_is_switched_off(api_engine: AsyncEngine) -> None:
    """ค่าที่ส่งไปต้องไม่ลง log ของ PostgreSQL เองด้วย (RQ-15)

    `hide_parameters` กันได้แค่ฝั่งแอป ฝั่ง server มี log ของตัวเองที่เขียนคำสั่งและ
    รายการค่าที่ bind ลงไปได้ นโยบายนี้ตั้งไว้ที่ระดับฐานข้อมูลใน bootstrap
    เทสต์จึงตรวจว่าค่าที่ session เห็นจริงเป็นไปตามนโยบาย ไม่ใช่ตรวจว่าไฟล์ตั้งค่ามีข้อความ
    """
    expected = {
        "log_statement": "none",
        "log_min_duration_statement": "-1",
        "log_parameter_max_length": "0",
        "log_parameter_max_length_on_error": "0",
        "log_error_verbosity": "terse",
    }
    async with api_engine.connect() as connection:
        for setting, wanted in expected.items():
            actual: str = (
                await connection.execute(text("SELECT current_setting(:name)"), {"name": setting})
            ).scalar_one()
            assert actual == wanted, f"{setting} เป็น {actual!r} ไม่ใช่ {wanted!r}"
