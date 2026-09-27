"""ตาข่ายชั้นที่สอง — V-24 ถึง V-27

ไฟล์นี้ทดสอบ **ชั้นที่สอง** หลักประกันหลักคือรายการที่อนุญาตซึ่งทดสอบใน
`test_event_shape.py` ชั้นนี้มีไว้จับกรณีที่รายละเอียดของเหตุการณ์ในอนาคต
เปิดช่องไว้โดยไม่ควรเปิด
"""

from __future__ import annotations

import traceback

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.audit import ForbiddenDetailError, ensure_no_forbidden_content

SECRET = "VALUE-THAT-MUST-NEVER-BE-STORED"


@pytest.mark.parametrize(
    "key",
    [
        "secret",
        "api_key",
        "apiKey",
        "password",
        "token",
        "cookie",
        "email",
        "customer_name",
        "phone_number",
        "ip_address",
        "home_address",
        "passport_no",
    ],
)
def test_forbidden_keys_are_rejected(key: str) -> None:
    """V-24 — ชื่อคีย์ที่ห้าม ถูกปฏิเสธ"""
    with pytest.raises(ForbiddenDetailError):
        ensure_no_forbidden_content({key: SECRET})


def test_forbidden_keys_are_rejected_at_any_depth() -> None:
    """V-24 — ลึกแค่ไหนก็ต้องเจอ เพราะของจริงมักซ้อนกันหลายชั้น"""
    nested = {"wallet": {"binance": {"connection": {"api_key": SECRET}}}}
    with pytest.raises(ForbiddenDetailError):
        ensure_no_forbidden_content(nested)

    inside_list = {"attempts": [{"ok": True}, {"secret_value": SECRET}]}
    with pytest.raises(ForbiddenDetailError):
        ensure_no_forbidden_content(inside_list)


@pytest.mark.parametrize(
    "value",
    ["someone@example.com", "ผู้ใช้ someone@example.co.th ติดต่อมา", "a.b+c@d.io"],
)
def test_values_that_look_like_email_are_rejected(value: str) -> None:
    """V-25 — ค่าที่มีรูปแบบเป็นอีเมล ถูกปฏิเสธ แม้คีย์จะไม่ได้ชื่อว่าอีเมล"""
    with pytest.raises(ForbiddenDetailError):
        ensure_no_forbidden_content({"reason": value})


def test_floats_are_rejected() -> None:
    """เงินต้องเป็นข้อความคู่กับหน่วย ไม่ใช่ทศนิยมลอยตัว (`AGENTS.md` กฎข้อ 6)"""
    with pytest.raises(ForbiddenDetailError):
        ensure_no_forbidden_content({"amount": 1.23})


def test_rejection_message_names_the_key_but_never_the_value() -> None:
    """V-26 — ข้อความบอกชื่อคีย์ ไม่บอกค่า และ traceback ก็ต้องไม่มีค่า

    ถ้าข้อความมีค่าที่ห้ามเก็บ การปฏิเสธจะกลายเป็นการย้ายค่านั้นไปอยู่ใน log แทน
    """
    with pytest.raises(ForbiddenDetailError) as caught:
        ensure_no_forbidden_content({"api_key": SECRET})

    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert "api_key" in str(caught.value)
    assert SECRET not in str(caught.value)
    assert SECRET not in rendered
    assert caught.value.code == "AUDIT_DETAIL_FORBIDDEN"


def test_allowed_content_passes() -> None:
    """กรณีที่ถูกต้องต้องผ่าน — ถ้าแดงด้วย แปลว่าตัวกรองจับผิดตัว"""
    ensure_no_forbidden_content({})
    ensure_no_forbidden_content(
        {"order_id": "abc-123", "amount": {"amount": "1.23", "unit": "USDT"}}
    )


async def test_server_log_policy_still_applies(api_engine: AsyncEngine) -> None:
    """V-27 — นโยบาย log ของ PostgreSQL จาก F-03 ยังมีผลกับงานนี้"""
    async with api_engine.connect() as connection:
        for setting, wanted in (
            ("log_statement", "none"),
            ("log_parameter_max_length", "0"),
            ("log_parameter_max_length_on_error", "0"),
            ("log_error_verbosity", "terse"),
        ):
            actual: str = (
                await connection.execute(text("SELECT current_setting(:name)"), {"name": setting})
            ).scalar_one()
            assert actual == wanted, f"{setting} เป็น {actual!r} ไม่ใช่ {wanted!r}"
