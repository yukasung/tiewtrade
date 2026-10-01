"""สคริปต์เก็บข้อมูลและไฟล์ที่บันทึกไว้ — V-31, V-36 ถึง V-38

อ่านสคริปต์ด้วย AST **ไม่รันสคริปต์** เพราะการรันคือการเรียกตลาดจริง
ซึ่งเทสต์ปกติต้องไม่ทำ (V-7)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Final

import pytest

from tests.venue_isolation import code_strings, identifiers

BACKEND_ROOT: Final = Path(__file__).parents[3]
SCRIPT: Final = BACKEND_ROOT / "scripts" / "record_binance_th.py"
RECORDED_DIR: Final = Path(__file__).parent / "recorded"

#: endpoint สาธารณะที่เจ้าของอนุมัติให้เรียกจากเครื่องนี้ (Q-5)
ALLOWED_ENDPOINTS: Final = frozenset({"/time", "/exchangeInfo", "/trades"})

#: คำที่บ่งชี้ว่ามีความลับหรือข้อมูลของใครติดมา
SECRET_HINTS: Final = (
    "apikey",
    "api_key",
    "secret",
    "signature",
    "authorization",
    "cookie",
    "token",
    "balance",
    "accountid",
    "email",
)


def _script_tree() -> ast.Module:
    return ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))


def test_every_recorded_case_exists_both_for_success_and_for_rejection() -> None:
    """V-36 — มีทั้งกรณีสำเร็จและกรณีที่ตลาดปฏิเสธ"""
    files = {path.stem for path in RECORDED_DIR.glob("*.json")}
    assert {"server_time", "exchange_info", "trades_btc_thb"} <= files
    assert {"rejected_unknown_symbol", "rejected_bad_limit"} <= files

    statuses = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))["status"]
        for path in RECORDED_DIR.glob("*.json")
    }
    assert 200 in statuses.values()
    assert 400 in statuses.values()


@pytest.mark.parametrize("path", sorted(RECORDED_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_no_recorded_file_carries_a_secret_or_anybodys_data(path: Path) -> None:
    """V-37 — ไฟล์ที่บันทึกไม่มี credential และไม่มีข้อมูลของใคร"""
    text = path.read_text(encoding="utf-8").lower()
    for hint in SECRET_HINTS:
        assert hint not in text, f"{path.name} มีคำว่า {hint!r}"


@pytest.mark.parametrize("path", sorted(RECORDED_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_every_recorded_file_came_from_an_allowed_public_endpoint(path: Path) -> None:
    """V-38 — บันทึกได้เฉพาะ endpoint ที่อนุมัติ"""
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["endpoint"] in ALLOWED_ENDPOINTS


def test_the_script_only_names_endpoints_that_were_approved() -> None:
    """V-38 — สคริปต์ไม่มี endpoint อื่นเขียนอยู่เลย แม้ยังไม่ถูกเรียก"""
    for text in code_strings(SCRIPT):
        if text.startswith("/"):
            assert text in ALLOWED_ENDPOINTS, f"สคริปต์อ้าง endpoint ที่ไม่ได้อนุมัติ {text!r}"


def test_the_script_never_sends_anything_but_a_read() -> None:
    """V-38 — ไม่มีเมธอดที่ไม่ใช่ GET และไม่มีการส่งคำสั่งซื้อขาย"""
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (".post(", ".put(", ".delete(", ".patch(", "/order"):
        assert forbidden not in source, f"สคริปต์มี {forbidden!r}"

    called = {
        node.func.attr
        for node in ast.walk(_script_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "post" not in called
    assert "get" in called


def test_the_script_carries_no_credentials_at_all() -> None:
    """Q-5 — ไม่มี credential ในสคริปต์ และไม่อ่านค่าลับจากสิ่งแวดล้อม"""
    source = SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in ("apikey", "api_key", "secret", "hmac", "hashlib", "environ", "getenv"):
        assert forbidden not in source, f"สคริปต์มี {forbidden!r}"


def test_the_script_reserves_quota_with_the_real_limiter() -> None:
    """V-31 — เส้นทางที่เรียกตลาดจริงต้องไม่ใช้ `NoRateLimit`

    ดูชื่อที่โค้ดใช้จริง ไม่ใช่ทั้งไฟล์ เพราะ docstring ของสคริปต์อธิบายไว้โดยเจตนา
    ว่าทำไมไม่ใช้ตัวนั้น
    """
    names = identifiers(SCRIPT)
    assert "IpWeightLimiter" in names
    assert "NoRateLimit" not in names
    assert "reserve" in names


def test_the_recorded_headers_keep_the_weight_the_market_reported() -> None:
    """Q-5 — บันทึก header ของ weight ไว้เทียบกับที่เราประกาศ"""
    entry = json.loads((RECORDED_DIR / "exchange_info.json").read_text(encoding="utf-8"))
    headers = entry["headers"]
    assert any(name.startswith("x-mbx-used-weight") for name in headers)
    assert all(value.isdigit() for value in headers.values())
