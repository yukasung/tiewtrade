# DEV-101 Market Data Diagnostics Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove unbounded Runtime diagnostic history, make backfill observation match the real call graph, and classify Binance source failures for diagnostics without changing Runtime decisions.

**Architecture:** `MarketDataRuntimeStatus` retains only the current immutable snapshot and emits state transitions through an optional synchronous callback owned by test composition. Existing action-oriented source exception types remain the Runtime policy seam, while a new `MarketDataFailureKind` supplies transport/protocol/payload metadata at the Binance adapter seam. Backfill keeps one required buffered `Candle`, removing an unreachable optional branch.

**Tech Stack:** Python 3.14, asyncio, aiohttp, pytest, Ruff, mypy

## Global Constraints

- Keep `MarketDataRuntimeSnapshot`, observable state sequence, Runtime reasons, bounded reconnect delays `1`, `2`, `4` seconds, source deadlines `30` seconds, and rate-limit fallback `60` seconds unchanged.
- `MarketDataFailureKind` is diagnostic metadata only; `MarketDataRuntime` must continue choosing retry, rate-limit, timeout, and fail-closed actions from the existing exception types.
- Production composition passes no transition callback and must retain no transition-history collection.
- The optional transition callback receives the initial `STARTING` snapshot and every state transition, but not `record_delivery()` watermark-only updates.
- Isolate `Exception` from the synchronous transition callback so it cannot change Runtime decisions; do not catch `BaseException` or add logging/operational events.
- `_backfill_to_boundary()` and `CompletedCandlePipeline.process_backfill()` require a buffered `Candle`; no `None` path remains.
- Tests use fake sources/transports only. Do not use credentials, Binance Private APIs, network calls, or Live Orders.
- Do not add structured logging (DEV-100), test-suite mypy expansion (DEV-102), a generic error framework, registry, factory, or base adapter.

---

### Task 1: Replace production state history with a test-owned transition observer

**Files:**
- Modify: `src/tiewtrade/market_data/runtime_state.py`
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `tests/unit/market_data/test_runtime_state.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `tests/acceptance/test_public_market_data_runtime.py`

**Interfaces:**
- Consumes: existing immutable `MarketDataRuntimeSnapshot` and `MarketDataRuntimeState`
- Produces: optional `on_transition: Callable[[MarketDataRuntimeSnapshot], None] | None` keyword on `MarketDataRuntime` and `MarketDataRuntimeStatus`; production `visited_states` properties are removed

- [ ] **Step 1: Write failing observer tests and move history ownership into test code**

Replace `test_status_owns_transitions_and_history` in `tests/unit/market_data/test_runtime_state.py` with an observer-owned sequence test:

```python
def test_status_publishes_transitions_without_retaining_history() -> None:
    observed: list[MarketDataRuntimeSnapshot] = []
    status = MarketDataRuntimeStatus(
        SequenceClock(START, TRANSITION),
        on_transition=observed.append,
    )

    status.transition(
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeReason.START_REQUESTED,
    )

    assert [snapshot.state for snapshot in observed] == [
        MarketDataRuntimeState.STARTING,
        MarketDataRuntimeState.WARMING_UP,
    ]
    assert status.snapshot.transitioned_at == TRANSITION
    assert not hasattr(status, "visited_states")
```

Extend `test_delivery_preserves_transition_metadata` with an observer and prove a watermark-only update emits no transition:

```python
observed: list[MarketDataRuntimeSnapshot] = []
status = MarketDataRuntimeStatus(
    SequenceClock(START, TRANSITION),
    on_transition=observed.append,
)
# existing transition and record_delivery calls
assert len(observed) == 2
```

In `tests/unit/market_data/test_runtime.py`, add a test-owned recorder and observed Runtime immediately above `runtime_for`:

```python
class RuntimeStateRecorder:
    def __init__(self) -> None:
        self.snapshots: list[MarketDataRuntimeSnapshot] = []

    def __call__(self, snapshot: MarketDataRuntimeSnapshot) -> None:
        self.snapshots.append(snapshot)

    @property
    def states(self) -> tuple[MarketDataRuntimeState, ...]:
        return tuple(snapshot.state for snapshot in self.snapshots)


class ObservedMarketDataRuntime(MarketDataRuntime):
    def __init__(
        self,
        *,
        config: MarketDataConfig,
        warm_up_count: int,
        source: FakeSource,
        sink: RecordingSink,
        scheduler: FakeScheduler,
    ) -> None:
        self._state_recorder = RuntimeStateRecorder()
        super().__init__(
            config=config,
            warm_up_count=warm_up_count,
            source=source,
            sink=sink,
            scheduler=scheduler,
            on_transition=self._state_recorder,
        )

    @property
    def observed_states(self) -> tuple[MarketDataRuntimeState, ...]:
        return self._state_recorder.states
```

Change `runtime_for()` to construct and return `ObservedMarketDataRuntime`, then replace every `runtime.visited_states` reference in this test file with `runtime.observed_states`. Change `run_until_recovered_or_runtime_stops()` to accept `ObservedMarketDataRuntime` because it reads `observed_states`.

In `tests/acceptance/test_public_market_data_runtime.py`, create a local `observed_states: list[MarketDataRuntimeState]`, pass an `on_transition` lambda that appends `snapshot.state`, and replace the `runtime.visited_states` ordering assertion with the local list:

```python
observed_states: list[MarketDataRuntimeState] = []
runtime = MarketDataRuntime(
    # existing arguments
    on_transition=lambda snapshot: observed_states.append(snapshot.state),
)

assert observed_states.index(MarketDataRuntimeState.WARMING_UP) < (
    observed_states.index(MarketDataRuntimeState.LIVE)
)
assert not hasattr(runtime, "visited_states")
```

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_runtime_state.py \
  tests/unit/market_data/test_runtime.py \
  tests/acceptance/test_public_market_data_runtime.py
```

Expected: FAIL because `MarketDataRuntimeStatus` and `MarketDataRuntime` do not accept `on_transition`, and production still exposes `visited_states`.

- [ ] **Step 3: Implement the observer and delete production history**

In `src/tiewtrade/market_data/runtime_state.py`, delete `_visited_states` and its property. Store the callback, publish the initial snapshot after construction, and publish after `transition()`:

```python
class MarketDataRuntimeStatus:
    def __init__(
        self,
        now: Callable[[], datetime],
        *,
        on_transition: Callable[[MarketDataRuntimeSnapshot], None] | None = None,
    ) -> None:
        self._now = now
        self._on_transition = on_transition
        self._snapshot = MarketDataRuntimeSnapshot(
            state=MarketDataRuntimeState.STARTING,
            reason=MarketDataRuntimeReason.START_REQUESTED,
            transitioned_at=self._now(),
            last_accepted_open_time=None,
        )
        self._publish_transition()

    def transition(
        self,
        state: MarketDataRuntimeState,
        reason: MarketDataRuntimeReason,
    ) -> None:
        self._snapshot = MarketDataRuntimeSnapshot(
            state=state,
            reason=reason,
            transitioned_at=self._now(),
            last_accepted_open_time=self._snapshot.last_accepted_open_time,
        )
        self._publish_transition()

    def _publish_transition(self) -> None:
        if self._on_transition is not None:
            try:
                self._on_transition(self._snapshot)
            except Exception:
                return
```

Do not call `_publish_transition()` from `record_delivery()`.

In `src/tiewtrade/market_data/runtime.py`, add the optional constructor keyword and pass it to `MarketDataRuntimeStatus`; delete the Runtime `visited_states` property:

```python
def __init__(
    self,
    *,
    config: MarketDataConfig,
    warm_up_count: int,
    source: MarketDataCandleSource,
    sink: MarketDataCandleSink,
    scheduler: RuntimeScheduler | None = None,
    on_transition: Callable[[MarketDataRuntimeSnapshot], None] | None = None,
) -> None:
    # existing validation and assignments
    self._status = MarketDataRuntimeStatus(
        self._scheduler.now,
        on_transition=on_transition,
    )
```

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the Step 2 command again.

Expected: all focused tests PASS and no Runtime/Status production object exposes `visited_states`.

- [ ] **Step 5: Run type/style checks and commit Task 1**

```bash
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/market_data/runtime_state.py \
  src/tiewtrade/market_data/runtime.py \
  tests/unit/market_data/test_runtime_state.py \
  tests/unit/market_data/test_runtime.py \
  tests/acceptance/test_public_market_data_runtime.py
git commit -m "refactor: externalize market data transition history"
```

---

### Task 2: Make the buffered backfill observation required

**Files:**
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `src/tiewtrade/market_data/candle_pipeline.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `tests/unit/market_data/test_candle_pipeline.py`

**Interfaces:**
- Consumes: the completed `Candle` returned by live-gap and reconnect paths
- Produces: required `observed: Candle` parameter on `_backfill_to_boundary()` and `CompletedCandlePipeline.process_backfill()`

- [ ] **Step 1: Add failing contract tests**

Import `Parameter`, `signature`, and `get_type_hints` in the focused test files. In `tests/unit/market_data/test_candle_pipeline.py`, add:

```python
def test_backfill_requires_a_buffered_observation() -> None:
    parameter = signature(CompletedCandlePipeline.process_backfill).parameters[
        "observed"
    ]
    hints = get_type_hints(CompletedCandlePipeline.process_backfill)

    assert parameter.default is Parameter.empty
    assert hints["observed"] is Candle
```

In `tests/unit/market_data/test_runtime.py`, add:

```python
def test_runtime_backfill_boundary_requires_an_observed_candle() -> None:
    parameter = signature(MarketDataRuntime._backfill_to_boundary).parameters[
        "observed"
    ]
    hints = get_type_hints(MarketDataRuntime._backfill_to_boundary)

    assert parameter.default is Parameter.empty
    assert hints["observed"] is Candle
```

- [ ] **Step 2: Run focused tests to verify RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_candle_pipeline.py \
  tests/unit/market_data/test_runtime.py
```

Expected: FAIL because the Runtime parameter defaults to `None` and both type hints contain `Candle | None`.

- [ ] **Step 3: Remove the unreachable optional path**

Change both interfaces to `observed: Candle`. In Runtime, remove the default:

```python
async def _backfill_to_boundary(
    self,
    end: datetime,
    *,
    received_at: datetime,
    observed: Candle,
) -> bool:
```

In Pipeline, always validate the observation:

```python
if validation_candles.accept(observed, received_at):
    raise ValueError("buffered observation was not covered by backfill")
```

Keep both existing call sites passing their concrete `observed` candle. Do not add a runtime `None` validation branch.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the Step 2 command again.

Expected: both focused files PASS, including existing empty/still-gapped/missing-observed fail-closed scenarios.

- [ ] **Step 5: Run type/style checks and commit Task 2**

```bash
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/market_data/runtime.py \
  src/tiewtrade/market_data/candle_pipeline.py \
  tests/unit/market_data/test_runtime.py \
  tests/unit/market_data/test_candle_pipeline.py
git commit -m "refactor: require observed backfill candle"
```

---

### Task 3: Classify transport, protocol, and payload source failures

**Files:**
- Modify: `src/tiewtrade/market_data/source_errors.py`
- Modify: `src/tiewtrade/integrations/binance/public_market_data.py`
- Modify: `tests/unit/market_data/test_source_errors.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `tests/unit/integrations/binance/test_public_market_data.py`
- Modify: `tests/acceptance/test_public_market_data_runtime.py`

**Interfaces:**
- Consumes: existing action-oriented `MarketDataRetryableError`, `MarketDataTimeoutError`, `MarketDataRateLimitError`, and `MarketDataFatalError`
- Produces: `MarketDataFailureKind` with `TRANSPORT`, `PROTOCOL`, `PAYLOAD`; read-only `MarketDataSourceError.kind`

- [ ] **Step 1: Add failing failure-kind tests**

In `tests/unit/market_data/test_source_errors.py`, import `MarketDataFailureKind` and
`MarketDataSourceError`, then add:

```python
@pytest.mark.parametrize(
    ("error", "expected_kind"),
    [
        (
            MarketDataRetryableError(
                "offline",
                kind=MarketDataFailureKind.TRANSPORT,
            ),
            MarketDataFailureKind.TRANSPORT,
        ),
        (
            MarketDataFatalError(
                "invalid payload",
                kind=MarketDataFailureKind.PAYLOAD,
            ),
            MarketDataFailureKind.PAYLOAD,
        ),
        (
            MarketDataTimeoutError("timed out"),
            MarketDataFailureKind.TRANSPORT,
        ),
        (
            MarketDataRateLimitError("rate limited", retry_after=None),
            MarketDataFailureKind.PROTOCOL,
        ),
    ],
)
def test_source_errors_expose_diagnostic_failure_kind(
    error: Exception,
    expected_kind: MarketDataFailureKind,
) -> None:
    assert isinstance(error, MarketDataSourceError)
    assert error.kind is expected_kind
```

Add a read-only assertion:

```python
def test_source_failure_kind_is_read_only() -> None:
    error = MarketDataFatalError(
        "invalid payload",
        kind=MarketDataFailureKind.PAYLOAD,
    )

    with pytest.raises(AttributeError):
        setattr(error, "kind", MarketDataFailureKind.TRANSPORT)  # noqa: B010
```

In Binance adapter tests, capture representative failures and assert both the existing action type and kind:

```python
with pytest.raises(MarketDataRetryableError) as captured:
    load_one(source)
assert captured.value.kind is MarketDataFailureKind.TRANSPORT
```

Cover this matrix by updating existing tests rather than duplicating them:

| Existing test scenario | Expected kind |
| --- | --- |
| REST/WebSocket client or timeout failure | `TRANSPORT` |
| HTTP `400`, `503`, `418`, `429` and unexpected WS message type | `PROTOCOL` |
| invalid REST JSON/kline or invalid WebSocket JSON/kline | `PAYLOAD` |

Add the missing unexpected-message protocol case:

```python
def test_unexpected_websocket_message_is_fatal_protocol_failure() -> None:
    source, _ = source_with(
        websocket_payloads=[
            FakeMessage("binary", message_type=WSMsgType.BINARY),
        ]
    )

    with pytest.raises(MarketDataFatalError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL
```

Update manually constructed `MarketDataRetryableError` and `MarketDataFatalError` instances in Runtime and acceptance tests to pass an explicit kind. Use `PROTOCOL` for fake HTTP/status failures and `PAYLOAD` for fake invalid candle payloads.

- [ ] **Step 2: Run focused tests to verify RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_source_errors.py \
  tests/unit/integrations/binance/test_public_market_data.py \
  tests/unit/market_data/test_runtime.py \
  tests/acceptance/test_public_market_data_runtime.py
```

Expected: collection/constructor failure because `MarketDataFailureKind` and the `kind` contract do not exist yet.

- [ ] **Step 3: Implement focused diagnostic metadata**

In `src/tiewtrade/market_data/source_errors.py`, add the enum and read-only base property. Keep exception subclasses as the action policy:

```python
from enum import StrEnum


class MarketDataFailureKind(StrEnum):
    TRANSPORT = "transport"
    PROTOCOL = "protocol"
    PAYLOAD = "payload"


class MarketDataSourceError(Exception):
    def __init__(self, message: str, *, kind: MarketDataFailureKind) -> None:
        super().__init__(message)
        self._kind = kind

    @property
    def kind(self) -> MarketDataFailureKind:
        return self._kind
```

`MarketDataRetryableError` and `MarketDataFatalError` inherit the required keyword. Give fixed kinds to timeout and rate-limit errors:

```python
class MarketDataTimeoutError(MarketDataRetryableError):
    def __init__(self, message: str) -> None:
        super().__init__(message, kind=MarketDataFailureKind.TRANSPORT)


class MarketDataRateLimitError(MarketDataSourceError):
    def __init__(self, message: str, *, retry_after: RetryAfter | None) -> None:
        # existing UTC validation
        super().__init__(message, kind=MarketDataFailureKind.PROTOCOL)
        self._retry_after = retry_after
```

In `BinancePublicMarketData`, assign kinds at the adapter seam:

```python
raise MarketDataRetryableError(
    "Binance market-data service is unavailable",
    kind=MarketDataFailureKind.PROTOCOL,
)
raise MarketDataFatalError(
    "Binance rejected the market-data request",
    kind=MarketDataFailureKind.PROTOCOL,
)
raise MarketDataRetryableError(
    "Binance market-data transport failed",
    kind=MarketDataFailureKind.TRANSPORT,
)
raise MarketDataFatalError(
    _INVALID_RESPONSE_MESSAGE,
    kind=MarketDataFailureKind.PAYLOAD,
)
```

For an unexpected WebSocket message type, raise fatal protocol failure directly rather than routing it through `ValueError`:

```python
raise MarketDataFatalError(
    _INVALID_RESPONSE_MESSAGE,
    kind=MarketDataFailureKind.PROTOCOL,
)
```

Do not branch on `.kind` anywhere in `MarketDataRuntime`.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the Step 2 command again.

Expected: all focused tests PASS and existing Runtime reasons/retry counts remain unchanged.

- [ ] **Step 5: Run the full verification gate**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Expected: `703+` Python tests PASS, both docs-site checks PASS, Ruff/format/mypy report no issues, and `git diff --check` emits no output.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/tiewtrade/market_data/source_errors.py \
  src/tiewtrade/integrations/binance/public_market_data.py \
  tests/unit/market_data/test_source_errors.py \
  tests/unit/market_data/test_runtime.py \
  tests/unit/integrations/binance/test_public_market_data.py \
  tests/acceptance/test_public_market_data_runtime.py
git commit -m "refactor: classify market data source failures"
```
