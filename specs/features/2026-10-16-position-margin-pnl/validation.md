# Position, Margin และ PnL — Validation

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-16
วันที่: 2026-10-16

## “เสร็จ” หมายถึง

| # | ครอบคลุม | เกณฑ์ | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-1 | RQ-1/RQ-2/RQ-3 | core ใช้ `Money`/`Quantity` เท่านั้น ไม่มี float/Decimal ภายนอก money package; Spot position ติดลบ/short/margin/liquidation ถูกปฏิเสธ | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; Required CI checkpoint ด้านล่าง |
| V-2 | RQ-1/RQ-9/RQ-13 | weighted-average examples และ properties ให้ quantity, total cost, realized PnL และ full-close remainder ตรงทุกหลัก | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; weighted-cost/property gates ตาม Required CI checkpoint |
| V-3 | RQ-4/RQ-13 | order intent/ack ไม่เปลี่ยน position; partial fill เปลี่ยนเฉพาะปริมาณ/quote ที่ยืนยันแล้ว | พัฒนา + candidate | **Passed** — F-14 candidate 2026-10-18; F-15 V-3/V-10 และ V-18 final candidate ยืนยัน confirmed partial fills |
| V-4 | RQ-5/RQ-6 | exact replay ไม่เปลี่ยน revision/audit/effect; ID/payload conflict, gap, duplicate sequence และ reverse order fail closed; retry conflict fingerprint เดิมไม่เพิ่ม conflict/audit ซ้ำ | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; closed-episode replay เป็น remediation 2026-10-25 ด้านล่าง |
| V-5 | RQ-7/RQ-9/RQ-10 | RECORD/REPLACE/VOID append-only และ rebuild จาก effective stream ให้ projection เดิมทุกครั้ง; correction คืน exact compensating effects และ append external-fee history; chain แตกแขนง/ขาดเป็น conflict ส่วน ledger/wallet parity เป็น F-15 integration gate | พัฒนา + candidate | **Passed** — F-14 candidate 2026-10-18; [F-15 V-10/V-15/V-18](../2026-10-18-paper-order-matching/validation.md) ปิด ledger/wallet parity และ fault integration |
| V-6 | RQ-2/RQ-13/RQ-16 | base/quote/third-asset fee และ rebate ทุกฝั่ง BUY/SELL ให้ exact effects; invalid unit/sign/fee เกิน quantity/proceeds ถูกปฏิเสธ | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; exact fee/rebate gates ตาม Required CI checkpoint |
| V-7 | RQ-11/RQ-12 | fresh latest trade คำนวณ unrealized ตรง; stale/disconnected/unreconciled/generation mismatch/unit mismatch คืน unavailable ไม่มีเลขเก่าหรือศูนย์ปลอม | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; freshness/generation/valuation gates ตาม Required CI checkpoint |
| V-8 | RQ-7/RQ-8/RQ-9/RQ-10 | PostgreSQL FK/CHECK/FORCE RLS/grants/append-only triggers กันข้าม owner/mode/episode; API/SCAN อ่านหรือเขียน F-14 state ไม่ได้ | พัฒนา + candidate | **Passed** — F-14 candidate 2026-10-18; F-15 V-9/V-14 ปิด owner-scoped reset readiness ตาม integration amendment |
| V-9 | RQ-7/RQ-15/RQ-19 | fill writers พร้อมกัน, fill แข่ง episode/reset lock และ snapshot readers ให้ผล serializable; writer ไม่เขียน closed/stale episode | พัฒนา + candidate | **Passed — historical integration** — [F-15 V-11/V-14/V-15/V-18](../2026-10-18-paper-order-matching/validation.md) ปิด reset/open-order races; closed-episode replay เป็น remediation 2026-10-25 |
| V-10 | RQ-5/RQ-7/RQ-9/RQ-16 | fault injection ทุก F-14 write boundary รวม event/projection/activity/external-fee/audit, cancellation, statement timeout และ deferred commit failure rollback ทั้งชุด; retry เดิมมีผลครั้งเดียว ส่วน order/ledger faults เป็น F-15 integration gate | พัฒนา + candidate | **Passed** — F-14 candidate 2026-10-18; F-15 V-10/V-15/V-18 ปิด order/ledger rollback และ lost-ack recovery |
| V-11 | RQ-14/RQ-15 | activity tri-state/lifecycle: missing/UNKNOWN/CONFLICTED/error/stale revision ไม่เป็น idle; READY ต้องมาจาก atomic source initialization; conflict ไม่กลับ READY เอง; READY zero/positive แยกถูก; F-13 reset ยังคง `ACTIVITY_UNKNOWN` ใน F-14 | พัฒนา + candidate | **Passed** — F-14 candidate 2026-10-18; F-15 V-13/V-14 ยืนยัน atomic initialization และ reset success หลัง authoritative sources พร้อม |
| V-12 | RQ-1/RQ-18 | fixture เดียวผ่าน shared fold สำหรับ Paper/Live adapter boundary ให้ state/effects/errors ตรงกัน ไม่มี implementation สูตรคู่ขนาน | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; shared-fold/parity gates ตาม Required CI checkpoint |
| V-13 | RQ-8/RQ-18 | Paper entrypoint/tests ทำงานโดยไม่มี venue key/network/Live executor; negative fixtures ที่ import/call dependency ต้องทำ gate แดง | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; AST negative fixture/runtime isolation ตาม Required CI checkpoint |
| V-14 | RQ-10/RQ-17 | position changes/corrections/conflicts มี typed audit exact owner/episode/pair/result หนึ่งครั้ง ไม่มี secret/raw payload และแก้ย้อนหลังไม่ได้ | พัฒนา + candidate | **Passed — historical candidate 2026-10-18**; typed immutable audit gates ตาม Required CI checkpoint |
| V-15 | RQ-7/RQ-8/RQ-10 | migration `0031→0032→0031→0032` บนฐานว่างผ่าน; downgrade เมื่อมี F-14 data ปฏิเสธโดย data เดิมอยู่ครบ | candidate | **Passed 2026-10-16** บน PostgreSQL แยกพอร์ต 55439 |
| V-16 | RQ-1 to RQ-19 | relevant backend regression, lint, format, types, import contracts, migration/security/secret gates และ required CI ผ่านบน source สุดท้าย | candidate ก่อน merge | **Passed — historical candidate 2026-10-18** — local full backend และ CI 39097281613, 2818 passed; remediation 2026-10-25 local candidate coverage ครบ 3258 tests และ static gates ผ่านตาม checkpoint ด้านล่าง; required CI บน commit สุดท้ายยัง Pending |
| V-17 | nonfunctional | deterministic rebuild และ snapshot workload ตามงบที่อนุมัติ ไม่ล็อก owner อื่นและไม่มี unbounded memory/query growth | release checkpoint | **Pending Full Validation** |

F-14 จะเป็น **Development Complete** ได้เมื่อ V-1–V-16 ผ่านและ review ไม่มี Critical/High
โดย V-17 คง Pending Full Validation ตาม testing standard; reset success/open-order races
ปิดด้วย F-15 integration ตาม amendment แล้ว แต่ F-13/F-14 ยังไม่ใช่ Completed ก่อนตรวจรับระบบ
ผล historical candidate ไม่ใช่หลักฐาน required CI ของ remediation ที่ยังไม่ commit

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

## Review remediation — 2026-10-25

เจ้าของสั่งแก้ Medium/Low findings บนฐาน `96bae0e`; branch
`fix/f14-review-findings`, uncommitted diff ใน worktree `/tmp/tiewtrade-f14-review`.
ใช้ PostgreSQL 16 แยก `tiewtrade-f14-review-pg`, พอร์ต `55452`, database `tiewtrade`,
bootstrap roles จริงและ Alembic upgrade ถึง head ผ่าน; ไม่ใช้ฐานข้อมูล application
และไม่มี Binance call หรือ Live order

- V-4/V-9/V-10: owner advisory lock และ row locks เดิมครอบการอ่าน immutable replay
  ของ episode เก่า; RECORD/REPLACE/VOID exact retry คืน `REPLAYED` และไม่มี effects
  ทุกคำขอที่จะเขียนใหม่ รวม conflict/audit ต้องผ่าน active-episode fence ก่อน
- เพิ่ม regression ใน `tests/infra/execution_market/test_worker.py` ต่อจาก production
  fill/correction/VOID และ real wallet reset; ตรวจ canonical replay ด้วย event ID เดิม/ใหม่,
  new/conflicting event, new correction, foreign owner และ initialization ของ closed episode
  พร้อมเทียบ ledger/event/external-fee/conflict/audit rows และ position/activity/revision
  ทั้งรอบเก่าและรอบใหม่ว่าไม่เปลี่ยน
- Regression บน writer เดิมล้มที่ `_lock_active` หลัง reset ตาม finding; หลังแก้ผ่าน
  ชุด 16 fault/restart/commit-outcome scenarios ของ test เดิมทั้งหมด
- คำสั่ง targeted: `pytest -p no:cacheprovider tests/core/test_positions.py
  tests/core/test_position_parity.py tests/infra/positions
  tests/infra/execution_market/test_worker.py tests/infra/execution_market/test_executions.py
  tests/infra/paper_wallet/test_storage.py -q --tb=short`.
  ผลรอบรวม **103 passed / 1 failed** จาก 104 tests: catalog re-add test ล้มที่
  `publish_input` ด้วย `WriterLeaseLost` หลังจำลอง remove/re-add (นอก position writer).
  Test ถือ lease เดิมข้ามขั้นตอนฐานข้อมูลและไม่มี renewal ก่อน publish นั้น;
  รัน test เดิมแยกเพื่อแยก timing variation แล้ว **1 passed** โดยไม่แก้ source/test.
  เก็บ failure รอบรวมไว้ ไม่อ้างว่ารอบรวมนั้นเขียวครบ
- Ruff check/format ของ source และ test ที่แก้ผ่าน; mypy ของ
  `src/tiewtrade/infra/positions/storage.py` ผ่าน; `git diff --check` ผ่าน
- แจ้ง **Ready for Code Review** แล้ว; final review ตรวจ active/new-write fence,
  replay fingerprint/identity precedence, owner/RLS และ lock/reset ordering ไม่พบ
  Critical/High หรือ finding ค้างในขอบเขตการแก้
- ตาราง V-1–V-16 ชี้ historical F-14 candidate และ F-15 integration evidence ล่าสุดแล้ว
  โดยไม่ใช้หลักฐานเก่าอ้างว่า remediation ผ่าน required CI
- ยังไม่รัน full candidate/required CI ของ diff นี้; ต้องผ่านก่อน merge
  V-17 คง **Pending Full Validation**; ไม่มี commit/push/merge และไม่เลื่อนเป็น Completed
- เวลาอ่าน/เขียน/tests/review ไม่ได้จับแยกครบ จึงไม่อ้างเวลารวม


## Local candidate checkpoint — 2026-10-25

เจ้าของสั่งเริ่ม candidate validation ของ `fix/f14-review-findings` บนฐาน `96bae0e`.
Source/test diff SHA-256 ก่อนและหลังตรวจตรงกัน:
`4fb5bc2fceaf288ebcc8b5253a71b1ddab4f86b0aff467c72cabccf49ba3e6cc`
(`git diff -- backend/src/tiewtrade/infra/positions/storage.py
backend/tests/infra/execution_market/test_worker.py | shasum -a 256`).
ไม่มี source/test/config/dependency change ระหว่างชุดตรวจ

### Environment และ static gates

- Python 3.12.15; ใช้ venv เดิมกับ `uv.lock` ที่ checksum ตรงกับ worktree;
  pytest ชี้ source ของ candidate ผ่าน `PYTHONPATH`/`pythonpath=src`
- PostgreSQL 16 แยก container `tiewtrade-f14-review-pg`, พอร์ต `55452`,
  database ใหม่ `tiewtrade_candidate`; bootstrap roles/event triggers และ
  `alembic upgrade head` ถึง `0040` ผ่านก่อนเริ่ม suite
- Redis แยก `tiewtrade-f14-review-redis`, พอร์ต `56396`; API/MARKET_DATA/test URLs
  ชี้ instance นี้ทั้งหมด ไม่ใช้ application database/Redis
- `ruff check .` ผ่าน; `ruff format --check .` ผ่าน **521 files**;
  `mypy` ผ่าน **476 source files**; import-linter ผ่าน **7 contracts**
- `git diff --check` ผ่าน; automated suite ไม่ส่ง Live order และไม่เรียก Binance;
  สอง `venue_contract` tests ถูกแยกตาม pytest/CI configuration เดิม

### Full backend regression และการใช้หลักฐานต่อ

เริ่ม suite ทั้งชุดด้วย `pytest -p no:cacheprovider
--junitxml=/tmp/tiewtrade-f14-candidate.xml --tb=short` ผ่าน runner
`/tmp/tiewtrade-f14-run.py` ที่ตั้ง role URLs ของฐาน/Redis แยกข้างต้น

| รอบ | ผล | เวลา pytest | หลักฐาน |
|---|---|---|---|
| Initial full collection; หยุดเพื่อวิเคราะห์ failures | **839 passed / 2 failed**, 2 venue-contract deselected; ยังรันไม่ครบ | 490.56s | `/tmp/tiewtrade-f14-candidate.xml` |
| Failed tests แยกเพื่อวินิจฉัย | TOTP **1 passed**, prepared refresh ยัง failed | 3.47s | `/tmp/tiewtrade-f14-diagnostic.xml` |
| Prepared refresh บน candidate เดิม ไม่มี instrumentation | **1 passed** | 4.18s | `/tmp/tiewtrade-f14-refresh-confirm.xml` |
| Continuation 1: ใช้ 841 passed เดิมต่อ | **1460 passed / 1 failed**; หยุดด้วย `-x` | 540.80s | `/tmp/tiewtrade-f14-candidate-continuation-1.xml` |
| Failed ingestion test แยก | **1 passed** โดยไม่แก้ source/test | 2.74s | `/tmp/tiewtrade-f14-ingestion-confirm.xml` |
| Continuation 2: ใช้ 2302 passed เดิมต่อ | **956 passed**, ไม่มี failure | 26.12s | `/tmp/tiewtrade-f14-candidate-continuation-2.xml` |

ใช้ผลที่ผ่านแล้วต่อบน diff เดิมตาม testing §7; ไม่แก้ tests, ไม่ใส่ skip/xfail,
ไม่ลด assertions/timeouts/thresholds. Harness ชั่วคราว `/tmp/f14_candidate_resume.py`
เทียบ pytest JUnit identities กับ collection จริงและเลือกรันเฉพาะ tests ที่ยังไม่มี
ผล Passed; มี guard ปฏิเสธ identity ซ้ำหรือผลเดิมที่ไม่ตรง collection. รายงาน
`/tmp/tiewtrade-f14-candidate-coverage.json` ยืนยัน **3258 selected / 3258 unique passed /
0 missing / 0 extra**; เป็น coverage รวมจากหลายรอบ ไม่ใช่การอ้างว่ารอบแรกเขียวครบ
หรือว่ามี single uninterrupted green run

### Failures ที่เก็บไว้และข้อจำกัด

- `tests/api/test_totp_flow.py::test_the_second_step_completes_the_sign_in`:
  confirm ได้ 403 invalid code; helper สร้างรหัสของช่วงก่อนหน้าจาก wall clock.
  รันแยกผ่านโดยไม่แก้ source; time-step boundary เป็นความเสี่ยงของ test แต่ยังไม่ได้
  พิสูจน์เวลาข้าม boundary ของ failure รอบแรก จึงไม่อ้าง root cause ที่ยืนยันแล้ว
- `tests/api/test_prepared_indicators.py::test_empty_derived_scheduler_refresh_and_rebuild`:
  consumer ได้ STOPPED; รอบ diagnostic แรกยังเกิดซ้ำ จากนั้น HTTP diagnostic ได้
  COMPLETE/200 และผ่าน. Test เดียวกันผ่านทั้ง source ก่อนแก้ F-14 และ candidate
  โดยไม่แก้ source; รอบ candidate ไม่มี instrumentation ผ่านด้วย. ยังไม่ยืนยัน
  สาเหตุย่อยของ STOPPED รอบแรก จึงเก็บเป็น intermittent validation risk
- `tests/services/market_data/test_ingestion.py::test_actual_rows_commit_and_complete_after_observations`:
  COMPLETE ได้ 3 แทน 4; ตรวจฐานทันทีพบ BTC/15m มี `SOURCE_FAILURE` หนึ่งรายการ.
  รันแยกผ่านโดยไม่แก้ source/test; ไม่ยืนยันสาเหตุย่อยของ source failure
- Failures ทั้งสามอยู่ใน paths นอก position writer ที่แก้; ไม่มีการแก้โค้ดนอกขอบเขต
  ผล Failed/partial ข้างต้นยังอยู่ครบ และ CI ต้องเป็นผู้ยืนยัน candidate บน commit สุดท้าย

Local backend regression coverage และ static gates ครบแล้ว; **required CI ยัง Pending**
เพราะยังไม่มีคำสั่ง commit/push. ไม่อ้างว่าพร้อม merge ก่อน CI ผ่าน และไม่เลื่อนเป็น
Completed; V-17 คง **Pending Full Validation** ที่ release checkpoint ตามเดิม.
ช่วงอ่าน/วินิจฉัย/รีวิว/static ไม่ได้จับเวลาแยกครบ จึงไม่อ้างเวลารวมทั้งงาน


## Publication checkpoint — 2026-10-25

เจ้าของสั่ง commit/push และเปิด PR หลัง local candidate checkpoint.
นำ remediation ขึ้นบน `main` ล่าสุด `f6bd712` (PR #31: F-13 reset confirmation และ
command-status safe errors); ไม่มี conflict หรือ source/test change ของ F-14.
Diff SHA-256 ของ position writer/regression เทียบ base ใหม่ยังเป็น
`4fb5bc2fceaf288ebcc8b5253a71b1ddab4f86b0aff467c72cabccf49ba3e6cc`.
หลัง rebase รัน `tests/services/api/test_paper_wallet_transaction.py` ผ่าน **5 tests**
ใน 0.37s; `git diff --check` ผ่าน. ใช้ผล F-14 correctness/safety เดิมที่ไม่เปลี่ยนต่อ
และให้ required CI ของ PR ตรวจ combined candidate บน commit สุดท้าย.
สถานะ required CI ณ checkpoint นี้ยัง Pending; ติดตามผลจาก PR/Actions ของ branch
`fix/f14-review-findings`. ไม่มีคำสั่ง merge และ V-17 คง Pending Full Validation
