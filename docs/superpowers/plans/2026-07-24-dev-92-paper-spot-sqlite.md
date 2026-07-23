# DEV-92 Paper Spot SQLite History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist normalized Paper Spot Basket Results and BUY/SELL Trade Fills
in versioned SQLite storage and prove that exact Decimal values remain readable
after reopening the database file.

**Architecture:** Trading owns immutable history records and complete Basket
close accounting. The SQLite integration owns schema migration, canonical
serialization, and basic Basket/Fill persistence. A SQLite-specific Paper Spot
mapper converts existing execution results without adding a generic history
interface before a second persistence adapter exists.

**Tech Stack:** Python 3.12+, standard-library `sqlite3`, `dataclasses`,
`Decimal`, `UUID`, pytest, Ruff, mypy strict.

## Global Constraints

- DEV-92 does not implement duplicate-event handling, explicit atomicity
  guarantees, persistence blocking, or in-memory fallback; those belong to
  DEV-93.
- DEV-92 does not implement filters, summaries, or pagination; those belong to
  DEV-94.
- Persist monetary and quantity values as canonical decimal strings, never
  SQLite `REAL` or Python binary floating point.
- Persist timezone-aware UTC timestamps as ISO 8601 strings.
- History ownership uses `session_id` directly and stores Symbol, Timeframe,
  Market Type, Trade Mode, and immutable Preset Version.
- Use deterministic Paper order, Fill, and Basket IDs.
- Do not call Binance APIs, store credentials, or send Live orders.
- Follow failing test → minimal implementation → refactor for every code task.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/tiewtrade/trading/basket.py` | Basket identity and complete close accounting |
| `src/tiewtrade/trading/trade_history.py` | Immutable normalized Basket and Fill records |
| `src/tiewtrade/integrations/sqlite/database.py` | Connection configuration and schema version 1 migration |
| `src/tiewtrade/integrations/sqlite/trade_history.py` | Canonical SQLite persistence and direct reads |
| `src/tiewtrade/integrations/sqlite/paper_spot_history.py` | Paper Spot execution-result normalization |
| `src/tiewtrade/application/paper_spot_session.py` | Expose deterministic active/closed Basket identity |
| `src/tiewtrade/execution/paper_spot.py` | Produce deterministic Paper order and Fill IDs |
| `tests/acceptance/test_paper_spot_trade_history.py` | Replay, reopen, and exact history acceptance |

The mapper belongs to the SQLite integration because it writes one concrete
persistence adapter. Application and Trading modules must not import SQLite.

---

### Task 1: Expose Basket Identity and Close Accounting

**Files:**

- Modify: `src/tiewtrade/trading/basket.py`
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `src/tiewtrade/execution/paper_spot.py`
- Modify: `tests/unit/trading/test_basket.py`
- Modify: `tests/unit/application/test_paper_spot_session.py`
- Modify: `tests/unit/execution/test_paper_spot.py`

**Interfaces:**

- `Basket.__init__(basket_id: UUID, policy: EntryPolicy, take_profit_atr_multiplier: Decimal)`
- `Basket.basket_id -> UUID`
- `ClosedBasket` exposes `basket_id`, `gross_realized_pnl`, `trading_fees`,
  `funding_fee`, and `net_realized_pnl`; `realized_pnl` remains a compatibility
  property returning Net PnL.
- `PaperSpotEntryFill` and `PaperSpotExitFill` expose `order_id` and `fill_id`.
- `PaperSpotSessionSnapshot.basket_id -> UUID | None`.

- [ ] **Step 1: Write failing Basket accounting and deterministic identity tests**

Add tests which construct a fixed `basket_id`, close one Entry, and assert:

```python
assert closed.basket_id == basket_id
assert closed.gross_realized_pnl == Decimal("20")
assert closed.trading_fees == Decimal("0.42")
assert closed.funding_fee == Decimal("0")
assert closed.net_realized_pnl == Decimal("19.58")
assert closed.realized_pnl == closed.net_realized_pnl
```

Add executor tests asserting IDs use:

```python
entry_order_id = f"entry:{intent.intent_id}"
entry_fill_id = f"paper:{session.session_id}:{entry_order_id}:fill"
exit_order_id = f"take-profit:{basket.basket_id}"
exit_fill_id = f"paper:{session.session_id}:{exit_order_id}:fill"
```

Add a Session test asserting the first Basket ID is:

```python
uuid5(session.session_id, "basket:1")
```

- [ ] **Step 2: Run focused tests and verify missing fields/signatures**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_basket.py \
  tests/unit/execution/test_paper_spot.py \
  tests/unit/application/test_paper_spot_session.py -q
```

Expected: FAIL because the current types do not expose these identities and
accounting fields.

- [ ] **Step 3: Implement the minimal identity and accounting changes**

Generate Basket IDs only when a new Basket is created:

```python
basket_id = uuid5(
    self._session.session_id,
    f"basket:{self._closed_basket_count + 1}",
)
```

Calculate:

```python
gross_realized_pnl = sum(
    ((exit_price - entry.price) * entry.quantity for entry in self._entries),
    Decimal("0"),
)
trading_fees = (
    sum((entry.fee for entry in self._entries), Decimal("0")) + exit_fee
)
funding_fee = Decimal("0")
net_realized_pnl = gross_realized_pnl - trading_fees - funding_fee
```

Expose the active Basket ID or just-closed Basket ID in every snapshot.

- [ ] **Step 4: Run focused and replay acceptance tests**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_basket.py \
  tests/unit/execution/test_paper_spot.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/replay/test_paper_spot_runner.py \
  tests/acceptance/test_paper_spot_replay.py -q
```

Expected: PASS; replay Net PnL remains `13.84062222`.

- [ ] **Step 5: Commit**

```bash
git add src/tiewtrade/trading/basket.py \
  src/tiewtrade/application/paper_spot_session.py \
  src/tiewtrade/execution/paper_spot.py tests
git commit -m "feat: expose paper basket accounting identities"
```

---

### Task 2: Define Normalized History Records

**Files:**

- Create: `src/tiewtrade/trading/trade_history.py`
- Create: `tests/support/__init__.py`
- Create: `tests/support/trade_history_records.py`
- Create: `tests/unit/trading/test_trade_history.py`

**Interfaces:**

- `BasketStatus`: `OPEN`, `CLOSED`
- `FillSide`: `BUY`, `SELL`
- `FillSource`: `PAPER_EXECUTOR`, `BINANCE`
- Immutable `TradeFill` containing Fill/order identity, ownership, execution
  values, commission, PnL, source, and UTC time.
- Immutable `BasketResult` containing ownership, Session market identity,
  lifecycle times, Entry count, notional, Gross PnL, Fees, Funding, Net PnL,
  and status.

- [ ] **Step 1: Write failing invariant tests**

Test UTC validation, finite positive price/quantity, exact
`notional == price * quantity`, non-negative commission, positive optional
Entry number, complete Session identity, and:

```python
expected_net = (
    basket.gross_realized_pnl
    - basket.trading_fees
    - basket.funding_fee
)
assert basket.net_realized_pnl == expected_net
```

Test that OPEN requires no close time and CLOSED requires a UTC close time.

- [ ] **Step 2: Run the new tests and verify import failure**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_trade_history.py -q
```

Expected: collection FAIL because `tiewtrade.trading.trade_history` does not
exist.

- [ ] **Step 3: Implement immutable records and exact validation**

Use `StrEnum`, frozen slotted dataclasses, `Decimal.is_finite()`, and:

```python
if value.tzinfo is None or value.utcoffset() != timedelta(0):
    raise ValueError(f"{field} must use UTC")
```

Do not accept empty IDs, symbols, timeframes, preset versions, or commission
assets.

- [ ] **Step 4: Run tests and type checks**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_trade_history.py -q
PYTHONPATH=src ../../.venv/bin/python -m mypy src/tiewtrade/trading
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tiewtrade/trading/trade_history.py tests/support \
  tests/unit/trading/test_trade_history.py
git commit -m "feat: define durable trade history records"
```

---

### Task 3: Add Versioned SQLite History Storage

**Files:**

- Create: `src/tiewtrade/integrations/__init__.py`
- Create: `src/tiewtrade/integrations/sqlite/__init__.py`
- Create: `src/tiewtrade/integrations/sqlite/database.py`
- Create: `src/tiewtrade/integrations/sqlite/trade_history.py`
- Create: `tests/unit/integrations/sqlite/test_trade_history.py`

**Interfaces:**

- `SQLiteDatabase.connect() -> sqlite3.Connection`
- `SQLiteDatabase.migrate() -> None`
- `SQLiteTradeHistory.record_open_basket(basket, fill) -> None`
- `SQLiteTradeHistory.record_entry_fill(basket, fill) -> None`
- `SQLiteTradeHistory.record_closed_basket(basket, fill) -> None`
- `SQLiteTradeHistory.get_basket(basket_id) -> BasketResult | None`
- `SQLiteTradeHistory.list_fills(basket_id) -> tuple[TradeFill, ...]`

- [ ] **Step 1: Write failing migration and round-trip tests**

Test schema version `1`, tables `basket_results` and `trade_fills`, required
history/fill indexes, exact Decimal round-trip, UTC round-trip, and reopening a
new `SQLiteTradeHistory` over the same file.

The restart assertion must compare complete records:

```python
assert reopened.get_basket(basket.basket_id) == basket
assert reopened.list_fills(basket.basket_id) == (buy_fill, sell_fill)
```

- [ ] **Step 2: Run tests and verify import failure**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py -q
```

Expected: collection FAIL because the SQLite integration does not exist.

- [ ] **Step 3: Implement migration version 1**

Store every Decimal column as `TEXT`, every identity as `TEXT`, and every UTC
timestamp as ISO 8601 `TEXT`. Create:

```sql
CREATE INDEX basket_results_history_idx
ON basket_results (opened_at_utc DESC, basket_id DESC);

CREATE INDEX trade_fills_basket_time_idx
ON trade_fills (basket_id, filled_at_utc, fill_id);
```

Enable foreign keys on every connection, set `PRAGMA user_version = 1`, make
migration repeatable, and reject schema versions greater than `1`.

- [ ] **Step 4: Implement canonical writes and direct reads**

Serialize with:

```python
def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _utc_text(value: datetime) -> str:
    return value.isoformat()
```

Deserialize with `Decimal(text)`, `datetime.fromisoformat(text)`, `UUID(text)`,
and enum constructors. Implement only the basic write/read behavior needed by
DEV-92. Do not add duplicate suppression, public fail-closed state,
filters, totals, or pagination.

- [ ] **Step 5: Run SQLite tests, lint, and mypy**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check \
  src/tiewtrade/integrations tests/unit/integrations
PYTHONPATH=src ../../.venv/bin/python -m mypy \
  src/tiewtrade/integrations
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tiewtrade/integrations tests/unit/integrations
git commit -m "feat: persist trade history in sqlite"
```

---

### Task 4: Map Paper Spot Results and Prove Restart History

**Files:**

- Create: `src/tiewtrade/integrations/sqlite/paper_spot_history.py`
- Create: `tests/unit/integrations/sqlite/test_paper_spot_history.py`
- Create: `tests/acceptance/test_paper_spot_trade_history.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**

- `PaperSpotHistoryContext` contains Session ID, Symbol, Timeframe, Preset
  Version, and commission asset.
- `PaperSpotSQLiteHistory.record_entry(...) -> None`
- `PaperSpotSQLiteHistory.record_close(...) -> None`

- [ ] **Step 1: Write failing mapper tests**

Record a deterministic Entry Fill and assert the stored OPEN Basket and BUY
Fill contain exact identity and execution values. Record its close and assert
the stored CLOSED Basket and SELL Fill contain:

```python
assert basket.gross_realized_pnl == Decimal("20")
assert basket.trading_fees == Decimal("0.42")
assert basket.funding_fee == Decimal("0")
assert basket.net_realized_pnl == Decimal("19.58")
assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
```

- [ ] **Step 2: Run mapper tests and verify import failure**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_paper_spot_history.py -q
```

Expected: collection FAIL because the mapper does not exist.

- [ ] **Step 3: Implement minimal Paper Spot normalization**

For Entry 1 create the OPEN Basket; for later Entries read and replace the
existing OPEN Basket aggregate. For close, preserve `opened_at_utc` and
`invested_notional`, write the SELL Fill, and replace the aggregate with the
complete `ClosedBasket` accounting.

Use:

```python
TradeFill(
    fill_id=fill.fill_id,
    basket_id=basket_id,
    session_id=context.session_id,
    order_id=fill.order_id,
    exchange_trade_id=None,
    side=FillSide.BUY,
    entry_number=entry_number,
    filled_at_utc=fill.filled_at,
    price=fill.price,
    quantity=fill.quantity,
    notional=fill.price * fill.quantity,
    commission=fill.fee,
    commission_asset=context.commission_asset,
    realized_pnl=Decimal("0"),
    source=FillSource.PAPER_EXECUTOR,
)
```

- [ ] **Step 4: Write and run restart acceptance**

Drive the existing tracer candles through `PaperSpotSession`. For every Entry
or close snapshot, synchronously call the mapper. Reopen the same SQLite file
with a new store and assert the known deterministic Basket ID has one BUY Fill,
one SELL Fill, and Net PnL `13.84062222`.

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

Expected: PASS.

- [ ] **Step 5: Update milestone status and run full verification**

State in `PROJECT_PLAN.md` that durable Paper Spot SQLite history is complete,
while DEV-93 hardening and later Paper/UI work remain.

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tiewtrade/integrations/sqlite/paper_spot_history.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/acceptance/test_paper_spot_trade_history.py PROJECT_PLAN.md
git commit -m "test: prove durable paper spot history"
```
