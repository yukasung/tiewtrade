# Response: Review โครงสร้าง backend ของ TiewTrade

วันที่: 2026-09-23
ผู้ตอบ: Claude Code
อ้างอิง: [backend-structure-review.md](backend-structure-review.md) (Codex, 2026-09-23)
สถานะ: REV-01 แก้แล้วและทดสอบ end-to-end แล้ว · IMP-01 ทำแล้ว · **IMP-02 ทำแล้ว** (2026-09-23) · IMP-03–IMP-04 ยังเป็น **Proposed**  
ผ่าน re-review ของ Codex 2 รอบ พบรวม 6 findings — แก้ครบทั้งหมดแล้ว

เอกสาร review เดิมไม่ถูกแก้ไข

---

## 1. REV-01 — migration runbook

**สิ่งที่ทำ:** เพิ่ม [docs/runbooks/rename-compose-project.md](../runbooks/rename-compose-project.md)
และลิงก์จาก `README.md` §Local infrastructure พร้อมคำเตือนไม่ให้ทำตาม fresh setup
ถ้าเคยรัน project ชื่อ `fasttrade` มาก่อน

โครงสร้าง runbook: §0 อะไรเปลี่ยน · §1 fresh installation · §2 existing installation
(เลือกแนวทาง) · A/B/C สามแนวทาง · §3 optional rename database/role · §4 สถานะการทดสอบ

**สามแนวทางที่เสนอ:**

| แนวทาง | วิธี | ข้อมูล |
|---|---|---|
| **A** (แนะนำ) | `COMPOSE_PROJECT_NAME=fasttrade` ใน `deploy/.env` — คง project/volume/credentials เดิม | ไม่ย้ายเลย |
| **B** | `pg_dump --format=custom --no-owner --no-acl` → `down` (ไม่ใส่ `-v`) → project ใหม่ → `pg_restore` → verify | dump/restore |
| **C** | เริ่มใหม่ว่าง เก็บ volume เดิมเป็น safety net | ทิ้งของเดิม |

แนะนำ A เพราะไม่ต้อง copy ข้อมูล rollback คือลบบรรทัดเดียวออกจาก `.env` และไม่ต้องแก้
compose file ที่ commit ไว้ Phase 1 ยังไม่มี migrations/schema ดังนั้น C ก็มักเพียงพอ —
runbook §2.1 มีคำสั่งตรวจว่า volume เดิมมีตารางจริงไหมก่อนตัดสินใจ

**เกณฑ์ปิด finding:**

| เกณฑ์ | สถานะ |
|---|---|
| แยก fresh install กับ existing installation ชัดเจน | ✅ §1 vs §2; README ชี้ทางแยกไว้ |
| อธิบาย project name, volume name และ database/user เดิมกับใหม่ | ✅ ตารางใน §0 ครบทั้ง project/volume/network/DB/user |
| มีขั้นตอน backup/restore หรือยืนยันใช้ volume เดิม รวมถึง rollback | ✅ §B.1 backup + ตรวจ dump, §B.5 verify, rollback ครบทุกแนวทาง |
| ทดลองกับข้อมูลตัวอย่างใน environment ชั่วคราว | ✅ รัน A/B/C และ §3 ครบกับข้อมูลตัวอย่างใน Compose project ชั่วคราว (ดู §3) |

เกณฑ์ปิด finding ครบทั้ง 4 ข้อ

**ข้อจำกัดที่เคารพตามคำสั่ง:** ไม่มีคำสั่งลบ volume อัตโนมัติใน runbook (`down -v`, `volume rm`,
`volume prune` มีเฉพาะใน block คำเตือนว่าห้ามใช้ และใน rollback §B.6 ที่ระบุชัดว่าลบเฉพาะ
volume **ใหม่** อย่างตั้งใจ) · ทุกจุดที่แตะ `.env` เขียนว่า append หรือแก้ด้วยมือ ไม่มี
`cp .env.example .env` ทับของเดิม · ไม่ได้แตะ container, volume หรือ `.env` จริงระหว่างทำงานนี้

---

## 2. IMP-01 — เอกสารสถานะ implementation

**สิ่งที่ทำ:** เพิ่ม [docs/implementation-status.md](../implementation-status.md) และลิงก์จาก
README §Documentation

ยึดตามเกณฑ์รับของ review — ผู้อ่านรู้ได้ว่า API มีแค่ health endpoint และ service ใดยังไม่มี
runtime โดยไม่ต้องเปิดทุกไฟล์:

- นิยาม 3 สถานะ: Implemented / Scaffold / Planned
- ตาราง packages (core implemented บางส่วน; strategies, binance, infra เป็น scaffold)
- ตาราง `tiewtrade_core` แยกราย module พร้อม public API และไฟล์ test ที่ครอบคลุม
- ตาราง services — `api` มี `GET /api/v1/health` อย่างเดียว; อีก 5 ตัวเป็น scaffold ไม่มี runtime
- ตาราง Planned: `frontend/`, `proxy`/Caddyfile, migrations, integration tests
- ตาราง infrastructure/tooling

**ไม่เขียนกติกาซ้ำ:** เอกสารระบุชัดว่าหน้าที่และขอบเขตอยู่ที่ architecture §3/§10 และ ADR-0006
แล้วลิงก์ไปแทนการคัดลอก ตัวเอกสารตอบเฉพาะคำถาม "ตอนนี้อะไรรันได้จริง"

**อ้างอิงโค้ดจริง:** ทุกแถวลิงก์ไปไฟล์จริงใน `backend/` และตรวจกับ source แล้ว (ดู §3)
มีหัวข้อ "วิธีตรวจซ้ำ" ให้ reviewer รันเองได้

---

## 3. ผล verification

### 3.1 Backend checks (ไม่มีโค้ดเปลี่ยน — ยืนยันว่าไม่พัง)

| Check | ผล |
|---|---|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 35 files already formatted |
| `mypy` | ✅ no issues, 27 source files |
| `lint-imports` | ✅ 6 contracts kept, 0 broken |
| `pytest` | ✅ 62 passed (2 dependency deprecation warnings) |
| Link/anchor checker บนไฟล์ใหม่ทั้งหมด + README | ✅ ทุก relative link และ heading anchor ตรง |

### 3.2 ทดสอบ runbook end-to-end กับข้อมูลตัวอย่าง

ทำใน Compose project ชั่วคราว `ttmig-old` / `ttmig-new` บน port 55432/56379 ใช้สำเนาของ
`deploy/docker-compose.yml` ข้อมูลตัวอย่าง 2 ตาราง 5 แถว รวมคอลัมน์ `numeric(30,10)`
Docker Engine 29.7.2, `postgres:16-alpine`

ก่อนเริ่มตรวจแล้วว่าเครื่องนี้ **ไม่มี** project หรือ volume ชื่อ `fasttrade`/`tiewtrade` อยู่เลย
จึงไม่มีข้อมูลจริงของ repo นี้ให้กระทบ resource ที่สร้างระหว่างทดสอบถูกลบครบหลังจบ
(`docker volume ls | grep ttmig` → ว่าง) และ project `mattersolv` ของเครื่องไม่ถูกแตะ

| ขั้นตอน | ผล |
|---|---|
| แนวทาง A — `COMPOSE_PROJECT_NAME` override `name:` **ตอน runtime** | ✅ volume ที่สร้างจริงใช้ชื่อเดิม ทั้งที่ไฟล์ระบุชื่อใหม่ |
| project ใหม่ขึ้นมาพร้อม database ว่าง (ยืนยันคำเตือนของ Codex) | ✅ `Did not find any relations.` |
| B.1 `pg_dump --format=custom --no-owner --no-acl` + ตรวจ dump | ✅ `Format: CUSTOM`, TOC 18 entries |
| B.2 cold copy ทั้ง volume ด้วย `tar` หลังหยุด container | ⚠️ สร้างไฟล์ได้ **ยังไม่ทดสอบ restore** |
| B.2 `docker compose down` (ไม่ใส่ `-v`) ไม่ลบ volume | ✅ |
| B.4 `pg_restore` ผ่าน `exec -T` | ✅ exit 0 |
| B.5 ตาราง, row count, ค่า `numeric` ตรงทุกหลัก, owner ย้าย role ถูก | ✅ `1000.1234567890` ตรงเป๊ะ |
| B.5 sequence เดินต่อถูก | ✅ insert หลัง restore ได้ `id = 3` ไม่ชน |
| B.6 rollback | ✅ ข้อมูลเดิมครบ และ**ไม่มี**แถวที่เพิ่มใน project ใหม่ — พิสูจน์ว่า volume เดิมไม่ถูกแตะ |
| §3.1 `ALTER DATABASE ... RENAME` | ✅ |
| §3.2 rename role ด้วย superuser ชั่วคราว | ✅ password ใช้ได้ต่อหลัง rename |

### 3.3 ข้อผิดพลาดที่การทดสอบจับได้ (แก้ในเอกสารแล้ว)

การทดสอบจริงจับได้ 4 จุดที่ร่างแรกของ runbook เขียนไว้แล้วใช้งานไม่ได้ — ทั้งหมดแก้แล้ว
และบันทึกไว้ใน runbook §4 ด้วย:

1. `pg_restore --list /dev/stdin` ผ่าน `exec -T` **fail เสมอ** (`did not find magic string in
   file header`) เพราะ custom format ต้องการ input ที่ seek ได้ → เปลี่ยนเป็น container ชั่วคราว
   ที่ mount backup directory แบบ read-only
2. `ALTER ROLE fasttrade RENAME TO fasttrade...` จาก session ของ role ตัวเอง **fail** ด้วย
   `ERROR: session user cannot be renamed` และ image `postgres` มี superuser แค่ตัวเดียว →
   เพิ่มขั้นตอนสร้าง superuser ชั่วคราวแล้วลบทิ้ง (§3.2)
3. `pg_isready` **ไม่ใช่** ตัวยืนยัน database/user — ตอบ `accepting connections` แม้ `-U`/`-d`
   จะเป็นชื่อที่ไม่มีอยู่จริง healthcheck ใน compose จึงขึ้นเขียวได้ทั้งที่ credentials ผิด →
   เปลี่ยนตัวตรวจเป็น `psql` ทุกจุด
4. `$POSTGRES_USER` ไม่มีค่าใน shell ผู้ใช้ (Compose อ่าน `.env` เอง ไม่ export) →
   เปลี่ยนเป็นชื่อจริงในคำสั่ง

**รอบ re-review (Codex, gpt-6-astra) พบเพิ่มอีก 2 จุด — แก้แล้วทั้งคู่:**

5. **`tar` volume ขณะ PostgreSQL ยังรันอยู่ไม่ใช่ backup ที่เชื่อถือได้** — mount `:ro` กันแค่
   ไม่ให้ **tar** เขียน ไม่ได้หยุด **PostgreSQL** ที่กำลังเขียน data directory ได้ไฟล์ที่ไม่
   consistent และอาจ restore ไม่ขึ้นโดยไม่มีอะไรเตือน → ย้ายไปหลัง `docker compose down`
   ใน §B.2 เป็น cold copy พร้อมคำเตือน และแก้สถานะการทดสอบให้ตรงความจริง
6. **`backend/README.md` อ้างว่า order ที่ลด position ต้องการ margin เพิ่ม 0** ซึ่งไม่จริงเมื่อ
   `open_loss` ไม่เป็นศูนย์ ยืนยันด้วยโค้ดจริง: sell ที่ลด position ราคา 95 ขณะ Mark Price 100
   ได้ `order_margin = 5` ไม่ใช่ 0 → แก้ข้อความให้ตรง

**รอบ re-review ที่สอง (Codex, gpt-6-astra, effort high) พบอีก 4 จุด — แก้แล้วทั้งหมด:**

7. **`$STAMP` ถูกเขียนทับใน §B.2** ทำให้ §B.4 ชี้ไปยังชื่อไฟล์ dump ที่ไม่มีอยู่จริงเมื่อทำ
   ตามลำดับ → เปลี่ยน cold copy ไปใช้ `$VOLSTAMP` แยก และเพิ่มวิธีหาชื่อ dump จริง
   ถ้าเปิด shell ใหม่ **นี่เป็น bug ที่ผมสร้างขึ้นตอนแก้ข้อ 5**
8. **ตาราง §3.2 ของเอกสารนี้ยังให้เครดิต `tar` ว่า ✅** ทั้งที่ `Format: CUSTOM`/TOC ยืนยัน
   เฉพาะ `pg_dump` ขัดกับ runbook §4 ที่แก้ไปแล้ว → แยกเป็นแถวของตัวเองและใส่ ⚠️
9. **`backend/README.md:119` ยังเหมารวมว่า order ที่ลด position ไม่เพิ่ม margin requirement**
   ซึ่งยังไม่จริง การแก้รอบก่อนเพิ่มแค่ข้อยกเว้น `open_loss` ยืนยันด้วยโค้ด: Long 1,
   Mark Price 100, leverage 10, Sell 1 @ 300 ทำให้ requirement เพิ่ม **10 → 20** ทั้งที่
   `open_loss = 0` → แก้เป็น `order_margin` = ส่วนต่างของ requirement + `open_loss`
   และเตือนว่าอย่าเหมาว่าได้ 0 เสมอ
10. **`backend/README.md` เขียนกติกาซ้ำกับ specs** (Average Cost/fee, เงื่อนไข liquidation,
    กติกา order margin) → เปลี่ยนเป็นลิงก์ไป calculation §3.1 / §2.4 / §2.7

11. **docstring ของ `order_margin` ใน `requirement.py` ไม่ถูกต้อง** ด้วยเหตุผลเดียวกับข้อ 9 —
    ประโยค "Orders that reduce the position therefore need zero additional margin"
    ไม่จริง ไม่ใช่แค่เรื่อง `open_loss` แต่ margin requirement เองก็เพิ่มได้
    **แก้แล้วตามที่เจ้าของอนุมัติ** เปลี่ยนเฉพาะข้อความ docstring ไม่แตะสูตร
    ระบุกรณี TP sell ที่ราคาไกลจาก Mark Price ไว้ชัด และเตือนว่า caller ต้องใช้ค่าที่
    ฟังก์ชันคืน ไม่ใช่สมมติว่าเป็นศูนย์
    ยืนยันด้วย `git diff`: บรรทัดที่ execute ได้ไม่เปลี่ยน (นอกจาก import rename ที่มีอยู่เดิม)
    และ pytest 62 tests ยังผ่าน

ข้อ 2 ยังแก้ความเข้าใจเดิมเรื่อง password ด้วย: PostgreSQL 16 default เป็น `scram-sha-256`
password จึง**ไม่ถูกล้าง**หลัง rename — ข้อจำกัดนั้นมีเฉพาะ `md5` runbook ระบุวิธีตรวจของตัวเองไว้แล้ว

### 3.4 ข้อความใน implementation-status ที่ตรวจกับโค้ดจริง

10 workspace members (`packages/*`, `services/*`) · `testpaths = ["packages", "services"]` ·
import-linter 6 contracts · mypy `strict = true` สำหรับ `tiewtrade_core.*` และ
`tiewtrade_strategies.*` · ไม่มี `main.py` ที่ใดเลย · ทุก package/service ที่ระบุว่า scaffold
มีเพียง `__init__.py` + `py.typed` · `frontend/`, `deploy/Caddyfile`, `backend/migrations/`,
`backend/tests/` ไม่มีจริง

### 3.5 ยังไม่ได้ทดสอบ

| รายการ | เหตุผล |
|---|---|
| ย้ายข้อมูลขนาดใหญ่ (หลาย GB) | ข้อมูลตัวอย่างเล็ก เวลาจริงจะนานกว่ามาก |
| Volume ที่มี extension, custom role หรือหลาย schema | ตัวอย่างใช้ `public` schema ล้วน |
| restore ข้าม PostgreSQL major version | ทดสอบใน `postgres:16-alpine` เท่านั้น |

---

## 4. ไฟล์ที่เปลี่ยน

| ไฟล์ | ประเภท |
|---|---|
| `docs/runbooks/rename-compose-project.md` | ใหม่ — REV-01 |
| `docs/implementation-status.md` | ใหม่ — IMP-01 |
| `docs/reviews/backend-structure-response.md` | ใหม่ — เอกสารนี้ |
| `README.md` | แก้ — เพิ่ม 2 ลิงก์และคำเตือน migration (บรรทัดที่มีอยู่เดิมไม่ถูกแตะ) |

ไม่แตะ trading logic, `backend/**`, `deploy/**`, `docs/architecture/**`, `docs/specs/**`,
`docs/requirements/**` และไม่แก้ `backend-structure-review.md`
งานที่ยังไม่ commit (rename `fasttrade` → `tiewtrade`) อยู่ครบ ไม่ได้ commit หรือ push

---

## 5. ที่ยังค้าง

2. **IMP-03** integration test discovery + ownership ของ migrations — ทำเมื่อมี persistence งานแรก
3. **IMP-04** ขอบเขต Paper execution กับ Live gateway — ทำเมื่อเริ่ม execution features
4. **ทดสอบ restore จาก cold copy (`tar`) ใน §B.2** — ตอนนี้ทดสอบแค่ว่าสร้างไฟล์ได้
5. ข้อจำกัดการทดสอบที่เหลือใน §3.5 (ข้อมูลขนาดใหญ่, extension/schema ซับซ้อน, ข้าม major version)

IMP-03 และ IMP-04 ยังเป็น **Proposed** ตามขอบเขตที่ตกลงไว้

## 6. IMP-02 — ปิดแล้ว (2026-09-23)

เกณฑ์รับที่ Codex เขียนไว้: *"ตัวอย่างอ่าน clock/network/file หรือสร้าง random ID ใน core ถูกตรวจพบ
ขณะที่ deterministic code และการรับ time/ID จาก caller ยังผ่าน"*

ทำด้วย [`test_core_purity.py`](../../backend/packages/core/tests/test_core_purity.py) ซึ่งอ่าน AST
ของทุกไฟล์ใน core แล้วบังคับ 4 ข้อ:

| กฎ | ทำไม |
|---|---|
| ฟังก์ชันที่ทำเลขคณิตต้องอยู่ใน `@calc` | ถูกลืมมาแล้ว 2 ครั้ง ทั้งคู่หลุด review ไปรอบถัดไป |
| ห้าม import `time`, `datetime`, `random`, `uuid`, `os`, `pathlib`, `socket` | ADR-0001: เวลาและ ID มาจาก caller |
| ห้ามเรียก `open`, `print`, `eval`, `exec` | ไม่มี I/O ใน core |
| ห้ามใช้ `float` | เงินต้องเป็น `Decimal` |

ตรงตามเกณฑ์: `datetime` ที่รับ**เป็นพารามิเตอร์**จาก caller ยังผ่าน เพราะตรวจที่ import ไม่ใช่ที่ type

**ยืนยันด้วย mutation test 5 แบบ** — ลืม `@calc`, `import random`, `from datetime import`,
`print()`, `quantity: float` → แดงทุกตัว

เพิ่ม **import-linter layers contract** ด้วย (7 contracts แล้ว) บังคับลำดับชั้นภายใน core ตาม
architecture §4.2: `execution` → `orders` → `margin` → `portfolio` → `market` → `_decimal`
ก่อนหน้านี้เหตุผลที่วาง `LiquidityRole` ไว้ `market/` บังคับด้วย review เท่านั้น
