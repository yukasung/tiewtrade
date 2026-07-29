# DEV-128 Repository Source of Truth Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ `AGENTS.md` อ้าง Source of Truth ที่มีอยู่จริง และลบเฉพาะ worktree ที่พิสูจน์แล้วว่าไม่มีงานตกหล่น

**Architecture:** ใช้ `docs/superpowers/specs/` เป็นแหล่งเหตุผลของการตัดสินใจเพียงแห่งเดียว แล้วใช้ Git ancestry และ working-tree state เป็น gate ก่อนลบ worktree แต่ละตัว งาน recovery ของ DEV-115/DEV-116 แยกอยู่ใน DEV-130 และไม่ถูกแก้หรือทำความสะอาดใน Issue นี้

**Tech Stack:** Markdown, Git worktree, Linear, Python quality gates, Node.js documentation checks

## Global Constraints

- ใช้แนวทาง B: `AGENTS.md` ต้องอ้าง `docs/superpowers/specs/` และห้ามสร้าง `docs/adr/`
- ห้ามแก้ product code, business rules, UI, persistence, execution หรือ Trading Safety
- ต้องเก็บ worktree และ branch ของ DEV-115/DEV-116 ไว้สำหรับ DEV-130
- ลบได้เฉพาะ worktree DEV-95, DEV-99, DEV-114, DEV-118 และ DEV-121 หลัง re-audit ผ่าน
- ห้ามใช้ `git worktree remove --force`, ห้ามลบ branch/tag และห้าม rewrite history
- `.superpowers/` ใน DEV-99 เป็น generated review scratch ที่ design อนุมัติให้ทิ้งได้; ห้ามลบไฟล์ untracked อื่น
- ห้าม push หรือ merge DEV-128 จนกว่าผู้ใช้จะยืนยันแยกตาม Git Workflow

---

### Task 1: Align repository Source of Truth

**Files:**
- Modify: `AGENTS.md:16`
- Test: repository contract commands และ documentation checks

**Interfaces:**
- Consumes: directory `docs/superpowers/specs/`
- Produces: repository instruction ที่ชี้ path ซึ่งมีอยู่จริง

- [ ] **Step 1: รัน contract check ก่อนแก้และยืนยันว่า fail**

Run:

```bash
test -d docs/superpowers/specs
! rg -n 'docs/adr/' AGENTS.md
```

Expected: คำสั่งแรกผ่าน แต่คำสั่งที่สอง fail เพราะ `AGENTS.md` ยังมี `docs/adr/`

- [ ] **Step 2: แก้ Source of Truth path ขั้นต่ำ**

แทนบรรทัด:

```markdown
- `docs/adr/` — เหตุผลของการตัดสินใจด้านสถาปัตยกรรม
```

ด้วย:

```markdown
- `docs/superpowers/specs/` — เหตุผลของการตัดสินใจด้านสถาปัตยกรรม
```

ห้ามแก้คำสั่ง repository ข้ออื่นใน Task นี้

- [ ] **Step 3: รัน contract check หลังแก้และยืนยันว่า pass**

Run:

```bash
test -d docs/superpowers/specs
! rg -n 'docs/adr/' AGENTS.md
rg -n 'docs/superpowers/specs/' AGENTS.md
```

Expected: ทุกคำสั่ง exit `0` และคำสั่งสุดท้ายแสดง Source of Truth path ใหม่หนึ่งบรรทัด

- [ ] **Step 4: รัน focused documentation gates**

Run:

```bash
npm --prefix docs-site ci
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Expected: documentation tests ผ่าน 50 tests, content check ผ่าน และ `git diff --check` ไม่มี output

- [ ] **Step 5: Commit Task 1**

```bash
git add AGENTS.md
git commit -m "docs: align repository source of truth"
```

Expected: commit มีเฉพาะ `AGENTS.md`

---

### Task 2: Re-audit and remove safe stale worktrees

**Files:**
- Delete worktree directories only:
  - `.worktrees/dev-95`
  - `.worktrees/dev-99-runtime-refactor`
  - `.worktrees/dev-114`
  - `.worktrees/dev-118`
  - `.worktrees/dev-121`
- Preserve:
  - `.worktrees/dev-115`
  - `.worktrees/dev-116`
  - `.worktrees/dev-128`

**Interfaces:**
- Consumes: `main` at the DEV-128 base plus Task 1 commit
- Produces: Git worktree registry ที่เหลือเฉพาะ active/recovery worktrees

- [ ] **Step 1: ตรวจ safe candidates ซ้ำก่อนลบ**

รัน `git status --short` ภายใน DEV-95, DEV-114, DEV-118 และ DEV-121 ทีละตัว
Expected: ไม่มี output

จาก repository root รัน ancestry checks:

```bash
git merge-base --is-ancestor dev-95-paper-futures-trade-history main
git merge-base --is-ancestor dev-114-desktop-session-recovery main
git merge-base --is-ancestor dev-118-sqlite-wal-busy-timeout main
git merge-base --is-ancestor dev-121-ci-verification-workflow main
git merge-base --is-ancestor 2ee2b28 main
```

Expected: ทุกคำสั่ง exit `0`; หากคำสั่งใด fail ให้หยุด Task 2 และรายงาน `BLOCKED`

- [ ] **Step 2: ตรวจ DEV-99 scratch scope ก่อนทิ้ง**

Run จาก `.worktrees/dev-99-runtime-refactor`:

```bash
git status --short
find .superpowers -maxdepth 3 -type f -print | sort
```

Expected: untracked มีเฉพาะ `.superpowers/` และรายการภายในมีเฉพาะ SDD brief, report,
review diff และ progress artifacts หากพบไฟล์อื่นให้หยุดและรายงาน `BLOCKED`

- [ ] **Step 3: ทิ้ง DEV-99 generated scratch เท่านั้น**

ลบเฉพาะ directory ต่อไปนี้จาก DEV-99 worktree:

```bash
rm -rf .superpowers
```

หลังลบ Run:

```bash
git status --short
```

Expected: ไม่มี output ห้ามลบ ignored caches หรือไฟล์อื่นด้วยคำสั่ง cleanup แบบกว้าง

- [ ] **Step 4: ลบ safe worktree registrations จาก repository root**

Run ทีละคำสั่งและหยุดทันทีเมื่อคำสั่งใด fail:

```bash
git worktree remove .worktrees/dev-95
git worktree remove .worktrees/dev-99-runtime-refactor
git worktree remove .worktrees/dev-114
git worktree remove .worktrees/dev-118
git worktree remove .worktrees/dev-121
git worktree prune
```

ห้ามเพิ่ม `--force` และห้ามใช้ `git branch -d` หรือ `git push --delete`

- [ ] **Step 5: ยืนยัน preserved worktrees และ branches**

Run:

```bash
git worktree list
git status --short
git -C .worktrees/dev-115 status --short
git -C .worktrees/dev-116 status --short
git branch --list dev-115-desktop-session-acceptance dev-116-desktop-session-workflow
git branch -r --list origin/dev-115-desktop-session-acceptance origin/dev-116-desktop-session-workflow
```

Expected:

- worktree list เหลือ repository root, DEV-115, DEV-116 และ DEV-128
- status ของ repository root, DEV-115 และ DEV-116 สะอาด
- local และ remote branch ของ DEV-115/DEV-116 ยังอยู่ครบ

- [ ] **Step 6: บันทึก operational evidence**

เขียนรายงาน Task 2 ใน `.superpowers/sdd/task-2-report.md` โดยระบุ:

- worktree ที่ลบจริง
- ancestry SHA ที่ตรวจ
- DEV-99 scratch file classes ที่ทิ้ง
- worktree และ branch ที่คงไว้
- ยืนยันว่าไม่มี branch/tag ถูกลบ

Task นี้ไม่มี repository commit เพราะเปลี่ยนเฉพาะ local Git worktree state

---

### Task 3: Align Linear scope and run final verification

**Files:**
- Modify: Linear issue DEV-128 description
- Verify: repository และ preserved worktrees

**Interfaces:**
- Consumes: Task 1 tracked change และ Task 2 operational report
- Produces: DEV-128 audit trail ที่ตรงกับ repository state

- [ ] **Step 1: ปรับ DEV-128 description ให้ตรงกับสถานะจริง**

หลัง Task 2 ลบครบทั้งห้าตัวแล้ว แทน description ด้วย Markdown ต่อไปนี้:

```markdown
## เป้าหมาย

ทำให้ Repository Instructions อ้าง Source of Truth ที่มีอยู่จริง และลบเฉพาะ stale
worktree ที่ตรวจ Git ancestry แล้วว่าไม่มีงานตกหล่น

## การตัดสินใจ

- ใช้ `docs/superpowers/specs/` เป็นแหล่งเหตุผลของการตัดสินใจด้านสถาปัตยกรรม
- ไม่สร้าง `docs/adr/` ซ้ำ
- `.mcp.json` และ `.superpowers/` ถูก ignore แล้วก่อนเริ่ม Issue นี้
- DEV-115 และ DEV-116 ไม่อยู่ในขอบเขต cleanup เพราะ commits ยังไม่อยู่ใน `main`
- branch ทั้งสองถูกสำรองบน GitHub และ recovery ผ่าน DEV-130

## ผลการทำความสะอาด

ลบ worktree ที่ผ่าน working-tree และ ancestry gates:

- DEV-95
- DEV-99
- DEV-114
- DEV-118
- DEV-121

เก็บ DEV-115, DEV-116 และ DEV-128 เพราะเป็น recovery/active worktrees

## Acceptance Criteria

- [ ] `AGENTS.md` อ้าง `docs/superpowers/specs/` และไม่อ้าง path ที่ไม่มีอยู่
- [ ] DEV-115/DEV-116 และ remote backup branches ยังอยู่ครบ
- [ ] stale worktrees ที่ผ่าน safety gates ถูกลบโดยไม่ใช้ `--force`
- [ ] `git worktree list` เหลือเฉพาะ main และ active/recovery worktrees
- [ ] full repository verification ผ่าน
```

ห้ามเปลี่ยน DEV-115/DEV-116 เป็น Todo และห้ามย้าย DEV-128 เป็น Done ก่อน final gates ผ่าน

- [ ] **Step 2: รัน full repository gates จาก DEV-128 worktree**

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check 3b1e52c HEAD
git status --short
```

Expected: Python tests ผ่านอย่างน้อย 581 tests, Ruff/format/Mypy ผ่าน, docs ผ่าน 50 tests,
content check ผ่าน, exact-range diff check ไม่มี output และ worktree สะอาด

- [ ] **Step 3: Final operational verification จาก repository root**

```bash
git worktree list
git status -sb
git branch -r --contains 3a31823
git branch -r --contains 4573387
```

Expected:

- เหลือ main, DEV-115, DEV-116 และ DEV-128 worktrees
- `main` ตรงกับ `origin/main`
- remote branches ของ DEV-115 และ DEV-116 ยัง contain commits ที่สำรองไว้

- [ ] **Step 4: บันทึกผล verification ใน DEV-128**

เพิ่ม Linear comment ภาษาไทยสรุป tracked commit, worktree ที่ลบ, worktree ที่เก็บ,
DEV-130 link, test counts และ quality gates จากผลที่รันจริง

หลัง independent review ผ่านจึงย้าย DEV-128 เป็น Done โดยยังไม่ merge, push หรือลบ
DEV-128 branch/worktree จนกว่าผู้ใช้จะยืนยัน
