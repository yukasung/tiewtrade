# DEV-100 Structured Market Data Logging Design

**Date:** 2026-07-30
**Status:** Approved in conversation; pending written-spec review
**Scope:** Public Market Data Runtime operational diagnostics

## 1. Purpose

DEV-100 เพิ่ม structured operational logs ให้ Public Market Data Runtime เพื่อให้
ตรวจสอบ Candle ที่ถูกทิ้ง, Clock Skew, Stale Data, Stream Reconnect, Backfill และ
terminal `FAILED_CLOSED` ได้ โดยไม่เปลี่ยน state machine, retry, rate-limit,
fail-closed หรือ business/risk decision ใด ๆ

Logs ใช้ Python standard-library `logging` และ structured `LogRecord` fields เท่านั้น
Issue นี้ไม่กำหนด file handler, rotation, persistence หรือ UI log viewer

## 2. Constraints

- คง Runtime state sequence, reason และ immutable snapshot เดิม
- คง reconnect delays `1`, `2`, `4` วินาที, source deadlines `30` วินาที และ
  rate-limit fallback `60` วินาที
- ใช้ `MarketDataFailureKind` เป็น diagnostic metadata เท่านั้น Runtime ยังตัดสินใจจาก
  action exception type เดิม
- ห้ามบันทึก API Key, Secret, credentials, private account payload, response body,
  exception message, Candle OHLC หรือ volume
- Logging failure ต้องไม่เปลี่ยน Runtime decision หรือทำให้ Runtime หยุด
- แยกเฉพาะ `Exception` จาก logging backend; ไม่จับ `BaseException` เช่น
  `KeyboardInterrupt` หรือ `SystemExit`
- ใช้ fake source, fake scheduler และ fake logger ใน tests เท่านั้น ไม่มี Binance
  network, Private API หรือ Live Order
- ไม่สร้าง generic logging interface, registry, factory หรือ persistence adapter

## 3. Architecture

เพิ่ม concrete `MarketDataRuntimeLog` ใน `market_data/runtime_logging.py` เพื่อเป็น
boundary เดียวที่กำหนด event names, levels, field whitelist และ serialization
Class นี้รับ concrete `logging.Logger` และมี typed method ต่อ event แทนการเปิด
arbitrary `**fields`

`MarketDataRuntime` รับ optional `logger: logging.Logger | None`; หากไม่ส่งให้ใช้
module logger ชื่อ `tiewtrade.market_data.runtime` แล้วสร้าง `MarketDataRuntimeLog`
ภายใน Runtime Production composition จึงใช้ Python logging hierarchy ตามปกติโดยไม่
ต้องเพิ่ม adapter หรือ configuration ใหม่

```text
CompletedCandleStream ── decision ──> CompletedCandlePipeline
                                          │
MarketDataRuntime ── typed event ──────────┼─> MarketDataRuntimeLog
                                          │        │
                                          │        └─> logging.Logger
                                          └─ existing state/risk decisions unchanged
```

## 4. Candle Acceptance Contract

เปลี่ยน `CompletedCandleStream.accept()` จาก boolean เป็น `CandleAcceptance` ซึ่งเป็น
`StrEnum` ใน module เดิม:

| Value | ความหมาย |
| --- | --- |
| `ACCEPTED` | Candle ใหม่ ปิดแล้ว และต่อเนื่อง |
| `NOT_CLOSED` | `received_at < candle.close_time` |
| `DUPLICATE_OR_OUT_OF_ORDER` | `candle.open_time <= last_open_time` |

Symbol/timeframe/UTC/OHLC validation และ `CandleGapError` คง semantics เดิม
`CompletedCandlePipeline` ต้องเปรียบเทียบ enum อย่าง explicit ใน warm-up, live และ
backfill paths เพื่อไม่พึ่ง truthiness ของ enum

`process_live()` คืน `CandleAcceptance` ให้ Runtime จึงสามารถบันทึก discard reason
โดยไม่อ่าน private state ของ stream ส่วน warm-up หรือ backfill rejection ยังคงเป็น
`CandlePipelineInputError` และ fail closed ตามเดิม เพราะไม่ใช่ silent live discard

## 5. Event Contract

`MarketDataEventName` เป็น `StrEnum` และทุก record ใช้ event name เป็นทั้ง log message
และ field `event_name`

| Event name | Level | Whitelisted fields |
| --- | --- | --- |
| `market_data.candle.discarded` | `INFO` | `event_name`, `symbol`, `timeframe`, `open_time`, `received_at`, `discard_reason` |
| `market_data.clock_skew.detected` | `WARNING` | `event_name`, `symbol`, `timeframe`, `open_time`, `close_time`, `received_at`, `skew_seconds` |
| `market_data.stale.detected` | `WARNING` | `event_name`, `symbol`, `timeframe`, `reason`, `last_accepted_open_time` |
| `market_data.reconnect.attempted` | `WARNING` | `event_name`, `symbol`, `timeframe`, `attempt`, `delay_seconds`, `reason` |
| `market_data.backfill.completed` | `INFO` | `event_name`, `symbol`, `timeframe`, `start`, `end`, `candle_count` |
| `market_data.backfill.failed` | `ERROR` | `event_name`, `symbol`, `timeframe`, `start`, `end`, `reason`, `failure_kind` |
| `market_data.runtime.failed_closed` | `ERROR` | `event_name`, `symbol`, `timeframe`, `reason`, `failure_kind` |

Serialization rules:

- `datetime` เป็น UTC ISO-8601 string ผ่าน `isoformat()`
- enum เป็น `.value`
- `attempt` และ `candle_count` เป็น integer
- `delay_seconds` และ `skew_seconds` เป็น non-negative float
- `failure_kind` เป็น `transport`, `protocol`, `payload` หรือ `None`
- Optional timestamp ที่ไม่มีค่าใช้ `None`

`MarketDataRuntimeLog` ไม่รับ Candle object, exception object, exception message,
HTTP body หรือ arbitrary mapping จึงไม่สามารถส่งข้อมูลนอก whitelist โดยบังเอิญ

## 6. Event Emission Rules

### 6.1 Live Candle discard และ Clock Skew

เมื่อ `process_live()` คืน `NOT_CLOSED` ให้ Runtime emit ตามลำดับ:

1. `market_data.candle.discarded`
2. `market_data.clock_skew.detected`

โดย `skew_seconds = (candle.close_time - received_at).total_seconds()` และต้องเป็นบวก
แนวทางนี้ไม่เรียก Binance Server Time API

เมื่อคืน `DUPLICATE_OR_OUT_OF_ORDER` ให้ emit เฉพาะ
`market_data.candle.discarded` ส่วน `ACCEPTED` ไม่ emit discard event

### 6.2 Stale Data

Emit `market_data.stale.detected` เฉพาะเมื่อ freshness timeout ทำให้ Runtime เข้า
`STALE / DATA_STALE` ไม่ใช้ event นี้กับ `STALE / SOURCE_DISCONNECTED`

### 6.3 Stream Reconnect

Emit `market_data.reconnect.attempted` หลังรอ delay สำเร็จและก่อนเปิด stream ใหม่
เพื่อไม่บันทึก attempt ที่ถูก Stop Session ยกเลิกระหว่างรอ

`attempt` เริ่มที่ `1` ถึง `3`; `delay_seconds` ใช้ delay จริงทั้ง bounded
`1/2/4` และ provider/fallback rate-limit delay; `reason` ใช้ Runtime reason ที่ทำให้
เริ่ม recovery

REST retries ภายใน `_run_source_operation()` ไม่ใช่ Stream Reconnect และไม่ emit
event นี้

### 6.4 Backfill Result

Emit `market_data.backfill.completed` หลัง `process_backfill()` ส่ง Candle เข้า sink
สำเร็จทั้งหมด ค่า `candle_count` คือจำนวน Candle ที่โหลดสำหรับ requested range

หาก source load, validation หรือ sink delivery ล้ม ให้ emit
`market_data.backfill.failed` ก่อน fail closed โดยใช้ Runtime reason เดียวกับ terminal
decision และส่ง `failure_kind` เฉพาะเมื่อ exception เป็น `MarketDataSourceError`

### 6.5 Terminal Failure

ทุก `_fail_closed()` emit `market_data.runtime.failed_closed` ด้วย terminal reason และ
optional `failure_kind` ก่อน transition ไป `FAILED_CLOSED` Logging exception ถูก isolate
และไม่ขัดขวาง transition

Backfill failure จะมีทั้ง `market_data.backfill.failed` และ
`market_data.runtime.failed_closed` เพราะ event แรกอธิบาย operation ส่วน event หลัง
อธิบาย terminal Runtime state

## 7. Error Isolation

ทุก typed method เรียก private `_emit()` ซึ่งครอบเฉพาะ `logger.log(...)`:

```python
try:
    self._logger.log(level, event_name.value, extra=fields)
except Exception:
    return
```

ห้าม log ซ้ำเมื่อ `_emit()` ล้ม เพราะอาจเกิด recursion Logging ไม่เปลี่ยน return value,
exception mapping, sleep, timeout, state transition หรือ sink delivery

## 8. Testing Strategy

ใช้ TDD แยกสาม behavior:

1. `CompletedCandleStream` tests พิสูจน์ acceptance enum, discard reason และ gap/
   validation semantics เดิม
2. `MarketDataRuntimeLog` tests พิสูจน์ event name, level, exact field whitelist,
   ISO-8601 serialization, absence of sensitive fields, `Exception` isolation และ
   `BaseException` propagation
3. Runtime tests พิสูจน์ discard/clock skew, stale, reconnect, backfill success/failure
   และ terminal fail-closed events พร้อมยืนยัน state/reason/delay/deadline เดิม

Acceptance test ของ Public Market Data Runtime ต้องพิสูจน์ว่า logging ไม่เปลี่ยน
end-to-end fail-closed flow และ records ไม่มี secret/private fields

หลัง focused tests ผ่าน ต้องรัน Python suite ทั้งหมด, Ruff check, Ruff format check,
mypy source, docs tests, content check และ `git diff --check`

## 9. Expected File Changes

- Create: `src/tiewtrade/market_data/runtime_logging.py`
- Modify: `src/tiewtrade/market_data/completed_candle_stream.py`
- Modify: `src/tiewtrade/market_data/candle_pipeline.py`
- Modify: `src/tiewtrade/market_data/runtime.py`
- Create: `tests/unit/market_data/test_runtime_logging.py`
- Modify: `tests/unit/market_data/test_completed_candle_stream.py`
- Modify: `tests/unit/market_data/test_candle_pipeline.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `tests/acceptance/test_public_market_data_runtime.py`

ไม่เพิ่ม production module อื่น เพราะ event ownership อยู่ที่ Market Data consumer
module และ output ใช้ concrete Python logging ที่มีอยู่แล้ว

## 10. Success Criteria

- Structured logs ครอบคลุม discard, Clock Skew, Stale Data, Stream Reconnect,
  Backfill success/failure และ terminal fail-closed
- Event name, level และ fields เป็น deterministic contract ที่ tests ตรวจได้
- Logs ไม่ถือ secrets, private payload, exception message, OHLC หรือ volume
- Logging backend failure ไม่เปลี่ยน Runtime decision
- Existing Runtime state, retry, timeout, rate-limit และ fail-closed behavior ไม่เปลี่ยน
- Regression tests และ quality gates ผ่านโดยไม่มี network หรือ Live side effect

## 11. Out of Scope

- File/JSON formatter, handler configuration, rotation หรือ retention policy
- SQLite persistence ของ logs หรือ operational events
- Desktop log viewer, notification หรือ alert routing
- Binance Server Time API หรือ Clock synchronization
- Private account, credentials, Live Order หรือ execution behavior
- การเปลี่ยน Strategy, Session, Basket, risk หรือ capital policy
