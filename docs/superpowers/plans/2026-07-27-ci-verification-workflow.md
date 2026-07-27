# DEV-121 CI Verification Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่ม GitHub Actions workflow ที่รัน Python verification checklist อัตโนมัติสำหรับ Pull Request ที่ target `main` และการ push เข้า `main`

**Architecture:** ใช้ workflow เดียวที่มี job `verify` บน `ubuntu-latest` และติดตั้ง `.[dev]` หนึ่งครั้งก่อนรัน checks ตามลำดับ Contract test อ่าน workflow และ repository instructions เป็น text เพื่อป้องกัน requirement สำคัญโดยไม่เพิ่ม YAML dependency ส่วน GitHub Actions run หลัง push เป็น final integration verification

**Tech Stack:** GitHub Actions, Python 3.12, Pytest, Ruff, Mypy, Git

## Global Constraints

- Implementation เปลี่ยนเฉพาะ `.github/workflows/verify.yml`, `tests/unit/test_ci_workflow.py` และ `AGENTS.md`; branch มี design และ plan documents ของ DEV-121 เพิ่มเติมตาม development workflow
- ห้ามเปลี่ยน production modules ใต้ `src/`, trading behavior, database schema หรือ `docs-site`
- Workflow ทำงานเฉพาะ Pull Request ที่ target `main` สำหรับ event `opened`, `synchronize`, `reopened`, `edited` และ push เข้า `main`
- ใช้ `ubuntu-latest`, timeout `10` นาที และ `permissions: contents: read`
- ใช้ `actions/checkout@v6` พร้อม `fetch-depth: 0`
- หลัง checkout ติดตั้ง Qt EGL runtime ด้วย `sudo apt-get update` และ `sudo apt-get install --yes libegl1` ก่อน Python setup/dependency use โดยไม่เพิ่ม X11 packages อื่น
- ใช้ `actions/setup-python@v6`, Python `3.12` และ pip cache จาก `pyproject.toml`
- ติดตั้งด้วย `python -m pip install -e ".[dev]"`
- กำหนด `PYTHONPATH=src` และ `QT_QPA_PLATFORM=offscreen` ระดับ job
- รัน Pytest, Ruff lint, Ruff format check, Mypy และ committed-range whitespace check โดยไม่มี `continue-on-error`
- ห้ามใช้ GitHub secrets และห้ามเชื่อม Binance
- DEV-121 ต้องคงสถานะ `In Progress` จนกว่า workflow ถูก push โดยได้รับอนุญาตและ GitHub Actions run ผ่านจริง

---

## File Structure

- Create `.github/workflows/verify.yml`: กำหนด event triggers, least-privilege job environment, dependency setup และ verification commands
- Create `tests/unit/test_ci_workflow.py`: contract tests สำหรับ workflow structure, exact verification commands และการจัดแนว repository instructions
- Modify `AGENTS.md:66-73`: แยก local working-tree whitespace check ออกจาก CI committed-range whitespace check

---

### Task 1: Add the CI workflow contract and workflow

**Files:**
- Create: `tests/unit/test_ci_workflow.py`
- Create: `.github/workflows/verify.yml`

**Interfaces:**
- Consumes: development dependencies จาก `pyproject.toml`; GitHub event fields `github.event.pull_request.base.sha` และ `github.event.before`
- Produces: GitHub Actions job `verify`; helper functions `_workflow_text() -> str` และ `_repository_instructions_text() -> str` สำหรับ contract tests

- [ ] **Step 1: Write the failing workflow contract tests**

สร้าง `tests/unit/test_ci_workflow.py`:

```python
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "verify.yml"
INSTRUCTIONS_PATH = REPOSITORY_ROOT / "AGENTS.md"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _repository_instructions_text() -> str:
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def test_verify_workflow_targets_main_without_duplicate_branch_pushes() -> None:
    workflow = _workflow_text()

    assert (
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "    types: [opened, synchronize, reopened, edited]"
    ) in workflow


def test_verify_workflow_uses_bounded_least_privilege_environment() -> None:
    workflow = _workflow_text()

    assert (
        "permissions:\n"
        "  contents: read\n\n"
        "jobs:\n"
        "  verify:\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 10\n"
        "    env:\n"
        "      PYTHONPATH: src\n"
        "      QT_QPA_PLATFORM: offscreen"
    ) in workflow

    assert (
        "      - name: Check out repository\n"
        "        uses: actions/checkout@v6\n"
        "        with:\n"
        "          fetch-depth: 0"
    ) in workflow

    assert (
        "      - name: Set up Python\n"
        "        uses: actions/setup-python@v6\n"
        "        with:\n"
        '          python-version: "3.12"\n'
        "          cache: pip\n"
        "          cache-dependency-path: pyproject.toml\n\n"
        "      - name: Install application and development tools\n"
        '        run: python -m pip install -e ".[dev]"'
    ) in workflow


def test_verify_workflow_installs_the_qt_egl_runtime() -> None:
    workflow = _workflow_text()

    assert (
        "      - name: Install Qt runtime libraries\n"
        "        run: |\n"
        "          sudo apt-get update\n"
        "          sudo apt-get install --yes libegl1"
    ) in workflow


def test_verify_workflow_runs_the_repository_checklist() -> None:
    workflow = _workflow_text()

    assert (
        "      - name: Run tests\n"
        "        run: python -m pytest -q\n\n"
        "      - name: Run Ruff lint\n"
        "        run: python -m ruff check .\n\n"
        "      - name: Check Ruff formatting\n"
        "        run: python -m ruff format --check .\n\n"
        "      - name: Run Mypy\n"
        "        run: python -m mypy src\n\n"
        "      - name: Check committed whitespace\n"
        "        env:\n"
        "          BASE_SHA: ${{ github.event_name == 'pull_request' && "
        "github.event.pull_request.base.sha || github.event.before }}\n"
        "        run: git diff --check \"$BASE_SHA\" HEAD"
    ) in workflow
    assert "continue-on-error" not in workflow
```

- [ ] **Step 2: Run the focused tests and verify the RED state**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest tests/unit/test_ci_workflow.py -q
```

Expected สำหรับ regression นี้: `1 failed, 3 passed` เพราะ trigger block ยังไม่มี `edited`

- [ ] **Step 3: Add the minimal GitHub Actions workflow**

สร้าง `.github/workflows/verify.yml`:

```yaml
name: Verify

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      PYTHONPATH: src
      QT_QPA_PLATFORM: offscreen

    steps:
      - name: Check out repository
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Install Qt runtime libraries
        run: |
          sudo apt-get update
          sudo apt-get install --yes libegl1

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: pyproject.toml

      - name: Install application and development tools
        run: python -m pip install -e ".[dev]"

      - name: Run tests
        run: python -m pytest -q

      - name: Run Ruff lint
        run: python -m ruff check .

      - name: Check Ruff formatting
        run: python -m ruff format --check .

      - name: Run Mypy
        run: python -m mypy src

      - name: Check committed whitespace
        env:
          BASE_SHA: ${{ github.event_name == 'pull_request' && github.event.pull_request.base.sha || github.event.before }}
        run: git diff --check "$BASE_SHA" HEAD
```

- [ ] **Step 4: Run the focused tests and verify the GREEN state**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest tests/unit/test_ci_workflow.py -q
```

Expected: `4 passed`

- [ ] **Step 5: Run focused static checks**

Run:

```bash
../../.venv/bin/python -m ruff check tests/unit/test_ci_workflow.py
../../.venv/bin/python -m ruff format --check tests/unit/test_ci_workflow.py
```

Expected: ทั้งสองคำสั่ง exit `0`

- [ ] **Step 6: Commit the workflow slice**

```bash
git add .github/workflows/verify.yml tests/unit/test_ci_workflow.py
git commit -m "ci: add Python verification workflow"
```

Expected: commit มีเฉพาะ workflow และ workflow contract test

---

### Task 2: Align repository verification instructions

**Files:**
- Modify: `tests/unit/test_ci_workflow.py`
- Modify: `AGENTS.md:66-73`

**Interfaces:**
- Consumes: `_repository_instructions_text() -> str` จาก Task 1
- Produces: repository instruction contract ที่แยก `git diff --check` สำหรับ local changes และ `git diff --check <base> HEAD` สำหรับ CI committed range

- [ ] **Step 1: Write the failing documentation-alignment test**

เพิ่มท้าย `tests/unit/test_ci_workflow.py`:

```python
def test_repository_instructions_distinguish_local_and_ci_whitespace() -> None:
    instructions = _repository_instructions_text()

    assert "`git diff --check` สำหรับ working-tree changes" in instructions
    assert "`git diff --check <base> HEAD` สำหรับ committed range" in instructions
```

- [ ] **Step 2: Run the new test and verify the RED state**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest \
  tests/unit/test_ci_workflow.py::test_repository_instructions_distinguish_local_and_ci_whitespace \
  -q
```

Expected: `1 failed` เพราะ `AGENTS.md` ยังมีเพียงข้อความ `ตรวจ git diff --check`

- [ ] **Step 3: Clarify local and CI whitespace checks**

แทน bullet `- ตรวจ git diff --check` ในหัวข้อ Verification ของ `AGENTS.md` ด้วย:

```markdown
- ตรวจ `git diff --check` สำหรับ working-tree changes ระหว่างการตรวจบนเครื่องนักพัฒนา
- ใน GitHub Actions ตรวจ `git diff --check <base> HEAD` สำหรับ committed range
```

- [ ] **Step 4: Run all workflow contract tests and verify the GREEN state**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest tests/unit/test_ci_workflow.py -q
```

Expected: `4 passed`

- [ ] **Step 5: Commit the instruction alignment slice**

```bash
git add AGENTS.md tests/unit/test_ci_workflow.py
git commit -m "docs: align local and CI verification checks"
```

Expected: commit มีเฉพาะ `AGENTS.md` และ contract test ที่รองรับ requirement นี้

---

### Task 3: Run the complete local verification gate

**Files:**
- Verify only: `.github/workflows/verify.yml`
- Verify only: `tests/unit/test_ci_workflow.py`
- Verify only: `AGENTS.md`

**Interfaces:**
- Consumes: workflow และ contract tests จาก Tasks 1-2
- Produces: หลักฐานว่า branch ผ่าน local verification โดยไม่มี production code changes

- [ ] **Step 1: Run the complete Python test suite in headless mode**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest -q
```

Expected: tests ทั้งหมดผ่าน โดยมีอย่างน้อย baseline `466` tests บวก contract tests ใหม่ `4` tests

- [ ] **Step 2: Run repository lint**

Run:

```bash
../../.venv/bin/python -m ruff check .
```

Expected: exit `0`

- [ ] **Step 3: Run repository format check**

Run:

```bash
../../.venv/bin/python -m ruff format --check .
```

Expected: exit `0`

- [ ] **Step 4: Run strict type checking**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -m mypy src
```

Expected: `Success: no issues found`

- [ ] **Step 5: Check local and committed-range whitespace**

Run:

```bash
git diff --check
git diff --check main HEAD
```

Expected: ทั้งสองคำสั่งไม่มี output และ exit `0`

- [ ] **Step 6: Confirm the change boundary and clean worktree**

Run:

```bash
git diff --name-only main...HEAD
git status --short
```

Expected:

```text
.github/workflows/verify.yml
AGENTS.md
docs/superpowers/plans/2026-07-27-ci-verification-workflow.md
docs/superpowers/specs/2026-07-27-ci-verification-workflow-design.md
tests/unit/test_ci_workflow.py
```

และ `git status --short` ไม่มี output หลัง commit plan document

- [ ] **Step 7: Stop before external publication**

รายงานผล local verification และขอคำยืนยันจากผู้ใช้ก่อน push branch ไป GitHub ตาม `AGENTS.md` หลัง push จึงตรวจ GitHub Actions run และคง DEV-121 เป็น `In Progress` จนกว่า run จะผ่าน ห้าม merge เข้า `main` โดยไม่ได้รับคำยืนยันแยกต่างหาก
