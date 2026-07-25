# DEV-93 Trade History Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Paper Spot Trade History atomic, idempotent, ownership-safe, and
fail closed when SQLite cannot confirm durable persistence.

**Architecture:** `SQLiteTradeHistory` owns transaction, duplicate comparison,
ownership, and Basket lifecycle validation. `PaperSpotSQLiteHistory` maps
Paper execution results and returns the store write result. A concrete
`PersistentPaperSpotSQLiteSession` in the SQLite integration synchronously
records each Session snapshot and blocks all later candles after any
persistence exception.

**Tech Stack:** Python 3.12+, standard-library `sqlite3`, `dataclasses`,
`Decimal`, `UUID`, pytest, Ruff, mypy strict.

## Global Constraints

- Use `fill_id` as the canonical idempotency key.
- An exact duplicate returns `False` and does not mutate Basket totals.
- A duplicate `fill_id` with different payload raises
  `TradeHistoryConflictError`.
- Multiple Partial Fills may share one `order_id`; each must have a distinct
  `fill_id`.
- Partial Fills for one Entry use the same `entry_number`; `entry_count`
  increases once per Entry, not once per Fill.
- Fill and Basket mutation commit or rollback in one `BEGIN IMMEDIATE`
  transaction.
- A Basket can transition only from `OPEN` to `CLOSED`.
- SQLite schema stays at version 1.
- Application and Trading modules must not import SQLite.
- Do not create a generic persistence interface before a second adapter exists.
- Do not change Paper execution to simulate Partial Fills.
- Do not add queries, pagination, Paper Futures, Live, UI, or startup Recovery.
- A persistence exception blocks future candle processing without an
  in-memory fallback or in-memory Session rollback.
- Do not call Binance APIs, store credentials, or send Live orders.
- Follow failing test → minimal implementation → refactor for every code task.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/tiewtrade/integrations/sqlite/trade_history.py` | Error model, idempotency, ownership/lifecycle validation, atomic writes |
| `src/tiewtrade/integrations/sqlite/paper_spot_history.py` | Paper-to-normalized mapping and write-result propagation |
| `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py` | SQLite-specific synchronous recording and fail-closed state |
| `tests/unit/integrations/sqlite/test_trade_history.py` | Duplicate, Partial Fill, ownership, lifecycle, and rollback tests |
| `tests/unit/integrations/sqlite/test_paper_spot_history.py` | Mapper duplicate-result tests |
| `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py` | READY/BLOCKED orchestration tests |
| `tests/acceptance/test_paper_spot_trade_history.py` | Replay retry and durable aggregate acceptance |

No schema migration file changes are required.

---

### Task 1: Add Canonical Fill Idempotency and Partial Fill Support

**Files:**

- Modify: `src/tiewtrade/integrations/sqlite/trade_history.py`
- Modify: `tests/unit/integrations/sqlite/test_trade_history.py`

**Interfaces:**

- Produces:

```python
class TradeHistoryError(RuntimeError):
    pass


class TradeHistoryConflictError(TradeHistoryError):
    pass


class TradeHistoryUnavailableError(TradeHistoryError):
    pass
```

- Changes all `SQLiteTradeHistory.record_*` methods to return `bool`.

- [ ] **Step 1: Write failing duplicate and Partial Fill tests**

Add focused helpers and tests to
`tests/unit/integrations/sqlite/test_trade_history.py`:

```python
def open_basket() -> BasketResult:
    return basket_result(
        closed_at_utc=None,
        invested_notional=Decimal("100"),
        gross_realized_pnl=Decimal("0"),
        trading_fees=Decimal("0.1"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("-0.1"),
        status=BasketStatus.OPEN,
    )


def test_exact_duplicate_fill_is_a_no_op(
    history: SQLiteTradeHistory,
) -> None:
    basket = open_basket()
    fill = trade_fill(
        quantity=Decimal("1"),
        notional=Decimal("100"),
        commission=Decimal("0.1"),
    )

    assert history.record_open_basket(basket, fill) is True
    assert history.record_open_basket(basket, fill) is False
    assert history.get_basket(basket.basket_id) == basket
    assert history.list_fills(basket.basket_id) == (fill,)


def test_same_fill_id_with_different_payload_is_a_conflict(
    history: SQLiteTradeHistory,
) -> None:
    basket = open_basket()
    fill = trade_fill(
        quantity=Decimal("1"),
        notional=Decimal("100"),
        commission=Decimal("0.1"),
    )
    history.record_open_basket(basket, fill)

    conflicting = replace(
        fill,
        price=Decimal("101"),
        notional=Decimal("101"),
    )
    with pytest.raises(TradeHistoryConflictError, match="fill_id"):
        history.record_open_basket(basket, conflicting)

    assert history.get_basket(basket.basket_id) == basket
    assert history.list_fills(basket.basket_id) == (fill,)


def test_partial_fills_share_order_and_entry_without_incrementing_entry_count(
    history: SQLiteTradeHistory,
) -> None:
    first = trade_fill(
        order_id="order-partial",
        entry_number=1,
        quantity=Decimal("1"),
        notional=Decimal("100"),
        commission=Decimal("0.1"),
    )
    opened = open_basket()
    history.record_open_basket(opened, first)
    second = trade_fill(
        fill_id="fill-partial-2",
        order_id=first.order_id,
        entry_number=first.entry_number,
        filled_at_utc=first.filled_at_utc + timedelta(seconds=1),
        price=Decimal("101"),
        quantity=Decimal("0.5"),
        notional=Decimal("50.5"),
        commission=Decimal("0.0505"),
    )
    updated = replace(
        opened,
        entry_count=1,
        invested_notional=Decimal("150.5"),
        trading_fees=Decimal("0.1505"),
        net_realized_pnl=Decimal("-0.1505"),
    )

    assert history.record_entry_fill(updated, second) is True
    assert history.get_basket(opened.basket_id) == updated
    assert history.list_fills(opened.basket_id) == (first, second)
```

Use a `history` fixture which migrates a temporary SQLite file.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py \
  -k "duplicate or partial" -q
```

Expected: FAIL because write methods return `None`, duplicate inserts raise
`sqlite3.IntegrityError`, and error types do not exist.

- [ ] **Step 3: Implement the error model and exact Fill comparison**

In `trade_history.py`, add:

```python
def _find_fill(
    connection: sqlite3.Connection,
    fill_id: str,
) -> TradeFill | None:
    row = connection.execute(
        "SELECT * FROM trade_fills WHERE fill_id = ?",
        (fill_id,),
    ).fetchone()
    return _fill_from_row(row) if row is not None else None


def _check_duplicate_fill(
    connection: sqlite3.Connection,
    fill: TradeFill,
) -> bool:
    existing = _find_fill(connection, fill.fill_id)
    if existing is None:
        return False
    if existing != fill:
        raise TradeHistoryConflictError(
            f"fill_id {fill.fill_id!r} has conflicting payload"
        )
    return True
```

Every write method must:

1. verify `basket.basket_id == fill.basket_id` and
   `basket.session_id == fill.session_id`;
2. execute `BEGIN IMMEDIATE`;
3. call `_check_duplicate_fill()` before Basket lifecycle mutation;
4. return `False` for an exact duplicate;
5. insert/update and return `True` for a new Fill.

Do not use `INSERT OR IGNORE`, because it cannot distinguish an exact retry
from conflicting payload.

- [ ] **Step 4: Validate Partial Fill Entry counting**

For `record_entry_fill()`, query earlier Fills for the same Basket and
`order_id`:

```python
def _existing_order_entry_number(
    connection: sqlite3.Connection,
    fill: TradeFill,
) -> int | None:
    row = connection.execute(
        """
        SELECT entry_number
        FROM trade_fills
        WHERE basket_id = ? AND order_id = ?
        ORDER BY filled_at_utc, fill_id
        LIMIT 1
        """,
        (str(fill.basket_id), fill.order_id),
    ).fetchone()
    return row["entry_number"] if row is not None else None
```

Rules:

```python
if prior_entry_number is not None:
    if fill.entry_number != prior_entry_number:
        raise TradeHistoryConflictError(
            "Partial Fills for one Order must use the same entry_number"
        )
    if basket.entry_count != current.entry_count:
        raise TradeHistoryConflictError(
            "Partial Fill must not increment Basket entry_count"
        )
else:
    expected_entry_number = current.entry_count + 1
    if fill.entry_number != expected_entry_number:
        raise TradeHistoryConflictError(
            "new Entry Fill has an unexpected entry_number"
        )
    if basket.entry_count != expected_entry_number:
        raise TradeHistoryConflictError(
            "new Entry Fill must increment Basket entry_count once"
        )
```

- [ ] **Step 5: Run focused tests and checks**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check \
  src/tiewtrade/integrations/sqlite/trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history.py
PYTHONPATH=src ../../.venv/bin/python -m mypy \
  src/tiewtrade/integrations/sqlite
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tiewtrade/integrations/sqlite/trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history.py
git commit -m "feat: make trade fills idempotent"
```

---

### Task 2: Enforce Ownership, Lifecycle, and Atomic Rollback

**Files:**

- Modify: `src/tiewtrade/integrations/sqlite/trade_history.py`
- Modify: `tests/unit/integrations/sqlite/test_trade_history.py`

**Interfaces:**

- Keeps the Task 1 public methods and errors.
- Adds no new public Module.

- [ ] **Step 1: Write failing ownership and lifecycle tests**

Add parameterized tests which mutate one identity field at a time:

```python
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", UUID("00000000-0000-0000-0000-000000000999")),
        ("trade_mode", TradeMode.LIVE),
        ("market_type", MarketType.FUTURES),
        ("symbol", "ETHUSDT"),
        ("timeframe", "15m"),
        ("strategy_preset_version", "rsi-step-grid-v2"),
        ("opened_at_utc", datetime(2026, 1, 2, tzinfo=UTC)),
    ],
)
def test_entry_rejects_changed_basket_identity(
    history: SQLiteTradeHistory,
    field: str,
    value: object,
) -> None:
    opened = open_basket()
    history.record_open_basket(opened, trade_fill())
    next_fill = trade_fill(
        fill_id="fill-2",
        order_id="order-2",
        entry_number=2,
    )
    proposed = replace(
        opened,
        **{
            field: value,
            "entry_count": 2,
            "invested_notional": opened.invested_notional + next_fill.notional,
            "trading_fees": opened.trading_fees + next_fill.commission,
            "net_realized_pnl": (
                opened.gross_realized_pnl
                - opened.trading_fees
                - next_fill.commission
                - opened.funding_fee
            ),
        },
    )

    with pytest.raises(TradeHistoryConflictError):
        history.record_entry_fill(proposed, next_fill)
```

Add these explicit cases using the existing `basket_result()` and
`trade_fill()` helpers:

| Test | Arrange | Expected assertion |
| --- | --- | --- |
| `test_fill_rejects_different_basket_or_session` | Parameterize a changed `basket_id` and a changed `session_id` on the Fill passed with an otherwise matching Basket | `TradeHistoryConflictError`; no Basket or Fill is written |
| `test_unknown_basket_rejects_entry_and_close` | Parameterize `record_entry_fill` with an OPEN proposal and `record_closed_basket` with a CLOSED proposal before opening the Basket | `TradeHistoryConflictError("Basket does not exist")`; tables remain empty |
| `test_closed_basket_rejects_new_entry` | Open and close a Basket, then submit a new BUY Fill and OPEN proposal | `TradeHistoryConflictError` and the stored CLOSED Basket plus its two Fills remain unchanged |
| `test_closed_basket_cannot_return_to_open` | Open and close a Basket, then submit an OPEN proposal with a new Fill | `TradeHistoryConflictError`; status remains `CLOSED` |
| `test_exact_duplicate_close_after_closed_is_a_no_op` | Call `record_closed_basket()` twice with the same CLOSED Basket and SELL Fill | First call is `True`, second is `False`, and only two Fills exist |

- [ ] **Step 2: Run ownership/lifecycle tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py \
  -k "identity or session or basket or closed or unknown" -q
```

Expected: FAIL because the current update accepts missing or closed Baskets and
allows identity fields to change.

- [ ] **Step 3: Implement immutable identity and lifecycle validation**

Add focused private helpers:

```python
def _validate_fill_ownership(
    basket: BasketResult,
    fill: TradeFill,
) -> None:
    if basket.basket_id != fill.basket_id:
        raise TradeHistoryConflictError("Fill belongs to a different Basket")
    if basket.session_id != fill.session_id:
        raise TradeHistoryConflictError("Fill belongs to a different Session")


def _validate_immutable_identity(
    current: BasketResult,
    proposed: BasketResult,
) -> None:
    fields = (
        "basket_id",
        "session_id",
        "trade_mode",
        "market_type",
        "symbol",
        "timeframe",
        "strategy_preset_version",
        "opened_at_utc",
    )
    for field in fields:
        if getattr(current, field) != getattr(proposed, field):
            raise TradeHistoryConflictError(
                f"Basket identity field {field} cannot change"
            )
```

Load the current Basket inside the transaction. Entry writes require current
and proposed status `OPEN`. Close writes require current `OPEN` and proposed
`CLOSED`. Check exact duplicate Fill before the current-Basket lifecycle check
so an identical close retry remains a no-op after closure.

Require update `rowcount == 1`; otherwise raise
`TradeHistoryConflictError("Basket does not exist")`.

- [ ] **Step 4: Write failing transaction rollback tests**

Add two tests using test-only SQLite triggers:

```python
def test_open_basket_rolls_back_when_fill_insert_fails(
    tmp_path: Path,
) -> None:
    database, history = migrated_history(tmp_path)
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_trade_fill
            BEFORE INSERT ON trade_fills
            BEGIN
                SELECT RAISE(ABORT, 'forced fill failure');
            END
            """
        )

    with pytest.raises(TradeHistoryUnavailableError):
        history.record_open_basket(open_basket(), trade_fill())

    assert history.get_basket(BASKET_ID) is None
    assert history.list_fills(BASKET_ID) == ()


def test_entry_fill_rolls_back_when_basket_update_fails(
    tmp_path: Path,
) -> None:
    database, history = migrated_history(tmp_path)
    opened = open_basket()
    first = trade_fill()
    history.record_open_basket(opened, first)
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_basket_update
            BEFORE UPDATE ON basket_results
            BEGIN
                SELECT RAISE(ABORT, 'forced Basket failure');
            END
            """
        )
    second = trade_fill(
        fill_id="fill-2",
        order_id="order-2",
        entry_number=2,
    )
    proposed = replace(
        opened,
        entry_count=2,
        invested_notional=opened.invested_notional + second.notional,
        trading_fees=opened.trading_fees + second.commission,
        net_realized_pnl=(
            opened.gross_realized_pnl
            - opened.trading_fees
            - second.commission
            - opened.funding_fee
        ),
    )

    with pytest.raises(TradeHistoryUnavailableError):
        history.record_entry_fill(proposed, second)

    assert history.get_basket(BASKET_ID) == opened
    assert history.list_fills(BASKET_ID) == (first,)
```

- [ ] **Step 5: Wrap SQLite errors at every public adapter method**

Use one internal transaction runner:

```python
def _run_write(
    self,
    operation: Callable[[sqlite3.Connection], bool],
) -> bool:
    connection: sqlite3.Connection | None = None
    try:
        connection = self._database.connect()
        connection.execute("BEGIN IMMEDIATE")
        result = operation(connection)
        connection.commit()
        return result
    except TradeHistoryError:
        if connection is not None:
            connection.rollback()
        raise
    except sqlite3.Error as error:
        if connection is not None:
            connection.rollback()
        raise TradeHistoryUnavailableError(
            "Trade History SQLite operation failed"
        ) from error
    finally:
        if connection is not None:
            connection.close()
```

Add an analogous focused read runner or explicit `try/except/finally` around
`get_basket()` and `list_fills()` so connection failures are also converted to
`TradeHistoryUnavailableError`.

Within update operations, insert the new Fill before updating the Basket. The
transaction rollback test must prove the Fill disappears if the update fails.

- [ ] **Step 6: Run Task 2 and regression checks**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/tiewtrade/integrations/sqlite/trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history.py
git commit -m "feat: enforce atomic trade history writes"
```

---

### Task 3: Add Fail-Closed Persistent Paper Spot Session

**Files:**

- Modify: `src/tiewtrade/integrations/sqlite/paper_spot_history.py`
- Modify: `tests/unit/integrations/sqlite/test_paper_spot_history.py`
- Create: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Create: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

**Interfaces:**

- `PaperSpotSQLiteHistory.record_entry(basket_id, entry_number, fill) -> bool`
- `PaperSpotSQLiteHistory.record_close(basket_id, fill, closed) -> bool`
- Produces:

```python
class PersistenceState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class SessionPersistenceBlockedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PersistentPaperSpotSnapshot:
    session: PaperSpotSessionSnapshot
    persistence_state: PersistenceState


class PersistentPaperSpotSQLiteSession:
    """Synchronously persist Paper Spot results before returning READY."""
```

The class constructor receives `PaperSpotSession` and
`PaperSpotSQLiteHistory`. Its public
`process_completed_candle(candle, *, received_at)` method returns
`PersistentPaperSpotSnapshot`.

- [ ] **Step 1: Write failing mapper result tests**

Extend mapper tests:

```python
def test_mapper_propagates_new_and_duplicate_write_results(
    history: PaperSpotSQLiteHistory,
) -> None:
    fill = entry_fill()

    assert history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=fill,
    ) is True
    assert history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=fill,
    ) is False
```

Update existing mapper assertions to expect `True` for new writes.

- [ ] **Step 2: Run mapper test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_paper_spot_history.py -q
```

Expected: FAIL because mapper methods currently return `None`.

- [ ] **Step 3: Return store results from the mapper**

Change every write path to:

```python
return self._store.record_open_basket(basket, normalized_fill)
return self._store.record_entry_fill(basket, normalized_fill)
return self._store.record_closed_basket(basket, normalized_fill)
```

Annotate both mapper public methods with `-> bool`.

- [ ] **Step 4: Write failing READY/BLOCKED Session tests**

Create `test_persistent_paper_spot_session.py`. Use autospecced concrete
dependencies so no production interface is introduced:

```python
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import create_autospec
from uuid import UUID

import pytest

from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionSnapshot,
)
from tiewtrade.execution.paper_spot import PaperSpotEntryFill, PaperSpotExitFill
from tiewtrade.integrations.sqlite.paper_spot_history import PaperSpotSQLiteHistory
from tiewtrade.integrations.sqlite.persistent_paper_spot_session import (
    PersistenceState,
    PersistentPaperSpotSQLiteSession,
    SessionPersistenceBlockedError,
)
from tiewtrade.integrations.sqlite.trade_history import (
    TradeHistoryConflictError,
    TradeHistoryUnavailableError,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.basket import ClosedBasket

SESSION_ID = UUID("00000000-0000-0000-0000-000000000101")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000102")
FILLED_AT = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)


def completed_candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("111"),
        low=Decimal("99"),
        close=Decimal("110"),
        volume=Decimal("10"),
    )


def entry_fill() -> PaperSpotEntryFill:
    return PaperSpotEntryFill(
        intent_id="intent-1",
        order_id="entry:intent-1",
        fill_id=f"paper:{SESSION_ID}:entry:intent-1:fill",
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=FILLED_AT,
    )


def exit_fill() -> PaperSpotExitFill:
    return PaperSpotExitFill(
        order_id=f"take-profit:{BASKET_ID}",
        fill_id=f"paper:{SESSION_ID}:take-profit:{BASKET_ID}:fill",
        price=Decimal("110"),
        quantity=Decimal("2"),
        fee=Decimal("0.22"),
        filled_at=FILLED_AT,
    )


def closed_basket() -> ClosedBasket:
    return ClosedBasket(
        basket_id=BASKET_ID,
        entry_count=1,
        average_entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        gross_realized_pnl=Decimal("20"),
        trading_fees=Decimal("0.42"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("19.58"),
        closed_at=FILLED_AT,
    )


def entry_snapshot() -> PaperSpotSessionSnapshot:
    return PaperSpotSessionSnapshot(
        accepted=True,
        pending_intent=None,
        entry_fill=entry_fill(),
        take_profit_fill=None,
        closed_basket=None,
        closed_basket_count=0,
        basket_id=BASKET_ID,
        basket_entry_count=1,
        take_profit_price=Decimal("105"),
    )


def close_snapshot() -> PaperSpotSessionSnapshot:
    return PaperSpotSessionSnapshot(
        accepted=True,
        pending_intent=None,
        entry_fill=None,
        take_profit_fill=exit_fill(),
        closed_basket=closed_basket(),
        closed_basket_count=1,
        basket_id=BASKET_ID,
        basket_entry_count=0,
        take_profit_price=None,
    )


def test_persistence_failure_blocks_every_later_candle() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    snapshot = entry_snapshot()
    session.process_completed_candle.return_value = snapshot
    history.record_entry.side_effect = TradeHistoryUnavailableError(
        "forced failure"
    )
    persistent = PersistentPaperSpotSQLiteSession(session, history)
    candle = completed_candle()

    with pytest.raises(TradeHistoryUnavailableError, match="forced failure"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    with pytest.raises(SessionPersistenceBlockedError, match="blocked"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    session.process_completed_candle.assert_called_once()
    history.record_entry.assert_called_once()


def test_successful_entry_is_durable_before_ready_snapshot_returns() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = entry_snapshot()
    history.record_entry.return_value = True
    persistent = PersistentPaperSpotSQLiteSession(session, history)
    candle = completed_candle()

    result = persistent.process_completed_candle(
        candle,
        received_at=candle.close_time,
    )

    history.record_entry.assert_called_once_with(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    assert result.session == entry_snapshot()
    assert result.persistence_state is PersistenceState.READY


def test_successful_close_is_durable_before_ready_snapshot_returns() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = close_snapshot()
    history.record_close.return_value = True
    persistent = PersistentPaperSpotSQLiteSession(session, history)
    candle = completed_candle()

    result = persistent.process_completed_candle(
        candle,
        received_at=candle.close_time,
    )

    history.record_close.assert_called_once_with(
        basket_id=BASKET_ID,
        fill=exit_fill(),
        closed=closed_basket(),
    )
    assert result.session == close_snapshot()
    assert result.persistence_state is PersistenceState.READY


def test_conflict_also_blocks_future_candles() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = entry_snapshot()
    history.record_entry.side_effect = TradeHistoryConflictError(
        "conflicting Fill"
    )
    persistent = PersistentPaperSpotSQLiteSession(session, history)
    candle = completed_candle()

    with pytest.raises(TradeHistoryConflictError, match="conflicting Fill"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    with pytest.raises(SessionPersistenceBlockedError, match="blocked"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    session.process_completed_candle.assert_called_once()
```

Successful results must contain `persistence_state is PersistenceState.READY`.

- [ ] **Step 5: Run wrapper tests and verify import failure**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py -q
```

Expected: collection FAIL because
`persistent_paper_spot_session.py` does not exist.

- [ ] **Step 6: Implement synchronous recording and fail-closed state**

Implement:

```python
def process_completed_candle(
    self,
    candle: Candle,
    *,
    received_at: datetime,
) -> PersistentPaperSpotSnapshot:
    if self._state is PersistenceState.BLOCKED:
        raise SessionPersistenceBlockedError(
            "Session is blocked because Trade History persistence failed"
        )

    snapshot = self._session.process_completed_candle(
        candle,
        received_at=received_at,
    )
    try:
        if snapshot.entry_fill is not None:
            assert snapshot.basket_id is not None
            self._history.record_entry(
                basket_id=snapshot.basket_id,
                entry_number=snapshot.basket_entry_count,
                fill=snapshot.entry_fill,
            )
        if snapshot.closed_basket is not None:
            assert snapshot.take_profit_fill is not None
            self._history.record_close(
                basket_id=snapshot.closed_basket.basket_id,
                fill=snapshot.take_profit_fill,
                closed=snapshot.closed_basket,
            )
    except Exception:
        self._state = PersistenceState.BLOCKED
        raise

    return PersistentPaperSpotSnapshot(
        session=snapshot,
        persistence_state=self._state,
    )
```

The `try` block must cover only persistence mapping. Do not catch an exception
raised by core candle processing.

- [ ] **Step 7: Run Task 3 and Session regression tests**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/tiewtrade/integrations/sqlite/paper_spot_history.py \
  src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py
git commit -m "feat: fail closed on trade history errors"
```

---

### Task 4: Prove Idempotent Replay and Record the DEV-93 Gate

**Files:**

- Modify: `tests/acceptance/test_paper_spot_trade_history.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**

- Consumes all interfaces from Tasks 1–3.
- Produces deterministic acceptance evidence only.

- [ ] **Step 1: Refactor the acceptance fixture into focused helpers**

Extract without duplicating trading logic:

```python
def persistent_session(
    store: SQLiteTradeHistory,
) -> PersistentPaperSpotSQLiteSession:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    preset = RsiStepGridPreset.v1()
    core = PaperSpotSession(session_config(preset), market_data, symbol_rules(), preset)
    history = PaperSpotSQLiteHistory(
        PaperSpotHistoryContext(
            session_id=SESSION_ID,
            symbol=market_data.symbol,
            timeframe=market_data.timeframe,
            preset_version=preset.version,
            commission_asset="USDT",
        ),
        store,
    )
    return PersistentPaperSpotSQLiteSession(core, history)


def replay(session: PersistentPaperSpotSQLiteSession) -> None:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    for candle in load_candles_csv(FIXTURE_PATH, market_data):
        session.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )
```

Keep configuration values identical to the existing acceptance test.

- [ ] **Step 2: Write the idempotent replay acceptance**

Add:

```python
def test_replaying_the_same_session_does_not_duplicate_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "paper-spot-history.sqlite3"
    store = migrated_history(database_path)

    replay(persistent_session(store))
    replay(persistent_session(store))

    reopened = migrated_history(database_path)
    basket = reopened.get_basket(BASKET_ID)
    fills = reopened.list_fills(BASKET_ID)

    assert basket is not None
    assert basket.status is BasketStatus.CLOSED
    assert basket.entry_count == 1
    assert basket.net_realized_pnl == Decimal("13.84062222")
    assert len(fills) == 2
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
```

- [ ] **Step 3: Run acceptance against the completed hardened path**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

Expected: PASS. The focused RED tests in Tasks 1–3 prove the implementation
changes; this Task adds whole-flow regression evidence without changing
production behavior.

- [ ] **Step 4: Update the milestone record**

In `PROJECT_PLAN.md`, replace the DEV-92-only status paragraph with:

```markdown
สถานะ DEV-92–DEV-93: durable Paper Spot SQLite history รองรับ normalized
Basket/Fill, exact Decimal/UTC round-trip, deterministic IDs, atomic writes,
idempotent duplicate handling, ownership/lifecycle validation และ fail-closed
Session state แล้ว ส่วน query/pagination, Paper Futures, Desktop UI และ startup
Recovery ยังคงอยู่ในลำดับถัดไปของ milestone นี้
```

Do not mark Paper Trading Complete itself complete.

- [ ] **Step 5: Run complete verification**

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
git add tests/acceptance/test_paper_spot_trade_history.py PROJECT_PLAN.md
git commit -m "test: prove idempotent paper trade history"
```
