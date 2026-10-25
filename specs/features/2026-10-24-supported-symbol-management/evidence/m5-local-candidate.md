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
- required CI สำหรับ corrections, merge และ post-merge evidence ยัง Pending;
  เจ้าของสั่ง commit/push ชุดแก้ทั้ง 4 findings แล้ว 2026-10-25

ดังนั้นหลักฐานนี้ไม่เรียก F-37 ว่า Completed และยังไม่ประกาศ milestone
**Catalog/Order Safety Ready** จน review, required CI และ merge ผ่านตามแผน

## Follow-up review corrections — 2026-10-25

เจ้าของสั่งแก้ findings 2 High / 2 Medium จาก deep review เพิ่มเติม บน base commit
`deb2a06`; เจ้าของสั่ง commit/push correction ชุดนี้แล้ว การเลือกตรวจอิงผลกระทบต่อ shared matching
state, reservation/cash/position, candle preparation, coordinator revision และ mutation retry:

- Paper worker ใช้ `cancel_order()` และ `persist_checkpoint()` เดิมยกเลิก BUY ที่ถูก removal
  invalidate ทุกใบใน pair state ก่อน admission/matching แม้ claim เป็นคำสั่งใหม่หลัง re-add
- Preview bootstrap enqueue backfill อย่างเดียว; candle proof มาจาก ingestion completion เดิม
- Coordinator ตรวจ pair revision ที่อ่านมา และตรึง global revision ก่อน venue I/O ทั้งเส้นทาง
  activate/fail; stored function ปฏิเสธเมื่อ revision เปลี่ยน ไม่ส่งผลเก่าไปยังคำขอใหม่
- Add/remove modal เก็บ payload/revision คู่กับ idempotency key ตั้งแต่ submit ครั้งแรก;
  retry ใช้ payload เดิม แต่กรอก TOTP ใหม่ได้

| การตรวจของ correction ชุดนี้ | ผล |
|---|---|
| execution-market integration, catalog integration, core matching, coordinator, candle preview และ ingestion | **225 passed in 105.62s** บน fresh migration ใน `tiewtrade_f37_review_fix_20261025_r2` |
| Regression ใหม่ | claim ของ BUY ใหม่ไม่ทำให้ resting BUY เก่า fill; BUY ใหม่ยัง fill ได้พร้อม cash/position หลัง fee ที่ถูกต้อง; pending backfill ไม่สร้าง candle proof และ activate ไม่ได้แม้ indicator/price พร้อม; delayed venue success/failure ไม่เปลี่ยน replacement command; lost-response ADD/REMOVE retry ส่ง body/key เดิมพร้อม TOTP ใหม่ |
| Backend quality | Ruff ผ่าน; format 521 files; strict mypy 476 source files; import-linter 7 kept / 0 broken |
| Frontend affected checks | SupportedSymbolPanel 6 tests ผ่าน; ESLint ของ source/test ที่แก้, TypeScript และ production build ผ่าน |
| Final affected diff review | ตรวจ wallet→pair lock order, deterministic cancellation identity, reservation release, revision conflict และ retry payload แล้ว ไม่มี Critical/High ค้างใน corrections |
| Runtime patch SHA-256 | `fd38b902219747dcb06ce098f35407cb9d24aabac65a28cb956b6fc436520be6` จาก `git diff -- backend/src frontend/src` |

Exploratory fixture runs เคย fail จาก fixture identity, privilege, source freshness และ expected
base fee ที่ไม่ถูกต้อง ซึ่งแก้แล้ว รอบรวมแรกบน DB ที่ใช้ลองซ้ำมี process-recovery สองกรณีและ
order-activity หนึ่งกรณี fail จึงหยุดรอบนั้นเป็น **Failed/Interrupted** แล้วรันชุดเดียวกันบน DB
ใหม่ ได้ผล 225 passed ข้างต้น ไม่ใช้ผลรอบที่หยุดเป็นหลักฐานผ่าน

ผล full regression/Chromium เดิมเป็นหลักฐานของ candidate ก่อน corrections; รอบนี้รันเฉพาะ
affected set ตาม testing §7 ไม่มี schema/API contract หรือสูตรการเงินเปลี่ยน ต้องให้ required CI
และ candidate gates ครบสำหรับ source ที่รวม corrections ก่อน merge ยังไม่ใช่ Completed;
V-10 Live, V-18 และ V-19 คง Pending ตามเดิม ไม่มีการส่ง Live order
