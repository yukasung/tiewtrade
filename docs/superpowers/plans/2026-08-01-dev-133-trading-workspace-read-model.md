# DEV-133 Trading Workspace Read Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้าง immutable Trading Workspace snapshot และเชื่อม Persistent Status Header ผ่าน application-facing read model โดยให้ refresh ทำงานนอก UI thread, ทิ้ง callback generation เก่า และรักษา last-known durable data เมื่อเกิด Loading, Error หรือ Stale

**Architecture:** เพิ่ม `application/trading_workspace.py` เป็น deep module ที่ซ่อนการแปลง durable Session และการเปลี่ยน read state ไว้หลัง immutable snapshot interface เดียว โดย snapshot ครอบ Header, Open Orders และ Basket facts แบบ exact `Decimal`/UTC. ใช้ `SessionWorkflow` ที่มี background-task และ generation guard อยู่แล้วเป็น refresh seam เพื่อไม่เพิ่ม loader หรือ thread coordinator ซ้ำ; `TradingWorkspace` รับ snapshot และ render เท่านั้น ส่วนการเติม Orders/Basket จริงยังเป็นขอบเขต DEV-135.

**Tech Stack:** Python 3.12, PySide6 6.10, pytest, pytest-qt, Ruff, Mypy strict

## Global Constraints

- UI copy ใช้ภาษาอังกฤษ ส่วนเอกสารและ Linear ใช้ภาษาไทย
- UI ห้าม import SQLite, Strategy, Binance SDK หรือ Execution adapter
- Snapshot และ nested facts ต้อง immutable ด้วย frozen slotted dataclasses
- ราคา, Quantity และ PnL ต้องคงเป็น `Decimal` ตลอด read model และห้ามแปลงผ่าน `float`
- เวลาใน read model ต้องเป็น timezone-aware UTC และห้ามแปลงเป็น local timezone
- Refresh persistence work ต้องทำผ่าน focused worker นอก UI thread
- Callback ที่ไม่ใช่ generation ปัจจุบันหรือมาหลัง close ต้องไม่เขียนทับ UI state
- Loading, Empty, Ready, Error และ Stale ต้องเป็นคนละ state
- Loading, Error และ Stale ต้องรักษา Header, Orders, Basket และ `data_as_of_utc` จาก last-known durable snapshot
- `Create Paper Session` ยังบันทึก configuration เท่านั้นและไม่เริ่ม Market Data, Strategy หรือ Execution
- DEV-133 ไม่เติมข้อมูล Order/Basket จำลองและไม่เริ่ม Runtime; concrete data integration เป็นขอบเขต DEV-135/DEV-136
- ใช้ Paper/Fake adapters เท่านั้นและห้ามเรียก Binance Private API หรือ credentials

---

## File Structure

- Create `src/tiewtrade/application/trading_workspace.py` — immutable read-model types, validation และ state transition factories
- Create `tests/unit/application/test_trading_workspace.py` — ล็อก exact Decimal/UTC, immutability, configured mapping และ last-known preservation
- Modify `src/tiewtrade/ui/session_workflow.py` — publish workspace snapshots ผ่าน background refresh/generation guard เดิม
- Modify `tests/unit/ui/test_session_workflow.py` — พิสูจน์ loading/empty/ready/error และ stale generation suppression
- Modify `src/tiewtrade/ui/trading_workspace.py` — render persistent header และ placeholder states จาก snapshot เท่านั้น
- Modify `src/tiewtrade/ui/main_window.py` — wire `SessionWorkflow.workspace_changed` ไปยัง Workspace
- Modify `tests/unit/ui/test_trading_workspace.py` — พิสูจน์ header rendering และ exact state copy
- Modify `tests/unit/ui/test_main_window.py` — พิสูจน์ end-to-end background snapshot flow และ last-known retention
- Modify `tests/acceptance/test_desktop_session_setup.py` — พิสูจน์ create/restart header ผ่าน immutable snapshot
- Modify `PROJECT_PLAN.md` — บันทึกสถานะ Unified Trading Workspace slice 2 หลัง acceptance ผ่าน

## Task 1: Immutable Application Read Model

**Files:**
- Create: `src/tiewtrade/application/trading_workspace.py`
- Create: `tests/unit/application/test_trading_workspace.py`

**Interfaces:**
- Consumes: `ConfiguredPaperSession`, `TradeMode`, `MarketType`
- Produces: `WorkspaceReadState`, `BotRuntimeState`, `DataFreshness`, `WorkspaceHeaderSnapshot`, `OpenOrderSnapshot`, `BasketSnapshot`, `TradingWorkspaceSnapshot`, `empty_workspace_snapshot()`, `configured_workspace_snapshot()`, `loading_workspace_snapshot()`, `failed_workspace_snapshot()` และ `stale_workspace_snapshot()`

- [ ] **Step 1: เขียน failing tests สำหรับ immutable exact facts และ state transitions**

```python
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    DataFreshness,
    OpenOrderSnapshot,
    WorkspaceReadState,
    configured_workspace_snapshot,
    failed_workspace_snapshot,
    loading_workspace_snapshot,
    stale_workspace_snapshot,
)


def test_configured_snapshot_exposes_exact_header_facts() -> None:
    session = configured_spot_session()
    observed_at = datetime(2026, 8, 1, 12, tzinfo=UTC)

    snapshot = configured_workspace_snapshot(session, observed_at_utc=observed_at)

    assert snapshot.read_state is WorkspaceReadState.READY
    assert snapshot.header is not None
    assert snapshot.header.symbol == "BTCUSDT"
    assert snapshot.header.timeframe == "5m"
    assert snapshot.header.trade_mode.value == "paper"
    assert snapshot.header.market_type.value == "spot"
    assert snapshot.header.runtime_state is BotRuntimeState.CONFIGURED
    assert snapshot.header.data_freshness is DataFreshness.NOT_STARTED
    assert snapshot.data_as_of_utc is observed_at


def test_decimal_and_utc_order_and_basket_facts_remain_exact() -> None:
    created_at = datetime(2026, 8, 1, 12, tzinfo=UTC)
    order = OpenOrderSnapshot(
        order_id="order-1",
        created_at_utc=created_at,
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("66321.1200"),
        quantity=Decimal("0.00300000"),
        filled_quantity=Decimal("0.00100000"),
        status="PARTIALLY_FILLED",
    )
    basket = BasketSnapshot(
        symbol="BTCUSDT",
        market_type="spot",
        entry_count=2,
        total_quantity=Decimal("0.00600000"),
        average_entry_price=Decimal("66000.1250"),
        current_price=Decimal("66321.1200"),
        take_profit_price=Decimal("67000.0000"),
        unrealized_pnl=Decimal("1.92600000"),
        liquidation_price=None,
        lifecycle="ACTIVE_PAIR",
        updated_at_utc=created_at,
    )

    assert type(order.price) is Decimal
    assert type(basket.unrealized_pnl) is Decimal
    assert order.created_at_utc is created_at
    assert basket.updated_at_utc is created_at
    with pytest.raises(FrozenInstanceError):
        order.status = "FILLED"  # type: ignore[misc]


def test_loading_error_and_stale_preserve_last_known_durable_data() -> None:
    ready = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    loading = loading_workspace_snapshot(ready)
    failed = failed_workspace_snapshot(ready, "Workspace data is unavailable")
    stale = stale_workspace_snapshot(ready)

    for snapshot in (loading, failed):
        assert snapshot.header == ready.header
        assert snapshot.orders == ready.orders
        assert snapshot.basket == ready.basket
        assert snapshot.data_as_of_utc == ready.data_as_of_utc
    assert stale.header == replace(
        ready.header,
        data_freshness=DataFreshness.STALE,
    )
    assert stale.orders == ready.orders
    assert stale.basket == ready.basket
    assert stale.data_as_of_utc == ready.data_as_of_utc
    assert loading.read_state is WorkspaceReadState.LOADING
    assert failed.read_state is WorkspaceReadState.ERROR
    assert stale.read_state is WorkspaceReadState.STALE
    assert stale.header is not None
    assert stale.header.data_freshness is DataFreshness.STALE
```

- [ ] **Step 2: รัน tests เพื่อยืนยัน RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest tests/unit/application/test_trading_workspace.py -q
```

Expected: FAIL ระหว่าง import เพราะ `tiewtrade.application.trading_workspace` ยังไม่มี

- [ ] **Step 3: Implement immutable read model และ validation ขั้นต่ำ**

สร้าง enum และ frozen slotted dataclasses ตาม interface นี้:

```python
class WorkspaceReadState(StrEnum):
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    ERROR = "error"
    STALE = "stale"


class BotRuntimeState(StrEnum):
    NO_SESSION = "no_session"
    CONFIGURED = "configured"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    BLOCKED = "blocked"


class DataFreshness(StrEnum):
    NOT_STARTED = "not_started"
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class WorkspaceHeaderSnapshot:
    symbol: str
    timeframe: str
    trade_mode: TradeMode
    market_type: MarketType
    preset_version: str
    runtime_state: BotRuntimeState
    data_freshness: DataFreshness


@dataclass(frozen=True, slots=True)
class OpenOrderSnapshot:
    order_id: str
    created_at_utc: datetime
    symbol: str
    side: str
    order_type: str
    price: Decimal | None
    quantity: Decimal
    filled_quantity: Decimal
    status: str


@dataclass(frozen=True, slots=True)
class BasketSnapshot:
    symbol: str
    market_type: str
    entry_count: int
    total_quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    take_profit_price: Decimal
    unrealized_pnl: Decimal
    liquidation_price: Decimal | None
    lifecycle: str
    updated_at_utc: datetime


@dataclass(frozen=True, slots=True)
class TradingWorkspaceSnapshot:
    read_state: WorkspaceReadState
    header: WorkspaceHeaderSnapshot | None
    orders: tuple[OpenOrderSnapshot, ...]
    basket: BasketSnapshot | None
    data_as_of_utc: datetime | None
    message: str | None = None
```

Validation ต้อง reject naive/non-UTC datetimes, non-`Decimal` monetary fields, negative quantities/entry counts, empty identifiers และ state combinations ที่ไม่ถูกต้อง. Factory functions ต้องสร้าง `EMPTY`, `READY`, `LOADING`, `ERROR` และ `STALE` โดยใช้ `dataclasses.replace`; `configured_workspace_snapshot()` แปลง `ConfiguredPaperSession` เป็น Header `CONFIGURED` + `NOT_STARTED` โดย `orders=()` และ `basket=None` อย่างซื่อสัตย์.

- [ ] **Step 4: รัน focused tests และ application tests เพื่อยืนยัน GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest tests/unit/application/test_trading_workspace.py tests/unit/application/test_paper_session_setup.py -q
```

Expected: PASS

- [ ] **Step 5: รัน type/lint checks สำหรับไฟล์ Task 1**

Run:

```bash
PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m ruff check src/tiewtrade/application/trading_workspace.py tests/unit/application/test_trading_workspace.py
PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m mypy src/tiewtrade/application/trading_workspace.py tests/unit/application/test_trading_workspace.py
```

Expected: PASS ทั้งสองคำสั่ง

- [ ] **Step 6: Commit Task 1**

```bash
git add src/tiewtrade/application/trading_workspace.py tests/unit/application/test_trading_workspace.py
git commit -m "feat: add immutable workspace read model"
```

## Task 2: Background Refresh and Generation Safety

**Files:**
- Modify: `src/tiewtrade/ui/session_workflow.py`
- Modify: `tests/unit/ui/test_session_workflow.py`

**Interfaces:**
- Consumes: Task 1 factory functions และ existing `BackgroundTask`
- Produces: `SessionWorkflow.workspace_changed: Signal(object)` ซึ่ง emit `TradingWorkspaceSnapshot` ทุก read-state transition

- [ ] **Step 1: เขียน failing tests สำหรับ background refresh, exact states และ stale generation**

เพิ่ม tests ที่พิสูจน์พฤติกรรมต่อไปนี้ด้วย `threading.Event`, dedicated `QThreadPool` และ `qtbot.waitUntil`:

```python
def test_load_publishes_loading_then_ready_snapshot_off_ui_thread(qtbot: QtBot) -> None:
    caller_thread = threading.get_ident()
    worker_threads: list[int] = []
    session = configured_spot_session()

    def load() -> ConfiguredPaperSession:
        worker_threads.append(threading.get_ident())
        return session

    workflow, thread_pool = _workflow(create_session=_unused_create, load_active=load)
    snapshots: list[TradingWorkspaceSnapshot] = []
    workflow.workspace_changed.connect(snapshots.append)

    workflow.start()

    qtbot.waitUntil(lambda: [item.read_state for item in snapshots] == [
        WorkspaceReadState.LOADING,
        WorkspaceReadState.READY,
    ])
    assert worker_threads[0] != caller_thread
    assert thread_pool.waitForDone(1_000)


def test_refresh_failure_preserves_last_known_snapshot(qtbot: QtBot) -> None:
    session = configured_spot_session()
    calls = 0

    def load() -> ConfiguredPaperSession:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("SQLite failed at /private/tmp/tiewtrade.sqlite3")
        return session

    workflow, thread_pool = _workflow(create_session=_unused_create, load_active=load)
    snapshots: list[TradingWorkspaceSnapshot] = []
    workflow.workspace_changed.connect(snapshots.append)

    workflow.start()
    qtbot.waitUntil(lambda: snapshots[-1].read_state is WorkspaceReadState.READY)
    ready = snapshots[-1]
    workflow.start()
    qtbot.waitUntil(lambda: snapshots[-1].read_state is WorkspaceReadState.ERROR)
    failed = snapshots[-1]

    assert failed.header == ready.header
    assert failed.orders == ready.orders
    assert failed.basket == ready.basket
    assert failed.data_as_of_utc == ready.data_as_of_utc
    assert failed.message == "Paper Session could not be loaded"
    assert "private/tmp" not in failed.message
    assert thread_pool.waitForDone(1_000)


def test_close_discards_late_workspace_generation(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()

    def delayed_load() -> ConfiguredPaperSession:
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return configured_spot_session()

    workflow, thread_pool = _workflow(
        create_session=_unused_create,
        load_active=delayed_load,
    )
    snapshots: list[TradingWorkspaceSnapshot] = []
    workflow.workspace_changed.connect(snapshots.append)

    workflow.start()
    qtbot.waitUntil(started.is_set)
    workflow.close()
    release.set()

    assert thread_pool.waitForDone(1_000)
    QCoreApplication.processEvents()
    assert [item.read_state for item in snapshots] == [WorkspaceReadState.LOADING]
```

- [ ] **Step 2: รัน focused tests เพื่อยืนยัน RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest tests/unit/ui/test_session_workflow.py -q
```

Expected: FAIL เพราะ `SessionWorkflow` ยังไม่มี `workspace_changed` และยังไม่ publish snapshot

- [ ] **Step 3: Publish snapshots ผ่าน refresh seam เดิม**

แก้ `SessionWorkflow` ดังนี้:

```python
workspace_changed = Signal(object)

def __init__(
    self,
    *,
    create_session: CreateSession,
    load_active: LoadActiveSession,
    thread_pool: QThreadPool | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    parent: QObject | None = None,
) -> None:
    super().__init__(parent)
    self._create_session = create_session
    self._load_active = load_active
    self._thread_pool = thread_pool or QThreadPool.globalInstance()
    self._clock = clock
    self._last_known_workspace: TradingWorkspaceSnapshot | None = None
    self._active_task: BackgroundTask | None = None
    self._active_operation: _Operation | None = None
    self._active_generation: int | None = None
    self._callback_generation = 0
    self._closed = False

def _publish_workspace(self, snapshot: TradingWorkspaceSnapshot) -> None:
    if snapshot.read_state in {
        WorkspaceReadState.EMPTY,
        WorkspaceReadState.READY,
        WorkspaceReadState.STALE,
    }:
        self._last_known_workspace = snapshot
    self.workspace_changed.emit(snapshot)
```

กติกาการ publish:

- เริ่ม `_Operation.LOAD` ให้ emit `loading_workspace_snapshot(self._last_known_workspace)` ก่อนส่ง `BackgroundTask` เข้า thread pool
- load `None` ให้ emit `empty_workspace_snapshot(observed_at_utc=self._clock())` ก่อน `setup_required`
- load/create สำเร็จให้ emit `configured_workspace_snapshot(session, observed_at_utc=self._clock())` ก่อน `session_ready`
- load/create storage หรือ unknown failure ให้ emit `failed_workspace_snapshot(self._last_known_workspace, sanitized_message)` และใช้ sanitized message เดียวกับ `unavailable`
- validation failure ไม่เปลี่ยน durable workspace snapshot
- callback ที่ `_callbacks_are_current()` เป็น false ห้าม publish snapshot
- ห้ามย้าย persistence operation ออกจาก `BackgroundTask`

- [ ] **Step 4: รัน workflow tests และ background-task tests เพื่อยืนยัน GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest tests/unit/ui/test_session_workflow.py tests/unit/ui/test_background_task.py -q
```

Expected: PASS

- [ ] **Step 5: รัน full suite ก่อน commit ตาม implementer contract**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest -q
```

Expected: PASS

- [ ] **Step 6: Commit Task 2**

```bash
git add src/tiewtrade/ui/session_workflow.py tests/unit/ui/test_session_workflow.py
git commit -m "feat: publish workspace refresh snapshots"
```

## Task 3: Persistent Status Header Integration

**Files:**
- Modify: `src/tiewtrade/ui/trading_workspace.py`
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `tests/unit/ui/test_trading_workspace.py`
- Modify: `tests/unit/ui/test_main_window.py`
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: `TradingWorkspaceSnapshot` และ `SessionWorkflow.workspace_changed`
- Produces: `TradingWorkspace.show_workspace_snapshot(snapshot)` ซึ่งเป็น interface เดียวสำหรับ Persistent Status Header

- [ ] **Step 1: เขียน failing UI tests สำหรับ snapshot-only header rendering**

เพิ่ม tests ให้ครอบคลุม:

```python
def test_snapshot_updates_all_persistent_header_facts(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    snapshot = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    workspace.show_workspace_snapshot(snapshot)

    assert workspace.header_symbol.text() == "BTCUSDT"
    assert workspace.header_timeframe.text() == "5m"
    assert workspace.header_mode.text() == "Paper"
    assert workspace.header_market_type.text() == "Spot"
    assert workspace.header_preset.text() == "RSI Step Grid v1"
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.header_freshness.text() == "Market data not started"
    assert workspace.header_read_state.text() == "Ready"


def test_error_and_stale_snapshots_keep_header_facts_visible(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    ready = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    expected_facts = ("BTCUSDT", "5m", "Paper", "Spot", "RSI Step Grid v1")

    for snapshot, read_state in (
        (failed_workspace_snapshot(ready, "Workspace data is unavailable"), "Error"),
        (stale_workspace_snapshot(ready), "Stale"),
    ):
        workspace.show_workspace_snapshot(snapshot)
        assert (
            workspace.header_symbol.text(),
            workspace.header_timeframe.text(),
            workspace.header_mode.text(),
            workspace.header_market_type.text(),
            workspace.header_preset.text(),
        ) == expected_facts
        assert workspace.header_read_state.text() == read_state


def test_ui_modules_do_not_import_prohibited_adapters() -> None:
    ui_source = "\n".join(path.read_text() for path in Path("src/tiewtrade/ui").glob("*.py"))
    for prohibited in (
        "tiewtrade.integrations.sqlite",
        "tiewtrade.strategies",
        "binance",
        "tiewtrade.execution",
    ):
        assert prohibited not in ui_source
```

เพิ่ม MainWindow test โดยใช้ delayed `load_active` ที่บันทึก worker thread ID แล้ว assert ตามลำดับว่า Header แสดง `Loading`, ต่อด้วย `Ready`/`Empty`; จากนั้นให้ create สำเร็จและ assert `Configured`. สำหรับ failure path ให้ load สำเร็จหนึ่งครั้งก่อน retry ที่ raise private-path error แล้ว assert Header facts เดิมยังอยู่และ `header_read_state` เป็น `Error`.

- [ ] **Step 2: รัน UI tests เพื่อยืนยัน RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py -q
```

Expected: FAIL เพราะ `show_workspace_snapshot`, `header_market_type` และ `header_read_state` ยังไม่มี

- [ ] **Step 3: Render Header จาก immutable snapshot เท่านั้น**

ใน `TradingWorkspace`:

```python
@Slot(object)
def show_workspace_snapshot(self, value: object) -> None:
    if not isinstance(value, TradingWorkspaceSnapshot):
        return
    self._show_header(value)
    self._show_placeholder_states(value)
```

เพิ่ม `header_market_type` และ `header_read_state` ใน persistent header. ใช้ explicit mapping dictionaries สำหรับ `BotRuntimeState`, `DataFreshness` และ `WorkspaceReadState`; ห้าม derive business decisions หรือใช้ `float`. เมื่อ snapshot มี Header ให้ render exact Symbol, Timeframe, Trade Mode, Market Type และ Preset. เมื่อ snapshot เป็น Loading/Error/Stale ที่มี last-known Header ให้คง facts เดิมและเปลี่ยนเฉพาะ read-state/freshness semantic text. เมื่อ EMPTY ให้แสดง `No Session` และ honest empty states.

ลบการเขียน Header ออกจาก `show_setup()`, `show_configured_session()` และ `show_unavailable()` เพื่อให้ snapshot เป็น interface เดียว; method เหล่านี้ยังเปลี่ยน Bot Control page ตาม responsibility เดิม.

- [ ] **Step 4: Wire MainWindow และ acceptance flow**

เชื่อม signal เพียงบรรทัดเดียวใน composition:

```python
self._workflow.workspace_changed.connect(self.workspace.show_workspace_snapshot)
```

อัปเดต existing tests ที่เรียก `show_configured_session()` โดยตรงให้ apply configured snapshot แยกก่อนตรวจ Header. เพิ่ม acceptance assertion ว่า create และ restart แสดง `BTCUSDT`, selected timeframe, `Paper`, market type, `Configured`, `Market data not started` และ `Ready` โดยไม่เริ่ม Runtime.

เพิ่มสถานะใน `PROJECT_PLAN.md` ว่า DEV-133 ส่งมอบ immutable Workspace read model, exact Decimal/UTC contracts, background generation-safe refresh และ persistent header แล้ว แต่ Bot lifecycle controls, durable Orders/Basket integration, Runtime Start/Stop/Recovery, Notifications และ Chart ยังอยู่ใน Sub-issues ถัดไป.

- [ ] **Step 5: รัน focused และ acceptance tests เพื่อยืนยัน GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest tests/unit/application/test_trading_workspace.py tests/unit/ui/test_session_workflow.py tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py -q
```

Expected: PASS

- [ ] **Step 6: รัน repository quality gates**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m pytest -q
PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m ruff check src tests
PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src /Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check 3988098 HEAD
```

Expected: PASS ทุกคำสั่ง

- [ ] **Step 7: Commit Task 3 และ plan/status docs**

```bash
git add src/tiewtrade/ui/trading_workspace.py src/tiewtrade/ui/main_window.py tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py PROJECT_PLAN.md docs/superpowers/plans/2026-08-01-dev-133-trading-workspace-read-model.md
git commit -m "feat: render persistent workspace status header"
```
