# DEV-100 Structured Market Data Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่ม structured operational logs สำหรับ Public Market Data Runtime โดยไม่เปลี่ยน Runtime decision, state sequence หรือ safety policy

**Architecture:** `CompletedCandleStream` คืน `CandleAcceptance` เพื่อให้ Runtime รู้เหตุผลของ live discard อย่างชัดเจน ส่วน concrete `MarketDataRuntimeLog` เป็น boundary เดียวที่กำหนด event name, level, field whitelist และ serialization ก่อนส่งเข้า Python `logging.Logger` Runtime เรียก typed methods เท่านั้นและ isolate logging `Exception`

**Tech Stack:** Python 3.12+, standard-library `logging`, asyncio, pytest, Ruff, mypy

## Global Constraints

- คง Runtime state sequence, reason และ immutable snapshot เดิม
- คง reconnect delays `1`, `2`, `4` วินาที, source deadlines `30` วินาที และ rate-limit fallback `60` วินาที
- ใช้ `MarketDataFailureKind` เป็น diagnostic metadata เท่านั้น Runtime ยังตัดสินใจจาก action exception type เดิม
- ห้ามบันทึก API Key, Secret, credentials, private account payload, response body, exception message, Candle OHLC หรือ volume
- Logging failure ต้องไม่เปลี่ยน Runtime decision หรือทำให้ Runtime หยุด
- แยกเฉพาะ `Exception` จาก logging backend; ไม่จับ `BaseException` เช่น `KeyboardInterrupt` หรือ `SystemExit`
- ใช้ fake source, fake scheduler และ fake logger ใน tests เท่านั้น ไม่มี Binance network, Private API หรือ Live Order
- ไม่สร้าง generic logging interface, registry, factory, persistence adapter, file handler, rotation หรือ UI log viewer
- ทุก production behavior ต้องเริ่มด้วย failing test และเห็น RED ก่อนเขียน implementation

---

### Task 1: ทำ Candle acceptance result ให้จำแนก discard reason ได้

**Files:**
- Modify: `src/tiewtrade/market_data/completed_candle_stream.py`
- Modify: `src/tiewtrade/market_data/candle_pipeline.py`
- Modify: `tests/unit/market_data/test_completed_candle_stream.py`
- Modify: `tests/unit/market_data/test_candle_pipeline.py`

**Interfaces:**
- Consumes: `Candle`, `MarketDataConfig`, UTC `received_at`
- Produces: `CandleAcceptance(StrEnum)` และ
  `CompletedCandlePipeline.process_live(candle, received_at=received_at) -> CandleAcceptance`

- [ ] **Step 1: เขียน failing tests สำหรับ acceptance enum**

ใน `tests/unit/market_data/test_completed_candle_stream.py` import
`CandleAcceptance` แล้วเปลี่ยน assertions ให้ระบุผลลัพธ์ชัดเจน:

```python
def test_accepts_only_closed_candles_and_deduplicates() -> None:
    config = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    stream = CompletedCandleStream(config)
    first = candle_at(0)

    assert stream.accept(
        first,
        datetime(2026, 1, 1, 0, 4, 59, tzinfo=UTC),
    ) is CandleAcceptance.NOT_CLOSED
    assert stream.accept(
        first,
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    ) is CandleAcceptance.ACCEPTED
    assert stream.accept(
        first,
        datetime(2026, 1, 1, 0, 6, tzinfo=UTC),
    ) is CandleAcceptance.DUPLICATE_OR_OUT_OF_ORDER
```

แก้ gap และ non-5m tests ให้เปรียบเทียบ `CandleAcceptance.ACCEPTED` และคง
`CandleGapError`/validation assertions เดิม

ใน `tests/unit/market_data/test_candle_pipeline.py` เปลี่ยน duplicate test เป็น:

```python
def test_duplicate_live_returns_discard_reason_without_sink_delivery() -> None:
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

    decision = asyncio.run(
        pipeline.process_live(candle_at(5), received_at=RECEIVED_AT)
    )

    assert decision is CandleAcceptance.DUPLICATE_OR_OUT_OF_ORDER
    assert sink.events == ["warm_up"]
```

- [ ] **Step 2: รัน focused tests เพื่อยืนยัน RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_completed_candle_stream.py \
  tests/unit/market_data/test_candle_pipeline.py
```

Expected: FAIL ขณะ import `CandleAcceptance` เพราะ type ยังไม่มี

- [ ] **Step 3: เพิ่ม enum และเปลี่ยน stream contract**

ใน `src/tiewtrade/market_data/completed_candle_stream.py`:

```python
from enum import StrEnum


class CandleAcceptance(StrEnum):
    ACCEPTED = "accepted"
    NOT_CLOSED = "not_closed"
    DUPLICATE_OR_OUT_OF_ORDER = "duplicate_or_out_of_order"


class CompletedCandleStream:
    # existing constructor

    def accept(self, candle: Candle, received_at: datetime) -> CandleAcceptance:
        # existing UTC, symbol and timeframe validation remains unchanged
        if received_at < candle.close_time:
            return CandleAcceptance.NOT_CLOSED
        if self._last_open_time is not None:
            if candle.open_time <= self._last_open_time:
                return CandleAcceptance.DUPLICATE_OR_OUT_OF_ORDER
            expected = self._last_open_time + self._config.interval
            if candle.open_time != expected:
                raise CandleGapError(
                    f"missing candle beginning {expected.isoformat()}"
                )
        self._last_open_time = candle.open_time
        return CandleAcceptance.ACCEPTED
```

ใน `src/tiewtrade/market_data/candle_pipeline.py` import enum และเปรียบเทียบแบบ
explicit ทุก path:

```python
decision = self._candles.accept(candle, received_at)
if decision is not CandleAcceptance.ACCEPTED:
    return decision
await self._deliver(candle, received_at=received_at)
return decision
```

ใน warm-up/backfill validation ให้ใช้รูปแบบ:

```python
if self._candles.accept(candle, received_at) is not CandleAcceptance.ACCEPTED:
    raise ValueError("warm-up requires new completed candles")
```

และ preserved backfill invariant:

```python
if (
    validation_candles.accept(observed, received_at)
    is CandleAcceptance.ACCEPTED
):
    raise ValueError("buffered observation was not covered by backfill")
```

- [ ] **Step 4: รัน focused tests เพื่อยืนยัน GREEN**

Run command จาก Step 2 อีกครั้ง

Expected: focused tests PASS และ gap/validation semantics เดิมยังผ่าน

- [ ] **Step 5: รัน quality checks และ commit Task 1**

```bash
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/market_data/completed_candle_stream.py \
  src/tiewtrade/market_data/candle_pipeline.py \
  tests/unit/market_data/test_completed_candle_stream.py \
  tests/unit/market_data/test_candle_pipeline.py
git commit -m "refactor: classify completed candle acceptance"
```

---

### Task 2: เพิ่ม concrete structured logging boundary

**Files:**
- Create: `src/tiewtrade/market_data/runtime_logging.py`
- Create: `tests/unit/market_data/test_runtime_logging.py`

**Interfaces:**
- Consumes: concrete `logging.Logger`, bound `symbol`/`timeframe`, `CandleAcceptance`, `MarketDataRuntimeReason`, `MarketDataFailureKind`
- Produces: `MarketDataEventName(StrEnum)` และ typed methods บน `MarketDataRuntimeLog`

- [ ] **Step 1: เขียน failing tests สำหรับ exact event contract**

สร้าง `tests/unit/market_data/test_runtime_logging.py` พร้อม logger ที่ไม่ propagate:

```python
import logging
from datetime import UTC, datetime

import pytest

from tiewtrade.market_data.completed_candle_stream import CandleAcceptance
from tiewtrade.market_data.runtime_logging import (
    MarketDataEventName,
    MarketDataRuntimeLog,
)


def configured_log(name: str) -> tuple[MarketDataRuntimeLog, logging.Logger]:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.DEBUG)
    return (
        MarketDataRuntimeLog(
            logger,
            symbol="BTCUSDT",
            timeframe="5m",
        ),
        logger,
    )


def custom_fields(record: logging.LogRecord) -> dict[str, object]:
    standard = logging.makeLogRecord({}).__dict__
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in standard
    }
```

เพิ่ม tests อย่างน้อยต่อไปนี้:

```python
def test_candle_discard_record_has_exact_whitelisted_fields(caplog) -> None:
    runtime_log, logger = configured_log("tests.market_data.discard")
    caplog.set_level(logging.INFO, logger=logger.name)
    opened = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    received = datetime(2026, 1, 1, 0, 19, tzinfo=UTC)

    runtime_log.candle_discarded(
        open_time=opened,
        received_at=received,
        discard_reason=CandleAcceptance.NOT_CLOSED,
    )

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert record.getMessage() == MarketDataEventName.CANDLE_DISCARDED.value
    assert custom_fields(record) == {
        "event_name": "market_data.candle.discarded",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "open_time": "2026-01-01T00:15:00+00:00",
        "received_at": "2026-01-01T00:19:00+00:00",
        "discard_reason": "not_closed",
    }
```

เพิ่ม parameterized tests ที่เรียก typed methods ทั้งเจ็ดและยืนยันชื่อ/level:

```python
def test_event_names_and_levels_are_stable(caplog) -> None:
    runtime_log, logger = configured_log("tests.market_data.events")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    opened = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    closed = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)
    received = datetime(2026, 1, 1, 0, 19, tzinfo=UTC)
    calls = {
        MarketDataEventName.CANDLE_DISCARDED: lambda: runtime_log.candle_discarded(
            open_time=opened,
            received_at=received,
            discard_reason=CandleAcceptance.NOT_CLOSED,
        ),
        MarketDataEventName.CLOCK_SKEW_DETECTED: lambda: (
            runtime_log.clock_skew_detected(
                open_time=opened,
                close_time=closed,
                received_at=received,
            )
        ),
        MarketDataEventName.STALE_DETECTED: lambda: runtime_log.stale_detected(
            reason=MarketDataRuntimeReason.DATA_STALE,
            last_accepted_open_time=opened,
        ),
        MarketDataEventName.RECONNECT_ATTEMPTED: lambda: (
            runtime_log.reconnect_attempted(
                attempt=1,
                delay_seconds=1.0,
                reason=MarketDataRuntimeReason.DATA_STALE,
            )
        ),
        MarketDataEventName.BACKFILL_COMPLETED: lambda: (
            runtime_log.backfill_completed(
                start=opened,
                end=closed,
                candle_count=1,
            )
        ),
        MarketDataEventName.BACKFILL_FAILED: lambda: runtime_log.backfill_failed(
            start=opened,
            end=closed,
            reason=MarketDataRuntimeReason.SOURCE_FATAL,
            failure_kind=MarketDataFailureKind.PROTOCOL,
        ),
        MarketDataEventName.RUNTIME_FAILED_CLOSED: lambda: (
            runtime_log.failed_closed(
                reason=MarketDataRuntimeReason.SOURCE_FATAL,
                failure_kind=MarketDataFailureKind.PROTOCOL,
            )
        ),
    }
    expected_levels = {
        MarketDataEventName.CANDLE_DISCARDED: logging.INFO,
        MarketDataEventName.CLOCK_SKEW_DETECTED: logging.WARNING,
        MarketDataEventName.STALE_DETECTED: logging.WARNING,
        MarketDataEventName.RECONNECT_ATTEMPTED: logging.WARNING,
        MarketDataEventName.BACKFILL_COMPLETED: logging.INFO,
        MarketDataEventName.BACKFILL_FAILED: logging.ERROR,
        MarketDataEventName.RUNTIME_FAILED_CLOSED: logging.ERROR,
    }

    for event_name, call in calls.items():
        call()
        record = caplog.records[-1]
        assert record.getMessage() == event_name.value
        assert record.event_name == event_name.value
        assert record.levelno == expected_levels[event_name]
```

เพิ่ม tests สำหรับ `clock_skew_detected()` ว่า `skew_seconds == 60.0`,
`failed_closed()` ว่า `failure_kind == "protocol"`, และ absence ของ keys:
`api_key`, `secret`, `credentials`, `payload`, `exception`, `open`, `high`, `low`,
`close`, `volume`

เพิ่ม failure isolation tests ด้วย `logging.Handler` ที่โยน exception:

```python
class RaisingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("logging failed")


class InterruptingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise KeyboardInterrupt(record.msg)


def test_logging_exception_does_not_escape() -> None:
    logger = logging.getLogger("tests.market_data.raise")
    logger.handlers[:] = [RaisingHandler()]
    logger.propagate = False
    runtime_log = MarketDataRuntimeLog(
        logger,
        symbol="BTCUSDT",
        timeframe="5m",
    )

    runtime_log.failed_closed(
        reason=MarketDataRuntimeReason.SOURCE_ERROR,
        failure_kind=None,
    )


def test_logging_base_exception_still_escapes() -> None:
    logger = logging.getLogger("tests.market_data.interrupt")
    logger.handlers[:] = [InterruptingHandler()]
    logger.propagate = False
    runtime_log = MarketDataRuntimeLog(
        logger,
        symbol="BTCUSDT",
        timeframe="5m",
    )

    with pytest.raises(KeyboardInterrupt):
        runtime_log.failed_closed(
            reason=MarketDataRuntimeReason.SOURCE_ERROR,
            failure_kind=None,
        )
```

- [ ] **Step 2: รัน focused tests เพื่อยืนยัน RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_runtime_logging.py
```

Expected: FAIL ขณะ import `runtime_logging` เพราะ module ยังไม่มี

- [ ] **Step 3: Implement concrete logger และ event whitelist**

สร้าง `src/tiewtrade/market_data/runtime_logging.py` ด้วย public API ต่อไปนี้:

```python
import logging
from datetime import datetime
from enum import StrEnum

from tiewtrade.market_data.completed_candle_stream import CandleAcceptance
from tiewtrade.market_data.runtime_state import MarketDataRuntimeReason
from tiewtrade.market_data.source_errors import MarketDataFailureKind


class MarketDataEventName(StrEnum):
    CANDLE_DISCARDED = "market_data.candle.discarded"
    CLOCK_SKEW_DETECTED = "market_data.clock_skew.detected"
    STALE_DETECTED = "market_data.stale.detected"
    RECONNECT_ATTEMPTED = "market_data.reconnect.attempted"
    BACKFILL_COMPLETED = "market_data.backfill.completed"
    BACKFILL_FAILED = "market_data.backfill.failed"
    RUNTIME_FAILED_CLOSED = "market_data.runtime.failed_closed"


class MarketDataRuntimeLog:
    def __init__(
        self,
        logger: logging.Logger,
        *,
        symbol: str,
        timeframe: str,
    ) -> None:
        self._logger = logger
        self._common = {"symbol": symbol, "timeframe": timeframe}

    def candle_discarded(
        self,
        *,
        open_time: datetime,
        received_at: datetime,
        discard_reason: CandleAcceptance,
    ) -> None:
        self._emit(
            logging.INFO,
            MarketDataEventName.CANDLE_DISCARDED,
            {
                "open_time": open_time.isoformat(),
                "received_at": received_at.isoformat(),
                "discard_reason": discard_reason.value,
            },
        )

    def clock_skew_detected(
        self,
        *,
        open_time: datetime,
        close_time: datetime,
        received_at: datetime,
    ) -> None:
        self._emit(
            logging.WARNING,
            MarketDataEventName.CLOCK_SKEW_DETECTED,
            {
                "open_time": open_time.isoformat(),
                "close_time": close_time.isoformat(),
                "received_at": received_at.isoformat(),
                "skew_seconds": max(
                    0.0,
                    (close_time - received_at).total_seconds(),
                ),
            },
        )

    def stale_detected(
        self,
        *,
        reason: MarketDataRuntimeReason,
        last_accepted_open_time: datetime | None,
    ) -> None:
        self._emit(
            logging.WARNING,
            MarketDataEventName.STALE_DETECTED,
            {
                "reason": reason.value,
                "last_accepted_open_time": (
                    last_accepted_open_time.isoformat()
                    if last_accepted_open_time is not None
                    else None
                ),
            },
        )

    def reconnect_attempted(
        self,
        *,
        attempt: int,
        delay_seconds: float,
        reason: MarketDataRuntimeReason,
    ) -> None:
        self._emit(
            logging.WARNING,
            MarketDataEventName.RECONNECT_ATTEMPTED,
            {
                "attempt": attempt,
                "delay_seconds": max(0.0, delay_seconds),
                "reason": reason.value,
            },
        )

    def backfill_completed(
        self,
        *,
        start: datetime,
        end: datetime,
        candle_count: int,
    ) -> None:
        self._emit(
            logging.INFO,
            MarketDataEventName.BACKFILL_COMPLETED,
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "candle_count": candle_count,
            },
        )

    def backfill_failed(
        self,
        *,
        start: datetime,
        end: datetime,
        reason: MarketDataRuntimeReason,
        failure_kind: MarketDataFailureKind | None,
    ) -> None:
        self._emit(
            logging.ERROR,
            MarketDataEventName.BACKFILL_FAILED,
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reason": reason.value,
                "failure_kind": (
                    failure_kind.value if failure_kind is not None else None
                ),
            },
        )

    def failed_closed(
        self,
        *,
        reason: MarketDataRuntimeReason,
        failure_kind: MarketDataFailureKind | None,
    ) -> None:
        self._emit(
            logging.ERROR,
            MarketDataEventName.RUNTIME_FAILED_CLOSED,
            {
                "reason": reason.value,
                "failure_kind": (
                    failure_kind.value if failure_kind is not None else None
                ),
            },
        )

    def _emit(
        self,
        level: int,
        event_name: MarketDataEventName,
        fields: dict[str, object],
    ) -> None:
        extra = {
            "event_name": event_name.value,
            **self._common,
            **fields,
        }
        try:
            self._logger.log(level, event_name.value, extra=extra)
        except Exception:
            return
```

- [ ] **Step 4: รัน focused tests เพื่อยืนยัน GREEN**

Run command จาก Step 2 อีกครั้ง

Expected: logger contract tests PASS รวม exact fields และ failure isolation

- [ ] **Step 5: รัน quality checks และ commit Task 2**

```bash
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/market_data/runtime_logging.py \
  tests/unit/market_data/test_runtime_logging.py
git commit -m "feat: add structured market data runtime logger"
```

---

### Task 3: Wire live discard, Clock Skew, Stale และ Stream Reconnect events

**Files:**
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `tests/unit/market_data/test_runtime.py`

**Interfaces:**
- Consumes: `CandleAcceptance`, `MarketDataRuntimeLog`, concrete optional `logging.Logger`
- Produces: Runtime events สำหรับ live discard, Clock Skew, Stale Data และ Stream Reconnect โดยไม่มี terminal/backfill event ใน task นี้

- [ ] **Step 1: เพิ่ม logger-aware test composition และ failing event tests**

ใน `tests/unit/market_data/test_runtime.py` import `logging`, `CandleAcceptance` และ
`MarketDataEventName`; เพิ่ม optional logger ให้ `ObservedMarketDataRuntime` กับ
`runtime_for()` แล้วส่งเข้า `MarketDataRuntime`

ใช้ `caplog.set_level(logging.INFO, logger=logger.name)` กับ named logger ต่อ test และ
เพิ่ม tests ต่อไปนี้:

```python
def market_data_records(caplog) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if hasattr(record, "event_name")
    ]


def test_not_closed_live_candle_logs_discard_then_clock_skew(caplog) -> None:
    # scheduler.now = 00:19 UTC; warm-up ends at 00:10; live candle opens 00:15
    # run until two records exist, then stop Runtime
    assert [record.event_name for record in market_data_records(caplog)] == [
        MarketDataEventName.CANDLE_DISCARDED.value,
        MarketDataEventName.CLOCK_SKEW_DETECTED.value,
    ]
    assert market_data_records(caplog)[1].skew_seconds == 60.0
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED


def test_duplicate_live_candle_logs_only_discard(caplog) -> None:
    # deliver 00:15 once, then receive 00:15 again and stop after discard record
    discard_records = [
        record
        for record in market_data_records(caplog)
        if record.event_name == MarketDataEventName.CANDLE_DISCARDED.value
    ]
    assert len(discard_records) == 1
    assert discard_records[0].discard_reason == "duplicate_or_out_of_order"
```

เพิ่ม assertions ให้ `test_stale_reconnect_uses_new_boundary_deadline_and_recovers`
ตรวจ `STALE_DETECTED` หนึ่ง record และ `RECONNECT_ATTEMPTED` attempt `1`, delay `1.0`

เพิ่ม assertions ให้ `test_reconnect_uses_one_two_four_seconds_then_fails_closed`
ตรวจ reconnect attempts `[1, 2, 3]` และ delays `[1.0, 2.0, 4.0]`

- [ ] **Step 2: รัน focused tests เพื่อยืนยัน RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_runtime.py
```

Expected: FAIL เพราะ Runtime ยังไม่รับ `logger` และยังไม่ emit events

- [ ] **Step 3: Compose concrete logger ใน Runtime**

ใน `src/tiewtrade/market_data/runtime.py` เพิ่ม:

```python
import logging

from tiewtrade.market_data.completed_candle_stream import (
    CandleAcceptance,
    CandleGapError,
)
from tiewtrade.market_data.runtime_logging import MarketDataRuntimeLog

_LOGGER = logging.getLogger("tiewtrade.market_data.runtime")
```

เพิ่ม keyword โดยไม่เปลี่ยน keyword เดิม:

```python
logger: logging.Logger | None = None,
```

และ compose:

```python
self._runtime_log = MarketDataRuntimeLog(
    logger or _LOGGER,
    symbol=config.symbol,
    timeframe=config.timeframe,
)
```

- [ ] **Step 4: Emit discard และ Clock Skew จาก `_accept_live_candle()`**

แทน boolean branch ด้วย enum branch:

```python
decision = await self._pipeline.process_live(candle, received_at=received_at)
if decision is not CandleAcceptance.ACCEPTED:
    self._runtime_log.candle_discarded(
        open_time=candle.open_time,
        received_at=received_at,
        discard_reason=decision,
    )
    if decision is CandleAcceptance.NOT_CLOSED:
        self._runtime_log.clock_skew_detected(
            open_time=candle.open_time,
            close_time=candle.close_time,
            received_at=received_at,
        )
    return True
```

คง exception mapping และ `LIVE_CANDLE_ACCEPTED` transition เดิม

- [ ] **Step 5: Emit Stale และ Reconnect โดยไม่เปลี่ยน state order**

ใน `_recover_stream()` เมื่อ `pending_rate_limit is None` และ reason เป็น
`DATA_STALE` ให้ emit `stale_detected()` ก่อน transition `STALE`

เปลี่ยน loop เป็น `enumerate(_RECONNECT_DELAYS_SECONDS, start=1)` และเก็บ delay จริงใน
`attempt_delay`; หลัง existing stop check และก่อนเปิด stream ให้ emit:

```python
self._runtime_log.reconnect_attempted(
    attempt=attempt,
    delay_seconds=attempt_delay,
    reason=reason,
)
```

ห้ามย้าย existing transition หรือ stop check เพราะ tests ต้องคง state sequence เดิม

- [ ] **Step 6: รัน focused tests เพื่อยืนยัน GREEN**

Run command จาก Step 2 อีกครั้ง

Expected: Runtime tests PASS และ delay/state assertions เดิมไม่เปลี่ยน

- [ ] **Step 7: รัน quality checks และ commit Task 3**

```bash
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/market_data/runtime.py \
  tests/unit/market_data/test_runtime.py
git commit -m "feat: log market data discard and recovery events"
```

---

### Task 4: Wire Backfill result, terminal failure และ acceptance coverage

**Files:**
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `tests/acceptance/test_public_market_data_runtime.py`

**Interfaces:**
- Consumes: `MarketDataRuntimeLog.backfill_completed()`, `backfill_failed()`, `failed_closed()` และ `MarketDataFailureKind`
- Produces: Backfill success/failure กับ terminal event ที่รักษา action exception policy เดิม

- [ ] **Step 1: เขียน failing tests สำหรับ Backfill และ terminal events**

ใน `tests/unit/market_data/test_runtime.py` เพิ่ม logger ให้ existing scenarios แล้ว
assert อย่างน้อย:

```python
def test_gap_backfill_logs_completed_range_and_count(caplog) -> None:
    # ใช้ source/sink setup เดียวกับ test_gap_backfills_in_order_before_resuming_live
    record = next(
        record
        for record in market_data_records(caplog)
        if record.event_name == MarketDataEventName.BACKFILL_COMPLETED.value
    )
    assert record.start == "2026-01-01T00:15:00+00:00"
    assert record.end == "2026-01-01T00:25:00+00:00"
    assert record.candle_count == 2


def test_fatal_backfill_logs_failure_kind_before_terminal_event(caplog) -> None:
    # ใช้ fatal protocol source failure
    events = [record.event_name for record in market_data_records(caplog)]
    assert events[-2:] == [
        MarketDataEventName.BACKFILL_FAILED.value,
        MarketDataEventName.RUNTIME_FAILED_CLOSED.value,
    ]
    assert market_data_records(caplog)[-2].failure_kind == "protocol"
    assert market_data_records(caplog)[-1].reason == "source_fatal"
```

เพิ่ม terminal tests ครอบคลุม `SOURCE_FATAL`, `RATE_LIMIT_EXHAUSTED`,
`SOURCE_ERROR` และ `SINK_ERROR`; source exceptions ต้องส่ง kind เดิม ส่วน built-in,
pipeline หรือ sink errors ใช้ `None`

เพิ่ม test ที่ใช้ failing logging handler แล้วพิสูจน์ว่า Runtime ยังไป
`FAILED_CLOSED` ด้วย reason เดิม

ใน `tests/acceptance/test_public_market_data_runtime.py` ใช้ named logger + `caplog`
กับ fatal source flow แล้ว assert:

```python
assert terminal_record.event_name == "market_data.runtime.failed_closed"
assert terminal_record.reason == "source_fatal"
assert terminal_record.failure_kind == "protocol"
assert not {
    "api_key",
    "secret",
    "credentials",
    "payload",
    "exception",
    "open",
    "high",
    "low",
    "close",
    "volume",
} & terminal_record.__dict__.keys()
```

- [ ] **Step 2: รัน focused tests เพื่อยืนยัน RED**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/market_data/test_runtime.py \
  tests/acceptance/test_public_market_data_runtime.py
```

Expected: FAIL เพราะ Backfill/terminal events ยังไม่ emit และ `_fail_closed()` ยังไม่รับ
`failure_kind`

- [ ] **Step 3: ส่ง failure kind เข้า terminal boundary**

ใน `src/tiewtrade/market_data/runtime.py` import `MarketDataFailureKind` กับ
`MarketDataSourceError`; เพิ่ม helper:

```python
def _failure_kind(error: BaseException) -> MarketDataFailureKind | None:
    if isinstance(error, MarketDataSourceError):
        return error.kind
    return None
```

เปลี่ยน `_fail_closed()` เป็น:

```python
def _fail_closed(
    self,
    reason: MarketDataRuntimeReason,
    *,
    failure_kind: MarketDataFailureKind | None = None,
) -> None:
    self._runtime_log.failed_closed(
        reason=reason,
        failure_kind=failure_kind,
    )
    self._transition(MarketDataRuntimeState.FAILED_CLOSED, reason)
```

Bind `as error` ใน catches ของ warm-up, live, backfill และ reconnect ที่รู้ source
exception แล้วเรียก `_fail_closed(reason, failure_kind=_failure_kind(error))`; generic,
pipeline, sink และ built-in errors ใช้ `None` ห้าม branch Runtime action ตาม kind

- [ ] **Step 4: เพิ่ม focused Backfill failure boundary**

เพิ่ม method เพื่อลดการทำ log + fail closed ซ้ำ:

```python
def _fail_backfill(
    self,
    *,
    start: datetime,
    end: datetime,
    reason: MarketDataRuntimeReason,
    failure_kind: MarketDataFailureKind | None,
) -> bool:
    self._runtime_log.backfill_failed(
        start=start,
        end=end,
        reason=reason,
        failure_kind=failure_kind,
    )
    self._fail_closed(reason, failure_kind=failure_kind)
    return False
```

ทุก failure path ภายใน `_backfill_to_boundary()` ต้อง return method นี้ด้วย reason เดิม
หลัง `process_backfill()` สำเร็จ emit:

```python
self._runtime_log.backfill_completed(
    start=start,
    end=end,
    candle_count=len(candles),
)
return True
```

- [ ] **Step 5: รักษา failure kind ล่าสุดตอน reconnect exhaustion**

ใน `_recover_stream()` เก็บ `last_failure_kind` เริ่มจาก pending rate limit kind หรือ
`None`; update เมื่อ catch `MarketDataSourceError`; reset เป็น `None` เมื่อ latest
failure เป็น generic exception แล้วส่งค่าเข้า terminal `_fail_closed()` ตอน attempts หมด
ห้ามเปลี่ยน attempts, delays หรือ reason selection เดิม

- [ ] **Step 6: รัน focused tests เพื่อยืนยัน GREEN**

Run command จาก Step 2 อีกครั้ง

Expected: focused unit/acceptance tests PASS, event order และ exact safe fields ตรง spec

- [ ] **Step 7: รัน full verification และ commit Task 4**

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
git add src/tiewtrade/market_data/runtime.py \
  tests/unit/market_data/test_runtime.py \
  tests/acceptance/test_public_market_data_runtime.py
git commit -m "feat: log market data backfill and terminal failures"
```

Expected: ทุก command exit `0`; ไม่มี network หรือ Live side effect

---

## Final Review Checklist

- ตรวจว่า event names/levels/fields ตรง design ทุกตัว
- ตรวจว่าไม่มี log call ที่ส่ง exception object/message, Candle object, OHLC, volume,
  credentials หรือ arbitrary mapping
- ตรวจว่า Runtime ไม่ branch ตาม `MarketDataFailureKind`
- ตรวจว่า state sequence/reasons, `1/2/4`, `30` และ `60` ยังตรง tests เดิม
- รัน whole-branch review จาก merge base ถึง HEAD
- รัน full verification ใหม่หลังแก้ review findings
