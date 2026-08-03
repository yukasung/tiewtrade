# DEV-139 Responsive, Accessibility และ Paper Workspace Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ปิด Integration Gate ของ Unified Trading Workspace ด้วย accessibility fixes ที่ตรวจพบและ deterministic acceptance coverage สำหรับ responsive layout, Paper Spot/Futures lifecycle, restart/recovery และ presentation failure isolation

**Architecture:** รักษา `ui` เป็น presentation owner โดยเพิ่ม accessible metadata และ focus styling ที่ widget/theme seam เท่านั้น ส่วน end-to-end flow ใช้ `MainWindow` ผ่าน application use cases, temporary SQLite และ fake/public candle source เดิม ไม่เพิ่ม business rule หรือ adapter ใหม่ ชุดทดสอบแยก widget contracts ออกจาก lifecycle acceptance เพื่อให้ failure ระบุเจ้าของได้ชัดเจน

**Tech Stack:** Python 3.12+, PySide6, pytest, pytest-qt, SQLite, Ruff, Mypy, npm docs checks

## Global Constraints

- สนทนา เอกสาร และ Linear updates ใช้ภาษาไทย; identifiers และ code comments ใช้ภาษาอังกฤษ
- ใช้ Paper Trading, temporary SQLite และ fake/public adapters เท่านั้น
- ห้ามใช้ Live credentials, Binance Private API, Testnet หรือเงินจริง
- UI ไม่ import SQLite, Strategy หรือ Execution adapter และไม่ถือ business rules
- `Create Session` ต้องไม่เริ่ม Runtime; recovery ต้อง fail closed
- ใช้ `QT_QPA_PLATFORM=offscreen PYTHONPATH=src` สำหรับ Qt tests ใน local checkout นี้ เพราะ editable install ปัจจุบันชี้ไป worktree เก่า
- ก่อนเริ่ม Task 1 ให้ย้ายเฉพาะ `DEV-139` เป็น `In Progress`

---

### Task 1: เติม Accessible Names และ Visible Table Focus

**Files:**
- Modify: `tests/unit/ui/test_session_setup.py`
- Modify: `tests/unit/ui/test_theme.py`
- Modify: `src/tiewtrade/ui/session_setup.py`
- Modify: `src/tiewtrade/ui/theme.py`

**Interfaces:**
- Consumes: `SessionSetupWidget` controls และ `DARK_THEME`
- Produces: explicit accessible names สำหรับ Session configuration/action controls และ focus border สำหรับ `QTableWidget`

- [ ] **Step 1: เขียน failing tests สำหรับ accessible names**

เพิ่ม test นี้ใน `tests/unit/ui/test_session_setup.py`:

```python
def test_configuration_controls_have_explicit_accessible_names(qtbot: QtBot) -> None:
    form = SessionSetupWidget()
    qtbot.addWidget(form)

    assert form.market_type.accessibleName() == "Market Type"
    assert form.symbol_field.accessibleName() == "Symbol"
    assert form.timeframe.accessibleName() == "Timeframe"
    assert form.available_capital.accessibleName() == "Available Capital (USDT)"
    assert form.max_entries.accessibleName() == "Maximum Entries"
    assert form.spot_ratio.accessibleName() == "Spot Trading Capital (%)"
    assert form.leverage.accessibleName() == "Futures Leverage"
    assert form.advanced_toggle.accessibleName() == "Advanced Execution Costs"
    assert form.fee_percent.accessibleName() == "Trading Fee (%)"
    assert form.slippage_bps.accessibleName() == "Slippage (bps)"
    assert form.create_button.accessibleName() == "Create Paper Session"
```

เพิ่ม assertion ใน `test_dark_theme_defines_focus_and_semantic_states`:

```python
assert "QTableWidget:focus" in DARK_THEME
assert "border: 2px solid #2f81f7" in DARK_THEME
```

- [ ] **Step 2: รัน test เพื่อยืนยัน RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/ui/test_session_setup.py::test_configuration_controls_have_explicit_accessible_names \
  tests/unit/ui/test_theme.py::test_dark_theme_defines_focus_and_semantic_states -q
```

Expected: FAIL เพราะ Session Setup controls มี accessible name ว่าง และ theme ยังไม่มีกฎ `QTableWidget:focus`

- [ ] **Step 3: เพิ่ม accessible metadata แบบ explicit**

ใน `SessionSetupWidget.__init__` หลังสร้าง control ทั้งหมด ให้กำหนด:

```python
self.market_type.setAccessibleName("Market Type")
self.symbol_field.setAccessibleName("Symbol")
self.timeframe.setAccessibleName("Timeframe")
self.available_capital.setAccessibleName("Available Capital (USDT)")
self.max_entries.setAccessibleName("Maximum Entries")
self.spot_ratio.setAccessibleName("Spot Trading Capital (%)")
self.leverage.setAccessibleName("Futures Leverage")
self.advanced_toggle.setAccessibleName("Advanced Execution Costs")
self.fee_percent.setAccessibleName("Trading Fee (%)")
self.slippage_bps.setAccessibleName("Slippage (bps)")
self.create_button.setAccessibleName("Create Paper Session")
```

ใน `DARK_THEME` เพิ่ม focus rule ที่ใช้ primary color เดิม:

```css
QTableWidget:focus {
    border: 2px solid #2f81f7;
}
```

- [ ] **Step 4: รัน focused tests เพื่อยืนยัน GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/ui/test_session_setup.py tests/unit/ui/test_theme.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tiewtrade/ui/session_setup.py src/tiewtrade/ui/theme.py \
  tests/unit/ui/test_session_setup.py tests/unit/ui/test_theme.py
git commit -m "fix: expose workspace controls to keyboard users"
```

### Task 2: พิสูจน์ Responsive, Keyboard และ Horizontal Table Contracts

**Files:**
- Create: `tests/acceptance/test_workspace_responsive_accessibility.py`

**Interfaces:**
- Consumes: `TradingWorkspace`, `BOT_CONTROL_BREAKPOINT`, `NotificationStore`, `TradeHistoryPage`
- Produces: acceptance proof ที่ boundary `1200/1199`, focus restoration และ scrollbar contract ของทุก trading table

- [ ] **Step 1: สร้าง responsive/accessibility acceptance file**

สร้าง `tests/acceptance/test_workspace_responsive_accessibility.py` โดยมี 3 tests:

```python
from dataclasses import replace
from datetime import UTC, datetime

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.qt_interactions import click
from tiewtrade.application.bot_control import BotLifecycleResult
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    configured_workspace_snapshot,
)
from tiewtrade.ui.notification_center import NotificationStore
from tiewtrade.ui.trading_workspace import TradingWorkspace


def test_breakpoint_reuses_bot_control_and_restores_keyboard_focus(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.show_configured_session(configured_spot_session())
    original_control = workspace.bot_control_widget

    workspace.resize(1200, 700)
    workspace.show()
    qtbot.waitUntil(lambda: not workspace.compact_mode)
    assert workspace.bot_control.isVisible()
    assert not workspace.bot_control_button.isVisible()

    workspace.resize(1199, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    assert workspace.bot_control_widget is original_control
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.bot_control_button.isVisible()

    click(workspace.bot_control_button)
    qtbot.waitUntil(workspace.bot_control.isVisible)
    assert workspace.bot_control_close_button.hasFocus()
    QTest.keyClick(workspace.bot_control_close_button, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not workspace.bot_control.isVisible())
    assert workspace.bot_control_button.hasFocus()


def test_notification_drawer_exposes_text_severity_and_keyboard_focus(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1199, 700)
    workspace.show()
    snapshot = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 3, 9, tzinfo=UTC),
    )
    assert snapshot.header is not None
    blocked = replace(
        snapshot,
        header=replace(snapshot.header, runtime_state=BotRuntimeState.BLOCKED),
    )
    store = NotificationStore()
    store.publish(
        BotLifecycleResult(
            workspace=blocked,
            blocked_reason="Paper Bot recovery required",
        ),
        occurred_at_utc=datetime(2026, 8, 3, 9, tzinfo=UTC),
    )
    workspace.show_workspace_snapshot(blocked)
    workspace.show_notifications(store)

    click(workspace.notification_button)
    qtbot.waitUntil(workspace.notification_drawer.isVisible)
    assert workspace.notification_close_button.hasFocus()
    assert "Critical" in workspace.notification_rows[0].text()
    assert workspace.header_runtime.text() == "Blocked"
    click(workspace.notification_close_button)
    assert workspace.notification_button.hasFocus()


def test_trading_tables_are_named_and_scroll_horizontally(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(760, 700)
    workspace.show()

    tables = (
        workspace.open_orders.table,
        workspace.position_basket.table,
        workspace.trade_history.basket_table,
        workspace.trade_history.fill_table,
    )
    for table in tables:
        assert table.accessibleName()
        assert (
            table.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        for column in range(table.columnCount()):
            table.setColumnWidth(column, 180)
        table.resize(360, 180)
        table.show()
        qtbot.waitUntil(lambda table=table: table.horizontalScrollBar().maximum() > 0)
```

- [ ] **Step 2: รัน acceptance test และ related unit tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest \
  tests/acceptance/test_workspace_responsive_accessibility.py \
  tests/unit/ui/test_trading_workspace.py \
  tests/unit/ui/test_trade_history_page.py -q
```

Expected: PASS; test นี้เป็น acceptance proof ของ behavior ที่ sub-issues ก่อนหน้าส่งมอบแล้ว จึงไม่เพิ่ม production abstraction หรือ duplicate implementation

- [ ] **Step 3: Commit**

```bash
git add tests/acceptance/test_workspace_responsive_accessibility.py
git commit -m "test: prove responsive workspace accessibility"
```

### Task 3: เชื่อม Create เข้ากับ Paper Spot/Futures Runtime Acceptance

**Files:**
- Modify: `tests/acceptance/test_desktop_session_setup.py`

**Interfaces:**
- Consumes: `CreatePaperSession`, `SQLiteActivePaperSessions`, `PaperRuntimeController`, `_AcceptancePublicCandleSource`
- Produces: parameterized `Create -> Start -> trade update -> Stop` proof สำหรับ Spot และ Futures ผ่าน `MainWindow`

- [ ] **Step 1: เปลี่ยน real runtime test ให้เริ่มจาก No Session**

ใน `test_desktop_real_paper_runtime_starts_once_and_stops_without_closing_basket`:

- ลบการ pre-create `session` ก่อนสร้าง `MainWindow`
- สร้าง `CreatePaperSession(create_active=active_sessions.create)` และส่ง `create_session=create_use_case.execute`
- ให้ `load_active=active_sessions.get_active` คืน `None` ตอนเปิดหน้าต่างครั้งแรก
- ใช้ `_enter_form_values(window, case)` แล้ว click `window.setup.create_button`
- รอ `window.overview.isVisible()` และอ่าน `session = active_sessions.get_active()`
- ยืนยัน Header เป็น `Configured`, source ยังไม่มี `load_recent_calls` และ lifecycle marker ยังไม่เป็น Running
- จากนั้น click `Start Bot` เพียงครั้งเดียวและใช้ assertions เดิมสำหรับ completed-candle trade update, Position / Basket, endpoint selection และ Stop

callback ต้องใช้ `snapshot.session` เป็น authoritative configuration แทนการ capture session ที่สร้างก่อน UI:

```python
def initialize_bot(snapshot: BotControlSnapshot) -> BotLifecycleResult:
    startup_controller = PaperRuntimeController(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=history,
        symbol_rules=_acceptance_symbol_rules(snapshot.session.market_data.symbol),
        source_factory=lambda _endpoints: pytest.fail(
            "clean startup inspection must not contact public market data"
        ),
        snapshot_callback=lambda _snapshot: None,
        clock=lambda: _RUNTIME_NOW,
    )
    return _paper_runtime_result_for_ui(
        snapshot,
        startup_controller.inspect_startup(snapshot.session),
    )
```

ใน `start_bot` ให้สร้าง candles/source จาก `snapshot.session.market_data` แล้วเก็บ source
ใน local holder เพื่อ assert หลัง Runtime เริ่ม

- [ ] **Step 2: รัน parameterized acceptance test**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest \
  tests/acceptance/test_desktop_session_setup.py::test_desktop_real_paper_runtime_starts_once_and_stops_without_closing_basket -q
```

Expected: 2 passed (`spot`, `futures`)

- [ ] **Step 3: รัน desktop session acceptance file**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest \
  tests/acceptance/test_desktop_session_setup.py -q
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/acceptance/test_desktop_session_setup.py
git commit -m "test: cover full paper workspace lifecycle"
```

### Task 4: พิสูจน์ Restart/Recovery และ Presentation Failure Isolation

**Files:**
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `tests/acceptance/test_desktop_chart.py`
- Modify: `tests/acceptance/test_notification_safety_feedback.py`

**Interfaces:**
- Consumes: `PaperRuntimeController.inspect_startup/recover`, `ChartWorkflow`, `TradingWorkspace.show_notifications`
- Produces: acceptance proof ว่า recovery fail closed และ Chart/Notification failures ไม่เปลี่ยน Runtime หรือ durable Trade History

- [ ] **Step 1: ขยาย restart/recovery scenario**

ใน `test_desktop_restart_blocks_interrupted_runtime_until_recovery` เพิ่ม assertions ก่อน recovery:

```python
window.workspace.tabs.setCurrentWidget(window.trade_history)
qtbot.waitUntil(lambda: window.trade_history.basket_state.text() == "No trade history")
assert window.workspace.header_runtime.text() == "Blocked"
assert not window.workspace.bot_control_widget.start_button.isVisible()
```

click recovery สองครั้งติดกัน แล้วคง assertion `recover_calls == 1` เพื่อพิสูจน์ duplicate guard
จากนั้นยืนยัน durable marker เป็น `STOPPED` และ Trade History ยังเปิดอยู่

- [ ] **Step 2: เพิ่ม Chart failure acceptance ขณะ Runtime Running**

เพิ่ม test ใน `tests/acceptance/test_desktop_chart.py` ที่ใช้ fake `start_bot` คืน
`BotRuntimeState.RUNNING`, ให้ `load_chart` raise `RuntimeError`, แล้ว assert:

```python
qtbot.waitUntil(
    lambda: window.workspace.chart._snapshot is not None
    and window.workspace.chart._snapshot.state is ChartReadState.UNAVAILABLE
)
click(window.workspace.bot_control_widget.start_button)
qtbot.waitUntil(lambda: window.workspace.header_runtime.text() == "Running")
window.workspace.tabs.setCurrentWidget(window.trade_history)
qtbot.waitUntil(lambda: window.trade_history.basket_state.text() == "No trade history")
assert window.workspace.chart.retry_button.isVisible()
assert window.workspace.bot_control_widget.stop_button.isEnabled()
```

ข้อความ raw exception ต้องไม่ปรากฏใน Chart หรือ Workspace labels

- [ ] **Step 3: เพิ่ม rejected Notification presentation acceptance**

ใน `tests/acceptance/test_notification_safety_feedback.py` เพิ่ม test ที่ทำให้ Workspace
อยู่ใน Running state, capture header/table state, เรียก `show_notifications(object())`
และ assert ว่า Runtime, Position / Basket, Open Orders และ Trade History ไม่เปลี่ยน
รวมทั้ง UI ยังเปิด/ปิด Bot Control drawer ได้

- [ ] **Step 4: รัน failure-boundary acceptance tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest \
  tests/acceptance/test_desktop_session_setup.py::test_desktop_restart_blocks_interrupted_runtime_until_recovery \
  tests/acceptance/test_desktop_chart.py \
  tests/acceptance/test_notification_safety_feedback.py -q
```

Expected: PASS และไม่มี network/private API call

- [ ] **Step 5: Commit**

```bash
git add tests/acceptance/test_desktop_session_setup.py \
  tests/acceptance/test_desktop_chart.py \
  tests/acceptance/test_notification_safety_feedback.py
git commit -m "test: verify workspace recovery isolation"
```

### Task 5: Repository Verification, Code Review และ Issue Completion

**Files:**
- Verify: `src/`, `tests/`, `docs-site/`
- Review: committed range `main..HEAD`

**Interfaces:**
- Consumes: งานจาก Tasks 1-4 และ Source of Truth ของ `DEV-139`
- Produces: fresh verification evidence, reviewed diff และ Linear state `Done`

- [ ] **Step 1: รัน related UI/acceptance suite**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/ui \
  tests/acceptance/test_workspace_responsive_accessibility.py \
  tests/acceptance/test_desktop_session_setup.py \
  tests/acceptance/test_desktop_chart.py \
  tests/acceptance/test_notification_safety_feedback.py \
  tests/acceptance/test_desktop_trade_history.py
```

Expected: PASS

- [ ] **Step 2: รัน repository quality gates**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m ruff check src tests
PYTHONPATH=src .venv/bin/python -m ruff format --check src tests
PYTHONPATH=src .venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main HEAD
```

Expected: ทุก command exit `0`

- [ ] **Step 3: ตรวจ safety/dependency assertions**

Run:

```bash
rg -n "api[_-]?key|secret|private.*api|live.*order|testnet" \
  tests/acceptance/test_workspace_responsive_accessibility.py \
  tests/acceptance/test_desktop_session_setup.py \
  tests/acceptance/test_desktop_chart.py \
  tests/acceptance/test_notification_safety_feedback.py
```

Expected: พบเฉพาะข้อความ assertion/forbidden-prefix ที่พิสูจน์การห้ามใช้ ไม่มี credential value, private transport หรือ Live order setup

- [ ] **Step 4: ใช้ `code-review` ตรวจ committed range**

Review `git diff main...HEAD` ทั้ง correctness และ architecture โดยยืนยัน acceptance criteria ทีละข้อ แก้ finding ที่ actionable ด้วย TDD และรัน quality gates ซ้ำหลังการแก้

- [ ] **Step 5: ตรวจ final diff และ commit fixes จาก review**

```bash
git status --short --branch
git diff --check main HEAD
git log --oneline main..HEAD
```

Expected: working tree clean, diff check ผ่าน และ commits แยกตาม responsibility

- [ ] **Step 6: อัปเดต Linear**

ย้าย `DEV-139` เป็น `Done` เฉพาะเมื่อ verification และ review ผ่านจริง พร้อม comment ภาษาไทยสรุป:

- responsive/accessibility contracts ที่พิสูจน์แล้ว
- Paper Spot/Futures lifecycle และ restart/recovery evidence
- Chart/Notification failure isolation
- ผล unit, integration, UI, acceptance, Ruff, format, Mypy, docs และ diff checks
- ยืนยันว่าไม่มี Live credentials, Binance Private API หรือเงินจริง
