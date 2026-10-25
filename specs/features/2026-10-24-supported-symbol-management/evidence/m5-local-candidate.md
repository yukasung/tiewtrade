# F-37 M5 — Local candidate validation

วันที่: 2026-10-25

สถานะ: **Local candidate + review fixes passed — Pending required CI และ merge**

## Candidate source

- ตรวจ production implementation ครบ M1–M4 ตาม diff ของ branch
  `feature/f37-supported-symbol-management`
- automated validation ใช้ Paper/FakeVenue และ isolated PostgreSQL/Redis เท่านั้น
- ไม่มีการเปิด Live Trading หรือส่ง private/live order

## ผลตรวจ

| การตรวจ | ผล |
|---|---|
| backend full regression | `3205 passed, 2 deselected, 5 warnings`; venue contract ถูกแยกตาม config |
| post-review affected regression | 207 passed บน fresh migrated PostgreSQL: catalog/API/engine/order worker/chart/realtime 83 และ indicator claim/rollout/scheduler 124 |
| Ruff check / format | ผ่านทั้ง backend; final format check `517 files` |
| strict mypy | ผ่าน `473 source files` หลัง review fixes |
| import-linter | 7 contracts kept, 0 broken |
| frontend Vitest | 27 files, 262 tests passed รวม async REQUESTED→ACTIVE polling โดยไม่ reload หน้า |
| frontend ESLint / TypeScript / production build | ผ่าน; rerun จาก image ที่ buildใหม่จาก source ปัจจุบัน |
| OpenAPI generated contract | 2 tests passed; generation deterministic ตรง contract |
| Chromium E2E | final rerun 2 passed (`24.6s`): Owner/TOTP/bootstrap/add/remove/durable `PARTIAL`, responsive 375/768/1440, dark mode, ไทย/อังกฤษ; Trader navigation/API 403 |
| `git diff --check` | ผ่าน |

Chromium ใช้ production FastAPI routes/lifespan, test-only bootstrap/reconcile endpoints,
fresh migration และ browser จริง การตรวจ `PARTIAL` มาจาก
`reconcile_supported_symbol_effects()` แล้ว reload catalog จากฐานข้อมูล ไม่ใช่ mock UI state

หลัง deep review แก้ idempotency preflight, column grant ภายใต้ FORCE RLS, removal-generation
fence ของ Paper BUY, indicator catalog filtering, runtime maintenance ของ re-add, candle metadata
pruning, quote-supervisor restart และ UI polling จึงคงผล full regression เดิมเฉพาะส่วนที่ไม่กระทบ
และ rerun affected set 207 tests บน source สุดท้ายตาม testing §7 นอกจากนี้ migration
`0040 -> 0039 -> 0040` ผ่าน และ quality gates backend/frontend ที่ได้รับผลกระทบผ่าน

## Coverage สำคัญ

- migration/append-only/RLS/bootstrap/protocol gate: catalog migration และ privilege tests
- readiness 8 timeframe, stale proof, add/remove/re-add: catalog lifecycle/service tests
- shared pair fence, queued rejection, active LIMIT cancellation, reduce-risk และ lock ordering:
  Paper engine/storage integration tests รวม remove→re-add ก่อน worker resume โดยไม่เกิด fill/balance drift
- dynamic market-data/indicator demand, maintenance และ durable zero-exposure proof:
  catalog/market-data/indicator integration tests
- API authorization/TOTP/idempotency/impact redaction/OpenAPI: API tests และ Chromium E2E
- UI loading/error/stale/pending/partial/conflict/accessibility/responsive/i18n: component tests และ
  Chromium E2E

## สิ่งที่ยัง Pending

- V-10 เฉพาะ Live cancellation/fill/partial/unknown reconciliation รอ F-22/F-23 ตาม amendment
  ที่เจ้าของอนุมัติ 2026-10-25; Paper/catalog contract ผ่านแล้ว
- V-18 รอ F-20/F-26 integration จริง
- V-19 รอ approved numeric release-validation profile และ full workload
- required CI, merge และ post-merge evidence ยังไม่เกิด เพราะยังไม่ได้รับคำสั่ง commit/push

ดังนั้นหลักฐานนี้ไม่เรียก F-37 ว่า Completed และยังไม่ประกาศ milestone
**Catalog/Order Safety Ready** จน review, required CI และ merge ผ่านตามแผน
