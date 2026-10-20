# Position, Margin และ PnL — Plan

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-16
วันที่: 2026-10-16

**Integration amendment อนุมัติ 2026-10-18:** [F-15 plan §6](../2026-10-18-paper-order-matching/plan.md#6-financial-writer-และ-f-13-reset-integration-amendment)
เป็น owner ของ Paper source initialization และประกอบ order/reservation/ledger กับ
F-14 session-bound writer ใน transaction เดียว; ใช้ exact effects/compensating effects
เดิม ไม่เปลี่ยน cost/PnL หรือ correction contract ของ F-14 การเปิด reset และการปิด
pending validations ต้องมีหลักฐาน F-15 integration จริง ไม่ถือว่าผ่านจาก core tests

## 1. แนวทางและขอบเขต implementation

ทำ F-14 เป็นสองส่วนที่มีขอบเขตชัด:

1. pure domain fold ใน `tiewtrade.core` รับ execution facts ที่ยืนยันแล้วและคืน position/PnL
   state ใหม่ โดยไม่รู้ว่า fact มาจาก Paper simulator หรือ Live venue
2. Paper persistence adapter เก็บ immutable facts, correction chain, projection และ
   authoritative activity state ภายใต้ transaction/owner lock เดียวกับ F-13

F-14 ยังไม่มี order producer จึงไม่สร้าง fill เองและไม่เปิด production entrypoint ให้รับข้อมูล
จาก API งาน F-15 จะเรียก session-bound writer ใน transaction เดียวกับ order/fill/ledger และ
เป็นผู้ยกระดับ Paper activity จาก `UNKNOWN` เป็น `READY` เมื่อพิสูจน์ source completeness แล้ว
F-23 ทำหน้าที่เดียวกันสำหรับ Live ในอนาคต จนกว่าจะถึงเวลานั้น Live activity เป็น unknown

งานนี้ไม่เปลี่ยน F-13 reset จาก fail-closed เป็น success และไม่สร้าง UI/API ใหม่
การเปิด reset success ทำใน integration amendment หลัง F-15 มี authoritative open-order source
และผ่าน race/fault validation ร่วมกันแล้ว

## 2. ของเดิมที่จะใช้ซ้ำ

| ของเดิม | ใช้อย่างไร |
|---|---|
| `backend/src/tiewtrade/core/money/{types,rounding,errors}.py` | ใช้ `Money`, `Quantity`, `RoundingDirection` และ error เดิมทุกการคำนวณ; ขยาย helper เฉพาะ operation ข้าม Money/Quantity ที่ขาด ห้ามใช้ `Decimal` นอก package |
| `backend/src/tiewtrade/venues/{symbols,prices}.py` | adapter แปลง `Symbol`/ราคาซื้อขายล่าสุดเข้า core input; core ไม่ import `venues` เพื่อคงทิศทาง dependency |
| `backend/src/tiewtrade/infra/market_data/{realtime_storage,realtime_records}.py` | อ่าน latest-trade snapshot, server time, feed generation/revision และสถานะพร้อมตามกฎ F-10; ไม่เรียก venue/network จาก position reader |
| `backend/src/tiewtrade/infra/paper_wallet/storage.py` | ใช้ `UserSession`, owner scope, active episode และ advisory lock key `paper-wallet:{user_id}` เดิม; writer ใหม่ไม่สร้าง lock namespace คู่ขนาน |
| `backend/migrations/versions/0031_paper_wallet.py` | ใช้ wallet/episode composite ownership, FORCE RLS, ENGINE grants และรูปแบบ append-only trigger เดิม |
| `backend/src/tiewtrade/infra/db/{session,money}.py` | ใช้ session boundary และตัวแปลง Money/Quantity เดิม |
| `backend/src/tiewtrade/infra/audit/{events,writer}.py` | เพิ่ม typed position actions/details ผ่าน invariant และ writer เดิม; ไม่สร้าง audit writer ใหม่ |
| `backend/tests/infra/paper_wallet/` | ใช้ PostgreSQL role fixtures, owner isolation, fault injection, worker/restart และ transaction assertions เดิม |
| `specs/decisions/004-shared-paper-live-trading.md` | บังคับ shared calculation/parity และ Paper isolation โดยไม่สร้าง implementation แยกต่อโหมด |

ไม่ใช้ indicator arithmetic เป็น position arithmetic โดยตรง เพราะ operation และ rounding contract
ต่างกัน แต่เพิ่ม operation กลางใน `core.money` เมื่อเป็น primitive ที่ Money/Quantity ยังไม่มี
เพื่อไม่ให้สูตรกระจายใน position module

## 3. Domain contract และสูตร

### 3.1 ชนิดข้อมูลกลาง

เพิ่ม `backend/src/tiewtrade/core/positions.py` พร้อม immutable types:

- `PositionPair(base, quote)` — value object สำหรับหน่วยของการคำนวณ แยกสองช่องและห้าม
  base เท่ากับ quote; ไม่ทำ supported-catalog/venue validation ซ้ำกับ `venues.Symbol`
- `ExecutionFact` — `execution_id`, pair, BUY/SELL, gross base `Quantity`, confirmed
  quote consideration `Money`, optional signed `FeeEffect`, source sequence และเวลา
- `FeeEffect` — จำนวนบวกคือ fee, จำนวนลบคือ rebate; unit เป็น base, quote หรือ third asset
- `PositionState` — pair, held quantity, total cost, cumulative realized PnL, last sequence/revision
- `PositionTransition` — state ใหม่และ exact base/quote/third-asset economic effects สำหรับ
  ledger/audit caller; correction คืน net compensating effects เทียบ durable state ก่อน rebuild
- `PositionAvailability` — `UNKNOWN`, `READY`, `CONFLICTED`
- typed domain errors สำหรับ unit/input/sequence/duplicate/conflict/insufficient position

service/infra adapter แปลง `venues.Symbol` เป็น `PositionPair` ที่ boundary เพราะ `core`
ห้าม import `venues`; ใช้ canonical unit validation เดิมจาก `core.money` ไม่สร้างกฎชื่อหน่วยใหม่

`execution_id` เป็น UUID กลางที่ execution adapter สร้าง/ผูกกับ source identity อย่างถาวร
source-specific identifier ไม่ออกจาก adapter และต้อง map ซ้ำเป็น UUID เดิมเสมอ
`quote consideration` มาจากผล execution ที่ยืนยันแล้ว ไม่คำนวณกลับจาก display price

### 3.2 Fee และ inventory effects

ให้ `s = +1` สำหรับ BUY และ `s = -1` สำหรับ SELL, `q` คือ gross base quantity,
`n` คือ confirmed quote consideration และ signed fee เป็นบวกเมื่อถูกเก็บ/ลบเมื่อ rebate:

- base inventory delta = `s*q - base_fee`
- quote cash delta = `-s*n - quote_fee`
- third-asset fee/rebate ไม่เปลี่ยน position/cost/PnL ของ pair แต่คืนเป็น exact expense effect
  พร้อมหน่วยเดิมให้ caller บันทึกแยก

BUY ต้องมี inventory delta มากกว่าศูนย์และ adjusted cost `n + quote_fee` ไม่ติดลบ
SELL ต้องมี inventory delta ติดลบ, ปริมาณที่ลดไม่เกินที่ถือ และ proceeds
`n - quote_fee` ไม่ติดลบ ผลที่ผิดเงื่อนไขเป็น conflict/fail closed ไม่ clamp เป็นศูนย์

### 3.3 Weighted-average cost และ realized PnL

เก็บ `held_quantity` กับ `total_cost` ไม่ persist average price ที่ถูกปัด:

- BUY: เพิ่ม net base quantity และ adjusted quote cost
- partial SELL: `released_cost = total_cost × sold_quantity ÷ held_quantity`
  ปัดขึ้นใน quote unitเพื่อไม่ทำให้ realized PnL สูงเกินจริง
- full SELL: ใช้ `released_cost = total_cost` โดยตรงเพื่อรักษาผลรวมและล้างเศษ
- realized increment = confirmed proceeds หลัง quote fee − released cost
- state ใหม่มี total cost เดิมลบ released cost; เมื่อ quantity เป็นศูนย์ total cost ต้องเป็นศูนย์
- การซื้อหลัง position เป็นศูนย์เริ่มฐานต้นทุนใหม่ แต่ cumulative realized PnL ของ episode/pair
  ยังคงต่อเนื่องเพื่อให้ผลต่อรอบไม่หาย

เพิ่ม helper ใน `core.money` สำหรับ notional/allocation ที่รับและคืน `Money`/`Quantity`,
ตรวจ units และบังคับ explicit rounding ทุกครั้ง ผลคูณสำหรับ current value ปัดลงเพื่อไม่แสดง
unrealized PnL สูงเกินจริง; ห้าม caller แตะ `.amount` เพื่อคำนวณเอง

### 3.4 Unrealized PnL

reader รับ latest trade ที่ผ่าน freshness/generation/reconciliation rules ของ F-10:

- current value = fresh latest price × held quantity ปัดลงใน quote unit
- unrealized PnL = current value − total cost
- quantity เป็นศูนย์ให้ unrealized PnL เป็นศูนย์โดยไม่ต้องเรียกราคา
- ราคา/feed ไม่พร้อม, stale, generation ไม่ตรง หรือ unit ไม่ตรงให้สถานะ unavailable
  พร้อม reason/time/revision; ห้ามคืนเลขเดิมเหมือนยังสด
- ไม่หัก estimated exit fee และไม่ใช้ข้อมูลที่แปลงเป็น browser `Number`

### 3.5 Duplicate, ordering และ correction

fold ปกติรับ source sequence ต่อเนื่องเท่านั้น:

- execution ID + canonical payload เดิมเป็น exact replay และไม่เปลี่ยน state/revision/audit
- ID เดิม payload ต่าง, sequence ซ้ำ payload ต่าง, gap หรือย้อนลำดับเป็น conflict
  ที่มี canonical conflict fingerprint; retry conflict เดิมคืนผลเดิม ไม่เพิ่ม event/audit ซ้ำ
- correction เป็น immutable event `REPLACE` หรือ `VOID` ที่อ้าง event ก่อนหน้า
  แต่ละ event ถูก supersede ได้ครั้งเดียวเพื่อไม่ให้ chain แตกแขนง
- `REPLACE`/`VOID` คง execution ID และ source sequence ของ chain เดิม; event ID กับเวลา
  บันทึกเป็น append order แยก และ correction ไม่ขยับ activity source completeness
- ทุก correction rebuild projection จาก effective event stream ด้วย fold เดิมในลำดับ source
  ไม่ patch เฉพาะ delta และไม่ UPDATE/DELETE fact เดิม จากนั้นเทียบ economic totals ก่อน/หลัง
  เพื่อคืน compensating effects ให้ caller append ledger/fee history ห้ามแก้ ledger เดิม
- ระหว่าง chain ขาด/ขัดกัน activity เป็น `CONFLICTED`; ไม่มี caller ใดแปลเป็น zero position

## 4. Persistence และ transaction boundary

### 4.1 Migration 0032

เพิ่ม migration `0032_position_pnl.py` หลัง 0031:

| ตาราง | หน้าที่ |
|---|---|
| `paper_position_activity` | หนึ่งแถวต่อ episode; owner/wallet composite FK, availability, source sequence, revision, observed_at และ failure code |
| `paper_position_events` | append-only RECORD/REPLACE/VOID facts, execution ID, pair, side, exact base/quote/fee columns, source sequence/time และ supersedes event |
| `paper_position_projections` | mutable derived projection ต่อ episode/pair: quantity, total cost, realized PnL, last event/revision |
| `paper_position_external_fees` | append-only exact third-asset fee/rebate effects ผูก event; ไม่แปลงหน่วย |

ทุกตารางมี `user_id`; FK ที่ข้ามตารางรวม owner key, pair units และ episode เพื่อกัน wiring
ข้ามผู้ใช้/รอบ DB CHECK บังคับ enum, positive gross values, canonical units, sequence/revision
และ shape ของ event type Projection เป็น cache ที่ rebuild ได้ ไม่ใช่แหล่งประวัติ

ใช้ FORCE RLS และ policy `current_setting('app.user_id', true)` แบบ F-13 ENGINE อ่าน/เขียน
ผ่าน `UserSession`; API และ ENGINE_SCAN ไม่มีสิทธิ์อ่านหรือเขียนตาราง F-14 เพราะงานนี้ยังไม่มี
public endpoint/scan use case; migrator เท่านั้นที่จัด schema TRIGGER ปฏิเสธ UPDATE/DELETE/TRUNCATE
บน events/external fees และปฏิเสธการเปลี่ยน owner/episode ของ activity/projection

episode ที่มีอยู่และ episode ใหม่เริ่ม `UNKNOWN` migration ไม่สร้าง `READY` จากการไม่มีแถว
downgrade อนุญาตเฉพาะเมื่อไม่มี F-14 data; ถ้ามีต้องปฏิเสธเพื่อไม่ทำลายประวัติการเงิน

### 4.2 Session-bound writer

เพิ่ม `backend/src/tiewtrade/infra/positions/{records,storage}.py` โดย writer:

1. รับ `UserSession` ที่ caller เปิด transaction ไว้และไม่ commit เอง
2. ใช้ advisory lock `paper-wallet:{user_id}` เดียวกับ F-13 ก่อนแตะ activity
3. lock active `paper_wallet_state`/activity row และตรวจ episode ยัง active
4. ตรวจ source availability/sequence/idempotency
5. append event แล้ว fold/rebuild ผ่าน core function
6. update projection/activity revision, append third-asset effect และ typed audit ใน transaction เดียว
7. คืน transition ให้ F-15 เขียน order state และ append F-13 ledger effect ใน transaction เดียวกัน;
   correction ใช้ compensating effect ห้าม UPDATE/DELETE ledger เดิม

เมื่อ F-15 เรียกใช้ transaction จะยังไม่สมบูรณ์จน order state, position event/projection,
wallet ledger, external fee และ audit ถูกเขียนครบ F-14 รับผิดชอบให้ transition คืน exact effects
และให้ event/projection/activity/audit rollback พร้อมกัน ส่วน F-15 รับผิดชอบ ledger schema/write
และ invariant ว่า initial capital บวก quote cash effects ทั้งหมดเท่ากับ wallet balance

หาก audit/ledger/order write หรือ commit ล้ม caller rollback ทั้ง transaction Event ที่ retry
ด้วย identity/payload เดิมต้อง replay โดยไม่เกิด economic effect หรือ audit ซ้ำ

writer ไม่รับ mode จาก browser ไม่มี HTTP route และไม่โหลด venue/credential/network
Paper worker ของ F-15 เป็น production caller แรก ส่วน test adapter ใช้ contract เดียวกัน

### 4.3 Authoritative activity สำหรับ F-13

เพิ่ม internal reader ที่คืน tri-state พร้อม episode/revision:

- `READY + quantity > 0` → position exists
- `READY + ทุก projection quantity = 0` และ source sequence complete → no position
- missing row, `UNKNOWN`, `CONFLICTED`, episode/revision mismatch หรือ source error → unknown

availability lifecycle เป็น fail-closed:

1. episode ใหม่เริ่ม `UNKNOWN` เสมอ
2. เฉพาะ source owner ที่ plan ของ F-15/F-23 อนุมัติแล้วเท่านั้นที่เรียก session-bound
   initialization พร้อม baseline/source sequence และ proof revision ภายใต้ account lock
3. initialization, baseline projection และ transition เป็น `READY` ต้อง commit พร้อมกัน
4. gap/conflicting replay/correction chain error เปลี่ยนเป็น `CONFLICTED` พร้อม durable
   fingerprint/audit แบบ idempotent; business conflict ถูกบันทึกแล้วคืน typed result ไม่ raise
   จน transaction rollback ส่วน infrastructure/audit failure ต้อง rollback ทั้งชุด
5. การกลับ `CONFLICTED → READY` ต้องมาจาก explicit reconciliation/rebuild ที่พิสูจน์
   complete stream ใหม่ ห้าม timer/retry เปลี่ยนเองและ F-14 ไม่มี production caller นี้

F-14 ยังไม่แก้ branch RESET ใน `paper_wallet/storage.py`; F-15 ต้องเพิ่ม authoritative
open-order reader และ integration transaction ที่ตรวจ position + orders ภายใต้ lock เดียวกัน
ก่อน F-13 จะสร้าง closure/episode/credit ใหม่

## 5. Audit, errors และ observability

เพิ่ม typed audit actions `PAPER_POSITION_APPLIED`, `PAPER_POSITION_CORRECTED` และ
`PAPER_POSITION_CONFLICTED` พร้อม owner, episode, pair, execution/event IDs, outcome,
exact Money/Quantity parts และ failure code ไม่มี raw source payload, credential หรือ stack trace

ข้อยกเว้นที่เจ้าของยืนยันใน NC-51: initialization conflict เป็นระดับ episode จึงใช้ subject
`PAPER_POSITION_ACTIVITY` และ details เฉพาะ episode/initialization ID โดยไม่มี pair สมมติ

domain errors map เป็น fixed internal codes เช่น `POSITION_SEQUENCE_GAP`,
`POSITION_DUPLICATE_CONFLICT`, `POSITION_INSUFFICIENT`, `POSITION_SOURCE_UNKNOWN`,
`POSITION_PRICE_UNAVAILABLE` F-14 ไม่มี public API จึงไม่เพิ่ม HTTP mapping ก่อนมี consumer spec

log เฉพาะ fixed IDs/code/revision ห้าม log raw event/fee/payload ข้อมูล conflict ต้องคงสถานะ
fail-closed ให้ recovery/reconciliation ตรวจได้ ไม่ retry แบบเพิ่ม event ใหม่เอง

## 6. ไฟล์ที่จะเปลี่ยน

| กลุ่มไฟล์ | เปลี่ยนอะไร |
|---|---|
| `backend/src/tiewtrade/core/positions.py` | immutable contracts, weighted-average fold, fee effects, correction rebuild และ errors |
| `backend/src/tiewtrade/core/money/` | เพิ่ม primitive cross-unit/allocation ที่ตรวจหน่วยและ explicit rounding; export ผ่าน `__init__.py` |
| `backend/migrations/versions/0032_position_pnl.py` | Paper facts/activity/projection/external fee, constraints, RLS/grants/triggers และ safe downgrade |
| `backend/src/tiewtrade/infra/positions/{__init__,records,storage}.py` | session-bound persistence, tri-state activity reader และ snapshot reader |
| `backend/src/tiewtrade/infra/paper_wallet/storage.py` | สร้าง UNKNOWN activity row พร้อม episode ใหม่เท่านั้น; ไม่เปิด reset success |
| `backend/src/tiewtrade/infra/audit/{events,__init__}.py` | typed position actions/details และ invariants |
| `backend/tests/core/` | formula/examples/property/parity/error tests |
| `backend/tests/infra/positions/`, `backend/tests/migrations/` | PostgreSQL roles/RLS/atomicity/races/rebuild/faults/migration tests |
| `backend/tests/gates/` | Paper isolation, core purity, Money/Quantity/no-float และ negative fixtures |
| `specs/features/2026-10-16-position-margin-pnl/` | validation evidence/checkpoints หลัง implementation |

ไม่แก้ frontend, OpenAPI หรือ generated TypeScript เพราะ F-14 ไม่มี public endpoint/UI

## 7. Milestones หลังอนุมัติ

1. **M0 — Spec checkpoint:** requirements/plan/validation Approved วันที่ 2026-10-16
2. **M1 — Domain:** failing examples/properties → money primitives → position fold/corrections;
   ผ่าน numeric, unit, parity และ deterministic rebuild tests
3. **M2 — Database:** migration/RLS/immutability/roles → persistence/activity/projection;
   ผ่าน owner/mode/episode isolation และ migration cycle
4. **M3 — Transaction safety:** wire F-13 episode UNKNOWN creation, audit, duplicate/concurrency/
   cancellation/timeout/commit-failure recovery โดย reset ยังคง fail closed
5. **M4 — Candidate:** review Critical/High, targeted regression, required candidate gates ตาม
   testing standard; workload ยาวคง release checkpoint ตาม validation

แต่ละ milestoneใช้ผลตรวจที่ยัง valid ต่อ ไม่รัน full suite ซ้ำทุก fix และไม่สร้าง F-15 simulator,
F-13 reset success หรือ Live writer เพื่อทำให้ F-14 ผ่านก่อน dependency

## 8. ความเสี่ยงและการกู้คืน

| ความเสี่ยง | การควบคุม |
|---|---|
| rounding ทำให้ต้นทุน/PnL สะสมคลาด | เก็บ total cost, full close ใช้ remainder, partial release ปัดขึ้น, property conservation tests |
| duplicate/worker restart เพิ่ม position ซ้ำ | durable execution identity + canonical payload + unique constraints + replay tests |
| correction ทำ projection ไม่ตรง history | append chain + rebuild ด้วย fold เดิม + parity checksum; conflict เปลี่ยน authority เป็น unknown |
| correction ทำ wallet balance ไม่ตรง position | F-14 คืน net compensating effects; F-15 ต้อง append ledger ใน transaction เดียวและผ่าน parity/fault integration tests |
| writer แข่ง reset/episode เปลี่ยน | advisory lock เดียวกับ F-13 + active episode check + race barrier tests |
| missing row ถูกแปลว่า idle | tri-state contract; DB/new episode เริ่ม UNKNOWN; negative gate ห้าม fallback-to-empty |
| ให้สิทธิ์อ่าน financial state ก่อนมี endpoint | F-14 ไม่ grant API/ENGINE_SCAN; feature consumer ต้องขอสิทธิ์ผ่าน migration/spec ของตน |
| Paper แตะ Live/venue | core pure, Paper adapterไม่มี network import, AST/runtime isolation gates |
| partial transaction เหลือ eventแต่ไม่มี projection/audit | transaction เดียว + fault injection ทุก write boundary/commit/cancel/timeout |
| price stale แสดง PnL เก่าเหมือนสด | reuse F-10 readiness/revision; unavailable result ไม่มี numeric unrealized PnL |
| third-asset fee ถูกละเลยหรือแปลงผิด | append exact separate effect; ไม่รวม pair PnL จนมี authoritative conversion spec |
| migration rollback ทำลาย financial history | downgrade ปฏิเสธเมื่อมี data และทดสอบ empty/data cases แยกกัน |

## 9. การเปลี่ยนแปลงหลังอนุมัติ — Approved 2026-10-16

ระหว่างเริ่ม M2 พบว่า validation เดิมสั่งให้ F-14 พิสูจน์ wallet ledger parity ทั้งที่ plan
กำหนดให้ F-15 เป็นเจ้าของ order/fill producer และ trade-ledger semantics ขณะที่ schema F-13
รองรับเพียง `EXTERNAL_CAPITAL` การเพิ่ม trade ledger ใน F-14 จะคิดข้อกำหนด F-15 ล่วงหน้า

เจ้าของอนุมัติให้แก้ขอบเขตดังนี้:

- F-14 พิสูจน์ exact quote/base/third-asset effects และ correction compensation ใน pure domain
- F-14 ทำ event/projection/activity/external-fee/audit ให้ atomic และ retry-safe
- F-15 กำหนด trade-ledger schema แล้วพิสูจน์ order + fill + F-14 state + ledger + wallet parity
  ใน transaction/fault integration gate ของ F-15
- F-14 ยังคงไม่มี production fill caller และ activity ยัง `UNKNOWN` จน F-15 initialize source

การแก้นี้ไม่เปลี่ยนสูตร PnL, RQ-7/RQ-9 หรือข้อกำหนดว่า integration สุดท้ายต้อง atomic
แต่ย้ายหลักฐานที่ต้องมี producer/ledger ไปอยู่กับ feature ที่เป็นเจ้าของข้อมูลนั้น

### Review remediation — เจ้าของสั่งแก้ 2026-10-16

การแก้ findings หลัง deep review ยังคง contract เดิม: ย้าย `AccountUse` ซึ่งเป็น enum โดเมนไป
`tiewtrade.core.trading_account` และ re-export ผ่าน path เดิม เพื่อให้การ import Paper position/audit
ไม่โหลด credential/signing storage; เพิ่ม snapshot completeness/time, initialization replay และ
projection revision/permission constraints โดยไม่เปลี่ยนสูตร position/PnL หรือขอบเขต F-15
