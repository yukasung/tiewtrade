# Unified Trading Workspace Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เปลี่ยน Desktop UI เดิมให้เป็น Unified Trading Workspace แบบ Full Dark Theme โดยคง Session Setup, Session Overview และ Trade History behavior เดิมไว้ครบ พร้อม responsive Bot Control drawer และ honest placeholders สำหรับ Chart, Open Orders และ Position / Basket

**Architecture:** `MainWindow` ยังคงเป็น composition/wiring owner ของ UI workflows แต่ย้าย layout responsibility ไปยัง focused `TradingWorkspace`. Existing Session และ Trade History widgets ถูกนำมาประกอบใหม่โดยไม่เปลี่ยน application contracts หรือเรียก SQLite/Runtime จาก UI. Slice นี้เป็น delivery slice แรกของ `Unified Trading Workspace Design`; Runtime read model, Start/Stop/Recovery, Notifications และ Chart จริงจะมี implementation plan แยกใน Sub-issues ถัดไป

**Tech Stack:** Python 3.12, PySide6 6.10, pytest, pytest-qt, Ruff, Mypy strict

## Global Constraints

- UI copy ใช้ภาษาอังกฤษ ส่วนเอกสารและ Linear ใช้ภาษาไทย
- Full Dark Theme ใช้ App Background `#0B0E11`, Primary Surface `#141A22`, Raised Surface `#1B2430`, Subtle Border `#2B3441`, Primary Text `#F1F5F9` และ Secondary Text `#94A3B8`
- TiewTrade Blue เป็น primary action; `#0ECB81` และ `#F6465D` ใช้เฉพาะ semantic positive/negative state; `#F0B90B` ใช้ warning/Paper state
- หนึ่ง Active Bot Session ต่อ installation และไม่มี Manual Buy/Sell
- `Create Paper Session` บันทึก immutable configuration เท่านั้นและไม่เริ่ม Market Data, Strategy หรือ Execution
- Trade History เปิดดูได้แม้ไม่มี Active Paper Session
- UI ห้าม import SQLite, Strategy, Binance SDK หรือ Execution adapter
- Network, persistence และ application work ต้องไม่ block UI thread
- Slice นี้ใช้ Paper/Fake adapters เท่านั้นและห้ามเรียก Binance Private API
- Bot Control แสดงด้านขวาที่ความกว้างตั้งแต่ 1,200 px และเป็น drawer เมื่อแคบกว่า 1,200 px
- หน้าต่างขั้นต่ำ 1,024 × 700 px
- Chart, Open Orders และ Position / Basket ใน slice นี้ต้องแสดง honest empty/placeholder state และห้ามสร้างข้อมูลจำลอง

---

## File Structure

- Create `src/tiewtrade/ui/trading_workspace.py` — เป็นเจ้าของ persistent header, Chart placeholder, bottom tabs, Bot Control panel และ responsive drawer behavior
- Modify `src/tiewtrade/ui/main_window.py` — เหลือ composition/wiring ของ existing workflows กับ `TradingWorkspace`
- Modify `src/tiewtrade/ui/theme.py` — เปลี่ยน stylesheet export เป็น `DARK_THEME` และกำหนด semantic object-name styles
- Modify `src/tiewtrade/ui/desktop.py` — apply `DARK_THEME`
- Create `tests/unit/ui/test_theme.py` — ล็อก dark palette และห้าม light background เดิมกลับมา
- Create `tests/unit/ui/test_trading_workspace.py` — ทดสอบ layout, header, tabs และ responsive Bot Control
- Modify `tests/unit/ui/test_main_window.py` — เปลี่ยน navigation assertions เป็น workspace/tab assertions โดยคง workflow/concurrency coverage เดิม
- Modify `tests/unit/test_desktop_main.py` — ตรวจ composition signature เดิมและ theme export ใหม่
- Modify `tests/acceptance/test_desktop_session_setup.py` — พิสูจน์ create/restart restore ผ่าน Bot Control
- Modify `tests/acceptance/test_desktop_trade_history.py` — พิสูจน์ Trade History tab เปิดได้ทุก Session state

## Task 1: Full Dark Theme Contract

**Files:**
- Create: `tests/unit/ui/test_theme.py`
- Modify: `src/tiewtrade/ui/theme.py`
- Modify: `src/tiewtrade/ui/desktop.py`
- Test: `tests/unit/ui/test_theme.py`
- Test: `tests/unit/test_desktop_main.py`

**Interfaces:**
- Consumes: Qt object names ที่มีอยู่ใน Session Setup, Session Overview และ Trade History
- Produces: `tiewtrade.ui.theme.DARK_THEME: str`

- [ ] **Step 1: เขียน failing test สำหรับ semantic dark palette**

```python
from tiewtrade.ui.theme import DARK_THEME


def test_dark_theme_uses_approved_workspace_palette() -> None:
    for color in (
        "#0B0E11",
        "#141A22",
        "#1B2430",
        "#2B3441",
        "#F1F5F9",
        "#94A3B8",
        "#0ECB81",
        "#F6465D",
        "#F0B90B",
    ):
        assert color in DARK_THEME

    assert "background: #F4F7FB;" not in DARK_THEME
    assert "background: #FFFFFF;" not in DARK_THEME


def test_dark_theme_defines_focus_and_semantic_states() -> None:
    assert 'QWidget[state="positive"]' in DARK_THEME
    assert 'QWidget[state="negative"]' in DARK_THEME
    assert 'QWidget[state="warning"]' in DARK_THEME
    assert "QPushButton:focus" in DARK_THEME
```

- [ ] **Step 2: รัน test เพื่อยืนยันว่า fail เพราะยังไม่มี `DARK_THEME`**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_theme.py -q
```

Expected: FAIL ระหว่าง import เพราะ `theme.py` ยัง export `LIGHT_THEME`

- [ ] **Step 3: เปลี่ยน stylesheet เป็น dark semantic theme**

แทน `LIGHT_THEME` ด้วย `DARK_THEME` และครอบ selectors ที่ existing widgets ใช้อยู่รวมทั้ง selectors ของ Workspace ใหม่:

```python
DARK_THEME = """
QMainWindow, QWidget#workspace, QWidget#workspaceContent {
    background: #0B0E11;
    color: #F1F5F9;
    font-family: "Inter", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 14px;
}
QFrame#workspaceHeader, QFrame#botControl, QFrame#card,
QFrame#statusCard, QFrame#filterCard, QFrame#emptyPanel {
    background: #141A22;
    border: 1px solid #2B3441;
    border-radius: 8px;
}
QFrame#chartPlaceholder {
    background: #10151C;
    border: 1px solid #2B3441;
    border-radius: 8px;
}
QLabel#brand, QLabel#pageTitle, QLabel#sectionTitle,
QLabel#detailValue, QLabel#readOnlyValue, QLabel#stateValue {
    color: #F1F5F9;
}
QLabel#brand {
    color: #4C7DFF;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#pageTitle {
    font-size: 24px;
    font-weight: 700;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 650;
}
QLabel#supportingText, QLabel#detailLabel, QLabel#filterLabel,
QLabel#summaryLabel, QLabel#pageLabel, QLabel[stateMessage="true"] {
    color: #94A3B8;
}
QLabel#environmentBadge, QWidget[state="warning"] {
    background: #2A2412;
    color: #F0B90B;
    border-radius: 6px;
}
QWidget[state="positive"] { color: #0ECB81; }
QWidget[state="negative"] { color: #F6465D; }
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background: #1B2430;
    border: 1px solid #3A4656;
    border-radius: 6px;
    color: #F1F5F9;
    min-height: 36px;
    padding: 0 10px;
    selection-background-color: #315CF4;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
QPushButton:focus, QTabBar::tab:focus {
    border: 2px solid #4C7DFF;
}
QLineEdit:read-only, QComboBox:disabled, QDateEdit:disabled {
    background: #151C25;
    color: #94A3B8;
}
QPushButton#primaryButton {
    background: #315CF4;
    border: 0;
    border-radius: 6px;
    color: #F8FAFC;
    font-weight: 650;
    min-height: 38px;
    padding: 0 18px;
}
QPushButton#primaryButton:hover { background: #416DFF; }
QPushButton#primaryButton:disabled {
    background: #26334D;
    color: #6F7D93;
}
QPushButton#secondaryButton, QPushButton[retryButton="true"] {
    background: #1B2430;
    border: 1px solid #3A4656;
    border-radius: 6px;
    color: #F1F5F9;
    min-height: 36px;
    padding: 0 14px;
}
QPushButton#secondaryButton:hover, QPushButton[retryButton="true"]:hover {
    background: #243044;
    border-color: #4C7DFF;
}
QPushButton#destructiveButton {
    background: #F6465D;
    border: 0;
    border-radius: 6px;
    color: #FFFFFF;
    min-height: 38px;
    padding: 0 18px;
}
QPushButton#advancedButton {
    background: transparent;
    border: 0;
    color: #6E97FF;
    font-weight: 600;
    text-align: left;
}
QTabWidget::pane {
    background: #141A22;
    border: 1px solid #2B3441;
}
QTabBar::tab {
    background: #0B0E11;
    color: #94A3B8;
    min-height: 36px;
    padding: 0 16px;
}
QTabBar::tab:selected {
    color: #F1F5F9;
    border-bottom: 2px solid #4C7DFF;
}
QTableWidget {
    alternate-background-color: #111821;
    background: #141A22;
    border: 0;
    color: #F1F5F9;
    gridline-color: #2B3441;
    selection-background-color: #22355F;
    selection-color: #F8FAFC;
}
QTableWidget::item { padding: 7px 8px; }
QHeaderView::section {
    background: #1B2430;
    border: 0;
    border-bottom: 1px solid #2B3441;
    color: #CBD5E1;
    font-weight: 650;
    padding: 8px;
}
QCheckBox { color: #CBD5E1; spacing: 7px; }
QCheckBox::indicator:checked {
    background: #315CF4;
    border: 1px solid #4C7DFF;
}
QLabel#fieldError, QLabel#filterError { color: #F6465D; }
QLabel#unavailableMessage {
    background: #2A1B20;
    border: 1px solid #71313D;
    border-radius: 6px;
    color: #FF9CAA;
    padding: 10px 12px;
}
"""
```

แก้ composition ให้ apply export ใหม่:

```python
from tiewtrade.ui.theme import DARK_THEME

# ...
window.setStyleSheet(DARK_THEME)
```

- [ ] **Step 4: รัน theme และ composition tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_theme.py tests/unit/test_desktop_main.py -q
```

Expected: PASS

- [ ] **Step 5: commit dark theme contract**

```bash
git add src/tiewtrade/ui/theme.py src/tiewtrade/ui/desktop.py tests/unit/ui/test_theme.py tests/unit/test_desktop_main.py
git commit -m "feat: add full dark desktop theme"
```

## Task 2: Unified Workspace Shell

**Files:**
- Create: `src/tiewtrade/ui/trading_workspace.py`
- Create: `tests/unit/ui/test_trading_workspace.py`

**Interfaces:**
- Consumes: `SessionSetupWidget`, `SessionOverviewWidget`, `TradeHistoryPage`, `ConfiguredPaperSession`
- Produces: `TradingWorkspace(QWidget)`, `TradingWorkspace.trade_history_activated`, `show_setup()`, `show_configured_session(session)`, `show_unavailable(message)`, `set_bot_busy(busy)`

- [ ] **Step 1: เขียน failing tests สำหรับหน้าเดียวและ honest placeholders**

```python
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.ui.trading_workspace import TradingWorkspace


def test_workspace_places_existing_features_in_one_screen(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    assert workspace.header_symbol.text() == "No Session"
    assert workspace.chart_state.text() == "Chart is not available yet"
    assert workspace.tabs.tabText(0) == "Open Orders"
    assert workspace.tabs.tabText(1) == "Position / Basket"
    assert workspace.tabs.tabText(2) == "Trade History"
    assert workspace.orders_state.text() == "No open orders"
    assert workspace.position_state.text() == "No open Position or Basket"
    assert workspace.setup.isVisible()


def test_configured_session_updates_header_and_bot_control(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    session = configured_spot_session()

    workspace.show_configured_session(session)

    assert workspace.header_symbol.text() == session.market_data.symbol
    assert workspace.header_timeframe.text() == session.market_data.timeframe
    assert workspace.header_mode.text() == "Paper · Spot"
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.header_freshness.text() == "Market data not started"
    assert workspace.overview.isVisible()


def test_trade_history_signal_is_emitted_when_tab_is_opened(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)

    with qtbot.waitSignal(workspace.trade_history_activated):
        workspace.tabs.setCurrentWidget(workspace.trade_history)
```

- [ ] **Step 2: รัน tests เพื่อยืนยันว่า fail เพราะยังไม่มี component**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py -q
```

Expected: FAIL ระหว่าง import `tiewtrade.ui.trading_workspace`

- [ ] **Step 3: สร้าง focused Workspace component**

ใช้ class shape ต่อไปนี้ โดยสร้าง existing widgets ภายในเพื่อให้ `MainWindow` wire ได้
โดยตรงและไม่สร้าง page framework:

```python
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.ui.preset_display import preset_display_name
from tiewtrade.ui.session_overview import SessionOverviewWidget
from tiewtrade.ui.session_setup import SessionSetupWidget
from tiewtrade.ui.trade_history_page import TradeHistoryPage


class TradingWorkspace(QWidget):
    trade_history_activated = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workspace")
        self.setup = SessionSetupWidget()
        self.overview = SessionOverviewWidget()
        self.trade_history = TradeHistoryPage()
        self.unavailable_panel = QFrame()
        self.unavailable_message = QLabel()
        self.unavailable_message.setObjectName("unavailableMessage")
        self.unavailable_message.setWordWrap(True)
        self.unavailable_retry_button = QPushButton("Try Again")
        self.unavailable_retry_button.setProperty("retryButton", True)
        self.header_symbol = QLabel("No Session")
        self.header_timeframe = QLabel("—")
        self.header_mode = QLabel("Paper")
        self.header_preset = QLabel("RSI Step Grid v1")
        self.header_runtime = QLabel("No Session")
        self.header_freshness = QLabel("Market data not started")
        self.chart_state = QLabel("Chart is not available yet")
        self.orders_state = QLabel("No open orders")
        self.position_state = QLabel("No open Position or Basket")
        self._bot_pages = QStackedWidget()
        self._bot_pages.addWidget(self.setup)
        self._bot_pages.addWidget(self.overview)
        self._bot_pages.addWidget(self.unavailable_panel)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._empty_panel(self.orders_state), "Open Orders")
        self.tabs.addTab(self._empty_panel(self.position_state), "Position / Basket")
        self.tabs.addTab(self.trade_history, "Trade History")
        self.tabs.currentChanged.connect(self._tab_changed)
        unavailable_layout = QVBoxLayout(self.unavailable_panel)
        unavailable_layout.addWidget(self.unavailable_message)
        unavailable_layout.addWidget(self.unavailable_retry_button)
        unavailable_layout.addStretch()
        self._build_layout()

    @Slot()
    def show_setup(self) -> None:
        self._bot_pages.setCurrentWidget(self.setup)
        self.header_runtime.setText("No Session")

    def show_configured_session(self, session: ConfiguredPaperSession) -> None:
        self.overview.show_session(session)
        self._bot_pages.setCurrentWidget(self.overview)
        self.header_symbol.setText(session.market_data.symbol)
        self.header_timeframe.setText(session.market_data.timeframe)
        market = session.config.market_type.value.title()
        self.header_mode.setText(f"Paper · {market}")
        self.header_preset.setText(preset_display_name(session.config.preset_version))
        self.header_runtime.setText("Configured")
        self.header_freshness.setText("Market data not started")

    def show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self._bot_pages.setCurrentWidget(self.unavailable_panel)
        self.header_runtime.setText("Unavailable")

    def set_bot_busy(self, busy: bool) -> None:
        self.setup.set_loading(busy)
        self.unavailable_retry_button.setDisabled(busy)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.workspace_header = QFrame()
        self.workspace_header.setObjectName("workspaceHeader")
        self._header_layout = QHBoxLayout(self.workspace_header)
        self._header_layout.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("TIEWTRADE")
        brand.setObjectName("brand")
        self._header_layout.addWidget(brand)
        for label in (
            self.header_symbol,
            self.header_timeframe,
            self.header_mode,
            self.header_preset,
            self.header_runtime,
            self.header_freshness,
        ):
            self._header_layout.addWidget(label)
        self._header_layout.addStretch()
        root.addWidget(self.workspace_header)

        self._body = QWidget()
        self._body.setObjectName("workspaceContent")
        self._body_layout = QHBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(12)

        primary = QWidget()
        primary_layout = QVBoxLayout(primary)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(12)
        chart = QFrame()
        chart.setObjectName("chartPlaceholder")
        chart_layout = QVBoxLayout(chart)
        self.chart_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_state.setProperty("stateMessage", True)
        chart_layout.addWidget(self.chart_state)
        primary_layout.addWidget(chart, 3)
        primary_layout.addWidget(self.tabs, 2)

        self.bot_control = QFrame()
        self.bot_control.setObjectName("botControl")
        self.bot_control.setFixedWidth(360)
        bot_layout = QVBoxLayout(self.bot_control)
        bot_title = QLabel("Bot Control")
        bot_title.setObjectName("sectionTitle")
        bot_layout.addWidget(bot_title)
        bot_layout.addWidget(self._bot_pages, 1)

        self._body_layout.addWidget(primary, 1)
        self._body_layout.addWidget(self.bot_control)
        root.addWidget(self._body, 1)

    @Slot(int)
    def _tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.trade_history:
            self.trade_history_activated.emit()

    @staticmethod
    def _empty_panel(message: QLabel) -> QFrame:
        panel = QFrame()
        panel.setObjectName("emptyPanel")
        layout = QVBoxLayout(panel)
        layout.addStretch()
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setProperty("stateMessage", True)
        layout.addWidget(message)
        layout.addStretch()
        return panel
```

โครงนี้ไม่เพิ่ม navigation sidebar หรือ notification button ที่ยังไม่มี behavior

- [ ] **Step 4: รัน Workspace tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py -q
```

Expected: PASS

- [ ] **Step 5: commit Workspace shell**

```bash
git add src/tiewtrade/ui/trading_workspace.py tests/unit/ui/test_trading_workspace.py
git commit -m "feat: add unified trading workspace shell"
```

## Task 3: MainWindow Workflow Integration

**Files:**
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `tests/unit/ui/test_main_window.py`
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `tests/acceptance/test_desktop_trade_history.py`

**Interfaces:**
- Consumes: Task 2 `TradingWorkspace` methods/signals; existing `SessionWorkflow` และ `TradeHistoryWorkflow`
- Produces: `MainWindow.workspace`, compatibility aliases `setup`, `overview`, `trade_history`, และ one-time Trade History activation

- [ ] **Step 1: เปลี่ยน tests ให้ใช้งาน Unified Workspace**

แทน navigation click ด้วย semantic tab activation และตรวจว่า existing workflows ยัง
independent:

```python
def open_trade_history(window: MainWindow) -> None:
    window.workspace.tabs.setCurrentWidget(window.trade_history)


def test_trade_history_opens_without_active_session(qtbot: QtBot) -> None:
    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    open_trade_history(window)

    qtbot.waitUntil(
        lambda: window.trade_history.basket_state.text() == "No trade history"
    )
    assert window.trade_history.isVisible()
    assert window.workspace.header_runtime.text() == "No Session"
```

ปรับ acceptance assertions หลัง create/restart ให้ตรวจ:

```python
assert window.workspace.header_runtime.text() == "Configured"
assert window.workspace.header_freshness.text() == "Market data not started"
assert window.overview.isVisible()
```

- [ ] **Step 2: รัน MainWindow และ acceptance tests เพื่อยืนยันว่า fail กับ layout เดิม**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py tests/acceptance/test_desktop_trade_history.py -q
```

Expected: FAIL เพราะ `MainWindow` ยังไม่มี `workspace` และยังใช้ navigation pages

- [ ] **Step 3: ย้าย layout ownership ออกจาก MainWindow**

`MainWindow.__init__()` ต้องสร้าง Workspace และ alias existing widgetsก่อน wire workflows:

```python
self.workspace = TradingWorkspace()
self.setup = self.workspace.setup
self.overview = self.workspace.overview
self.trade_history = self.workspace.trade_history
self.unavailable_panel = self.workspace.unavailable_panel
self.unavailable_message = self.workspace.unavailable_message
self.unavailable_retry_button = self.workspace.unavailable_retry_button
self.setCentralWidget(self.workspace)
self.setWindowTitle("TiewTrade")
self.setMinimumSize(1024, 700)
self.resize(1440, 900)
```

เปลี่ยน Session callbacks เป็น Workspace methods:

```python
@Slot(bool)
def _set_busy(self, busy: bool) -> None:
    self.workspace.set_bot_busy(busy)

@Slot(object)
def _show_session(self, session: ConfiguredPaperSession) -> None:
    self.workspace.show_configured_session(session)

def _show_unavailable(self, message: str) -> None:
    self.workspace.show_unavailable(message)

@Slot()
def _show_setup(self) -> None:
    self.workspace.show_setup()
```

ลบ navigation/sidebar และ `_pages`/`_session_pages` จาก `MainWindow`. เชื่อม
`workspace.trade_history_activated` กับ method ที่เริ่ม `TradeHistoryWorkflow` เพียงครั้งเดียว:

```python
@Slot()
def _start_trade_history_once(self) -> None:
    if self._history_started:
        return
    self._history_started = True
    self._history_workflow.start()
```

คง `closeEvent()` ที่ปิดทั้งสอง workflows และรอ `QThreadPool` ตาม timeout เดิม

- [ ] **Step 4: รัน focused UI และ acceptance tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py tests/acceptance/test_desktop_trade_history.py -q
```

Expected: PASS โดยไม่มี network call และ Trade History query เริ่มครั้งเดียว

- [ ] **Step 5: commit MainWindow integration**

```bash
git add src/tiewtrade/ui/main_window.py tests/unit/ui/test_main_window.py tests/acceptance/test_desktop_session_setup.py tests/acceptance/test_desktop_trade_history.py
git commit -m "refactor: compose desktop flows in trading workspace"
```

## Task 4: Responsive Bot Control Drawer

**Files:**
- Modify: `src/tiewtrade/ui/trading_workspace.py`
- Modify: `tests/unit/ui/test_trading_workspace.py`

**Interfaces:**
- Consumes: Task 2 `TradingWorkspace` และ Task 3 MainWindow minimum size
- Produces: `TradingWorkspace.compact_mode: bool`, `bot_control_button`, `open_bot_control()`, `close_bot_control()`

- [ ] **Step 1: เขียน failing tests สำหรับ breakpoint และ drawer**

```python
from tests.support.qt_interactions import click


def test_bot_control_is_docked_at_wide_width(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    qtbot.waitUntil(lambda: not workspace.compact_mode)
    assert workspace.bot_control.isVisible()
    assert not workspace.bot_control_button.isVisible()


def test_bot_control_uses_drawer_below_breakpoint(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1199, 700)
    workspace.show()

    qtbot.waitUntil(lambda: workspace.compact_mode)
    assert not workspace.bot_control.isVisible()
    assert workspace.bot_control_button.isVisible()

    click(workspace.bot_control_button)

    assert workspace.bot_control.isVisible()
    assert workspace.bot_control.geometry().right() == workspace.rect().right()

    workspace.close_bot_control()
    assert not workspace.bot_control.isVisible()
```

- [ ] **Step 2: รัน test เพื่อยืนยันว่า fail เพราะยังไม่มี responsive API**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py -q
```

Expected: FAIL เพราะยังไม่มี `compact_mode`, `bot_control_button` และ drawer methods

- [ ] **Step 3: เพิ่ม responsive layout โดยไม่ duplicate Bot Control widgets**

เพิ่มค่าคงที่และ state:

```python
from PySide6.QtGui import QResizeEvent

BOT_CONTROL_BREAKPOINT = 1200
BOT_CONTROL_WIDTH = 360

self.compact_mode = self.width() < BOT_CONTROL_BREAKPOINT
self._drawer_open = False
self.bot_control_button = QPushButton("Bot Control")
self.bot_control_button.setObjectName("secondaryButton")
self.bot_control_button.clicked.connect(self.open_bot_control)
self._header_layout.addWidget(self.bot_control_button)
self._apply_layout_mode()
```

ใช้ Bot Control instance เดียวและย้ายระหว่าง managed layout กับ child overlay:

```python
def resizeEvent(self, event: QResizeEvent) -> None:
    super().resizeEvent(event)
    compact = event.size().width() < BOT_CONTROL_BREAKPOINT
    if compact != self.compact_mode:
        self.compact_mode = compact
        self._apply_layout_mode()
    if self.compact_mode and self._drawer_open:
        self._position_drawer()

@Slot()
def open_bot_control(self) -> None:
    if not self.compact_mode:
        return
    self._drawer_open = True
    self._position_drawer()
    self.bot_control.show()
    self.bot_control.raise_()
    self.bot_control.setFocus()

@Slot()
def close_bot_control(self) -> None:
    if not self.compact_mode:
        return
    self._drawer_open = False
    self.bot_control.hide()
    self.bot_control_button.setFocus()

def _position_drawer(self) -> None:
    width = min(BOT_CONTROL_WIDTH, self.width())
    top = self.workspace_header.geometry().bottom() + 13
    self.bot_control.setGeometry(
        self.width() - width,
        top,
        width,
        self.height() - top,
    )

def _apply_layout_mode(self) -> None:
    self._body_layout.removeWidget(self.bot_control)
    if self.compact_mode:
        self._drawer_open = False
        self.bot_control.setParent(self)
        self.bot_control.hide()
        self.bot_control_button.show()
        return

    self._drawer_open = False
    self.bot_control_button.hide()
    self.bot_control.setParent(self._body)
    self._body_layout.addWidget(self.bot_control)
    self.bot_control.show()
```

เพิ่ม block นี้หลัง `_build_layout()` ใน constructor เพื่อให้ initial width ใช้ state ที่
ถูกต้องโดยไม่สร้าง Session widget ชุดที่สอง

- [ ] **Step 4: รัน responsive tests และ MainWindow regression**

Run:

```bash
.venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py -q
```

Expected: PASS ทั้ง 1,199 px และ 1,200 px โดย Session/History workflows ไม่ถูกสร้างซ้ำ

- [ ] **Step 5: commit responsive Bot Control**

```bash
git add src/tiewtrade/ui/trading_workspace.py tests/unit/ui/test_trading_workspace.py
git commit -m "feat: add responsive bot control drawer"
```

## Task 5: Workspace Acceptance and Quality Gates

**Files:**
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `tests/acceptance/test_desktop_trade_history.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: Tasks 1–4 complete Workspace shell
- Produces: regression proof ของ create/restore/history flows และ delivery status ของ slice แรก

- [ ] **Step 1: เพิ่ม acceptance assertion ว่าไม่มี Manual Order และไม่มี Runtime side effect**

เพิ่ม assertions ใน existing acceptance flows:

```python
assert window.findChildren(QPushButton, "manualBuyButton") == []
assert window.findChildren(QPushButton, "manualSellButton") == []
assert window.workspace.chart_state.text() == "Chart is not available yet"
assert window.workspace.orders_state.text() == "No open orders"
assert window.workspace.position_state.text() == "No open Position or Basket"
assert _trade_side_effect_counts(database) == initial_side_effect_counts
```

เพิ่ม resize assertion:

```python
window.resize(1199, 700)
qtbot.waitUntil(lambda: window.workspace.compact_mode)
assert window.workspace.bot_control_button.isVisible()
```

- [ ] **Step 2: รัน acceptance tests**

Run:

```bash
.venv/bin/python -m pytest tests/acceptance/test_desktop_session_setup.py tests/acceptance/test_desktop_trade_history.py -q
```

Expected: PASS สำหรับ no-session, configured Spot/Futures, restart restore และ Trade History unavailable paths

- [ ] **Step 3: บันทึกสถานะ delivery ใน Project Plan**

เพิ่มย่อหน้าใน Milestone 3 หลังสถานะ DEV-97:

```markdown
สถานะ Unified Trading Workspace slice 1: Desktop UI ใช้ Full Dark Theme และรวม
Session Setup, configured Session summary และ Trade History ไว้ใน Workspace หน้าเดียว
พร้อม responsive Bot Control แล้ว ส่วน dynamic Runtime read model, Start/Stop/Recovery,
Notifications และ Chart ยังคงส่งมอบตาม Sub-issues ถัดไป
```

- [ ] **Step 4: รัน quality gates ทั้ง repository**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Expected: ทุกคำสั่ง exit 0; UI tests ใช้ offscreen/fake data และไม่มี Live/API credentials

- [ ] **Step 5: commit acceptance evidence**

```bash
git add tests/acceptance/test_desktop_session_setup.py tests/acceptance/test_desktop_trade_history.py PROJECT_PLAN.md
git commit -m "test: verify unified workspace shell acceptance"
```

## Self-Review Results

- Spec coverage: แผนนี้ครอบเฉพาะ Delivery Slice 1 ตามที่ประกาศและไม่อ้างว่าส่งมอบ Runtime, Notifications หรือ Chart จริง
- Boundary check: UI รับ `ConfiguredPaperSession` ซึ่งเป็น application result เดิมและไม่ import SQLite, Strategy หรือ Execution
- Behavior preservation: Session create/restore, independent Trade History workflow, stale callback suppression และ close lifecycle ยังคงอยู่
- Placeholder check: Chart/Orders/Position ใช้ข้อความ empty state ที่ตั้งใจส่งมอบใน slice นี้ ไม่มี `TBD`, `TODO` หรือข้อมูลจำลอง
- Type consistency: `TradingWorkspace` methods และ attributes ที่ MainWindow/tests ใช้ตรงกันทุก Task
- Safety check: ไม่มี network, credentials, Live adapter หรือ Manual Order control
