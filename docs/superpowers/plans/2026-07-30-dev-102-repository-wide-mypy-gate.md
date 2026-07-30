# DEV-102 Repository-wide mypy Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้คำสั่ง `.venv/bin/python -m mypy` ตรวจทั้ง production code และ tests ภายใต้ strict mode และผ่านร่วมกับ pytest/Ruff โดยไม่ลดความเข้มงวดของ type checking

**Architecture:** กำหนด repository-wide scope ใน `pyproject.toml` เพียงจุดเดียว แล้วแก้ type boundary ใน tests ด้วย typed fixtures และ helpers ที่มีความรับผิดชอบเฉพาะด้าน การ cast อนุญาตเฉพาะขอบเขตที่ runtime ตั้งใจรับค่าจาก third-party, Qt, SQLite หรือ invalid-contract test โดยไม่เปลี่ยน business behavior ของ production code

**Tech Stack:** Python 3.12, mypy strict mode, pytest, pytest-qt, PySide6, aiohttp, Ruff, GitHub Actions

## Global Constraints

- คำสั่ง default `.venv/bin/python -m mypy` ต้องตรวจ `src/tiewtrade` และ `tests` โดยไม่ต้องระบุ path เพิ่ม
- คง `strict = true`; ห้ามปิด error code, exclude tests, ใช้ `follow_imports = "skip"` หรือเพิ่ม per-module override เพื่อลดความเข้มงวด
- ใช้ `files = ["src/tiewtrade", "tests"]`, `mypy_path = "src"` และ `explicit_package_bases = true` ใน `pyproject.toml`
- การ cast ต้องอยู่ตรง dynamic boundary ที่ตรวจสอบหรือมี test ยืนยัน contract เท่านั้น
- ห้ามเปลี่ยน trading rules, runtime behavior, Paper/Live policy หรือเชื่อม Live/private Binance API
- Test doubles ต้องมี signature ตรงกับ production protocol หรือ third-party stub ที่ implement
- ทุก Task ต้องผ่าน tests ที่เกี่ยวข้อง, mypy เฉพาะไฟล์ที่แก้ และ Ruff ก่อน commit

---

### Task 1: Define the repository-wide mypy gate

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/verify.yml`
- Modify: `tests/unit/test_ci_workflow.py`
- Modify: `README.md`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: repository layout `src/tiewtrade` and `tests`
- Produces: bare command `.venv/bin/python -m mypy` as the single local/CI type-checking contract

- [ ] **Step 1: Add failing configuration contract tests**

Define focused TOML types and assert the exact gate:

```python
from typing import TypedDict, cast

class MypyConfig(TypedDict):
    python_version: str
    strict: bool
    files: list[str]
    mypy_path: str
    explicit_package_bases: bool

class ToolConfig(TypedDict):
    mypy: MypyConfig

class PyprojectConfig(TypedDict):
    tool: ToolConfig

def _pyproject_config() -> PyprojectConfig:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return cast(PyprojectConfig, tomllib.load(pyproject_file))

def test_mypy_configuration_checks_source_and_tests_strictly() -> None:
    assert _pyproject_config()["tool"]["mypy"] == {
        "python_version": "3.12",
        "strict": True,
        "files": ["src/tiewtrade", "tests"],
        "mypy_path": "src",
        "explicit_package_bases": True,
    }
```

Change the workflow expectation to `run: python -m mypy`.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/test_ci_workflow.py -q`

Expected: FAIL because `packages = ["tiewtrade"]` remains and the workflow still passes `src` explicitly.

- [ ] **Step 3: Configure the single gate and update operator documentation**

Replace `[tool.mypy]` with:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
files = ["src/tiewtrade", "tests"]
mypy_path = "src"
explicit_package_bases = true
```

Set the GitHub Actions command to `python -m mypy`. Replace `.venv/bin/python -m mypy src` with `.venv/bin/python -m mypy` in `README.md` and `PROJECT_PLAN.md`.

- [ ] **Step 4: Verify GREEN and expose the remaining test typing inventory**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/test_ci_workflow.py -q
../../.venv/bin/python -m mypy --show-error-codes --no-pretty
```

Expected: CI contract tests PASS; mypy reaches both source and tests and fails only on the typed-test-boundary errors handled by Tasks 2–7.

- [ ] **Step 5: Run focused quality checks and commit**

```bash
../../.venv/bin/python -m ruff check pyproject.toml tests/unit/test_ci_workflow.py
../../.venv/bin/python -m ruff format --check tests/unit/test_ci_workflow.py
git diff --check
git add pyproject.toml .github/workflows/verify.yml tests/unit/test_ci_workflow.py README.md PROJECT_PLAN.md
git commit -m "build: extend strict mypy gate to tests"
```

---

### Task 2: Type trade-history fixtures and domain validation tests

**Files:**
- Create: `tests/support/dataclass_validation.py`
- Modify: `tests/support/trade_history_records.py`
- Modify: `tests/unit/trading/test_trade_history.py`
- Modify: `tests/unit/trading/test_basket.py`
- Modify: `tests/unit/application/test_trade_history_query.py`
- Modify: `tests/unit/integrations/sqlite/test_trade_history.py`
- Modify: `tests/unit/integrations/sqlite/test_trade_history_query.py`
- Modify: `tests/acceptance/test_paper_spot_trade_history.py`

**Interfaces:**
- Consumes: `TradeFill`, `BasketResult`, `TradeHistoryFilter`, `Basket`, and SQLite history repositories
- Produces: fully typed `trade_fill(...)`, `basket_result(...)`, and `replace_unchecked(instance, **changes)` test helpers

- [ ] **Step 1: Use the strict gate as RED for the listed files**

Run:

```bash
../../.venv/bin/python -m mypy tests/support/trade_history_records.py tests/unit/trading/test_trade_history.py tests/unit/trading/test_basket.py tests/unit/application/test_trade_history_query.py tests/unit/integrations/sqlite/test_trade_history.py tests/unit/integrations/sqlite/test_trade_history_query.py tests/acceptance/test_paper_spot_trade_history.py --show-error-codes --no-pretty
```

Expected: FAIL on untyped `dict[str, object]` construction, invalid dataclass arguments, optional SQLite rows and collection inference.

- [ ] **Step 2: Replace untyped fixture dictionaries with explicit keyword-only factories**

Give every dataclass field a typed parameter and construct the dataclass directly. The `trade_fill` signature must begin as follows and continue with the remaining existing fields using their exact dataclass types/defaults:

```python
def trade_fill(
    *,
    fill_id: str = "fill-1",
    basket_id: UUID = BASKET_ID,
    session_id: UUID = SESSION_ID,
    order_id: str = "order-1",
    exchange_trade_id: str | None = None,
    side: FillSide = FillSide.BUY,
    entry_number: int = 1,
    filled_at_utc: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    price: Decimal = Decimal("100"),
    quantity: Decimal = Decimal("2"),
    notional: Decimal = Decimal("200"),
    commission: Decimal = Decimal("0.2"),
    commission_asset: str = "USDT",
    realized_pnl: Decimal = Decimal("0"),
    source: FillSource = FillSource.PAPER_EXECUTOR,
) -> TradeFill:
    return TradeFill(
        fill_id=fill_id,
        basket_id=basket_id,
        session_id=session_id,
        order_id=order_id,
        exchange_trade_id=exchange_trade_id,
        side=side,
        entry_number=entry_number,
        filled_at_utc=filled_at_utc,
        price=price,
        quantity=quantity,
        notional=notional,
        commission=commission,
        commission_asset=commission_asset,
        realized_pnl=realized_pnl,
        source=source,
    )
```

Apply the same explicit construction to all current `BasketResult` fields in `basket_result`.

- [ ] **Step 3: Add one localized helper for intentional invalid dataclass values**

```python
from collections.abc import Callable
from dataclasses import replace
from typing import TypeVar, cast

T = TypeVar("T")

def replace_unchecked(instance: T, **changes: object) -> T:
    unchecked_replace = cast(Callable[..., T], replace)
    return unchecked_replace(instance, **changes)
```

Use this helper only where a test deliberately supplies an invalid runtime value to prove `__post_init__` validation.

- [ ] **Step 4: Narrow optional and collection values at their use sites**

Use `first_fills: tuple[TradeFill, ...] = ()`; assert `legacy.closed_at_utc is not None` before calling `isoformat`; rename variables that change from database rows to domain results; build Basket test inputs directly instead of expanding `dict[str, object]`; use typed factory callbacks for invalid UTC filter cases.

- [ ] **Step 5: Verify GREEN and commit**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/trading/test_trade_history.py tests/unit/trading/test_basket.py tests/unit/application/test_trade_history_query.py tests/unit/integrations/sqlite/test_trade_history.py tests/unit/integrations/sqlite/test_trade_history_query.py tests/acceptance/test_paper_spot_trade_history.py -q
../../.venv/bin/python -m mypy tests/support/trade_history_records.py tests/support/dataclass_validation.py tests/unit/trading/test_trade_history.py tests/unit/trading/test_basket.py tests/unit/application/test_trade_history_query.py tests/unit/integrations/sqlite/test_trade_history.py tests/unit/integrations/sqlite/test_trade_history_query.py tests/acceptance/test_paper_spot_trade_history.py
../../.venv/bin/python -m ruff check tests/support tests/unit/trading tests/unit/application/test_trade_history_query.py tests/unit/integrations/sqlite tests/acceptance/test_paper_spot_trade_history.py
../../.venv/bin/python -m ruff format --check tests/support tests/unit/trading tests/unit/application/test_trade_history_query.py tests/unit/integrations/sqlite tests/acceptance/test_paper_spot_trade_history.py
git diff --check
git add tests/support tests/unit/trading tests/unit/application/test_trade_history_query.py tests/unit/integrations/sqlite tests/acceptance/test_paper_spot_trade_history.py
git commit -m "test: type trade history domain fixtures"
```

---

### Task 3: Type desktop composition test seams

**Files:**
- Modify: `tests/unit/test_desktop_main.py`

**Interfaces:**
- Consumes: `SQLiteDatabase`, `CreateSession`, `LoadActiveSession`, `ListBaskets`, `ListFills`
- Produces: typed captured composition dependencies without altering desktop production composition

- [ ] **Step 1: Verify RED**

Run: `../../.venv/bin/python -m mypy tests/unit/test_desktop_main.py --show-error-codes --no-pretty`

Expected: FAIL on dynamic module attributes, captured `object` values, SQLite row access and the `Path.mkdir` fake signature.

- [ ] **Step 2: Make captured dependencies explicit at the boundary**

Import the concrete types from their owning modules and narrow captured values when reading them:

```python
database = cast(SQLiteDatabase, captured["database"])
create_session = cast(CreateSession, captured["create_session"])
load_active_session = cast(LoadActiveSession, captured["load_active_session"])
list_baskets = cast(ListBaskets, captured["list_baskets"])
list_fills = cast(ListFills, captured["list_fills"])
```

Access `SQLiteDatabase` through its infrastructure module, not as a non-exported attribute on `desktop_main`. Narrow `fetchone()` with a localized cast after asserting a row exists.

- [ ] **Step 3: Match the `Path.mkdir` fake signature**

```python
def record_mkdir(
    path: Path,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    mkdir_calls.append((path, mode, parents, exist_ok))
```

- [ ] **Step 4: Verify GREEN and commit**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/test_desktop_main.py -q
../../.venv/bin/python -m mypy tests/unit/test_desktop_main.py
../../.venv/bin/python -m ruff check tests/unit/test_desktop_main.py
../../.venv/bin/python -m ruff format --check tests/unit/test_desktop_main.py
git diff --check
git add tests/unit/test_desktop_main.py
git commit -m "test: type desktop composition seams"
```

---

### Task 4: Type paper-session mocks and worker callbacks

**Files:**
- Modify: `tests/unit/application/test_paper_spot_session.py`
- Modify: `tests/unit/application/test_paper_futures_session.py`
- Modify: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`
- Modify: `tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py`
- Modify: `tests/unit/ui/test_session_workflow.py`
- Modify: `tests/unit/ui/test_trade_history_workflow.py`

**Interfaces:**
- Consumes: `EntryIntent`, session application callables, autospecced mocks and Qt worker signals
- Produces: signature-compatible fakes and callbacks returning `None`

- [ ] **Step 1: Verify RED**

Run the strict gate over the six listed files and confirm failures for untyped helper functions, obsolete ignores, autospec assertion methods and lambda return values.

- [ ] **Step 2: Type session intent helpers**

Use exact signatures:

```python
def arm_entry_intent(...) -> EntryIntent:
    ...

def arm_next_entry_intent(...) -> EntryIntent:
    ...

def minute_after(intent: EntryIntent) -> int:
    return intent.created_at_utc.minute + 1
```

Keep existing helper bodies and arguments unchanged; add the return/parameter types from the production domain objects.

- [ ] **Step 3: Type autospec assertion and signal boundaries**

Keep an explicitly typed `Mock` reference for each assertion-only autospec and remove now-unused `type: ignore` comments. Replace value-returning lambdas connected to signals with callbacks such as:

```python
def record_result(value: object) -> None:
    results.append(value)
```

For tests that intentionally send an invalid worker result, cast that single value to the expected callable result alias at the signal boundary.

- [ ] **Step 4: Verify GREEN and commit**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/application/test_paper_spot_session.py tests/unit/application/test_paper_futures_session.py tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py tests/unit/ui/test_session_workflow.py tests/unit/ui/test_trade_history_workflow.py -q
../../.venv/bin/python -m mypy tests/unit/application/test_paper_spot_session.py tests/unit/application/test_paper_futures_session.py tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py tests/unit/ui/test_session_workflow.py tests/unit/ui/test_trade_history_workflow.py
../../.venv/bin/python -m ruff check tests/unit/application tests/unit/integrations/sqlite tests/unit/ui
../../.venv/bin/python -m ruff format --check tests/unit/application tests/unit/integrations/sqlite tests/unit/ui
git diff --check
git add tests/unit/application tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py tests/unit/ui/test_session_workflow.py tests/unit/ui/test_trade_history_workflow.py
git commit -m "test: type paper session boundaries"
```

---

### Task 5: Type structured market-data log assertions

**Files:**
- Create: `tests/support/market_data_logging.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `tests/unit/market_data/test_runtime_logging.py`
- Modify: `tests/unit/market_data/test_runtime_state.py`
- Modify: `tests/acceptance/test_public_market_data_runtime.py`

**Interfaces:**
- Consumes: standard `logging.LogRecord` plus structured fields emitted by market-data runtime
- Produces: `MarketDataLogRecord`, `as_market_data_record` and `market_data_records`

- [ ] **Step 1: Verify RED**

Run mypy on the five listed files and confirm failures from dynamic log attributes, untyped `caplog`, enum/string comparisons, stale union narrowing and a deliberate non-Candle fake.

- [ ] **Step 2: Add a checked structured-log boundary**

```python
import logging
from collections.abc import Iterable
from typing import Protocol, cast

class MarketDataLogRecord(Protocol):
    levelno: int
    event_name: str
    symbol: str
    timeframe: str
    reason: str
    failure_kind: str | None
    attempt: int
    delay_seconds: float
    discard_reason: str
    skew_seconds: float
    start: str
    end: str
    candle_count: int

    def getMessage(self) -> str: ...

def as_market_data_record(record: logging.LogRecord) -> MarketDataLogRecord:
    assert hasattr(record, "event_name")
    return cast(MarketDataLogRecord, record)

def market_data_records(
    records: Iterable[logging.LogRecord],
) -> list[MarketDataLogRecord]:
    return [
        as_market_data_record(record)
        for record in records
        if hasattr(record, "event_name")
    ]
```

- [ ] **Step 3: Use typed log and runtime values**

Annotate `caplog` as `pytest.LogCaptureFixture`; use the helper before accessing structured attributes; compare enums through `.value`; bind a new typed snapshot after each state transition; verify an `object` numeric field with `isinstance(value, float)` before comparing it; use `cast(Candle, object())` only in the deliberate invalid-source test.

- [ ] **Step 4: Verify GREEN and commit**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/market_data/test_runtime.py tests/unit/market_data/test_runtime_logging.py tests/unit/market_data/test_runtime_state.py tests/acceptance/test_public_market_data_runtime.py -q
../../.venv/bin/python -m mypy tests/support/market_data_logging.py tests/unit/market_data/test_runtime.py tests/unit/market_data/test_runtime_logging.py tests/unit/market_data/test_runtime_state.py tests/acceptance/test_public_market_data_runtime.py
../../.venv/bin/python -m ruff check tests/support/market_data_logging.py tests/unit/market_data tests/acceptance/test_public_market_data_runtime.py
../../.venv/bin/python -m ruff format --check tests/support/market_data_logging.py tests/unit/market_data tests/acceptance/test_public_market_data_runtime.py
git diff --check
git add tests/support/market_data_logging.py tests/unit/market_data tests/acceptance/test_public_market_data_runtime.py
git commit -m "test: type market data diagnostics"
```

---

### Task 6: Type the aiohttp fake transport boundary

**Files:**
- Modify: `tests/unit/integrations/binance/test_public_market_data.py`

**Interfaces:**
- Consumes: `aiohttp.ClientSession`, `RequestInfo`, `ContentTypeError`, `ClientResponseError`
- Produces: typed fake transport setup without changing the production Binance client

- [ ] **Step 1: Verify RED**

Run: `../../.venv/bin/python -m mypy tests/unit/integrations/binance/test_public_market_data.py --show-error-codes --no-pretty`

Expected: FAIL on fake session argument types, untyped candle collection and exception request metadata.

- [ ] **Step 2: Type collection and fake-session construction**

Annotate collection callbacks as `tuple[Candle, ...]`. Keep the fake behavior and use one localized `cast(aiohttp.ClientSession, fake_session)` only where constructing the production source.

- [ ] **Step 3: Construct real typed aiohttp exception metadata**

Build `RequestInfo` with `yarl.URL`, `multidict.CIMultiDict` and `CIMultiDictProxy`, then pass that typed object and typed headers into `ContentTypeError` and `ClientResponseError`. Do not replace these exceptions with generic fakes.

- [ ] **Step 4: Verify GREEN and commit**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py -q
../../.venv/bin/python -m mypy tests/unit/integrations/binance/test_public_market_data.py
../../.venv/bin/python -m ruff check tests/unit/integrations/binance/test_public_market_data.py
../../.venv/bin/python -m ruff format --check tests/unit/integrations/binance/test_public_market_data.py
git diff --check
git add tests/unit/integrations/binance/test_public_market_data.py
git commit -m "test: type Binance market data transport fakes"
```

---

### Task 7: Type Qt interaction and widget boundaries

**Files:**
- Create: `tests/support/qt_interactions.py`
- Modify: `tests/unit/ui/test_trade_history_page.py`
- Modify: `tests/unit/ui/test_main_window.py`
- Modify: `tests/unit/ui/test_session_setup.py`
- Modify: `tests/acceptance/test_paper_trade_history_acceptance.py`
- Modify: `tests/acceptance/test_desktop_trade_history.py`
- Modify: `tests/acceptance/test_desktop_session_setup.py`

**Interfaces:**
- Consumes: `QWidget`, `QTableWidget`, `QTableWidgetItem`, `QDate`, `QTest`, `Qt.MouseButton`, `QThreadPool.waitForDone`
- Produces: `click`, `table_item`, `qdate` and a signature-compatible recording thread pool

- [ ] **Step 1: Verify RED**

Run mypy on the seven listed test files and confirm failures from untyped pytest-qt mouse calls, optional table items, Python `date` passed to Qt, and the incompatible `waitForDone` override.

- [ ] **Step 2: Add focused Qt interaction helpers**

```python
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QWidget

def click(
    widget: QWidget,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
) -> None:
    QTest.mouseClick(widget, button)

def table_item(table: QTableWidget, row: int, column: int) -> QTableWidgetItem:
    item = table.item(row, column)
    assert item is not None
    return item

def qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)
```

- [ ] **Step 3: Use typed helpers and match the overloaded Qt method**

Replace direct mouse calls, nullable `.item()` dereferences and Python-date `setDate` calls with the helpers. Declare both `QThreadPool.waitForDone` overloads using `@overload`, then implement one union-compatible method that records the call and returns the existing test result; preserve test behavior and assertions.

- [ ] **Step 4: Verify GREEN**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_page.py tests/unit/ui/test_main_window.py tests/unit/ui/test_session_setup.py tests/acceptance/test_paper_trade_history_acceptance.py tests/acceptance/test_desktop_trade_history.py tests/acceptance/test_desktop_session_setup.py -q
../../.venv/bin/python -m mypy tests/support/qt_interactions.py tests/unit/ui/test_trade_history_page.py tests/unit/ui/test_main_window.py tests/unit/ui/test_session_setup.py tests/acceptance/test_paper_trade_history_acceptance.py tests/acceptance/test_desktop_trade_history.py tests/acceptance/test_desktop_session_setup.py
../../.venv/bin/python -m ruff check tests/support/qt_interactions.py tests/unit/ui tests/acceptance
../../.venv/bin/python -m ruff format --check tests/support/qt_interactions.py tests/unit/ui tests/acceptance
git diff --check
```

- [ ] **Step 5: Run the repository-wide acceptance gate**

```bash
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m mypy
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check .
../../.venv/bin/python -m ruff format --check .
git diff --check
git diff --check main HEAD
```

Expected: mypy reports success for all source files, pytest reports all tests passing, both Ruff commands exit 0 and both diff checks produce no output.

- [ ] **Step 6: Commit**

```bash
git add tests/support/qt_interactions.py tests/unit/ui tests/acceptance
git commit -m "test: type Qt interaction boundaries"
```

---

## Final Review

- [ ] Review the complete branch against `docs/superpowers/specs/2026-07-30-dev-102-repository-wide-mypy-gate-design.md`
- [ ] Confirm `git diff main...HEAD -- src/tiewtrade` is empty unless a reviewer documents a real production seam mismatch
- [ ] Confirm no `type: ignore`, mypy override or cast was introduced outside a documented dynamic boundary
- [ ] Re-run the repository-wide acceptance gate from Task 7
- [ ] Update DEV-102 to `Done` only after implementation and verification are complete
