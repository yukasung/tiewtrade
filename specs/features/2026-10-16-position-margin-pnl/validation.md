# Position, Margin และ PnL — Validation

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-16
วันที่: 2026-10-16

## “เสร็จ” หมายถึง

| # | ครอบคลุม | เกณฑ์ | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-1 | RQ-1/RQ-2/RQ-3 | core ใช้ `Money`/`Quantity` เท่านั้น ไม่มี float/Decimal ภายนอก money package; Spot position ติดลบ/short/margin/liquidation ถูกปฏิเสธ | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-2 | RQ-1/RQ-9/RQ-13 | weighted-average examples และ properties ให้ quantity, total cost, realized PnL และ full-close remainder ตรงทุกหลัก | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-3 | RQ-4/RQ-13 | order intent/ack ไม่เปลี่ยน position; partial fill เปลี่ยนเฉพาะปริมาณ/quote ที่ยืนยันแล้ว | พัฒนา + candidate | **Development Passed** — writer รับเฉพาะ confirmed `ExecutionFact`; F-15 producer gate pending |
| V-4 | RQ-5/RQ-6 | exact replay ไม่เปลี่ยน revision/audit/effect; ID/payload conflict, gap, duplicate sequence และ reverse order fail closed; retry conflict fingerprint เดิมไม่เพิ่ม conflict/audit ซ้ำ | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-5 | RQ-7/RQ-9/RQ-10 | RECORD/REPLACE/VOID append-only และ rebuild จาก effective stream ให้ projection เดิมทุกครั้ง; correction คืน exact compensating effects และ append external-fee history; chain แตกแขนง/ขาดเป็น conflict ส่วน ledger/wallet parity เป็น F-15 integration gate | พัฒนา + candidate | **Development Passed**; F-15 ledger integration pending |
| V-6 | RQ-2/RQ-13/RQ-16 | base/quote/third-asset fee และ rebate ทุกฝั่ง BUY/SELL ให้ exact effects; invalid unit/sign/fee เกิน quantity/proceeds ถูกปฏิเสธ | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-7 | RQ-11/RQ-12 | fresh latest trade คำนวณ unrealized ตรง; stale/disconnected/unreconciled/generation mismatch/unit mismatch คืน unavailable ไม่มีเลขเก่าหรือศูนย์ปลอม | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-8 | RQ-7/RQ-8/RQ-9/RQ-10 | PostgreSQL FK/CHECK/FORCE RLS/grants/append-only triggers กันข้าม owner/mode/episode; API/SCAN อ่านหรือเขียน F-14 state ไม่ได้ | พัฒนา + candidate | **Development Passed**; candidate security gates pending |
| V-9 | RQ-7/RQ-15/RQ-19 | fill writers พร้อมกัน, fill แข่ง episode/reset lock และ snapshot readers ให้ผล serializable; writer ไม่เขียน closed/stale episode | พัฒนา + candidate | **Partial** — writer/snapshot race ผ่าน; reset/open-order integration รอ F-15 |
| V-10 | RQ-5/RQ-7/RQ-9/RQ-16 | fault injection ทุก F-14 write boundary รวม event/projection/activity/external-fee/audit, cancellation, statement timeout และ deferred commit failure rollback ทั้งชุด; retry เดิมมีผลครั้งเดียว ส่วน order/ledger faults เป็น F-15 integration gate | พัฒนา + candidate | **Development Passed** สำหรับ F-14 boundaries; F-15 order/ledger pending |
| V-11 | RQ-14/RQ-15 | activity tri-state/lifecycle: missing/UNKNOWN/CONFLICTED/error/stale revision ไม่เป็น idle; READY ต้องมาจาก atomic source initialization; conflict ไม่กลับ READY เอง; READY zero/positive แยกถูก; F-13 reset ยังคง `ACTIVITY_UNKNOWN` ใน F-14 | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-12 | RQ-1/RQ-18 | fixture เดียวผ่าน shared fold สำหรับ Paper/Live adapter boundary ให้ state/effects/errors ตรงกัน ไม่มี implementation สูตรคู่ขนาน | พัฒนา + candidate | **Development Passed** — scenario matrix และ correction parity; candidate pending |
| V-13 | RQ-8/RQ-18 | Paper entrypoint/tests ทำงานโดยไม่มี venue key/network/Live executor; negative fixtures ที่ import/call dependency ต้องทำ gate แดง | พัฒนา + candidate | **Development Passed** — AST negative fixture + isolated runtime import; candidate pending |
| V-14 | RQ-10/RQ-17 | position changes/corrections/conflicts มี typed audit exact owner/episode/pair/result หนึ่งครั้ง ไม่มี secret/raw payload และแก้ย้อนหลังไม่ได้ | พัฒนา + candidate | **Development Passed**; candidate pending |
| V-15 | RQ-7/RQ-8/RQ-10 | migration `0031→0032→0031→0032` บนฐานว่างผ่าน; downgrade เมื่อมี F-14 data ปฏิเสธโดย data เดิมอยู่ครบ | candidate | **Passed 2026-10-16** บน PostgreSQL แยกพอร์ต 55439 |
| V-16 | RQ-1 to RQ-19 | relevant backend regression, lint, format, types, import contracts, migration/security/secret gates และ required CI ผ่านบน source สุดท้าย | candidate ก่อน merge | **Passed 2026-10-18** - local full backend 100%; CI run 39097281613 ผ่านครบ 6 jobs, backend 2818 passed |
| V-17 | nonfunctional | deterministic rebuild และ snapshot workload ตามงบที่อนุมัติ ไม่ล็อก owner อื่นและไม่มี unbounded memory/query growth | release checkpoint | **Pending Full Validation** |

F-14 จะเป็น **Development Complete** ได้เมื่อ V-1–V-16 ผ่านและ review ไม่มี Critical/High
โดย V-17 คง Pending Full Validation ตาม testing standard งานนี้ไม่ทำให้ F-13 Completed:
reset success/open-order race ยังต้องรอ F-15 และ validation amendment ของ F-13

## ตัวเลขตัวอย่างที่ต้องพิสูจน์

ทุกค่าผ่าน `Money`/`Quantity`; expected results ต้องเขียน exact string ไม่ใช้ float:

1. BUY `2 BTC` ด้วย confirmed quote `200 USDT`, ไม่มี fee → quantity `2 BTC`, cost
   `200 USDT`, realized `0 USDT`
2. BUY เพิ่ม `1 BTC`/`130 USDT` → quantity `3 BTC`, cost `330 USDT`; SELL `1 BTC`
   ได้ `150 USDT` → released cost `110 USDT`, remaining cost `220 USDT`, realized `40 USDT`
3. ปิด `2 BTC` ที่เหลือด้วย proceeds `180 USDT` → remaining quantity/cost เป็นศูนย์,
   realized cumulative `0 USDT`; ห้ามเหลือเศษจาก average division
4. BUY `1 BTC`/`100 USDT`, base fee `0.001 BTC` → quantity `0.999 BTC`, cost `100 USDT`
5. BUY `1 BTC`/`100 USDT`, quote fee `0.1 USDT` → quantity `1 BTC`, cost `100.1 USDT`
6. SELL `0.5 BTC`/`60 USDT`, quote fee `0.06 USDT` → proceeds ที่เข้า realized formula
   `59.94 USDT`
7. third-asset fee `0.0002 BNB` → pair quantity/cost/PnL ไม่เปลี่ยนเพราะ fee แต่มี
   external fee effect exact หนึ่งรายการ
8. rebate ใช้ signed negative effect และต้องไม่ทำ inventory delta/cost/proceeds ผิดทิศ
9. precision สูงสุด/ต่ำสุด, ค่าใกล้ขอบ, division ไม่ลงตัว และผลลบของ realized/unrealized
   ต้องไม่ overflow, double-round หรือแปลง scientific notation
10. unit mismatch ทุกคู่ เช่น BTC quantity กับ ETH pair หรือ THB quote กับ USDT pair ต้องดัง

## Property tests

- fold event stream เดิมซ้ำกี่ครั้งให้ state เดิมและ canonical serialization เดิม
- แบ่ง BUY เดียวเป็น partial fills ที่ quote/base/fee รวมเท่ากันให้ economic totals เท่ากัน
  ภายใต้กฎปัดที่อนุมัติ; ถ้า boundary ทำให้ต่างต้องมี expected remainder rule ชัด
- quantity และ total cost ไม่ติดลบทุก prefix ของ valid stream
- full close ล้าง total cost พอดี และผลรวม released cost เท่ากับ cost ที่เคยรับเข้าหลัง correction
- realized increments รวมเท่ากับ cumulative realized state
- rebuild จาก immutable events เท่ากับ incremental projection สำหรับทุก valid stream
- transition ของ correction เท่ากับ net economic difference ก่อน/หลัง rebuild;
  F-15 ต้องพิสูจน์ว่า compensating ledger รักษา wallet/position/PnL parity
- exact replay แทรกตำแหน่งใดไม่เปลี่ยน state; conflicting replay เปลี่ยน availability เป็น conflict
- owner/mode/episode/pair สลับกันไม่สามารถเปลี่ยน state ของกันและกัน
- unavailable price ไม่สร้าง numeric unrealized PnL สำหรับทุก nonzero position

ใช้ bounded Hypothesis examples ระหว่างพัฒนา; seed/replay artifact ของ failure ต้องเก็บได้
ชุด workload ขนาดใหญ่รันเฉพาะ release checkpoint V-17

## Transactions, concurrency และ recovery

ทดสอบกับ PostgreSQL จริงและ role จริง:

1. worker สองตัวส่ง execution เดียวกันพร้อมกัน → event/projection/audit/effect ชุดเดียว
2. execution ต่าง ID sequence เดียวกัน → มีผู้ชนะไม่เกินหนึ่งและ source conflict/rollback
   ตาม contract ไม่มี projection ผสม
3. execution ต่อเนื่องคนละ symbol ของ owner เดียวรักษาลำดับ account writer;
   owner ต่างกันเดินต่อได้ ไม่เกิด global serialization
4. barrier race ระหว่าง writer กับ episode transition/reset lock → writer อยู่รอบเก่าหรือ reset
   เห็น activity ล่าสุดครบชุด ห้ามเขียนข้ามหลัง episode ปิด
5. snapshot อ่านแข่ง event/correction → ได้ revision เก่าหรือใหม่ครบชุด ไม่มี quantity/cost/PnL ปน
6. cancel/timeout หลัง INSERT event, หลัง projection, หลัง external fee, หลัง activity revision
   และหลัง audit → rollback ทั้ง transaction, connection คืน pool ใช้ต่อได้
7. deferred constraint trigger ล้มตอน COMMIT → ไม่มี event/projection/activity/audit ครึ่งชุด;
   retry identity เดิมสำเร็จครั้งเดียวหลังเอา fault ออก
8. restart/lost response หลัง commit → replay อ่านผลเดิม ไม่เพิ่ม economic effect
9. correction ล้มระหว่าง rebuild หรือ F-14 write → event/projection/activity/external-fee/audit
   กลับเป็นชุดก่อน correction ทั้งหมด; compensating ledger failure อยู่ใน F-15 gate
10. malformed/conflicting event ของ owner หนึ่งไม่ขวาง owner อื่น และไม่มี unbounded retry loop
11. crash ทุก boundary ของ source initialization ไม่เหลือ READY ที่ไม่มี baseline;
    restart/retry ใช้ proof เดิมครั้งเดียว และ conflict ไม่มีทางกลับ READY อัตโนมัติ

ห้ามใช้ mock database ปิดเกณฑ์ transaction/race และต้องตรวจจำนวนแถวพร้อม exact financial values
หลัง fault ทุกกรณี

## Database, security และ audit

- API/ENGINE_SCAN/foreign owner/ไม่มี `app.user_id` อ่านหรือเขียนข้อมูลไม่ได้;
  error ไม่บอกว่ามี foreign row
- UPDATE/DELETE/TRUNCATE events/external fees ถูก DB ปฏิเสธทุก role application
- FK composite ปฏิเสธ wallet/episode/user/event ที่นำ UUID ของคนอื่นหรือคนละรอบมาประกอบ
- projection/activity เปลี่ยนได้เฉพาะ ENGINE path และห้ามย้าย owner/episode/pair
- audit schema/invariant/DB constraint ปฏิเสธ mode/owner/action/outcome/details ที่ไม่ตรง
- log/error/audit canary ไม่มี credential, cookie, raw source response หรือ DSN
- migration downgrade มีทั้งฐานว่างที่ผ่านและฐานมีข้อมูลที่ fail safely

## Parity และ isolation

ใช้ fixture contract เดียวเรียก core fold ผ่าน Paper adapter และ fake Live adapter ที่ไม่แตะ network:

- BUY/add/partial sell/full sell
- base/quote/third fee และ rebate
- duplicate/gap/conflict/correction
- stale/unavailable price
- overflow/unit/rounding errors

assert state, exact effects, errors และ canonical serialization เท่ากันทั้งหมด AST/import/runtime gate
ต้องพิสูจน์ว่า core ไม่ import infra/services/venues และ Paper persistence/fixtures ไม่โหลด
credential, HTTP client, venue factory หรือ Live executor Negative fixture ต้องทำ gate แดงจริง

Automated validation ห้ามส่ง Live order และห้ามเรียก Binance

## ตรวจด้วยมือ

F-14 ไม่มี UI/public API จึงไม่มี browser acceptance ใน feature นี้ ตรวจเอกสาร/ฐานข้อมูลแบบ read-only:

1. ดู immutable event/projection/activity ของ Paper episode ทดสอบและเทียบ exact expected values
2. ยืนยัน event correction เดิมยังอยู่ครบและ projection มาจาก effective chain ล่าสุด
3. ยืนยัน episode ใหม่มี activity `UNKNOWN` ไม่ใช่ `READY`
4. เรียก F-13 reset ผ่าน API เดิมและยืนยันว่ายังถูกปฏิเสธ `ACTIVITY_UNKNOWN`
5. ตรวจ process/env ของ Paper test ว่าไม่มี venue credential และ network call

ไม่ใช้ข้อมูลบัญชีจริง, API key จริง หรือ Live order ในการตรวจด้วยมือ

## ด่านและช่วงเวลารัน

### ระหว่างพัฒนา

- targeted core numeric/property tests ตาม operation ที่เปลี่ยน
- PostgreSQL migration/RLS/immutability/transaction tests ตาม write boundary ที่เปลี่ยน
- parity/isolation/negative gates ทุกครั้งที่แตะ dependency boundary
- Ruff/format และ targeted type/import checks ของไฟล์ที่เปลี่ยน

### Candidate ก่อน merge

- V-1–V-16 บน source สุดท้าย
- full backend suite เมื่อ candidate นิ่งหนึ่งรอบ พร้อม lint/format/mypy/import-linter
- migration upgrade/downgrade/re-upgrade และ DB role/security gates
- diff review เน้น Critical/High: duplicate effects, quantities, cost/PnL, owner/mode/episode,
  correction, commit/retry และ false-idle activity
- required CI ที่เกี่ยวข้องผ่าน; rerun เฉพาะเมื่อ failure ถูกจัดประเภทและมีเหตุผล

### Release checkpoint

- V-17 rebuild/snapshot/concurrency workload ขนาดที่อนุมัติและ resource observation
- ชุดยาวไม่รันโดยอัตโนมัติระหว่างพัฒนา; บันทึก `Pending Full Validation` จนเจ้าของสั่ง
- ผล targeted/candidate ไม่ใช้แทน V-17 และไม่เปลี่ยน Pending เป็น Passed โดยไม่มีหลักฐาน

หลักฐานทุกชุดต้องระบุ commit/diff identity, PostgreSQL roles/database, คำสั่ง, จำนวน tests,
เวลา, pass/fail/partial และยืนยันว่าไม่มี Live order/network call

## Amendment checkpoint — Approved 2026-10-16

เจ้าของอนุมัติย้ายการพิสูจน์ trade-ledger/wallet parity และ order/ledger fault boundaries ไป F-15
เพราะ F-15 เป็นเจ้าของ fill producer และ ledger semantics F-14 ยังคงต้องผ่าน exact-effect,
correction compensation และ atomic F-14 storage gates ทั้งหมด การย้ายนี้ไม่ถือว่า F-13 reset
พร้อมใช้งานและไม่ลดเกณฑ์ integration ก่อนเปิด reset success

## Development checkpoint — 2026-10-16

หลักฐานนี้เป็นของ branch `feature/f14-position-margin-pnl` จาก base `363ce96` บน working tree
ที่ยังไม่ commit ใช้ PostgreSQL แยก `tiewtrade-f14-pg` ที่พอร์ต `55439` และ role จริงของ
MIGRATOR/API/ENGINE/ENGINE_SCAN ไม่มี venue credential, Binance call หรือ Live order:

- `pytest tests/core/test_positions.py tests/core/test_position_parity.py tests/infra/positions -q`
  ผ่าน **57 tests** ในประมาณ 11 วินาที ครอบคลุม exact arithmetic, weighted cost, fee/rebate,
  correction, durable replay/conflict, RLS, append-only, concurrent writers, snapshot race,
  ทุก F-14 write boundary, cancellation, timeout และ deferred commit failure
- valuation test ผ่านซ้ำสองรอบบนฐานเดิม และครอบคลุม missing, fresh, disconnected,
  expired producer lease, generation mismatch, future timestamp, recovering และ stale โดยสถานะ
  ที่ไม่พร้อมไม่คืน numeric unrealized PnL
- `pytest tests/infra/audit -q` ผ่าน **115 tests**; Paper wallet regression ที่ไม่รวม destructive
  migration CLI test ผ่าน **23 tests**
- targeted F-14 + audit + trading-account regression ผ่าน **211 tests** ในประมาณ 16 วินาที
- Ruff format/check ผ่าน, targeted mypy ผ่าน **29 files**, core-purity ผ่าน **1 test**
  และ import-linter ผ่าน **7 contracts** (`PYTHONUTF8=1` บน Windows)
- migration `0031→0032→0031→0032` บนฐานว่างผ่าน และ populated downgrade ปฏิเสธโดยข้อมูล
  ยังอยู่ครบ; Alembic CLI ปกติบน Windows ยังติด cp1252 จาก comment ภาษาไทย จึงตรวจ migration
  ด้วย programmatic Alembic `Config` ซึ่งผ่าน
- รีวิว Critical/High พบ RQ-11 provenance ขาดจาก snapshot contract แล้วแก้ให้ activity คืน
  `user_id`, `mode` และ `source_proof`; หลังแก้ targeted suite และ static gates ผ่านซ้ำ
- รีวิวเชิงลึกพบและแก้ initialization exact retry หลัง source sequence เดินหน้า, projection
  completeness/DELETE permission, conflict revision, RECORD/REPLACE NULL shape, snapshot time และ
  credential dependency ทางอ้อม; regression ของแต่ละกรณีผ่าน

สถานะ coverage ปัจจุบัน: V-1–V-8 และ V-10–V-15 มีหลักฐานระดับ development ตามขอบเขต F-14;
V-9 ผ่านส่วน writer/snapshot concurrency แต่ reset success/open-order integration ยังเป็น gate ของ
F-15 ตาม amendment; V-16 ยัง **Pending Candidate Validation** เพราะยังไม่รัน full backend suite และ
required CI บน source สุดท้าย; V-17 คง **Pending Full Validation** ตามเดิม ดังนั้น F-14 ยังเป็น
**In Progress** และยังไม่ใช่ Development Complete/Completed

## Critical/High remediation checkpoint — 2026-10-17

- แก้ multi-revision downgrade ที่เคยลบ schema F-14 แล้วค้างที่ revision `0031`: migration
  `0032` ตรวจ F-13 Paper wallet data ก่อน destructive DDL และปฏิเสธขณะที่ revision/table F-14
  ยังอยู่ครบ
- เพิ่ม regression ใน `tests/infra/paper_wallet/test_migration.py` ให้ตรวจ command เดิม,
  `alembic_version='0032'` และ `paper_position_activity` หลัง `downgrade 0030` ล้มเหลว
- Linux/PostgreSQL แยกพอร์ต `55439`: populated multi-revision downgrade regression ผ่าน **1 test**;
  empty `0032→0031→0032` ผ่าน; targeted core/position/migration ผ่าน **58 tests**
- Ruff check และ Ruff format check ของ migration/test ที่เปลี่ยนผ่าน
- V-16 ยัง **Pending Candidate Validation**: การเริ่ม full suite ใหม่บนฐานว่างถูกบล็อกก่อนถึง
  F-14 ที่ migration `0024` ด้วย `SOURCE_MAINTENANCE_SCOPE_REQUIRED`; ไม่ใช้ผล targeted แทน
  candidate gate และยังไม่เปลี่ยนสถานะเป็น Development Complete

## Candidate validation retry — 2026-10-17

- แก้ test harness ให้ใช้ PostgreSQL/Redis ผ่าน dedicated Docker network และ mount root-level
  `specs/`, `config/`, `.github/`, `backend/` และ `compose.yaml` ที่ tests อ้างถึง; migration ถึง
  `0032` ผ่านบนฐานใหม่สะอาด
- full backend fail-fast รอบแรกหลัง harness ครบผ่านถึง 66% แล้วหยุดที่ flaky timing test
  `test_source_deadline_bounds_attempts_and_persists_timeout_retry`; รัน test เดิมแยกแล้วผ่าน **1 test**
- full backend fail-fast รอบยืนยันผ่านจุดเดิมถึง 68% แล้วหยุดที่ minute-boundary race ใน
  `test_seed_uses_database_clock_despite_two_hour_caller_skew` (เวลาห่าง boundary ประมาณ 2.6 ms);
  รัน test เดิมแยกแล้วผ่าน **1 test**
- failure ทั้งสองอยู่ใน F-09 market-data ingestion ที่ F-14 ไม่ได้แก้ และไม่ทำซ้ำเมื่อรันเดี่ยว;
  ตามกฎห้ามแก้โค้ดนอกขอบเขต จึงบันทึกเป็น candidate blocker แยกและไม่แก้ใน branch F-14
- static gates บน source code สุดท้ายผ่าน: Ruff check, Ruff format **441 files**, mypy **407 files**
  และ import-linter **7 contracts**; final diff review ไม่พบ Critical/High ใหม่หลังแก้ downgrade
- V-16 ยังคง **Pending Candidate Validation** เพราะยังไม่มี full backend suite สีเขียวหนึ่งรอบและ
  required CI บน source สุดท้าย; F-14 จึงยังเป็น **In Progress**

## Candidate validation after F-09 stabilization - 2026-10-18

- PR #16 แก้ flaky timing tests ของ F-09 และ merge เข้า main ที่ 518ee09; CI ผ่านครบ 6 jobs รวม backend full suite และ browser E2E
- F-14 fast-forward มาที่ 518ee09 แล้ว migration ถึง 0032 และ full backend candidate บน PostgreSQL/Redis แยกผ่านครบ 100% โดยไม่มี test failure
- การรันสองครั้งแรกหยุดด้วย FileNotFoundError เพราะ candidate harness ไม่ได้ mount README.md/frontend และ backend/scripts; หลังแก้เฉพาะ harness และสร้างฐานข้อมูลใหม่ การรันครบผ่าน ผลสองครั้งแรกไม่นับเป็น product failure
- static gates ของ F-14 source ผ่านก่อนหน้า: Ruff check/format 441 files, mypy 407 files และ import-linter 7 contracts; F-09 commit ที่เพิ่มเข้ามาผ่าน static/full CI ของ PR #16
- final Critical/High review ของ diff F-14 และ dependencies ที่เกี่ยวข้องไม่พบ finding ใหม่
- V-16 ปิดแล้ว: local candidate ผ่าน และ required CI run 39097281613 ผ่านครบ 6 jobs หลัง rerun backend disconnect timing variation; F-14 พร้อมสถานะ **Development Complete**
## Required CI checkpoint - 2026-10-18

- PR #17 commit 86a8edc รัน CI 39097281613 ผ่านครบ 6 jobs: config, API contract, frontend, container, browser E2E และ backend
- backend รอบแรกผ่าน 2817 tests และล้ม 1 F-11 disconnect test เพราะ SQLSTATE 08003 ถูกแปลเป็น InfraError; failed-job rerun โดยไม่แก้ source ผ่าน 2818 tests, 2 deselected
- V-16 ผ่านครบและ final Critical/High review ไม่มี finding; F-14 เลื่อนเป็น **Development Complete**
- V-17 ยังคง **Pending Full Validation** และไม่ถือว่า F-14 Completed หรือพร้อม production
