# F-16 M1 — Contract / persistence checkpoint

วันที่: 2026-10-25
สถานะ: M1 implementation และ targeted checks ผ่าน; F-16 ยัง In Progress
Branch: `feat/f16-manual-order-entry`; source เป็น uncommitted working tree ต่อจาก main
requirements และ plan/validation ฉบับแก้ F16-R1/R2/R3 ได้รับอนุมัติก่อนเริ่มโค้ด

## ขอบเขตและผล

- Strict input variants สำหรับ MARKET BUY quote budget, MARKET SELL base quantity,
  LIMIT BUY/SELL base+price/GTC ใช้ Money/Quantity เท่านั้น ไม่รับ client mode/origin/order ID
- Migration 0041 เพิ่ม immutable inbox/results, dispatch metadata, composite owner/episode
  linkage, RLS, runtime role grants, JSON/financial-domain constraints และ typed audit events
- API-role intake เขียน request/dispatch/audit ใน transaction เดียว ใช้ wallet advisory lock
  แต่ไม่ขอ UPDATE privilege บน wallet state; ไม่สร้าง order/reservation/ledger effects
- จับ authoritative catalog revision ของ BUY ภายใต้ pair fence ตั้งแต่ intake;
  canonical fingerprint ไม่รวม server-generated order ID หรือ catalog metadata
- Same-key concurrent requests คืน request/order เดิม; decode ตรวจ canonical intent,
  owner/episode/identity/fingerprint ไม่ยอมรับ stored payload ที่ไม่สอดคล้อง
- เพิ่ม joined intake/command outcome reader ที่คืน downstream rejection ได้โดยไม่มี
  paper_orders และ owner-bound keyset discovery สำหรับ unresolved requests ทุก episode
- เพิ่ม pending inbox ลง paper_wallet_reset_readiness โดยคงหลักฐานเดิมทั้งหมด;
  terminal rejection ปล่อย reset blocker, หลัง reset replay key เดิมยังคืน request เก่า
- API ไม่มีสิทธิ์เขียน financial tables; scanner อ่าน payload ไม่ได้; ขยาย Paper isolation
  gate ครอบ schema/input และ inbox/read modules ใหม่

## การเลือกตรวจ

Schema ใหม่เพิ่ม owner/RLS boundary และช่วง pending ก่อนเข้าคิว F-15 ซึ่งหลักฐานเดิม
ยังไม่ครอบคลุม จึงใช้ PostgreSQL runtime roles จริงสำหรับ transaction/replay/reset/grants
และ reuse wallet/dispatch/audit regression. ไม่เปลี่ยน matching/fee/PnL arithmetic จึงไม่
เพิ่มชุดคำนวณซ้ำ ไม่มี workload/endurance/timed smoke หรือ Live order

## หลักฐาน

Environment: Python 3.12 ผ่าน `backend/.venv`/uv, PostgreSQL image จาก
`config/postgres.env`; isolated Compose project `tiewtrade-f16` พอร์ต 55432 ไม่ใช้ DB
ของ release/F-14/F-15 sessions อื่น. Bootstrap roles เดิมจาก `backend/db/bootstrap/`
ฐานข้อมูลมี migration head 0041; connection URLs ใช้ dev-only roles ตาม README

| การตรวจ | ผล |
|---|---|
| Upgrade head → downgrade 0040 → upgrade head บน schema ว่าง | Passed ทั้งก่อนและหลังปรับ audit failure-code allowlist |
| Populated downgrade safety guard | Passed — ปฏิเสธด้วย `manual order request history prevents downgrade`; ไม่ลบประวัติ |
| Schema inputs + inbox + audit regression | 161 passed / 10.45s บน revision ก่อนเพิ่ม terminal-intake replay case; ใช้ audit/schema evidence ที่ไม่รับผลจากการแก้ภายหลังต่อ |
| Final M1 regression: `tests/services/api/test_manual_order_models.py tests/infra/manual_orders tests/infra/audit tests/infra/paper_wallet tests/infra/execution_market/test_dispatch.py tests/gates/test_paper_isolation.py` | **210 passed / 19.97s** บน schema ฉบับสุดท้าย รวม nullable-result และ terminal replay cases |
| Ruff สำหรับ source/migration/tests ที่เปลี่ยน | Passed |
| Full strict mypy | Passed — 484 source files ณ รอบนั้น; ตรวจ full strict mypy อีกครั้งหลังเพิ่ม terminal replay และ nullable-result regression ผ่านเท่าเดิม |
| Import-linter | Passed — 7 contracts kept / 0 broken |
| git diff --check | Passed ก่อน checkpoint |

คำสั่ง pytest/alembic รันจาก backend ด้วย role environment ของ DB แยก F-16;
wrapper ชั่วคราว `/tmp/tiewtrade-f16-run.py` ตั้งชื่อ role/URL ตาม README แล้ว exec uv
ไม่ใส่ credentials ลง evidence หรือ logs. คำสั่งมาตรฐาน: `uv run alembic ...`,
`uv run pytest ...`, `uv run ruff check ...`, `uv run mypy`, `uv run lint-imports`

Failures ที่แก้แล้ว: asyncpg UUID ต้อง normalize ที่ boundary ก่อน strict audit details;
เพิ่ม failure codes ทั้ง global Python allowlist และ DB CHECK; legacy wallet downgrade test
เพิ่ม guard 0041 แบบเฉพาะเจาะจงและยังยืนยันข้อมูลเดิมไม่หาย. Fixture error ของ input-only
suite เกิดจาก autouse DB setup ใต้ tests/api; ย้ายไป tests/services/api ให้ตรงระดับ unit
ไม่ลด assertions. เพิ่ม scan_engine fixture ที่ขาดใน terminal replay test แล้ว rerun ผ่าน; review พบ
SQL CHECK ของ rejection ต้องระบุ failure_code IS NOT NULL เพื่อปิด nullable boolean
จึงเพิ่ม regression เขียนตรงด้วย engine role และ rebuild schema/rerun final suite

เวลาที่มีหลักฐานเป็น elapsed ของเครื่องมือตามตาราง; ไม่ได้วัดช่วงอ่าน/เขียน/review/รออนุมัติ
แยกกันครบ จึงไม่แต่งเวลารวมและไม่บวกเวลางานขนานซ้ำ

## Coverage และงานค้าง

- V-1: input/domain boundary ผ่าน; public route/form ยังรอ M2/M3
- V-2/3/4/7/10/11: persistence/replay/audit/RLS/reset/rollback/joined request reader ผ่านใน
  ขอบเขต M1; API permissions/errors, bridge crash/transfer races และ full financial views
  ยังต้องตรวจใน M2 ไม่ถือทั้ง V ผ่านครบ
- F16-R1: intake revision pin ผ่าน; bridge/execution propagation ยังรอ M2
- F16-R2: joined command rejection reader ผ่าน; public response/polling ยังรอ M2/M3
- F16-R3: unresolved discovery ผ่าน; journal/reload/browser recovery ยังรอ M3
- M2: claim/fencing/atomic transfer, original catalog revision ถึง F-15, shared account policy,
  API/read contracts และแยก throttle buckets พร้อม affected safety tests
- M3: shared form/Paper+Live URLs, owner-scoped queries, journal/discovery, i18n/template/E2E
- M4: Ready for Code Review notification เมื่อเขียนครบ feature, review/fixes และ candidate gates
- V-18 ยัง Pending Dependency F-18; V-20 Pending Full Validation ที่ release checkpoint
  ไม่มี public order route ใหม่หรือ production activation ใน M1; worker ยัง policy=None
- ยังไม่ commit/push/merge และยังไม่ Completed หรือพร้อม merge
