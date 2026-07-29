# DEV-130 Desktop Session Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** กู้ Desktop Session Setup acceptance contract จาก DEV-115 และ focused `SessionWorkflow` refactor จาก DEV-116 เข้าสู่ `main` ล่าสุดโดยไม่ย้อน hardening ใหม่

**Architecture:** ใช้ Selective Recovery จาก backup branches เป็น reference เท่านั้น ไม่ merge หรือ cherry-pick branch เก่าทั้งก้อน กู้ acceptance test ก่อน จากนั้นสร้าง `SessionWorkflow(QObject)` ด้วย TDD แล้วให้ `MainWindow` เชื่อม semantic signals เพื่อ render Setup, Overview และ Unavailable โดยคง application contract, SQLite schema, UI copy และ current safety coverage

**Tech Stack:** Python 3.12+, PySide6, pytest, pytest-qt, SQLite, Ruff, mypy strict, Node.js documentation tests

## Global Constraints

- ใช้ Paper/fake adapters เท่านั้น ห้ามเชื่อม Binance หรือส่ง Live order
- ไม่เปลี่ยน application request/result, SQLite schema, UI copy หรือ business rules
- ไม่สร้าง generic task framework, ViewModel framework หรือ hypothetical interface
- UI ห้าม import SQLite, Strategy, Execution, Market Data Runtime, Binance หรือ credentials
- ห้าม merge หรือ cherry-pick DEV-115/DEV-116 ทั้ง branch; ใช้ไฟล์เดิมเป็น reference แล้วปรับเฉพาะ behavior ที่ยังถูกต้อง
- ต้องรักษา decimal-context, persistence, runtime, trading และ current MainWindow safety hardening บน `main`
- ใช้ TDD สำหรับ production behavior: test ต้อง fail ด้วยเหตุผลที่คาดไว้ก่อนเพิ่ม production implementation
- Semantic result ต้องเกิดก่อน `busy_changed(False)`
- `close()` ต้อง suppress late semantic result แต่ worker `finished` ยังต้อง disconnect callbacks และ clear active task
- DEV-115 acceptance tests ต้องผ่านหลัง refactor

---

## File Structure

- Create: `tests/acceptance/test_desktop_session_setup.py` — recovered Spot/Futures Desktop vertical-slice contract
- Create: `tests/unit/ui/test_session_workflow.py` — focused Workflow lifecycle contract
- Create: `src/tiewtrade/ui/session_workflow.py` — Qt-only Session task orchestration
- Modify: `src/tiewtrade/ui/main_window.py` — presentation และ semantic-signal wiring เท่านั้น
- Modify: `src/tiewtrade/ui/desktop.py` — import callable aliases จาก Workflow owner
- Modify: `tests/unit/ui/test_main_window.py` — architecture contract และ current presentation/safety coverage
- Modify: `PROJECT_PLAN.md` — บันทึกสถานะ recovery โดยไม่เปลี่ยน delivery order

### Task 1: กู้ DEV-115 Desktop acceptance contract บน `main` ล่าสุด

**Files:**
- Create: `tests/acceptance/test_desktop_session_setup.py`

**Interfaces:**
- Consumes: `MainWindow`, `CreatePaperSession`, `SQLiteActivePaperSessions`, `SQLiteDatabase`
- Produces: acceptance contract สำหรับ Task 3 และ final gate

- [ ] **Step 1: ตรวจ source artifact ที่อนุมัติให้กู้**

อ่านไฟล์จาก backup branch โดยไม่ checkout, merge หรือ cherry-pick:

```bash
git show dev-115-desktop-session-acceptance:tests/acceptance/test_desktop_session_setup.py
```

ยืนยันว่า artifact มี tests ต่อไปนี้ครบ:

```text
test_desktop_paper_session_create_overview_and_restart_restore
test_desktop_session_storage_unavailable_fails_closed
test_desktop_session_sqlite_write_failure_after_setup_fails_closed
test_desktop_session_validation_failure_after_setup_preserves_input
test_desktop_session_setup_sources_exclude_runtime_and_sensitive_imports
test_desktop_session_setup_smoke_composes_without_network
```

- [ ] **Step 2: สร้าง acceptance test file แบบ selective copy**

สร้าง `tests/acceptance/test_desktop_session_setup.py` จาก content ที่ commit
`3a31823` โดยคง test scenarios, deterministic UUID/time, socket guard, AST boundary,
Basket/Fill side-effect assertions และ temporary SQLite ครบทุกข้อ

ห้ามนำ `PROJECT_PLAN.md` หรือไฟล์อื่นจาก branch เก่ามาพร้อมขั้นตอนนี้ และห้ามแก้
production code

- [ ] **Step 3: รัน acceptance tests กับ source ปัจจุบัน**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/acceptance/test_desktop_session_setup.py -q
```

Expected: 7 parameterized test cases PASS หากมี incompatibility ให้แก้เฉพาะ test
harness ให้ใช้ current public contract ห้ามลด assertion หรือเปลี่ยน production behavior
ใน Task นี้

- [ ] **Step 4: รัน focused quality checks**

```bash
../../.venv/bin/python -m ruff check tests/acceptance/test_desktop_session_setup.py
../../.venv/bin/python -m ruff format --check tests/acceptance/test_desktop_session_setup.py
git diff --check
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/acceptance/test_desktop_session_setup.py
git commit -m "test: recover desktop session acceptance"
```

### Task 2: สร้าง focused SessionWorkflow ด้วย TDD

**Files:**
- Create: `tests/unit/ui/test_session_workflow.py`
- Create: `src/tiewtrade/ui/session_workflow.py`

**Interfaces:**
- Consumes: `SessionTask`, `PaperSessionSetupValues`, `PaperSessionCreateOutcome`, `ConfiguredPaperSession`, `QThreadPool`
- Produces: `CreateSession`, `LoadActiveSession`, `SessionWorkflow.start()`, `SessionWorkflow.create(values)`, `SessionWorkflow.close()` และ signals `setup_required`, `session_ready`, `validation_failed`, `unavailable`, `busy_changed`

- [ ] **Step 1: เขียน failing Workflow interface tests**

ใช้ `tests/unit/ui/test_session_workflow.py` ที่ commit `4573387` เป็น behavior reference
และสร้าง test file ใหม่ให้ครอบคลุม:

```text
startup without active session -> setup_required
startup with ConfiguredPaperSession -> session_ready
create success -> session_ready and reusable after finished
validation error -> validation_failed before setup_required
storage/unexpected errors -> sanitized unavailable copy
invalid load/create result and invalid nested session -> fail closed
duplicate create while busy -> one callback invocation
finished -> clear active task and disconnect succeeded/failed/finished callbacks
close -> suppress late semantic result and reject new work
close followed by worker finished -> clear active task and disconnect callbacks
semantic result -> emitted before busy_changed(False)
```

เพิ่ม test ordering ที่บันทึก events:

```python
events: list[str] = []
workflow.setup_required.connect(lambda: events.append("setup"))
workflow.busy_changed.connect(lambda busy: events.append(f"busy:{busy}"))

workflow.start()

qtbot.waitUntil(lambda: events == ["busy:True", "setup", "busy:False"])
```

เพิ่ม close-cleanup assertion หลัง release worker:

```python
workflow.close()
release.set()
qtbot.waitUntil(lambda: workflow._active_task is None)
assert thread_pool.waitForDone(1_000)
assert semantic_events == []
```

- [ ] **Step 2: รัน tests เพื่อยืนยัน RED**

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_session_workflow.py -q
```

Expected: FAIL during collection with
`ModuleNotFoundError: No module named 'tiewtrade.ui.session_workflow'`

- [ ] **Step 3: เพิ่ม minimal SessionWorkflow implementation**

สร้าง `src/tiewtrade/ui/session_workflow.py` โดยใช้ focused interface:

```python
from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.ui.session_tasks import SessionTask

CreateSession = Callable[[PaperSessionSetupValues], PaperSessionCreateOutcome]
LoadActiveSession = Callable[[], ConfiguredPaperSession | None]


class _Operation(Enum):
    LOAD = "load"
    CREATE = "create"


class SessionWorkflow(QObject):
    setup_required = Signal()
    session_ready = Signal(object)
    validation_failed = Signal(str, str)
    unavailable = Signal(str)
    busy_changed = Signal(bool)
```

Implementation ต้อง:

- เก็บเพียง one active `SessionTask` และ operation เดียว
- emit busy `True` ก่อน start worker
- ตรวจ outer result และ nested `ConfiguredPaperSession`
- map errors ตาม design โดยไม่ส่ง raw exception
- ใน `_task_finished()` disconnect `succeeded`, `failed`, `finished` ก่อน clear state
- clear state เสมอแม้ `close()` แล้ว
- emit busy `False` เฉพาะ callbacks generation ปัจจุบัน

- [ ] **Step 4: รัน Workflow tests เพื่อยืนยัน GREEN**

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_session_workflow.py -q
```

Expected: all Workflow tests PASS และไม่มี warning

- [ ] **Step 5: รัน focused quality checks**

```bash
../../.venv/bin/python -m ruff check src/tiewtrade/ui/session_workflow.py tests/unit/ui/test_session_workflow.py
../../.venv/bin/python -m ruff format --check src/tiewtrade/ui/session_workflow.py tests/unit/ui/test_session_workflow.py
env PYTHONPATH=src ../../.venv/bin/python -m mypy src/tiewtrade/ui/session_workflow.py
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 6: Commit Task 2**

```bash
git add src/tiewtrade/ui/session_workflow.py tests/unit/ui/test_session_workflow.py
git commit -m "refactor: recover desktop session workflow"
```

### Task 3: ให้ MainWindow delegate lifecycle โดยไม่ลด current safety coverage

**Files:**
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `src/tiewtrade/ui/desktop.py`
- Modify: `tests/unit/ui/test_main_window.py`

**Interfaces:**
- Consumes: `SessionWorkflow` จาก Task 2
- Produces: `MainWindow` constructor เดิมที่ render semantic signals และไม่ถือ Qt task lifecycle เอง

- [ ] **Step 1: เพิ่ม failing architecture test**

เพิ่มใน `tests/unit/ui/test_main_window.py`:

```python
import ast
import inspect

import tiewtrade.ui.main_window as main_window_module


def test_main_window_delegates_session_task_lifecycle_to_workflow() -> None:
    source = inspect.getsource(main_window_module)
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "SessionWorkflow" in imported_names
    assert "SessionTask" not in imported_names
    assert "_active_create_task" not in source
    assert "_active_load_task" not in source
    assert "_callback_generation" not in source
```

- [ ] **Step 2: รัน architecture test เพื่อยืนยัน RED**

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_main_window.py::test_main_window_delegates_session_task_lifecycle_to_workflow -q
```

Expected: FAIL เพราะ current `MainWindow` ยัง import `SessionTask` และเก็บ active-task
fields

- [ ] **Step 3: Rewire MainWindow ไปยัง SessionWorkflow**

ปรับ `src/tiewtrade/ui/main_window.py` ให้:

- import `CreateSession`, `LoadActiveSession`, `SessionWorkflow` จาก
  `tiewtrade.ui.session_workflow`
- สร้าง Workflow หลัง widgets/layout พร้อมและก่อนเริ่ม startup load
- เชื่อม `busy_changed`, `setup_required`, `session_ready`, `validation_failed`,
  `unavailable`
- ให้ `_create_requested()` clear form errors แล้วเรียก `workflow.create(values)`
- ให้ `_set_busy()` เปลี่ยน Setup loading และ retry state
- ให้ `_show_session()`, `_show_validation_error()`, `_show_unavailable()`,
  `_show_setup()` ทำ presentation เท่านั้น
- ให้ `closeEvent()` เรียก `workflow.close()`
- ลบ direct `SessionTask`, active-task sets, operation-specific generation state และ
  error mapping ออกจาก Window

ใน `src/tiewtrade/ui/desktop.py` import type aliases จาก Workflow owner:

```python
from tiewtrade.ui.main_window import MainWindow
from tiewtrade.ui.session_workflow import CreateSession, LoadActiveSession
```

- [ ] **Step 4: ปรับเฉพาะ private-state assertion โดยไม่ลด behavior coverage**

คง current MainWindow tests สำหรับ duplicate submit, unknown create failure,
parameterized load failures, retry และ close safetyทั้งหมด

ใน close test ลบเฉพาะ assertion ที่อ่าน `window._tasks` เพราะ ownership ย้ายไป
Workflow และแทนด้วยการรอ event loop:

```python
assert thread_pool.waitForDone(1_000)
qtbot.wait(20)
```

Task cleanup และ signal disconnect ต้องถูกพิสูจน์แล้วใน
`tests/unit/ui/test_session_workflow.py`

- [ ] **Step 5: รัน focused UI tests เพื่อยืนยัน GREEN**

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_session_workflow.py tests/unit/ui/test_main_window.py tests/unit/ui/test_session_setup.py tests/unit/ui/test_session_overview.py tests/unit/test_desktop_main.py -q
```

Expected: all selected UI/composition tests PASS

- [ ] **Step 6: รัน recovered acceptance หลัง rewire**

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/acceptance/test_desktop_session_setup.py -q
```

Expected: 7 cases PASS; no network attempt, duplicate durable state, Basket หรือ Fill

- [ ] **Step 7: รัน focused quality checks**

```bash
../../.venv/bin/python -m ruff check src/tiewtrade/ui tests/unit/ui tests/acceptance/test_desktop_session_setup.py
../../.venv/bin/python -m ruff format --check src/tiewtrade/ui tests/unit/ui tests/acceptance/test_desktop_session_setup.py
env PYTHONPATH=src ../../.venv/bin/python -m mypy src
git diff --check
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 8: Commit Task 3**

```bash
git add src/tiewtrade/ui/main_window.py src/tiewtrade/ui/desktop.py tests/unit/ui/test_main_window.py
git commit -m "refactor: delegate desktop session lifecycle"
```

### Task 4: บันทึก recovery และรัน integration gate

**Files:**
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: verified DEV-115 acceptance และ DEV-116 Workflow recovery
- Produces: delivery status ที่ตรงกับ source code บน branch ล่าสุด

- [ ] **Step 1: เพิ่มสถานะ recovery ใน PROJECT_PLAN**

เพิ่มหลังสถานะ DEV-99 โดยไม่เปลี่ยน delivery order:

```markdown
สถานะ DEV-115/DEV-116 (กู้คืนผ่าน DEV-130): Desktop Session Setup acceptance
พิสูจน์ Paper Spot และ Paper Futures ตั้งแต่ form, durable create, Overview,
restart/restore, duplicate suppression และ fail-closed paths โดยไม่เริ่ม Market Data,
Strategy หรือ Execution แล้ว Background-task lifecycle ถูกย้ายจาก `MainWindow` ไปอยู่
ใน focused `SessionWorkflow` ซึ่งดูแล startup load, create, busy state, sanitized error
mapping, task cleanup และ late-callback invalidation โดยไม่เปลี่ยน SQLite schema,
application contract, UI copy หรือ business rules
```

- [ ] **Step 2: รัน full Python gate**

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
env PYTHONPATH=src ../../.venv/bin/python -m mypy src
```

Expected: tests อย่างน้อย 581 เดิมรวม recovered tests ทั้งหมด PASS และทุก quality
check exit 0

- [ ] **Step 3: รัน documentation และ whitespace gates**

```bash
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check 766140e HEAD
```

Expected: docs 50 tests PASS และทุกคำสั่ง exit 0

- [ ] **Step 4: ตรวจ recovery scope**

```bash
git diff --stat 766140e..HEAD
git diff --name-status 766140e..HEAD
git status --short
```

Expected: ไม่มีไฟล์บน `main` ถูกลบ ไม่มี schema, business rule, Binance/private API,
credential หรือ Live execution change และ working tree สะอาดหลัง commit

- [ ] **Step 5: Commit Task 4**

```bash
git add PROJECT_PLAN.md
git commit -m "docs: record desktop session recovery"
```

- [ ] **Step 6: Final review**

สร้าง review package จาก merge base `766140e` ถึง HEAD แล้วใช้
`requesting-code-review` ตรวจสองแกน:

- Standards: DEV-130 spec, Source of Truth, TDD evidence, Trading Safety และ quality gates
- Code Quality: depth/locality ของ Workflow, signal ordering, cleanup, no behavior
  regression และไม่มี hypothetical abstraction

แก้ Critical/Important findings ผ่าน subagent review loop และรัน covering tests ซ้ำ
ก่อนรายงานพร้อม merge ห้าม push, merge หรือ cleanup จนกว่าจะได้รับคำยืนยันจากผู้ใช้
