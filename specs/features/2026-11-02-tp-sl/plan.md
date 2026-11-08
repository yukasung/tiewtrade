# F-17 — TP/SL และ Bracket — Plan

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-04; NC-F17-06 Approved 2026-11-04**; **NC-SET4-12 Approved A 2026-11-06; §16/18 Approved 2026-11-07 - separate internal checkpoint**
วันที่: 2026-11-04

NC-F17-MANUAL-01: requirements MR-01–11 **Approved A 2026-11-08**;
[implementation amendment](manual-acceptance-fix-plan.md) และ
[validation amendment](manual-acceptance-fix-validation.md) **Approved 2026-11-08**
ตามคำสั่ง approve ของเจ้าของ; ผล implementation/checks ดู checkpoint amendment.
อ้างอิง: requirements.md Approved 2026-11-04, ADR-004, testing §6–7

NC-F17-SEC-01: **Approved A 2026-11-08** — [six exact public-checksum exceptions](security-checksum-publication-proposal.md), existing policy tests, normal commit/push and one replacement required CI round. No scanner or trading-rule change; CI results remain pending until observed.

## แนวทาง

เพิ่ม protection domain ที่รับสถานะ/ราคา/เวลาเป็น input และคืน transition/intent
โดยไม่อ่าน DB/network/clock เอง แปลง trigger เป็น MARKET SELL ผ่าน F-15 เดิม
ไม่เพิ่ม STOP order type ลง matcher และไม่สร้างสูตร matching/fee/PnL อีกชุด
origin ยังคง MANUAL/BOT; ใช้ protection identity/link แยก purpose ของ exit
ไม่เดา purpose จาก SELL และไม่ให้ browser ระบุ internal protection link

API บันทึก owner-scoped durable request แล้ว engine ประมวลผล; เพิ่ม protection round
ใน paper order worker เดิม ไม่เพิ่ม service, Redis หรือ infrastructure ใหม่
PostgreSQL เก็บ intent, allocation, revision, retry deadline, trigger evidence,
exit linkage และ unresolved work ทั้งหมด; notification/cache เป็น hint เท่านั้น
worker หลายตัวใช้ owner session/RLS และ episode lock/claim/fence เดิม
restart ต้องค้นงานจาก DB ได้ แม้ browser ปิดหรือไม่มี order ปกติค้างอยู่

## ของเดิมที่จะใช้ซ้ำ — ตรวจจาก source

Path backend ในตารางอยู่ใต้ `backend/src/tiewtrade/`:

| ของเดิม | Path และการใช้ |
|---|---|
| เงิน/ปริมาณและ order contracts | `core/money/`, `core/orders.py`, `core/positions.py` — Money/Quantity, OrderScope/OrderIntent/BaseSize และ execution facts |
| Matching | `core/paper_matching.py` — MARKET execution, liquidity, fee, reservation และ partial/terminal semantics |
| Durable request bridge | `infra/paper_orders/requests.py`, `request_dispatch.py`, `request_worker.py` — pattern intake/transfer/result/idempotency |
| Command/claim และ single writer | `infra/paper_orders/dispatch.py`, `storage.py`, `worker.py` — submit/cancel, episode lock, catalog/fence และ replay |
| Financial transaction | `infra/paper_orders/executions.py`, `matching_storage.py`, `corrections.py`, `infra/positions/storage.py` — stage_fill_cash, persist_checkpoint และ authoritative correction/recovery |
| Market evidence | `infra/market_data/order_book_storage.py`, `realtime_storage.py`, `realtime_records.py`, `infra/paper_orders/records.py` — source identity/generation/readiness และ execution evidence |
| Safety | `infra/risk_limits/policy.py`, `boundaries.py`, `infra/paper_orders/manual_policy.py`, `core/trading_stops.py` — ใช้ gates เดิมและไม่ทำ protection เป็น opening |
| API/session/audit | `services/api/manual_order_routes.py`, `manual_order_models.py`, `request_identity.py`, `safe_input_routes.py`, `infra/db/session.py`, `infra/audit/` |
| Worker composition | `services/engine/paper_order.py`, `paper_order_main.py`, `manual_order.py` |
| UI/client | `frontend/src/ManualOrderForm.tsx`, `PaperTradePage.tsx`, `LiveTradePage.tsx`, `TradingWorkspace.tsx`, `PaperOrderList.tsx`, `manualOrders.ts`, `manualOrderJournal.ts`, `components/MarketValue.tsx` |

บันทึก refactor ที่เจ้าของอนุมัติ 2026-11-04: รวมการใช้
`infra/market_data/order_book_storage.py::read_latest_book` และ
`core/protections.py::validate_setup` ผ่าน helper ภายใน protection worker เดียวกัน
สำหรับ initial setup และ replacement; รวมการค้น execution links/filter effective facts
สำหรับ entry/exit ไว้ใน worker โดยยังใช้ authoritative fold จาก
`infra/positions/storage.py::read_effective_executions` เดิม ไม่เปลี่ยน trading policy,
ลำดับ transaction, schema หรือ contract ของ API

### UI mapping

ใช้ `frontend/src/components/ui/{Input,Select,Label,Button,Modal,Table,Badge,Alert}.tsx`
ก่อนเสมอ ต้นแบบที่ตรวจพบ:

- `references/admin-template/src/components/form/form-elements/{DefaultInputs,InputStates}.tsx`
- `references/admin-template/src/components/form/input/InputField.tsx` และ `form/Select.tsx`
- `references/admin-template/src/components/tables/BasicTables/BasicTableOne.tsx`
- `references/admin-template/src/components/ui/{badge/Badge.tsx,alert/Alert.tsx,modal/index.tsx}`

เพิ่ม optional TP/SL ใน shared entry form และรายการ protection ใน workspace เดิม
ฟอร์มตั้งทีหลัง/แก้ไข/ขายส่วนที่ป้องกันใช้ shared modal/controls; แสดงจำนวนจาก backend
ไม่คำนวณ available quantity หรือราคาเปอร์เซ็นต์ใน browser
แสดง armed quantity, pending/unprotected quantity, feed readiness, exit status และ residual
พร้อมเวลา snapshot เป็นข้อความ ไม่ใช้สีอย่างเดียว ไม่มี style exception ใหม่
Live ใช้ shared presentation แต่ unavailable และไม่มี mutation ไป Paper
ล้าง draft เมื่อคู่/owner/mode/episode เปลี่ยน; pending request ต้องค้นคืนจาก server ได้

## สถานะและ transaction

แยก lifecycle ของ request, protection และ exit order ไม่ใช้ ACCEPTED แทน protected/closed:

| ส่วน | ความหมาย |
|---|---|
| request | PENDING / APPLIED / REJECTED; exact retry คืนผลเดิม; key เดิม payload ต่างเป็น conflict |
| protection | WAITING_ENTRY / ARMING / ARMED / EXITING / CLOSED / CANCELED / FAILED; readiness/covered/residual เป็นข้อมูลแยก ห้าม ARMED บังส่วนที่ยังไม่ได้ป้องกัน |
| exit | อ้าง authoritative command/order state ของ F-15; ผลไม่ทราบคง unresolved และ reconcile |

1. Bracket intake บันทึก entry request และ protection intent ใน transaction เดียวกัน
   entry ที่ reject ไม่สร้าง active coverage; entry fill สร้าง/เพิ่ม allocation และ durable
   protection work พร้อม financial checkpoint ใน transaction เดียวกัน ก่อน commit
2. Allocation ผูก owner/mode/episode/pair/protection และ entry เมื่อเป็น bracket
   ใช้ net acquired quantity จาก financial facts เดิม; TP/SL ใช้ allocation เดียว
   available-to-sell ต้องหัก active protection allocation และ order reservation โดยไม่หักซ้ำ
3. ตั้งทีหลัง/แก้ไข/ขายมือ/trigger ใช้ episode lock เดียวกันและตรวจ revision ภายใน lock
   ค่าเก่าปฏิเสธให้ refresh ไม่ overwrite การแก้ล่าสุด การขายส่วนที่มี protection ต้องระบุ
   allocations ที่ผู้ใช้เลือก; ย้าย allocation เป็น reservation ของ exit อย่าง atomic
   ถ้าการรับคำสั่งล้มเหลว rollback แล้ว protection เดิมยังอยู่
4. Trigger บันทึก winning leg, source identity/price/time, group revision และ durable
   exit intent ใน transaction เดียวกัน สร้าง command identity คงที่ต่อ exit intent
   อีกขาไม่สามารถ enqueue ซ้ำ; cancel entry remainder ผ่านกลไกเดิมและติดตามผลจริง
5. Fill ระหว่าง cancel ต้องเพิ่ม exposure ที่ต้องจัดการ โดยตรวจผล exit เดิมก่อนออก
   intent สำหรับปริมาณใหม่; ไม่ส่งซ้ำเพื่อชดเชย residual ของ MARKET ที่ terminal แล้ว
   ต้องมี regression แยก late entry fill ออกจาก partial exit residual
6. การแก้ protection เป็น atomic revision replacement; immutable history เก็บเดิมไว้
   เมื่อ EXITING ห้ามใช้ endpoint แก้/ยกเลิก protection ไปเปลี่ยนคำสั่งปิดที่ส่งแล้ว
7. Reuse correction/recovery facts: ยืนยันปริมาณ authoritative ก่อน resume ไม่ย้อน audit
   หรือปล่อย allocation เกิน held quantity หาก correction เปิดช่องว่างเรื่องการจัดสรร
   ที่ requirements ไม่กำหนด ให้หยุดขอคำตัดสินก่อนเปลี่ยน trading policy

### ราคาและ scheduling

ใช้ last trade evidence ของตลาดที่เชื่อถือได้พร้อม identity/generation/freshness
ไม่ใช้ best bid, candle close หรือ OHLC แทน last trade; freshness/reconnect ใช้ readiness
contract เดิมของ market data ไม่ตั้ง stale threshold ใหม่เอง
persist consumed cursor/trigger evidence เพื่อไม่ประเมินเหตุการณ์ซ้ำหลัง restart
ปิดช่องที่ protection หยุดเดินเมื่อ F-15 ไม่มี active order ด้วย durable due scan
ของ protection round; scan role อ่านได้เฉพาะ scheduling hints แล้วกลับ owner RLS
การรับรู้ fill ต้อง enqueue protection ใน commit เดียวกัน; SLA 1 วินาทีวัดจากเวลาที่
input จำเป็นพร้อมถึงเริ่มประมวลผลจริง ไม่ใช้เวลา enqueue แทน processing
feed gap แสดง unavailable; recovery ประเมินราคาสดตาม NC-F17-05 ไม่จำลอง fill ย้อนเวลา
source conflict/unknown ไม่ใช้ราคาที่พิสูจน์ไม่ได้ ต้องคงสถานะและแจ้งปัญหา

Retry state/deadline/attempt count อยู่ DB ตาม NC-F17-05 โดยใช้ clock ที่ caller ส่ง
permanent failure เข้ากฎ failure โดยไม่ยิงซ้ำ; unknown ค้นผล identity เดิมก่อน
test bot failure intent ด้วย shared domain แต่ bot runtime/Live execution ยัง Pending Dependency

## API contract ที่เสนอ

Router paths ด้านล่างใช้ `/api` prefix ฝั่ง browser ตามเดิม; session, CSRF และ throttle
ใช้กฎเดิม ทุกจำนวนเป็น string ตรวจด้วย Money/Quantity ฝั่ง server ห้ามรับ owner/mode
หรือ internal origin/purpose จาก client ใช้ strict schema และ error codes ไทย/อังกฤษ

| เส้นทาง | Contract |
|---|---|
| POST `/paper/orders` | เพิ่ม optional `protection` ที่มี `take_profit_price`/`stop_loss_price` อย่างน้อยหนึ่งค่า สำหรับ BUY entry; เก็บรวมใน canonical idempotency fingerprint |
| GET `/paper/protections` | owner/episode-scoped keyset list; default 20/max 100, snapshot_at, readiness, protected/unprotected quantities, revisions และ linked entry/exit |
| POST `/paper/protections` | ตั้งทีหลัง: wallet/episode/pair, quantity, TP/SL; Idempotency-Key UUID |
| POST `/paper/protections/{id}/replace` | expected_revision และ quantity/TP/SL ใหม่; APPLIED ต่อเมื่อ atomic replace สำเร็จ |
| POST `/paper/protections/{id}/cancel` | expected_revision และ scope; ยกเลิกเฉพาะ protection ไม่ถือว่า position ถูกขาย |
| POST `/paper/orders` สำหรับ SELL | optional explicit protection allocations/revisions ที่ผู้ใช้เลือก; engine ตรวจปริมาณและประสานการลด protection ก่อน admit |
| GET `/paper/protection-requests/{id}` | ผล intake/application/failure และ link; ยัง pending ต้อง poll ต่อ |
| GET `/paper/protection-requests/by-key/{key}` | owner-scoped recovery เมื่อ response หาย; action เป็นส่วนของ lookup identity |
| GET `/paper/protection-requests?state=unresolved` | discover งานค้างข้าม reload/instance; keyset scope ผูก owner/filter ไม่ตัดงานด้วยอายุ |

ใช้ 202 สำหรับ durable intake, 404 เหมือนกันสำหรับไม่มีจริง/ของผู้อื่น และ conflict
สำหรับ key/revision ไม่ตรงตาม pattern เดิม; API ไม่มีสิทธิ์เขียน financial/protection projection
ผลตอบกลับต้องมี request state และ authoritative protection/exit snapshot แยกกัน
ส่ง bracket ซ้ำผ่าน F-16 recovery ต้องไม่สร้าง entry หรือ protection ใหม่
สร้าง TypeScript types จาก OpenAPI ไม่เขียน schema ฝั่ง browser คู่ขนาน

## สิ่งที่จะแก้

| ส่วน | เปลี่ยนอะไร |
|---|---|
| `backend/src/tiewtrade/core/protections.py` (ใหม่) | immutable domain, transitions, allocation, trigger/retry decisions |
| `backend/src/tiewtrade/infra/protections/` (ใหม่) | requests/storage/views/dispatch/worker; ใช้ transaction/session/audit contracts เดิม |
| `backend/src/tiewtrade/infra/paper_orders/` | bracket transfer, availability/reservation integration, fill checkpoint, exit links/recovery; จำกัด diff ให้สัมพันธ์ F-17 |
| `backend/src/tiewtrade/services/engine/paper_order*.py` | protection round และ composition พร้อม fairness/restart discovery |
| `backend/src/tiewtrade/services/api/protection_{models,routes}.py` (ใหม่), manual order models/routes/app | strict input, read/status/recovery routes และ auth registration |
| `backend/src/tiewtrade/infra/audit/`, `backend/migrations/versions/` | action/schema/invariants/RLS/grants/constraints ที่รองรับ protection |
| `frontend/src/` | shared ProtectionForm/ProtectionList, API/query/messages/journal, entry form และ workspace integration; generated API types |
| tests/specs | targeted unit/PostgreSQL/API/UI/E2E และ evidence; อัปเดต roadmap ตามผลจริง |

## ผลต่อฐานข้อมูลและ deployment

เพิ่ม numbered additive migration หลัง migration head ณ implementation ไม่แก้ migration เก่า:
protection requests/results, group headers, immutable revisions/events, active allocations,
trigger/exit links และ durable work claims/retry deadlines ข้อมูลผู้ใช้ทุกตารางมี owner
และ RLS; composite identity/FK กัน cross-owner/mode/episode linking
unique request fingerprint/trigger/exit identity กัน duplicate financial effects
ใช้ monetary DB domains เดิม, UTC timestamps และ CHECK quantities ไม่ติดลบ
ledger/events/audit เพิ่มอย่างเดียว; projection แก้ได้เฉพาะ engine ตาม invariant เดิม
audit ใช้ partition เดิม; ไม่สร้าง generic high-volume log ใหม่

API เขียนเฉพาะ intake อ่าน projection ที่จำเป็น ไม่มี credentials; scanner read-only
engine เขียนใต้ owner RLS; migrator เท่านั้นเป็น table owner
migration ไม่ backfill protection ให้ไม้เก่าและไม่เปลี่ยน protection โดยเดาว่าผู้ใช้ต้องการ
reset wallet ต้องตรวจ active allocation/unresolved protection work เพิ่มใน proof เดิม
แยก protocol readiness: เปิดรับ F-17 หลัง migration + engine ที่เข้าใจ allocation พร้อม
ห้าม mixed old financial writer ที่ไม่รู้จัก allocation ทำงานพร้อมเปิด F-17
rollback runtime หลังเริ่มใช้ต้องหยุด intake และใช้ compatible worker จัดการ protection
ค้างจนปลอดภัย; ห้าม downgrade ลบข้อมูลทางการเงิน/ประวัติที่มีอยู่แล้ว

### Approved migration rollback amendment — 2026-11-05

เจ้าของอนุมัติให้0063/0064 downgrade ได้เฉพาะ protocol ปิดและไม่มีข้อมูล F-17
รวม requests, manual-order bracket/allocations, projections/progress, immutable history
และ protection audit events; ไม่อนุญาตลบประวัติแม้ protection terminal แล้ว
ใช้ ACCESS EXCLUSIVE locks และตรวจทุก owner ด้วย migration-owner visibility ภายใน
transaction ตาม pattern `backend/migrations/versions/0061_kill_switch.py::downgrade`
ถ้าพบข้อมูลให้ rollback รวม FORCE RLS/DDL; กรณีว่าง restore shared audit/reset contracts
ก่อนถอด schema ของ F-17 และทดสอบ empty down/up สองรอบด้วย F-03 tests เดิม
Numbered migrations คง self-contained ตามของเดิม ไม่ import runtime policy หรือ migration รุ่นใหม่
การเปลี่ยนนี้ไม่อนุญาต financial/runtime downgrade เมื่อมีข้อมูลหรือ protocol ยังเปิด

## ความเสี่ยงและหลักฐาน

| ความเสี่ยง | หลักฐานใน validation |
|---|---|
| double sell / reservation ซ้ำ / เงินหรือ PnL เปลี่ยน | V-02–V-06, V-10 |
| trigger หายเมื่อไม่มี active order หรือ restart | V-07–V-09 |
| stop/risk/catalog sweep ยกเลิก protection | V-11 |
| ผู้ใช้/โหมด/episode ปะปนและ false success | V-12–V-15 |
| schema/grants/protocol ทำ old writer ละเมิด allocation | V-16 |
| shared core/matcher กระทบหลายระบบ | V-17 และ full regression ก่อน merge เมื่อเข้าเกณฑ์ testing §7 |

## Checkpoints

| ขั้น | งานและการตรวจ |
|---|---|
| M1 | core contracts/transitions + golden/property/parity tests V-01–V-04 |
| M2 | migration, allocation, durable request/recovery และ PostgreSQL tests V-05/06/09/12/16 |
| M3 | fill/trigger/exit integration, worker/safety และ SLA V-07–V-11/17 |
| M4 | API/generated types/shared UI และ targeted end-to-end V-13–V-15 |
| Feature candidate | ทุก Feature criteria ผ่าน พร้อม static checks/review/required CI; ตรวจ full regression ก่อน merge หาก diff แตะส่วนกลางหลายระบบตาม testing §7 |
| Batch — ท้ายชุดที่ 4 | V-18 รวม regression/cross-feature E2E และชุดยาวเดิมที่เกี่ยวข้อง; ไม่สร้าง profile ใหม่หรือลดเกณฑ์เอง |
| Release — ชุดที่ 9/ก่อน Live | V-19–V-20 และ dependency criteria; คง Pending Dependency/Full Validation จนมีผลจริง |

ทำ M1–M4 ต่อเนื่องเมื่อ plan/validation ได้รับอนุมัติ ไม่หยุดขอคำสั่งท้าย milestone
เมื่อครบทั้ง feature ให้แจ้ง **Ready for Code Review** พร้อมผล/งานค้าง/ความเสี่ยง แล้วหยุด
รอ `review code`; หลังแก้ findings รอคำตอบว่าจะ `refactor the code` ต่อหรือไม่
หลัง refactor ที่อนุมัติให้ validation ต่อทันที ใช้ผลเดิมที่ยัง valid
commit/push/merge เฉพาะคำสั่งเจ้าของ และติดตาม CI ตาม AGENTS.md

### Approved CI isolation amendment — 2026-11-05

หลัง read-only diagnostic บน 2407df2 เจ้าของเลือก A: แยก F-17 integration tests
ไปใช้ freshly migrated test database ใน required backend CI โดยคง tests/assertions
และ production logic เดิมทั้งหมด ใช้ `.github/workflows/ci.yml` และ
`backend/scripts/reset_ci_test_database.sh` ซ้ำตาม isolated migration/global-state steps เดิม

ชุด pytest หลักใช้ `--ignore=tests/infra/protections` แล้วเพิ่ม required step หลัง reset
ให้รัน `uv run pytest tests/infra/protections` ภายใต้ marker defaults เดิม;
`isolated_migration` guards ยังคงรันแยกหลัง reset ตามเดิม ไม่มี test ถูกตัดออกจาก CI
ตรวจ collection ว่าชุดหลักและชุดแยกรวมกันเท่าชุดเดิมและไม่ซ้ำกัน ก่อนติดตาม required CI
บน candidate ใหม่ การแยกฐานทดสอบนี้ไม่เปลี่ยน runtime isolation หรือ scheduler policy

## NC-F17-06 — Approved integration amendment

Correction ที่ทำให้ protection allocation ไม่ปลอดภัยเข้าสู่ conflict/unavailable
ตาม requirements NC-F17-06; ผู้ใช้จัดสรรใหม่อย่าง explicit ผ่าน revision-checked
replace/cancel เดิม ไม่จัดลำดับตัดชุดเอง ไม่แตะ exit ที่ส่งแล้วโดยเดา
V-10 ต้องตรวจ conflict → authoritative reconciliation → explicit allocation repair
→ resume รวม duplicate repair, stale revision, unknown exit และหลาย instance
ก่อนเปิดรับคำสั่งที่อาศัย quantity นั้น; ห้ามแสดง protected ระหว่างยังขัดกัน

## NC-F17-07 — Approved amendment: manual SELL แบบ A

ใน admission transaction ตรวจ expected protection revisions และ authoritative quantity
ลด allocation ของชุดที่เลือกก่อนสร้าง ordinary SELL reservation; rollback การลดหาก
admission ไม่ผ่าน เมื่อ admission commit แล้ว ให้ cancel/expired ใช้ F-15 เดิมคืน reservation
เป็น available quantity ไม่เรียก re-arm/restore protection เดิม รวมกรณี partial fill
ใช้ immutable linkage จากคำขอ SELL ถึงชุด/revision/quantity ที่ลดสำหรับ audit/replay
และใช้ผลคำขอเดิมเมื่อ retry ไม่ลด allocation ซ้ำ
UI แจ้งผลก่อนส่งและแสดง unprotected quantity หลัง terminal ตาม snapshot จริง
V-04/06/15 ครอบคลุม admission rejected, accepted→cancel, partial→cancel/expired,
reload/retry, trigger race และการคง protection ของส่วนที่ไม่ได้เลือก

## Internal Paper checkpoint - NC-SET4-12 Approved A

Owner approved the [internal-pilot requirements/plan/validation amendment](internal-paper-acceptance-amendment.md)
on2026-11-06. Use its parameters as the single source of truth. Scoped harness/checks
and conditional campaign are authorized. Existing100-account results, Release gates,
Completed definition and Git/deploy permissions remain unchanged.


NC12 §16 — owner approved2026-11-07: internal20-account engine processing acceptance
is p95≤500ms/p99≤2s; retain250ms/1s as a separately reported target with warning.
This supersedes IP-R4 only for internal engine-processing acceptance. TP/SL start≤1s,
snapshot limits, financial/safety correctness, workload/duration and100-account Release
criteria remain unchanged. Complete owned pool inventory includes the read-only admin
observer; missing evidence is Incomplete and proven violations remain Failed. See
[approved §16](internal-paper-acceptance-amendment.md#16-revised-acceptance-and-complete-owned-inventory--approved2026-11-07).


NC12 §18 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V2 changes
W2 only to10commands/s/1200s with120cycles-per-owner/12000commands unchanged.
Completion allowance1260s; required book inputs12000 at10Hz. V1/defaults, money,
worker/pool/coordinator/retry and other phase definitions unchanged. Actual V2 name
is forwarded to worker subprocesses and recorded in manifests/timing revision.
Tests233 passed8.77s;5 profile rechecks passed0.31s after test typing correction.
Scoped Ruff/format passed5repo files and private runner; mypy passed5files. Private
runner retains its pre-existing broad cleanup exception with BLE001 excluded only
for that file. Production source hashes unchanged; prior safety evidence remains
valid. W1§16 passing evidence reused only for unchanged assertions. All earlier
Failed/Incomplete runs retained. No§17 diagnostic added or executed.

Next: one approved fresh-DB V2 W2 withpreflight (~25–30min including20min measured),
then overflow/W3/W4 conditional on passing each gate. No repeated W1/D20. A failed/
incomplete gate stops without retry. Internal pilot and F17 remain open pending gates.


NC12 §21 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V3 changes
W3 only to1800s/30cycles-per-owner/3000commands;7pinned fault kinds/durations retained
at180..1260s offsets. Selected duration drives hold/minimum, RSS window and30periodic
snapshot rounds(620total includingfinal20), with15000inputs and1830s completion
ceiling. V1/V2/default4h/282cycles/original schedule and240periodic rounds unchanged.
Short stability is labelled separately;4h Release remains Pending Full Validation.

Targeted220passed10.73s;6affected final rechecks passed1.50s; scoped Ruff/format and
mypy passed5repo files(private runner scoped Ruff excludes pre-existing BLE001 only).
Actual parent/reporting regression verifies1800s hold/minimum,30snapshot rounds,
short RSS and unchanged financial/counter/latency/resource predicates. Production
source hashes unchanged. Applicable W1/W2/overflow/production safety evidence reused;
no ceremonial reruns. See nc12-section21-*.xml/logs for evidence.

Next: approved one fresh-DB V3 short W3 with existing preflight, estimated35–45min
including30min measured/final replay/cleanup; passing permits W4. A failed/incomplete
gate stops without retry. Prior owner-stopped W3 remains Incomplete; no4h acceptance.


## Approved unified activity UI — 2026-11-08

Owner approved [layout amendment/validation](unified-trading-activity-ui-plan.md),
superseding only the separate TP-SL panel navigation. Existing financial logic,
release gates and publication approvals remain unchanged.


## Approved single-row activity UI — 2026-11-08

Owner approved [single-row amendment/validation](single-row-activity-ui-amendment.md),
superseding the two-level navigation layout only. One mixed table, distinct record
semantics and current-episode all-symbol scope; no financial/API rule changes.
