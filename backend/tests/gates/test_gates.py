"""พิสูจน์ว่าด่านตรวจจับความผิดได้จริง (RQ-12)

เกณฑ์ผ่านของเทสต์กลุ่มนี้เข้มกว่าปกติ ตาม plan.md และ validation.md
แค่ "เครื่องมือไม่สำเร็จ" ไม่นับว่าผ่าน ทุกกรณีต้องครบสามข้อ:

1. แดงเพราะกฎที่ตั้งใจทดสอบ ไม่ใช่เพราะ config ผิดหรือหา package ไม่เจอ
2. กรณีที่ถูกต้องคู่กันต้องผ่านภายใต้ชุดตั้งค่าเดียวกัน
3. รันด้วยชุดตั้งค่าเดียวกับด่านจริง

เหตุผล: เทสต์ที่คาดหวังแค่ "ไม่สำเร็จ" จะขึ้นเขียวเมื่อเครื่องมือพัง
ซึ่งเป็นกรณีที่ต้องดังที่สุด แต่กลับกลายเป็นเงียบที่สุด
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.purity import check_file

FIXTURES = Path(__file__).parent / "fixtures"
BACKEND_ROOT = Path(__file__).parents[2]


def _run(args: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> tuple[int, str]:
    """รันเครื่องมือแล้วคืน (exit code, ผลรวม stdout กับ stderr)"""
    import os

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    done = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


# ─────────────────────────────────────────────────────────────
# ด่าน: ตัวตรวจความบริสุทธิ์ของ core
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fixture", "expected_kind"),
    [
        ("purity_bad_float.py", "float"),
        ("purity_bad_clock.py", "forbidden-call"),
        ("purity_bad_random.py", "forbidden-import"),
        ("purity_bad_file.py", "forbidden-call"),
        ("purity_bad_network.py", "forbidden-import"),
        ("purity_bad_clock_alias.py", "forbidden-call"),
        ("purity_bad_clock_direct_import.py", "forbidden-call"),
        ("purity_bad_external_import.py", "external-import"),
        # F-03 — ไลบรารีฐานข้อมูลต้องเข้า core ไม่ได้ (RQ-11)
        ("purity_bad_database_import.py", "external-import"),
    ],
)
def test_purity_gate_rejects(fixture: str, expected_kind: str) -> None:
    """ตัวตรวจต้องจับได้ และต้องจับด้วยเหตุผลที่ตั้งใจทดสอบ"""
    violations = check_file(FIXTURES / fixture)
    assert violations, f"{fixture} ควรถูกปฏิเสธ แต่ตัวตรวจไม่พบอะไรเลย"
    kinds = {v.kind for v in violations}
    assert expected_kind in kinds, (
        f"{fixture} ถูกจับด้วยเหตุผล {kinds} ซึ่งไม่ใช่ {expected_kind} ที่ตั้งใจทดสอบ"
    )


def test_purity_gate_accepts_valid_code() -> None:
    """กรณีที่ถูกต้องต้องผ่าน — ถ้าแดงด้วย แปลว่าตัวตรวจจับผิดตัว ไม่ใช่จับถูก"""
    assert check_file(FIXTURES / "purity_good.py") == []


# ─────────────────────────────────────────────────────────────
# ด่าน: mypy
# ─────────────────────────────────────────────────────────────


def test_mypy_gate_rejects_untyped_function() -> None:
    code, output = _run(
        [sys.executable, "-m", "mypy", str(FIXTURES / "mypy_bad_untyped.py")],
        cwd=BACKEND_ROOT,
    )
    assert code != 0, f"mypy ควรปฏิเสธฟังก์ชันที่ไม่ระบุชนิด แต่ผ่าน:\n{output}"
    assert "no-untyped-def" in output, f"mypy แดงแต่ไม่ใช่เพราะกฎที่ตั้งใจทดสอบ ผลที่ได้:\n{output}"


def test_mypy_gate_accepts_typed_function() -> None:
    code, output = _run(
        [sys.executable, "-m", "mypy", str(FIXTURES / "mypy_good_typed.py")],
        cwd=BACKEND_ROOT,
    )
    assert code == 0, f"mypy ควรผ่านโค้ดที่ระบุชนิดครบ แต่แดง:\n{output}"


# ─────────────────────────────────────────────────────────────
# ด่าน: ruff check
# ─────────────────────────────────────────────────────────────


def test_ruff_check_gate_rejects_unused_import() -> None:
    code, output = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            str(FIXTURES / "ruff_bad_unused_import.py"),
        ],
        cwd=BACKEND_ROOT,
    )
    assert code != 0, f"ruff ควรปฏิเสธ import ที่ไม่ได้ใช้ แต่ผ่าน:\n{output}"
    assert "F401" in output, f"ruff แดงแต่ไม่ใช่เพราะ F401 ที่ตั้งใจทดสอบ:\n{output}"


def test_ruff_check_gate_accepts_clean_file() -> None:
    code, output = _run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", str(FIXTURES / "ruff_good.py")],
        cwd=BACKEND_ROOT,
    )
    assert code == 0, f"ruff ควรผ่านไฟล์ที่สะอาด แต่แดง:\n{output}"


# ─────────────────────────────────────────────────────────────
# ด่าน: ruff format
# ─────────────────────────────────────────────────────────────


def test_ruff_format_gate_rejects_badly_formatted_file() -> None:
    code, output = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "--no-cache",
            str(FIXTURES / "format_bad.py"),
        ],
        cwd=BACKEND_ROOT,
    )
    assert code != 0, f"ruff format ควรปฏิเสธไฟล์ที่จัดรูปแบบผิด แต่ผ่าน:\n{output}"
    assert "format_bad.py" in output, f"ruff format แดงแต่ไม่ได้ชี้ที่ไฟล์ที่ทดสอบ:\n{output}"


def test_ruff_format_gate_accepts_formatted_file() -> None:
    code, output = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "--no-cache",
            str(FIXTURES / "format_good.py"),
        ],
        cwd=BACKEND_ROOT,
    )
    assert code == 0, f"ruff format ควรผ่านไฟล์ที่จัดรูปแบบถูก แต่แดง:\n{output}"


# ─────────────────────────────────────────────────────────────
# ด่าน: import-linter
# ─────────────────────────────────────────────────────────────

#: เรียกผ่าน console script ของ venv เดียวกับด่านจริง ไม่ใช่ python -m
LINT_IMPORTS = BACKEND_ROOT / ".venv" / "bin" / "lint-imports"

#: **ใช้ config จริงจาก pyproject.toml ไม่ใช่สำเนา** (รีวิว 2026-09-27 ข้อ S-2, R-1)
#: ถ้าเทสต์มี config ของตัวเอง กฎจริงถูกลบหรืออ่อนลงได้โดยเทสต์ยังเขียว
REAL_CONFIG = BACKEND_ROOT / "pyproject.toml"


def _contract_names() -> list[str]:
    """อ่านชื่อกฎจาก config จริง เพื่อไม่ให้ชื่อในเทสต์หลุดจากชื่อจริง"""
    import tomllib

    with REAL_CONFIG.open("rb") as handle:
        data = tomllib.load(handle)
    contracts = data["tool"]["importlinter"]["contracts"]
    names = [str(contract["name"]) for contract in contracts]
    assert names, "ไม่พบกฎ import-linter ใน pyproject.toml"
    return names


def _lint_imports(variant: str) -> tuple[int, str]:
    """รัน import-linter ด้วยกฎจริง แต่ชี้ source ไปที่ fixture"""
    root = FIXTURES / variant
    assert LINT_IMPORTS.exists(), f"ไม่พบ lint-imports ที่ {LINT_IMPORTS} — venv ยังไม่ได้ติดตั้ง"
    return _run(
        [str(LINT_IMPORTS), "--config", str(REAL_CONFIG)],
        cwd=root,
        env_extra={"PYTHONPATH": "src"},
    )


@pytest.mark.parametrize("contract", _contract_names())
def test_import_linter_gate_rejects(contract: str) -> None:
    """ทุกกฎการพึ่งพาในกฎจริงต้องถูกจับ และต้องระบุได้ว่ากฎข้อไหนพัง"""
    code, output = _lint_imports("imports_bad")
    assert code != 0, f"import-linter ควรปฏิเสธชุดที่ผิดกฎ แต่ผ่าน:\n{output}"
    assert f"{contract} BROKEN" in output, f"กฎ {contract!r} ไม่ได้ถูกรายงานว่าพัง ผลที่ได้:\n{output}"


def test_import_linter_gate_accepts_valid_tree() -> None:
    """ชุดที่ถูกต้องต้องผ่านทุกกฎภายใต้ config เดียวกัน"""
    code, output = _lint_imports("imports_good")
    assert code == 0, f"import-linter ควรผ่านชุดที่ถูกต้อง แต่แดง:\n{output}"
    for contract in _contract_names():
        assert f"{contract} KEPT" in output, f"กฎ {contract!r} ไม่ได้ถูกตรวจในชุดที่ถูกต้อง"
