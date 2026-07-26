# DEV-99 Market Data Runtime Refactor Design

**Date:** 2026-07-26

**Status:** Implemented and verified

**Scope:** Behavior-preserving refactor of DEV-99

## 1. Purpose

ลดความซับซ้อนภายใน Public Binance Market Data Runtime โดยคง public interface,
state sequence, failure policy และผลลัพธ์เดิมทั้งหมด ก่อน refactor
`market_data/runtime.py` เคยรวม lifecycle orchestration, candle validation, sink
delivery, watermark publishing และ runtime status ไว้ในไฟล์เดียว ทำให้ invariant
สำคัญกระจายอยู่หลาย method

Refactor นี้สร้าง deep internal modules สองส่วนแล้ว เพื่อให้กฎการส่ง candle และการ
เผยแพร่ runtime status มีเจ้าของเพียงจุดเดียว โดย `MarketDataRuntime` ยังคงเป็น
external interface เดิมของ application และ tests

## 2. Constraints

- ห้ามเปลี่ยน public interface ของ `MarketDataRuntime`,
  `MarketDataCandleSource`, `MarketDataCandleSink` หรือ application composition
- ห้ามเปลี่ยน state sequence ที่ sink และ caller สังเกตได้
- ห้ามเปลี่ยน timeout, retry, backfill, fail-closed หรือ shutdown policy
- ห้ามเพิ่ม generic base class, registry, factory หรือ hypothetical adapter
- ห้ามรวม DEV-100 structured logging, DEV-101 diagnostic cleanup หรือ DEV-102
  test typing expansion
- ห้ามใช้ API Key, private Binance endpoint, network test หรือ Live Order

## 3. Decision

ใช้ `MarketDataRuntime` เป็น lifecycle orchestrator และแยก implementation ภายใน
เป็น `CompletedCandlePipeline` กับ `MarketDataRuntimeStatus`

```text
MarketDataRuntime -> CompletedCandlePipeline -> MarketDataCandleSink
                           |
                           +-> MarketDataRuntimeStatus.record_delivery(...)
```

`MarketDataRuntime` records state transitions with `MarketDataRuntimeStatus`;
`CompletedCandlePipeline` records the delivery watermark only after a successful
sink delivery.

Recovery และ backfill orchestration ยังคงอยู่ใน `MarketDataRuntime` เพราะต้องใช้
source, scheduler, deadline, retry policy และ lifecycle state ร่วมกัน การแยกสอง
ส่วนนี้ออกเป็น module เพิ่มจะทำให้เกิด shallow modules และเพิ่ม interface โดยไม่
เพิ่ม leverage

## 4. Module Responsibilities

### 4.1 MarketDataRuntime

`market_data/runtime.py` ยังคงเป็น external seam และรับผิดชอบ:

- เริ่มและหยุด runtime
- ขอ Warm-up และ backfill candles จาก source ภายใน deadline
- consume live stream และตรวจ freshness deadline
- orchestrate stale, reconnect และ bounded retry
- เลือก runtime state/reason ตามผลจาก source และ pipeline
- ปิด source แบบ idempotent

Properties `snapshot` และ `visited_states` ยังคงอยู่และ delegate ไปยัง status
module เพื่อไม่ให้ caller ต้องเปลี่ยนโค้ด

### 4.2 CompletedCandlePipeline

สร้าง `market_data/candle_pipeline.py` เป็น internal deep module ที่รับผิดชอบ:

- ใช้ `CompletedCandleStream` ตรวจ identity, UTC alignment, duplicate และ
  continuity
- เป็นเจ้าของ deduplication และ sink-delivery invariant ทั้งหมด
- ตรวจจำนวนและความต่อเนื่องของ Warm-up batch
- ตรวจ backfill batch และ buffered observation ก่อนเริ่ม delivery
- เรียก `MarketDataCandleSink`
- แจ้ง successful delivery หลัง sink สำเร็จเท่านั้น

Interface ภายในมีสาม operation:

- `warm_up(...)`
- `process_live(...)`
- `process_backfill(...)`

`process_backfill(...)` รับ lifecycle callback ภายในหนึ่งรายการ Pipeline เรียก
callback นี้หลังตรวจ batch ผ่านและก่อนส่ง candle แรก เพื่อรักษาพฤติกรรมเดิมที่
Runtime เปลี่ยนเป็น `LIVE / BACKFILL_COMPLETED` ก่อน sink รับ backfilled candles
Callback นี้ไม่เป็นส่วนหนึ่งของ public application interface

### 4.3 MarketDataRuntimeStatus

เพิ่ม tracker ใน `market_data/runtime_state.py` เพื่อเป็นเจ้าของ:

- immutable `MarketDataRuntimeSnapshot`
- state และ reason ปัจจุบัน
- transition timestamp จาก injected clock
- last delivered candle watermark
- state history ที่รองรับ `visited_states` เดิม

Interface ภายในประกอบด้วย:

- `snapshot`
- `visited_states`
- `transition(state, reason)`
- `record_delivery(open_time)`

`record_delivery` ต้องสร้าง snapshot ใหม่โดยรักษา state, reason และ transition
timestamp เดิมไว้ การแก้ policy เกี่ยวกับ unbounded state history ไม่อยู่ใน scope
นี้และถูกติดตามแยกใน DEV-101

## 5. Data Flow

### 5.1 Warm-up

1. Runtime เปลี่ยนเป็น `WARMING_UP`
2. Runtime ขอ completed candles จาก source ภายใน 30 วินาที
3. Pipeline ตรวจจำนวน, ordering และ continuity
4. Pipeline ส่งทั้ง batch เข้า warm-up sink
5. เมื่อ sink สำเร็จ Pipeline บันทึก watermark ของ candle สุดท้าย
6. Runtime เปลี่ยนเป็น `LIVE / WARM_UP_COMPLETED`

Sink failure ต้องไม่เลื่อน watermark

### 5.2 Live Candle

1. Runtime รับ completed candle จาก source ภายใน freshness deadline
2. Pipeline ตรวจ candle ผ่าน `CompletedCandleStream`
3. Duplicate คืนผลว่าไม่ต้องส่งซ้ำ
4. Gap ส่งสัญญาณให้ Runtime เริ่ม backfill
5. Candle ที่ต่อเนื่องถูกส่งเข้า sink
6. Pipeline บันทึก watermark หลัง sink สำเร็จ
7. Runtime publish `LIVE / LIVE_CANDLE_ACCEPTED`

### 5.3 Backfill

1. Runtime เปลี่ยนเป็น `BACKFILLING / GAP_DETECTED`
2. Runtime โหลดช่วงที่ขาดภายใน 30 วินาที
3. Pipeline ตรวจ batch ทั้งชุดและ buffered observation ก่อน delivery
4. Pipeline เรียก lifecycle callback เพื่อ publish
   `LIVE / BACKFILL_COMPLETED`
5. Pipeline ส่ง candle ตาม open time
6. Pipeline เลื่อน watermark หลังแต่ละ sink delivery สำเร็จ

หาก sink ล้มเหลวกลาง batch snapshot ต้องรายงาน watermark ของ candle ล่าสุดที่
ส่งสำเร็จ ไม่ใช่ candle สุดท้ายของ batch

## 6. Failure Handling

- Invalid, insufficient หรือ discontinuous input ถูก map เป็น `SOURCE_ERROR`
- `CandleGapError` จาก live candle เริ่ม backfill แทน terminal failure
- Sink exception ถูก map เป็น `SINK_ERROR`
- Warm-up timeout ยังคงเป็น `WARM_UP_TIMEOUT`
- Backfill source/timeout failure ยังคงเป็น `SOURCE_ERROR`
- Reconnect exhaustion ยังคงเป็น `RECONNECT_EXHAUSTED`
- `FAILED_CLOSED` ยังคง terminal สำหรับ runtime instance เดิม
- Refactor ห้ามเพิ่ม fallback, invented candle หรือ unbounded retry

Pipeline ใช้ focused internal exceptions แยก input failure ออกจาก sink failure
เพื่อให้ Runtime map reason ได้โดยไม่ inspect exception message

## 7. Testing Strategy

สร้าง `tests/unit/market_data/test_candle_pipeline.py` เพื่อทดสอบผ่าน internal
pipeline interface:

- successful Warm-up และ watermark
- Warm-up sink failure ไม่เลื่อน watermark
- duplicate live candle ไม่ส่งซ้ำ
- live gap ส่งสัญญาณ backfill
- backfill validation เกิดก่อน delivery
- lifecycle callback เกิดก่อน backfill sink calls
- partial backfill sink failure เก็บ watermark ของ delivery ล่าสุด

`test_runtime.py` ยังคงทดสอบ behavior ที่ external Runtime interface:

- deadlines และ timeout mapping
- state sequence
- stale/reconnect/backfill orchestration
- terminal failure
- idempotent shutdown และ cancellation

Tests ที่ซ้ำเฉพาะ implementation detail จะถูกย้าย ไม่เพิ่ม test ซ้อนสองชั้นโดยไม่มี
observable behavior ต่างกัน Acceptance tests เดิมต้องผ่านโดยไม่เปลี่ยน assertion

## 8. File Changes

- Create: `src/tiewtrade/market_data/candle_pipeline.py`
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `src/tiewtrade/market_data/runtime_state.py`
- Create: `tests/unit/market_data/test_candle_pipeline.py`
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify เฉพาะเอกสาร DEV-99 เมื่อชื่อหรือ ownership เปลี่ยน

## 9. Success Criteria

- Public interface และ observable state sequence เดิม
- Watermark เลื่อนหลัง successful sink delivery เท่านั้น
- Candle validation และ sink-delivery invariant มีเจ้าของเพียง module เดียว
- Runtime lifecycle code ไม่ทำ validation หรือสร้าง snapshot โดยตรง
- Tests ทั้ง repository ผ่าน
- Ruff check, Ruff format check, mypy และ `git diff --check` ผ่าน
- ไม่มี credentials, network call หรือ Live Order ใน verification

## 10. Out of Scope

- Structured logging และ operational events (DEV-100)
- การลดหรือลบ `visited_states`, optional observation cleanup และ error taxonomy
  expansion (DEV-101)
- การขยาย mypy ให้ตรวจ test suite ทั้ง repository (DEV-102)
- Feature, UI, persistence หรือ trading-policy behavior ใหม่
