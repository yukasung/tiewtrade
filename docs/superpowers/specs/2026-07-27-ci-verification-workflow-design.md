# DEV-121 CI Verification Workflow Design

**Date:** 2026-07-27
**Status:** Approved for implementation planning
**Scope:** GitHub Actions verification for Python application changes

## Goal

เพิ่ม GitHub Actions workflow ที่ตรวจโค้ดทุก Pull Request ซึ่งมีเป้าหมายเป็น `main` และทุกครั้งที่มีการ push เข้า `main` เพื่อป้องกันไม่ให้การเปลี่ยนแปลงที่ไม่ผ่าน verification checklist ของ repository เข้าสู่ branch หลัก

งานนี้เพิ่มเฉพาะ CI configuration, contract test และคำอธิบาย verification ใน `AGENTS.md` โดยไม่เปลี่ยน production code, trading behavior, database schema หรือ `docs-site`

## Current Gap

ปัจจุบัน verification checklist ถูกเรียกใช้จากเครื่องนักพัฒนา แต่ repository ยังไม่มี `.github/workflows/verify.yml` จึงไม่มีตัวตรวจอัตโนมัติที่เป็นมาตรฐานเดียวกันบน GitHub ก่อน merge

นอกจากนี้ `git diff --check` บน clean checkout ไม่มี working-tree diff ให้ตรวจ จึงไม่สามารถใช้คำสั่งแบบ local ตรง ๆ ใน CI ได้ CI ต้องตรวจ committed range ระหว่าง base commit กับ `HEAD` แทน

## Workflow Boundary

ใช้ workflow เดียวและ job เดียวชื่อ `verify` เพราะทั้งห้า check ใช้ environment และ dependency ชุดเดียวกัน การแยกเป็นหลาย jobs หรือ matrix จะเพิ่มเวลาติดตั้งและความซับซ้อนโดยยังไม่มีประโยชน์ต่อขอบเขตปัจจุบัน

ไฟล์ที่อยู่ในขอบเขต:

- `.github/workflows/verify.yml` — GitHub Actions workflow
- `tests/unit/test_ci_workflow.py` — contract test สำหรับ requirement สำคัญของ workflow
- `pyproject.toml` — ขอบเขตไฟล์ที่ Ruff format และ lint ตรวจ
- `AGENTS.md` — แยกความหมายของ whitespace check ระหว่าง local checkout และ CI

ไฟล์ที่ไม่อยู่ในขอบเขต:

- production modules ใต้ `src/`
- `docs-site` build, lint หรือ tests
- deployment, release หรือ packaging workflow
- Live Binance connectivity, credentials หรือ secrets

## Triggers

Workflow ทำงานเมื่อ:

1. มี Pull Request ที่ target `main` เมื่อเปิด, push commit ใหม่, เปิดใหม่ หรือเปลี่ยน target branch (`opened`, `synchronize`, `reopened`, `edited`)
2. มีการ push เข้า `main`

ไม่เรียก workflow จากทุก feature-branch push เพื่อลดการรันซ้ำ เพราะ branch ที่มี Pull Request จะถูกตรวจผ่าน `pull_request` event อยู่แล้ว

## Runtime and Security

Job ใช้ค่าต่อไปนี้:

- runner: `ubuntu-latest`
- timeout: `10` นาที
- repository permission: `contents: read`
- Python: `3.12`
- environment:
  - `PYTHONPATH=src`
  - `QT_QPA_PLATFORM=offscreen`

Workflow ไม่ใช้ GitHub secrets และไม่เชื่อม Binance การกำหนด `QT_QPA_PLATFORM=offscreen` ทำให้ UI tests ทำงานบน runner ที่ไม่มีจอแสดงผลโดยไม่เปลี่ยน behavior ของ application

GitHub Actions run `30287870327` พบว่า pytest-qt import `PySide6.QtGui` ไม่ได้เพราะไม่มี `libEGL.so.1` บน Ubuntu runner จึงติดตั้ง `libegl1` ซึ่งเป็น package ที่ให้ runtime library นี้เท่านั้น ไม่ติดตั้ง X11 package เพิ่มเติมโดยไม่มีหลักฐานว่าจำเป็น

## Actions and Dependency Installation

Workflow ใช้:

- `actions/checkout@v6` พร้อม `fetch-depth: 0` เพื่อให้ base commit ที่ใช้ตรวจ committed range มีอยู่ใน checkout
- step `Install Qt runtime libraries` รัน `sudo apt-get update` และ `sudo apt-get install --yes libegl1` หลัง checkout และก่อน Python setup/dependency use
- `actions/setup-python@v6` พร้อม pip cache และ `cache-dependency-path: pyproject.toml`
- `python -m pip install -e ".[dev]"` เพื่อติดตั้ง application และ verification tools จาก Source of Truth เดียวกัน

การ pin ที่ major version ทำให้รับ patch fixes ของ official actions โดยไม่กระโดดข้าม breaking major version

## Verification Sequence

Job เรียก checks ตามลำดับเดียวกันและหยุดทันทีเมื่อคำสั่งใดล้มเหลว:

```text
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
git diff --check "$BASE_SHA" HEAD
```

ไม่มี `continue-on-error` เพราะทุก check เป็น merge requirement

## Ruff Formatter Scope

GitHub Actions run `30288239088` ผ่าน Pytest หลังแก้ Qt EGL แต่ `python -m ruff format --check .` ล้มเหลว เพราะ CI ติดตั้ง Ruff `0.16.0` ซึ่งตรวจ Markdown เก่า 10 ไฟล์ ขณะที่ venv local ใช้ Ruff `0.15.22` จึงไม่แสดงปัญหาเดียวกัน

ตั้งค่า `[tool.ruff]` เป็น `extend-exclude = ["*.md"]` เพื่อกำหนด formatter และ linter ใน workflow นี้ให้ตรวจเฉพาะไฟล์ที่อยู่ในขอบเขต Python โดยไม่ pin Ruff, ไม่แก้ Markdown เดิม และไม่เปลี่ยน workflow command. การ reproduce แบบ isolated ด้วย Ruff `0.16.0` ต้องรายงาน `115 files already formatted`.

## Committed-Range Whitespace Check

CI กำหนด `BASE_SHA` ตาม event:

- Pull Request: `${{ github.event.pull_request.base.sha }}`
- push เข้า `main`: `${{ github.event.before }}`

จากนั้นใช้ `git diff --check "$BASE_SHA" HEAD` เพื่อตรวจ whitespace errors ที่ถูก commit ในช่วงการเปลี่ยนแปลงจริง ส่วนการตรวจบนเครื่องนักพัฒนายังคงใช้ `git diff --check` เพื่อตรวจ working-tree changes ก่อน commit

`fetch-depth: 0` เป็นข้อกำหนดของแนวทางนี้ เพราะ shallow checkout อาจไม่มี base commit ที่ต้องใช้เปรียบเทียบ

## Workflow Contract Test

เพิ่ม `tests/unit/test_ci_workflow.py` เพื่ออ่าน workflow เป็น text โดยไม่เพิ่ม YAML dependency ใหม่ และตรวจ complete YAML blocks ที่ repository ควบคุมได้ ได้แก่:

- trigger สำหรับ push ที่ `main` และ Pull Request ที่ `main` โดยมี `types: [opened, synchronize, reopened, edited]`
- `permissions`, job runtime และ job environment block
- checkout, Python setup และ dependency-installation blocks
- Qt EGL runtime installation block ที่ติดตั้งเฉพาะ `libegl1`
- ค่า `config["tool"]["ruff"]["extend-exclude"] == ["*.md"]` จาก `pyproject.toml` โดยใช้ stdlib `tomllib`
- verification sequence ทั้งห้ารายการ รวมถึง `BASE_SHA` expression แบบ exact และ whitespace check แบบ base-to-HEAD committed range

Contract test ไม่แทน GitHub Actions parser หรือ runner การรันจริงบน GitHub หลัง push ยังคงเป็น final integration verification

## Documentation Alignment

ปรับหัวข้อ Verification ใน `AGENTS.md` ให้ชัดเจนว่า:

- local verification ใช้ `git diff --check` สำหรับ uncommitted changes
- GitHub Actions verification ใช้ `git diff --check <base> HEAD` สำหรับ committed range

คำสั่ง Python อีกสี่รายการใน workflow ต้องตรงกับ tools ที่กำหนดใน `pyproject.toml`

## Failure Behavior and Completion Gate

หาก setup หรือ check ใดล้มเหลว job ต้องเป็น failed และป้องกันการสรุปว่า DEV-121 เสร็จ

DEV-121 จะย้ายเป็น `Done` ได้เมื่อครบทุกข้อ:

1. contract test และ verification suite ผ่านใน local worktree
2. workflow ถูก push ไป GitHub หลังได้รับคำยืนยันจากผู้ใช้
3. GitHub Actions run ของ branch หรือ Pull Request ผ่านจริง
4. ไม่มี production code changes ใน diff

เนื่องจาก GitHub Actions ตรวจ workflow ได้สมบูรณ์หลัง push เท่านั้น Issue ต้องคงสถานะ `In Progress` จนกว่าจะยืนยันผล run สีเขียว

## Verification Strategy

ระหว่าง implementation ใช้ TDD ตามลำดับ:

1. เพิ่มหรือยกระดับ contract test และยืนยันว่า test ล้มเหลวเพราะ workflow ยังไม่มี behavior ที่ต้องการ
2. เพิ่ม workflow ขั้นต่ำให้ contract test ผ่าน
3. ปรับ `AGENTS.md` ให้ตรงกับ behavior ที่ implement
4. รัน Python unit/integration tests, Ruff lint, Ruff format check, Mypy และ `git diff --check`
5. หลังได้รับอนุญาตให้ push ให้ตรวจ GitHub Actions run ก่อนปิด Issue

## Risks and Mitigations

- **Action/runtime incompatibility:** ใช้ official `actions/*@v6` และ Python 3.12 ตาม project support
- **UI tests fail เพราะไม่มี display:** กำหนด `QT_QPA_PLATFORM=offscreen` ระดับ job
- **Base commit หาไม่พบ:** ใช้ `fetch-depth: 0`
- **CI และ local checklist ไม่ตรงกัน:** มี contract test และปรับ `AGENTS.md` ระบุคำสั่งทั้งสองบริบท
- **Workflow scope ขยายเกิน Issue:** ไม่รวม docs-site, deployment, Live connectivity หรือ production refactor
