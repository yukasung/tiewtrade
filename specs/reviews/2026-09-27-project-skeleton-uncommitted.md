# Review: F-01 Project Skeleton — Uncommitted Changes

วันที่: 2026-09-27  
สถานะ: แก้ครบทั้ง 4 ประเด็นแล้ว 2026-09-27 — ด่านทั้งหมดเขียวรวม container  
ขอบเขต: การเปลี่ยนแปลงใน working tree เทียบกับ HEAD รวมไฟล์ใหม่ที่ยังไม่ tracked

ตรวจเทียบกับ [requirements](../features/2026-09-26-project-skeleton/requirements.md), [plan](../features/2026-09-26-project-skeleton/plan.md), [validation](../features/2026-09-26-project-skeleton/validation.md) และมาตรฐานใน `specs/standards/`

พบ 4 ประเด็นไม่ซ้ำกัน แยกผลตามมาตรฐานและความตรงตามสเปกด้านล่าง เลขบรรทัดอ้างถึงฉบับที่ตรวจและอาจเปลี่ยนหลังแก้โค้ด ผลรีวิวไม่ใช่การอนุมัติ merge

## Standards

### S-1 [P1] ตัวตรวจ core พลาดการอ่านเวลาผ่าน alias — ✅ แก้แล้ว 2026-09-27

ที่มา: [backend/tests/purity.py](../../backend/tests/purity.py) บรรทัด 105–115

ตัวตรวจเทียบชื่อการเรียกโดยไม่ติดตาม import จึงปล่อยโค้ดทั้งสองรูปแบบนี้ผ่าน:

```python
from datetime import datetime as dt

def now():
    return dt.now()
```

```python
from time import time

def now():
    return time()
```

**หลักฐาน:** ทดลอง parse โค้ดทั้งสองด้วย AST แล้วเรียก `_PurityVisitor` ทั้งสองกรณีคืนรายการข้อผิดพลาดว่าง (`[]`)

**ผลกระทบ:** โค้ดใน `core` อ่านเวลาปัจจุบันได้โดยด่านความบริสุทธิ์ไม่ปฏิเสธ ขัดกับ `standards/testing.md` หัวข้อ 3 และ RQ-7

**ข้อเสนอ:** ติดตามชื่อ import และ alias ในตัวตรวจ พร้อมเพิ่มกรณีทดสอบทั้งสองรูปแบบและกรณีถูกต้องคู่กัน

### S-2 [P2] เทสต์ import-linter ตรวจ config สำเนาแทนด่านจริง — ✅ แก้แล้ว 2026-09-27

ที่มา: [backend/tests/gates/test_gates.py](../../backend/tests/gates/test_gates.py) บรรทัด 185

เทสต์โหลด `.importlinter` ใน fixture แต่ CI ใช้ `backend/pyproject.toml` และเนื้อหาต่างกันแล้ว เช่น fixture ไม่มีข้อห้าม `fastapi` และ `uvicorn` ที่ config จริงมี

**หลักฐาน:** ตรวจเส้นทาง config ใน `_lint_imports()` และไฟล์ตั้งค่าของ fixture เทียบกับ `backend/pyproject.toml` เทสต์ import-linter ทั้งห้าผ่าน แต่เป็นผลของ config สำเนา

**ผลกระทบ:** หากกฎจริงถูกลบหรืออ่อนลง เทสต์ยังเขียวได้ จึงไม่พิสูจน์ว่าด่านที่ CI ใช้ยังทำงาน ขัดกับเงื่อนไขใน plan และ validation ที่กำหนดให้ใช้ชุดตั้งค่าเดียวกับด่านจริง และสร้าง config ซ้ำที่แยกจากกันได้

**ข้อเสนอ:** ใช้ config จริงร่วมกัน โดยเปลี่ยนเฉพาะตำแหน่ง source ที่ตรวจ และให้ทั้งกรณีผิดและกรณีถูกผ่านเส้นทางตั้งค่าเดียวกัน

### S-3 [P2] กฎห้าม core พึ่งไลบรารีภายนอกครอบคลุมเพียงบางชื่อ — ✅ แก้แล้ว 2026-09-27

ที่มา: [backend/pyproject.toml](../../backend/pyproject.toml) บรรทัด 80–88

รายการห้าม dependency ภายนอกครอบคลุม `fastapi`, `uvicorn`, `httpx` แต่ไม่ครอบคลุม dependency อื่น เช่น `pydantic` และตัวตรวจ purity ก็ไม่ได้ตรวจ external imports เพื่อปิดช่องนี้

**ผลกระทบ:** การ import เช่น `pydantic.BaseModel` ไม่อยู่ในรายการห้าม จึงยังบังคับกฎให้ `core` ใช้เฉพาะ standard library ไม่ครบ ขัดกับ `standards/architecture.md` หัวข้อ 1 และ RQ-4/RQ-6

**ข้อเสนอ:** ตรวจจากรายการที่อนุญาต หรือสร้างข้อห้าม dependency ภายนอกให้ครบโดยอัตโนมัติ แทนการเติมชื่อห้ามทีละไลบรารี พร้อมกรณีทดสอบ dependency ที่ไม่ได้ระบุในรายการเดิม

## Spec

### R-1 [P2] เทสต์ import-linter ไม่ใช้ชุดตั้งค่าเดียวกับด่านจริง — ✅ แก้แล้ว 2026-09-27 (ร่วมกับ S-2)

เป็นประเด็นเดียวกับ S-2 ข้างบน และขัดกับแผน/validation ที่อนุมัติโดยตรง: “รันด้วยชุดตั้งค่าเดียวกับด่านจริง ไม่ใช่ตั้งค่าพิเศษเฉพาะเทสต์” ให้แก้และปิดประเด็นร่วมกัน ไม่ต้องนับเป็นงานแยก

### R-2 [P2] Contract test ไม่ได้ตรวจโค้ดหน้าบ้านจริง — ✅ แก้แล้ว 2026-09-27

ที่มา: [frontend/tests/gates/api-contract.test.ts](../../frontend/tests/gates/api-contract.test.ts) บรรทัด 23 และ 58

เทสต์สร้าง `probe.ts` ขึ้นเองเพื่อใช้ `Health["status"]` แล้วรัน TypeScript ด้วย flags เฉพาะ แทนการตรวจ `src/api.ts` และ `App.tsx` ภายใต้ `tsconfig.json` จริง

**หลักฐาน:** เส้นทาง compile ในเทสต์อ้างเฉพาะ `probe.ts` ไม่มีการอ่านหรือคัดลอก source consumer และ tsconfig จริง ปัจจุบัน `api.ts` ใช้ generated types แล้ว แต่เทสต์นี้ไม่ได้ตรวจความสัมพันธ์ดังกล่าว

**ผลกระทบ:** เทสต์ยังผ่านได้แม้หน้าบ้านจริงเลิกใช้ generated types จึงไม่พิสูจน์ตาม P-10/V-16 ว่าเมื่อเปลี่ยนสัญญา API แล้ว typecheck ของหน้าบ้านจริงต้องแดง

**ข้อเสนอ:** ใช้สำเนา source และ config ของ frontend จริงในพื้นที่ชั่วคราว เปลี่ยน schema และสร้าง types ใหม่ แล้วรันคำสั่ง typecheck ของโปรเจกต์ ตรวจว่าแดงด้วยเหตุผลที่คาดหวัง และมีกรณีสัญญาเดิมที่ต้องผ่าน

## การตรวจที่รันแล้ว

- Backend: `.venv/bin/python -m pytest` จาก `backend/` — 21 tests ผ่าน มี deprecation warning 1 รายการ
- Frontend: `npm run test` จาก `frontend/` — 4 tests ผ่าน
- ทดลองตัวตรวจ AST กับการอ่านเวลาทั้งสองรูปแบบใน S-1 — ไม่พบ violation ทั้งสองกรณี

ไม่ได้รัน E2E หรือ Docker ในรอบนี้ ผลเทสต์ที่ผ่านยังไม่ปิดช่องว่างของด่านตรวจที่ระบุข้างต้น

## ส่งต่อให้ Claude Code

แก้ประเด็นทั้ง 4 ข้อโดยอ้างข้อกำหนดที่อนุมัติแล้ว เพิ่มกรณีทดสอบที่พิสูจน์ข้อผิดพลาดแต่ละข้อและรันด่านที่เกี่ยวข้อง จากนั้นบันทึกสถานะและหลักฐานสำหรับตรวจซ้ำ ก่อน merge ต้องผ่านด่านที่ repo และ validation กำหนดครบ

รวม Standards 3 ข้อ และ Spec 2 ข้อ โดยซ้ำกัน 1 ข้อ จุดสำคัญที่สุดของแต่ละด้านคือการตรวจนาฬิกาที่หลุดผ่าน และเทสต์ที่ไม่ได้ตรวจ config/source จริงตามแผน

---

## บันทึกการแก้ไข 2026-09-27

### S-1 ตัวตรวจ core พลาดการอ่านเวลาผ่าน alias

ยืนยันช่องโหว่ก่อนแก้ — ทั้ง `dt.now()` และ `from time import time; time()`
คืนรายการว่างจริง ตรงตามที่รีวิวระบุ

แก้ `backend/tests/purity.py` ให้ **ติดตาม import และ alias** เก็บ map ชื่อที่ใช้ในไฟล์
ไปเป็นชื่อเต็มจริง แล้วคลี่ก่อนเทียบกับรายการที่ห้าม `FORBIDDEN_CALLS`
เปลี่ยนคีย์เป็นชื่อเต็ม เช่น `datetime.datetime.now` แทน `datetime.now`

เพิ่มกรณีที่ต้องถูกปฏิเสธสองไฟล์: `purity_bad_clock_alias.py`,
`purity_bad_clock_direct_import.py` และกรณีที่ถูกต้อง `purity_good.py` ยังต้องผ่าน

### S-3 กฎห้าม core พึ่งไลบรารีภายนอกครอบคลุมเพียงบางชื่อ

เปลี่ยนจาก **รายการที่ห้าม** เป็น **รายการที่อนุญาต** ตัวตรวจใช้
`sys.stdlib_module_names` ตัดสินว่า import นั้นอยู่ใน standard library หรือไม่
อะไรที่ไม่อยู่ในนั้นและไม่ใช่ package ของโปรเจกต์เอง ถือว่าผิดทันที

วิธีนี้ไม่ต้องตามเติมชื่อทุกครั้งที่เพิ่ม dependency ใหม่
เพิ่มกรณีที่ต้องถูกปฏิเสธ `purity_bad_external_import.py` ซึ่งใช้ `pydantic`
ที่ไม่เคยอยู่ในรายการห้ามเดิม

### S-2 และ R-1 เทสต์ import-linter ใช้ config สำเนา

**ลบไฟล์ `.importlinter` ของ fixture ทั้งสองชุดออก** เทสต์รัน `lint-imports`
ด้วย `--config` ที่ชี้ไปที่ `backend/pyproject.toml` ตัวจริง แล้วใช้ `PYTHONPATH`
ชี้ source ไปที่ fixture

และ **อ่านชื่อกฎจาก `pyproject.toml` ด้วย `tomllib`** ไม่ประกาศชื่อซ้ำในเทสต์
ถ้ามีใครลบกฎออกจาก config จริง จำนวนกรณีทดสอบจะลดลงตามและกฎที่หายไป
จะไม่มีใครอ้างว่าทดสอบแล้ว

### R-2 Contract test ไม่ได้ตรวจโค้ดหน้าบ้านจริง

เขียน `frontend/tests/gates/api-contract.test.ts` ใหม่ ให้**คัดลอก source และ config
จริงของหน้าบ้าน** ไปที่โฟลเดอร์ชั่วคราว (`src/`, `tests/`, `e2e/`, `tsconfig.json`
และไฟล์ config อื่น) เชื่อม `node_modules` ชุดเดียวกันเพื่อให้เวอร์ชันเครื่องมือตรงกัน
สร้างชนิดข้อมูลจากสัญญาที่เปลี่ยนแล้ว จากนั้นรัน `tsc --noEmit -p tsconfig.json`
ด้วย config จริง

**พิสูจน์ว่าเทสต์ใหม่จับได้จริง** — แก้ `src/api.ts` ให้เขียนชนิดเองแทนการใช้ไฟล์ที่สร้าง
เทสต์แดงทันที (`ควรแดงเพราะช่อง status หายไป แต่ผ่าน`) แล้วเขียวคืนหลังคืนค่า
เทสต์ฉบับก่อนหน้าจะยังเขียวในสถานการณ์เดียวกัน ซึ่งคือช่องโหว่ที่รีวิวชี้

## ผลด่านหลังแก้

| ด่าน | ผล |
|---|---|
| ruff check, ruff format | เขียว |
| mypy strict | เขียว |
| import-linter 4 กฎ | เขียว |
| pytest | เขียว 24 เทสต์ (เพิ่มจาก 21) |
| eslint, tsc, vitest | เขียว |
| e2e (Playwright) | เขียว |
| สัญญา API สองฝั่งตรงกัน | เขียว |
| container (V-10) | เขียว — ตรวจแล้ว 2026-09-27 |

**V-10 ผ่านแล้ว** `docker compose up --build --wait` ขึ้นครบทั้งสอง container
healthcheck ผ่าน `/health` ตอบผ่าน container ได้ หน้าบ้านเสิร์ฟได้
เรียก API ผ่าน proxy ใน container ได้ และ e2e ยิงไปที่ container แล้วผ่าน
