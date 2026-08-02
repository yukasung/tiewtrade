# DEV-137 Notification Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development task-by-task.

**Goal:** เพิ่ม Notification Center สำหรับ operational and safety feedback ของ Paper Trading Workspace

**Architecture:** เก็บ notification เป็น in-memory UI read model ที่รับ immutable lifecycle/workspace results เท่านั้น. Header และ drawer render state เดียวกัน; Bot Control ยังคง render safety state โดยไม่พึ่ง drawer.

**Tech Stack:** Python 3.14, PySide6, pytest-qt, pytest, Ruff, MyPy

## Global Constraints

- Paper/fake only; ห้าม private Binance, Live adapter, credentials หรือ network ใหม่
- UI ไม่ import SQLite, session, strategy หรือ execution
- ทุกข้อความต้อง sanitized; ห้าม raw exception, database path หรือ transport payload
- เวลาเป็น UTC; acknowledge ห้ามเปลี่ยน durable trading state

## File Structure

- Create `src/tiewtrade/ui/notification_center.py` — immutable records, in-memory store และ mapping
- Modify `src/tiewtrade/ui/bot_lifecycle_workflow.py` — publish lifecycle/workspace events ไป store
- Modify `src/tiewtrade/ui/main_window.py` และ workspace widgets — header badge/drawer rendering
- Create `tests/unit/ui/test_notification_center.py`; modify workflow/window/acceptance tests

## Task 1: Notification Read Model

**Files:** Create `src/tiewtrade/ui/notification_center.py`; Create `tests/unit/ui/test_notification_center.py`

**Produces:** `NotificationStore.publish(result, occurred_at_utc)`, `acknowledge(fingerprint)`, `unread_count`, `highest_unread_severity`, immutable notification rows.

- [ ] Write failing tests for BLOCKED/STALE/recovery mapping, UTC records, raw message sanitization, duplicate fingerprints and idempotent acknowledge.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../.venv/bin/python -m pytest tests/unit/ui/test_notification_center.py -q`; expect RED.
- [ ] Implement enum/record/store with bounded in-memory list and stable fingerprint derived only from safe state/category/message.
- [ ] Rerun focused tests; expect PASS. Commit `feat: add notification read model`.

## Task 2: Workflow and Desktop Drawer

**Files:** Modify `src/tiewtrade/ui/bot_lifecycle_workflow.py`, `src/tiewtrade/ui/main_window.py`, existing widgets/tests.

**Consumes:** `NotificationStore` and queued UI-thread lifecycle results.

**Produces:** Header unread/highest severity status, drawer rows with UTC/severity/category/message, acknowledge UI action, and unchanged Bot Control state.

- [ ] Write failing Qt tests for current-generation event rendering, stale callback rejection, repeated event responsiveness and acknowledge behavior.
- [ ] Run focused UI tests; expect RED.
- [ ] Wire store on Qt thread only; make drawer read model renderable at all sizes and preserve Blocked/Stale outside drawer.
- [ ] Rerun tests; expect PASS. Commit `feat: show notification center safety feedback`.

## Task 3: Acceptance and Delivery Record

**Files:** Modify acceptance tests and `PROJECT_PLAN.md`.

- [ ] Add deterministic Paper/fake flows for Blocked, Stale and Recovery; assert no private credential/network or SQLite trading mutation from acknowledge.
- [ ] Run focused acceptance RED/then GREEN.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../.venv/bin/python -m pytest -q`, Ruff, format check, MyPy and `git diff --check`.
- [ ] Update project plan and commit `test: verify notification safety feedback`.

## Final Verification

- [ ] Full pytest, Ruff check/format, MyPy and diff check pass.
- [ ] Review all DEV-137 acceptance criteria; move Linear issue Done only after verification.
