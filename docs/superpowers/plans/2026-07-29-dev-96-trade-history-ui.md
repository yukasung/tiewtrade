# DEV-96 Trade History UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่มหน้า Desktop Trade History ที่แสดง Basket History และ Trade Fills แบบ filter/pagination ผ่าน application query บน background worker โดยเปิดดูได้เสมอและไม่ให้ UI เรียก SQLite โดยตรง

**Architecture:** `TradeHistoryPage` เป็น thin PySide6 presentation, `TradeHistoryWorkflow` เป็นเจ้าของ query lifecycle และ generation guards, ส่วน `desktop_main.py` inject `SQLiteTradeHistory.list_baskets` และ `list_fills` ผ่าน callable contracts หน้าใหม่ใช้ `BackgroundTask` ร่วมกับ `SessionWorkflow` และไม่เปลี่ยน schema หรือ business rules

**Tech Stack:** Python 3.12, PySide6 6.10, SQLite adapter เดิม, pytest, pytest-qt, Ruff และ Mypy strict

## Global Constraints

- UI เป็นภาษาอังกฤษและใช้ light theme โทน neutral/blue
- `Trade History` เปิดดูได้เสมอ แม้ไม่มี Active Paper Session หรือ Session workflow อยู่ใน unavailable state
- ค่าเริ่มต้นแสดงทุก Session เรียง Basket ล่าสุดก่อนและใช้ `PageRequest(page=1, page_size=50)`
- Date filter ใช้ `BasketResult.opened_at_utc`; From รวมตั้งแต่ต้นวัน UTC และ To รวมทั้งวันโดยแปลงเป็นก่อนต้นวันถัดไป
- Query เกิดเมื่อกด `Apply Filters`; `Reset` คืน empty filter และหน้า 1
- Basket แรกของแต่ละผลลัพธ์ถูกเลือกและโหลด Fills อัตโนมัติ
- Total Net PnL ใช้ `BasketHistoryPage.net_realized_pnl` โดยตรงและไม่คำนวณซ้ำใน UI
- Decimal ต้องไม่แปลงผ่าน `float`; เวลาแสดงเป็น UTC
- Positive, negative และ zero PnL ต้องมีข้อความ `Profit`, `Loss` หรือ `Break-even` ไม่พึ่งสีเพียงอย่างเดียว
- Basket query failure ห้ามแสดงค่า `0.00` ปลอม; error copy ห้ามมี exception text หรือ SQLite path
- UI ห้าม import SQLite, Strategy, Execution หรือ Binance และ persistence ต้องไม่บล็อก UI thread
- ไม่เพิ่ม chart, CSV export, Live execution, schema, migration, business rule, generic repository หรือ generic page framework
- ใช้ Paper/fake adapters และ no-network tests เท่านั้น

---

### Task 1: Rename the shared UI background task

**Files:**
- Create: `src/tiewtrade/ui/background_task.py`
- Delete: `src/tiewtrade/ui/session_tasks.py`
- Modify: `src/tiewtrade/ui/session_workflow.py`
- Create: `tests/unit/ui/test_background_task.py`
- Test: `tests/unit/ui/test_session_workflow.py`

**Interfaces:**
- Consumes: `Callable[[], object]`, Qt `QRunnable` และ `Signal`
- Produces: `BackgroundTask(operation: Callable[[], object])` และ `BackgroundTaskSignals` ที่มี `succeeded`, `failed`, `finished`

- [ ] **Step 1: Write failing import and behavior tests**

```python
from tiewtrade.ui.background_task import BackgroundTask


def test_background_task_emits_success_before_finished(qtbot: QtBot) -> None:
    task = BackgroundTask(lambda: "result")
    events: list[object] = []
    task.signals.succeeded.connect(lambda value: events.append(value))
    task.signals.finished.connect(lambda: events.append("finished"))

    task.run()

    assert events == ["result", "finished"]


def test_background_task_emits_failure_before_finished(qtbot: QtBot) -> None:
    error = RuntimeError("failed")

    def fail() -> object:
        raise error

    task = BackgroundTask(fail)
    events: list[object] = []
    task.signals.failed.connect(lambda value: events.append(value))
    task.signals.finished.connect(lambda: events.append("finished"))

    task.run()

    assert events == [error, "finished"]
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_background_task.py -q
```

Expected: FAIL with `ModuleNotFoundError: tiewtrade.ui.background_task`.

- [ ] **Step 3: Move the implementation and update SessionWorkflow**

```python
class BackgroundTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()


class BackgroundTask(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation
        self.signals = BackgroundTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:
            self.signals.failed.emit(error)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
```

Update every `SessionTask` reference to `BackgroundTask` and delete
`session_tasks.py`; do not change SessionWorkflow semantics.

- [ ] **Step 4: Run GREEN and regression tests**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_background_task.py tests/unit/ui/test_session_workflow.py tests/unit/ui/test_main_window.py -q
../../.venv/bin/python -m ruff check src/tiewtrade/ui tests/unit/ui
../../.venv/bin/python -m mypy src/tiewtrade/ui
```

Expected: all selected tests and checks PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/tiewtrade/ui/background_task.py src/tiewtrade/ui/session_workflow.py tests/unit/ui/test_background_task.py
git add -u src/tiewtrade/ui/session_tasks.py
git commit -m "refactor: share UI background task"
```

---

### Task 2: Add pure Trade History presentation values and formatting

**Files:**
- Create: `src/tiewtrade/ui/trade_history_presenter.py`
- Create: `tests/unit/ui/test_trade_history_presenter.py`

**Interfaces:**
- Consumes: `TradeHistoryFilter`, `BasketHistoryPage`, `BasketResult`, `TradeFill`, `MarketType`, `TradeMode`, `BasketStatus`
- Produces: `TradeHistoryFilterValues`, `BasketRow`, `FillRow`, `PageState`, `trade_history_filter`, `basket_rows`, `fill_rows`, `page_state`, `pnl_text`

- [ ] **Step 1: Write failing filter conversion tests**

```python
def test_filter_values_build_inclusive_utc_date_range() -> None:
    values = TradeHistoryFilterValues(
        symbol="BTCUSDT",
        timeframe="5m",
        market_type="spot",
        trade_mode="paper",
        status="closed",
        from_date=date(2026, 1, 2),
        to_date=date(2026, 1, 3),
    )

    assert trade_history_filter(values) == TradeHistoryFilter(
        symbol="BTCUSDT",
        timeframe="5m",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        status=BasketStatus.CLOSED,
        opened_from_utc=datetime(2026, 1, 2, tzinfo=UTC),
        opened_before_utc=datetime(2026, 1, 4, tzinfo=UTC),
    )


def test_filter_values_reject_from_after_to() -> None:
    values = TradeHistoryFilterValues(
        from_date=date(2026, 1, 3),
        to_date=date(2026, 1, 2),
    )

    with pytest.raises(ValueError, match="From Date must not be after To Date"):
        trade_history_filter(values)
```

- [ ] **Step 2: Write failing formatting and pagination tests**

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("19.580000000000000001"), "19.580000000000000001 USDT · Profit"),
        (Decimal("-0.2"), "-0.2 USDT · Loss"),
        (Decimal("0"), "0.00 USDT · Break-even"),
    ],
)
def test_pnl_text_preserves_decimal_and_adds_semantic_label(
    value: Decimal, expected: str
) -> None:
    assert pnl_text(value) == expected


def test_basket_and_fill_rows_format_utc_and_all_columns() -> None:
    basket = basket_result()
    fill = trade_fill()

    assert basket_rows((basket,))[0].values == (
        "2026-01-01 00:00:00 UTC", "Paper", "Spot", "BTCUSDT", "5m",
        "1", "200 USDT", "20 USDT", "0.42 USDT", "0.00 USDT",
        "19.58 USDT · Profit", "Closed",
    )
    assert fill_rows((fill,))[0].values == (
        "2026-01-01 00:00:00 UTC", "Buy", "1", "100", "2", "200 USDT",
        "0.2 USDT", "0.00 USDT · Break-even", "Paper Executor",
    )


def test_page_state_bounds_previous_and_next() -> None:
    assert page_state(page=2, page_size=50, total_items=120) == PageState(
        current_page=2, total_pages=3, previous_enabled=True, next_enabled=True
    )
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_presenter.py -q
```

Expected: FAIL because `trade_history_presenter` does not exist.

- [ ] **Step 4: Implement immutable presentation types and pure functions**

```python
@dataclass(frozen=True, slots=True)
class TradeHistoryFilterValues:
    symbol: str | None = None
    timeframe: str | None = None
    market_type: str | None = None
    trade_mode: str | None = None
    status: str | None = None
    from_date: date | None = None
    to_date: date | None = None


@dataclass(frozen=True, slots=True)
class BasketRow:
    basket_id: UUID
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FillRow:
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PageState:
    current_page: int
    total_pages: int
    previous_enabled: bool
    next_enabled: bool
```

Implement exact enum mapping, UTC bounds, Decimal-only formatting, 12 Basket cells,
9 Fill cells and bounded page calculations. Use `0.00` for exact zero only; never
quantize non-zero values or call `float()`.

- [ ] **Step 5: Run GREEN and static checks**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_presenter.py -q
../../.venv/bin/python -m ruff check src/tiewtrade/ui/trade_history_presenter.py tests/unit/ui/test_trade_history_presenter.py
../../.venv/bin/python -m mypy src/tiewtrade/ui/trade_history_presenter.py
```

Expected: tests, Ruff and Mypy PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/tiewtrade/ui/trade_history_presenter.py tests/unit/ui/test_trade_history_presenter.py
git commit -m "feat: present Trade History values"
```

---

### Task 3: Implement TradeHistoryWorkflow with latest-request semantics

**Files:**
- Create: `src/tiewtrade/ui/trade_history_workflow.py`
- Create: `tests/unit/ui/test_trade_history_workflow.py`

**Interfaces:**
- Consumes: `BackgroundTask`, `TradeHistoryFilterValues`, `ListBaskets`, `ListFills`
- Produces: `TradeHistoryWorkflow` public operations and semantic signals defined in the approved design

- [ ] **Step 1: Write failing first-load, auto-selection and empty tests**

```python
def page_with(*items: BasketResult, page: int = 1, total_items: int | None = None) -> BasketHistoryPage:
    return BasketHistoryPage(
        items=tuple(items),
        page=page,
        page_size=50,
        total_items=len(items) if total_items is None else total_items,
        net_realized_pnl=sum(
            (item.net_realized_pnl for item in items if item.status is BasketStatus.CLOSED),
            start=Decimal("0"),
        ),
    )


def workflow_with(
    *,
    list_baskets: ListBaskets,
    list_fills: ListFills,
) -> tuple[TradeHistoryWorkflow, QThreadPool]:
    pool = QThreadPool()
    pool.setMaxThreadCount(2)
    return (
        TradeHistoryWorkflow(
            list_baskets=list_baskets,
            list_fills=list_fills,
            thread_pool=pool,
        ),
        pool,
    )


def test_start_loads_first_page_and_auto_loads_first_basket_fills(qtbot: QtBot) -> None:
    basket = basket_result()
    fill = trade_fill()
    basket_calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    fill_calls: list[UUID] = []

    def list_baskets(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        basket_calls.append((filters, request))
        return page_with(basket)

    def list_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        fill_calls.append(basket_id)
        return (fill,)

    workflow, pool = workflow_with(
        list_baskets=list_baskets,
        list_fills=list_fills,
    )
    pages: list[BasketHistoryPage] = []
    fills: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.fills_ready.connect(lambda basket_id, values: fills.append((basket_id, values)))

    workflow.start()

    qtbot.waitUntil(lambda: len(fills) == 1)
    assert basket_calls == [(TradeHistoryFilter(), PageRequest(page=1, page_size=50))]
    assert pages[0].items == (basket,)
    assert fill_calls == [basket.basket_id]
    assert fills == [(basket.basket_id, (fill,))]
    assert pool.waitForDone(1_000)


def test_empty_basket_page_does_not_query_fills(qtbot: QtBot) -> None:
    fill_calls: list[UUID] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(),
        list_fills=lambda basket_id: fill_calls.append(basket_id) or (),
    )
    empty_events: list[None] = []
    workflow.baskets_empty.connect(lambda: empty_events.append(None))

    workflow.start()

    qtbot.waitUntil(lambda: empty_events == [None])
    assert fill_calls == []
    assert pool.waitForDone(1_000)
```

- [ ] **Step 2: Write failing filter, pagination and retry tests**

```python
def test_apply_filters_resets_to_page_one_and_uses_exact_filter(qtbot: QtBot) -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []

    def list_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        calls.append((filters, request))
        return page_with()

    workflow, pool = workflow_with(
        list_baskets=list_baskets,
        list_fills=lambda basket_id: (),
    )
    values = TradeHistoryFilterValues(symbol="BTCUSDT", status="closed")
    workflow.apply_filters(values)
    qtbot.waitUntil(lambda: len(calls) == 1)
    assert calls[0] == (
        TradeHistoryFilter(symbol="BTCUSDT", status=BasketStatus.CLOSED),
        PageRequest(page=1, page_size=50),
    )
    assert pool.waitForDone(1_000)


def test_invalid_filter_emits_validation_without_query() -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: calls.append((filters, request)) or page_with(),
        list_fills=lambda basket_id: (),
    )
    messages: list[str] = []
    workflow.filter_invalid.connect(messages.append)

    workflow.apply_filters(
        TradeHistoryFilterValues(
            from_date=date(2026, 1, 3),
            to_date=date(2026, 1, 2),
        )
    )

    assert messages == ["From Date must not be after To Date"]
    assert calls == []
    assert pool.waitForDone(1_000)


def test_page_request_stays_within_known_bounds(qtbot: QtBot) -> None:
    calls: list[PageRequest] = []

    def list_baskets(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        calls.append(request)
        return page_with(basket_result(), page=request.page, total_items=51)

    workflow, pool = workflow_with(list_baskets=list_baskets, list_fills=lambda basket_id: ())
    workflow.start()
    qtbot.waitUntil(lambda: len(calls) == 1)

    workflow.go_to_page(0)
    workflow.go_to_page(3)
    workflow.go_to_page(2)

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls == [PageRequest(page=1, page_size=50), PageRequest(page=2, page_size=50)]
    assert pool.waitForDone(1_000)


def test_basket_failure_is_sanitized_and_retry_reuses_latest_request(qtbot: QtBot) -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []

    def fail_then_succeed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        calls.append((filters, request))
        if len(calls) == 1:
            raise RuntimeError("SQLite failed at /private/tmp/history.sqlite3")
        return page_with()

    workflow, pool = workflow_with(list_baskets=fail_then_succeed, list_fills=lambda basket_id: ())
    messages: list[str] = []
    workflow.baskets_unavailable.connect(messages.append)
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    qtbot.waitUntil(lambda: messages == ["Trade History unavailable"])

    workflow.retry_baskets()

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls[1] == calls[0]
    assert "/private/tmp" not in messages[0]
    assert pool.waitForDone(1_000)
```

- [ ] **Step 3: Write failing generation and close lifecycle tests**

```python
def test_new_filter_supersedes_running_basket_request(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    old_basket = basket_result(symbol="OLD")
    new_basket = basket_result(
        basket_id=UUID("00000000-0000-0000-0000-000000000199"),
        symbol="BTCUSDT",
    )
    calls = 0

    def delayed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            assert release.wait(timeout=2)
            return page_with(old_basket)
        return page_with(new_basket)

    workflow, pool = workflow_with(list_baskets=delayed, list_fills=lambda basket_id: ())
    pages: list[BasketHistoryPage] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.start()
    qtbot.waitUntil(started.is_set)
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    release.set()

    qtbot.waitUntil(lambda: len(pages) == 1)
    assert pages[0].items == (new_basket,)
    assert pool.waitForDone(1_000)


def test_new_selection_supersedes_running_fill_request(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    first = basket_result()
    second = basket_result(basket_id=UUID("00000000-0000-0000-0000-000000000299"))
    first_fill = trade_fill()
    second_fill = trade_fill(basket_id=second.basket_id, fill_id="fill-2")

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        if basket_id == first.basket_id:
            started.set()
            assert release.wait(timeout=2)
            return (first_fill,)
        return (second_fill,)

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(first, second),
        list_fills=delayed_fills,
    )
    results: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    workflow.fills_ready.connect(lambda basket_id, fills: results.append((basket_id, fills)))
    workflow.start()
    qtbot.waitUntil(started.is_set)
    workflow.select_basket(second.basket_id)
    release.set()

    qtbot.waitUntil(lambda: len(results) == 1)
    assert results == [(second.basket_id, (second_fill,))]
    assert pool.waitForDone(1_000)


def test_close_suppresses_late_results_and_finished_cleans_tasks(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()

    def delayed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        started.set()
        assert release.wait(timeout=2)
        return page_with(basket_result())

    workflow, pool = workflow_with(list_baskets=delayed, list_fills=lambda basket_id: ())
    pages: list[BasketHistoryPage] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.start()
    qtbot.waitUntil(started.is_set)

    workflow.close()
    release.set()

    assert pool.waitForDone(1_000)
    qtbot.wait(20)
    assert pages == []
    assert workflow._basket_task is None
    assert workflow._fill_task is None
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_workflow.py -q
```

Expected: FAIL because `TradeHistoryWorkflow` does not exist.

- [ ] **Step 5: Implement serialized latest-request queues per operation**

```python
ListBaskets = Callable[[TradeHistoryFilter, PageRequest], BasketHistoryPage]
ListFills = Callable[[UUID], tuple[TradeFill, ...]]


class TradeHistoryWorkflow(QObject):
    baskets_loading = Signal(bool)
    baskets_ready = Signal(object)
    baskets_empty = Signal()
    baskets_unavailable = Signal(str)
    filter_invalid = Signal(str)
    fills_loading = Signal(bool)
    fills_ready = Signal(object, object)
    fills_empty = Signal(object)
    fills_unavailable = Signal(object, str)

    PAGE_SIZE = 50
```

Keep one active and one latest pending request for Basket operations, and the same for
Fill operations. Every new request increments the relevant generation; stale semantic
results are ignored, `finished` disconnects callbacks and starts only the latest pending
request. Emit semantic result before the matching loading false signal. Basket requests
invalidate Fill generation and selection. `retry_baskets()` repeats the latest failed
Basket request and `retry_fills()` repeats the latest failed Fill request for the current
selection only. `close()` rejects new work and invalidates both generations.

- [ ] **Step 6: Run GREEN, regression and static checks**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_workflow.py tests/unit/ui/test_background_task.py tests/unit/ui/test_session_workflow.py -q
../../.venv/bin/python -m ruff check src/tiewtrade/ui tests/unit/ui
../../.venv/bin/python -m mypy src/tiewtrade/ui
```

Expected: all tests and checks PASS without Qt warnings.

- [ ] **Step 7: Commit Task 3**

```bash
git add src/tiewtrade/ui/trade_history_workflow.py tests/unit/ui/test_trade_history_workflow.py
git commit -m "feat: coordinate Trade History queries"
```

---

### Task 4: Build the two-table TradeHistoryPage

**Files:**
- Create: `src/tiewtrade/ui/trade_history_page.py`
- Create: `tests/unit/ui/test_trade_history_page.py`
- Modify: `src/tiewtrade/ui/theme.py`

**Interfaces:**
- Consumes: `TradeHistoryFilterValues`, `BasketHistoryPage`, presenter row functions and semantic workflow results
- Produces: `TradeHistoryPage` request signals and display slots consumed by Task 5

- [ ] **Step 1: Write failing layout and column tests**

```python
def test_page_exposes_filters_and_exact_table_columns(qtbot: QtBot) -> None:
    page = TradeHistoryPage()
    qtbot.addWidget(page)

    assert page.basket_headers == (
        "Opened At", "Mode", "Market", "Symbol", "Timeframe", "Entries",
        "Notional", "Gross PnL", "Fees", "Funding Fee", "Net PnL", "Status",
    )
    assert page.fill_headers == (
        "Filled At", "Side", "Entry #", "Price", "Quantity", "Notional",
        "Commission", "Realized PnL", "Source",
    )
    assert [page.symbol.itemText(index) for index in range(page.symbol.count())] == [
        "All", "BTCUSDT"
    ]
```

- [ ] **Step 2: Write failing interaction and state tests**

```python
def test_apply_and_reset_emit_immutable_filter_values(qtbot: QtBot) -> None:
    page = TradeHistoryPage()
    emitted: list[TradeHistoryFilterValues] = []
    resets: list[None] = []
    page.apply_filters_requested.connect(emitted.append)
    page.reset_requested.connect(lambda: resets.append(None))
    page.symbol.setCurrentIndex(page.symbol.findData("BTCUSDT"))

    qtbot.mouseClick(page.apply_button, Qt.MouseButton.LeftButton)
    assert emitted[-1].symbol == "BTCUSDT"

    qtbot.mouseClick(page.reset_button, Qt.MouseButton.LeftButton)
    assert resets == [None]
    assert page.filter_values() == TradeHistoryFilterValues()


def test_show_baskets_selects_first_row_without_parsing_cell_text(qtbot: QtBot) -> None:
    first = basket_result()
    second = basket_result(
        basket_id=UUID("00000000-0000-0000-0000-000000000202")
    )
    page = TradeHistoryPage()
    qtbot.addWidget(page)

    page.show_baskets(
        BasketHistoryPage(
            items=(first, second),
            page=1,
            page_size=50,
            total_items=2,
            net_realized_pnl=Decimal("39.16"),
        )
    )

    assert page.basket_table.currentRow() == 0
    assert page.basket_table.item(0, 0).data(Qt.ItemDataRole.UserRole) == first.basket_id


def test_summary_distinguishes_profit_loss_and_break_even_without_color(qtbot: QtBot) -> None:
    page = TradeHistoryPage()
    qtbot.addWidget(page)

    for value, semantic in [
        (Decimal("1"), "Profit"),
        (Decimal("-1"), "Loss"),
        (Decimal("0"), "Break-even"),
    ]:
        page.show_baskets(
            BasketHistoryPage(
                items=(), page=1, page_size=50, total_items=0,
                net_realized_pnl=value,
            )
        )
        assert semantic in page.total_net_pnl.text()


def test_basket_failure_hides_summary_and_clears_stale_rows(qtbot: QtBot) -> None:
    page = TradeHistoryPage()
    qtbot.addWidget(page)
    page.show_baskets(
        BasketHistoryPage(
            items=(basket_result(),), page=1, page_size=50, total_items=1,
            net_realized_pnl=Decimal("19.58"),
        )
    )
    page.show_fills(basket_result().basket_id, (trade_fill(),))

    page.show_baskets_unavailable("Trade History unavailable")

    assert page.basket_table.rowCount() == 0
    assert page.fill_table.rowCount() == 0
    assert page.total_net_pnl.isHidden()
    assert page.basket_state.text() == "Trade History unavailable"


def test_fill_failure_keeps_basket_rows_and_scopes_retry(qtbot: QtBot) -> None:
    basket = basket_result()
    page = TradeHistoryPage()
    qtbot.addWidget(page)
    page.show_baskets(
        BasketHistoryPage(
            items=(basket,), page=1, page_size=50, total_items=1,
            net_realized_pnl=Decimal("19.58"),
        )
    )

    page.show_fills_unavailable(basket.basket_id, "Trade Fills unavailable")

    assert page.basket_table.rowCount() == 1
    assert page.fill_table.rowCount() == 0
    assert page.fill_state.text() == "Trade Fills unavailable"
    assert page.retry_fills_button.isVisible()
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_page.py -q
```

Expected: FAIL because `TradeHistoryPage` does not exist.

- [ ] **Step 4: Implement the page and light-theme styles**

```python
class TradeHistoryPage(QWidget):
    apply_filters_requested = Signal(object)
    reset_requested = Signal()
    page_requested = Signal(int)
    basket_selected = Signal(object)
    baskets_retry_requested = Signal()
    fills_retry_requested = Signal()

    BASKET_HEADERS = (
        "Opened At", "Mode", "Market", "Symbol", "Timeframe", "Entries",
        "Notional", "Gross PnL", "Fees", "Funding Fee", "Net PnL", "Status",
    )
    FILL_HEADERS = (
        "Filled At", "Side", "Entry #", "Price", "Quantity", "Notional",
        "Commission", "Realized PnL", "Source",
    )
```

Use `QTableWidget` with row selection, read-only cells and UUID in
`Qt.ItemDataRole.UserRole`. Build optional dates with checkboxes plus `QDateEdit`.
Block table signals while rendering and selecting row 0 so Workflow remains the only
owner of automatic Fill loading. Add object names and stylesheet rules for filter cards,
tables, secondary buttons, summary labels, loading/empty/error states and selected rows.

- [ ] **Step 5: Run GREEN and static checks**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_trade_history_page.py tests/unit/ui/test_session_setup.py tests/unit/ui/test_main_window.py -q
../../.venv/bin/python -m ruff check src/tiewtrade/ui tests/unit/ui
../../.venv/bin/python -m ruff format --check src/tiewtrade/ui tests/unit/ui
../../.venv/bin/python -m mypy src/tiewtrade/ui
```

Expected: tests and checks PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add src/tiewtrade/ui/trade_history_page.py src/tiewtrade/ui/theme.py tests/unit/ui/test_trade_history_page.py
git commit -m "feat: add Trade History tables"
```

---

### Task 5: Wire navigation, workflows and Desktop composition

**Files:**
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `src/tiewtrade/ui/desktop.py`
- Modify: `src/tiewtrade/desktop_main.py`
- Modify: `tests/unit/ui/test_main_window.py`
- Modify: `tests/unit/test_desktop_main.py`
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Create: `tests/support/trade_history_ui.py`

**Interfaces:**
- Consumes: `TradeHistoryPage`, `TradeHistoryWorkflow`, `ListBaskets`, `ListFills`
- Produces: Desktop navigation and composition that inject both query callables without a UI-to-SQLite dependency

- [ ] **Step 1: Add failing MainWindow navigation tests**

```python
def test_navigation_opens_trade_history_without_active_session(qtbot: QtBot) -> None:
    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Trade History")
    assert window.trade_history.isVisible()
    assert window.trade_history.empty_message.text() == "No trade history"


def test_trade_history_remains_available_when_session_load_fails(qtbot: QtBot) -> None:
    def fail_load() -> ConfiguredPaperSession | None:
        raise PaperSessionUnavailableError("SQLite failed at /private/tmp/session.sqlite3")

    window = MainWindow(
        create_session=unused_create,
        load_active=fail_load,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.unavailable_panel.isVisible)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Trade History")
    assert window.trade_history.empty_message.text() == "No trade history"


def test_navigation_starts_history_query_only_once(qtbot: QtBot) -> None:
    calls = 0

    def count_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        nonlocal calls
        calls += 1
        return empty_basket_page(filters, request)

    window = MainWindow(
        create_session=unused_create,
        load_active=no_active_session,
        list_baskets=count_baskets,
        list_fills=empty_fills,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.setup.create_button.isEnabled)

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: calls == 1)
    qtbot.mouseClick(window.session_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    assert calls == 1
```

- [ ] **Step 2: Add failing composition tests**

```python
def test_desktop_composition_supplies_migrated_trade_history_queries(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    captured = capture_run_desktop_ui(monkeypatch)

    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0

    list_baskets = captured["list_baskets"]
    list_fills = captured["list_fills"]
    assert list_baskets(TradeHistoryFilter(), PageRequest()).items == ()
    assert list_fills(UUID("00000000-0000-0000-0000-000000000001")) == ()
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_main_window.py tests/unit/test_desktop_main.py -q
```

Expected: FAIL because MainWindow and Desktop composition do not accept History query callables.

- [ ] **Step 4: Implement focused navigation and wiring**

```python
class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        create_session: CreateSession,
        load_active: LoadActiveSession,
        list_baskets: ListBaskets,
        list_fills: ListFills,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.navigation_items = ("Session", "Trade History")
        self.trade_history = TradeHistoryPage()
        self._history_started = False
        self._history_workflow = TradeHistoryWorkflow(
            list_baskets=list_baskets,
            list_fills=list_fills,
            thread_pool=thread_pool,
            parent=self,
        )
```

Add exactly two navigation buttons. Keep Session Setup/Overview/Unavailable inside the
Session page stack and Trade History as the second top-level page. Connect Page requests
to Workflow operations and semantic results to Page display slots. Start History only on
its first navigation. Call both workflows' `close()` from `closeEvent`.

Use these composition wrappers in `desktop_main.py`:

```python
history = SQLiteTradeHistory(database)


def list_baskets_after_migration(
    filters: TradeHistoryFilter,
    page: PageRequest,
) -> BasketHistoryPage:
    prepare_database()
    return history.list_baskets(filters, page)


def list_fills_after_migration(basket_id: UUID) -> tuple[TradeFill, ...]:
    prepare_database()
    return history.list_fills(basket_id)
```

In `desktop_main.py`, create `SQLiteTradeHistory(database)` and inject wrappers that call
`prepare_database()` inside the worker before `list_baskets` or `list_fills`. Update direct
UI tests with reusable `empty_basket_page` and `empty_fills` support callables; do not add
production defaults that fabricate a successful empty query.

- [ ] **Step 5: Run GREEN, Session regression and static checks**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/ui/test_main_window.py tests/unit/test_desktop_main.py tests/acceptance/test_desktop_session_setup.py -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m mypy src
```

Expected: navigation/composition tests and all existing Session acceptance tests PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add src/tiewtrade/ui/main_window.py src/tiewtrade/ui/desktop.py src/tiewtrade/desktop_main.py tests/unit/ui/test_main_window.py tests/unit/test_desktop_main.py tests/acceptance/test_desktop_session_setup.py tests/support/trade_history_ui.py
git commit -m "feat: wire Trade History navigation"
```

---

### Task 6: Prove the durable Desktop Trade History acceptance flow

**Files:**
- Create: `tests/acceptance/test_desktop_trade_history.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: Desktop composition callables, `SQLiteTradeHistory`, presenter/workflow/page contracts from Tasks 2–5
- Produces: DEV-96 end-to-end acceptance evidence and delivery status for DEV-97

- [ ] **Step 1: Write failing durable Desktop acceptance tests**

```python
def test_desktop_trade_history_reads_durable_spot_and_futures_records(
    qtbot: QtBot, tmp_path: Path
) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    history = SQLiteTradeHistory(database)
    record_spot_and_futures_history(history)
    window = composed_window(database)
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 2)
    assert window.trade_history.basket_table.item(0, 2).text() == "Futures"
    assert window.trade_history.total_net_pnl.text().endswith("· Profit")
    qtbot.waitUntil(lambda: window.trade_history.fill_table.rowCount() > 0)


def test_desktop_trade_history_filters_paginates_and_survives_restart(
    qtbot: QtBot, tmp_path: Path
) -> None:
    path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(path)
    database.migrate()
    history = SQLiteTradeHistory(database)
    for index in range(51):
        basket_id = UUID(int=index + 1)
        opened_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
        _record_closed(
            history,
            basket_result(
                basket_id=basket_id,
                opened_at_utc=opened_at,
                closed_at_utc=opened_at + timedelta(hours=1),
                timeframe="15m" if index == 50 else "5m",
            ),
        )
    first = _window_for(history)
    qtbot.addWidget(first)
    first.show()
    qtbot.mouseClick(first.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 50)

    first.trade_history.timeframe.setCurrentIndex(
        first.trade_history.timeframe.findData("15m")
    )
    qtbot.mouseClick(first.trade_history.apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 1)
    assert first.trade_history.basket_table.item(0, 4).text() == "15m"

    qtbot.mouseClick(first.trade_history.reset_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 50)
    qtbot.mouseClick(first.trade_history.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: first.trade_history.basket_table.rowCount() == 1)
    first.close()

    reopened_history = SQLiteTradeHistory(SQLiteDatabase(path))
    restarted = _window_for(reopened_history)
    qtbot.addWidget(restarted)
    restarted.show()
    qtbot.mouseClick(restarted.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: restarted.trade_history.basket_table.rowCount() == 50)
    assert restarted.trade_history.page_label.text() == "Page 1 of 2"


def test_trade_history_read_failure_is_fail_closed_and_sanitized(qtbot: QtBot) -> None:
    def fail(filters: TradeHistoryFilter, page: PageRequest) -> BasketHistoryPage:
        raise TradeHistoryUnavailableError(
            "SQLite failed at /private/tmp/tiewtrade.sqlite3"
        )

    window = MainWindow(
        create_session=unused_create,
        load_active=lambda: None,
        list_baskets=fail,
        list_fills=lambda basket_id: (),
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.trade_history.basket_state.text() == "Trade History unavailable")

    assert window.trade_history.basket_table.rowCount() == 0
    assert window.trade_history.fill_table.rowCount() == 0
    assert window.trade_history.total_net_pnl.isHidden()
    assert "/private/tmp" not in window.trade_history.basket_state.text()


def test_trade_history_desktop_flow_has_no_forbidden_import_or_network(
    qtbot: QtBot, monkeypatch: MonkeyPatch
) -> None:
    forbidden = ("sqlite", "strategy", "execution", "binance", "aiohttp")
    for path in Path("src/tiewtrade/ui").glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert all(not any(name in module for name in forbidden) for module in imports)

    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail("network must not run"),
    )
    window = MainWindow(
        create_session=unused_create,
        load_active=lambda: None,
        list_baskets=lambda filters, page: BasketHistoryPage(
            items=(), page=1, page_size=50, total_items=0,
            net_realized_pnl=Decimal("0"),
        ),
        list_fills=lambda basket_id: (),
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.trade_history_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.trade_history.empty_message.text() == "No trade history")
```

Define `_record_closed()` in the same test file with exact durable calls:

```python
def _record_closed(history: SQLiteTradeHistory, closed: BasketResult) -> None:
    assert closed.closed_at_utc is not None
    opened = replace(
        closed,
        closed_at_utc=None,
        gross_realized_pnl=Decimal("0"),
        trading_fees=Decimal("0"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("0"),
        status=BasketStatus.OPEN,
    )
    buy = trade_fill(
        basket_id=opened.basket_id,
        session_id=opened.session_id,
        fill_id=f"{opened.basket_id}-buy",
        order_id=f"{opened.basket_id}-buy-order",
        filled_at_utc=opened.opened_at_utc,
    )
    sell = trade_fill(
        basket_id=closed.basket_id,
        session_id=closed.session_id,
        fill_id=f"{closed.basket_id}-sell",
        order_id=f"{closed.basket_id}-sell-order",
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=closed.closed_at_utc,
        realized_pnl=closed.net_realized_pnl,
    )
    history.record_open_basket(opened, buy)
    history.record_closed_basket(closed, sell)
```

- [ ] **Step 2: Run RED acceptance tests**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/acceptance/test_desktop_trade_history.py -q
```

Expected: at least one assertion fails until final interaction/composition gaps are completed.

- [ ] **Step 3: Make the smallest integration fixes required by acceptance**

Only modify DEV-96 UI/workflow/composition files when the acceptance failure proves a
missing behavior. Do not change Trade History schema, query ordering or PnL calculations.

- [ ] **Step 4: Record delivery status without changing milestone order**

Add a status paragraph under Milestone 3 after the DEV-115/116 recovery status:

```markdown
สถานะ DEV-96: Desktop Trade History แสดง Basket History และ Trade Fills ของทุก
Session ผ่าน application query แบบ filter/pagination บน background worker พร้อม
Total Net PnL, UTC date range, accessible PnL state และ scoped unavailable states แล้ว
งานนี้ปลด prerequisite ด้าน UI เพื่อเริ่ม DEV-97 แต่ยังไม่ทำให้ Paper Trading Complete
จนกว่า acceptance, Stop Session และ startup Recovery ที่เหลือจะผ่าน
```

- [ ] **Step 5: Run focused and full verification**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/acceptance/test_desktop_trade_history.py tests/acceptance/test_desktop_session_setup.py -q
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
env PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check 064c5cf HEAD
git diff --check
```

Expected: all Python tests, Ruff, format, Mypy, docs tests, content and whitespace checks PASS.

- [ ] **Step 6: Commit Task 6**

```bash
git add tests/acceptance/test_desktop_trade_history.py PROJECT_PLAN.md src/tiewtrade/ui src/tiewtrade/desktop_main.py tests/unit tests/support
git commit -m "test: prove Desktop Trade History flow"
```
