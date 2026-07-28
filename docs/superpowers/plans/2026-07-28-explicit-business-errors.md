# Explicit Business Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** แทน production `assert` ที่ทำหน้าที่ป้องกัน business state ด้วย explicit exceptions ซึ่งยังทำงานเมื่อรัน Python ด้วย `-O`

**Architecture:** คง ownership เดิมทั้งหมด โดย `trading` ป้องกัน Entry Pair lifecycle invariant ของตนเอง และ `application` ตรวจ Futures Session configuration ที่ boundary ก่อนสร้าง runtime dependencies ไม่เพิ่ม abstraction หรือเปลี่ยน valid-session behavior

**Tech Stack:** Python 3.12, Pytest, Ruff และ Mypy strict

## Global Constraints

- แก้เฉพาะ `assert` ใน `EntryPairLifecycle.can_enter()` และ `PaperFuturesSession.__init__()` ตาม DEV-125
- คง internal `assert` จุดอื่นที่ใช้ type narrowing หลัง guard และไม่ได้เป็น public business validation
- `EntryPairLifecycle` ต้อง raise `RuntimeError` พร้อมข้อความที่สื่อว่า completed-pair state ขาด month เมื่อพบ state ที่ไม่สอดคล้องกัน
- `PaperFuturesSession` ต้อง raise `ValueError` ที่ระบุ `futures_policy` เมื่อได้รับ Futures configuration ที่ขาด policy
- valid Entry Pair, Paper Futures, deterministic replay และ execution behavior ต้องไม่เปลี่ยน
- ทดสอบทั้ง Python ปกติและ `python -O`
- ใช้ Paper/fake data เท่านั้น ห้ามเรียก Binance private API หรือส่ง Live order

---

### Task 1: แทน business assertions ด้วย explicit exceptions

**Files:**
- Modify: `src/tiewtrade/trading/entry_pair.py`
- Modify: `src/tiewtrade/application/paper_futures_session.py`
- Test: `tests/unit/trading/test_entry_pair.py`
- Test: `tests/unit/application/test_paper_futures_session.py`

**Interfaces:**
- Consumes: `EntryPairLifecycle.can_enter(at: datetime) -> bool`
- Produces: `RuntimeError("completed Entry Pair is missing its completion month")` เมื่อ completed-pair state ไม่สมบูรณ์
- Consumes: `PaperFuturesSession(session, market_data, symbol_rules, preset)`
- Produces: `ValueError` ที่มีคำว่า `futures_policy` เมื่อ Futures Session ขาด policy

- [ ] **Step 1: เขียน failing Entry Pair invariant test**

สร้าง lifecycle ที่บันทึกครบหนึ่ง Pair แล้วจำลอง state ที่เสียหายโดยล้าง `_completed_pair_month` จากนั้นยืนยันว่า `can_enter()` raise `RuntimeError` พร้อมข้อความที่สื่อความหมาย

- [ ] **Step 2: รัน Entry Pair test และตรวจสอบ RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_entry_pair.py::test_completed_pair_requires_completion_month -q
```

ผลที่คาดหวัง: production code เดิม raise `AssertionError` แทน `RuntimeError`

- [ ] **Step 3: implement Entry Pair explicit guard ขั้นต่ำ**

แทน `assert self._completed_pair_month is not None` ด้วย explicit `if ... is None: raise RuntimeError(...)` แล้วคง cooldown calculation เดิม

- [ ] **Step 4: เขียน failing Futures configuration test**

สร้าง `SessionConfig` ที่ถูกต้องก่อน แล้วจำลอง corrupted persisted/input state ด้วยการทำให้ `futures_policy` เป็น `None`; ยืนยันว่า constructor raise `ValueError` ที่ระบุ `futures_policy`

- [ ] **Step 5: รัน Futures test และตรวจสอบ RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_futures_session.py::test_session_requires_futures_policy -q
```

ผลที่คาดหวัง: guard เดิมให้ข้อความทั่วไป `Paper Futures` และไม่ผ่าน contract ที่ระบุสาเหตุ

- [ ] **Step 6: implement Futures explicit guard ขั้นต่ำ**

แยก validation ของ `trade_mode`/`market_type` ออกจาก `futures_policy`, เก็บ policy ที่ผ่าน validation ไว้ใน local variable และใช้ตัวแปรนั้นสร้าง identity, executor dependencies, margin model และ capital plan โดยไม่ใช้ `assert`

- [ ] **Step 7: รัน targeted tests ทั้ง normal และ optimized mode**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_entry_pair.py \
  tests/unit/application/test_paper_futures_session.py -q
PYTHONPATH=src ../../.venv/bin/python -O -m pytest \
  tests/unit/trading/test_entry_pair.py \
  tests/unit/application/test_paper_futures_session.py -q
```

ผลที่คาดหวัง: tests ผ่านทั้งสอง mode และ explicit exceptions มี behavior เหมือนกัน

- [ ] **Step 8: รัน full verification gates**

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -O -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

ผลที่คาดหวัง: ทุก gate ผ่าน โดย optimized full suite พิสูจน์ว่า business validation ไม่พึ่ง `assert`

- [ ] **Step 9: commit implementation**

```bash
git add \
  src/tiewtrade/trading/entry_pair.py \
  src/tiewtrade/application/paper_futures_session.py \
  tests/unit/trading/test_entry_pair.py \
  tests/unit/application/test_paper_futures_session.py
git commit -m "fix: raise explicit business state errors"
```
