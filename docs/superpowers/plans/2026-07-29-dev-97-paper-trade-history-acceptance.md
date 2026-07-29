# DEV-97 Paper Trade History Acceptance Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to
> implement this plan task-by-task, with TDD for every production behavior change.

**Goal:** พิสูจน์ Paper Spot/Futures Trade History ตั้งแต่ production Paper execution
ผ่าน durable SQLite, restart boundary, application query และ Desktop UI พร้อมหลักฐาน
Open Basket, duplicate/Partial Fill และ persistence fail-closed ครบตาม DEV-97

**Architecture:** ใช้ concrete Paper Spot/Futures Sessions และ SQLite coordinators
ที่มีอยู่สร้าง durable records ใน temporary database เดียว จากนั้นสร้าง database/store
objects ชุดใหม่เพื่ออ่านผ่าน application query และ Desktop composition จริง เพิ่ม
direct normalized persistence scenario เฉพาะ Partial Fill ซึ่ง Paper executor v1
ยังไม่จำลอง และไม่สร้าง production abstraction ใหม่หาก acceptance tests ไม่พบ defect

**Tech Stack:** Python 3.12+, pytest, pytest-qt, PySide6, SQLite, Ruff, mypy,
Nextra documentation checks

---

## Global Constraints

- ใช้ `TradeMode.PAPER`, fake/local data และ temporary SQLite เท่านั้น
- ห้ามเรียก Binance Private API, Live order, OS Keyring หรือ credentials
- ปิด network ใน cross-layer Desktop scenario และ fail test ทันทีหากมี connection
- ใช้ completed candles แบบ deterministic; ไม่มีการดาวน์โหลดข้อมูลระหว่าง test
- ใช้ production Paper Sessions, persistence coordinators, application queries และ
  Desktop composition จริงใน cross-layer scenario
- Open Basket ต้องไม่ถูกรวมใน closed Net PnL
- duplicate Fill ต้องเป็น idempotent no-op; Partial Fills ของ Order เดียวกันต้องคง
  `entry_count` เดิมและเรียง deterministic
- persistence failure ต้อง rollback transaction และ block candle ถัดไปก่อน core
  Session ประมวลผล
- ไม่สร้าง generic interface, repository, factory หรือ acceptance coordinator ใหม่
- การเพิ่ม acceptance test เพื่อพิสูจน์ behavior เดิมอาจผ่านตั้งแต่ครั้งแรกได้; หากต้อง
  แก้ production code ต้องเพิ่ม focused failing test และเห็น RED ที่ตรงสาเหตุก่อนเสมอ
- UI ต้องอ่านผ่าน callables ที่ compose ใน `desktop_main`; ห้าม import SQLite,
  Strategy หรือ Execution เข้า `ui`
- UI error ต้องเป็น sanitized unavailable state และไม่แสดง path/error ภายใน

## Task 1: Cross-layer Paper Execution, Restart and Desktop Proof

**Files:**

- Create: `tests/support/paper_trade_history_acceptance.py`
- Create: `tests/acceptance/test_paper_trade_history_acceptance.py`
- Read/verify: `tests/acceptance/test_paper_spot_trade_history.py`
- Read/verify: `tests/acceptance/test_paper_futures_trade_history.py`
- Read/verify: `tests/acceptance/test_desktop_trade_history.py`

### Step 1: Add focused deterministic test builders

Create test support with constants that do not collide with existing acceptance tests:

```python
SPOT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000401")
FUTURES_SESSION_ID = UUID("00000000-0000-0000-0000-000000000402")
OPEN_SPOT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000403")
```

Add builders with explicit inputs and production return types:

```python
def build_spot_session(session_id: UUID) -> PaperSpotSession: ...
def build_futures_session(session_id: UUID) -> PaperFuturesSession: ...
def spot_history(session_id: UUID, store: SQLiteTradeHistory) -> PaperSpotSQLiteHistory: ...
def futures_history(
    session_id: UUID, store: SQLiteTradeHistory
) -> PaperFuturesSQLiteHistory: ...
def spot_candles() -> tuple[Candle, ...]: ...
def futures_candles() -> tuple[Candle, ...]: ...
```

Use the approved values already exercised by existing acceptance tests:

- Symbol `BTCUSDT`, Timeframe `5m`, Preset `rsi-step-grid-v1`
- Spot capital `1000`, trading ratio `0.6`, `max_entries=4`
- Futures capital `200000`, leverage `3`, `max_entries=10`
- fee rate `0.001`, slippage `2` bps
- Spot symbol rules: tick `0.01`, step `0.001`, min notional `5`
- Futures symbol rules: tick `0.1`, step `0.001`, min notional `5`
- Spot candles from `tests/fixtures/btcusdt_5m_tracer.csv`
- Futures candles copy the deterministic down-then-up series used by the existing
  Paper Futures acceptance test

Provide helpers that return the closed Basket ID only after seeing a real close:

```python
def run_closed_spot(store: SQLiteTradeHistory) -> UUID: ...
def run_closed_futures(store: SQLiteTradeHistory) -> UUID: ...
```

Each helper must assert every returned persistent snapshot is `PersistenceState.READY`
and fail explicitly when the deterministic sequence does not close a Basket.

### Step 2: Write the cross-layer acceptance test

Add:

```python
def test_paper_execution_history_survives_restart_and_reaches_desktop(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
) -> None:
    ...
```

The test must:

1. Create/migrate one temporary SQLite database.
2. Block `socket.create_connection`, `socket.socket.connect`, `socket.getaddrinfo`
   and `socket.gethostbyname` with functions that call `pytest.fail`.
3. Run real closed Spot and Futures sessions into the same `SQLiteTradeHistory`.
4. Read `before_restart = history.list_baskets(TradeHistoryFilter(), PageRequest())`.
5. Assert exact durable results:
   - two closed Baskets
   - Futures Net PnL `Decimal("2259.8497298")`
   - Spot Net PnL `Decimal("13.84062222")`
   - total closed Net PnL `Decimal("2273.69035202")`
   - each Basket has BUY then SELL Fills from `PAPER_EXECUTOR`
   - Futures leverage `3` and Funding Fee `Decimal("0.00")`
6. Construct new `SQLiteDatabase` and `SQLiteTradeHistory` objects from the same
   path and assert Basket page/Fills equal the pre-restart values exactly.
7. Compose `MainWindow` through `desktop_main.run_desktop(path)` using the same
   non-blocking QApplication/captured-window seam as existing Desktop acceptance.
8. Open Trade History and assert two Basket rows, total PnL text
   `2273.69035202 USDT · Profit`, and deterministic Futures-first ordering.
9. Assert Futures row values:

```text
2026-01-01 02:05:00 UTC | Paper | Futures | BTCUSDT | 5m | 1 |
29999.9492 USDT | 2322.1718 USDT | 62.3220702 USDT | 0.00 USDT |
2259.8497298 USDT · Profit | Closed
```

10. Assert its BUY/SELL Fill rows, select the Spot Basket, and assert the displayed
    fills switch to the exact persisted Spot fills.

Keep the Desktop capture helper private to this acceptance file. Do not expose a
production test seam or change production composition solely for the test.

### Step 3: Run the new acceptance test

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  -k execution_history -q
```

If the test passes immediately, record that it is new cross-layer acceptance evidence
for existing production behavior and make no production change. If it fails because a
required production behavior is absent, first add the smallest focused failing unit or
integration test, confirm RED, then apply the minimum GREEN fix and rerun this test.

### Step 4: Run adjacent acceptance tests

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/acceptance/test_trade_history_query_acceptance.py \
  tests/acceptance/test_desktop_trade_history.py \
  tests/acceptance/test_paper_trade_history_acceptance.py -q
```

### Step 5: Commit Task 1

```bash
git add tests/support/paper_trade_history_acceptance.py \
  tests/acceptance/test_paper_trade_history_acceptance.py
git commit -m "test: prove Paper Trade History end to end"
```

## Task 2: Open Basket, Duplicate and Partial Fill Determinism

**Files:**

- Modify: `tests/support/paper_trade_history_acceptance.py`
- Modify: `tests/acceptance/test_paper_trade_history_acceptance.py`
- Read/verify: `src/tiewtrade/integrations/sqlite/trade_history.py`
- Read/verify: `tests/unit/integrations/sqlite/test_trade_history.py`
- Read/verify: `tests/unit/integrations/sqlite/test_trade_history_query.py`

### Step 1: Add an actual open-Basket runner

Add:

```python
@dataclass(frozen=True, slots=True)
class OpenSpotHistory:
    basket: BasketResult
    fill: TradeFill


def run_spot_until_entry(store: SQLiteTradeHistory) -> OpenSpotHistory: ...
```

Use `OPEN_SPOT_SESSION_ID`, stop immediately after the first real Paper Spot Entry
Fill is persisted, then load the Basket and Fill from SQLite. Assert Basket status
is `OPEN` and exactly one Fill exists before returning.

### Step 2: Write the Open Basket and normalized Partial Fill acceptance test

Add:

```python
def test_open_basket_duplicate_and_partial_fills_remain_deterministic(
    tmp_path: Path,
) -> None:
    ...
```

Scenario:

1. Record one closed Spot Basket through `run_closed_spot`.
2. Record one Open Spot Basket through `run_spot_until_entry`.
3. Call `record_open_basket(open_basket, first_fill)` again and assert `False`.
4. Build a second `TradeFill` with:
   - new `fill_id`
   - same `basket_id`, `session_id`, `order_id` and `entry_number`
   - `filled_at_utc = first_fill.filled_at_utc + timedelta(seconds=1)`
   - price `first_fill.price`, quantity `Decimal("0.001")`
   - exact derived notional and commission using fee rate `0.001`
5. Build the proposed Basket with added notional/fee and unchanged `entry_count=1`.
6. Assert first `record_entry_fill` returns `True` and exact replay returns `False`.
7. Reopen SQLite and assert:
   - Open Basket has two Fills sharing one Order/Entry
   - `entry_count == 1`
   - Fills are ordered by time then ID
   - an unfiltered query includes Open and Closed Baskets
   - Net PnL equals only the closed Spot Basket `Decimal("13.84062222")`
   - `status=OPEN` query has Net PnL `Decimal("0")`
8. Reopen/query a second time and assert page and fills are byte-for-value identical
   to the first restart read.

This test exercises the normalized persistence contract directly for the synthetic
second partial Fill. Do not modify Paper execution to emit more than one Fill.

### Step 3: Run focused tests

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  tests/unit/integrations/sqlite/test_trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history_query.py -q
```

If a persistence behavior fails, add/confirm the matching focused RED test before any
production correction. Do not weaken current conflict or ownership validation.

### Step 4: Commit Task 2

```bash
git add tests/support/paper_trade_history_acceptance.py \
  tests/acceptance/test_paper_trade_history_acceptance.py
git commit -m "test: prove durable partial Fill semantics"
```

## Task 3: Real SQLite Failure and Fail-Closed Session Proof

**Files:**

- Modify: `tests/acceptance/test_paper_trade_history_acceptance.py`
- Read/verify: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Read/verify: `src/tiewtrade/integrations/sqlite/session_persistence.py`
- Read/verify: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

### Step 1: Write the real SQLite failure acceptance test

Add:

```python
def test_sqlite_failure_blocks_new_paper_entry_fail_closed(tmp_path: Path) -> None:
    ...
```

The test must:

1. Migrate a temporary database.
2. Create a SQLite trigger on `trade_fills`:

```sql
CREATE TRIGGER fail_trade_fill_insert
BEFORE INSERT ON trade_fills
BEGIN
    SELECT RAISE(ABORT, 'forced Trade History failure');
END;
```

3. Build a real `PaperSpotSession`, `PaperSpotSQLiteHistory` and
   `PersistentPaperSpotSQLiteSession` using a unique Session ID.
4. Iterate deterministic Spot candles until Entry persistence raises
   `TradeHistoryUnavailableError`.
5. Assert the transaction rolled back: no Basket and no Fill is visible.
6. Pass the next candle and assert `SessionPersistenceBlockedError` before any new
   persistence attempt.
7. Reopen SQLite and assert history remains empty.

Do not mock `PaperSpotSession` or `SQLiteTradeHistory` in this acceptance test. The
trigger is the deterministic failure injector and must remain inside the temporary DB.

### Step 2: Run RED/GREEN checks

Run the single acceptance test first:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  -k sqlite_failure -q
```

Then run coordinator and SQLite suites:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_trade_history.py -q
```

If the existing production flow already passes, retain the acceptance proof without
production changes. If not, add the smallest focused RED test before a minimal fix.

### Step 3: Commit Task 3

```bash
git add tests/acceptance/test_paper_trade_history_acceptance.py
git commit -m "test: prove Trade History fails closed"
```

## Task 4: Delivery Status and Complete Verification

**Files:**

- Modify: `PROJECT_PLAN.md`
- Modify: `docs/superpowers/specs/2026-07-29-dev-97-paper-trade-history-acceptance-design.md`
- Add: `docs/superpowers/plans/2026-07-29-dev-97-paper-trade-history-acceptance.md`

### Step 1: Record delivered DEV-97 status

After all acceptance tests pass, append a concise status paragraph after DEV-96 in
`PROJECT_PLAN.md` stating:

- real Paper Spot/Futures execution reaches durable SQLite and Desktop Trade History
- restart preserves Basket/Fills and exact closed Net PnL
- Open Basket, duplicate, Partial Fill and SQLite fail-closed semantics are covered
- no Live/network/credential behavior was introduced
- DEV-97 closes the Trade History acceptance slice but does not by itself complete
  Stop Session, startup Recovery or all Paper Trading Complete criteria

Do not mark Milestone 3 complete.

### Step 2: Verify focused acceptance coverage

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/acceptance/test_trade_history_query_acceptance.py \
  tests/acceptance/test_desktop_trade_history.py -q
```

### Step 3: Run all project quality gates

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
MYPYPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main...HEAD
```

Record exact pass counts and any warnings in the implementation report. A skipped or
aborted gate is not a pass.

### Step 4: Commit documentation status

```bash
git add PROJECT_PLAN.md \
  docs/superpowers/specs/2026-07-29-dev-97-paper-trade-history-acceptance-design.md \
  docs/superpowers/plans/2026-07-29-dev-97-paper-trade-history-acceptance.md
git commit -m "docs: report DEV-97 acceptance"
```

### Step 5: Review and issue completion

1. Generate a review package for each task and require spec-compliance plus
   code-quality approval before the next task.
2. Generate a whole-branch review package from the branch merge base to `HEAD`.
3. Resolve every Critical/Important finding and rerun covering tests.
4. Run the complete gates again after final fixes.
5. Add a Thai Linear comment summarizing changes, tests and residual risk.
6. Move DEV-97 to `Done` only after implementation and verification are complete.
7. Do not push, merge or delete the branch/worktree until the user gives the required
   separate confirmations.
