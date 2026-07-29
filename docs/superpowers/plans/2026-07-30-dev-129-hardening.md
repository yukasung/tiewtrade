# DEV-129 Runtime Boundary Hardening Implementation Plan

> **สำหรับ Codex:** SUB-SKILL ที่ต้องใช้: ใช้ `subagent-driven-development` เพื่อ
> ดำเนินการตามแผนนี้ทีละ task และใช้ TDD สำหรับการเปลี่ยนแปลง behavior ทุกครั้ง

**Goal:** ปิดช่องว่างทั้งห้าของ DEV-129 โดยรักษา architecture boundaries และ public
contracts เดิม

**Architecture:** ให้ UI จัดการ lifecycle ของ worker pool ที่ถูก inject, ให้ Binance
integration บังคับ request/payload contracts, ให้ SQLite integration นิยาม storage-specific
exception และให้ Desktop composition แปลงเป็น application error ก่อนถึง UI ส่วน
completed-candle pipeline เปลี่ยนเฉพาะคำอธิบาย invariant

**Tech Stack:** Python 3.12+, PySide6, pytest, pytest-qt, SQLite, Ruff, mypy

---

## Global Constraints

- ใช้ Paper/fake adapters และ local temporary SQLite เท่านั้น
- ห้ามเรียก Live order, Binance Private API, credentials หรือ OS Keyring
- UI ห้าม import SQLite integration
- `BinanceMarketDataPayloadError` และข้อความ public เดิมต้องไม่เปลี่ยน
- ทุก behavior change ต้องเห็น focused RED test ก่อนแก้ production
- ไม่สร้าง abstraction ใหม่ที่ไม่มี consumer จริงอย่างน้อยสองแบบ

## Task 1: Atomic Desktop Worker Shutdown

**Files:**

- แก้ไข: `tests/unit/ui/test_main_window.py`
- แก้ไข: `src/tiewtrade/ui/main_window.py`

### Steps

1. เพิ่ม failing test ด้วย recording thread pool เพื่อยืนยันว่า `closeEvent` เรียก
   `waitForDone(5000)` หลัง workflows ถูกปิด
2. รัน focused test และยืนยัน RED จาก missing wait behavior
3. เก็บ injected pool ใน `MainWindow`, เพิ่ม named timeout constant และรอ pool ตามลำดับ
4. รัน `tests/unit/ui/test_main_window.py` และ UI tests ที่เกี่ยวข้อง
5. Commit: `fix: wait for desktop workers during shutdown`

## Task 2: Binance Request and Payload Diagnostics

**Files:**

- แก้ไข: `tests/unit/integrations/binance/test_public_market_data.py`
- แก้ไข: `tests/unit/integrations/binance/test_kline_parser.py`
- แก้ไข: `src/tiewtrade/integrations/binance/public_market_data.py`
- แก้ไข: `src/tiewtrade/integrations/binance/kline_parser.py`

### Steps

1. เพิ่ม failing test ว่า `load_recent(count=1001)` raise `ValueError` และไม่สร้าง request
2. เพิ่ม focused tests สำหรับ malformed REST/WebSocket fields โดย assert public error text
   เดิมและ field-specific cause ใหม่
3. รัน focused tests และยืนยัน RED ของแต่ละ contract
4. เพิ่ม fail-fast page-limit guard และ diagnostic `ValueError` causes ขั้นต่ำ
5. รัน Binance market-data unit tests ทั้งชุด
6. Commit: `fix: harden Binance market data validation`

## Task 3: Typed Newer-Schema Error Through the UI Boundary

**Files:**

- แก้ไข: `tests/unit/integrations/sqlite/test_database.py`
- สร้าง: `tests/unit/application/test_database_compatibility.py`
- แก้ไข: Desktop composition tests ที่ครอบคลุม `prepare_database`
- แก้ไข: `tests/unit/ui/test_session_workflow.py`
- แก้ไข: `src/tiewtrade/integrations/sqlite/database.py`
- สร้าง: `src/tiewtrade/application/database_compatibility.py`
- แก้ไข: `src/tiewtrade/desktop_main.py`
- แก้ไข: `src/tiewtrade/ui/session_workflow.py`

### Steps

1. เพิ่ม failing SQLite test สำหรับ `UnsupportedDatabaseSchemaError` พร้อม version facts
2. เพิ่ม failing application/workflow tests สำหรับ shared
   `DatabaseCompatibilityError` และข้อความ
   `Database was created by a newer version of TiewTrade`
3. เพิ่ม composition test ว่า SQLite exception ถูก translate ที่ shared
   `prepare_database()` โดย UI ไม่ import SQLite; error contract ไม่ผูกกับ Session เพราะ
   seam นี้ใช้ทั้ง Session และ Trade History
4. รัน focused tests และยืนยัน RED ตามแต่ละ layer
5. เพิ่ม typed integration error, focused application compatibility error, composition
   translation และ UI mapping
6. รัน SQLite, application, desktop composition และ UI workflow suites
7. Commit: `fix: report unsupported database schema safely`

## Task 4: Document the Backfill Commit Invariant

**Files:**

- แก้ไข: `src/tiewtrade/market_data/candle_pipeline.py`
- ตรวจสอบ: `tests/unit/market_data/test_candle_pipeline.py`

### Steps

1. เพิ่ม code comment ก่อน ignored `accept()` return value เพื่ออธิบายว่า validation บน
   deep copy รับประกัน acceptance ใน state จริง
2. ไม่เปลี่ยน algorithm หรือ public behavior
3. รัน candle-pipeline tests
4. Commit: `docs: explain candle backfill commit invariant`

## Task 5: Whole-Issue Verification and Review

### Steps

1. รัน focused suites ของทั้งสี่ tasks
2. รัน full Python suite ด้วย `QT_QPA_PLATFORM=offscreen PYTHONPATH=src`
3. รัน `ruff check`, `ruff format --check` และ `mypy`
4. รัน documentation tests และ content checks
5. รัน `git diff --check <base> HEAD` และตรวจ working tree
6. ขอ whole-branch code review และแก้ Critical/Important findings ด้วย TDD
7. Commit correction ที่จำเป็น, ย้าย DEV-129 เป็น Done เมื่อ verification ผ่านจริง
8. หยุดรอคำยืนยันก่อน push และรอคำยืนยันแยกก่อน merge เข้า `main`
