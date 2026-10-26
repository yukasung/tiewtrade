# F-37 — รายการคู่เทรดที่รองรับและการจัดการ — Validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-24; amended 2026-10-25 ให้ Live cancellation/reconciliation ของ V-10 รอ F-22/F-23 โดย Paper/catalog safety ยังเป็น candidate gate**

อ้างอิง requirements: **Approved 2026-10-24**

## “เสร็จ” หมายถึง

| # | เกณฑ์ | ตรวจอย่างไร | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | migration seed BTC/USDT และ ETH/USDT โดยไม่แตะ trading/market history; เอา hard-coded pair checks/counts/scheduler SQL ออก; คู่ที่สามเดินครบ prepare/activate/remove/re-add; up/down/up ปลอดภัยและ downgrade ปฏิเสธเมื่อมี runtime history | PostgreSQL migration integration, pg catalog/source gate + row digests ก่อน/หลัง | พัฒนา + candidate | **Passed — M1 + M5 evidence** |
| V-02 | catalog history/revision/audit เพิ่มอย่างเดียว แก้/ลบ/truncate และ revision ถอยหลังไม่ได้ทุก runtime role | privilege/trigger tests ด้วย role จริง | พัฒนา + candidate | **Passed — M1 + M5 evidence** |
| V-03 | bootstrap role ไม่เป็น owner/superuser/BYPASSRLS ไม่มี table privilege, สร้างได้เฉพาะ owner คนแรกที่เปิด TOTP และเรียกซ้ำไม่ได้ | isolated DB + CLI integration/negative matrix | พัฒนา + candidate | **Passed — M1 + M5 evidence** |
| V-04 | Trader เปลี่ยน catalog/ดู admin preview ไม่ได้; Admin/Owner ทำได้เมื่อ TOTP ใหม่ถูกต้องเท่านั้น; recovery grant ใช้แทนไม่ได้ | API auth/routing/DB-function tests รวม request ดัดแปลง | พัฒนา + candidate | **Passed — M5 evidence** |
| V-05 | เพิ่มได้เฉพาะ normalized `BASE/USDT` ที่ Binance TH รายงาน Spot/TRADING พร้อม filters; unknown, non-USDT, non-Spot, halted, malformed, stale และ venue unavailable fail closed | FakeVenue fixtures + bounded public venue contract แยก | พัฒนา; contract ตามรอบ | **Passed for candidate — FakeVenue/error matrix; public contract แยกตามรอบ** |
| V-06 | pair อยู่ PREPARING จน constraints, fresh price และ candle/indicator 8 timeframe มี proof revision เดียวกัน; proof ขาด/เก่า/คนละ revision activate ไม่ได้ | DB/service integration และ restart during preparation | พัฒนา + candidate | **Passed — M5 evidence** |
| V-07 | API/frontend ใช้ server catalog/revision ไม่มี static BTC/ETH allowlist หรือ generated dynamic enum เหลือใน runtime callers | source gate + OpenAPI generation + contract tests | พัฒนา + candidate | **Passed — M5 evidence** |
| V-08 | shared pair fence ทำให้ Paper opening admission/match ที่ commit หลัง REMOVED commit เกิดไม่ได้ ทั้ง race ก่อน/หลัง submit, queue, claim, dispatch และ active LIMIT matching; lock order ไม่ deadlock และ catalog read/protocol failure fail closed | deterministic barriers และ deadlock/lock-order assertions บน PostgreSQL + engine integration | พัฒนา + candidate | **Passed — M5 evidence** |
| V-09 | position เดิมไม่ถูกแตะและคำสั่งลดจริงขนาดไม่เกิน position ยังได้; คำสั่งเกิน position, BUY หรือ opening path อื่นถูกปฏิเสธ | core property/examples + Paper integration พร้อม exact amounts | พัฒนา + candidate | **Passed — M5 evidence** |
| V-10 | queued opening ถูก terminal reject, Paper open entry order ไม่ fill หลัง removal, reduce-risk/TP/SL คงอยู่; durable effect ต้องแสดง `PARTIAL` เมื่อ dependency ยังไม่พร้อมและ pair ยัง inactive; Live fill/partial fill/unknown outcome ที่เกิดก่อนหรือระหว่าง cancel ต้อง reconcile balance/position/order จริงเมื่อ F-22/F-23 พร้อม | Paper engine effect integration, retry/idempotency/restart; Live simulated venue ordering/reconciliation หลัง F-22/F-23 | Paper/catalog: พัฒนา + candidate; Live: หลัง F-22/F-23 | **Paper/catalog Passed — M5 evidence; Live Pending Integration — owner approved 2026-10-25** |
| V-11 | add/remove replay ด้วย key เดิมคืนผลเดิม, payload ต่าง conflict; concurrent expected revision ไม่มี lost update และสร้าง audit/effect ครั้งเดียว | PostgreSQL concurrent integration | พัฒนา + candidate | **Passed — M5 evidence** |
| V-12 | Redis หาย, process restart, delayed/stale notification และ worker revision เก่าไม่ทำให้คู่กลับ activeหรือสร้าง demand/job ใหม่; mutation ถูกปฏิเสธเมื่อมี missing/old heartbeat, live old lease หรือ mixed deployment generation และเปิดได้หลัง drain/protocol gate ครบ | failure/recovery + mixed-version rollout integration ทุก affected process | พัฒนา + candidate | **Passed — M5 evidence** |
| V-13 | inactive historical pair ยัง decode/read order/fill/balance/position/ledger/audit ได้ และ removal ไม่ลบ history หรือ market rows | migration/storage regression + before/after digests | พัฒนา + candidate | **Passed — M5 evidence** |
| V-14 | removed pair ไม่มี public chart/backfill demand ใหม่ แต่มี fresh maintenance price/constraints ขณะมี exposure/order และหยุดได้หลัง durable zero-exposure proof | market-data/engine integration with controlled clocks | พัฒนา + candidate | **Passed — M5 evidence** |
| V-15 | impact preview คืน aggregate counts + snapshot time เท่านั้น ไม่รั่ว owner/order detail และ stale/incomplete ถูกระบุจริง | API schema, DB authorization และ browser assertions | พัฒนา + candidate | **Passed — M5 evidence** |
| V-16 | audit success/failure มี ownership ตาม requester, PLATFORM/SYSTEM actor ที่ถูกต้อง, action/pair/revisions/typed reason code/outcome/error โดยไม่มี secret; free-text/unknown reason ถูกปฏิเสธ; bootstrap/async activation/audit failure rollback mutation และ mutation successไม่มีทางขาด audit; market-data ไม่มี audit privilege | typed event/unit + DB RLS/privilege/transaction/redaction tests | พัฒนา + candidate | **Passed — M1 + M5 evidence** |
| V-17 | หน้า Admin ใช้ template/shared components; Trader ไม่เห็น navigation; keyboard/focus, 375/768/1440, ไทย/อังกฤษ, loading/empty/error/stale/pending/partial/conflict และ TOTP modal ถูกต้อง | component tests + real Chromium API/DB E2E + screenshots | พัฒนา + candidate | **Passed — 261 frontend tests + Chromium 2/2; M5 evidence** |
| V-18 | removal event ทำให้บอท F-20 หยุด durable ไม่ auto-resume และ F-26 แสดง in-app notification แก่ผู้ได้รับผล | cross-feature integration/E2E | หลัง F-20/F-26 ก่อน Completed | **Pending Integration** |
| V-19 | catalog churn และ preparation/maintenance หลายคู่ไม่ทำลาย latency/freshness/recovery/memory/queue bounds เดิม; ไม่มี unbounded task/subscription growth | full workload/stress/restart/resource profile ตาม release-validation plan ที่ต้องได้รับอนุมัติและระบุ fixture digest/pair count/churn/mix/duration/restarts/replicas/threshold mapping ก่อนรัน | release checkpoint | **Pending Full Validation — ยังไม่มี approved numeric profile** |
| V-20 | ไม่ส่ง Live order, ไม่เปิด Live และไม่มี endpoint/admin path สั่งหรือปิด position แทนผู้ใช้ | network deny/fake adapters/source gate + authorization E2E | พัฒนา + candidate | **Passed — M5 evidence; no Live order sent** |

## การเลือกตรวจตามผลกระทบ

| พฤติกรรม/ความเสี่ยง | หลักฐานเดิมที่ใช้ได้ | ช่องว่างที่ต้องตรวจเพิ่ม |
|---|---|---|
| Money/Quantity และ venue symbol/filter parsing | F-02/F-33 tests เดิม | เพิ่มเฉพาะ dynamic symbol, USDT policy และ malformed/venue-state cases; ไม่เขียน arithmetic ใหม่ |
| TOTP reverify/route default-deny | F-06 authentication/routing tests | เพิ่ม catalog routes, recovery-grant rejection, role check และ bootstrap |
| append-only audit/idempotency | F-04 และ Paper command patterns | เพิ่ม global revision, platform actor, catalog details และ concurrent mutation |
| Paper orders/positions | F-14/F-15 core/storage/dispatch evidence | static pair dependency เปลี่ยน จึงต้อง rerun affected admission, dispatch, cancel, wallet/position safety และ migration tests |
| market-data/indicator | F-09–F-12/F-38 correctness และ release evidenceที่ source ไม่ได้รับผลยังใช้ได้ | pair discovery/hot reload/readiness/maintenance/restart เปลี่ยน จึงตรวจ affected workers/contracts ใหม่; ไม่รัน workload เต็มทุก milestone |
| Frontend shell/components | shared controls และ chart/account browser evidenceเดิม | เพิ่ม Admin visibility, dynamic catalog, modal states, aggregate truthfulness และ responsive page |
| Bot/notification | ยังไม่มี implementation | contract test ตอน F-37 และคง V-18 Pending จน F-20/F-26 integration จริง |

เมื่อ source, migration, generated contract หรือ worker topology เปลี่ยนจาก checkpoint ให้ทำเครื่องหมาย
หลักฐานที่พึ่งส่วนนั้นว่าใช้ไม่ได้และ rerun เฉพาะ affected set ก่อน; full suite รันเมื่อ candidate นิ่ง
ไม่ใช้ focused pass แทน candidate gates หรือ V-19/V-18

## เทสต์ที่ต้องมี

### ตัวเลขจริง

- revision/expected revision เพิ่มทีละหนึ่งและไม่สูญหายภายใต้ concurrent mutation
- impact counts เทียบ exact rows แยก bot/open-entry/protective/reduce-risk/position โดยไม่คืน ID ผู้ใช้
- active/preparing/maintenance series เท่ากับจำนวน pair × 8 timeframe ตาม snapshot เดียวกัน
- Money/Quantity/order constraints ใช้ชนิดเดิมและ exact decimal; ไม่มี `float`/`Decimal` เปล่า

### คุณสมบัติ (Hypothesis)

- ลำดับ add/remove/replay/conflict/restart ใด ๆ ให้ revision monotonic และ current view เท่ากับ
  event ล่าสุด โดย active set ไม่มี PREPARING/REMOVED
- ชื่อ base ที่กฎเดิมยอมรับ normalize เหมือน `Symbol`; quote อื่นและ base=quote ถูกปฏิเสธ
- order size เทียบ held quantity: `<=` ยังลดความเสี่ยง, `>` ไม่ใช่ และ catalog removal
  เปลี่ยนเฉพาะผลของ opening path
- interleaving submit/remove/claim/retry/cancel/match ทำให้ Paper ไม่มี opening fill ที่ commit หลัง
  removal revision commit; Live fill ที่ venue รับก่อน cancel ต้องถูก reconcile ไม่สูญหายหรือทำซ้ำ

### ความปลอดภัยการเทรด

- ทุก order path ผ่าน admission เดียวกันและ engine authoritative recheck ไม่มีทางลัด
- fail closed เมื่อ catalog, revision, constraints, price หรือ readiness proof อ่านไม่ได้/เก่า
- removal ไม่บังคับปิด position, ไม่ลบประวัติ และไม่กันทาง reduce-risk
- pending/open opening orders ถูกทิ้งหรือยกเลิกตามคำตัดสิน; protective orders ไม่ถูกยกเลิก
- Live fill/partial fill/unknown cancel outcome ที่แข่งกับ removal ต้องอัปเดต order, balance และ
  position แบบ idempotent ตามความจริงของ venue; removal ไม่ใช่หลักฐานว่า order ไม่ fill;
  ส่วนนี้คง Pending Integration จน F-22/F-23 พร้อมตาม amendment 2026-10-25
- bot/notification contract durable และห้าม auto-resume; V-18 ต้องผ่านก่อน Completed
- automated validation ใช้ Paper/FakeVenue เท่านั้นและ network guard กัน private/live order endpoint

## ตรวจด้วยมือ

1. Bootstrap owner คนแรกด้วย CLI ใน isolated environment; ตรวจว่า credential ไม่อยู่ใน API
   container และรอบสองถูกปฏิเสธ
2. Login เป็น Trader: ไม่มีเมนู Admin และเปิด URL/ยิง request เองได้ 404/403 ตาม contract
3. Login เป็น Owner/Admin: เพิ่มคู่ด้วย TOTP+reason เห็น PREPARING แล้ว ACTIVE เมื่อ proof ครบ
4. ถอนคู่ที่ fixture มี position/open orders: modal แสดง snapshot/คำเตือน, คู่หายจาก opening UI
   ทันที, cleanup pending/partial ตรงจริง และคำสั่งลด position ยังทำได้
5. refresh/restart API, engine, market-data และ Redis ระหว่างแต่ละสถานะ; UI/revision ไม่ย้อน
6. ตรวจหน้า 375/768/1440, light/dark, keyboard-only, focus restore, ไทย/อังกฤษ และ screen-reader labels
7. เมื่อ F-20/F-26 พร้อม ตรวจผู้ใช้จริงใน Paper ว่าบอทหยุดและเห็น in-app notification โดยไม่
   auto-resume หลังเพิ่มคู่คืน

## ด่านที่ต้องเขียว

### ระหว่างพัฒนา

- targeted core/infra/API/engine/market-data/indicator/frontend tests ตาม milestone และ diff
- PostgreSQL/Redis integration สำหรับ transaction, RLS, locking, revision, restart และ dispatch race
- mixed-version deployment/protocol heartbeat tests ก่อนเปิด catalog mutation
- affected Ruff/format/mypy/import checks, frontend lint/type/build และ OpenAPI contract เมื่อ input เปลี่ยน
- ไม่รัน V-19 full workload โดยปริยาย; correctness/order safety V-08–V-14 เลื่อนไม่ได้

### Candidate ก่อน merge

- backend full regression (เว้น venue contract ตาม config), Ruff check/format, strict mypy,
  import-linter และ migration fresh + upgrade/downgrade guard
- frontend full Vitest, ESLint, TypeScript, production build และ generated API types ตรง OpenAPI
- real Chromium E2E สำหรับ auth/Admin/add/remove/partial/reduce-risk/restart ที่ไม่ส่ง Live order
- required CI ทุก job ผ่านบน commit/source เดียวกัน และ review Critical/High ไม่มีค้าง
- V-18 คง Pending Integration และ roadmap ระบุ Development Complete ไม่ใช่ Completed
- V-01–V-09, V-10 เฉพาะ Paper/catalog contract, V-11–V-17 และ V-20 ผ่านจึงประกาศ
  Catalog/Order Safety Ready เพื่อปลด F-16 ได้; Live subpart ของ V-10 คง Pending F-22/F-23 และ milestone นี้
  ไม่เปลี่ยน V-18/V-19 เป็น Passed

### ก่อน Completed / release

- V-18 ผ่านหลัง F-20/F-26 integration
- release-validation plan ของ V-19 ได้รับอนุมัติก่อนรัน และ V-19 ผ่านพร้อม environment,
  runtime versions, fixture digest/pair count, churn/mix, thresholds, duration, resource results
  และ failure/recovery artifacts
- เกณฑ์ Not Run/Partial/Failed ไม่มีค้าง; หลักฐานตรง source สุดท้ายและไม่ใช้ targeted run
  ทดแทน full validation
