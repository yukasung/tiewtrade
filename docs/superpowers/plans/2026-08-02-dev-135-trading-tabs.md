# DEV-135 Trading Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** แสดง Open Orders, Position / Basket และ durable Trade History ใน Bottom Tabs หน้าเดียว โดยแต่ละ Tab มี Loading, Empty, Error และ Stale state ของตนเอง

**Architecture:** ขยาย immutable `TradingWorkspaceSnapshot` ด้วย concrete tab snapshots ที่ application เป็นเจ้าของ จากนั้นให้ focused PySide6 widgets render facts โดยไม่คำนวณ PnL หรือ execution result เอง Trade History ใช้ query/workflow เดิมและรักษา last-known durable rows เมื่อ refresh ล้มเหลว ส่วน Runtime source จริงยังอยู่ใน DEV-136

**Tech Stack:** Python 3.12, immutable dataclasses, PySide6, SQLite, pytest/pytest-qt, Ruff, Mypy

## Global Constraints

- UI เป็นภาษาอังกฤษและใช้ Full Dark Theme กับ TiewTrade Blue ตาม `docs/superpowers/specs/2026-07-30-unified-trading-workspace-design.md`
- Bot เป็นผู้สร้างคำสั่งเท่านั้น; ห้ามเพิ่ม Manual Buy/Sell หรือ order-entry controls
- Trade History ต้องเปิดดูได้เสมอแม้ไม่มี Active Bot Session
- Open Orders, Position / Basket และ Trade History ต้องมี Loading, Empty, Error และ Stale state แยกจากกัน
- UI ห้าม import SQLite, Strategy, Binance SDK หรือ Execution adapter และห้ามคำนวณ business PnL หรือ authoritative Live facts
- `Decimal` ต้องคง exact text และเวลาต้องเป็น UTC; ห้ามแปลงผ่าน `float` หรือ local timezone
- หนึ่ง Order แสดงเป็นหนึ่ง row แม้มีหลาย Partial Fills และ Partial Fill ของ Order เดิมต้องไม่เพิ่ม Basket `entry_count`
- Spot liquidation แสดง `—`; Futures แสดง application-provided liquidation fact เท่านั้น
- ใช้ Paper/Fake adapters ระหว่างพัฒนาและทดสอบ ห้ามเพิ่ม network, credentials, Binance Private API หรือ Live order side effect
- DEV-135 ไม่เพิ่ม Runtime source, schema สำหรับ Open Orders หรือ Market Data orchestration; งานเหล่านี้เป็น DEV-136

---

### Task 1: Independent Trading Tab Read Models

**Files:**
- Modify: `src/tiewtrade/application/trading_workspace.py`
- Modify: `src/tiewtrade/application/bot_control.py`
- Test: `tests/unit/application/test_trading_workspace.py`
- Test: `tests/unit/application/test_bot_control.py`

**Interfaces:**
- Produces: `WorkspaceTabState`, `OpenOrdersTabSnapshot`, `PositionBasketTabSnapshot`
- Produces: `empty_open_orders_tab()`, `ready_open_orders_tab()`, `loading_open_orders_tab()`, `failed_open_orders_tab()`, `stale_open_orders_tab()`
- Produces: corresponding `*_position_basket_tab()` helpers
- Preserves: `TradingWorkspaceSnapshot.orders` and `.basket` as read-only convenience properties for existing Bot Control consumers

- [ ] **Step 1: Write failing validation and state-isolation tests**

Add tests that define the concrete contract before production changes:

```python
def test_open_orders_tab_aggregates_one_row_per_order_and_sorts_latest_first() -> None:
    older = _order(_utc(minute=1), order_id="order-1", filled="0.001")
    newer = _order(_utc(minute=2), order_id="order-2", filled="0.002")

    tab = ready_open_orders_tab((older, newer), observed_at_utc=_utc(minute=3))

    assert tab.state is WorkspaceTabState.READY
    assert tuple(item.order_id for item in tab.orders) == ("order-2", "order-1")


def test_open_orders_tab_rejects_duplicate_order_rows_and_overfill() -> None:
    order = _order(_utc(), order_id="order-1", filled="0.003")
    with pytest.raises(ValueError, match="order_id must be unique"):
        ready_open_orders_tab((order, order), observed_at_utc=_utc(minute=1))
    with pytest.raises(ValueError, match="filled_quantity must not exceed quantity"):
        replace(order, filled_quantity=Decimal("0.004"))


def test_orders_and_position_tabs_transition_independently() -> None:
    orders = ready_open_orders_tab((_order(_utc()),), observed_at_utc=_utc())
    position = ready_position_basket_tab(_basket(_utc()), observed_at_utc=_utc())

    snapshot = replace(
        configured_workspace_snapshot(configured_spot_session(), observed_at_utc=_utc()),
        open_orders=loading_open_orders_tab(orders),
        position_basket=stale_position_basket_tab(position),
    )

    assert snapshot.open_orders.state is WorkspaceTabState.LOADING
    assert snapshot.position_basket.state is WorkspaceTabState.STALE
    assert snapshot.orders == orders.orders
    assert snapshot.basket == position.basket
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_trading_workspace.py \
  tests/unit/application/test_bot_control.py -q
```

Expected: FAIL because the tab snapshot types and helpers do not exist.

- [ ] **Step 3: Implement immutable tab snapshots and invariants**

Use concrete dataclasses rather than a generic UI-state framework:

```python
class WorkspaceTabState(StrEnum):
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    ERROR = "error"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class OpenOrdersTabSnapshot:
    state: WorkspaceTabState
    orders: tuple[OpenOrderSnapshot, ...]
    data_as_of_utc: datetime | None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class PositionBasketTabSnapshot:
    state: WorkspaceTabState
    basket: BasketSnapshot | None
    data_as_of_utc: datetime | None
    message: str | None = None
```

Enforce these exact state rules:

- `EMPTY`: no durable item and no message
- `READY`: required durable item(s), UTC `data_as_of_utc`, no message
- `LOADING`: preserves last-known item(s), no message
- `ERROR`: preserves last-known item(s) and requires sanitized display message
- `STALE`: preserves last-known item(s), requires UTC `data_as_of_utc`, no raw message

`ready_open_orders_tab()` must sort by `(created_at_utc, order_id)` descending and reject duplicate `order_id`. Add `filled_quantity <= quantity` to `OpenOrderSnapshot` validation.

Change `TradingWorkspaceSnapshot` to own `open_orders` and `position_basket`, then expose compatibility properties:

```python
@property
def orders(self) -> tuple[OpenOrderSnapshot, ...]:
    return self.open_orders.orders

@property
def basket(self) -> BasketSnapshot | None:
    return self.position_basket.basket
```

Update `_require_workspace_continuity()` to compare the two complete tab snapshots so a lifecycle transition cannot silently change rows or scoped states.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all focused tests pass.

- [ ] **Step 5: Commit the application contract**

```bash
git add src/tiewtrade/application/trading_workspace.py \
  src/tiewtrade/application/bot_control.py \
  tests/unit/application/test_trading_workspace.py \
  tests/unit/application/test_bot_control.py
git commit -m "feat: model independent trading tab states"
```

---

### Task 2: Spot Partial Fill Entry Ownership

**Files:**
- Modify: `src/tiewtrade/integrations/sqlite/paper_spot_history.py`
- Test: `tests/unit/integrations/sqlite/test_paper_spot_history.py`

**Interfaces:**
- Consumes: existing `SQLiteTradeHistory.list_fills()` and `record_entry_fill()`
- Preserves: one `BasketResult` per Basket and one `entry_count` increment per unique `order_id`

- [ ] **Step 1: Write a failing Spot partial-fill test**

```python
def test_partial_fill_for_same_spot_order_does_not_increment_entry_count(
    history: PaperSpotSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    first = _entry_fill(order_id="entry-order-1", fill_id="fill-1", quantity="0.001")
    partial = _entry_fill(
        order_id="entry-order-1",
        fill_id="fill-2",
        quantity="0.0005",
    )

    assert history.record_entry(basket_id=BASKET_ID, entry_number=1, fill=first)
    assert history.record_entry(basket_id=BASKET_ID, entry_number=1, fill=partial)

    basket = store.get_basket(BASKET_ID)
    assert basket is not None
    assert basket.entry_count == 1
    assert tuple(fill.order_id for fill in store.list_fills(BASKET_ID)) == (
        "entry-order-1",
        "entry-order-1",
    )
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  -k partial_fill -q
```

Expected: FAIL because Spot currently increments `entry_count` for every Fill.

- [ ] **Step 3: Reuse the existing order ownership rule**

Before replacing the Basket, read existing Fills and preserve `entry_count` when the incoming `order_id` already exists:

```python
order_already_filled = any(
    item.order_id == normalized_fill.order_id
    for item in self._store.list_fills(basket_id)
)
entry_count = (
    existing.entry_count
    if order_already_filled
    else existing.entry_count + 1
)
```

Continue adding exact notional and commission for every Partial Fill. Do not create a second Basket and do not change SQLite schema.

- [ ] **Step 4: Run Spot and generic Trade History tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_trade_history.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the Partial Fill fix**

```bash
git add src/tiewtrade/integrations/sqlite/paper_spot_history.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py
git commit -m "fix: preserve spot entry count across partial fills"
```

---

### Task 3: Open Orders and Position / Basket Widgets

**Files:**
- Create: `src/tiewtrade/ui/open_orders_table.py`
- Create: `src/tiewtrade/ui/position_basket_table.py`
- Test: `tests/unit/ui/test_open_orders_table.py`
- Test: `tests/unit/ui/test_position_basket_table.py`

**Interfaces:**
- Consumes: `OpenOrdersTabSnapshot` and `PositionBasketTabSnapshot`
- Produces: `OpenOrdersTable.show_snapshot(object)` and `PositionBasketTable.show_snapshot(object)`
- Does not import persistence, strategy, Binance or execution modules

- [ ] **Step 1: Write failing Open Orders widget tests**

```python
def test_open_orders_table_renders_all_authoritative_columns(qtbot: QtBot) -> None:
    widget = OpenOrdersTable()
    qtbot.addWidget(widget)
    widget.show_snapshot(
        ready_open_orders_tab((_order(),), observed_at_utc=OBSERVED_AT)
    )

    assert widget.headers == (
        "Order ID", "Created Time", "Symbol", "Side", "Type",
        "Price", "Quantity", "Filled Quantity", "Status",
    )
    assert _row(widget.table, 0) == (
        "order-1", "2026-08-02 01:02:03 UTC", "BTCUSDT", "Buy", "Limit",
        "66321.1200", "0.00300000", "0.00100000", "Partially Filled",
    )


def test_open_orders_error_and_stale_keep_last_known_rows(qtbot: QtBot) -> None:
    widget = OpenOrdersTable()
    qtbot.addWidget(widget)
    ready = ready_open_orders_tab((_order(),), observed_at_utc=OBSERVED_AT)

    widget.show_snapshot(failed_open_orders_tab(ready, "Open Orders unavailable"))
    assert widget.table.rowCount() == 1
    assert widget.state_label.text() == "Open Orders unavailable"

    widget.show_snapshot(stale_open_orders_tab(ready))
    assert widget.table.rowCount() == 1
    assert widget.state_label.text().startswith("Stale")
```

- [ ] **Step 2: Write failing Position / Basket widget tests**

```python
def test_position_basket_renders_application_facts_without_recalculation(
    qtbot: QtBot,
) -> None:
    widget = PositionBasketTable()
    qtbot.addWidget(widget)
    widget.show_snapshot(
        ready_position_basket_tab(_futures_basket(), observed_at_utc=OBSERVED_AT)
    )

    assert _row(widget.table, 0) == (
        "BTCUSDT", "Futures", "2", "0.00600000", "66000.1250",
        "66321.1200", "67000.0000", "1.92600000 USDT · Profit",
        "44000.5000", "Active Pair",
    )


def test_spot_position_displays_no_liquidation_price(qtbot: QtBot) -> None:
    widget = PositionBasketTable()
    qtbot.addWidget(widget)
    widget.show_snapshot(
        ready_position_basket_tab(_spot_basket(), observed_at_utc=OBSERVED_AT)
    )
    assert widget.table.item(0, 8).text() == "—"
```

- [ ] **Step 3: Run widget tests and verify RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/ui/test_open_orders_table.py \
  tests/unit/ui/test_position_basket_table.py -q
```

Expected: FAIL because the widgets do not exist.

- [ ] **Step 4: Implement focused read-only tables**

Each widget uses `QTableWidget` configured with row selection, no editing, alternating rows, stretch-last-column and horizontal scrolling. `show_snapshot()` must:

- render values from immutable snapshot only
- keep rows for `LOADING`, `ERROR` and `STALE` when last-known rows exist
- show exact scoped state text and accessible name
- clear rows for honest `EMPTY`
- ignore an object of the wrong type

Use `format(value, "f")` for Decimal, `strftime("%Y-%m-%d %H:%M:%S UTC")` for UTC and enum-like text formatting via `value.replace("_", " ").title()`. PnL labeling may classify the provided value as Profit/Loss/Break-even but must not derive the numeric PnL.

- [ ] **Step 5: Run widget tests and verify GREEN**

Run the command from Step 3. Expected: all tests pass.

- [ ] **Step 6: Commit the widgets**

```bash
git add src/tiewtrade/ui/open_orders_table.py \
  src/tiewtrade/ui/position_basket_table.py \
  tests/unit/ui/test_open_orders_table.py \
  tests/unit/ui/test_position_basket_table.py
git commit -m "feat: render bot orders and basket tables"
```

---

### Task 4: Workspace Integration and Durable Trade History Stale State

**Files:**
- Modify: `src/tiewtrade/ui/trading_workspace.py`
- Modify: `src/tiewtrade/ui/trade_history_page.py`
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `src/tiewtrade/ui/theme.py`
- Test: `tests/unit/ui/test_trading_workspace.py`
- Test: `tests/unit/ui/test_trade_history_page.py`
- Test: `tests/unit/ui/test_main_window.py`
- Test: `tests/unit/ui/test_theme.py`

**Interfaces:**
- Consumes: focused widgets from Task 3
- Preserves: existing `TradeHistoryWorkflow` filters, pagination, Basket selection, Fill details and generation guards
- Preserves: Trade History lazy activation even when no Active Session exists

- [ ] **Step 1: Write failing workspace integration tests**

```python
def test_workspace_tabs_render_independent_scoped_states(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    snapshot = _workspace_with(
        open_orders=loading_open_orders_tab(_ready_orders()),
        position_basket=ready_position_basket_tab(
            _basket(), observed_at_utc=OBSERVED_AT
        ),
    )

    workspace.show_workspace_snapshot(snapshot)

    assert workspace.open_orders.state_label.text().startswith("Loading")
    assert workspace.open_orders.table.rowCount() == 1
    assert workspace.position_basket.state_label.text() == ""
    assert workspace.position_basket.table.rowCount() == 1
```

Replace assertions against the old placeholder labels with assertions against the focused table widgets. Keep the tab labels and active-tab persistence tests.

- [ ] **Step 2: Write failing Trade History stale-preservation tests**

```python
def test_basket_refresh_failure_keeps_last_known_durable_rows(qtbot: QtBot) -> None:
    page = TradeHistoryPage()
    qtbot.addWidget(page)
    page.show_baskets(_basket_page(_closed_basket()))

    page.set_baskets_loading(True)
    page.show_baskets_unavailable("Trade History unavailable")

    assert page.basket_table.rowCount() == 1
    assert page.basket_state.text() == "Stale · Trade History unavailable"
    assert page.retry_baskets_button.isVisible()


def test_fill_refresh_failure_does_not_clear_basket_or_last_known_fills(
    qtbot: QtBot,
) -> None:
    page = TradeHistoryPage()
    qtbot.addWidget(page)
    basket_id = UUID("00000000-0000-0000-0000-000000000001")
    page.show_baskets(_basket_page(_closed_basket(basket_id=basket_id)))
    page.show_fills(basket_id, (_fill(basket_id=basket_id),))

    page.show_fills_unavailable(basket_id, "Trade Fills unavailable")

    assert page.basket_table.rowCount() == 1
    assert page.fill_table.rowCount() == 1
    assert page.fill_state.text() == "Stale · Trade Fills unavailable"
```

- [ ] **Step 3: Run integration-focused UI tests and verify RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/ui/test_trading_workspace.py \
  tests/unit/ui/test_trade_history_page.py \
  tests/unit/ui/test_main_window.py \
  tests/unit/ui/test_theme.py -q
```

Expected: FAIL because Workspace still uses placeholder panels and Trade History clears durable rows.

- [ ] **Step 4: Integrate widgets and preserve durable Trade History rows**

In `TradingWorkspace`:

```python
self.open_orders = OpenOrdersTable()
self.position_basket = PositionBasketTable()
self.tabs.addTab(self.open_orders, "Open Orders")
self.tabs.addTab(self.position_basket, "Position / Basket")
self.tabs.addTab(self.trade_history, "Trade History")
```

`show_workspace_snapshot()` forwards only `value.open_orders` and `value.position_basket` to their widgets. Remove `_show_placeholder_states()` and the old placeholder labels.

In `TradeHistoryPage`, track whether each scope has a durable result:

```python
self._has_basket_result = False
self._fill_result_basket_id: UUID | None = None
```

Set those markers after successful ready/empty results. Loading keeps last-known rows visible and shows scoped loading text. On unavailable:

- if a durable result exists for the same scope, keep rows/summary/pagination and show `Stale · <sanitized message>`
- if no durable result exists, clear the scope and show the existing unavailable state
- Fill failure must never clear the Basket table

Add theme selectors for scoped state labels and ensure stale/error meaning uses text in addition to semantic color.

- [ ] **Step 5: Run focused UI tests and verify GREEN**

Run the command from Step 3. Expected: all tests pass.

- [ ] **Step 6: Commit Workspace integration**

```bash
git add src/tiewtrade/ui/trading_workspace.py \
  src/tiewtrade/ui/trade_history_page.py \
  src/tiewtrade/ui/main_window.py \
  src/tiewtrade/ui/theme.py \
  tests/unit/ui/test_trading_workspace.py \
  tests/unit/ui/test_trade_history_page.py \
  tests/unit/ui/test_main_window.py \
  tests/unit/ui/test_theme.py
git commit -m "feat: integrate independent trading workspace tabs"
```

---

### Task 5: DEV-135 Acceptance and Project Status

**Files:**
- Modify: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `tests/acceptance/test_desktop_trade_history.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Verifies: Paper Spot and Paper Futures snapshots render without Runtime or network side effects
- Verifies: Trade History remains available with no Active Session
- Documents: DEV-135 delivery boundary and DEV-136 remaining Runtime ownership

- [ ] **Step 1: Write a failing acceptance test for the complete tab slice**

Use fake application snapshots and existing SQLite Trade History fixtures:

```python
def test_workspace_shows_orders_basket_and_history_without_manual_trading(
    qtbot: QtBot,
) -> None:
    window = _window_with_fake_workspace_snapshot(_running_workspace())
    qtbot.addWidget(window)

    assert window.workspace.open_orders.table.rowCount() == 1
    assert window.workspace.position_basket.table.rowCount() == 1
    window.workspace.tabs.setCurrentWidget(window.trade_history)
    qtbot.waitUntil(lambda: window.trade_history.basket_table.rowCount() == 1)
    assert "Buy" not in _button_texts(window)
    assert "Sell" not in _button_texts(window)
```

Also assert one Partial Fill Order row maps to one Basket row with unchanged `entry_count`, and switch to Trade History in a no-session window to prove its query starts independently.

- [ ] **Step 2: Run acceptance tests and verify RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_desktop_session_setup.py \
  tests/acceptance/test_desktop_trade_history.py -q
```

Expected: FAIL until the fake lifecycle snapshot is displayed through the integrated tabs.

- [ ] **Step 3: Complete the acceptance seam without production Runtime**

Wire the test fake through the existing `LifecycleAction -> BotLifecycleResult -> TradingWorkspaceSnapshot` boundary. Do not add production network, SQLite order schema, runtime start/stop or execution composition.

- [ ] **Step 4: Update the delivery status**

Add a DEV-135 paragraph under Milestone 3 in `PROJECT_PLAN.md` stating:

- independent Open Orders and Position/Basket tabs now render immutable application facts
- durable Trade History retains filters, pagination, details and stale last-known results
- Spot Partial Fill ownership preserves one Basket entry per Order
- Runtime source and authoritative refresh remain DEV-136

- [ ] **Step 5: Run all repository quality gates**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main HEAD
```

Expected: every command exits `0`.

- [ ] **Step 6: Commit acceptance and status documentation**

```bash
git add tests/acceptance/test_desktop_session_setup.py \
  tests/acceptance/test_desktop_trade_history.py PROJECT_PLAN.md
git commit -m "test: verify DEV-135 trading tabs acceptance"
```

---

## Plan Self-Review

- Acceptance criteria mapping: Task 1 covers independent state contracts and order aggregation; Task 2 covers Partial Fill Basket ownership; Tasks 3–4 cover all visible fields and scoped states; Task 4 preserves Trade History behavior; Task 5 covers no-session and full acceptance.
- Dependency check: DEV-133/134 contracts are preserved; no DEV-136 Runtime implementation is pulled forward.
- Boundary check: UI only consumes immutable application snapshots; SQLite change is restricted to existing Paper Spot history ownership behavior.
- Placeholder scan: the plan contains no deferred implementation placeholders or unspecified production behavior.
- Type check: all downstream widgets consume the concrete snapshot types introduced in Task 1.
