"""เวอร์ชัน PostgreSQL ต้องมีแหล่งเดียว — V-41 (plan.md ข้อ 8)

ถ้า CI กับเครื่องนักพัฒนาใช้เวอร์ชันต่างกัน เราจะเจอปัญหาคนละอย่างและอธิบายกันไม่ได้
เรื่องนี้เงียบมาก เพราะทุกอย่างดูเขียวทั้งสองฝั่ง
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[4]
VERSION_FILE = REPO_ROOT / "config" / "postgres.env"
COMPOSE_FILE = REPO_ROOT / "compose.yaml"
CI_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _pinned_version() -> str:
    for line in VERSION_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_VERSION="):
            return line.split("=", 1)[1].strip()
    pytest.fail(f"{VERSION_FILE} ไม่มีบรรทัด POSTGRES_VERSION")


def test_version_file_declares_one_version() -> None:
    """แหล่งเดียวต้องมีอยู่จริงและอ่านออก"""
    version = _pinned_version()
    assert version, "ไฟล์กลางไม่ได้ระบุเวอร์ชัน"
    assert int(version.split(".")[0]) >= 16, "ต้องเป็น PostgreSQL 16 ขึ้นไป (tech-stack.md หัวข้อ 4)"


def test_compose_reads_the_central_file_and_fails_loudly_without_it() -> None:
    """Compose ต้องอ้างตัวแปรกลาง และต้องดังถ้าไม่มีค่า ไม่ใช่ใช้ค่าสำรองเงียบ ๆ"""
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "postgres:${POSTGRES_VERSION:?" in compose, "compose ไม่ได้บังคับให้มีค่าจากไฟล์กลาง"
    assert f"postgres:{_pinned_version()}\n" not in compose, "compose ตรึงเวอร์ชันซ้ำเป็นค่าตายตัว"


def test_ci_takes_the_version_from_the_central_file() -> None:
    """CI ต้องรับเวอร์ชันผ่าน job output ไม่ใช่เขียนเลขไว้เอง"""
    ci = CI_FILE.read_text(encoding="utf-8")
    assert "config/postgres.env" in ci, "CI ไม่ได้อ่านไฟล์กลาง"
    assert "needs.config.outputs.postgres_version" in ci, "CI ไม่ได้ต่อค่าจาก job config"
    assert f"image: postgres:{_pinned_version()}" not in ci, "CI ตรึงเวอร์ชันซ้ำเป็นค่าตายตัว"


@pytest.mark.skipif(shutil.which("docker") is None, reason="เครื่องนี้ไม่มี docker ให้ resolve")
def test_compose_resolves_to_the_pinned_image() -> None:
    """ภาพที่ Compose ใช้จริงต้องตรงกับไฟล์กลาง — ตรวจผลที่ resolve แล้ว ไม่ใช่ข้อความในไฟล์"""
    docker = shutil.which("docker")
    assert docker is not None

    # ลบค่าจากสภาพแวดล้อมก่อน เพื่อพิสูจน์ว่าเวอร์ชันมาจากไฟล์กลาง ไม่ใช่จาก shell
    environment = dict(os.environ)
    environment.pop("POSTGRES_VERSION", None)

    done = subprocess.run(
        [docker, "compose", "--env-file", "config/postgres.env", "config", "--images"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert done.returncode == 0, f"docker compose config ล้มเหลว:\n{done.stdout}{done.stderr}"
    assert f"postgres:{_pinned_version()}" in done.stdout, (
        f"ภาพที่ resolve ได้ไม่ตรงกับไฟล์กลาง:\n{done.stdout}"
    )
