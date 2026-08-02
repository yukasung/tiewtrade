# DEV-134 Bot Control Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ Bot Control แสดงข้อมูลและ action ตาม `No Session`, `Configured`, `Starting`, `Running`, `Stopping`, `Stopped` และ `Blocked` ผ่าน immutable application snapshot โดยไม่เริ่ม Market Data, Strategy หรือ Execution จริงใน slice นี้

**Architecture:** เพิ่ม deep application module `bot_control.py` ซึ่งเป็นเจ้าของ state invariants, allowed actions และการรักษา Workspace facts จากนั้นให้ `BotLifecycleWorkflow` ใน UI layer เป็นเจ้าของ background task/generation lifecycle สำหรับ injected Start/Stop/Recover callables ส่วน `BotControlWidget` แสดง snapshot โดยไม่ derive business decision เอง Production composition ยังไม่ inject Runtime actions จึงแสดง `Start Bot` แบบ disabled อย่างซื่อสัตย์จน DEV-136 เชื่อม use case จริง ขณะที่ tests/acceptance inject fake actions เพื่อพิสูจน์ state flow โดยไม่มี trading side effect

**Tech Stack:** Python 3.13, frozen/slotted dataclasses, `Decimal`, UTC `datetime`, PySide6, `QThreadPool`, pytest, pytest-qt, Ruff, Mypy

## Global Constraints

- UI เป็นภาษาอังกฤษและใช้ Full Dark Theme; เอกสารและ Linear ใช้ภาษาไทย
- UI ห้าม import SQLite, Strategy, Binance SDK หรือ Execution adapter โดยตรง
- Create Session ตรวจสอบและบันทึก immutable configuration เท่านั้น; ห้ามเริ่ม Market Data, Strategy หรือ Execution
- Production composition ของ DEV-134 ห้ามจำลอง `Running`; Start/Stop/Recover actions เปิดใช้เฉพาะเมื่อมี injected application callable
- Tests ใช้ fake actions เท่านั้นและห้ามเรียก network, Binance Private API, credentials หรือ Live order
- `TradingWorkspaceSnapshot` เป็นแหล่งข้อมูล Header/Orders/Basket เดียว; Bot Control snapshot ต้องอ้าง Workspace snapshot เดิมและห้ามคำนวณ PnL หรือ Basket business rules ซ้ำ
- `Starting` และ `Stopping` ห้ามรับ action ซ้ำ; callback จาก generation เก่าหรือหลัง close ต้องถูกละทิ้ง
- `Blocked` ต้องแสดง sanitized reason, ไม่มี raw exception/path/payload และ `entry_creation_allowed` ต้องเป็น `False`
- ไม่มี Manual Buy/Sell หรือ manual order fields
- ห้ามสร้าง generic base class, registry หรือ factory; ใช้ callable interface ที่ consumer Module เป็นเจ้าของเท่านั้น

---

### Task 1: สร้าง immutable Bot Control lifecycle model

**Files:**
- Create: `src/tiewtrade/application/bot_control.py`
- Create: `tests/unit/application/test_bot_control.py`

**Interfaces:**
- Consumes: `ConfiguredPaperSession`, `TradingWorkspaceSnapshot`, `BotRuntimeState`, `DataFreshness`, `WorkspaceReadState`
- Produces: `BotControlAction`, `BotLifecycleResult`, `BotControlSnapshot`, `configured_bot_control()`, `transition_bot_control()`, `blocked_bot_control()`

- [ ] **Step 1: เขียน failing tests สำหรับ state invariants และ action availability**

เพิ่ม tests ที่สร้าง configured Spot Session และ exact UTC Workspace แล้ว assert:

```python
def test_configured_control_exposes_summary_without_runtime_actions() -> None:
    snapshot = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        actions=frozenset(),
    )

    assert snapshot.state is BotRuntimeState.CONFIGURED
    assert snapshot.workspace.header is not None
    assert snapshot.workspace.header.runtime_state is BotRuntimeState.CONFIGURED
    assert snapshot.available_actions == frozenset()
    assert snapshot.entry_creation_allowed is False
```

เพิ่ม tests สำหรับ action-enabled fake seam, Starting/Running/Stopping/Stopped/Blocked, invalid action/state combinations, missing sanitized Blocked reason, workspace/header state mismatch และ immutable/frozen behavior:

```python
def test_running_control_uses_workspace_facts_and_allows_only_stop() -> None:
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=OBSERVED_AT,
        actions=frozenset({BotControlAction.START}),
    )
    running_workspace = workspace_with_runtime_state(
        configured.workspace,
        BotRuntimeState.RUNNING,
        data_freshness=DataFreshness.FRESH,
    )

    starting = transition_bot_control(
        configured,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                configured.workspace,
                BotRuntimeState.STARTING,
            ),
        ),
        progress_message="Starting Paper Bot",
    )
    running = transition_bot_control(
        starting,
        result=BotLifecycleResult(workspace=running_workspace),
        actions=frozenset({BotControlAction.STOP}),
    )

    assert running.available_actions == frozenset({BotControlAction.STOP})
    assert running.entry_creation_allowed is True
    assert running.workspace is running_workspace
```

- [ ] **Step 2: รัน RED และยืนยัน failure ที่ถูกต้อง**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/application/test_bot_control.py -q
```

Expected: FAIL เพราะยังไม่มี `tiewtrade.application.bot_control`

- [ ] **Step 3: Implement deep application module ขั้นต่ำ**

สร้าง interface หลัก:

```python
class BotControlAction(StrEnum):
    START = "start"
    STOP = "stop"
    RECOVER = "recover"


@dataclass(frozen=True, slots=True)
class BotLifecycleResult:
    workspace: TradingWorkspaceSnapshot
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BotControlSnapshot:
    state: BotRuntimeState
    session: ConfiguredPaperSession
    workspace: TradingWorkspaceSnapshot
    available_actions: frozenset[BotControlAction]
    progress_message: str | None = None
    blocked_reason: str | None = None

    @property
    def entry_creation_allowed(self) -> bool:
        header = self.workspace.header
        return (
            self.state is BotRuntimeState.RUNNING
            and self.workspace.read_state is WorkspaceReadState.READY
            and header is not None
            and header.data_freshness is DataFreshness.FRESH
        )
```

Validation ต้องบังคับ:

- `workspace.header` ต้องมีและ `header.runtime_state == state`
- `Configured` อนุญาต action เฉพาะ `START`
- `Starting`/`Stopping` ต้องมี `progress_message` และไม่มี action
- `Running` อนุญาต action เฉพาะ `STOP`; การสร้าง Entry อนุญาตเฉพาะเมื่อ Workspace เป็น `READY` และ Data Freshness เป็น `FRESH`
- `Stopped` ไม่มี action
- `Blocked` ต้องมี non-empty sanitized `blocked_reason`, อนุญาตเฉพาะ `RECOVER` และไม่อนุญาต Entry
- `No Session` ไม่สร้างด้วย `BotControlSnapshot`; Form ยังคงขับจาก empty Workspace เดิม
- transition ต้องเป็นไปตาม state diagram เท่านั้นและรักษา exact Session, Orders, Basket และ `data_as_of_utc`
- `BotLifecycleResult.blocked_reason` ต้องมีค่าเฉพาะเมื่อ result Workspace เป็น `BLOCKED`

เพิ่ม helper ใน module เดียว:

```python
def workspace_with_runtime_state(
    workspace: TradingWorkspaceSnapshot,
    state: BotRuntimeState,
    *,
    data_freshness: DataFreshness | None = None,
) -> TradingWorkspaceSnapshot:
    ...
```

Helper ใช้ `dataclasses.replace` เท่านั้นและ reject Workspace ที่ไม่มี Header รวมทั้งรักษา `WorkspaceReadState`, Orders, Basket และ UTC facts เดิม

- [ ] **Step 4: รัน GREEN, lint, type check และ diff check**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/application/test_bot_control.py tests/unit/application/test_trading_workspace.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src/tiewtrade/application/bot_control.py tests/unit/application/test_bot_control.py
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src/tiewtrade/application/bot_control.py tests/unit/application/test_bot_control.py
PYTHONPATH=src ../../.venv/bin/python -m mypy
git diff --check
```

Expected: ทุกคำสั่งผ่าน

- [ ] **Step 5: Commit**

```bash
git add src/tiewtrade/application/bot_control.py tests/unit/application/test_bot_control.py
git commit -m "feat: model bot control lifecycle states"
```

---

### Task 2: สร้าง generation-safe Bot Lifecycle Workflow

**Files:**
- Create: `src/tiewtrade/ui/bot_lifecycle_workflow.py`
- Create: `tests/unit/ui/test_bot_lifecycle_workflow.py`

**Interfaces:**
- Consumes: Task 1 `BotControlSnapshot`, `BotLifecycleResult`, `BotControlAction`, `transition_bot_control()`, `blocked_bot_control()`, `BackgroundTask`, `QThreadPool`
- Produces: `LifecycleAction`, `BotLifecycleWorkflow.configure()`, `.start_bot()`, `.stop_bot()`, `.recover()`, `.close()`, `snapshot_changed`, `busy_changed`

- [ ] **Step 1: เขียน failing workflow tests**

ใช้ `QThreadPool(maxThreadCount=1)` และ fake callables เพื่อพิสูจน์:

```python
def test_start_emits_starting_then_running_off_ui_thread(qtbot: QtBot) -> None:
    worker_threads: list[int] = []

    def start(snapshot: BotControlSnapshot) -> BotLifecycleResult:
        worker_threads.append(threading.get_ident())
        return BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                snapshot.workspace,
                BotRuntimeState.RUNNING,
                data_freshness=DataFreshness.FRESH,
            )
        )

    workflow = BotLifecycleWorkflow(start_bot=start, stop_bot=None, recover=None, ...)
    emitted: list[BotControlSnapshot] = []
    workflow.snapshot_changed.connect(emitted.append)
    workflow.configure(configured_spot_session())
    workflow.start_bot()

    qtbot.waitUntil(lambda: emitted[-1].state is BotRuntimeState.RUNNING)
    assert [item.state for item in emitted[-2:]] == [
        BotRuntimeState.STARTING,
        BotRuntimeState.RUNNING,
    ]
    assert worker_threads[0] != threading.get_ident()
```

เพิ่ม tests สำหรับ repeated Start/Stop ไม่สร้าง task ซ้ำ, Running→Stopping→Stopped, failure→Blocked ด้วย sanitized constant, Blocked→Configured/Stopped ผ่าน fake recover, invalid result→Blocked, reconfigure ระหว่าง task ทิ้ง callback เก่า และ close ทิ้ง callback/ไม่ emit busy หลังปิด

- [ ] **Step 2: รัน RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_bot_lifecycle_workflow.py -q
```

Expected: FAIL เพราะยังไม่มี workflow module

- [ ] **Step 3: Implement workflow ขั้นต่ำ**

ใช้ callable interface ที่ consumer UI module เป็นเจ้าของ:

```python
LifecycleAction = Callable[[BotControlSnapshot], BotLifecycleResult]


class BotLifecycleWorkflow(QObject):
    snapshot_changed = Signal(object)
    busy_changed = Signal(bool)

    def configure(self, session: ConfiguredPaperSession) -> None: ...
    def start_bot(self) -> None: ...
    def stop_bot(self) -> None: ...
    def recover(self) -> None: ...
    def close(self) -> None: ...
```

ข้อกำหนด implementation:

- `configure()` increment generation และ publish `Configured`; `START` มีเฉพาะเมื่อ `start_bot` callable ถูก inject
- Start publish `Starting` ก่อน submit background task; Stop publish `Stopping`
- Success รับเฉพาะ `BotLifecycleResult` ที่มี Workspace Header และ target state ที่อนุญาต: Start→Running/Blocked, Stop→Stopped/Blocked, Recover→Configured/Stopped/Blocked
- result แบบ `Blocked` ต้องมี sanitized `blocked_reason`; result state อื่นต้องไม่มี reason
- Actions หลัง success คำนวณจาก callable ที่มีจริง ไม่ derive ใน UI
- Exception และ invalid result map เป็น sanitized `"Paper Bot could not be started"`, `"Paper Bot could not be stopped"` หรือ `"Paper Bot recovery failed"`; ห้ามส่ง `str(error)` ไป UI
- `_task_generation` ต้องตรงกับ current generation และ workflow ต้องไม่ closed ก่อน publish
- ระหว่าง active task action ซ้ำเป็น no-op
- `close()` increment generation และ late callback ไม่เปลี่ยน snapshot

- [ ] **Step 4: รัน GREEN และ quality checks เฉพาะส่วน**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_bot_lifecycle_workflow.py tests/unit/application/test_bot_control.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src/tiewtrade/ui/bot_lifecycle_workflow.py tests/unit/ui/test_bot_lifecycle_workflow.py
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src/tiewtrade/ui/bot_lifecycle_workflow.py tests/unit/ui/test_bot_lifecycle_workflow.py
PYTHONPATH=src ../../.venv/bin/python -m mypy
git diff --check
```

Expected: ทุกคำสั่งผ่าน

- [ ] **Step 5: Commit**

```bash
git add src/tiewtrade/ui/bot_lifecycle_workflow.py tests/unit/ui/test_bot_lifecycle_workflow.py
git commit -m "feat: coordinate bot lifecycle actions"
```

---

### Task 3: เชื่อม state-driven Bot Control กับ Workspace และ acceptance

**Files:**
- Create: `src/tiewtrade/ui/bot_control.py`
- Modify: `src/tiewtrade/ui/session_overview.py`
- Modify: `src/tiewtrade/ui/trading_workspace.py`
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `src/tiewtrade/ui/desktop.py`
- Modify: `src/tiewtrade/desktop_main.py`
- Create: `tests/unit/ui/test_bot_control.py`
- Modify: `tests/unit/ui/test_trading_workspace.py`
- Modify: `tests/unit/ui/test_main_window.py`
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `PROJECT_PLAN.md`
- Add to commit: `docs/superpowers/plans/2026-08-01-dev-134-bot-control-lifecycle.md`

**Interfaces:**
- Consumes: Task 1 `BotControlSnapshot`; Task 2 `BotLifecycleWorkflow`; existing Session Setup, Session Overview และ Workspace Header
- Produces: state-driven `BotControlWidget`, `TradingWorkspace.start_bot_requested/stop_bot_requested/recover_requested`, optional lifecycle callable injection ใน `MainWindow`/desktop composition

- [ ] **Step 1: เขียน failing widget/workspace tests**

สร้าง `BotControlWidget` tests ที่ feed immutable snapshots และ assert:

- `Configured` แสดง immutable `SessionOverviewWidget`, `Start Bot`, ไม่มี Stop/Recover และไม่มี Manual Buy/Sell
- `Starting` แสดง progress text และปิดทุก action
- `Running` แสดง Runtime/Basket facts จาก `snapshot.workspace` และ `Stop Session`
- `Stopping` แสดง progress และปิด action ซ้ำ
- `Stopped` แสดง durable summary และไม่มี Start/Stop
- `Blocked` แสดง sanitized reason, `Recovery Required`, Recover เฉพาะเมื่อ action มีอยู่ และไม่มี Entry action
- Click action emit semantic signal เพียงครั้งเดียวเมื่อ action enabled

ตัวอย่าง:

```python
def test_running_shows_runtime_and_basket_facts_without_manual_order_controls(
    qtbot: QtBot,
) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)

    widget.show_snapshot(running_control_with_basket())

    assert widget.state_value.text() == "Running"
    assert widget.entry_count_value.text() == "2"
    assert widget.average_entry_value.text() == "64000 USDT"
    assert widget.take_profit_value.text() == "66000 USDT"
    assert widget.stop_button.isVisible()
    assert widget.findChildren(QPushButton, "manualBuyButton") == []
    assert widget.findChildren(QPushButton, "manualSellButton") == []
```

- [ ] **Step 2: เขียน failing MainWindow/acceptance tests**

เพิ่ม MainWindow tests ที่ inject fake Start/Stop/Recover และ assert lifecycle snapshots update Header + Bot Control ในลำดับเดียวกัน, repeated clicks ทำงานครั้งเดียว, raw fake exception ไม่ปรากฏ และ callback เก่าหลัง close/reconfigure ไม่เขียน UI

เพิ่ม deterministic acceptance แบบ parameterized Spot/Futures:

1. create durable session แล้ว state เป็น Configured
2. inject fake Start ที่คืน Running Workspace โดยไม่แตะ SQLite Basket/Fill และไม่เรียก network
3. Start แสดง Starting ก่อน Running
4. Running ไม่มี Manual Buy/Sell และแสดง Stop Session
5. fake Stop คืน Stopped โดย Basket/History ไม่ถูก force close
6. constructor ที่ไม่ inject lifecycle actions แสดง Start Bot แบบ disabled พร้อม supporting text `Runtime integration is not available yet` และไม่สร้าง fake Running state

- [ ] **Step 3: รัน RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_bot_control.py tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py -q
```

Expected: FAIL เพราะยังไม่มี `BotControlWidget`, signals และ MainWindow lifecycle composition

- [ ] **Step 4: Implement UI renderer และ composition**

สร้าง `BotControlWidget` เป็น thin presentation:

```python
class BotControlWidget(QWidget):
    start_requested = Signal()
    stop_requested = Signal()
    recover_requested = Signal()

    @Slot(object)
    def show_snapshot(self, value: object) -> None:
        if not isinstance(value, BotControlSnapshot):
            return
        ...
```

Widget ใช้ `SessionOverviewWidget` สำหรับ immutable configuration summary และ render state/action จาก snapshot เท่านั้น ตัวเลขใช้ `Decimal` formatting โดยไม่ผ่าน float

ปรับ `TradingWorkspace`:

- ใช้ `BotControlWidget` เป็น non-setup lifecycle page
- expose `overview = bot_control.overview` เพื่อรักษา existing tests/callers
- `show_bot_control_snapshot()` ต้อง render Bot Control และเรียก `show_workspace_snapshot(snapshot.workspace)` เพื่อให้ Header กับ control ใช้ generation เดียวกัน
- relay semantic action signals
- storage unavailable page ยังคงแยกจาก runtime Blocked

ปรับ `MainWindow`:

- constructor รับ optional `start_bot`, `stop_bot`, `recover_bot` callables ค่าเริ่มต้น `None`
- สร้าง `BotLifecycleWorkflow` ด้วย thread pool เดิม
- เมื่อ `SessionWorkflow.session_ready` ให้ `configure(session)`; ห้ามเริ่ม action อัตโนมัติ
- wire action signals ไป workflow และ snapshot ไป Workspace
- close workflow ก่อน `waitForDone`
- optional callables ไม่ถูก inject ใน `desktop_main.py` ของ DEV-134 ทำให้ production Configured แสดง Start Bot แบบ disabled อย่างซื่อสัตย์

- [ ] **Step 5: อัปเดต acceptance และ Project Plan**

เพิ่มสถานะ DEV-134 ใน `PROJECT_PLAN.md` ว่าส่งมอบ state-driven Bot Control, fake lifecycle seam, repeated-action guard และ stale callback suppression แล้ว แต่ Runtime Start/Stop/Recovery จริงยังอยู่ DEV-136

ยืนยัน acceptance source guards ยังคงห้าม UI/composition import Runtime, Strategy, Execution, Binance/private API และ sensitive terms

- [ ] **Step 6: รัน focused และ full quality gates**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/application/test_bot_control.py tests/unit/ui/test_bot_lifecycle_workflow.py tests/unit/ui/test_bot_control.py tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py -q
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Expected: ทุก command ผ่าน ไม่มี network/private/live side effect

- [ ] **Step 7: Commit**

```bash
git add PROJECT_PLAN.md docs/superpowers/plans/2026-08-01-dev-134-bot-control-lifecycle.md src/tiewtrade/ui/bot_control.py src/tiewtrade/ui/session_overview.py src/tiewtrade/ui/trading_workspace.py src/tiewtrade/ui/main_window.py src/tiewtrade/ui/desktop.py src/tiewtrade/desktop_main.py tests/unit/ui/test_bot_control.py tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py
git commit -m "feat: render bot control lifecycle states"
```

## Plan Self-Review

- Spec coverage: ครบทุก DEV-134 acceptance criterion และ Delivery Slice 3 โดยไม่ดึง Runtime integration ของ DEV-136 เข้ามา
- Placeholder scan: ไม่มี TBD/TODO หรือ behavior ที่ไม่ระบุ
- Type consistency: Task 2/3 ใช้ `BotControlSnapshot` และ `TradingWorkspaceSnapshot` จาก Task 1 ชื่อเดียวกัน
- Safety: Production ไม่สร้าง fake Running; optional callables ไม่ถูก inject จน DEV-136
- YAGNI: ไม่มี base class, registry, factory, Runtime adapter หรือ persistence schema ใหม่
