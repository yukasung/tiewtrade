"""ด่านเส้นทางที่ย้ายเงิน — V-32, V-32.1, V-32.2 (F-07 RQ-16)

**ไม่พอที่จะเขียวบนโค้ดที่ถูกอยู่แล้ว** ด่านต้องพิสูจน์ว่าจับของผิดได้จริง
ตามแบบแผนของ F-01 และ F-33
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.money_movement import FORBIDDEN_PATH_FRAGMENTS, check_no_money_paths, check_tree
from tiewtrade.venues.binance_th.endpoints import Endpoint

BACKEND_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = BACKEND_ROOT / "src"
FIXTURES = Path(__file__).parent / "gates" / "fixtures" / "money_paths"


def test_the_whole_source_tree_is_clean() -> None:
    """V-32 — ไม่มีเส้นทางที่ย้ายเงินอยู่ในโค้ดของระบบเลย"""
    violations = check_tree(SOURCE_ROOT)
    assert violations == [], "\n".join(str(violation) for violation in violations)


@pytest.mark.parametrize("name", ["bad_literal", "bad_built"])
def test_the_gate_catches_a_file_that_names_a_money_path(name: str) -> None:
    """V-32.2 — ด่านจับไฟล์ที่ผิดได้จริง ทั้งแบบเขียนตรงและแบบประกอบจากชิ้นส่วน"""
    violations = check_no_money_paths(FIXTURES / f"{name}.py")

    assert violations, f"ด่านไม่จับ {name}"
    assert all(violation.rule == "money-moving-path" for violation in violations)


def test_the_gate_leaves_a_correct_file_alone() -> None:
    """ด่านต้องไม่ดังกับเส้นทางที่อ่านอย่างเดียว และไม่ดังกับคำในคำอธิบาย"""
    assert check_no_money_paths(FIXTURES / "good.py") == []


def test_every_declared_endpoint_is_a_read() -> None:
    """V-32 — ทุกสมาชิกของรายการปิดต้องไม่ใช่เส้นทางที่ย้ายเงิน

    รายการปิดคือชั้นที่บังคับจริง ฉะนั้นมันเองต้องถูกตรวจด้วย — มิฉะนั้นการเพิ่ม
    สมาชิกที่ถอนเงินจะทำให้ทุกอย่างถูกต้องตามกฎทันที
    """
    for endpoint in Endpoint:
        lowered = endpoint.path.lower()
        for fragment in FORBIDDEN_PATH_FRAGMENTS:
            assert fragment not in lowered, f"{endpoint.name} เป็นเส้นทางที่ย้ายเงิน"


def test_only_the_transport_reaches_the_network() -> None:
    """V-32.1 — ไม่มีทางลัดรอบตัวส่งคำขอ

    ถ้าโมดูลอื่นต่อเครือข่ายเองได้ รายการปิดของ `Endpoint` ก็ไม่ได้ครอบคำขอทุกใบ
    และด่านนี้ทั้งด่านจะกลายเป็นของประดับ · กฎนี้มีอยู่แล้วใน import-linter
    (contract "การแปลข้อมูลของตัวเชื่อม…") เทสต์นี้ยืนยันว่ามันยังครอบโมดูลใหม่ด้วย
    """
    from tests.venue_isolation import modules_not_reaching

    adapter = SOURCE_ROOT / "tiewtrade" / "venues" / "binance_th"
    reaching = {path.name for path in adapter.glob("*.py")} - {
        path.name for path in modules_not_reaching(adapter, "transport")
    }
    assert reaching == {"__init__.py", "transport.py", "prices.py", "constraints.py", "wallets.py"}
