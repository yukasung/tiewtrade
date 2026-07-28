# Paper Spot Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Paper Spot entry transitions atomic, fail closed on execution invariant failures, bind persistence to immutable Session identity, emit per-Candle close snapshots, and reject non-finite capital without changing deterministic replay output.

**Architecture:** Keep `PaperSpotSession` independent from `PaperFuturesSession`, while applying the proven candidate-copy and fail-closed patterns from Futures. Application owns Session orchestration and identity; SQLite integration validates identity and snapshot invariants; shared `trading` capital policy validates inputs at its boundary.

**Tech Stack:** Python 3.12, immutable dataclasses, `Decimal`, Pytest, Ruff, Mypy, SQLite integration adapters.

## Global Constraints

- Paper Spot and Paper Futures remain separate application orchestrators; do not create a shared base class, generic interface, registry, or factory.
- Paper and Live continue to share business policies but never execution adapters.
- Production behavior changes must follow failing-test-first TDD.
- Whole-Candle commit uses candidate copies of Basket, Entry Pair lifecycle, Strategy, Indicator state, pending intent, and counters; original objects must not receive partial mutation from a failed accepted Candle.
- Session identity is exactly `session_id`, `symbol`, `timeframe`, and `preset_version`.
- A failed Paper Spot execution becomes terminal `FAILED_CLOSED`, clears pending intent, and rejects later Candles.
- `take_profit_fill` and `closed_basket` are both present only on the Candle that closes the Basket and are both absent otherwise.
- Deterministic 40-Candle replay output remains exactly `{"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}`.
- Use Paper and fake objects only; do not call Binance private APIs or send Live orders.

---

### Task 1: Reject non-finite Paper Spot capital

**Files:**
- Modify: `src/tiewtrade/trading/capital.py`
- Test: `tests/unit/trading/test_capital.py`

**Interfaces:**
- Consumes: `SpotCapitalPlan.from_available(available: Decimal, spot_policy: SpotTradingPolicy, entry_policy: EntryPolicy) -> SpotCapitalPlan`
- Produces: the same public method, now raising `ValueError("available capital must be finite and positive")` for non-finite or non-positive input.

- [ ] **Step 1: Write the failing parameterized test**

Replace the zero-only Spot test with the complete invalid-input contract:

```python
@pytest.mark.parametrize(
    "available",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_spot_capital_plan_rejects_invalid_available_capital(
    available: Decimal,
) -> None:
    with pytest.raises(ValueError, match="available capital"):
        SpotCapitalPlan.from_available(
            available,
            SpotTradingPolicy(trading_capital_ratio=Decimal("0.80")),
            EntryPolicy(max_entries=10),
        )
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/trading/test_capital.py::test_spot_capital_plan_rejects_invalid_available_capital -q
```

Expected: `NaN` errors with `decimal.InvalidOperation` or Infinity cases do not raise the required `ValueError`.

- [ ] **Step 3: Implement the minimal boundary validation**

Change `SpotCapitalPlan.from_available()` to:

```python
if not available.is_finite() or available <= 0:
    raise ValueError("available capital must be finite and positive")
```

Keep all allocation calculations unchanged.

- [ ] **Step 4: Verify GREEN and the capital module**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/trading/test_capital.py -q
```

Expected: all capital tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/tiewtrade/trading/capital.py tests/unit/trading/test_capital.py
git commit -m "fix: validate Paper Spot capital boundary"
```

### Task 2: Bind Paper Spot persistence to immutable Session identity

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `src/tiewtrade/integrations/sqlite/paper_spot_history.py`
- Modify: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Test: `tests/unit/application/test_paper_spot_session.py`
- Test: `tests/unit/integrations/sqlite/test_paper_spot_history.py`
- Test: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

**Interfaces:**
- Produces: immutable `PaperSpotSessionIdentity(session_id: UUID, symbol: str, timeframe: str, preset_version: str)`.
- Produces: `PaperSpotSession.identity -> PaperSpotSessionIdentity`.
- Produces: `PaperSpotHistoryContext.session_identity -> PaperSpotSessionIdentity` and `PaperSpotSQLiteHistory.session_identity -> PaperSpotSessionIdentity`.
- Consumes: `PersistentPaperSpotSQLiteSession` compares `session.identity` with `history.session_identity` before retaining either dependency.

- [ ] **Step 1: Write failing identity exposure tests**

Add the application import and test:

```python
from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionIdentity,
)


def test_session_exposes_immutable_persistence_identity() -> None:
    application = paper_session()

    assert application.identity == PaperSpotSessionIdentity(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )
```

In `test_paper_spot_history.py`, reuse the existing `history` fixture and add:

```python
def test_history_exposes_session_identity(
    history: PaperSpotSQLiteHistory,
) -> None:
    assert history.session_identity == PaperSpotSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )
```

Add only the missing `PaperSpotSessionIdentity` import; the history fixture and
`PaperSpotSQLiteHistory` import already exist.

- [ ] **Step 2: Write the failing persistence mismatch test**

Add a focused identity helper and mismatch test:

```python
def session_identity() -> PaperSpotSessionIdentity:
    return PaperSpotSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )


def test_constructor_rejects_mismatched_session_and_history_identity() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = replace(  # type: ignore[misc]
        session_identity(),
        timeframe="15m",
    )

    with pytest.raises(ValueError, match="identity"):
        PersistentPaperSpotSQLiteSession(session, history)
```

Add `replace` to the dataclasses import. Introduce this helper for all existing mock-based
constructor calls:

```python
def persistent_session(
    session: PaperSpotSession,
    history: PaperSpotSQLiteHistory,
) -> PersistentPaperSpotSQLiteSession:
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = session_identity()  # type: ignore[misc]
    return PersistentPaperSpotSQLiteSession(session, history)
```

Replace existing direct mock-based `PersistentPaperSpotSQLiteSession(session, history)`
calls with `persistent_session(session, history)` so those tests explicitly satisfy the new
boundary.

- [ ] **Step 3: Run the identity tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_session_exposes_immutable_persistence_identity \
  tests/unit/integrations/sqlite/test_paper_spot_history.py::test_history_exposes_session_identity \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_constructor_rejects_mismatched_session_and_history_identity -q
```

Expected: imports/properties do not exist or the mismatch constructor does not raise.

- [ ] **Step 4: Implement the immutable identity contracts**

In `paper_spot_session.py`, add:

```python
@dataclass(frozen=True, slots=True)
class PaperSpotSessionIdentity:
    session_id: UUID
    symbol: str
    timeframe: str
    preset_version: str
```

Snapshot identity in `PaperSpotSession.__init__`:

```python
self._identity = PaperSpotSessionIdentity(
    session_id=session.session_id,
    symbol=market_data.symbol,
    timeframe=market_data.timeframe,
    preset_version=session.preset_version,
)
```

Expose it read-only:

```python
@property
def identity(self) -> PaperSpotSessionIdentity:
    return self._identity
```

In `paper_spot_history.py`, add the application identity import and properties:

```python
@property
def session_identity(self) -> PaperSpotSessionIdentity:
    return PaperSpotSessionIdentity(
        session_id=self.session_id,
        symbol=self.symbol,
        timeframe=self.timeframe,
        preset_version=self.preset_version,
    )
```

on `PaperSpotHistoryContext`, and:

```python
@property
def session_identity(self) -> PaperSpotSessionIdentity:
    return self._context.session_identity
```

on `PaperSpotSQLiteHistory`.

In the persistent constructor, validate before assignment:

```python
if session.identity != history.session_identity:
    raise ValueError("Paper Spot Session and Trade History identity differ")
```

- [ ] **Step 5: Verify GREEN and all Spot persistence tests**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  src/tiewtrade/integrations/sqlite/paper_spot_history.py \
  src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py
git commit -m "feat: bind Paper Spot persistence identity"
```

### Task 3: Make Paper Spot Entry atomic and fail closed

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Test: `tests/unit/application/test_paper_spot_session.py`
- Test: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

**Interfaces:**
- Produces: `PaperSpotSessionState` with `ACTIVE` and `FAILED_CLOSED`.
- Produces: `PaperSpotFailureReason.EXECUTION_ERROR` and `PaperSpotSessionError`.
- Produces: `PaperSpotSession.snapshot -> PaperSpotSessionSnapshot`.
- Changes: `PaperSpotSessionSnapshot` adds required `state` and `failure_reason` fields.
- Preserves: minimum-notional rejection re-arms Strategy and is not a failure.

- [ ] **Step 1: Write the failing atomicity and failure-cause test**

Add imports for `EntryPairLifecycle` and the new contracts, then add:

```python
def test_entry_transition_is_atomic_when_lifecycle_rejects_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent),
        open_price="120",
        close_price="121",
    )
    first_fill = application.process_completed_candle(
        first_fill_candle,
        received_at=first_fill_candle.close_time,
    )
    assert first_fill.basket_entry_count == 1

    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    second_fill_candle = candle(
        minute_after(second_intent),
        open_price="100",
        close_price="101",
    )

    def reject_fill(self: EntryPairLifecycle, filled_at: datetime) -> None:
        raise ValueError("entry is blocked by pair lifecycle")

    monkeypatch.setattr(EntryPairLifecycle, "record_fill", reject_fill)

    with pytest.raises(PaperSpotSessionError, match="execution failed") as captured:
        application.process_completed_candle(
            second_fill_candle,
            received_at=second_fill_candle.close_time,
        )

    assert isinstance(captured.value.__cause__, ValueError)
    assert str(captured.value.__cause__) == "entry is blocked by pair lifecycle"
    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.failure_reason is PaperSpotFailureReason.EXECUTION_ERROR
    assert application.snapshot.pending_intent is None
    assert application.snapshot.basket_entry_count == 1
    assert application._lifecycle.entry_count == 1
```

- [ ] **Step 2: Write failing tests for terminal rejection and warm-up**

Add:

```python
def test_failed_closed_session_rejects_later_candles_and_warm_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    failed_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )

    def raise_execution_error(*args: object, **kwargs: object) -> None:
        raise ValueError("broken execution invariant")

    monkeypatch.setattr(application._executor, "fill_entry", raise_execution_error)
    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        application.process_completed_candle(
            failed_candle,
            received_at=failed_candle.close_time,
        )

    before = application.snapshot
    following = candle(
        minute_after(pending) + 5,
        open_price="121",
        close_price="122",
    )
    after = application.process_completed_candle(
        following,
        received_at=following.close_time,
    )

    assert after.accepted is False
    assert after.state is before.state
    assert after.basket_id == before.basket_id
    assert after.basket_entry_count == before.basket_entry_count
    with pytest.raises(PaperSpotSessionError, match="not active"):
        application.warm_up_completed_candles(
            [following],
            received_at=following.close_time,
        )
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_entry_transition_is_atomic_when_lifecycle_rejects_fill \
  tests/unit/application/test_paper_spot_session.py::test_failed_closed_session_rejects_later_candles_and_warm_up -q
```

Expected: new contracts are missing and/or partial Basket mutation remains.

- [ ] **Step 4: Add Spot-specific state and snapshot contracts**

Add `deepcopy` and `StrEnum` imports, then define:

```python
class PaperSpotSessionState(StrEnum):
    ACTIVE = "active"
    FAILED_CLOSED = "failed_closed"


class PaperSpotFailureReason(StrEnum):
    EXECUTION_ERROR = "execution_error"


class PaperSpotSessionError(RuntimeError):
    """Paper Spot stopped because an execution invariant failed."""
```

Add these required fields to `PaperSpotSessionSnapshot`:

```python
state: PaperSpotSessionState
failure_reason: PaperSpotFailureReason | None
```

Initialize state in the Session:

```python
self._state = PaperSpotSessionState.ACTIVE
self._failure_reason: PaperSpotFailureReason | None = None
```

Expose a snapshot:

```python
@property
def snapshot(self) -> PaperSpotSessionSnapshot:
    return self._snapshot(accepted=self._state is PaperSpotSessionState.ACTIVE)
```

Pass `state=self._state` and `failure_reason=self._failure_reason` when constructing every
snapshot. Update direct `PaperSpotSessionSnapshot` fixtures in the persistent-session tests
with:

```python
state=PaperSpotSessionState.ACTIVE,
failure_reason=None,
```

- [ ] **Step 5: Add the fail-closed execution boundary**

At the start of `process_completed_candle()`:

```python
if self._state is not PaperSpotSessionState.ACTIVE:
    return self._snapshot(accepted=False)
```

Keep completed-candle acceptance outside the execution `try`, and wrap all subsequent
orchestration:

```python
try:
    # existing Entry, Take Profit, indicator, and Strategy flow
except PaperSpotSessionError:
    raise
except Exception as error:
    self._fail_closed()
    raise PaperSpotSessionError("Paper Spot execution failed") from error
```

Guard warm-up before iteration:

```python
if self._state is not PaperSpotSessionState.ACTIVE:
    raise PaperSpotSessionError("Paper Spot session is not active")
```

Add:

```python
def _fail_closed(self) -> None:
    self._state = PaperSpotSessionState.FAILED_CLOSED
    self._failure_reason = PaperSpotFailureReason.EXECUTION_ERROR
    self._pending_intent = None
    self._strategy = RsiStepGridStrategy(self._session.session_id, self._preset)
```

- [ ] **Step 6: Implement candidate-copy Entry commit**

Replace the successful Fill mutation block with:

```python
intent = self._pending_intent
fill = self._executor.fill_entry(intent, candle)
if fill is None:
    self._strategy.on_entry_rejected(intent.intent_id)
    self._pending_intent = None
    return None

if self._basket is None:
    basket_id = uuid5(
        self._session.session_id,
        f"basket:{self._closed_basket_count + 1}",
    )
    candidate_basket = Basket(
        basket_id,
        self._session.entry_policy,
        self._preset.take_profit_atr_multiplier,
    )
else:
    candidate_basket = deepcopy(self._basket)
candidate_lifecycle = deepcopy(self._lifecycle)
candidate_strategy = deepcopy(self._strategy)

candidate_basket.add_entry(
    price=fill.price,
    quantity=fill.quantity,
    fee=fill.fee,
    filled_at=fill.filled_at,
    atr=intent.atr,
    tick_size=self._symbol_rules.tick_size,
)
candidate_lifecycle.record_fill(fill.filled_at)
candidate_strategy.on_entry_filled(intent.intent_id)

self._basket = candidate_basket
self._lifecycle = candidate_lifecycle
self._strategy = candidate_strategy
self._pending_intent = None
return fill
```

- [ ] **Step 7: Verify GREEN and Spot Session integration**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

Expected: all selected tests pass and replay output remains unchanged.

- [ ] **Step 8: Commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py
git commit -m "fix: make Paper Spot entry fail closed atomically"
```

### Task 4: Make Paper Spot close snapshots per-Candle and invariant-safe

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Test: `tests/unit/application/test_paper_spot_session.py`
- Test: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`
- Test: `tests/acceptance/test_paper_spot_replay.py`

**Interfaces:**
- Preserves: `PaperSpotSessionSnapshot.take_profit_fill` name for existing consumers.
- Changes: `take_profit_fill` and `closed_basket` describe only the current Candle.
- Strengthens: persistent close requires both fields and matching Basket IDs.

- [ ] **Step 1: Write the failing non-sticky snapshot test**

In the existing multi-Basket test, change the assertion after the next Basket Entry from:

```python
assert new_fill.take_profit_fill is not None
```

to:

```python
assert new_fill.take_profit_fill is None
assert new_fill.closed_basket is None
```

This uses an existing flow that closes one Basket and processes later Candles, proving the
old `_latest_take_profit_fill` no longer leaks into a later snapshot.

Strengthen `test_replaying_the_tracer_fixture_is_deterministic()` with the exact stable
serialization contract:

```python
assert first.to_json() == (
    '{"accepted_candles":40,"closed_baskets":1,'
    '"current_entries":0,"realized_pnl":"13.84062222"}'
)
```

- [ ] **Step 2: Write failing persistent snapshot invariant tests**

Add:

```python
def test_take_profit_fill_without_closed_basket_blocks_persistence() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = replace(
        entry_snapshot(),
        entry_fill=None,
        take_profit_fill=exit_fill(),
        closed_basket=None,
    )
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="present together"):
        persistent.process_completed_candle(candle, received_at=candle.close_time)

    history.record_close.assert_not_called()


def test_closed_basket_with_mismatched_snapshot_basket_id_blocks_persistence() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = replace(
        close_snapshot(),
        basket_id=UUID("00000000-0000-0000-0000-000000000199"),
    )
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="matching Basket ID"):
        persistent.process_completed_candle(candle, received_at=candle.close_time)

    history.record_close.assert_not_called()
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_closed_two_entry_basket_resets_lifecycle_for_a_new_basket \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_take_profit_fill_without_closed_basket_blocks_persistence \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_closed_basket_with_mismatched_snapshot_basket_id_blocks_persistence -q
```

Expected: the later snapshot still contains the old Fill and persistent pair/identity checks
do not all raise.

- [ ] **Step 4: Make Take Profit Fill a local Candle result**

Remove `_latest_take_profit_fill`. Change the processing flow to:

```python
take_profit_fill: PaperSpotExitFill | None = None
closed_basket: ClosedBasket | None = None
if basket_existed_at_candle_open and not entry_filled_on_current_candle:
    take_profit_fill = self._fill_take_profit(candle)
    if take_profit_fill is not None:
        closed_basket = self._close_basket(take_profit_fill)
```

Change `_fill_take_profit()` to return the executor result without mutation:

```python
def _fill_take_profit(self, candle: Candle) -> PaperSpotExitFill | None:
    assert self._basket is not None
    return self._executor.fill_take_profit(self._basket, candle)
```

Move close mutation into:

```python
def _close_basket(self, exit_fill: PaperSpotExitFill) -> ClosedBasket:
    assert self._basket is not None
    closed = self._basket.close(
        exit_price=exit_fill.price,
        exit_fee=exit_fill.fee,
        closed_at=exit_fill.filled_at,
    )
    self._basket = None
    self._lifecycle.reset()
    self._closed_basket_count += 1
    return closed
```

Add `take_profit_fill: PaperSpotExitFill | None = None` to `_snapshot()` and pass the local
value from `process_completed_candle()`. Construct snapshots with that parameter, never a
stored previous Fill.

- [ ] **Step 5: Enforce the persistent pair and Basket ID contract**

Replace the close branch in `_record_snapshot()` with:

```python
if snapshot.take_profit_fill is None and snapshot.closed_basket is None:
    return
if snapshot.take_profit_fill is None or snapshot.closed_basket is None:
    raise ValueError("Take Profit Fill and closed Basket must be present together")
if snapshot.basket_id != snapshot.closed_basket.basket_id:
    raise ValueError("closed Basket requires a matching Basket ID")
self._history.record_close(
    basket_id=snapshot.closed_basket.basket_id,
    fill=snapshot.take_profit_fill,
    closed=snapshot.closed_basket,
)
```

- [ ] **Step 6: Verify GREEN, deterministic replay, and all repository gates**

Run:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix ../../docs-site test
npm --prefix ../../docs-site run check:content
git diff --check
```

Expected: all commands exit `0`; replay assertion remains exactly the Global Constraint
JSON.

- [ ] **Step 7: Commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py
git commit -m "fix: scope Paper Spot close snapshots per Candle"
```

### Task 5: Expand atomicity to the whole accepted Candle and close review findings

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `tests/unit/application/test_paper_spot_session.py`
- Modify: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`
- Modify: `docs/superpowers/plans/2026-07-28-paper-spot-hardening.md`

**Interfaces:**
- Produces: private `_PaperSpotTransition` that owns candidate Basket, lifecycle,
  Strategy, Indicator, pending intent, and closed-Basket count for one accepted Candle.
- Changes: `PaperSpotSession` commits candidate state only after Entry, Take Profit,
  Indicator, and Strategy steps all succeed.
- Preserves: public Session, snapshot, identity, persistence, replay, and fail-closed
  contracts from Tasks 1–4.

- [ ] **Step 1: Write failing late-Entry and late-close durability tests**

เพิ่ม helper ที่สร้าง persistent coordinator จาก real Session กับ mock History โดยกำหนด
identity ให้ตรงกัน:

```python
def persistent_spot_session(
    application: PaperSpotSession,
) -> tuple[PersistentPaperSpotSQLiteSession, PaperSpotSQLiteHistory]:
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    history.session_identity = application.identity  # type: ignore[misc]
    return PersistentPaperSpotSQLiteSession(application, history), history
```

เพิ่ม test ที่ทำให้ Indicator ล้มหลัง Entry Fill candidate ถูกสร้างแล้ว:

```python
def test_late_entry_failure_does_not_commit_or_persist_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    persistent, history = persistent_spot_session(application)
    entry_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )

    def raise_indicator_error(*args: object, **kwargs: object) -> None:
        raise ValueError("indicator transition failed")

    monkeypatch.setattr(WilderIndicators, "update", raise_indicator_error)

    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        persistent.process_completed_candle(
            entry_candle,
            received_at=entry_candle.close_time,
        )

    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.basket_id is None
    assert application.snapshot.basket_entry_count == 0
    history.record_entry.assert_not_called()
    history.record_close.assert_not_called()
```

เพิ่ม test ที่บันทึก Entry สำเร็จก่อน แล้วทำให้ Indicator ล้มหลัง candidate Basket close:

```python
def test_late_close_failure_keeps_open_basket_and_does_not_persist_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    persistent, history = persistent_spot_session(application)
    entry_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )
    entry = persistent.process_completed_candle(
        entry_candle,
        received_at=entry_candle.close_time,
    )
    assert entry.session.basket_entry_count == 1

    def raise_indicator_error(*args: object, **kwargs: object) -> None:
        raise ValueError("indicator transition failed after close")

    monkeypatch.setattr(WilderIndicators, "update", raise_indicator_error)
    close_candle = candle(
        minute_after(pending) + 5,
        open_price="125",
        close_price="130",
        high="1000",
    )

    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        persistent.process_completed_candle(
            close_candle,
            received_at=close_candle.close_time,
        )

    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.basket_id == entry.session.basket_id
    assert application.snapshot.basket_entry_count == 1
    history.record_entry.assert_called_once()
    history.record_close.assert_not_called()
```

เพิ่ม imports สำหรับ `create_autospec`, `WilderIndicators`, `PaperSpotSQLiteHistory` และ
`PersistentPaperSpotSQLiteSession` ใน test file เดียวกัน

- [ ] **Step 2: Write the failing Strategy-candidate rollback regression**

เพิ่ม test ที่ callback บน candidate Strategy mutate ก่อน raise:

```python
def test_strategy_callback_failure_does_not_commit_candidate_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent),
        open_price="120",
        close_price="121",
    )
    application.process_completed_candle(
        first_fill_candle,
        received_at=first_fill_candle.close_time,
    )
    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    original_strategy = application._strategy
    original_callback = RsiStepGridStrategy.on_entry_filled

    def mutate_then_raise(
        self: RsiStepGridStrategy,
        intent_id: str,
    ) -> None:
        original_callback(self, intent_id)
        raise ValueError("strategy transition failed")

    monkeypatch.setattr(RsiStepGridStrategy, "on_entry_filled", mutate_then_raise)
    second_fill_candle = candle(
        minute_after(second_intent),
        open_price="100",
        close_price="101",
    )

    with pytest.raises(PaperSpotSessionError) as captured:
        application.process_completed_candle(
            second_fill_candle,
            received_at=second_fill_candle.close_time,
        )

    assert str(captured.value.__cause__) == "strategy transition failed"
    assert application.snapshot.basket_entry_count == 1
    assert application._lifecycle.entry_count == 1
    assert original_strategy._pending_intent == second_intent
    assert application._strategy is not original_strategy
```

- [ ] **Step 3: Parameterize identity mismatch coverage for all four fields**

แทน test mismatch เดิมด้วย:

```python
@pytest.mark.parametrize(
    "mismatched_identity",
    [
        replace(
            session_identity(),
            session_id=UUID("00000000-0000-0000-0000-000000000199"),
        ),
        replace(session_identity(), symbol="ETHUSDT"),
        replace(session_identity(), timeframe="15m"),
        replace(session_identity(), preset_version="rsi-step-grid-v2"),
    ],
)
def test_constructor_rejects_mismatched_session_and_history_identity(
    mismatched_identity: PaperSpotSessionIdentity,
) -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = mismatched_identity  # type: ignore[misc]

    with pytest.raises(
        ValueError,
        match="Paper Spot Session and Trade History identity differ",
    ):
        PersistentPaperSpotSQLiteSession(session, history)
```

- [ ] **Step 4: Run focused tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_late_entry_failure_does_not_commit_or_persist_entry \
  tests/unit/application/test_paper_spot_session.py::test_late_close_failure_keeps_open_basket_and_does_not_persist_close \
  tests/unit/application/test_paper_spot_session.py::test_strategy_callback_failure_does_not_commit_candidate_transition \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_constructor_rejects_mismatched_session_and_history_identity -q
```

Expected: late Entry/close tests แสดงว่า state จริงถูก mutate ก่อน error; Strategy test หรือ
identity matrix ยังไม่ผ่าน contract ใหม่ทั้งหมด

- [ ] **Step 5: Introduce the whole-Candle candidate state**

เพิ่ม private mutable dataclass ใน `paper_spot_session.py`:

```python
@dataclass(slots=True)
class _PaperSpotTransition:
    indicators: WilderIndicators
    strategy: RsiStepGridStrategy
    lifecycle: EntryPairLifecycle
    basket: Basket | None
    pending_intent: EntryIntent | None
    closed_basket_count: int
```

สร้าง candidate จาก state เดิม:

```python
def _new_transition(self) -> _PaperSpotTransition:
    return _PaperSpotTransition(
        indicators=deepcopy(self._indicators),
        strategy=deepcopy(self._strategy),
        lifecycle=deepcopy(self._lifecycle),
        basket=deepcopy(self._basket),
        pending_intent=self._pending_intent,
        closed_basket_count=self._closed_basket_count,
    )
```

และ commit พร้อมกันหลังทุก fallible step สำเร็จ:

```python
def _commit_transition(self, transition: _PaperSpotTransition) -> None:
    self._indicators = transition.indicators
    self._strategy = transition.strategy
    self._lifecycle = transition.lifecycle
    self._basket = transition.basket
    self._pending_intent = transition.pending_intent
    self._closed_basket_count = transition.closed_basket_count
```

- [ ] **Step 6: Run all accepted-Candle behavior on the candidate**

หลัง Candle acceptance ให้สร้าง `transition = self._new_transition()` แล้วเปลี่ยน private
helpers ให้รับ transition เป็น argument:

```python
entry_fill = self._fill_pending_intent(transition, candle)
take_profit_fill = self._fill_take_profit(transition, candle)
closed_basket = self._close_basket(transition, take_profit_fill)
indicators = transition.indicators.update(candle)
self._evaluate_strategy(transition, candle, indicators)
self._commit_transition(transition)
```

`_fill_pending_intent()` ต้อง mutate `transition.basket`, `transition.lifecycle`,
`transition.strategy` และ `transition.pending_intent` โดยตรง และลบ candidate-copy ชั้นใน
ที่ซ้ำซ้อนจาก Task 3

`_fill_take_profit()`, `_close_basket()` และ Strategy evaluation ต้องอ่าน/เขียน state
ผ่าน transition เท่านั้น โดยเพิ่ม `transition.closed_basket_count` เมื่อ close สำเร็จ

`_commit_transition()` ต้องถูกเรียกหลัง Indicator/Strategy step และก่อนสร้าง success
snapshot เท่านั้น หาก exception เกิดก่อนหน้านั้นให้ใช้ fail-closed boundary เดิมโดยไม่
commit candidate

- [ ] **Step 7: Translate implementation-plan prose to Thai**

แปล narrative, instructions, expected results และ explanatory text ในไฟล์แผนนี้เป็น
ภาษาไทยทั้งหมด คง required writing-plans header, section labels (`Goal`,
`Architecture`, `Tech Stack`, `Global Constraints`, `Task`, `Files`, `Interfaces`,
`Step`), identifiers, code, commands, paths และ exact error strings เป็นอังกฤษ

- [ ] **Step 8: Verify GREEN and all repository gates**

Run:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix ../../docs-site test
npm --prefix ../../docs-site run check:content
git diff --check
```

Expected: ทุก command exit `0`, late-failure tests ไม่พบ memory/durable divergence และ
replay JSON ยังคงตรง Global Constraint ทุกตัวอักษร

- [ ] **Step 9: Commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  docs/superpowers/specs/2026-07-28-paper-spot-hardening-design.md \
  docs/superpowers/plans/2026-07-28-paper-spot-hardening.md
git commit -m "fix: make Paper Spot Candle transitions atomic"
```
