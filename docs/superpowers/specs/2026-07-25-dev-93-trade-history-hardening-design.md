# DEV-93 Trade History Hardening Design

## 1. เป้าหมาย

ทำให้ Trade History ที่เริ่มใน DEV-92 ทนต่อ event ซ้ำ, Partial Fill และ
SQLite failure โดยรักษากฎต่อไปนี้:

- Fill ใหม่กับ Basket aggregate เปลี่ยนพร้อมกันหรือไม่เปลี่ยนเลย
- Fill เดิมไม่ถูกนับซ้ำ
- Fill ID เดิมที่มี payload ต่างกันถูกปฏิเสธ
- ownership และ Basket lifecycle ต้องถูกต้องก่อนเขียน
- Session หยุดรับ candle ใหม่ทันทีเมื่อยืนยัน durable persistence ไม่ได้

งานนี้ใช้ Paper และ fake failure scenarios เท่านั้น ไม่เชื่อม Binance Private API
และไม่ส่ง Live order

## 2. ขอบเขต

### 2.1 สิ่งที่ทำ

- รองรับหลาย `TradeFill` ที่ใช้ `order_id` เดียวกัน แต่มี `fill_id` ต่างกัน
- ใช้ `fill_id` เป็น canonical idempotency key
- ทำ write methods ของ `SQLiteTradeHistory` ให้ atomic และ idempotent
- ตรวจ Session/Basket ownership และ immutable market identity
- บังคับ Basket transition `OPEN → CLOSED` ทางเดียว
- แปลง SQLite failure เป็น error ที่ caller เข้าใจได้
- เพิ่ม SQLite-specific Session wrapper ที่เปลี่ยนเป็น `BLOCKED` เมื่อ persistence
  ไม่สำเร็จ
- พิสูจน์ว่า replay event ซ้ำไม่เพิ่ม Fill หรือ PnL ซ้ำ

### 2.2 สิ่งที่ไม่ทำ

- ไม่เปลี่ยน `PaperSpotExecutor` ให้จำลอง Partial Fill
- ไม่เพิ่ม generic persistence interface ก่อนมี adapter ตัวที่สอง
- ไม่เพิ่ม query, filter, summary หรือ pagination ซึ่งเป็นขอบเขต DEV-94
- ไม่เพิ่ม Paper Futures, Live adapter, UI หรือ startup Recovery
- ไม่ rollback in-memory state ของ `PaperSpotSession` หลัง Fill เกิดขึ้นแล้ว
- ไม่เพิ่ม schema version 2 หรือ Binance-specific unique index ก่อนมี Live producer

## 3. Architecture

```text
PaperSpotSession
      │ PaperSpotSessionSnapshot
      ▼
PersistentPaperSpotSQLiteSession
      │ synchronous record
      ▼
PaperSpotSQLiteHistory
      │ normalized BasketResult + TradeFill
      ▼
SQLiteTradeHistory
```

### 3.1 `SQLiteTradeHistory`

`src/tiewtrade/integrations/sqlite/trade_history.py` เป็นเจ้าของ:

- transaction
- idempotency comparison
- ownership validation
- lifecycle validation
- canonical SQLite read/write errors

Public write methodsเปลี่ยนเป็น:

```python
def record_open_basket(
    self,
    basket: BasketResult,
    fill: TradeFill,
) -> bool: ...

def record_entry_fill(
    self,
    basket: BasketResult,
    fill: TradeFill,
) -> bool: ...

def record_closed_basket(
    self,
    basket: BasketResult,
    fill: TradeFill,
) -> bool: ...
```

คืน `True` เมื่อเขียน Fill ใหม่และเปลี่ยน Basket aggregate สำเร็จ คืน `False`
เมื่อ `fill_id` เดิมมี payload ตรงกันทุก fieldและไม่มีการเปลี่ยน Basket

### 3.2 `PaperSpotSQLiteHistory`

`src/tiewtrade/integrations/sqlite/paper_spot_history.py` ยังคง normalize Paper
execution result และส่ง aggregate ที่คำนวณแล้วเข้า `SQLiteTradeHistory`
โดย `record_entry()` และ `record_close()` ส่งต่อผล `bool` ให้ caller

Mapper ไม่เป็นเจ้าของ transaction และไม่ตัดสินว่า duplicate เปลี่ยนยอดหรือไม่
เพราะ store ต้องตรวจ Fill เดิมภายใน transaction เดียวกับ Basket mutation

### 3.3 `PersistentPaperSpotSQLiteSession`

สร้าง
`src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
เพื่อ compose `PaperSpotSession` กับ `PaperSpotSQLiteHistory` โดยตรง

วาง Module นี้ใน SQLite integration เพื่อรักษา dependency direction:
`application` และ `trading` ไม่ import SQLite และยังไม่ต้องสร้าง hypothetical
persistence seam

Interface:

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
    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentPaperSpotSnapshot: ...
```

## 4. Canonical Idempotency

`fill_id` เป็น identity หลักสำหรับ Fill ทุก source

### 4.1 Fill ใหม่

```text
BEGIN IMMEDIATE
  → validate Basket/Fill identity
  → query existing Fill by fill_id
  → load and validate current Basket
  → INSERT Trade Fill
  → INSERT or UPDATE Basket Result
COMMIT
```

สำหรับ Basket ใหม่ต้อง insert Basket ก่อน Fill เพราะ foreign key แต่ทั้งสองคำสั่ง
อยู่ใน transaction เดียวกัน หาก Fill insert ล้มเหลว Basket insert ต้อง rollback

### 4.2 Fill เดิม

Store query Fill ด้วย `fill_id` ก่อนตรวจหรือ apply proposed Basket:

- ทุก field ตรงกัน: return `False`
- field ใด field หนึ่งต่างกัน: raise `TradeHistoryConflictError`

ลำดับนี้สำคัญ เพราะ mapper อาจสร้าง proposed aggregate ที่รวม duplicate event
มาแล้ว Store ต้องตรวจและหยุดก่อน mutation จึงไม่มีการเพิ่ม aggregate ซ้ำ

### 4.3 Partial Fill

หลาย Partial Fills ต่อหนึ่ง Order ใช้:

```text
order_id = order เดียวกัน
fill_id = execution แต่ละครั้ง
```

ดังนั้น `order_id` ไม่เป็น unique key แต่ละ Fill ใหม่เพิ่ม aggregate ได้หนึ่งครั้ง
ตาม `fill_id` ของตน

Partial Fills ของ Entry เดียวกันต้องใช้ `entry_number` เดียวกัน โดย
`BasketResult.entry_count` นับจำนวน Entry ไม่ใช่จำนวน Fill จึงเพิ่มเพียงครั้งเดียว
เมื่อ Order ของ Entry นั้นเริ่มมี Fill รายการแรก Fill ถัดไปของ Order เดิมเพิ่มเฉพาะ
quantity, notional และ commission aggregate ที่เกี่ยวข้อง

DEV-93 ทดสอบความสามารถนี้ที่ normalized persistence layer โดยสร้าง
`TradeFill` หลายรายการ ไม่เปลี่ยน Paper execution model

### 4.4 SQLite Schema

คง `PRAGMA user_version = 1`

Primary Key `trade_fills.fill_id` เพียงพอสำหรับ canonical idempotency
ส่วน constraint เดิม:

```sql
UNIQUE (source, order_id, exchange_trade_id)
```

ไม่ถูกใช้เป็น Paper idempotency rule เพราะ Paper ใช้ `exchange_trade_id = NULL`
และ SQLite อนุญาต `NULL` ซ้ำ การกำหนด Binance uniqueness จะทำเมื่อมี Live
producer และ exchange identity semantics จริง

## 5. Ownership และ Lifecycle Validation

ก่อน mutation ต้องตรวจ:

- `basket.basket_id == fill.basket_id`
- `basket.session_id == fill.session_id`
- Basket ที่อยู่ใน SQLite ใช้ `session_id` เดียวกัน
- `trade_mode`, `market_type`, `symbol`, `timeframe`,
  `strategy_preset_version` และ `opened_at_utc` เปลี่ยนไม่ได้
- `record_entry_fill()` รับเฉพาะ proposed Basket สถานะ `OPEN`
- `record_closed_basket()` รับเฉพาะ current Basket `OPEN` และ proposed Basket
  `CLOSED`
- Basket `CLOSED` รับ Fill ใหม่หรือกลับเป็น `OPEN` ไม่ได้
- Basket ที่ไม่มีอยู่ปิดหรือเพิ่ม Entry ไม่ได้

Duplicate Fill ที่ payload เหมือนเดิมคืน `False` ก่อน lifecycle mutation
เพื่อให้ retry ของ close event ที่ Basket ปิดแล้วเป็น no-op ได้

## 6. Transaction และ Error Model

เพิ่ม error hierarchy ใน SQLite history Module:

```python
class TradeHistoryError(RuntimeError):
    pass


class TradeHistoryConflictError(TradeHistoryError):
    pass


class TradeHistoryUnavailableError(TradeHistoryError):
    pass
```

ทุก public read/write method:

- ปิด connection ใน `finally`
- แปลง `sqlite3.Error` เป็น `TradeHistoryUnavailableError`
- เก็บ original exception เป็น `__cause__`
- ไม่แปลง `TradeHistoryConflictError`

Write methods ใช้ `BEGIN IMMEDIATE` และ commit หลัง Fill กับ Basket สำเร็จทั้งคู่
เท่านั้น ถ้า insert/update/commit ล้มเหลว context manager rollback transaction

## 7. Fail-Closed Session State

State transition:

```text
READY
  │ persistence exception
  ▼
BLOCKED
```

`PersistentPaperSpotSQLiteSession.process_completed_candle()`:

1. ถ้า state เป็น `BLOCKED` ให้ raise `SessionPersistenceBlockedError`
   ก่อนเรียก core Session
2. เรียก `PaperSpotSession.process_completed_candle()`
3. ถ้ามี Entry Fill ให้บันทึก synchronously
4. ถ้ามี Closed Basket ให้บันทึก synchronously
5. ถ้าเกิด exception ระหว่าง persistence ให้เปลี่ยนเป็น `BLOCKED`
   แล้ว re-raise original exception
6. ถ้าสำเร็จคืน `PersistentPaperSpotSnapshot` พร้อม state `READY`

การ catch ครอบเฉพาะ persistence block แต่จับทุก `Exception` โดยตั้งใจ:
หาก durable recording ยืนยันไม่ได้ไม่ว่าจาก SQLite, conflict หรือ programming
error Session ต้องหยุดก่อนรับ candle ถัดไป

Core Session อาจเปลี่ยน in-memory stateแล้วก่อน persistence failure งานนี้ไม่
rollback state ดังกล่าว แต่ห้ามใช้ state นั้นทำ Entry ต่อ ไม่มี in-memory history
fallback และ startup Recovery เป็นงานแยก

## 8. Testing Strategy

### 8.1 Unit Tests

`tests/unit/integrations/sqlite/test_trade_history.py`:

- Partial Fills สองรายการใช้ `order_id` เดียวกันและ `fill_id` ต่างกัน
- Partial Fills ใช้ `entry_number` เดียวกันและไม่เพิ่ม `entry_count` ซ้ำ
- exact duplicate คืน `False`
- conflicting duplicate raise `TradeHistoryConflictError`
- ownership mismatch ทุกกรณีถูกปฏิเสธ
- identity field ที่ถูกแก้ถูกปฏิเสธ
- unknown Basket ถูกปฏิเสธ
- Closed Basket ไม่รับ Entry Fill
- Closed Basket ไม่กลับเป็น Open
- duplicate close หลังปิดแล้วเป็น no-op

### 8.2 Transaction Tests

ใช้ temporary SQLite และ test-only trigger เพื่อบังคับ failure:

- Fill insert ล้มเหลวแล้ว Basket insert/update ไม่คงอยู่
- Basket update ล้มเหลวแล้ว Fill insert rollback
- SQLite exception ถูกแปลงเป็น `TradeHistoryUnavailableError`

### 8.3 Session Tests

`tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`:

- Entry/close ถูกบันทึกก่อนรับ candle ถัดไป
- persistence error ครั้งแรกเปลี่ยน state เป็น `BLOCKED`
- call หลัง Blocked raise `SessionPersistenceBlockedError`
- core `PaperSpotSession` ไม่ถูกเรียกหลัง Blocked
- ไม่มี fallback store

### 8.4 Acceptance Tests

ขยาย Paper Spot history acceptance:

- replay ครั้งแรกสร้าง BUY/SELL และ Net PnL เดิม
- replay event เดิมซ้ำผ่าน mapper/store เดิมไม่เพิ่ม Fill
- Basket aggregate และ Net PnL ไม่เปลี่ยน
- ปิดและเปิด SQLite file ใหม่แล้วยังอ่านข้อมูลได้ครบ

Regression gates:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

## 9. Acceptance Mapping

| DEV-93 Acceptance Criterion | Design Coverage |
| --- | --- |
| หลาย Partial Fills ต่อ Order | Section 4.3, 8.1 |
| duplicate ไม่เปลี่ยน record/aggregate | Section 4.2, 8.1, 8.4 |
| Fill และ Basket atomic | Section 4.1, 6, 8.2 |
| ownership mismatch ถูกปฏิเสธ | Section 5, 8.1 |
| Closed Basket immutable | Section 5, 8.1 |
| SQLite failure → Blocked | Section 6–7, 8.3 |
| Blocked ไม่สร้าง Entry ใหม่ | Section 7, 8.3 |
| error/duplicate tests | Section 8 |
