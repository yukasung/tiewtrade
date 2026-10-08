# TiewTrade

Web application สำหรับเทรดคริปโตบน Binance TH แบบหลายผู้ใช้
รองรับทั้งการสั่งออเดอร์เองและบอทเทรดตามกลยุทธ์สำเร็จรูป มีทั้ง Paper Trading
และ Live Trading

สถานะงานปัจจุบันอ่านจาก [`specs/roadmap.md`](specs/roadmap.md) — ยังไม่มีความสามารถด้านการเทรด
เอกสารทั้งหมดอยู่ใน [`specs/`](specs/) — อ่าน [`specs/README.md`](specs/README.md) ก่อน

---

## ต้นฉบับ UI template

[`references/admin-template/`](references/admin-template/) เก็บ TailAdmin Pro React
ที่เจ้าของเลือกใช้เป็นต้นฉบับ UI; source ที่นำมาปรับใช้จริงอยู่ใน `frontend/src/`
ไม่รันหรือ import แอปจาก references และไม่คัดลอก demo data/auth หรือ package.json
ทับโปรเจกต์ ก่อนนำ component/assets มาใช้ให้ตรวจเงื่อนไข license ที่มากับการซื้อ

แผนการปรับใช้และ dependency ที่เสนออยู่ใน
[F-08 plan.md](specs/features/2026-10-07-single-trading-account/plan.md) และ
[validation.md](specs/features/2026-10-07-single-trading-account/validation.md)
หน้าจัดการบัญชี/key/ประเภทการใช้งานปรับใช้ layout/component ที่เลือกจากต้นฉบับแล้ว
ใช้ React/Vite เดิมร่วมกับ Tailwind 4 โดยไม่ import runtime จาก references

## สิ่งที่ต้องมีในเครื่อง

| เครื่องมือ | เวอร์ชัน |
|---|---|
| [uv](https://docs.astral.sh/uv/) | ล่าสุด — จัดการ Python และ dependency |
| Node.js | 22.x |
| Docker | สำหรับรันด้วย container |

Python 3.12 ไม่ต้องติดตั้งเอง `uv` จะจัดการให้ตาม `backend/.python-version`

---

## ฐานข้อมูลบนเครื่องนักพัฒนา

เวอร์ชัน PostgreSQL มีแหล่งเดียวคือ [`config/postgres.env`](config/postgres.env)
ทุกคำสั่ง Compose จึงต้องอ่านไฟล์นั้น และต้องลบค่าจาก shell ก่อน
เพื่อไม่ให้ค่าภายนอกทับเวอร์ชันกลางโดยไม่ตั้งใจ

```sh
# ขึ้นฐานข้อมูล (บทบาททั้งห้าถูกสร้างครั้งเดียวตอนสร้าง volume)
env -u POSTGRES_VERSION docker compose --env-file config/postgres.env up -d --wait postgres

# รัน migration ด้วยบทบาท migrator เท่านั้น
cd backend
export TIEWTRADE_DATABASE_URL_MIGRATOR="postgresql+asyncpg://tiewtrade_migrator:dev_migrator@127.0.0.1:55432/tiewtrade"
uv run alembic upgrade head
```

ฐานข้อมูลที่สร้างไว้ **ก่อน** มีตัวดักการสร้างพาร์ทิชัน (F-04) ติดตั้งเพิ่มได้โดยรันไฟล์
bootstrap ซ้ำ — ทุกไฟล์ในโฟลเดอร์นั้นรันซ้ำได้โดยไม่เสียหาย:

```sh
for script in backend/db/bootstrap/*.sql; do
  psql "postgresql://postgres:postgres@127.0.0.1:55432/tiewtrade" -v ON_ERROR_STOP=1 -f "$script"
done
```

แล้วปิดพาร์ทิชันที่ค้างอยู่ด้วย `uv run alembic upgrade head`
หรือสั่ง `SELECT tiewtrade_protect_all_partitions();` ด้วยบทบาท `tiewtrade_migrator`

**เทสต์ต้องมีฐานข้อมูลจริง** ถ้าไม่ตั้ง URL เทสต์จะแดง ไม่ใช่ข้าม (ตั้งใจให้เป็นแบบนั้น)
ตั้งครบทั้งห้าบทบาทก่อนรัน `uv run pytest`:

```sh
H=127.0.0.1:55432/tiewtrade
export TIEWTRADE_DATABASE_URL_MIGRATOR="postgresql+asyncpg://tiewtrade_migrator:dev_migrator@$H"
export TIEWTRADE_DATABASE_URL_API="postgresql+asyncpg://tiewtrade_api:dev_api@$H"
export TIEWTRADE_DATABASE_URL_ENGINE="postgresql+asyncpg://tiewtrade_engine:dev_engine@$H"
export TIEWTRADE_DATABASE_URL_ENGINE_SCAN="postgresql+asyncpg://tiewtrade_engine_scan:dev_engine_scan@$H"
export TIEWTRADE_DATABASE_URL_MARKET_DATA="postgresql+asyncpg://tiewtrade_market_data:dev_market_data@$H"
export TIEWTRADE_DATABASE_URL_AUTH="postgresql+asyncpg://tiewtrade_auth:dev_auth@$H"
```

**การยืนยันตัวตน (F-05)** ตั้งเพิ่มสองค่าเมื่อจะลองสมัครหรือเข้าสู่ระบบในเครื่อง:

```sh
export TIEWTRADE_SIGNUP_OPEN=1      # ค่าเริ่มต้นคือปิด — เปิดเองโดยเจตนา
export TIEWTRADE_COOKIE_SECURE=0    # เพราะเครื่องพัฒนาใช้ http — บนเครื่องจริงห้ามปิด
```

**TOTP (F-06) และ API key (F-07)** ต้องมีกุญแจปิดผนึกของตัวเองทั้งสองงาน
มิฉะนั้น **แอปไม่เริ่มเลย** (กุญแจไม่ครบต้องดังตอนเปิด ไม่ใช่ตอนมีผู้ใช้คนแรก):

```sh
export TIEWTRADE_SEALING_KEY_TOTP_SECRET="1:ZGV2LW9ubHkta2V5LW5vdC1hLXNlY3JldC0zMmJ5dGU="
export TIEWTRADE_SEALING_KEY_VENUE_API_SECRET="1:VlZWVlZWVlZWVlZWVlZWVlZWVlZWVlZWVlZWVlZWVlY="
```

กุญแจสองดอกนี้ต่างกันโดยเจตนา (RQ-4) · API ใช้กุญแจของ API key เพื่อปิดผนึก
ส่วนการเปิดผนึกทำเฉพาะใน `engine` · worker ต้องใช้กุญแจ API key ชุดเดียวกับ API
จึงจะอ่านแถวที่ปิดผนึกไว้ได้

**รอบตรวจ API key (F-07)** ยังรันด้วยมือ ใช้ URL ของบทบาท `engine` และ
`engine_scan` ที่ตั้งข้างบน พร้อมกุญแจ `TIEWTRADE_SEALING_KEY_VENUE_API_SECRET`:

```sh
cd backend
uv run python -m tiewtrade.services.engine.main
```

worker ตรวจ key ผ่านสัญญา venue และบันทึกผลลงฐานข้อมูล · เมื่อหยุด worker
รายการที่ยังไม่ผ่านจะรอจนเปิด process อีกครั้ง · **ตัวตั้งเวลาบนเครื่องจริงเป็นงาน F-31**
หากพบ log ระดับ ERROR รหัส `VENUE_PROTOCOL` ต้องตรวจตัวเชื่อม
และต่อ log นี้เข้าช่องทางแจ้งผู้ดูแลตอนนำขึ้นเครื่องจริงใน F-31

**เก็บกวาดตารางของการยืนยันตัวตน** — ปิดหนี้ที่ค้างมาจาก F-05 (`auth_throttle`)
และครอบ `login_challenges` ของ F-06 ด้วย · **ยังไม่มีตัวตั้งเวลาให้ การตั้งเวลา
บนเครื่องจริงเป็นงาน F-31** และต้องมีก่อนปล่อยผู้ใช้จริง:

```sh
cd backend
uv run python scripts/sweep_auth_tables.py --dry-run  # บอกว่าจะลบเท่าไรโดยไม่ลบ
uv run python scripts/sweep_auth_tables.py            # ลบจริง
```

สคริปต์ลบเฉพาะแถวที่ **ไม่มีผลจำกัดการเดาแล้ว** — ถังที่ยังหน่วงอยู่หรือที่โควตา
ยังไม่เต็ม และ challenge ที่ยังใช้ได้ จะไม่ถูกลบ

รูปแบบคือ `รุ่น:กุญแจแบบ base64` คั่นหลายรุ่นด้วยจุลภาค **รุ่นแรกใช้ปิดผนึกของใหม่**
ที่เหลืออ่านของเก่าได้ เพื่อให้หมุนกุญแจได้โดยแถวเก่าไม่อ่านไม่ออก
· **ค่าข้างบนใช้ได้เฉพาะเครื่องพัฒนาและ CI** กุญแจบนเครื่องจริงยังเป็นข้อที่ต้องตัดสิน
(**T-03**) ซึ่งเป็นงาน **F-31**

พอร์ตบนเครื่องคือ **55432** เพื่อไม่ชนกับ PostgreSQL ที่อาจติดตั้งไว้แล้วที่ 5432
**รหัสผ่านชุดนี้ใช้ได้เฉพาะเครื่องนักพัฒนาและ CI** บนเครื่องจริงเป็นงาน F-31

เริ่มใหม่ทั้งหมด (รวมรื้อบทบาท) ด้วย
`env -u POSTGRES_VERSION docker compose --env-file config/postgres.env down -v`

---

## รันในเครื่อง

```sh
# หลังบ้าน
cd backend
uv sync
uv run uvicorn tiewtrade.services.api.app:app --no-proxy-headers --reload --port 8000 --ws tiewtrade.services.api.price_protocol:PriceWebSocketProtocol

# หน้าบ้าน (อีกหน้าต่าง)
cd frontend
npm install
npx playwright install chromium   # ครั้งแรกเท่านั้น สำหรับเทสต์ e2e
npm run dev
```

API ปิดการอ่าน forwarded headers ด้วย `--no-proxy-headers` ทุก launch command
เพื่อให้ WebSocket admission ใช้ TCP peer จริง ผู้เรียกจึงปลอม `X-Forwarded-For`
เพื่อเปลี่ยน IP bucket ไม่ได้ เมื่อผ่าน Vite/reverse proxy ผู้ใช้จะใช้ IP bucket
ของ proxy ร่วมกัน หาก deployment ต้องแยก client IP ต้องกำหนด trusted proxy
อย่างชัดเจนและให้ proxy ล้าง/เขียน forwarded headers ใหม่ก่อนเปิดรับ headers เหล่านี้.


`npx playwright install chromium` เก็บเบราว์เซอร์ไว้ที่ระดับผู้ใช้ ไม่ใช่ในโฟลเดอร์โปรเจกต์
จึงต้องรันครั้งเดียวต่อเครื่อง ไม่ใช่ครั้งเดียวต่อการโคลน — ถ้าข้าม `npm run test:e2e` จะพัง

เปิด http://localhost:5173 เพื่อเข้าสู่ระบบ จัดการ TOTP และ API key ของตัวเอง
การเพิ่ม key ต้องเปิด TOTP ก่อนและยืนยันด้วยรหัสชุดใหม่ทุกครั้ง · เมื่อเพิ่มแล้ว
สถานะจะอัปเดตเอง แต่ต้องรัน worker ตามคำสั่งด้านบนเพื่อให้มีการตรวจจริง
หน้าเว็บยังแสดงข้อมูลจาก `GET /health` และยังไม่มีความสามารถด้านการเทรด

**F-08 บัญชีเทรดเดียว:** API key หนึ่งชุดต่อผู้ใช้รวมทุกสถานะ
เลือก MANUAL หรือ BOT ครั้งแรกได้เมื่อ key ACTIVE และยืนยัน fresh TOTP
ความเลือกเก็บที่ server; การลบ key คงความเลือกไว้ และยังเปลี่ยนประเภทไม่ได้
เมื่อไม่มีหลักฐาน activity ครบ คง UI จาก TailAdmin; ยังไม่มีการส่งออเดอร์/บอท/เปิด Live
สถานะ validation/review ปัจจุบันอ่านจาก roadmap และ validation.md

## รันด้วย container

```sh
env -u POSTGRES_VERSION docker compose --env-file config/postgres.env up --build
```

ลำดับคือ `postgres` → `migrate` (รันครั้งเดียวแล้วจบ) → `api` → `frontend`
ยังไม่มี Redis ใน `compose.yaml` โดยเจตนา — ยังไม่มีงานไหนต้องใช้คิว

---

## คำสั่งตรวจ

**ทุกด่านต้องเขียวก่อน merge ไม่มีข้อยกเว้น** และคำสั่งเหล่านี้เหมือนที่ CI รันทุกประการ

```sh
# หลังบ้าน
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pytest

# หน้าบ้าน
cd frontend
npm run lint
npm run typecheck
npm run test
npm run test:e2e

# สัญญา API สองฝั่งต้องตรงกัน
cd backend && uv run python -m tiewtrade.services.api.openapi_export
cd ../frontend && npm run check:api
```

### ฐานข้อมูลสำหรับ E2E

ก่อน `npm run test:e2e` ให้สร้างฐานข้อมูล PostgreSQL ที่ทิ้งได้แยกจากฐานพัฒนา
เช่น `tiewtrade_e2e_local`, bootstrap บทบาทและรัน migration ตามขั้นตอนเดิม
ตั้ง `TIEWTRADE_E2E_DATABASE_NAME=tiewtrade_e2e_local` และ URL ของบทบาท
`MIGRATOR`, `API`, `AUTH`, `ENGINE`, `ENGINE_SCAN` ให้ชี้ชื่อฐานนี้บน loopback
host/port เดียวกัน; F-09 E2E ต้องตั้ง `MARKET_DATA` ให้ชี้ฐานเดียวกันด้วย
ใช้ username ของแต่ละบทบาทตามเดิม ไม่มี query parameters ใน URL

E2E ล้าง `auth_throttle` ก่อนแต่ละ test **เฉพาะฐานทดสอบที่ตรวจแล้ว**
ตรวจชื่อจาก connection จริงก่อนล้าง และไม่ reuse API/frontend ที่เปิดอยู่
หยุด server บน port 8000/5173 ก่อนรัน; proxy ของ E2E ชี้ API ที่เริ่มเอง
หากไม่ตั้งฐานทดสอบหรือ URL ไม่ตรงกัน จะหยุดด้วย `E2E_DATABASE_REJECTED`
CI job E2E ใช้ฐานแยกชื่อ `tiewtrade_e2e`

### ประวัติแท่งเทียน (F-09)

หลัง migration0013 API ที่เข้าสู่ระบบแล้วอ่าน `GET /market-data/candles`
ด้วย `base`, `quote`, `timeframe` และ `start`/`end` คู่กัน (ไม่ระบุช่วงจะใช้ช่วงตั้งต้น)
รองรับ1m/5m/15m/1h/4h/1d และอ่านได้สูงสุด1,000 slots ต่อครั้งภายใน365วัน
การอ่านไม่สร้างงานดึงข้อมูล; ใช้ `POST /market-data/candles/requests` พร้อม CSRF
เพื่อขอเติมประวัติหรือ refresh observation ที่เข้าเกณฑ์ มีข้อมูลครบและไม่มีงานที่ต้องรอจะคืน200
งานที่รับ/coalesce แล้วคืน202 โดยอ่าน `coverage`, `gaps`, `status`, `refresh_pending`
และเวลาของ observation จาก GET ต่อไป

รัน public-market worker ด้วยบทบาท `MARKET_DATA` ที่ตั้งไว้แล้ว:

```sh
cd backend
uv run python -m tiewtrade.services.market_data.main --once
```

ไม่ใส่ `--once` จะวนทุก30s; ตัวตั้งเวลา deployment เป็นงาน F-31
worker อ่าน public market data ผ่าน venue โดยไม่ใช้ key ผู้ใช้หรือส่งออเดอร์
REST finality คงเป็น `UNCONFIRMED`; presence ไม่ใช่คำรับรองว่าปิดแล้วหรือพร้อมให้กลยุทธ์ใช้
ไม่รับรอง upstream history ครบ365วัน และต้องทำ rolling partition maintenance ก่อนช่วงที่เตรียมไว้หมด
เทสต์ปกติและ Docker smoke ใช้ FakeVenue/fixtures; realtime/indicator/chart เป็น F-10/F-11/F-12

### ถ้าแก้ API แล้วด่านแดง

สร้างสัญญาและชนิดข้อมูลใหม่ แล้ว commit ทั้งสองไฟล์

```sh
cd backend && uv run python -m tiewtrade.services.api.openapi_export
cd ../frontend && npm run gen:api
```

`frontend/src/api-types.ts` **สร้างจากสัญญา API ห้ามแก้มือ**

---

## โครงโฟลเดอร์

```
backend/src/tiewtrade/
├── core/         ตรรกะโดเมนบริสุทธิ์ — ห้ามพึ่งอะไรเลย ห้ามใช้ float
├── strategies/   กลยุทธ์ — พึ่ง core เท่านั้น
├── venues/       ชั้นแยกตลาด — ยังว่าง (งาน F-33)
├── infra/        ฐานข้อมูล (db/) คิว log
└── services/     api, engine, market_data — ห้าม import กันเอง
```

โค้ดทั้งหมดอยู่ใต้ namespace `tiewtrade` เพื่อไม่ให้ชื่ออย่าง `core` หรือ `services`
ชนกับ package อื่น — import จึงเป็น `from tiewtrade.core import ...`

ทิศทางการพึ่งพาถูกบังคับด้วย `import-linter` ใน CI ไม่ใช่ด้วยการรีวิว
ดู [`specs/standards/architecture.md`](specs/standards/architecture.md)

### `backend/tests/gates/` — ห้ามลบ

ไฟล์ในนั้นผิดกฎโดยเจตนา และมีเทสต์ที่พิสูจน์ว่าด่านตรวจจับได้จริง
ถ้าลบ จะไม่มีอะไรบอกได้ว่าด่านยังทำงานอยู่ ดู [`plan.md` ของ F-01](specs/features/2026-09-26-project-skeleton/plan.md)
