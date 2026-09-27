# TiewTrade

Web application สำหรับเทรดคริปโตบน Binance TH แบบหลายผู้ใช้
รองรับทั้งการสั่งออเดอร์เองและบอทเทรดตามกลยุทธ์สำเร็จรูป มีทั้ง Paper Trading
และ Live Trading

**สถานะ: F-01 โครงเริ่มต้น** ยังไม่มีความสามารถด้านการเทรด
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
docker compose up --build
```

ยังไม่มี PostgreSQL และ Redis ใน `compose.yaml` โดยเจตนา — งานนี้ยังไม่มีตารางและไม่มีคิว

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
├── infra/        ฐานข้อมูล คิว log
└── services/     api, engine, market_data — ห้าม import กันเอง
```

โค้ดทั้งหมดอยู่ใต้ namespace `tiewtrade` เพื่อไม่ให้ชื่ออย่าง `core` หรือ `services`
ชนกับ package อื่น — import จึงเป็น `from tiewtrade.core import ...`

ทิศทางการพึ่งพาถูกบังคับด้วย `import-linter` ใน CI ไม่ใช่ด้วยการรีวิว
ดู [`specs/standards/architecture.md`](specs/standards/architecture.md)

### `backend/tests/gates/` — ห้ามลบ

ไฟล์ในนั้นผิดกฎโดยเจตนา และมีเทสต์ที่พิสูจน์ว่าด่านตรวจจับได้จริง
ถ้าลบ จะไม่มีอะไรบอกได้ว่าด่านยังทำงานอยู่ ดู [`plan.md` ของ F-01](specs/features/2026-09-26-project-skeleton/plan.md)
