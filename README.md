# TiewTrade

Web application สำหรับเทรดคริปโตบน Binance TH แบบหลายผู้ใช้
รองรับทั้งการสั่งออเดอร์เองและบอทเทรดตามกลยุทธ์สำเร็จรูป มีทั้ง Paper Trading
และ Live Trading

**สถานะ: F-03 โครงฐานข้อมูล** ยังไม่มีความสามารถด้านการเทรด
เอกสารทั้งหมดอยู่ใน [`specs/`](specs/) — อ่าน [`specs/README.md`](specs/README.md) ก่อน

---

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
uv run uvicorn tiewtrade.services.api.app:app --reload --port 8000

# หน้าบ้าน (อีกหน้าต่าง)
cd frontend
npm install
npx playwright install chromium   # ครั้งแรกเท่านั้น สำหรับเทสต์ e2e
npm run dev
```

`npx playwright install chromium` เก็บเบราว์เซอร์ไว้ที่ระดับผู้ใช้ ไม่ใช่ในโฟลเดอร์โปรเจกต์
จึงต้องรันครั้งเดียวต่อเครื่อง ไม่ใช่ครั้งเดียวต่อการโคลน — ถ้าข้าม `npm run test:e2e` จะพัง

เปิด http://localhost:5173 จะเห็นหน้าเปล่าหนึ่งหน้าที่แสดงข้อมูลจาก `GET /health`

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
