# DEV-136 Paper Runtime Lifecycle Implementation Plan

> For agentic workers: use subagent-driven-development (recommended) or executing-plans task by task.

**Goal:** ให้ Workspace เริ่ม หยุด และกู้คืน Paper Spot/Futures runtime ได้จริง โดยไม่ block UI และ fail closed เมื่อ runtime หรือ SQLite ไม่พร้อม

**Architecture:** เพิ่ม PaperRuntimeController เป็น application owner ของ lifecycle จริง: สร้าง concrete Paper Spot/Futures session, เชื่อม persistent history, เรียก Public Market Data Runtime บน dedicated asyncio thread และแปลง facts เป็น immutable TradingWorkspaceSnapshot. SQLite เก็บ lifecycle marker เพียงพอสำหรับตรวจ startup recovery; runtime ที่กำลังทำงานก่อนโปรแกรมปิดจะไม่ resume แบบเดา state แต่เข้าสู่ BLOCKED จนผู้ใช้ Recover เพื่อจบเป็น STOPPED อย่างปลอดภัย.

**Tech Stack:** Python 3.14, PySide6 6.10, asyncio, SQLite, pytest, pytest-qt, Ruff, Mypy strict

## Global Constraints

- Paper Spot และ Paper Futures ใช้ SessionConfig, strategy, capital, Entry Pair และ Basket policies ที่มีอยู่ร่วมกัน; execution ใช้ concrete Paper adapters เท่านั้น
- ห้ามเรียก Binance Private API, credentials, Live adapter หรือส่ง Live order
- Runtime, SQLite และ market-data work ต้องไม่ block UI thread
- Stop Session หยุด Entry ใหม่, persist lifecycle marker, คง Basket Take Profit และไม่ force close; deadline คือ 30 seconds
- failure จาก SQLite, warm-up, runtime หรือ recovery ต้อง return safe BLOCKED state พร้อม sanitized message เท่านั้น
- ใช้ UTC และ Decimal; ไม่ใช้ float หรือ local time
- UI รับ immutable TradingWorkspaceSnapshot เท่านั้น และไม่ import SQLite, session หรือ market-data runtime
- ไม่เพิ่ม generic base class, factory หรือ registry ที่ไม่มี consumer จริง

---

## File Structure

- Create src/tiewtrade/application/paper_runtime.py — ownership ของ Paper Spot/Futures runtime, startup/stop/recovery และ snapshot projection
- Create src/tiewtrade/integrations/sqlite/paper_runtime_lifecycle.py — SQLite lifecycle marker ของ Active Paper Session
- Modify src/tiewtrade/integrations/sqlite/database.py — schema migration สำหรับ marker ที่ durable
- Modify src/tiewtrade/application/trading_workspace.py — pure converters จาก Paper runtime facts เป็น Workspace Header, Orders และ Basket snapshots
- Modify src/tiewtrade/ui/bot_lifecycle_workflow.py, src/tiewtrade/ui/main_window.py, src/tiewtrade/ui/desktop.py และ src/tiewtrade/desktop_main.py — wire runtime snapshots กับ UI thread และ controlled shutdown
- Create/modify focused tests under tests/unit/application, tests/unit/integrations/sqlite, tests/unit/ui, and tests/acceptance
- Modify PROJECT_PLAN.md — บันทึก DEV-136 scope ที่ส่งมอบจริงและข้อจำกัด recovery

## Task 1: Persist Paper Runtime Lifecycle Facts

**Files:** database.py, new paper_runtime_lifecycle.py, new test_paper_runtime_lifecycle.py

**Consumes:** active bot_sessions row keyed by session_id.

**Produces:** SQLitePaperRuntimeLifecycle.read(session_id) -> PaperRuntimeLifecycleRecord | None, mark_running(session_id, observed_at_utc), and mark_stopped(session_id, observed_at_utc).

- [ ] Write failing tests for no marker, running/stopped UTC persistence, unknown session and sanitized SQLite failure.
- [ ] Verify RED with the focused SQLite test.
- [ ] Add schema v4 migration for a one-row-per-session lifecycle marker (session_id, state, observed_at_utc); use BEGIN IMMEDIATE and translate errors to PaperRuntimeLifecycleUnavailableError.
- [ ] Verify GREEN and commit feat: persist paper runtime lifecycle.

## Task 2: Paper Runtime Controller and Snapshot Projection

**Files:** new paper_runtime.py; modify trading_workspace.py; new test_paper_runtime.py; modify test_trading_workspace.py

**Consumes:** ConfiguredPaperSession, existing MarketDataRuntime, existing Spot/Futures sessions and persistence coordinators, lifecycle adapter.

**Produces:** PaperRuntimeController.start(session) -> BotLifecycleResult, stop(session) -> BotLifecycleResult, recover(session) -> BotLifecycleResult, and a current immutable workspace callback.

- [ ] Write failing tests using deterministic fake public market data: Spot/Futures choose their existing concrete session/persistence adapters; warm-up reaches RUNNING once; a completed candle refreshes Header freshness, Open Orders and Position/Basket; sink/persistence failure preserves last-known facts and returns sanitized BLOCKED.
- [ ] Verify RED: QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/application/test_paper_runtime.py -q.
- [ ] Implement the deep module. Select Spot/Futures with a concrete market-type branch, start an owned asyncio loop, wait only for LIVE or terminal failure, and use pure snapshot projection helpers. Do not duplicate strategy/capital policy.
- [ ] Verify GREEN and commit feat: run paper market data lifecycle.

## Task 3: Stop Deadline and Safe Startup Recovery

**Files:** modify paper_runtime.py; tests in test_paper_runtime.py and new test_paper_runtime_lifecycle.py

**Consumes:** lifecycle marker and controller.

**Produces:** 30-second stop deadline; recovery that returns CONFIGURED only after a clean stopped marker and returns BLOCKED for prior running marker, missing durable state or persistence failure.

- [ ] Write failing tests: Stop calls runtime shutdown, prevents new Entry, preserves Basket/Take Profit and writes stopped; timeout/storage error yields BLOCKED; interrupted running marker never resumes execution and Recover ends safely STOPPED.
- [ ] Verify RED with both focused test files.
- [ ] Implement bounded stop through the owning runtime loop. Recovery verifies and safely stops only; it never reconstructs indicators or pending intents from history.
- [ ] Verify GREEN and commit feat: recover paper runtime safely.

## Task 4: Wire Runtime Snapshots into Desktop UI

**Files:** modify bot_lifecycle_workflow.py, main_window.py, desktop.py, desktop_main.py; tests in test_bot_lifecycle_workflow.py, test_main_window.py, test_desktop_main.py

**Consumes:** controller lifecycle actions and immutable workspace callback.

**Produces:** Start/Stop/Recover actions are supplied by desktop composition, and current-generation runtime updates render through the UI thread.

- [ ] Write failing UI/composition tests: Start only runs once; runtime snapshot updates header/tables outside the UI worker; Stop retains Basket; stale callbacks after close/reconfigure are ignored; no network contact occurs.
- [ ] Verify RED with the three focused suites.
- [ ] Add one generation-guarded snapshot publication path to the existing lifecycle workflow and controlled runtime shutdown in MainWindow.closeEvent. Keep SQLite composition in desktop_main.
- [ ] Verify GREEN and commit feat: wire paper runtime into desktop controls.

## Task 5: Paper Spot/Futures Acceptance and Delivery Record

**Files:** modify tests/acceptance/test_desktop_session_setup.py, tests/acceptance/test_paper_futures_session.py, PROJECT_PLAN.md

- [ ] Add fake-source acceptance paths for both market types: create, start exactly once, warm-up, completed candle updates, Stop retains Basket, restart detects unsafe runtime marker, and SQLite/runtime failure is safe.
- [ ] Run acceptance tests, then full suite: QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest -q.
- [ ] Update project plan to state that interruption recovery blocks rather than fabricates indicator/pending-intent state; notifications, chart and Live remain later issues.
- [ ] Commit test: verify paper runtime lifecycle.

## Final Verification

- [ ] QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest -q
- [ ] PYTHONPATH=src .venv/bin/python -m ruff check src tests
- [ ] PYTHONPATH=src .venv/bin/python -m ruff format --check src tests
- [ ] PYTHONPATH=src .venv/bin/python -m mypy
- [ ] npm --prefix docs-site test && npm --prefix docs-site run check:content
- [ ] git diff --check
- [ ] Update DEV-136 acceptance criteria and move it to Done only after all checks pass

## Plan Self-Review

- Coverage: all DEV-136 acceptance criteria map to Tasks 1–5.
- Safety: the only network seam is existing public market data; no Private API or Live adapter is introduced.
- Recovery: interrupted runtime is explicitly fail-closed rather than reconstructed from insufficient history.
- Boundaries: SQLite remains in integrations, orchestration is application-owned and UI renders immutable snapshots.

