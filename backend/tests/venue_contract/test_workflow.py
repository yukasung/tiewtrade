"""งาน CI ของเทสต์สัญญา — V-39, V-41

อ่าน workflow ทั้งสองไฟล์ ไม่รัน เพราะสิ่งที่ต้องยืนยันคือ **การตั้งค่า**:
งานนี้ต้องแยกไฟล์ มีตารางรายวัน กดรันเองได้ และไม่อยู่ในเงื่อนไข merge
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).parents[3]
WORKFLOWS: Final = REPO_ROOT / ".github" / "workflows"
CI: Final = WORKFLOWS / "ci.yml"
VENUE_CONTRACT: Final = WORKFLOWS / "venue-contract.yml"


@pytest.fixture(scope="module")
def contract_workflow() -> str:
    return VENUE_CONTRACT.read_text(encoding="utf-8")


def test_the_contract_job_lives_in_its_own_file() -> None:
    """V-39 — แยกไฟล์จาก `ci.yml`

    ถ้าอยู่ไฟล์เดียวกัน วันที่ตลาดล่มจะ merge ไม่ได้ทั้ง repo
    """
    assert VENUE_CONTRACT.exists()
    assert "venue_contract" not in CI.read_text(encoding="utf-8")
    assert "venue-contract" not in CI.read_text(encoding="utf-8")


def test_the_contract_job_runs_daily_and_can_be_started_by_hand(contract_workflow: str) -> None:
    """V-39 — ตารางรายวันและ `workflow_dispatch`"""
    assert "schedule:" in contract_workflow
    assert "cron:" in contract_workflow
    assert "workflow_dispatch:" in contract_workflow


def test_the_contract_job_is_not_triggered_by_pushes_or_pull_requests(
    contract_workflow: str,
) -> None:
    """V-39 — ไม่อยู่ในเงื่อนไข merge จึงต้องไม่ผูกกับ push หรือ pull request"""
    trigger_section = contract_workflow.split("jobs:")[0]
    assert "push:" not in trigger_section
    assert "pull_request" not in trigger_section


def test_the_contract_job_only_runs_the_marked_tests(contract_workflow: str) -> None:
    """เทสต์สัญญาต้องรันด้วยเครื่องหมายของตัวเอง ไม่ใช่รันทั้งชุด"""
    assert "pytest -m venue_contract" in contract_workflow


def test_the_marked_tests_are_out_of_the_normal_run() -> None:
    """เครื่องหมายถูกประกาศไว้และชุดปกติตัดออก — ไม่ใช่พึ่งว่าคนจะจำ"""
    config = tomllib.loads((REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = config["tool"]["pytest"]["ini_options"]
    assert "not venue_contract" in pytest_config["addopts"]
    assert any(marker.startswith("venue_contract:") for marker in pytest_config["markers"])


def test_the_maintainer_sees_a_summary_and_an_attached_file(contract_workflow: str) -> None:
    """V-41 — สองทางที่ไม่ต้องเปิด log: job summary และไฟล์ที่แนบไว้"""
    assert "GITHUB_STEP_SUMMARY" in contract_workflow
    assert "upload-artifact" in contract_workflow
    assert "if: always()" in contract_workflow


def test_the_contract_job_gets_no_secrets_at_all(contract_workflow: str) -> None:
    """Q-5 — ไม่มี credential ในงานนี้ จึงไม่มีอะไรให้หลุด"""
    assert "secrets." not in contract_workflow
    assert "APIKEY" not in contract_workflow.upper()


def test_the_live_test_reserves_quota_with_the_real_limiter() -> None:
    """V-31 — เส้นทางที่สองที่เรียกตลาดจริงก็ไม่ใช้ `NoRateLimit`"""
    source = (Path(__file__).parent / "test_live_contract.py").read_text(encoding="utf-8")
    assert "IpWeightLimiter(clock=" in source
    assert "NoRateLimit(" not in source
