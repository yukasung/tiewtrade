# Review: โครงสร้าง backend ของ TiewTrade

วันที่: 2026-09-23  
Reviewer: Codex  
สถานะ: Review เสร็จ — พบ 1 ประเด็นด้านการย้าย local infrastructure; ข้อเสนอเพิ่มเติมยังเป็น **Proposed**

## ขอบเขตและหลักฐาน

- ตรวจ working tree รวม staged และ unstaged changes ด้วย `git diff HEAD` เทียบ commit `3eaeff2fde5c3624507cadbf92461c888fd2a52a`
- อ้างอิงโครงสร้างที่ตกลงในบทสนทนา, `docs/architecture/architecture.md` §4/§10/§11, ADR-0001 และ ADR-0006 รวมถึงกติกาที่บันทึกใน repository ปัจจุบัน
- ไม่พบ `docs/plans/backend-structure.md` ณ เวลาตรวจ จึงไม่ได้อ้างว่า implementation ผ่าน acceptance criteria จากไฟล์แผนดังกล่าว
- ตรวจ metadata ของทั้ง 10 workspace members, import paths, wheel paths, lockfile diff, CI และ deploy config
- เปรียบเทียบไฟล์ backend เดิมกับไฟล์ใหม่หลังแทน `fasttrade` ด้วย `tiewtrade`: ไฟล์เดิมที่จับคู่ได้ทั้งหมดนอกจาก `uv.lock` ไม่มีความต่างอื่น; lockfile ตรวจแยกจาก diff
- งาน review นี้ไม่แก้ implementation, Git remote, containers หรือข้อมูลในฐานข้อมูล และไม่ commit/push

## ผลประเมินโครงสร้าง

โครงสร้างปัจจุบันเหมาะสำหรับพัฒนาต่อ ไม่จำเป็นต้องรื้อใหม่ การแยก `packages/` และ `services/` มีอยู่ใน baseline แล้ว; diff รอบนี้เป็นการ rename ให้สอดคล้องกับชื่อ TiewTrade เป็นหลัก

```text
backend/
├── pyproject.toml
├── uv.lock
├── packages/
│   ├── core/
│   │   ├── pyproject.toml
│   │   ├── src/tiewtrade_core/
│   │   │   ├── market/
│   │   │   ├── portfolio/
│   │   │   └── margin/
│   │   └── tests/
│   ├── strategies/
│   │   ├── pyproject.toml
│   │   └── src/tiewtrade_strategies/
│   ├── binance/
│   │   ├── pyproject.toml
│   │   └── src/tiewtrade_binance/
│   └── infra/
│       ├── pyproject.toml
│       └── src/tiewtrade_infra/
└── services/
    ├── api/          # pyproject.toml + src/tiewtrade_api/ + tests/
    ├── engine/       # pyproject.toml + src/tiewtrade_engine/
    ├── market_data/  # pyproject.toml + src/tiewtrade_market_data/
    ├── execution/    # pyproject.toml + src/tiewtrade_execution/
    ├── jobs/         # pyproject.toml + src/tiewtrade_jobs/
    └── notifier/     # pyproject.toml + src/tiewtrade_notifier/
```

| ส่วน | สถานะที่ตรวจพบ | ขอบเขตที่ควรรักษา |
|---|---|---|
| `core` | มี market, portfolio, margin และ unit/property tests | กฎธุรกิจและ Decimal calculations แบบ pure |
| `strategies` | Scaffold | สร้าง Order Intent; ขึ้นกับ core |
| `binance` | Scaffold | Exchange client และการแปลง payload |
| `infra` | Scaffold | Persistence, messaging และ infrastructure adapters |
| `api` | มี health endpoint และ test | HTTP/WebSocket boundary; ประกอบ dependencies |
| `engine` | Scaffold | ประสาน Strategy, Risk, Order Manager และ Paper execution |
| `market_data` | Scaffold | รับและเผยแพร่ข้อมูลตลาด |
| `execution` | Scaffold สำหรับ Phase 2 | Live gateway และการเข้าถึง credentials |
| `jobs`, `notifier` | Scaffold | งานตามเวลาและการส่งแจ้งเตือน |

การมีครบหก service directories ยังไม่ได้หมายความว่ามี trading processes ที่รันได้ครบทั้งหมด และไม่ถือว่าฟีเจอร์อนาคตที่ยังไม่มีเป็นข้อบกพร่องของ structural refactor นี้

## Standards

**0 findings ที่เกิดจาก diff นี้**

- Package names, imports, wheel configuration และ import-linter contracts เปลี่ยนชื่อสอดคล้องกัน
- ไม่พบการเพิ่ม I/O หรือการเปลี่ยนสูตรคำนวณใน core จากการ rename
- การเปลี่ยนชื่อใน Accepted ADRs ไม่ได้เปลี่ยนสาระของ architectural decisions
- ไม่พบ code smell ที่มีผลมากพอจะต้องแก้ในงานนี้

ข้อเสนอเรื่องความครอบคลุมของ architecture checks อยู่ในส่วน Proposed ด้านล่าง ไม่ใช่ regression

## Spec

**1 finding — P2**

### REV-01: เพิ่มขั้นตอนย้าย local infrastructure เมื่อเปลี่ยนชื่อ Compose project

**ตำแหน่ง:** `deploy/docker-compose.yml:3` และ `README.md:33–38`  
**เงื่อนไข:** ผู้พัฒนาเคยรัน Compose project ชื่อเดิมแล้ว และไม่ได้ override project name

การเปลี่ยน `name: fasttrade` เป็น `name: tiewtrade` เปลี่ยนทั้ง identity ของ Compose project และชื่อ default PostgreSQL volume เนื่องจาก `postgres-data` ไม่ได้กำหนดชื่อภายนอกตายตัว

ยืนยันด้วย `docker compose config --format json` โดยใช้ password placeholder และ `--env-file /dev/null`:

| Project | Volume ที่ resolve ได้ |
|---|---|
| ชื่อเดิม | `fasttrade_postgres-data` |
| ชื่อใหม่ | `tiewtrade_postgres-data` |

ผลที่เกิดได้:

- ถ้า stack เดิมยังทำงานอยู่ stack ใหม่จะชน published ports เดิม
- ถ้าหยุด stack เดิมแล้วเปิดชื่อใหม่ PostgreSQL จะใช้ volume ใหม่และเริ่มฐานข้อมูลว่าง
- ข้อมูลเดิมยังอยู่ใน volume เดิม **ไม่ได้ถูกลบ** แต่ไม่มีขั้นตอนย้ายตาม README ปัจจุบัน
- การเปลี่ยน `POSTGRES_DB` / `POSTGRES_USER` ใน config ไม่ใช่ขั้นตอนเปลี่ยนชื่อ database/role ที่ initialize ไปแล้ว

นี่เป็นผลต่อ environment ที่มีอยู่เดิมจากงาน rename ซึ่งควรมีคำอธิบายก่อนถือว่าส่งต่องานเสร็จ

**แนวทางแก้ที่เสนอ:** เพิ่ม migration runbook แยกจาก fresh setup ให้เลือกแนวทางตามข้อมูลที่ต้องเก็บ:

1. คง identity/volume/credentials เดิมระหว่างเปลี่ยนชื่อ application; หรือ
2. สำรองข้อมูล หยุด project เดิมโดยไม่ลบ volumes เริ่ม project ใหม่ แล้ว restore และตรวจสอบข้อมูล

อย่าสร้างคำสั่งลบ volume อัตโนมัติ และอย่า overwrite `.env` เดิมเป็นส่วนหนึ่งของขั้นตอน upgrade ให้ตรวจค่าที่ใช้อยู่ก่อน

**เกณฑ์ปิด finding:**

- [ ] เอกสารแยก fresh install กับ existing installation ชัดเจน
- [ ] อธิบาย project name, volume name และ database/user เดิมกับใหม่
- [ ] มีขั้นตอนตรวจ backup/restore หรือยืนยันการใช้ volume เดิม รวมถึง rollback
- [ ] ทดลองขั้นตอนที่เลือกกับข้อมูลตัวอย่างใน environment ชั่วคราว และบันทึกผล

Reviewer ตรวจเฉพาะการ resolve config ไม่ได้รัน migration กับฐานข้อมูลของผู้ใช้

## ข้อเสนอปรับปรุง — Proposed

ส่วนนี้เป็นข้อเสนอ ไม่ใช่ข้อกำหนดที่อนุมัติแล้ว และไม่ใช่เงื่อนไขให้ต้องสร้างทุกโมดูลก่อนจบงาน rename

### IMP-01: บันทึกสถานะ implementation และขอบเขตงานส่งต่อ

**ควรทำในรอบเอกสารถัดไป**

เพิ่มตารางสถานะสั้น ๆ ในเอกสารที่มีอยู่ หรือแผนงานเฉพาะ task เพื่อแยก scaffold, implemented และ planned พร้อม acceptance criteria ที่ชัดเจน ใช้ architecture เป็น source of truth และลิงก์อ้างอิงแทนการคัดลอกกติกาหลายชุด

**เกณฑ์รับ:** ผู้อ่านระบุได้ว่าปัจจุบัน API มีเพียง health endpoint และบริการใดยังไม่มี runtime โดยไม่ต้องเปิดทุกไฟล์

### IMP-02: เพิ่มการตรวจ core purity ให้ครอบคลุมขึ้น

**ทำเมื่อขยาย core; ไม่จำเป็นต้องบล็อก rename**

ที่ `backend/pyproject.toml:96–105` import-linter ห้าม framework และ packages ที่ระบุไว้ แต่ไม่ได้พิสูจน์ว่าไม่มี filesystem access, clock reads หรือ randomness ทั้งหมด เช่น `open()` หรือ `datetime.now()`

พิจารณาเพิ่ม static checks ที่เจาะจง API ต้องห้าม พร้อมตัวอย่างที่ควรผ่านและควรไม่ผ่าน ระวังไม่ห้าม type import ที่จำเป็น เช่น `datetime` สำหรับค่าที่ caller ส่งเข้ามา

**เกณฑ์รับ:** ตัวอย่างอ่าน clock/network/file หรือสร้าง random ID ใน core ถูกตรวจพบ ขณะที่ deterministic code และการรับ time/ID จาก caller ยังผ่าน

### IMP-03: เพิ่ม integration test discovery พร้อม persistence งานแรก

**ทำเมื่อมี integration tests จริง**

`backend/pyproject.toml:84` มี `testpaths = ["packages", "services"]` หากเพิ่ม `backend/tests/integration/` หรือ `backend/tests/e2e/` ภายหลัง ต้องเพิ่ม path ใน pytest configuration พร้อม markers และ infrastructure setup ใน CI

เลือก ownership ของ migrations ให้ชัดเจนในงาน persistence แรก เช่น `backend/migrations/` โดยยังไม่ต้องสร้าง directory ว่างตอนนี้

**เกณฑ์รับ:** `pytest --collect-only` และ CI เก็บ tests ใหม่ได้จริง; migration ของ schema ที่เพิ่มมีผลทดสอบตามขอบเขตงาน

### IMP-04: รักษาขอบเขต Paper execution และ Live gateway

**ทำเมื่อเริ่ม execution features**

ตาม ADR-0001 และ architecture §4.3 กฎ Paper fills เป็น pure computation ใน core และ engine เป็นผู้เรียกใช้ ส่วน `services/execution` คือ Live gateway สำหรับ Phase 2

เมื่อสร้างโมดูลเหล่านี้ ควรระบุหน้าที่ใน module docstring และ tests ให้ชัด เพื่อป้องกันการวาง network/credentials ลง core หรือย้าย Paper flow ไปผูกกับ Live service

เพิ่ม `main.py`, bootstrap และ settings เมื่อ service เริ่มมี lifecycle จริง จัดภายในตาม domain/use case และไม่จำเป็นต้องสร้าง layers เหมือนกันทุก service

**เกณฑ์รับ:** Paper flow ทดสอบได้โดยไม่มี Binance credentials และ services ไม่ import implementation ของกันและกัน

## ผล verification

| Check | ผล |
|---|---|
| Ruff lint | ผ่าน |
| Ruff format | ผ่าน — 35 files |
| mypy | ผ่าน — 27 source files |
| import-linter | ผ่าน — 6 contracts, 0 broken |
| pytest | ผ่าน — 62 tests |
| Backend rename comparison | ไม่พบความต่างอื่นในไฟล์เดิมที่จับคู่ได้ หลัง normalize ชื่อ; ยกเว้น lockfile ที่ตรวจแยก |
| Compose config | ยืนยันว่า project rename เปลี่ยน default volume name |

คำสั่ง checks ใช้จาก `backend/`:

```sh
UV_CACHE_DIR=/private/tmp/fasttrade-review-uv uv run --frozen ruff check .
UV_CACHE_DIR=/private/tmp/fasttrade-review-uv uv run --frozen ruff format --check .
.venv/bin/python -m mypy --cache-dir=/private/tmp/tiewtrade-review-mypy --show-traceback
UV_CACHE_DIR=/private/tmp/fasttrade-review-uv uv run --frozen lint-imports --no-cache
UV_CACHE_DIR=/private/tmp/fasttrade-review-uv uv run --frozen pytest
```

ข้อจำกัดของ environment: sandbox ยังอ้าง writable root ชื่อเก่า จึงเขียน cache ใน directory ชื่อใหม่ไม่ได้ การรัน mypy/import-linter ครั้งแรกติดสิทธิ์ cache และผ่านเมื่อย้าย cache ไป `/private/tmp` หรือปิด cache แล้ว pytest ใช้ Hypothesis database ใน memory และเขียน pytest cache ไม่ได้ แต่ tests ผ่านทั้งหมด มี dependency deprecation warnings จาก FastAPI/Starlette เพิ่มเติม ชื่อเก่าใน temporary UV cache path เป็นเพียง cache ของการ review

ไม่ได้ทำ clean install ใน environment ใหม่, build Docker images, ทดสอบ migration จริง หรือยืนยัน CI บน remote ดังนั้นผลนี้ไม่ใช่การรับรอง deployment readiness

## ข้อความส่งต่อให้ Claude Code

```text
อ่าน docs/reviews/backend-structure-review.md แล้วจัดการ REV-01 ก่อน
เพิ่มเอกสาร migration สำหรับ existing local infrastructure และวิธีตรวจสอบผล
อย่าเปลี่ยนหรือลบฐานข้อมูล/volume ของผู้ใช้ และอย่า overwrite .env
ถ้าต้องเลือกนโยบายเก็บข้อมูลที่ยังไม่ชัด ให้เสนอทางเลือกก่อนลงมือกับ environment จริง

IMP-01 ถึง IMP-04 เป็น Proposed: เสนอ scope งานถัดไป ไม่ต้อง implement ทั้งหมดในรอบนี้
รักษางานที่ยังไม่ commit และอย่า commit/push
เมื่อเสร็จ รายงานรายการไฟล์ที่เปลี่ยน หลักฐาน verification และข้อที่ยังไม่ทำ
ให้ Codex review diff ซ้ำ โดยไม่แก้ผล review เดิมเพื่อทำให้ finding ดูเหมือนผ่าน
```

ผลแยกตามแกน: Standards 0 findings; Spec 1 finding ระดับ P2 — ขั้นตอนย้าย local infrastructure หลังเปลี่ยนชื่อ Compose project
