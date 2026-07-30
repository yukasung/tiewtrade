# DEV-127 Shared Persistence Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the duplicated Paper Spot and Paper Futures SQLite persistence coordinators with one fail-closed coordinator behind an application-owned contract while preserving each market's snapshot-to-history mapping.

**Architecture:** `application/session_persistence.py` owns the consumer-facing protocol and shared result/error types. `integrations/sqlite/session_persistence.py` implements the single generic state machine, while the existing Spot and Futures integration modules retain only identity validation, market-specific recorders, and focused composition functions.

**Tech Stack:** Python 3.12+, dataclasses, typing Protocol/Generic, pytest, unittest.mock, Ruff, mypy strict, SQLite

## Global Constraints

- Preserve the exact blocked message: `Session is blocked because Trade History persistence failed`.
- Call the application Session outside the persistence exception boundary; Session failures must not block persistence.
- Any recorder, mapping, or SQLite history failure must transition the coordinator to `BLOCKED` and re-raise the original exception.
- Do not add a `MarketType` conditional to the shared contract or coordinator.
- Keep Paper Spot and Paper Futures application sessions and history adapters separate.
- Delete `PersistentPaperSpotSQLiteSession`, `PersistentPaperFuturesSQLiteSession`, `PersistentPaperSpotSnapshot`, and `PersistentPaperFuturesSnapshot`; do not add compatibility aliases.
- Do not change trading decisions, SQLite schema, transaction boundaries, PnL, Basket, Entry Pair, Take Profit, or Liquidation rules.
- Use Paper sessions, fake processors, and fake recorders only; do not access Binance Private APIs or Live credentials.

---

## File Structure

- Create `src/tiewtrade/application/session_persistence.py`: application-owned contract, state, error, and generic persisted result.
- Modify `src/tiewtrade/integrations/sqlite/session_persistence.py`: the only common SQLite fail-closed coordinator implementation.
- Create `tests/unit/integrations/sqlite/test_session_persistence.py`: implementation-level state-machine tests independent of Spot/Futures.
- Modify `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`: Spot recorder and composition function only.
- Modify `src/tiewtrade/integrations/sqlite/persistent_paper_futures_session.py`: Futures recorder and composition function only.
- Modify existing unit, acceptance, and support files that construct either concrete coordinator so they use the new composition functions and application contract.

### Task 1: Application Contract and Common SQLite Coordinator

**Files:**
- Create: `src/tiewtrade/application/session_persistence.py`
- Modify: `src/tiewtrade/integrations/sqlite/session_persistence.py`
- Create: `tests/unit/integrations/sqlite/test_session_persistence.py`

**Interfaces:**
- Produces: `PersistenceState`, `SessionPersistenceBlockedError`, `PersistentSessionSnapshot[SessionSnapshotT]`, and `SessionPersistenceCoordinator[SessionSnapshotT]` from the application Module.
- Produces: `SQLiteSessionPersistenceCoordinator[SessionSnapshotT](session, record_snapshot)` from the SQLite integration.
- Consumes: any structural Session exposing `process_completed_candle(candle, *, received_at)` and any `Callable[[SessionSnapshotT], None]` recorder.

- [ ] **Step 1: Write failing common coordinator tests**

Create focused fakes and these tests in `tests/unit/integrations/sqlite/test_session_persistence.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceBlockedError,
)
from tiewtrade.integrations.sqlite.session_persistence import (
    SQLiteSessionPersistenceCoordinator,
)
from tiewtrade.market_data.candle import Candle


@dataclass(frozen=True, slots=True)
class FakeSnapshot:
    sequence: int


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> FakeSnapshot:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return FakeSnapshot(self.calls)


def candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
    )


def test_snapshot_is_recorded_before_ready_result_returns() -> None:
    session = FakeSession()
    recorded: list[FakeSnapshot] = []
    coordinator = SQLiteSessionPersistenceCoordinator(session, recorded.append)
    completed = candle()

    result = coordinator.process_completed_candle(
        completed,
        received_at=completed.close_time,
    )

    assert recorded == [result.session]
    assert result == result.__class__(
        session=FakeSnapshot(1),
        persistence_state=PersistenceState.READY,
    )


def test_recorder_failure_blocks_every_later_candle() -> None:
    session = FakeSession()

    def fail_recording(snapshot: FakeSnapshot) -> None:
        raise OSError("forced persistence failure")

    coordinator = SQLiteSessionPersistenceCoordinator(session, fail_recording)
    completed = candle()

    with pytest.raises(OSError, match="forced persistence failure"):
        coordinator.process_completed_candle(
            completed,
            received_at=completed.close_time,
        )
    with pytest.raises(
        SessionPersistenceBlockedError,
        match="Session is blocked because Trade History persistence failed",
    ):
        coordinator.process_completed_candle(
            completed,
            received_at=completed.close_time,
        )

    assert session.calls == 1


def test_session_failure_does_not_become_persistence_failure() -> None:
    session = FakeSession()
    session.error = RuntimeError("session failed")
    recorded: list[FakeSnapshot] = []
    coordinator = SQLiteSessionPersistenceCoordinator(session, recorded.append)
    completed = candle()

    with pytest.raises(RuntimeError, match="session failed"):
        coordinator.process_completed_candle(
            completed,
            received_at=completed.close_time,
        )

    session.error = None
    result = coordinator.process_completed_candle(
        completed,
        received_at=completed.close_time,
    )
    assert result.persistence_state is PersistenceState.READY
    assert session.calls == 2
    assert recorded == [FakeSnapshot(2)]
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_session_persistence.py -q
```

Expected: FAIL during collection because the application contract and common coordinator do not exist.

- [ ] **Step 3: Add the application-owned contract**

Create `src/tiewtrade/application/session_persistence.py` with these exact responsibilities:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Generic, Protocol, TypeVar

from tiewtrade.market_data.candle import Candle

SessionSnapshotT = TypeVar("SessionSnapshotT", covariant=True)


class PersistenceState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class SessionPersistenceBlockedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PersistentSessionSnapshot(Generic[SessionSnapshotT]):
    session: SessionSnapshotT
    persistence_state: PersistenceState


class SessionPersistenceCoordinator(Protocol[SessionSnapshotT]):
    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentSessionSnapshot[SessionSnapshotT]:
        pass
```

- [ ] **Step 4: Implement the single SQLite state machine**

Replace the duplicated state definitions in `src/tiewtrade/integrations/sqlite/session_persistence.py` with a generic implementation. Keep a separate covariant type variable for the structural processor and an invariant type variable for the coordinator:

```python
from collections.abc import Callable
from datetime import datetime
from typing import Generic, Protocol, TypeVar

from tiewtrade.application.session_persistence import (
    PersistenceState,
    PersistentSessionSnapshot,
    SessionPersistenceBlockedError,
)
from tiewtrade.market_data.candle import Candle

_SessionSnapshotT = TypeVar("_SessionSnapshotT")
_SessionSnapshotT_co = TypeVar("_SessionSnapshotT_co", covariant=True)


class _CompletedCandleProcessor(Protocol[_SessionSnapshotT_co]):
    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> _SessionSnapshotT_co:
        pass


class SQLiteSessionPersistenceCoordinator(Generic[_SessionSnapshotT]):
    def __init__(
        self,
        session: _CompletedCandleProcessor[_SessionSnapshotT],
        record_snapshot: Callable[[_SessionSnapshotT], None],
    ) -> None:
        self._session = session
        self._record_snapshot = record_snapshot
        self._state = PersistenceState.READY

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentSessionSnapshot[_SessionSnapshotT]:
        if self._state is PersistenceState.BLOCKED:
            raise SessionPersistenceBlockedError(
                "Session is blocked because Trade History persistence failed"
            )

        snapshot = self._session.process_completed_candle(
            candle,
            received_at=received_at,
        )
        try:
            self._record_snapshot(snapshot)
        except Exception:
            self._state = PersistenceState.BLOCKED
            raise

        return PersistentSessionSnapshot(
            session=snapshot,
            persistence_state=self._state,
        )
```

- [ ] **Step 5: Run focused tests, static checks, and commit**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_session_persistence.py -q
../../.venv/bin/python -m ruff check \
  src/tiewtrade/application/session_persistence.py \
  src/tiewtrade/integrations/sqlite/session_persistence.py \
  tests/unit/integrations/sqlite/test_session_persistence.py
../../.venv/bin/python -m mypy src
```

Expected: all commands PASS.

Commit:

```bash
git add src/tiewtrade/application/session_persistence.py \
  src/tiewtrade/integrations/sqlite/session_persistence.py \
  tests/unit/integrations/sqlite/test_session_persistence.py
git commit -m "refactor: add shared persistence coordinator"
```

### Task 2: Paper Spot Recorder and Composition

**Files:**
- Modify: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Modify: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`
- Modify: `tests/unit/application/test_paper_spot_session.py`
- Modify: `tests/acceptance/test_paper_spot_trade_history.py`
- Modify: `tests/acceptance/test_paper_trade_history_acceptance.py`
- Modify: `tests/support/paper_trade_history_acceptance.py`

**Interfaces:**
- Consumes: `SQLiteSessionPersistenceCoordinator[PaperSpotSessionSnapshot]` from Task 1.
- Produces: `create_persistent_paper_spot_session(session, history) -> SessionPersistenceCoordinator[PaperSpotSessionSnapshot]`.
- Preserves: all existing Spot identity and snapshot-to-history validation messages.

- [ ] **Step 1: Convert Spot tests and callers to the new contract first**

Change imports to:

```python
from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceBlockedError,
    SessionPersistenceCoordinator,
)
from tiewtrade.integrations.sqlite.persistent_paper_spot_session import (
    create_persistent_paper_spot_session,
)
```

Change every Spot construction from:

```python
PersistentPaperSpotSQLiteSession(session, history)
```

to:

```python
create_persistent_paper_spot_session(session, history)
```

Change helper return annotations to:

```python
SessionPersistenceCoordinator[PaperSpotSessionSnapshot]
```

Keep every existing assertion for entry durability, close durability, invalid snapshot mapping,
identity mismatch, fail-closed behavior, deterministic replay, and acceptance behavior.

- [ ] **Step 2: Run Spot tests and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_trade_history_acceptance.py -q
```

Expected: FAIL because `create_persistent_paper_spot_session` does not exist.

- [ ] **Step 3: Replace the Spot coordinator with a focused recorder and composition function**

Keep the current `_record_snapshot` body unchanged inside `_PaperSpotSnapshotRecorder.record` and compose the common coordinator:

```python
from tiewtrade.application.session_persistence import SessionPersistenceCoordinator
from tiewtrade.integrations.sqlite.session_persistence import (
    SQLiteSessionPersistenceCoordinator,
)


class _PaperSpotSnapshotRecorder:
    def __init__(self, history: PaperSpotSQLiteHistory) -> None:
        self._history = history

    def record(self, snapshot: PaperSpotSessionSnapshot) -> None:
        if snapshot.entry_fill is not None:
            if snapshot.basket_id is None:
                raise ValueError("entry Fill requires a Basket ID")
            self._history.record_entry(
                basket_id=snapshot.basket_id,
                entry_number=snapshot.basket_entry_count,
                fill=snapshot.entry_fill,
            )
        if snapshot.take_profit_fill is None and snapshot.closed_basket is None:
            return
        if snapshot.take_profit_fill is None or snapshot.closed_basket is None:
            raise ValueError(
                "Take Profit Fill and closed Basket must be present together"
            )
        if snapshot.basket_id != snapshot.closed_basket.basket_id:
            raise ValueError("closed Basket requires a matching Basket ID")
        self._history.record_close(
            basket_id=snapshot.closed_basket.basket_id,
            fill=snapshot.take_profit_fill,
            closed=snapshot.closed_basket,
        )


def create_persistent_paper_spot_session(
    session: PaperSpotSession,
    history: PaperSpotSQLiteHistory,
) -> SessionPersistenceCoordinator[PaperSpotSessionSnapshot]:
    if session.identity != history.session_identity:
        raise ValueError("Paper Spot Session and Trade History identity differ")
    recorder = _PaperSpotSnapshotRecorder(history)
    return SQLiteSessionPersistenceCoordinator(session, recorder.record)
```

Do not keep the old Spot coordinator or result dataclass.

- [ ] **Step 4: Run Spot/common tests and commit**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_session_persistence.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_trade_history_acceptance.py -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m mypy src
```

Expected: all commands PASS.

Commit:

```bash
git add src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  tests/support/paper_trade_history_acceptance.py
git commit -m "refactor: compose spot persistence coordinator"
```

### Task 3: Paper Futures Recorder and Composition

**Files:**
- Modify: `src/tiewtrade/integrations/sqlite/persistent_paper_futures_session.py`
- Modify: `tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py`
- Modify: `tests/acceptance/test_paper_futures_trade_history.py`
- Modify: `tests/support/paper_trade_history_acceptance.py`

**Interfaces:**
- Consumes: `SQLiteSessionPersistenceCoordinator[PaperFuturesSessionSnapshot]` from Task 1.
- Produces: `create_persistent_paper_futures_session(session, history) -> SessionPersistenceCoordinator[PaperFuturesSessionSnapshot]`.
- Preserves: Futures identity checks, same-candle liquidation entry numbering, Take Profit mapping, and Liquidation mapping.

- [ ] **Step 1: Convert Futures tests and callers to the new contract first**

Use the same application-owned imports as Task 2 and replace every construction with:

```python
create_persistent_paper_futures_session(session, history)
```

Annotate helper returns as:

```python
SessionPersistenceCoordinator[PaperFuturesSessionSnapshot]
```

Keep all current assertions, especially `closed_basket.entry_count` for same-candle entry plus
liquidation and both Take Profit/Liquidation exit cases.

- [ ] **Step 2: Run Futures tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py \
  tests/acceptance/test_paper_futures_trade_history.py -q
```

Expected: FAIL because `create_persistent_paper_futures_session` does not exist.

- [ ] **Step 3: Replace the Futures coordinator with a focused recorder and composition function**

Keep the current `_record_snapshot` body unchanged inside `_PaperFuturesSnapshotRecorder.record`:

```python
from tiewtrade.application.session_persistence import SessionPersistenceCoordinator
from tiewtrade.integrations.sqlite.session_persistence import (
    SQLiteSessionPersistenceCoordinator,
)


class _PaperFuturesSnapshotRecorder:
    def __init__(self, history: PaperFuturesSQLiteHistory) -> None:
        self._history = history

    def record(self, snapshot: PaperFuturesSessionSnapshot) -> None:
        if snapshot.entry_fill is not None:
            if snapshot.basket_id is None:
                raise ValueError("entry Fill requires a Basket ID")
            entry_number = snapshot.basket_entry_count
            if snapshot.closed_basket is not None:
                entry_number = snapshot.closed_basket.entry_count
            self._history.record_entry(
                basket_id=snapshot.basket_id,
                entry_number=entry_number,
                fill=snapshot.entry_fill,
            )

        if snapshot.exit_fill is None and snapshot.closed_basket is None:
            return
        if snapshot.exit_fill is None or snapshot.closed_basket is None:
            raise ValueError("exit Fill and closed Basket must be present together")
        if snapshot.basket_id != snapshot.closed_basket.basket_id:
            raise ValueError("closed Basket requires a matching Basket ID")
        self._history.record_close(
            basket_id=snapshot.closed_basket.basket_id,
            fill=snapshot.exit_fill,
            closed=snapshot.closed_basket,
        )


def create_persistent_paper_futures_session(
    session: PaperFuturesSession,
    history: PaperFuturesSQLiteHistory,
) -> SessionPersistenceCoordinator[PaperFuturesSessionSnapshot]:
    if session.identity != history.session_identity:
        raise ValueError("Paper Futures Session and Trade History identity differ")
    recorder = _PaperFuturesSnapshotRecorder(history)
    return SQLiteSessionPersistenceCoordinator(session, recorder.record)
```

Do not keep the old Futures coordinator or result dataclass.

- [ ] **Step 4: Run Futures/common tests and commit**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_session_persistence.py \
  tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/acceptance/test_paper_trade_history_acceptance.py -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m mypy src
```

Expected: all commands PASS.

Commit:

```bash
git add src/tiewtrade/integrations/sqlite/persistent_paper_futures_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_futures_session.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/support/paper_trade_history_acceptance.py
git commit -m "refactor: compose futures persistence coordinator"
```

### Task 4: Contract Cleanup and Full Verification

**Files:**
- Modify only files found by the cleanup searches below if stale imports remain.
- Verify: all `src/tiewtrade/**/*.py`, `tests/**/*.py`, and documentation checks.

**Interfaces:**
- Verifies: all callers use `SessionPersistenceCoordinator` and market-specific composition functions.
- Verifies: no old concrete coordinator/result name remains and the common path contains no `MarketType` dependency.

- [ ] **Step 1: Search for stale names and incorrect dependency direction**

Run:

```bash
rg -n "PersistentPaper(Spot|Futures)(SQLiteSession|Snapshot)" src tests
rg -n "from tiewtrade\.integrations|import tiewtrade\.integrations" \
  src/tiewtrade/application/session_persistence.py
rg -n "MarketType" \
  src/tiewtrade/application/session_persistence.py \
  src/tiewtrade/integrations/sqlite/session_persistence.py
```

Expected: all three commands produce no matches. If a stale import remains, replace it with the
application contract or the appropriate composition function; do not add an alias.

- [ ] **Step 2: Run complete verification**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main...HEAD
git status --short
```

Expected: 700 existing tests plus the new common coordinator tests PASS; Ruff, formatter,
mypy strict, docs tests, content checks, and diff check all PASS. The exact test count may increase
with the new tests.

- [ ] **Step 3: Commit any cleanup needed by the searches**

If Step 1 required changes:

```bash
git add src tests
git commit -m "refactor: remove duplicated persistence contracts"
```

If no cleanup change was needed, do not create an empty commit.

- [ ] **Step 4: Prepare the completion report**

Record:

- exact commits created for DEV-127
- exact verification commands and results
- confirmation that no Live or Binance Private API was used
- residual risks, if any
- branch name and worktree path

Do not push, merge, or delete the branch/worktree until the user gives the confirmations required
by `AGENTS.md`.
