# DEV-127 Shared Persistence Coordinator Design

**Date:** 2026-07-30
**Status:** Approved
**Scope:** Paper Spot and Paper Futures fail-closed persistence coordination

## 1. Purpose

Paper Spot และ Paper Futures มี persistence coordinator คนละ class แต่ทำ state machine
ชุดเดียวกันทุกขั้นตอน: ตรวจว่า session ยังรับ candle ได้, ประมวลผล completed candle,
บันทึก snapshot แบบ synchronous, เปลี่ยนเป็น `BLOCKED` เมื่อการบันทึกล้มเหลว และคืน
snapshot เมื่อบันทึกสำเร็จ ความแตกต่างจริงอยู่เฉพาะการแปลง Spot/Futures snapshot ไปเป็น
Trade History records

DEV-127 จึงรวมเฉพาะ state machine นี้เป็น coordinator เดียว หลังมี consumer จริงครบสองแบบ
โดยไม่รวม application sessions, Trade History adapters หรือ business rules ของ Spot/Futures
เข้าด้วยกัน

## 2. Chosen Approach

ใช้ application-owned contract ร่วมกับ SQLite-owned implementation:

- `application/session_persistence.py` ประกาศ persistence state, blocked error,
  generic persisted snapshot และ `SessionPersistenceCoordinator` protocol
- `integrations/sqlite/session_persistence.py` มี
  `SQLiteSessionPersistenceCoordinator` เพียง class เดียวที่ implement fail-closed state
  machine
- `persistent_paper_spot_session.py` และ
  `persistent_paper_futures_session.py` เก็บเฉพาะ snapshot recorder และ composition
  function ของตลาดนั้น
- ลบ concrete coordinator เดิม
  `PersistentPaperSpotSQLiteSession` และ `PersistentPaperFuturesSQLiteSession` รวมถึง
  result type ที่ซ้ำกัน โดยไม่สร้าง compatibility alias

แนวทางนี้รักษา dependency direction เพราะ application ไม่ import integration ขณะที่ SQLite
integration import application contract และ concrete Paper sessions ได้ตาม composition role

## 3. Public Contract

Application contract ต้องเล็กและสื่อเฉพาะ behavior ที่ caller ใช้:

- `PersistenceState` มี `READY` และ `BLOCKED`
- `SessionPersistenceBlockedError` หมายถึง coordinator ไม่ยอมรับ candle เพิ่ม เพราะ
  durability ของ Trade History ไม่แน่นอนแล้ว
- `PersistentSessionSnapshot[SessionSnapshotT]` เก็บ application session snapshot และ
  persistence state
- `SessionPersistenceCoordinator[SessionSnapshotT]` มี
  `process_completed_candle(candle, *, received_at)` เพียง operation เดียว

contract ไม่รู้จัก SQLite, Paper Spot, Paper Futures หรือ `MarketType`

## 4. Composition and Data Flow

Spot และ Futures มี composition function แยกกันเพื่อ validate Session Identity และประกอบ
dependency ที่ถูกชนิด:

```text
completed Candle
       |
       v
SQLiteSessionPersistenceCoordinator
       |
       +--> concrete Paper Session.process_completed_candle(...)
       |          |
       |          v
       |    Spot/Futures Session Snapshot
       |
       +--> market-specific Snapshot Recorder
                  |
                  v
        market-specific SQLite Trade History
```

coordinator ไม่เลือกตลาดและไม่มี `if MarketType` หรือ `match MarketType` การเลือก Spot หรือ
Futures เกิดตอน composition ด้วย recorder ที่ส่งเข้า constructor เท่านั้น

Spot recorder ต้องรักษากฎเดิมเรื่อง Entry Fill, Take Profit Fill, closed Basket และ Basket ID
ส่วน Futures recorder ต้องรักษากฎเดิมเรื่อง Entry Fill, Take Profit/Liquidation Exit Fill,
closed Basket, entry number และ Basket ID

## 5. Fail-Closed Semantics

ลำดับการทำงานต้องคงเดิมอย่างเคร่งครัด:

1. หาก state เป็น `BLOCKED` ให้ raise `SessionPersistenceBlockedError` ก่อนเรียก Session
2. เรียก application Session นอก persistence error boundary
3. เรียก snapshot recorder ภายใน persistence error boundary
4. หาก recorder หรือ Trade History raise exception ให้เปลี่ยน state เป็น `BLOCKED` และ
   re-raise exception เดิม
5. คืน `PersistentSessionSnapshot` หลังบันทึกสำเร็จเท่านั้น

Session processing exception ไม่ใช่ persistence failure จึงต้องไม่เปลี่ยน state เป็น
`BLOCKED` ส่วน mapping validation error ของ recorder ถือเป็น persistence uncertainty และ
ต้อง fail closed เช่นเดียวกับ SQLite write error

ข้อความ blocked error เดิม
`Session is blocked because Trade History persistence failed` ต้องไม่เปลี่ยน

## 6. Identity Validation

Spot และ Futures composition functions ต้องตรวจว่า application Session และ Trade History
ใช้ `SessionIdentity` เดียวกันก่อนสร้าง coordinator และรักษาข้อความ error ของแต่ละตลาดไว้
การตรวจนี้เป็นหน้าที่ของ market-specific composition เพราะ common coordinator ไม่ควรรู้จัก
ชนิดของ Session หรือ History

## 7. Testing Strategy

ใช้ TDD แยกความรับผิดชอบดังนี้:

1. common coordinator tests ใช้ fake processor และ recorder เพื่อพิสูจน์ READY flow,
   synchronous persistence, recorder failure -> BLOCKED, blocked subsequent candle และ
   processor failure ที่ไม่เปลี่ยนเป็น persistence failure
2. Spot adapter tests พิสูจน์ identity validation และ Spot snapshot-to-history mapping เดิม
3. Futures adapter tests พิสูจน์ identity validation, Take Profit/Liquidation mapping และ
   entry-number behavior เดิม
4. acceptance/support callers เปลี่ยนไปใช้ composition functions และ common result โดย
   observable Trade History behavior ต้องไม่เปลี่ยน
5. ตรวจ dependency direction, ไม่มี `MarketType` conditional และไม่มีชื่อ concrete class เดิม
6. รัน full Python suite, Ruff, formatter, mypy strict, documentation tests และ
   `git diff --check`

## 8. Non-Goals

- ไม่รวม `paper_spot_history.py` กับ `paper_futures_history.py`
- ไม่รวม `paper_spot_session.py` กับ `paper_futures_session.py`
- ไม่เปลี่ยน SQLite schema, transaction boundary หรือ Trade History data model
- ไม่เปลี่ยน order matching, PnL, Basket, Entry Pair, Take Profit หรือ Liquidation rules
- ไม่เพิ่ม Live execution, Binance Private API หรือ credential access
- ไม่เพิ่ม `MarketType` switch, registry, factory hierarchy หรือ generic repository
- ไม่รักษา compatibility aliases ของ concrete coordinator เดิมซึ่งยังเป็น internal API
