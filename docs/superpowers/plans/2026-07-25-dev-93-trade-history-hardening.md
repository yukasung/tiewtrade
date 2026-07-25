# แผน Implement DEV-93: Trade History Hardening

> ใช้ `test-driven-development` ทำทีละพฤติกรรม และใช้
> `verification-before-completion` ก่อน commit

## เป้าหมาย

ทำให้ Paper Spot Trade History เขียน Fill กับ Basket แบบ atomic, รองรับ event
ซ้ำและ Partial Fill, ป้องกัน ownership/lifecycle ที่ไม่ถูกต้อง และหยุด Session
แบบ fail closed เมื่อ SQLite ยืนยัน durable state ไม่ได้

รายละเอียดการออกแบบและเหตุผลอยู่ใน
`docs/superpowers/specs/2026-07-25-dev-93-trade-history-hardening-design.md`

## ขอบเขตไฟล์

- แก้ `src/tiewtrade/integrations/sqlite/trade_history.py`
- แก้ `src/tiewtrade/integrations/sqlite/paper_spot_history.py`
- สร้าง
  `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- แก้ unit tests ใต้ `tests/unit/integrations/sqlite/`
- แก้ acceptance test
  `tests/acceptance/test_paper_spot_trade_history.py`
- ปรับ `ARCHITECTURE.md` และ `PROJECT_PLAN.md` ให้ ownership/status ตรงกับระบบ
- ไม่แก้ schema version, Paper executor, Live, Futures, UI หรือ Recovery

## Task 1 — Idempotency และ Partial Fill

### RED

เพิ่ม tests ใน `tests/unit/integrations/sqlite/test_trade_history.py`:

1. Fill ใหม่คืน `True`
2. `fill_id` และ payload เดิมซ้ำคืน `False`
3. `fill_id` เดิมแต่ payload ต่างกัน raise `TradeHistoryConflictError`
4. Partial Fills ที่ใช้ `order_id` เดียวกันต้องใช้ `entry_number` เดิม
5. Partial Fill ลำดับถัดไปไม่เพิ่ม `BasketResult.entry_count`

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py \
  -k "duplicate or partial" -q
```

ผล RED ที่คาดหวัง: ยังไม่มี error model, method คืน `None` และ duplicate
หลุดเป็น `sqlite3.IntegrityError`

### GREEN

เพิ่ม error model:

```python
class TradeHistoryError(RuntimeError):
    pass


class TradeHistoryConflictError(TradeHistoryError):
    pass


class TradeHistoryUnavailableError(TradeHistoryError):
    pass
```

ใช้ `fill_id` เป็น canonical key และเปรียบเทียบ `TradeFill` ทุก field:

- ไม่พบ Fill เดิม: ทำรายการและคืน `True`
- payload ตรงกัน: ไม่แก้ Basket และคืน `False`
- payload ต่างกัน: raise `TradeHistoryConflictError`

สำหรับ `record_entry_fill()` ให้ค้นหา Fill เดิมด้วย `(basket_id, order_id)`:

- พบ Order เดิม: `entry_number` ต้องเท่าเดิมและ `entry_count` ห้ามเพิ่ม
- ไม่พบ Order เดิม: `entry_number` และ proposed `entry_count` ต้องเท่ากับ
  `current.entry_count + 1`

ไม่ใช้ `INSERT OR IGNORE` และไม่เปลี่ยน schema v1

### ตรวจ Task 1

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check \
  src/tiewtrade/integrations/sqlite/trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history.py
```

## Task 2 — Ownership, Lifecycle และ Atomic Transaction

### RED

เพิ่ม tests ต่อไปนี้:

- Fill กับ Basket ใช้ `basket_id` หรือ `session_id` ต่างกัน
- proposed Basket เปลี่ยน `trade_mode`, `market_type`, `symbol`, `timeframe`,
  `strategy_preset_version` หรือ `opened_at_utc`
- `record_open_basket()` รับ Basket ที่ไม่ใช่ `OPEN`
- Entry/Close อ้าง Basket ที่ไม่มีอยู่
- Basket ที่ `CLOSED` รับ Fill ใหม่หรือกลับเป็น `OPEN`
- duplicate Close หลัง Basket ปิดแล้วเป็น no-op
- trigger บังคับให้ INSERT Fill ล้มเหลวแล้ว Open Basket ต้อง rollback
- trigger บังคับให้ UPDATE Basket ล้มเหลวแล้ว Fill ใหม่ต้อง rollback
- error จาก `close()` และ `rollback()` ห้ามหลุดเป็น raw `sqlite3.Error`

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py \
  -k "identity or closed or rollback or close_failure" -q
```

### GREEN

ทุก write ใช้ลำดับ:

1. ตรวจ Fill/Basket ownership
2. เปิด connection
3. `BEGIN IMMEDIATE`
4. ตรวจ exact duplicate ก่อน lifecycle เพื่อให้ duplicate Close เป็น no-op
5. โหลด current Basket ภายใน transaction
6. ตรวจ immutable identity และ transition `OPEN → CLOSED`
7. INSERT Fill และ INSERT/UPDATE Basket
8. commit แล้ว close

เมื่อเกิด `TradeHistoryConflictError` ให้ rollback โดยไม่ให้ cleanup error
กลบ conflict เดิม เมื่อเกิด `sqlite3.Error` จาก connect, execute, commit, rollback
หรือ close ให้ public method raise `TradeHistoryUnavailableError` และเก็บ
original exception เป็น `__cause__`

### ตรวจ Task 2

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_trade_history.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py -q
PYTHONPATH=src ../../.venv/bin/python -m mypy src
```

## Task 3 — Fail-Closed Persistent Paper Spot Session

### RED

แก้ mapper tests ให้ `record_entry()` และ `record_close()` ส่งต่อ `True/False`
จาก store แล้วสร้าง
`tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py` เพื่อพิสูจน์:

- successful Entry ถูกบันทึกก่อนคืน snapshot สถานะ `READY`
- successful Close ถูกบันทึกก่อนคืน snapshot สถานะ `READY`
- `TradeHistoryUnavailableError` ทำให้ Session เปลี่ยนเป็น `BLOCKED`
- `TradeHistoryConflictError` ทำให้ Session เปลี่ยนเป็น `BLOCKED`
- candle หลังถูก Block ต้องถูกปฏิเสธก่อนเรียก core `PaperSpotSession`

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py -q
```

### GREEN

สร้าง:

```python
class PersistenceState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class SessionPersistenceBlockedError(RuntimeError):
    pass
```

`PersistentPaperSpotSQLiteSession.process_completed_candle()` ต้อง:

1. ปฏิเสธทันทีถ้าสถานะเป็น `BLOCKED`
2. เรียก core Session นอก persistence `try`
3. บันทึก Entry/Close แบบ synchronous
4. ถ้า persistence mapping เกิด exception ให้เปลี่ยนเป็น `BLOCKED` และ re-raise
5. คืน `PersistentPaperSpotSnapshot` เฉพาะเมื่อ durability ยืนยันแล้ว

ห้าม rollback core in-memory state และห้าม fallback ไปบันทึกเฉพาะ memory

## Task 4 — Replay Acceptance และเอกสารสถานะ

แก้ `tests/acceptance/test_paper_spot_trade_history.py` ให้:

1. replay fixture รอบแรกผ่าน `PersistentPaperSpotSQLiteSession`
2. assert Basket, BUY/SELL Fills และ Net PnL `13.84062222`
3. replay Session เดิมลง database เดิมอีกครั้ง
4. เปรียบเทียบ Basket aggregate และ Fills ก่อน/หลัง replay ให้เท่ากันทุก field
5. reopen SQLite แล้วตรวจผลเดิมอีกครั้ง

ปรับ Source of Truth:

- `ARCHITECTURE.md`: `application` เป็นเจ้าของ business Session orchestration;
  `integrations/sqlite` เป็นเจ้าของ transaction, durable mapping และ
  persistence-specific fail-closed coordinator
- `PROJECT_PLAN.md`: ระบุว่า DEV-92–DEV-93 ส่งมอบ durable Paper Spot history
  ส่วน query/pagination, Paper Futures, Desktop UI และ startup Recovery ยังไม่ทำ

## Final Verification

รันใหม่ทั้งหมดจาก worktree:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

จากนั้น review `git diff main...HEAD` สองแกน:

- Standards เทียบ `AGENTS.md`, `PRODUCT.md`, `CONTEXT.md`,
  `ARCHITECTURE.md`, `PROJECT_PLAN.md`
- Spec เทียบ design และ plan ของ DEV-93

Commit implementation หลังทุก gate ผ่าน โดยยังไม่ push และไม่ merge จนกว่าจะได้รับ
คำยืนยันแยกจากผู้ใช้
