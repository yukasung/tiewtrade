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
from tests.venue_isolation import central_venue_modules, check_no_network, check_vocabulary

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


@pytest.fixture(scope="session")
def broken_contract_report() -> tuple[int, str]:
    """ผลของการรัน import-linter กับชุดที่ผิดกฎ — รันครั้งเดียวต่อการทดสอบหนึ่งรอบ

    ผลเหมือนกันทุกกฎ การรันซ้ำต่อกฎจึงเป็นการเสียเวลาเปล่าที่โตตามจำนวนกฎ
    """
    return _lint_imports("imports_bad")


@pytest.mark.parametrize("contract", _contract_names())
def test_import_linter_gate_rejects(contract: str, broken_contract_report: tuple[int, str]) -> None:
    """ทุกกฎการพึ่งพาในกฎจริงต้องถูกจับ และต้องระบุได้ว่ากฎข้อไหนพัง"""
    code, output = broken_contract_report
    assert code != 0, f"import-linter ควรปฏิเสธชุดที่ผิดกฎ แต่ผ่าน:\n{output}"
    assert f"{contract} BROKEN" in output, f"กฎ {contract!r} ไม่ได้ถูกรายงานว่าพัง ผลที่ได้:\n{output}"


def test_import_linter_gate_accepts_valid_tree() -> None:
    """ชุดที่ถูกต้องต้องผ่านทุกกฎภายใต้ config เดียวกัน"""
    code, output = _lint_imports("imports_good")
    assert code == 0, f"import-linter ควรผ่านชุดที่ถูกต้อง แต่แดง:\n{output}"
    for contract in _contract_names():
        assert f"{contract} KEPT" in output, f"กฎ {contract!r} ไม่ได้ถูกตรวจในชุดที่ถูกต้อง"


# ─────────────────────────────────────────────────────────────
# ด่าน: บันทึกการกระทำ (F-04) — กรณีที่ต้องแดง
#
# สองกรณีนี้คือทางที่ค่าลับและการเขียนที่ไม่มีเจ้าของจะเข้ามาได้ ถ้าไม่แดงตรงนี้
# จะไม่มีอะไรบอกว่าตัวกันยังทำงานอยู่ (V-40)
# ─────────────────────────────────────────────────────────────


def test_audit_gate_rejects_forbidden_detail_keys() -> None:
    """คีย์ที่ห้ามต้องถูกปฏิเสธ และกรณีที่ถูกต้องคู่กันต้องผ่าน"""
    from tiewtrade.infra.audit import ForbiddenDetailError, ensure_no_forbidden_content

    with pytest.raises(ForbiddenDetailError):
        ensure_no_forbidden_content({"wallet": {"api_key": "ค่าลับ"}})

    ensure_no_forbidden_content({"wallet": {"order_id": "abc-123"}})


def test_audit_gate_rejects_writing_without_a_user_session() -> None:
    """ทางเขียนบันทึกต้องรับเฉพาะ session ของผู้ใช้"""
    import asyncio
    from uuid import uuid4

    from tiewtrade.infra.audit import (
        ActorKind,
        AuditAction,
        AuditEvent,
        AuditOutcome,
        SubjectKind,
        UserCreatedDetails,
        record_event,
    )
    from tiewtrade.infra.db import SessionKindError

    owner = uuid4()
    event = AuditEvent(
        owner_user_id=owner,
        action=AuditAction.USER_CREATED,
        actor_kind=ActorKind.USER,
        actor_id=owner,
        subject_kind=SubjectKind.USER,
        subject_id=str(owner),
        outcome=AuditOutcome.SUCCEEDED,
        details=UserCreatedDetails(),
    )

    with pytest.raises(SessionKindError):
        asyncio.run(record_event(object(), event))


# ─────────────────────────────────────────────────────────────
# ด่าน: ชั้นแยก venue (F-33) — กรณีที่ต้องแดงและกรณีที่ต้องผ่าน
#
# สองด่านนี้ import-linter ทำแทนไม่ได้ เพราะการรั่วของคำศัพท์ไม่ใช่การ import
# และขอบเขตของด่านเครือข่ายต้องไม่ครอบ package ของตัวเชื่อมจริง (V-2, V-3, V-4.1)
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fixture", "expected_kind"),
    [
        ("venue_bad_word.py", "venue-word"),
        ("venue_bad_joined_pair.py", "joined-pair"),
        # ชื่อฟังก์ชัน ชื่อตัวแปร และชื่อ module ก็เป็นทางที่คำศัพท์ของตลาดรั่วได้
        ("venue_bad_identifier.py", "venue-word"),
        ("venue_bad_identifier.py", "joined-pair"),
        ("venue_bad_import.py", "venue-word"),
    ],
)
def test_venue_vocabulary_gate_rejects(fixture: str, expected_kind: str) -> None:
    """V-2 — ด่านคำศัพท์จับได้ และจับด้วยเหตุผลที่ตั้งใจทดสอบ"""
    violations = check_vocabulary(FIXTURES / fixture)
    assert violations, f"{fixture} ควรถูกปฏิเสธ แต่ด่านไม่พบอะไรเลย"
    kinds = {violation.kind for violation in violations}
    assert expected_kind in kinds, f"{fixture} ถูกจับด้วยเหตุผล {kinds} ซึ่งไม่ใช่ {expected_kind}"


def test_venue_vocabulary_gate_allows_documentation() -> None:
    """V-3 — docstring และคอมเมนต์ที่อ้างถึงตลาดต้องผ่าน

    ถ้าด่านจับเอกสารด้วย เราจะต้องเลี่ยงคำในเอกสาร ซึ่งทำให้เอกสารแย่ลง
    โดยไม่ได้ปลอดภัยขึ้นเลย
    """
    assert check_vocabulary(FIXTURES / "venue_good_outside.py") == []


def test_venue_network_gate_rejects_network_import() -> None:
    """V-4 — ส่วนกลางของ venues พึ่งไลบรารีเครือข่ายไม่ได้"""
    violations = check_no_network(FIXTURES / "venue_bad_network_import.py")
    assert violations, "ไฟล์ที่ import httpx ควรถูกปฏิเสธ"
    assert {violation.kind for violation in violations} == {"not-allowed-import"}


def test_venue_network_gate_accepts_central_style_file() -> None:
    """V-4 — กรณีที่ถูกต้องคู่กันต้องผ่านภายใต้ชุดตั้งค่าเดียวกัน"""
    assert check_no_network(FIXTURES / "venue_good_central.py") == []


def test_venue_network_gate_scope_excludes_adapter_packages() -> None:
    """V-4.1 — ด่านต้องไม่บล็อกตัวเชื่อมจริงของ F-35

    `architecture.md` หัวข้อ 1 วางตัวเชื่อมไว้ใน package ย่อยของ `venues`
    และตัวเชื่อมต้องต่อเครือข่ายเป็นงานหลัก ขอบเขตของด่านจึงเป็น **โครงสร้าง**:
    ไฟล์ระดับบนสุดเท่านั้น ทดสอบกับต้นไม้จำลองที่มีทั้งสองแบบ เพื่อให้พิสูจน์
    พฤติกรรมจริง ไม่ใช่การสะกดของรายชื่อที่เขียนไว้
    """
    tree = FIXTURES / "venue_tree" / "venues"
    central = central_venue_modules(tree)

    assert [path.name for path in central] == ["central.py"]
    assert not any("adapter_like" in str(path) for path in central)

    # ไฟล์ของตัวเชื่อมจะถูกด่านจับถ้าถูกส่งเข้าไป — ขอบเขตจึงเป็นสิ่งที่กันมันไว้
    assert check_no_network(tree / "adapter_like" / "client.py")


def test_indirect_network_dependency_is_caught_only_by_import_linter(
    broken_contract_report: tuple[int, str],
) -> None:
    """ด่านสองตัวตรวจคนละมิติ — เทสต์นี้คือเหตุผลที่เก็บไว้ทั้งคู่ (เจ้าของตัดสิน 2026-09-28)

    ส่วนกลางที่พึ่งเครือข่าย **ทางอ้อม** ผ่าน package ของตัวเชื่อม:

    - ด่าน AST มองไม่เห็น เพราะบรรทัด import ที่ไฟล์นั้นเป็นของในโปรเจกต์เอง
      ซึ่งอยู่ในรายการที่อนุญาต
    - import-linter เห็น เพราะมันไล่ทั้งเส้นทางการพึ่งพา ไม่ใช่ดูบรรทัด import ทีละไฟล์

    ถ้าวันหนึ่งเทสต์นี้แดงเพราะด่าน AST เริ่มจับได้ด้วย แปลว่าข้อสรุปเรื่อง
    "ตรวจคนละมิติ" เปลี่ยนไปแล้ว และต้องทบทวนว่ายังต้องมีสองด่านหรือไม่
    """
    indirect = FIXTURES / "imports_bad" / "src" / "tiewtrade" / "venues" / "limits.py"
    assert check_no_network(indirect) == [], "ด่าน AST ไม่ควรเห็นการพึ่งพาทางอ้อม"

    code, output = broken_contract_report
    assert code != 0
    assert "ส่วนกลางของ venues ห้ามพึ่งไลบรารีเครือข่าย BROKEN" in output
    assert "adapter_like" in output, f"รายงานไม่ได้ชี้เส้นทางทางอ้อม:\n{output}"


def test_adapter_packages_may_use_the_network(broken_contract_report: tuple[int, str]) -> None:
    """และด่านที่สองต้องไม่บล็อกตัวเชื่อมจริงของ F-35

    ชุดที่ถูกต้องมี package ตัวเชื่อมที่ import ไลบรารีเครือข่ายอยู่ด้วย
    ถ้ากฎครอบกว้างเกินไป ชุดนั้นจะแดง
    """
    code, output = _lint_imports("imports_good")
    assert code == 0, f"ชุดที่ถูกต้องควรผ่านทุกกฎ แต่แดง:\n{output}"

    broken_code, _ = broken_contract_report
    assert broken_code != 0
