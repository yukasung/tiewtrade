# F-09 — Market data validation audit

วันที่: 2026-10-07
สถานะ: **Approved** — issue1–5แก้แล้ว; final Standards/Spec deep reviewไม่พบ actionable findings และlocal gatesตรวจใหม่ผ่านครบ
ตาราง verification: backend/frontend/E2E/generated contract/Docker ตรวจใหม่หลังแก้ issue1–5; เจ้าของสั่งดำเนินการ commit/push/PR/CI/merge
Branch: feature/f-09-market-data

Owner approvals: requirements และ plan/validation Approved ครบก่อน code; NC-09/T-04 Closed
Specs: [requirements](../features/2026-10-07-market-data/requirements.md),
[plan](../features/2026-10-07-market-data/plan.md), [validation](../features/2026-10-07-market-data/validation.md)

## Verification evidence

| Gate | Result |
|---|---|
| `.venv/bin/pytest` | 1,652 passed / 1 live-contract test deselected / 3 inherited deprecation warnings, 94.50s; หลังแก้ issue1–5 |
| Ruff lint / format | ผ่าน; 239 files formatted; หลังแก้ issue1–5 |
| strict mypy | ผ่าน; 221 files; หลังแก้ issue1–5 |
| import-linter | 6 contracts kept |
| frontend lint / typecheck | ผ่าน; หลังแก้ issue1–5 |
| frontend Vitest | 113 passed / 13 suites, 4.36s; หลังแก้ issue1–5 |
| frontend build | ผ่าน; 145 modules, 421ms; หลังแก้ issue1–5 |
| Playwright E2E | 9 passed, 44.5s บนฐานใหม่ที่ว่าง; หลังแก้ issue1–5 |
| generated API contract | export/regenerate2รอบ byte-identicalกับไฟล์ก่อนตรวจ; SHA256 checks/typecheck/contract gate2testsผ่าน หลังแก้ issue1–5 |
| Docker | Linux images build / migrate / API health / UI proxy health ผ่าน หลังแก้ issue1–5 |
| actual CLI --once | FakeVenue injected at composition; 1,000 rows commit ผ่าน role MARKET_DATA หลังแก้ issue1–5 |
| final diff | whitespace check ผ่าน; ไม่มี commit/push |

Backend ใช้ disposable project tiewtrade-f09-test ที่ port55445, roles/bootstrap/event triggerจริง
E2E ใช้ฐานแยก tiewtrade_e2e_f09_final ไม่ reuse app servers; Docker smoke ใช้ project/ports แยก
ไม่ migrate/resetฐานเดิมของเจ้าของหรือ F-08 preview และไม่มีการยิง private/live exchange ใน tests
หลังตรวจเสร็จปิด/ลบเฉพาะ test/smoke projects และ volumes ที่สร้างใน F-09;
ตรวจว่า containers เดิมและ F-08 preview ยังอยู่ครบ

## Validation coverage

Paths ของ tests อยู่ใต้ backend/ หากไม่ระบุ frontend

| Criteria | Evidence |
|---|---|
| V-1 | venue/import/money-movement gates, market-data composition positive/negative tests, closed Endpoint.KLINES/public transport |
| V-2 | adapter/API input tests + PAIRS/Timeframe + schema checks สำหรับ5pairs/6timeframes |
| V-3 | core precision tests, recorded adapter fixtures, actualDB financial-domain rejection, E2E exact price/volume strings |
| V-4 | 6interval fixtures/SITE/GLOBAL/bounds tests, pureUTC/timeframe alignment helpers |
| V-5 | REST UNCONFIRMED, all3core finalities, partial observation refresh tests/monotonic stored observation guard |
| V-6 | partitioned PK/SQL constraints, DB claim/storage tests, duplicate/conflict worker tests |
| V-7 | initial_window6timeframe tests, worker30seed/idempotency + daily cutoff |
| V-8 | leap-year fixed365 test + Hypothesis temporal properties + DB-clock skew/clamp tests |
| V-9 | adapter half-open bounds/ms ceiling tests, worker five-page pagination |
| V-10 | malformed/permanent/duplicate/partial worker tests; empty repair sweep exhaustion |
| V-11 | actual interior-gap repair + two-sweep UNAVAILABLE, preserved gaps/no generated candles |
| V-12 | actual API routes, concurrent API-role enqueue, pending watermark follow-up and completion lock tests |
| V-13 | API input/CSRF tests, storage oversized/expired/future rejection, bounded GET limit/window |
| V-14 | actual role claims/lease expiry + late-worker no-commit tests |
| V-15 | actual page/cursor fault rollback, durable reserved-attempt crash test, committed REFRESH qualification |
| V-16 | actual API role read/enqueue allowed; delete/OHLC/generation/status/worker-column INSERT/DDL denied |
| V-17 | MarketDataSession role/type assertions; actual worker credentials access denied; no runtime ownership/DDL grants |
| V-18 | monthly partitions/PK/grants; actual missing-partition worker test restores test partition and proves no candle/cursor commit |
| V-19 | actual expired/current cleanup test; SQL deletion limited10,000rows with tableoid+ctid; existing audit isolation regression |
| V-20 | empty replay + populated candle/demand downgrade refusal/version/schema/data preservation tests |
| V-21 | limiter floor/cost/default/accounting boundary tests, adapter/factory shared guard tests |
| V-22 | 120/600s source deferral/restart + concurrent failures/global-before-row lock + greatest persisted deadlines |
| V-23 | durable per-unit retries, five-page job, terminal eligibility, partial REFRESH, whole-source timeout regression |
| V-24 | four-attempt round/30s loop/10sdeadline, fair claim ordering, HTTP outside transactions, stored-data reuse |
| V-25 | real authentication/CSRF/noTOTP routes; public market tables contain no private identity/credentials |
| V-26 | FakeVenue/fixtures in normal tests; only pre-implementation17public probes as research evidence |
| V-27 | fixed validation DTO/OpenAPI200/202/422 + byte-identical types; no raw source/driver details in API payload |
| V-28 | full checks/reviews/regressions + README/spec/status updates in this change |

## Review fixes

- Missing gap-repair path, stale partial observations, CallCost/reservation ambiguity: fixed in approved plan before code.
- Pending refresh POST/completion race and retry-unit ambiguity: approved plan now has durable requested/served snapshots and per-unit budgets.
- Runtime review: future bounds, disjoint-window refresh metadata, nullable fetch-state CHECK: fixed with failing regression tests.
- Runtime review: concurrent source backoff deadlock and shortened cooldown: source advisory lock precedes row lock; every deadline update uses greatest.
- Runtime review: ignored older REFRESH observations falsely completing: success checks committed rows; unit persists/retries when still due.
- Runtime review: early POST authorizing terminal retry: terminal claim requires request timestamp at/after eligibility.
- Runtime review: host/DB clock mismatch and unbounded source call: seed/clamp use DB time and fetch has a shared10sdeadline.
- Related refactor: all four DB session wrappers reuse one execute/error translator; scoped79 session/auth/F-09 tests and final full suite passed.
- Regression gates updated for new routes/adapter and for predecessor migration refusal leaving version0012 before re-upgrading head.

One initial full E2E run used a DB also used for canary tests and failed the old key-worker scenario:
pending synthetic keys consumed the FakeVenue error before the new test key. A fresh dedicated E2E DB passed all9tests;
no application behavior or throttle rule was changed to make that pass.
Initial Docker FakeFixture assumed daily series first; actual lexicographic first series is15m.
Fixture corrected and smoke rerun committed1,000 observations; no runtime code changed for fixture ordering.

## Refactor follow-up (2026-10-07)

เจ้าของขอ review/refactor เฉพาะ F-09 โดยคง behavior/business logic:
รวม bounded-window iterator ใน core ให้ storage/worker ใช้ร่วมกัน,
แยก CandleView mapper ตามรูปแบบ API เดิม, เปลี่ยนชื่อ next-fetch/initial-seed helpers,
ถอด argument ของ private seed ที่ถูกเขียนทับทันที และใช้ rate-limit error instance ร่วมใน failure handler
public run_round signature, lock order, retry budgets, DTO/schema และ precision คงเดิม

Relevant core/storage/worker/API tests **74 passed**, 16.33s;
backend Ruff/format/mypy/import-linter และ frontend lint/typecheck ผ่าน
OpenAPI export ยัง byte-identical กับผลก่อน refactor; reviews สองด้านไม่มี findings
เทสต์ใหม่ยืนยัน unaligned chunk boundaries และขอบเขต1,000slots; test DB แยกจากฐานเดิม
ผล full suite 1,618 ข้างต้นเป็นผลก่อน refactor ไม่ได้นับเป็น full run ใหม่

## Deep review issue1 fix (2026-10-07)

เมื่อ repair2 ยังมี gap ให้บันทึก UNAVAILABLE/GAP_REPAIR_EXHAUSTED และ deadline120s
ก่อนพิจารณาขยาย desiredwindow; leasedwindow/pass2 คงเดิมและไม่เริ่มรอบใหม่จาก POST ก่อนเวลา
desiredwindow ที่ขยายยังอยู่ใน DB; explicit POST หลัง eligibility จึงอนุญาต UNAVAILABLE claim
รับ desired union เป็น leasedwindow ของ repair cycle ใหม่ เพื่อเติมส่วนใหม่ได้แม้ gap เดิมยังขาด
ไม่แก้ FAILED retry, active lease/fence, schema หรือ budgets

TDD: left/right/both scenarios แดง3ก่อนแก้ แล้วผ่าน3หลังแก้
Relevant core/claims/storage/worker/API tests77ผ่านใน17.40s; Ruff/format/mypy/import checks ผ่าน
Scoped spec/standards re-reviews ไม่มี findings ใน issue1; ปิดเฉพาะ issue1
ยังค้าง issue2 full-history scan cost, issue3 per-row write cost, issue4 DST cleanup cutoff,
issue5 datetime normalization overflow ตาม deep review; ไม่มีการแก้ส่วนเหล่านี้ในครั้งนี้

## Deep review issue2 fix (2026-10-07)

แทน chunk scans ที่ hydrate OHLC ทั้งช่วงด้วย COUNT/BOOL_OR จาก series/time metadata
SQLอาศัย PK uniqueness และ open-time alignment ของ schema เพื่อเทียบจำนวน expected slots
ใช้ pure slot_count สูตรเดิมร่วมกับ read-window validation; SQL refresh condition
เทียบกับ Python refresh_due ด้วย CLOSED/OPEN/UNCONFIRMED, fetch-start,30s/end_at boundaries
coalescing/request timestamps/row lock/permissions/retention/business rules คงเดิม

TDD actual SQL instrumentation: year/1m request และ duplicate request ใช้2market-data checks
และไม่เรียก OHLC hydration; redก่อนแก้แล้วgreenหลังแก้
Relevant tests91ผ่านใน18.15s; Ruff/format/mypy/import-linter ผ่าน; scoped reviewsสองด้านไม่มี findings
จำนวน DB round trips คงที่ต่อ POST แต่ aggregate ยังอ่าน metadata ตามจำนวนแถวในช่วงที่มีขอบเขต
issue3–5 ยังไม่แก้; ไม่มี schema/index/grant/API contract changes ใน issue2

## Deep review issue3 fix (2026-10-07)

แทน per-row DB calls ด้วย distinct-partition lookup1ครั้ง, existing-row lookup1ครั้ง
ที่เรียง open_at/FOR UPDATE และ multi-values upsert1ครั้ง พร้อม fence/clockเดิม
วัดผ่าน actual SQL instrumentation ได้5callsต่อ1,000แท่ง เทียบ3,002callsก่อนแก้
ใช้ Money/Quantity convertersและ bound parameters เดิม ไม่มี JSON float หรือการปัดใหม่
fold observations ตาม input order ก่อน batch เพื่อคง newer/older/generation/CLOSED/equal-version rules
transactionที่รวม candles+cursorยังอยู่ใต้ demand fence เดิม

TDD query-countแดงก่อนแก้แล้วgreen; exact18-decimalราคา/volume, duplicate versions,
older/CLOSED preservation, whole-batch conflict rejection และ partitionsข้ามเดือนผ่าน
Relevant tests96ผ่านใน11.29s; Ruff/format/mypy (221files)/import-linterผ่าน
Scoped spec/standards reviews ไม่มี findings ใน issue3; ไม่มี schema/grant/interface changes
issue4 DST cutoffและissue5 datetime overflowยังไม่แก้; ไม่มี commit/push

## Deep review issue4 fix (2026-10-07)

เพิ่ม pure retention_cutoff ที่ require aware reference, normalize UTC แล้วหัก timedelta365วัน
ทุก cutoff ใน initial/read/coalescing/prepare/write/cleanup ใช้ helper เดียวกัน
cleanup อ่าน database_now แล้วส่ง UTC cutoff เป็น bound parameter;
ไม่ใช้ timestamptz-calendar subtraction จึงไม่ขึ้นกับ session TimeZone/DST
strict less-than, boundary preservation,10,000-row budget,role/transactionและschema คงเดิม

TDD actual DB: clock injectionผ่าน test SQL wrapper, DELETEจริงใน session UTC/New York/Paris
พร้อมข้อมูลก่อน/ตรง/หลัง cutoff ข้าม spring/fall; New Yorkแดง2ก่อนแก้แล้วผ่านทั้ง6หลังแก้
pure ZoneInfo reference testผ่านด้วย; Relevant tests103ผ่านใน11.61s
Ruff/format/mypy/import-linterและ scoped reviewsสองด้านผ่าน; issue5ยังไม่แก้ ไม่มี commit/push

## Deep review issue5 — input datetime overflow

Authenticated GET/POST regression4กรณียืนยันว่า timezone offset ที่ขอบปี1/9999
ผ่าน Pydantic แต่ทำให้ CandleWindow UTC normalization เกิด OverflowError
ก่อนแก้ทั้ง4กรณีล้มเหลว; หลังแก้ `_window` แปลงเฉพาะ exception นี้เป็น ValueError
เพื่อให้ route ใช้ fixed422 `INPUT_REJECTED` เดิม ไม่เผย exception/raw input
ไม่เพิ่ม broad exception handler และไม่เปลี่ยน auth/CSRF/retention/business logic

Related core/venue/storage/worker/API suite141ผ่านใน12.63s, inherited Starlette warning1รายการ
Ruff lint/format239files, strict mypy221files, import-linter6contracts ผ่าน
ใช้ disposable project tiewtrade-f09-fix5 ที่port55445; ไม่ใช้ฐานข้อมูลเจ้าของ
issue1–5แก้ครบแล้ว แต่ผล full suite/frontend/E2E ด้านบนเป็นประวัติก่อน deep review
ยังไม่มี commit/push และยังต้องตรวจครบทุกด่าน/รีวิวสุดท้ายก่อน merge

## Backend final verification หลังแก้ issue1–5

ตามคำสั่งเจ้าของ ตรวจ backend full suite/lint/type/architecture ใหม่ทั้งหมด
บน disposable project `tiewtrade-f09-backend-final` port55445 และ migrate ถึง head
คำสั่ง `.venv/bin/pytest -o addopts='--strict-markers --strict-config' -m 'not venue_contract'`
ผ่าน **1,652 tests**, deselected1 live-contract ตาม policy, inherited deprecation warnings3
เวลา94.50s; ไม่มี skipped/failed tests และไม่เรียกตลาดจริง
Ruff lint/format239files, strict mypy221files, import-linter6contracts ผ่าน
หลังตรวจปิดเฉพาะ test project; ไม่มี production code changes/commit/push
Frontend/E2E/generated contract และ final review ยังต้องตรวจใหม่ก่อน merge

## Frontend final verification หลังแก้ issue1–5

ตามคำสั่งเจ้าของ รัน `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
ผ่านทุกคำสั่ง; Vitest113tests/13suitesใน4.36s, Vite production build145modulesใน421ms
`CI=1 npm run test:e2e` ผ่าน9testsใน44.5s โดย Playwright เปิด API/frontend servers ใหม่
ใช้ disposable project `tiewtrade-f09-e2e-check` port55445 และฐานใหม่ `tiewtrade_e2e_f09_final`
bootstrap roles/event trigger และ migrate head; worker ใช้ FakeVenue ตาม test policy
ไม่เรียกตลาดจริงและไม่ใช้ฐานข้อมูลเดิมของเจ้าของ; ปิด test project หลังตรวจ
มี Node color-environment warning ของ test runner; ไม่มี test failures
Generated contract และ final review ยังต้องตรวจใหม่ก่อน merge; ไม่มี code changes/commit/push

## Generated API contract final verification หลังแก้ issue1–5

ตามคำสั่งเจ้าของ สร้าง `backend/openapi.json` ด้วย
`.venv/bin/python -m tiewtrade.services.api.openapi_export` แล้วสร้าง
`frontend/src/api-types.ts` ด้วย `npm run gen:api` รวม2รอบ
SHA256เทียบทั้งสองไฟล์กับ snapshot ก่อนตรวจผ่านทุกครั้ง (byte-identical)
ไม่มี generated drift และไม่มีการเปลี่ยนเนื้อหาไฟล์ generated ในการตรวจนี้
เทียบกับ working tree ปัจจุบัน เพราะ F-09 ยังไม่commit; ความต่างจาก HEAD เป็น contractใหม่ของF-09
`npm run typecheck` ผ่าน; contract gate2testsผ่านใน3.51s
ทั้ง positive contract และ negative canary ที่เปลี่ยนชื่อfieldทำให้ชนิดข้อมูลไม่ตรง
Backend/frontend/E2E/contract ตรวจใหม่แล้ว; final review ยังรอ ไม่มี commit/push

## Final deep review และ Docker verification

Standards/Spec parallel reviewers ตรวจ git diff HEAD และ untracked F-09 files
กับ approved requirements/plan/validation และ surrounding code; ไม่พบ actionable findings
ผล final deep review **APPROVED**; ไม่มีการแก้ code ระหว่าง review
หลัง ownerสั่งเริ่มขั้นส่งงาน สร้าง Linux API/frontend/migration images ใหม่ด้วย
disposable project `tiewtrade-f09-smoke-final` ports55446/8113/5183
migration/APIhealth/UIproxyhealthผ่าน; actual CLI `--once` ใน imageใหม่ผ่านFakeVenue
บันทึก1,000observationsด้วยroleMARKET_DATA โดยไม่มี live calls
ปิด smoke project หลังตรวจ; owner data/F-08 previewไม่ถูกแก้
local gatesครบและพร้อม commit/push/PR/CI/merge ตามคำสั่งเจ้าของ

## Limits carried forward

REST remains UNCONFIRMED, including historical observations. Presence/freshness/finality are separate.
Refresh is request-driven; no continuous websocket/polling chart/indicator implementation is included.
Unknown listing/history and upstream corrections remain explicit; local retention is not proof of365-day availability.
Reservation floor10 is a local policy, not a measured tariff; shared-IP guard across processes is still a deployment prerequisite.
Partitions are pre-created by migrator; rolling maintenance/scheduling belongs to F-31. No runtime DDL granted.
Orders/balances/positions/PnL/leverage/margin/liquidation/Live enablement were not added in F-09.
