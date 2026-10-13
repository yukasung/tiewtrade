# F-12 final candidate validation

วันที่: 2026-10-13 (Asia/Bangkok)

สถานะ: **Automated local checks recorded; acceptance ยัง Partial**

สถานะนี้ไม่ใช่การรับรองว่า V-01..16 หรือ V-18 ผ่านครบ. หลักฐาน automated ด้านล่าง
ใช้ยืนยันเฉพาะ checks ที่ระบุ ส่วน criterion mapping, owner manual acceptance,
required CI และ V-17 ยังต้องปิดตาม `validation.md`.

Candidate นี้เริ่มจาก commit `d4b29c2` และรวม working-tree changes ที่แสดงใน
`git status` ของรอบนี้ ได้แก่ ingestion right expansion, manual Retry-After,
test isolation และหลักฐานที่เกี่ยวข้อง. ไม่มีการส่งออเดอร์, เปลี่ยน trading mode,
แก้ Money/Quantity หรือเรียก Live Trading ระหว่าง validation.

## ผลที่ใช้ตัดสิน candidate

| ด่าน | Environment / คำสั่ง | ผล |
|---|---|---|
| Dependency sync | Python/uv: `uv sync --frozen`; frontend Node 22: `npm ci` | ผ่าน; lockfiles ไม่เปลี่ยน และ npm audit รายงาน 0 vulnerabilities |
| Backend static | Ruff check/format, mypy, import-linter | ผ่าน: Ruff ผ่าน, 399 files formatted, mypy 370 filesไม่มี issue, import contracts 7 kept/0 broken |
| Frontend static/build | ESLint, TypeScript, Vite build บน Node 22 | ผ่าน; build 167 modules |
| Generated contract | export `backend/openapi.json`, generate `frontend/src/api-types.ts`, `git diff --exit-code` | ผ่าน; ไม่มี generated diff |
| Backend full regression | Linux Python 3.12.12, isolated ephemeral PostgreSQL 16/Redis 7, schema `0024`; `pytest` | **2,611 passed, 1 skipped, 2 deselected**, 0 failed/error, 499.34s; [JUnit](backend-linux-final-candidate.xml) |
| Frontend full regression | Linux Node 22 image; full Vitest รวม contract gate | **202 passed / 22 files**, 0 failed, 7.91s; [JUnit](frontend-linux-final-candidate.xml) |
| Browser E2E | Node 22 / Chromium / isolated F-12 DB; full chart config | **8 passed**, 133.73s; [JUnit](browser-final-candidate.xml) |
| Deployed browser smoke | `http://localhost:5173/chart`, frontend image `sha256:965ed8e14cbb72129baaa99401cdf3c89a581e5bd5a2832966b8937dd49ef56f` | default BTC/USDT 1h HTTP 200, history/proof consistent, live READY; Retry-After ไม่มี auto-retryและปุ่มเปิดเมื่อ cooldown หมด |
| Deep diff review | changed files กับ affected dependencies; correctness, concurrency, security และ trading safety | พบ Medium 2 ข้อ: cooldown พึ่ง wall clock และรายงาน acceptance กว้างเกินหลักฐาน; แก้ทั้งสองข้อหลัง artifact ชุดเต็ม จึงใช้ targeted verification ด้านล่างกับโค้ดล่าสุด และยังไม่เปลี่ยน V ใดเป็น Passed |

Backend skip คือ
`tests.infra.db.test_version_pin::test_compose_resolves_to_the_pinned_image`
เพราะ Linux test container ไม่มี Docker CLI. ตรวจทดแทนบน host ที่มี Dockerแล้ว:
targeted version-pin test **1 passed**; Compose resolve เป็น `postgres:16` และ Docker
client/server เป็น 29.8.2.
สอง tests ที่ deselected คือ `venue_contract` ตามการแยกชุดปกติ; ไม่มี API key,
private venue call หรือ order request ในรอบนี้.

E2E ครอบคลุม chart panes/exact values/languages, module routing, source mutation,
disconnect recovery, gap/logout, pair/timeframe switching, preview → REST settlement,
manual refresh failure และ fenced worker restart. Agent-driven browser checks เพิ่มเติมครอบคลุม
375/768/1,440 px, ไทย/อังกฤษ, offline/reconnect, truthful partial/stale/typed failures
ตาม [latest-history checkpoint](latest-history-ready.md); checks เหล่านี้ไม่ใช่ owner manual acceptance.

## Validation coverage ของ candidate

ตารางนี้ผูก V ทุกข้อกับหลักฐานที่มีและงานที่ยังขาด โดยใช้เกณฑ์ฉบับเต็มใน
[`validation.md`](../validation.md) เป็นตัวตัดสิน. คำว่า Partial หมายถึงยังไม่มี
criterion-to-test/artifact mapping และหลักฐานรับรองครบทุกข้อย่อย จึงห้ามตีความผล suite
ที่เขียวว่า V นั้นผ่านทั้งด่าน.

| V | หลักฐานที่มีสำหรับ candidate | สถานะ / งานที่ยังขาด |
|---|---|---|
| V-01 | public fixtures ใน `kline-public.json`/`kline-ordering.json`, dependency lock/license, frontend build และ full JUnit | **Partial** — ผูก parser/dependency checks ทุกข้อและ synthetic `x=true` closure กับ test/artifact ให้ครบ |
| V-02 | backend full JUnit รวม parser/feed lifecycle และ `chart-integrity-tests.xml` | **Partial** — mapping property cases เรื่อง ordering/conflict/duplicate/reconnect/epoch ยังไม่ปิดรายข้อ |
| V-03 | backend full JUnit และ bundle/snapshot integration เดิม | **Partial** — ต้องยืนยัน mapping LEGACY/PREPARED และ same-snapshot ทุกกรณีกับ final inputs |
| V-04 | proof fault artifacts และ backend full JUnit | **Partial** — mapping seed/gap/finality/retention/DDL และ overlay suppression ยังไม่ครบ |
| V-05 | backend full JUnit ครอบ proof/token/auth fault tests | **Partial** — ต้องผูก purpose/session/expiry/cross-replica/no-log ทุกข้อกับหลักฐานฉบับสุดท้าย |
| V-06 | response-boundary/cancellation artifacts และ backend full JUnit | **Partial** — timeout/abort/cleanup/no-partial ทุก boundary ยังไม่ถูกปิดรายข้อ |
| V-07 | migration/role/gate และ preview lifecycle artifacts, backend full JUnit | **Partial** — actual-role/lease/fencing/rollback mapping ยังต้องตรวจครบ |
| V-08 | backend integration, browser REST repair และ latest-history checkpoint | **Partial** — coalescing/end-boundary/fetch-proof/commit cases ยังต้องปิด mapping |
| V-09 | admission/recovery artifacts, backend JUnit และ browser E2E | **Partial** — freshness/restart/Redis/slow-consumer/control-limit mapping ยังไม่ครบ |
| V-10 | auth/security route tests ใน backend JUnit และ browser logout/routing E2E | **Partial** — session expiry/revocation/routing policy ทุกกรณียังต้องผูกหลักฐาน |
| V-11 | frontend JUnit และ targeted controller/read-episode tests | **Partial** — finite-state/retry/stop/refresh criteria ต้องปิด mapping กับโค้ดล่าสุด |
| V-12 | frontend renderer/API tests, browser panes/exact-value flow | **Partial** — numeric boundaries/whitespace/continuous-segment cases ยังต้องผูกครบ |
| V-13 | frontend controller tests และ browser route/series flows | **Partial** — 12,000-slot pagination/eviction/viewport closure ยังขาด |
| V-14 | browser JUnit, screenshots และ agent-driven viewport/language checks | **Partial** — owner manual acceptance ของ chart/panes/keyboard/mobile/languages ยังไม่เกิดขึ้น |
| V-15 | browser E2E กับ isolated DB/FakeVenue/worker และ backend JUnit | **Partial** — ต้องยืนยัน flow-to-criterion mapping กับ final inputs และ required environment records |
| V-16 | browser E2E, screenshots และ panel state tests | **Partial** — owner manual ของ states/refresh/stop/no-trading-action และ mapping ทุกภาพ/ข้อความยังค้าง |
| V-17 | smoke/bounds evidence เท่านั้น | **Pending Full Validation** — workload/resource/latency ทั้ง LEGACY/PREPARED รอ release checkpoint |
| V-18 | static/build/contracts/full JUnit artifacts และ targeted post-review checks | **Partial** — owner manual, required CI, final exact-candidate closure และส่วนที่พึ่ง V-17 ยังค้าง |

## Defect ที่พบและปิดในรอบ candidate

Security route matrix เคยพึ่ง indicator rows ที่ค้างจาก test run ก่อนหน้า:
`GET /market-data/indicators` บน clean DB ตอบ `503 INDICATOR_DATA_NOT_READY`
ตามสัญญา แต่ test บังคับ HTTP 200. แก้ test ให้ยอมรับเฉพาะ typed 503 นี้และยังตรวจ
ทุก response ว่าไม่เผย API secret. Targeted matrix ผ่าน 2/2 และ backend full regression
บน clean DB ผ่านตามผลด้านบน.

## Diagnostic runs ที่ไม่นำมาใช้แทนผล candidate

- Backend บน Windows ได้ 2,442 passed, 15 failed, 155 errors เพราะ harness ใช้
  `.venv/bin`, CP1252, timezone data และ network guard ที่ชน Proactor socketpair.
- Frontend บน Windows ได้ 200 passed, 2 errors เพราะ OS ไม่อนุญาต symlink ใน temp;
  contract tests เดียวกันและ full suite ผ่านใน Linux artifact ด้านบน.
- Linux diagnostic ที่ mount source read-only ทำให้ mypy/cache gates ล้ม.
- มี diagnostic runners สองตัวชน PostgreSQL cluster เดียวกันระหว่างวิเคราะห์;
  ผลนั้นถูกตัดทิ้ง. Final backend artifact รันด้วย runner เดียวบน DB/Redis ใหม่,
  bootstrap+migrate ถึง `0024` และไม่มี workload อื่นร่วม.

## Subsequent scoped refactor review

เจ้าของสั่ง review/refactor เฉพาะโค้ดงานล่าสุด: ปรับชื่อ `cooldownRemaining` และ
`cooldownTimer`, แยกเงื่อนไข cooldown เป็น block เพื่ออ่านง่าย และย่อคอมเมนต์ของ
security route matrix. ไม่มีการเปลี่ยน business logic, assertions หรือ backend
executable code และไม่เพิ่ม utility/abstraction ใหม่.

หลัง refactor: chart controller/panel/read episode/API tests **32/32 passed**,
frontend ESLint/TypeScript ผ่าน, backend Ruff/format ผ่าน และ mypy 370 filesผ่าน.
ผล backend full regression เดิมยังใช้ได้; ไม่รัน full suite/build/E2E ซ้ำเพราะ
frontend เปลี่ยนเฉพาะชื่อ local variables/รูปแบบ และ targeted regression ผ่าน.

## Post-review corrections

Deep review รอบถัดมาพบ Medium 2 ข้อและแก้โดยไม่แตะ trading/order paths:

- Controller เปลี่ยนการบังคับ cooldown เป็น monotonic deadline ด้วย
  `performance.now()`; wall-clock ที่ย้อนระหว่างรอจึงไม่ทำให้ปุ่ม Retry ค้าง disabled.
  Regression test จำลอง `Date` ย้อน 60 วินาทีและยืนยันว่าไม่มี auto-retry,
  ปุ่มปลด cooldown ตามเวลาที่ผ่านจริง และ manual retry ส่งคำขอได้หนึ่งครั้ง.
- รายงานนี้เปลี่ยนจากคำว่า local gates passed เป็นสถานะ automated checks recorded,
  เพิ่ม mapping V-01..18 และระบุ owner manual/criterion closure ที่ยังค้างตามจริง.

ตรวจโค้ดล่าสุดด้วย chart controller/panel tests **15/15 passed**, targeted ESLint ผ่าน
และ TypeScript `--noEmit` ผ่าน. ไม่รัน full suite/build/E2E ซ้ำ เพราะการแก้ executable
จำกัดที่ frontend cooldown controller/panel และ targeted regression ครอบผลกระทบตรง;
full candidate/CI ของ commit สุดท้ายยังเป็นงาน V-18 ก่อน merge.

## Owner manual viewport correction

ระหว่าง owner manual วันที่ 2026-10-13 เจ้าของพบว่าเมื่อมีข้อมูลเพียงไม่กี่แท่ง
initial viewport ขยาย candle เต็มพื้นที่; หลังปรับใช้ library default พบว่าแท่งจำนวนน้อย
กองชิดขอบจนแทบมองไม่เห็น เจ้าของจึงยืนยันให้แสดงแบบ TradingView. แก้ panel ให้ initial
viewport มี 100 logical slots ล่าสุดและเว้นด้านขวา 5 slots โดยไม่ clamp ช่องว่างก่อนข้อมูล
พร้อมรักษา logical viewport เดิมเมื่อข้อมูลอัปเดต. Browser review พบ follow-up ว่า
การนับจาก candle อย่างเดียวทำให้แกนที่มี indicator history มากกว่าเปิดไปยังวันเก่า;
แก้ให้ anchor จากจำนวน time slots รวมของ candle และ indicator ตามแกนจริง. การตรวจ
browser ต่อพบว่า live preview มาถึงก่อน history และ provisional range ถูกเก็บหลัง history
1,000 แท่งมาถึง จึงเพิ่ม state แยกเพื่อแทน provisional range ด้วยช่วงล่าสุดหนึ่งครั้งเมื่อ
history bundle แรกพร้อม แล้วจึงรักษา viewport ที่ผู้ใช้ปรับใน update ถัดไป.
บันทึก amendment นี้ใน `plan.md`; requirements และ validation criteria เดิมไม่เปลี่ยน.

Targeted panel/renderer tests **11/11 passed**, ESLint และ TypeScript `--noEmit` ผ่าน.
Build/restart เฉพาะ frontend สำเร็จด้วย image
`sha256:3aeb3298d74e39bbef2a4f3cc72ee9decc4defcb26a53a9158c07c466e6af25c`.
Browser smoke ที่ `http://localhost:5173/chart` หลังรอ live polling แสดง candle
ใน viewport 100 slots พร้อมระยะขวา 5 slots มองเห็นแท่งได้ทันทีและไม่ถูก polling
ขยายหรือย่อกลับ. History response มี 1,000 slots ช่วง 1 ก.ย.–13 ต.ค.; viewport
เริ่มที่ 9 ต.ค. และสิ้นสุดข้อมูลล่าสุด 13 ต.ค. ตาม 100 slots ที่กำหนด มี 11 canvases
และไม่มี JavaScript page error.
ผลนี้ปิดเฉพาะ feedback เรื่อง initial candle size; owner manual รายการอื่นยังค้าง.

## งานที่ยังค้าง

- Required CI ต้องรันกับ commit สุดท้ายหลังเจ้าของสั่ง commit/push; local results
  ไม่ใช้แทนสถานะ CI.
- Owner manual acceptance ตาม `validation.md` ยังไม่เกิดขึ้น และ V-01..16 ยังเป็น
  **Partial** จน criterion-to-test/artifact mapping กับ final inputs ปิดครบ.
- V-17 performance/workload/resource ทั้ง LEGACY/PREPARED ยังคง
  **Pending Full Validation** สำหรับ release checkpoint/ชุดที่ 9 ตาม validation เดิม.
- F-12 ยังไม่เปลี่ยนเป็น Completed และไม่รับรอง production PREPARED, Live Trading
  หรือการเปิดใช้เงินจริงจนงานค้างข้างต้นผ่านตามระยะของมัน.
