# DEV-99 Market Data Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** แยก candle validation/delivery และ runtime status ออกจาก `MarketDataRuntime` โดยรักษา public interface, state sequence และ fail-closed behavior เดิมทั้งหมด

**Architecture:** `MarketDataRuntime` ยังคง orchestrate source, deadlines, backfill, reconnect และ shutdown ส่วน `CompletedCandlePipeline` ตรวจและส่ง candle เข้า sink และ `MarketDataRuntimeStatus` เป็นเจ้าของ snapshot, watermark และ state history Pipeline บันทึก delivery หลัง sink สำเร็จเท่านั้น

**Tech Stack:** Python 3.12+, asyncio, dataclasses, Protocol, pytest, Ruff, mypy strict

## Global Constraints

- ห้ามเปลี่ยน public interface ของ `MarketDataRuntime`, `MarketDataCandleSource`, `MarketDataCandleSink` หรือ application composition
- ห้ามเปลี่ยน state sequence ที่ sink และ caller สังเกตได้
- Warm-up และ REST backfill deadline คงที่ 30 วินาที
- Reconnect delays คงที่ 1, 2 และ 4 วินาที
- ห้ามเพิ่ม generic base class, registry, factory หรือ hypothetical adapter
- ห้ามรวม DEV-100, DEV-101 หรือ DEV-102
- Tests ใช้ fake adapters เท่านั้น ห้ามใช้ API Key, network call, private endpoint หรือ Live Order
- ใช้ TDD: failing test → minimal implementation → refactor

## File Structure

- `src/tiewtrade/market_data/runtime.py` — external Runtime interface และ lifecycle orchestration
- `src/tiewtrade/market_data/runtime_state.py` — state types, immutable snapshot และ Status Tracker
- `src/tiewtrade/market_data/candle_pipeline.py` — sink interface, focused errors และ candle delivery invariant
- `tests/unit/market_data/test_runtime_state.py` — Status Tracker tests
- `tests/unit/market_data/test_candle_pipeline.py` — Pipeline tests
- `tests/unit/market_data/test_runtime.py` — lifecycle, recovery และ shutdown tests

---

### Task 1: Deepen Runtime State Ownership

**Files:**
- Create: `tests/unit/market_data/test_runtime_state.py`
- Modify: `src/tiewtrade/market_data/runtime_state.py`
- Modify: `src/tiewtrade/market_data/runtime.py`

**Interfaces:**
- Consumes: `MarketDataRuntimeState`, `MarketDataRuntimeReason`, `MarketDataRuntimeSnapshot`
- Produces: `MarketDataRuntimeStatus(now)`, `snapshot`, `visited_states`, `transition(...)`, `record_delivery(...)`

- [ ] **Step 1: Write the failing Status Tracker tests**

```python
from datetime import UTC, datetime

from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeState,
    MarketDataRuntimeStatus,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
TRANSITION = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
DELIVERY = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def test_status_owns_transitions_and_history() -> None:
    status = MarketDataRuntimeStatus(SequenceClock(START, TRANSITION))
    status.transition(
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeReason.START_REQUESTED,
    )
    assert status.snapshot.transitioned_at == TRANSITION
    assert status.visited_states == (
        MarketDataRuntimeState.STARTING,
        MarketDataRuntimeState.WARMING_UP,
    )


def test_delivery_preserves_transition_metadata() -> None:
    status = MarketDataRuntimeStatus(SequenceClock(START, TRANSITION))
    status.transition(
        MarketDataRuntimeState.LIVE,
        MarketDataRuntimeReason.WARM_UP_COMPLETED,
    )
    status.record_delivery(DELIVERY)
    assert status.snapshot.state is MarketDataRuntimeState.LIVE
    assert status.snapshot.reason is MarketDataRuntimeReason.WARM_UP_COMPLETED
    assert status.snapshot.transitioned_at == TRANSITION
    assert status.snapshot.last_accepted_open_time == DELIVERY
```

- [ ] **Step 2: Run the test and confirm RED**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime_state.py -q
```

Expected: collection fails because `MarketDataRuntimeStatus` does not exist

- [ ] **Step 3: Implement the Status Tracker**

Add to `runtime_state.py`:

```python
from collections.abc import Callable


class MarketDataRuntimeStatus:
    def __init__(self, now: Callable[[], datetime]) -> None:
        self._now = now
        self._snapshot = MarketDataRuntimeSnapshot(
            state=MarketDataRuntimeState.STARTING,
            reason=MarketDataRuntimeReason.START_REQUESTED,
            transitioned_at=self._now(),
            last_accepted_open_time=None,
        )
        self._visited_states = [MarketDataRuntimeState.STARTING]

    @property
    def snapshot(self) -> MarketDataRuntimeSnapshot:
        return self._snapshot

    @property
    def visited_states(self) -> tuple[MarketDataRuntimeState, ...]:
        return tuple(self._visited_states)

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
        self._visited_states.append(state)

    def record_delivery(self, open_time: datetime) -> None:
        self._snapshot = MarketDataRuntimeSnapshot(
            state=self._snapshot.state,
            reason=self._snapshot.reason,
            transitioned_at=self._snapshot.transitioned_at,
            last_accepted_open_time=open_time,
        )
```

- [ ] **Step 4: Run the focused test and confirm GREEN**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime_state.py -q
```

Expected: 2 passed

- [ ] **Step 5: Delegate Runtime status without changing public properties**

Import `MarketDataRuntimeStatus` from `runtime_state.py`:

```python
from tiewtrade.market_data.runtime_state import MarketDataRuntimeStatus
```

Construct the tracker after the scheduler:

```python
self._scheduler = scheduler or AsyncioRuntimeScheduler()
self._status = MarketDataRuntimeStatus(self._scheduler.now)
```

Delegate existing properties and transitions:

```python
@property
def snapshot(self) -> MarketDataRuntimeSnapshot:
    return self._status.snapshot

@property
def visited_states(self) -> tuple[MarketDataRuntimeState, ...]:
    return self._status.visited_states

def _transition(
    self,
    state: MarketDataRuntimeState,
    reason: MarketDataRuntimeReason,
) -> None:
    self._status.transition(state, reason)
```

Replace successful watermark assignments with
`self._status.record_delivery(candle.open_time)` and read the current watermark
from `self._status.snapshot.last_accepted_open_time`. Delete `_snapshot`,
`_visited_states`, `_last_accepted_open_time` and `_refresh_snapshot_watermark`.

- [ ] **Step 6: Run Runtime regressions and static checks**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime_state.py tests/unit/market_data/test_runtime.py -q
.venv/bin/python -m ruff check src/tiewtrade/market_data/runtime.py src/tiewtrade/market_data/runtime_state.py tests/unit/market_data/test_runtime_state.py tests/unit/market_data/test_runtime.py
.venv/bin/python -m ruff format --check src/tiewtrade/market_data/runtime.py src/tiewtrade/market_data/runtime_state.py tests/unit/market_data/test_runtime_state.py tests/unit/market_data/test_runtime.py
.venv/bin/python -m mypy
```

Expected: all commands exit 0

- [ ] **Step 7: Commit Task 1**

```bash
git add src/tiewtrade/market_data/runtime_state.py src/tiewtrade/market_data/runtime.py tests/unit/market_data/test_runtime_state.py
git commit -m "refactor: centralize market data runtime status"
```

---

### Task 2: Add the Completed Candle Pipeline

**Files:**
- Create: `tests/unit/market_data/test_candle_pipeline.py`
- Create: `src/tiewtrade/market_data/candle_pipeline.py`

**Interfaces:**
- Consumes: `MarketDataConfig`, `CompletedCandleStream`, `Candle`, sink and delivery callback
- Produces: `CompletedCandlePipeline`, `CandlePipelineInputError`, `CandlePipelineSinkError`, `MarketDataCandleSink`

- [ ] **Step 1: Write failing Pipeline invariant tests**

Create the test helpers and fake sink:

```python
import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.candle_pipeline import (
    CandlePipelineSinkError,
    CompletedCandlePipeline,
)
from tiewtrade.market_data.completed_candle_stream import CandleGapError
from tiewtrade.market_data.config import MarketDataConfig

RECEIVED_AT = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)


def candle_at(minute: int) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("10"),
    )


class RecordingSink:
    def __init__(
        self,
        *,
        fail_at: int | None = None,
        fail_warm_up: bool = False,
    ) -> None:
        self._fail_at = fail_at
        self._fail_warm_up = fail_warm_up
        self.live_attempts = 0
        self.events: list[str] = []

    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        received_at: datetime,
    ) -> None:
        if self._fail_warm_up:
            raise RuntimeError("warm-up failed")
        self.events.append("warm_up")

    async def process_completed(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> None:
        self.live_attempts += 1
        if self.live_attempts == self._fail_at:
            raise RuntimeError("sink failed")
        self.events.append(f"sink:{candle.open_time.minute}")


def pipeline_for(
    sink: RecordingSink,
    deliveries: list[datetime],
) -> CompletedCandlePipeline:
    return CompletedCandlePipeline(
        config=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        sink=sink,
        on_delivery=deliveries.append,
    )
```

Then write the invariant tests:

```python
def test_live_gap_does_not_reach_sink() -> None:
    sink = RecordingSink()
    deliveries: list[datetime] = []
    pipeline = pipeline_for(sink, deliveries)
    asyncio.run(
        pipeline.warm_up(
            (candle_at(0), candle_at(5)),
            expected_count=2,
            received_at=RECEIVED_AT,
        )
    )
    with pytest.raises(CandleGapError):
        asyncio.run(
            pipeline.process_live(candle_at(15), received_at=RECEIVED_AT)
        )
    assert sink.events == ["warm_up"]
    assert deliveries == [candle_at(5).open_time]


def test_partial_backfill_records_only_successful_deliveries() -> None:
    sink = RecordingSink(fail_at=2)
    deliveries: list[datetime] = []
    pipeline = pipeline_for(sink, deliveries)
    asyncio.run(
        pipeline.warm_up(
            (candle_at(0), candle_at(5), candle_at(10)),
            expected_count=3,
            received_at=RECEIVED_AT,
        )
    )
    with pytest.raises(CandlePipelineSinkError):
        asyncio.run(
            pipeline.process_backfill(
                (candle_at(15), candle_at(20)),
                start=candle_at(15).open_time,
                end=candle_at(25).open_time,
                observed=candle_at(20),
                received_at=RECEIVED_AT,
                on_ready_for_delivery=lambda: sink.events.append("ready"),
            )
        )
    assert sink.events == ["warm_up", "ready", "sink:15"]
    assert deliveries == [
        candle_at(10).open_time,
        candle_at(15).open_time,
    ]
```

Add duplicate and Warm-up failure cases:

```python
def test_duplicate_live_returns_false_without_sink_delivery() -> None:
    sink = RecordingSink()
    deliveries: list[datetime] = []
    pipeline = pipeline_for(sink, deliveries)
    asyncio.run(
        pipeline.warm_up(
            (candle_at(0), candle_at(5)),
            expected_count=2,
            received_at=RECEIVED_AT,
        )
    )
    accepted = asyncio.run(
        pipeline.process_live(candle_at(5), received_at=RECEIVED_AT)
    )
    assert accepted is False
    assert sink.events == ["warm_up"]


def test_warm_up_sink_failure_does_not_record_delivery() -> None:
    deliveries: list[datetime] = []
    pipeline = pipeline_for(
        RecordingSink(fail_warm_up=True),
        deliveries,
    )
    with pytest.raises(CandlePipelineSinkError):
        asyncio.run(
            pipeline.warm_up(
                (candle_at(0),),
                expected_count=1,
                received_at=RECEIVED_AT,
            )
        )
    assert deliveries == []
```

- [ ] **Step 2: Run the test and confirm RED**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_candle_pipeline.py -q
```

Expected: collection fails because `candle_pipeline.py` does not exist

- [ ] **Step 3: Implement Pipeline types and sink interface**

```python
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import (
    CandleGapError,
    CompletedCandleStream,
)
from tiewtrade.market_data.config import MarketDataConfig


class CandlePipelineInputError(ValueError):
    pass


class CandlePipelineSinkError(RuntimeError):
    pass


class MarketDataCandleSink(Protocol):
    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        received_at: datetime,
    ) -> None: ...

    async def process_completed(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> None: ...
```

Construct `CompletedCandlePipeline` with the concrete config, sink and delivery
callback:

```python
class CompletedCandlePipeline:
    def __init__(
        self,
        *,
        config: MarketDataConfig,
        sink: MarketDataCandleSink,
        on_delivery: Callable[[datetime], None],
    ) -> None:
        self._config = config
        self._sink = sink
        self._on_delivery = on_delivery
        self._candles = CompletedCandleStream(config)
```

- [ ] **Step 4: Implement Warm-up and live processing**

```python
async def warm_up(
    self,
    candles: tuple[Candle, ...],
    *,
    expected_count: int,
    received_at: datetime,
) -> None:
    try:
        if len(candles) < expected_count:
            raise ValueError("insufficient warm-up candles")
        for candle in candles:
            if not self._candles.accept(candle, received_at):
                raise ValueError("warm-up requires new completed candles")
    except ValueError as error:
        raise CandlePipelineInputError from error
    try:
        await self._sink.warm_up(candles, received_at=received_at)
    except Exception as error:
        raise CandlePipelineSinkError from error
    self._on_delivery(candles[-1].open_time)

async def process_live(
    self,
    candle: Candle,
    *,
    received_at: datetime,
) -> bool:
    try:
        accepted = self._candles.accept(candle, received_at)
    except CandleGapError:
        raise
    except ValueError as error:
        raise CandlePipelineInputError from error
    if not accepted:
        return False
    await self._deliver(candle, received_at=received_at)
    return True
```

- [ ] **Step 5: Implement backfill validation before delivery**

Implement validation and ordering in one operation:

```python
async def process_backfill(
    self,
    candles: tuple[Candle, ...],
    *,
    start: datetime,
    end: datetime,
    observed: Candle | None,
    received_at: datetime,
    on_ready_for_delivery: Callable[[], None],
) -> None:
    try:
        if start < end and not candles:
            raise ValueError("backfill must not be empty")
        if start >= end and candles:
            raise ValueError("backfill must be empty when no range is missing")
        accepted: list[Candle] = []
        for candle in candles:
            if not self._candles.accept(candle, received_at):
                raise ValueError("backfill requires new completed candles")
            accepted.append(candle)
        if accepted:
            reached = accepted[-1].open_time + self._config.interval
            if reached != end:
                raise ValueError("backfill did not reach requested boundary")
        if observed is not None and self._candles.accept(observed, received_at):
            raise ValueError("buffered observation was not covered by backfill")
    except ValueError as error:
        raise CandlePipelineInputError from error

    on_ready_for_delivery()
    for candle in accepted:
        await self._deliver(candle, received_at=received_at)
```

Use this delivery implementation so callback order cannot regress:

```python
async def _deliver(
    self,
    candle: Candle,
    *,
    received_at: datetime,
) -> None:
    try:
        await self._sink.process_completed(candle, received_at=received_at)
    except Exception as error:
        raise CandlePipelineSinkError from error
    self._on_delivery(candle.open_time)
```

Convert validation `ValueError` to `CandlePipelineInputError`; preserve
`CandleGapError` only from `process_live(...)`

- [ ] **Step 6: Run Pipeline tests and static checks**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_candle_pipeline.py -q
.venv/bin/python -m ruff check src/tiewtrade/market_data/candle_pipeline.py tests/unit/market_data/test_candle_pipeline.py
.venv/bin/python -m ruff format --check src/tiewtrade/market_data/candle_pipeline.py tests/unit/market_data/test_candle_pipeline.py
.venv/bin/python -m mypy
```

Expected: all commands exit 0

- [ ] **Step 7: Commit Task 2**

```bash
git add src/tiewtrade/market_data/candle_pipeline.py tests/unit/market_data/test_candle_pipeline.py
git commit -m "refactor: add completed candle delivery pipeline"
```

---

### Task 3: Compose Runtime Through the Pipeline

**Files:**
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Verify: `src/tiewtrade/application/public_market_data_runtime.py`
- Verify: `tests/acceptance/test_public_market_data_runtime.py`

**Interfaces:**
- Consumes: Pipeline types from Task 2 and Status Tracker from Task 1
- Produces: unchanged `MarketDataRuntime` import path, methods, properties and state sequence

- [ ] **Step 1: Add a regression for input-error reason mapping**

Add to `test_runtime.py` using its existing helpers:

```python
def test_invalid_live_candle_maps_to_source_error() -> None:
    source = FakeSource(
        recent=warm_up_candles(),
        live=[candle_at(15, symbol="ETHUSDT")],
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)
    asyncio.run(runtime.run())
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_ERROR
    assert sink.live_candles == []
```

Retain existing assertions that backfill sink calls observe `LIVE` and partial
sink failure reports only the last successful watermark

- [ ] **Step 2: Run Runtime tests before replacement**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime.py -q
```

Expected: pass and protect observable behavior before internal replacement

- [ ] **Step 3: Re-export the moved sink interface**

Remove the Protocol declaration from `runtime.py` and import the same name into
its module namespace:

```python
from tiewtrade.market_data.candle_pipeline import (
    CandlePipelineInputError,
    CandlePipelineSinkError,
    CompletedCandlePipeline,
    MarketDataCandleSink,
)
```

Do not change application imports from `tiewtrade.market_data.runtime`

- [ ] **Step 4: Construct the Pipeline with the delivery callback**

```python
self._pipeline = CompletedCandlePipeline(
    config=config,
    sink=sink,
    on_delivery=self._status.record_delivery,
)
```

Delete Runtime's direct `CompletedCandleStream` and sink fields

- [ ] **Step 5: Delegate Warm-up processing**

Keep source I/O in Runtime and replace its validation/delivery block:

```python
try:
    candles = await self._source.load_recent(
        self._config,
        count=self._warm_up_count,
        completed_before=completed_before,
    )
except Exception as error:
    raise _WarmUpSourceError from error

try:
    await self._pipeline.warm_up(
        candles,
        expected_count=self._warm_up_count,
        received_at=completed_before,
    )
except CandlePipelineInputError as error:
    raise _WarmUpSourceError from error
except CandlePipelineSinkError as error:
    raise _WarmUpSinkError from error
```

- [ ] **Step 6: Delegate live acceptance with exact reason mapping**

```python
received_at = self._scheduler.now()
try:
    accepted = await self._pipeline.process_live(
        candle,
        received_at=received_at,
    )
except CandleGapError:
    return await self._backfill_through(candle, received_at=received_at)
except CandlePipelineInputError:
    self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
    return False
except CandlePipelineSinkError:
    self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
    return False
if not accepted:
    return True
self._transition(
    MarketDataRuntimeState.LIVE,
    MarketDataRuntimeReason.LIVE_CANDLE_ACCEPTED,
)
return True
```

- [ ] **Step 7: Delegate backfill while preserving transition timing**

Read `start` from the Status Tracker watermark and load only when `start < end`:

```python
last_open_time = self._status.snapshot.last_accepted_open_time
if last_open_time is None:
    self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
    return False
start = last_open_time + self._config.interval
candles: tuple[Candle, ...] = ()
if start < end:
    try:
        candles = await self._scheduler.wait_for(
            self._source.load_range(
                self._config,
                start=start,
                end=end,
            ),
            _BACKFILL_TIMEOUT_SECONDS,
        )
    except Exception:
        self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
        return False
```

Publish `LIVE` only after validation and before delivery:

```python
def publish_backfill_ready() -> None:
    self._transition(
        MarketDataRuntimeState.LIVE,
        MarketDataRuntimeReason.BACKFILL_COMPLETED,
    )

try:
    await self._pipeline.process_backfill(
        candles,
        start=start,
        end=end,
        observed=observed,
        received_at=received_at,
        on_ready_for_delivery=publish_backfill_ready,
    )
except CandlePipelineInputError:
    self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
    return False
except CandlePipelineSinkError:
    self._fail_closed(MarketDataRuntimeReason.SINK_ERROR)
    return False
return True
```

Delete `_deliver` and `_validate_buffered_observation` from Runtime

- [ ] **Step 8: Run focused regressions**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_candle_pipeline.py tests/unit/market_data/test_runtime_state.py tests/unit/market_data/test_runtime.py tests/unit/application/test_public_market_data_runtime_composition.py tests/acceptance/test_public_market_data_runtime.py -q
```

Expected: all tests pass with unchanged state sequence assertions

- [ ] **Step 9: Verify import compatibility and static checks**

```bash
.venv/bin/python -c "from tiewtrade.market_data.runtime import MarketDataCandleSink, MarketDataRuntime; from tiewtrade.application.public_market_data_runtime import create_public_market_data_runtime; print('imports-ok')"
.venv/bin/python -m ruff check src/tiewtrade/market_data tests/unit/market_data tests/unit/application/test_public_market_data_runtime_composition.py tests/acceptance/test_public_market_data_runtime.py
.venv/bin/python -m ruff format --check src/tiewtrade/market_data tests/unit/market_data tests/unit/application/test_public_market_data_runtime_composition.py tests/acceptance/test_public_market_data_runtime.py
.venv/bin/python -m mypy
```

Expected: prints `imports-ok`; all checks exit 0

- [ ] **Step 10: Commit Task 3**

```bash
git add src/tiewtrade/market_data/runtime.py tests/unit/market_data/test_runtime.py
git commit -m "refactor: compose runtime through candle pipeline"
```

---

### Task 4: Document Ownership and Run Full Verification

**Files:**
- Modify: `docs/superpowers/specs/2026-07-26-public-binance-market-data-runtime-design.md`
- Modify: `docs/superpowers/specs/2026-07-26-dev-99-runtime-refactor-design.md`
- Verify: all `src/` and `tests/`

**Interfaces:**
- Consumes: verified Runtime, Pipeline and Status Tracker
- Produces: documentation and repository-wide verification evidence

- [ ] **Step 1: Update DEV-99 module ownership**

Add this implemented internal flow to the DEV-99 design:

```text
MarketDataRuntime -> CompletedCandlePipeline -> MarketDataCandleSink
                           |
                           +-> MarketDataRuntimeStatus.record_delivery(...)
```

Document these exact responsibilities:

- Runtime owns lifecycle, deadlines, source I/O, recovery and shutdown
- Pipeline owns candle validation, deduplication, continuity and sink delivery
- Status owns snapshots, delivery watermark and state history

- [ ] **Step 2: Run the complete test suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: zero failures

- [ ] **Step 3: Run repository quality gates**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy
git diff --check
```

Expected: every command exits 0

- [ ] **Step 4: Confirm scope and untouched user files**

```bash
git status --short
git diff --stat
```

Expected: changes are limited to the listed Runtime refactor files;
`.mcp.json` and `.superpowers/` remain untracked and untouched

- [ ] **Step 5: Mark the refactor design verified**

Only after Steps 2–4 pass, change its header to:

```markdown
**Status:** Implemented and verified
```

- [ ] **Step 6: Commit Task 4**

```bash
git add docs/superpowers/specs/2026-07-26-public-binance-market-data-runtime-design.md docs/superpowers/specs/2026-07-26-dev-99-runtime-refactor-design.md
git commit -m "docs: record DEV-99 runtime refactor"
```

- [ ] **Step 7: Update Linear without push or merge**

Add a Thai DEV-99 comment with:

```markdown
## DEV-99 Refactor Verification

- แยก CompletedCandlePipeline และ MarketDataRuntimeStatus แล้ว
- Public Runtime interface และ observable state sequence ไม่เปลี่ยน
- Watermark เลื่อนหลัง successful sink delivery เท่านั้น
- ระบุ commit SHAs ของ Task 1–4
- ระบุจำนวน tests และผล Ruff, format, mypy, git diff --check
- ไม่รวม DEV-100, DEV-101 หรือ DEV-102
```

Keep DEV-99 in `Done`. Do not push or merge without separate user confirmation.
