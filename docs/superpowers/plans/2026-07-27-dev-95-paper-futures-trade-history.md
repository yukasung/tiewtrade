# DEV-95 Paper Futures Trade History Implementation Plan

> ใช้ `test-driven-development` ทำทีละพฤติกรรม และใช้
> `verification-before-completion` ก่อน commit

## Goal

เชื่อม concrete `PaperFuturesSession` result เข้ากับ normalized Trade History
เดียวกับ Paper Spot โดยคง atomic/idempotent SQLite flow เดิม บันทึก leverage context,
Gross Realized PnL, Trading Fees, Funding Fee `0.00` และ Net Realized PnL ได้แบบ
durable โดยไม่เรียก Binance Private API หรือส่ง Live order

## Design Decisions

- เพิ่ม `BasketResult.leverage: int | None` เป็น normalized execution context
  ที่ UI อ่านได้โดยไม่คำนวณ business rule เอง
- Spot Basket ต้องมี `leverage = None`; Futures Basket ต้องมี leverage เป็นจำนวนเต็ม
  1x–5x ตาม Session policy
- leverage เป็น immutable Basket identity และ persist ใน `basket_results`
- เพิ่ม SQLite schema version 2 พร้อม migration จาก version 1 ที่เก็บ Spot history เดิม
  โดยเพิ่ม nullable `leverage` column
- สร้าง concrete `PaperFuturesSQLiteHistory` mapper และ
  `PersistentPaperFuturesSQLiteSession` coordinator; ไม่สร้าง generic executor,
  repository interface หรือ factory
- Long Entry/Exit normalize เป็น BUY/SELL; Short Entry/Exit normalize เป็น SELL/BUY
- mapper ใช้ PnL aggregate จาก shared `ClosedBasket` โดยตรง และ normalize Paper
  Futures Funding Fee เป็น `Decimal("0.00")`
- reuse `SQLiteTradeHistory.record_open_basket()`, `record_entry_fill()` และ
  `record_closed_basket()` เพื่อคง atomic transaction, Partial Fill และ canonical
  `fill_id` idempotency เดิม
- แยก persistence state/error ที่ Spot และ Futures ใช้ร่วมกันไปไว้ใน Module เล็ก
  `session_persistence.py` โดยไม่สร้าง abstract base class
- coordinator ตรวจ Session identity, symbol, timeframe, Preset และ leverage ของ
  core Session กับ History context ก่อนรับ candle แรก

## Files

- Modify `src/tiewtrade/trading/trade_history.py`
- Modify `src/tiewtrade/integrations/sqlite/database.py`
- Modify `src/tiewtrade/integrations/sqlite/trade_history.py`
- Create `src/tiewtrade/integrations/sqlite/paper_futures_history.py`
- Create `src/tiewtrade/integrations/sqlite/session_persistence.py`
- Create `src/tiewtrade/integrations/sqlite/persistent_paper_futures_session.py`
- Modify `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Modify/add focused tests under `tests/unit/trading/` and
  `tests/unit/integrations/sqlite/`
- Create `tests/acceptance/test_paper_futures_trade_history.py`
- Update `PROJECT_PLAN.md` after verification reflects delivered status

## Task 1 — Normalized Futures Context and Schema v2

### RED

Add tests that prove:

1. Futures `BasketResult` requires integer leverage in the Session cap 1x–5x.
2. Spot `BasketResult` rejects leverage.
3. A new database uses schema version 2 and exposes nullable `leverage`.
4. Migration from schema version 1 preserves an existing Spot Basket and assigns
   `leverage = NULL`.
5. Futures Basket leverage round-trips exactly after reopening SQLite.
6. A proposed Basket cannot mutate leverage after its first Fill.

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history.py -q
```

### GREEN

- Append `leverage: int | None = None` to `BasketResult` and validate it against
  `market_type` and the 1x–5x product cap.
- Add `leverage` to SQLite insert/update/read mapping and immutable identity.
- Implement ordered migration `0 → 2` and `1 → 2`; reject version 3 or newer.
- Keep old Spot constructors source-compatible through the default `None`.

## Task 2 — Paper Futures History Mapper

### RED

Create `tests/unit/integrations/sqlite/test_paper_futures_history.py` covering:

1. Long Entry creates Futures/Paper open Basket, BUY Fill, leverage and entry fee.
2. Short Entry creates SELL Fill.
3. A second Entry updates notional/fee aggregate and entry count.
4. Long and Short exits map to the opposite Fill side.
5. Close persists shared gross PnL/fees, explicit `0.00` funding and exact net PnL.
6. Duplicate Entry and Close return `False` without changing aggregates.
7. Wrong Basket/session ownership remains rejected by the shared store.

Run the new test file and confirm import/module failure before implementation.

### GREEN

Implement:

```python
@dataclass(frozen=True, slots=True)
class PaperFuturesHistoryContext:
    session_id: UUID
    symbol: str
    timeframe: str
    preset_version: str
    commission_asset: str
    leverage: int


class PaperFuturesSQLiteHistory:
    def record_entry(...) -> bool: ...
    def record_close(...) -> bool: ...
```

The mapper only normalizes execution results. It does not own transactions or
recalculate shared Futures PnL policy.

## Task 3 — Fail-Closed Persistent Futures Session

### RED

Create `tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py`
covering:

1. Entry is durable before a READY snapshot returns.
2. Take Profit and Liquidation exits both persist before return.
3. SQLite/conflict failure changes persistence state to BLOCKED.
4. Every later candle raises `SessionPersistenceBlockedError` before the core
   Session is called.
5. Invalid snapshot invariants fail closed.
6. Entry และ Liquidation ใน candle เดียวกันใช้ `closed_basket.entry_count` เพื่อ
   บันทึก Entry Fill ก่อน Close Fill
7. Session กับ History context ที่มี identity หรือ leverage ต่างกันถูกปฏิเสธ

### GREEN

- Extract shared `PersistenceState` and `SessionPersistenceBlockedError` without
  changing Spot behavior.
- Implement concrete `PersistentPaperFuturesSQLiteSession` that synchronously
  records `entry_fill` and `exit_fill + closed_basket` from each snapshot.
- Catch all persistence-block exceptions, mark BLOCKED and re-raise the original
  error; provide no in-memory fallback.

## Task 4 — Acceptance, Restart and Idempotency

### RED

Create `tests/acceptance/test_paper_futures_trade_history.py` that runs the real
configured Paper Futures Session through a deterministic Entry and Take Profit,
then:

1. Reopens the SQLite file through a new database/store instance.
2. Reads one closed Futures/Paper Basket with leverage 3.
3. Reads exact BUY/SELL Fills and execution costs.
4. Confirms Funding Fee is represented as `Decimal("0.00")`.
5. Replays the captured Entry/Close persistence events and confirms both are
   idempotent no-ops with unchanged Basket totals.

### GREEN

Make only the minimum integration changes required by the acceptance test. Do not
add startup Session Recovery, UI, Live execution or Binance Private API access.

## Task 5 — Documentation, Review and Verification

1. Update `PROJECT_PLAN.md` status only after implementation is verified.
2. Run focused tests after every RED/GREEN cycle.
3. Run complete gates:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
MYPYPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

4. Use `code-review` against the DEV-95 branch diff and fix Critical/Important
   findings.
5. Commit the verified branch. Do not push or merge without separate user
   confirmation.
6. Move DEV-95 to Done only when implementation and verification are complete.

## Out of Scope

- Binance Private API, credentials or Live order
- Paper funding simulation beyond explicit `0.00`
- Startup Session Recovery/reconstruction
- Desktop UI and chart history
- Changing Paper Spot PnL semantics
- Simulating Partial Fills inside `PaperFuturesExecutor`
- Generic persistence/executor interface, registry or factory
