# SQLite WAL and Busy Timeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ทุก file-backed connection จาก `SQLiteDatabase.connect()` ใช้ WAL และรอ writer lock สูงสุด 5 วินาที

**Architecture:** Concrete SQLite adapter เป็นเจ้าของ concurrency policy และกำหนด PRAGMA ทุกครั้งที่เปิด connection โดยไม่เปลี่ยน repository interface หรือ transaction boundary เดิม Contract tests อ่านค่าจาก connection จริงและพิสูจน์ว่า reader อ่าน committed snapshot ได้ระหว่าง writer transaction

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, pytest, Ruff, mypy strict

## Global Constraints

- ใช้ file-backed SQLite และ temporary test databases เท่านั้น
- ไม่เปลี่ยน schema version, migration, repository contract หรือ business rules
- กำหนด `busy_timeout` เป็น `5000` milliseconds และ `journal_mode` เป็น `WAL`
- ไม่เพิ่ม retry loop, connection pool, background thread หรือ configuration option
- ใช้ TDD: tests ใหม่ต้อง fail กับ implementation เดิมก่อนแก้ production code

---

## File Structure

- Create: `tests/unit/integrations/sqlite/test_database.py` — contract tests สำหรับ connection policy และ concurrent reader
- Modify: `src/tiewtrade/integrations/sqlite/database.py` — กำหนด SQLite connection policy ที่ boundary เดียว

### Task 1: Enforce the SQLite connection concurrency policy

**Files:**
- Create: `tests/unit/integrations/sqlite/test_database.py`
- Modify: `src/tiewtrade/integrations/sqlite/database.py:5-15`

**Interfaces:**
- Consumes: `SQLiteDatabase(path: pathlib.Path)` และ `SQLiteDatabase.connect() -> sqlite3.Connection`
- Produces: file-backed connection ที่รายงาน `journal_mode = wal`, `busy_timeout = 5000` และเปิด foreign keys

- [ ] **Step 1: Write failing connection-policy tests**

สร้าง `tests/unit/integrations/sqlite/test_database.py` ด้วยเนื้อหาต่อไปนี้:

```python
from pathlib import Path

from tiewtrade.integrations.sqlite.database import SQLiteDatabase


def test_connect_enables_wal_and_explicit_busy_timeout(tmp_path: Path) -> None:
    connection = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3").connect()
    try:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        connection.close()

    assert journal_mode == "wal"
    assert busy_timeout == 5_000


def test_reader_can_read_committed_snapshot_while_writer_is_active(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    writer = database.connect()
    reader = database.connect()
    try:
        writer.execute(
            "CREATE TABLE concurrency_probe (value TEXT NOT NULL)"
        )
        writer.commit()
        reader.execute("PRAGMA busy_timeout = 50")

        writer.execute("BEGIN EXCLUSIVE")
        writer.execute(
            "INSERT INTO concurrency_probe (value) VALUES ('uncommitted')"
        )

        rows = reader.execute(
            "SELECT value FROM concurrency_probe ORDER BY value"
        ).fetchall()
    finally:
        writer.rollback()
        reader.close()
        writer.close()

    assert rows == []
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_database.py -q
```

Expected: FAIL เพราะ file-backed database ยังรายงาน `journal_mode = delete` และ reader
ถูก rollback-journal lock ขวาง

- [ ] **Step 3: Implement the minimal connection policy**

แก้ส่วนต้นของ `src/tiewtrade/integrations/sqlite/database.py` เป็น:

```python
import sqlite3
from pathlib import Path


class SQLiteDatabase:
    _SCHEMA_VERSION = 3
    _BUSY_TIMEOUT_MS = 5_000

    def __init__(self, path: Path) -> None:
        self._path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute(
            f"PRAGMA busy_timeout = {self._BUSY_TIMEOUT_MS}"
        )
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
```

คง methods และ schema functions หลัง `connect()` ไว้เหมือนเดิมทั้งหมด

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_database.py -q
```

Expected: `2 passed` และไม่มี warning

- [ ] **Step 5: Run the SQLite integration regression suite**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/acceptance/test_trade_history_query_acceptance.py -q
```

Expected: tests ทั้งหมด PASS และไม่มี `database is locked`

- [ ] **Step 6: Run focused static checks**

Run:

```bash
../../.venv/bin/python -m ruff check \
  src/tiewtrade/integrations/sqlite/database.py \
  tests/unit/integrations/sqlite/test_database.py
../../.venv/bin/python -m ruff format --check \
  src/tiewtrade/integrations/sqlite/database.py \
  tests/unit/integrations/sqlite/test_database.py
../../.venv/bin/python -m mypy src
```

Expected: ทุกคำสั่ง exit `0`

- [ ] **Step 7: Commit the tested implementation**

```bash
git add \
  src/tiewtrade/integrations/sqlite/database.py \
  tests/unit/integrations/sqlite/test_database.py
git commit -m "fix: enforce SQLite concurrency policy"
```

### Task 2: Run the integration gate and review the issue branch

**Files:**
- Verify: `src/tiewtrade/integrations/sqlite/database.py`
- Verify: `tests/unit/integrations/sqlite/test_database.py`
- Verify: `docs/superpowers/specs/2026-07-27-sqlite-wal-busy-timeout-design.md`

**Interfaces:**
- Consumes: tested DEV-118 connection policy จาก Task 1
- Produces: verification evidence และ reviewed branch ที่พร้อมส่งมอบโดยยังไม่ push หรือ merge

- [ ] **Step 1: Run the full Python gate**

Run:

```bash
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
```

Expected: tests ทั้งหมด PASS และ static checks ทุกคำสั่ง exit `0`

- [ ] **Step 2: Run documentation and whitespace gates**

Run:

```bash
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main..HEAD
```

Expected: documentation tests รายงาน `50` tests ผ่าน และคำสั่งที่เหลือ exit `0`

- [ ] **Step 3: Inspect scope and safety**

Run:

```bash
git diff --stat main..HEAD
git diff main..HEAD -- \
  src/tiewtrade/integrations/sqlite/database.py \
  tests/unit/integrations/sqlite/test_database.py \
  docs/superpowers/specs/2026-07-27-sqlite-wal-busy-timeout-design.md \
  docs/superpowers/plans/2026-07-27-sqlite-wal-busy-timeout.md
git status --short
```

Expected: diff อยู่ในสี่ไฟล์ตามแผน, ไม่มี schema, business rule, UI, Binance,
credential หรือ user-owned file change และ worktree สะอาด

- [ ] **Step 4: Review the complete branch**

ใช้ `requesting-code-review` ตรวจ diff `main..HEAD` ตามสองแกน:

- Standards: DEV-118 acceptance criteria, design, repository rules, TDD evidence และ
  Trading Safety
- Code Quality: PRAGMA ordering, deterministic file-backed connection tests และ
  ไม่มี abstraction เกินความจำเป็น

แก้ Critical/Important findings และรัน verification ที่เกี่ยวข้องซ้ำก่อนรายงานเสร็จ

- [ ] **Step 5: Update Linear after verification**

เพิ่ม comment ภาษาไทยใน DEV-118 โดยสรุป files, behavior, RED/GREEN evidence,
ผล full gates และ commit range จากนั้นย้าย DEV-118 เป็น `Done` เฉพาะเมื่อ review
ไม่มี Critical/Important findings งานนี้ยังไม่ย้าย DEV-117 เป็น `Done`

ห้าม push ไป GitHub หรือ merge เข้า `main` จนกว่าจะได้รับคำยืนยันแยกจากผู้ใช้
