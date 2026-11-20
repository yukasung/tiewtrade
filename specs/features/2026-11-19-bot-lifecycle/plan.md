# F-20 — ส่วนต่อประสานกลยุทธ์ + วงจรชีวิตบอท — Plan

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-19 หลังแก้ผล deep review**
วันที่: 2026-11-19 (Asia/Bangkok)
Branch: `feature/f-20-bot-lifecycle`
ฐานข้อกำหนด: requirements.md Approved 2026-11-19 รวม NC-F20-01..04

## 1. แนวทาง

เพิ่ม pure strategy/lifecycle contracts ใน `core` และ orchestration ใน engine เดิม
ใช้ PostgreSQL เป็น authority ของ run/commands/decision progress และใช้ transaction locks,
claim revision และ fencing ของระบบเดิม ไม่เพิ่ม infrastructure หรือ service-to-service import
ไม่สร้างกลยุทธ์จริง ตาราง scheduling ตามกลยุทธ์จริง หรือ Live executor ในงานนี้

F-20 ส่งมอบ lifecycle ที่ทดสอบกับ Paper executor จริงได้โดย test strategy จาก tests เท่านั้น
production registry ไม่มี test strategy และไม่มี default ที่แปลงชื่อ `Grid Close System`
เป็นโค้ด ปุ่มเริ่มใน UI ปกติคง disabled จน F-21 และ activation gates พร้อม
Live มี shared domain contract/readiness rejection; ไม่อ้างว่าตรวจ Live execution ผ่านแล้ว

### ช่องว่างที่พบและทางเลือก

- `core.orders.OrderIntent` มี `OrderOrigin.BOT` แล้ว และ Paper worker มี risk admission
  สำหรับ non-manual แต่ยังไม่มี run/config/decision authority จึงใช้เพียง origin BOT
  เป็นหลักฐานสิทธิ์ไม่ได้ ต้องเพิ่มการตรวจ run/fence ที่ admission และก่อน commit execution
- `infra/paper_orders/manual_policy.py` และ manual request bridge รับผิดชอบ MANUAL
  โดยเจตนาของ F-16: ไม่ส่ง bot intent ผ่านฟังก์ชันที่บังคับ manual origin และไม่ผ่อนกฎนั้น
  เพิ่ม bot policy ที่ประกอบ shared checks และเรียก Paper dispatch/matcher เดิม
- `services/engine/kill_switch.py::_apply_resume` ยังไม่มี proof ของ strategy failure
  จึงปฏิเสธ SYSTEM resume อยู่ เพิ่มเฉพาะ proof ของ F-20 ที่ตรง cause/run/version
  ไม่เปิดทางลัดสำหรับ SYSTEM cause อื่นหรือใช้การรับทราบแทน proof

ทางเลือกคัดลอก matcher/risk/stop อีกชุดเพิ่มโอกาส Paper/Live และ manual/bot ต่างกัน
จึงเลือกเพิ่ม contract/policy ตรง boundary เดิมภายใต้ ADR-004 ไม่เปลี่ยนกฎเงินหรือ SLA
หาก implementation ต้องเปลี่ยนแนวทางนี้ให้บันทึก amendment ก่อนแก้ตาม AGENTS.md

## 2. ของเดิมที่จะใช้ซ้ำ

| Path / ส่วนเดิม | การใช้ |
|---|---|
| `backend/src/tiewtrade/core/orders.py` | OrderScope, OrderIntent, OrderOrigin, TradingMode, AdmissionPolicy; ไม่สร้าง order model คู่ขนาน |
| `backend/src/tiewtrade/core/money/` | Money/Quantity และ numeric operations เดิม |
| `backend/src/tiewtrade/core/trading_account.py`, `core/manual_trading.py` | AccountUse และ regression ของ manual/reducing behavior |
| `backend/src/tiewtrade/core/trading_stops.py`, `infra/trading_stops/`, `services/engine/kill_switch.py` | stop authority/cutoff, summary, resume requests และ progress เดิม |
| `backend/src/tiewtrade/infra/risk_limits/dispatch.py`, `policy.py` | owner locking, claim/CAS pattern และ transaction-scoped risk proof |
| `backend/src/tiewtrade/infra/paper_orders/dispatch.py`, `worker.py` | durable commands, claim/fencing, admission, matching และผล execution |
| `backend/src/tiewtrade/infra/positions/`, `infra/protections/` | authoritative activity, exposure/reservations และ protection lifecycle |
| `backend/src/tiewtrade/infra/platform/effects.py`, `storage.py` | durable catalog event/effect และ pair revision fence |
| `backend/src/tiewtrade/infra/market_data/indicator_reader.py`, `infra/indicators/` | อ่าน indicator/provenance เดิม; ไม่คำนวณซ้ำใน strategy/UI |
| `backend/src/tiewtrade/infra/db/session.py`, `infra/audit/` | RLS sessions, scan role, append-only audit และ redaction |
| `frontend/src/PaperBotPanel.tsx`, `KillSwitchControls.tsx`, `killSwitchJournal.ts` | แผงเดิม stop/resume UX และ recovery identity pattern |
| `frontend/src/components/ui/` | Button/Input/Select/Badge/Alert/Modal/Table กลาง |

UI source mapping: ใช้ `references/admin-template/src/pages/UiElements/Buttons.tsx`,
`Alerts.tsx`, `Badges.tsx`, `Modals.tsx` และ `pages/Forms/FormElements.tsx`
เป็น reference ของ controls/status/summary; runtime import จาก shared components เท่านั้น
คง compact panel และ amendments ของ Paper Spot Bot Panel ไม่ยกเลิกข้อยกเว้นอื่นนอก scope

## 3. Pure contracts และสถานะ

เพิ่ม `core/strategies.py` สำหรับ immutable descriptor, versioned configuration/state,
evaluation input, decision และผล execution ที่ผูกกับ intent เดิม กลยุทธ์ใน
`tiewtrade.strategies` implement protocol นี้และพึ่ง `core` เท่านั้น
เวลา/identity/market snapshot มาจาก caller; เงิน serialize เป็นข้อความตาม codec เดิม
configuration/state มี schema version และตรวจ roundtrip แบบ exact ไม่รับ executable code
หรือ import path จาก browser ผลลัพธ์ตรวจครบก่อน persist ห้ามใช้ output บางส่วนหลัง exception

Input identity ประกอบ run, strategy/config version และ authoritative source/event revisions
ใช้เป็น durable deduplication key; execution feedback มี identity/revision แยกจาก market input
ไม่ใช้ timestamp อย่างเดียวกันซ้ำ และไม่ทำให้ warm-up incomplete เป็น no-op ที่เลื่อน cursor
จนพลาด input ที่ยังรอได้ เงื่อนไข trigger/warm-up/catch-up จริงให้ F-21 ประกาศก่อนเปิดใช้งาน

เพิ่ม `core/bots.py` สำหรับ transition function โดยแยก run lifecycle ออกจาก command receipt
และ F-19 order-cleanup progress:

| สถานะ | ความหมาย / ทางออก |
|---|---|
| `STARTING` | รับ start intent แล้ว รอ engine ตรวจ authoritative prerequisites; ยังไม่ประเมินกลยุทธ์ |
| `RUNNING` | ผ่าน readiness และไม่มี stop/latch; ประเมินได้เฉพาะ input ที่ผ่าน contract |
| `PAUSED` | ข้อมูลตลาด/บัญชีไม่พร้อม พร้อม reason; กลับผ่าน reconciliation และ loss recheck |
| `RECOVERING` | หลัง restart/takeover ตรวจ state, intents/results และ reconcile; ไม่เปิดความเสี่ยง |
| `STOPPED` | durable user/platform/system/loss/catalog cause; เปิดกลับตาม F-19 หรือคงหยุด |
| `RETIRED` | run เก่าที่หยุดและพิสูจน์ flat/ไม่มี orders แล้ว ถูกแทนด้วย run ใหม่; history ยังอยู่ |

Active slot ต่อ `(owner, account, mode)` ครอบคลุมทุกสถานะยกเว้น RETIRED รวมพัก/หยุด/recovery
เพื่อกันการข้าม stop หรือรับช่วง inventory การแทน run เดิมต้องเป็นคำขอที่เจ้าของยืนยัน
โดยระบุ run/revision เดิม และ revision ของ stop/summary/reconciliation ที่เกี่ยวข้อง
นำกฎสิทธิ์ การรับทราบ และหลักฐานเฉพาะสาเหตุของ F-19 มาตรวจใน transaction เดียวกับการแทน run
ผู้ใช้ปลดได้เฉพาะ stop ที่ F-19 อนุญาตตามหลักฐานปัจจุบัน หากยังติด platform stop, loss latch
หรือ stop อื่นที่คำขอนี้ไม่มีสิทธิ์ปลด ให้ปฏิเสธ

ภายใต้ lock เดียวกับ admission ตรวจซ้ำว่า run เดิมยัง STOPPED และไม่มี position/order
ที่ระบบดูแลในบัญชีและโหมดนั้น รวมถึงคำสั่งค้างส่งและผลที่ยังไม่ทราบ ตรวจ readiness ของ run ใหม่
แล้ว commit การจัดการ stop ที่ได้รับอนุญาต, retire run เดิม, สลับ active slot ไปยัง run ใหม่
และบันทึกผล/audit พร้อมกัน หากหลักฐานเปลี่ยนหรือขั้นใดล้มเหลว ให้คง stop และ run เดิมไว้
run เดิมไม่มีช่วงกลับเป็น RUNNING และ decision ที่ถือ revision เดิมหมดสิทธิ์ commit
การ resume run เดิมพร้อม exposure ใช้ F-19 ตามเดิม

Strategy/config pin ของ run เปลี่ยนไม่ได้ การกลับจาก PAUSED ไม่สร้าง run ใหม่ ไม่ล้าง cause
การ restart จาก RUNNING ต้องผ่าน RECOVERING; user/platform/system stop ไม่ฟื้นเอง
คืนสถานะไม่ได้/ไม่มี cause ให้คง STOPPED และแสดง unavailable ไม่เดาว่าไม่เคยหยุด

## 4. Persistence และ concurrency

เพิ่ม migration ถัดจาก Alembic head ที่ตรวจจริงตอนเริ่มงาน ไม่จองเลขล่วงหน้า:

| ข้อมูลใหม่ | ข้อบังคับ |
|---|---|
| `bot_runs` | owner/account/mode, Paper wallet/episode, pinned descriptor/config/state version, lifecycle revision, source progress; partial unique active slot ต่อบัญชี/โหมด |
| `bot_control_requests` / results / dispatch | append-only request/result, action/payload fingerprint/idempotency key, durable claim/revision; แยก requested จาก applied |
| `bot_decisions` และ order links | input identity, pinned versions, state before/after, validated intents/result links; unique input ต่อ run และ unique intent ordinal |
| `bot_run_events` / stop proof | append-only transition/cause/actor และ proof ที่ผูก run revision, strategy/config/state, stop identity/generation; ไม่ใช้ boolean ว่าแก้แล้ว |
| consumer progress | durable catalog/execution event receipts; ส่งซ้ำไม่ทำ side effect ซ้ำ |

Projection/dispatch/state ที่แก้ได้แยกจาก facts ที่เพิ่มอย่างเดียว Owner/mode/run linkage
ใช้ composite constraints ป้องกัน cross-owner/mode แม้ application ส่ง key ผิด
ตาราง user data ใช้ RLS และ grant ตามมาตรฐาน; engine scanner คืน IDs ที่ต้องทำงานเท่านั้น
API เขียนเฉพาะ inbox ผ่านสิทธิ์จำกัด อ่าน views/receipts ไม่แก้ run/order/stop โดยตรง
run events/audit ที่โตต่อเนื่องใช้ partition/retention pattern เดิม ไม่เพิ่มการลบ history

Lock ordering: global stop shared/exclusive ตาม F-19 → owner financial lock ของโหมดเดิม
→ run/claim fence → catalog pair fence ตามลำดับคงที่ที่ทดสอบกับ callers จริง
ไม่ตั้ง lock ใหม่แทน owner lock เดิม; ห้าม reverse lock order ระหว่าง stop/admission/fill
หาก claim เสีย fence ให้ยกเลิก transaction ก่อน commit financial state
หลายโหมดมี active slot แยก แต่ preference บัญชี MANUAL/BOT ยังเป็นของเดิม
ไม่เปิด concurrent writers ให้ข้อมูลบัญชีชุดเดียวกัน

Decision commit ต้องทำ input receipt, state progress, durable order intent และ audit
ใน transaction เดียว ไม่ publish ก่อน commit Evaluation ทำจาก pinned immutable snapshot
แล้ว recheck source/run/fences ก่อน commit; revision เปลี่ยนต้อง discard ผลเก่า
ไม่อ่าน indicator ยาว/รันกลยุทธ์ขณะถือ financial locks โดยไม่จำเป็น
กลยุทธ์ไม่มี side effect จึง discard/re-evaluate ได้ แต่ durable decision เดิมห้ามสร้าง order ใหม่
ผล unknown ตามรอย order เดิมจนได้ authoritative result ไม่สร้าง intent ทดแทน

Migration เป็น additive ไม่เปิด scheduler/admission เมื่อ upgrade; runtime เก่าที่ไม่รู้ bot
ต้องไม่รับ claim บอท Proof/version compatibility ใช้ pattern readiness เดิม
Downgrade ได้เฉพาะเมื่อไม่มี run/requests/financial links/history ที่จะสูญหาย หากมีให้ refuse
โดยไม่ลบข้อมูลสำคัญ ทดสอบ both empty roundtrip และ populated refusal

## 5. Engine และ integration

เพิ่ม `infra/bots/` สำหรับ requests/views/claims/storage/proofs/input assembly และ
`services/engine/bot.py` สำหรับ bounded owner-fair orchestration ใช้ scan hints แล้ว
กลับ owner RLS session ไม่ถือ scanner เป็น authority ไม่ใช้ Redis เป็น queue แหล่งเดียว
ทำงานภายใน engine boundary เดิม มี explicit composition ที่ปิดโดยปริยาย
ไม่เพิ่ม worker เข้า production Compose หรือเปลี่ยนค่ารอบ scheduling เดิมใน F-20

1. Control round ตรวจ BOT/readiness/flatness และ active slot ก่อน start หรือ replacement
   คำขอซ้ำคืนผลเดิม ใช้ key ซ้ำแต่ payload ต่างให้ conflict หลัง timeout อ่าน receipt
   ด้วย key เดิมตาม §6
2. Decision round อ่าน declared input ผ่าน readers เดิม ตรวจ provenance/readiness และ
   evaluate strategy version ที่ allowlisted ฝั่ง server; test strategy อยู่ `backend/tests/` เท่านั้น
3. ประกอบ bot admission policy: BOT/run/strategy ownership + common risk, funds,
   reservations, catalog, constraints, stop fences; ใช้ OrderIntent BOT แล้วส่ง `submit_order`
   ไม่ผ่าน manual HTTP request bridge แก้ Paper worker ให้ recheck bot run/decision fence
   ก่อน admission/fill โดยไม่บล็อก cancel/protection/reducing operations ที่กฎเดิมอนุญาต
4. ผล admitted/rejected/filled/partial/canceled/unknown จาก matcher/protection เดิม
   กลับเป็น feedback contract; persisted revision กัน feedback เก่าย้อน state
5. Consume F-18/F-19 authority และ F-37 withdrawal events การถอนคู่มีผลกับทุก run
   ที่ผูกกับคู่นั้นในขอบเขต revision ของเหตุการณ์ ครอบคลุมทุกเจ้าของและทุกโหมด
   ใช้ catalog fence กัน opening ก่อน cleanup และบันทึก stop/progress ของแต่ละ run
   ตาม pair และ withdrawal revision เพื่อกันผลซ้ำ การเพิ่มคู่คืนไม่ปลด stop และ event เก่า
   ไม่ทำให้ run ที่เริ่มอย่างถูกต้องใน revision ใหม่ถูกหยุดย้อนหลัง รายงาน effect ครบเมื่อ
   notification และ order cleanup ที่เกี่ยวข้องเสร็จจริง
6. Strategy failure หยุด run พร้อม cause-specific proof path; revalidate pinned implementation,
   config/state contract, readiness และ reconciliation; สำหรับ evaluation error ต้องมีผล pure
   evaluation ที่สำเร็จและผ่าน output validation บน input ปัจจุบันโดยไม่ commit intent/state
   ไม่ถือว่า schema ถูกต้องอย่างเดียวพิสูจน์ว่าแก้ error แล้ว ผูก proof กับ stop generation ปัจจุบัน
   เจ้าของรับทราบบน summary เดิมจึง resume ได้ Proof หมดอายุเมื่อ inputs ที่พิสูจน์เปลี่ยน
   ไม่มี proof สำหรับ SYSTEM cause อื่นให้ปฏิเสธต่อ ห้าม probe ด้วยการส่ง order

ต่อ F-17 protection failure ใช้ policy เดิม ไม่ใช้ abnormal-stop policy กลบการปิดไม้
ที่ F-17 บังคับ ส่วน failure ปกติของ strategy ไม่แตะ position/protection
คง durable user-visible reason/exposure ใน status/read model; การส่ง Email/Telegram/LINE
ยัง Pending Dependency ไม่เพิ่ม provider ในงานนี้
Live intent/result adapters และ reconciliation proof จริงรอ F-22/F-23 ใช้ rejection
เมื่อ capability ไม่พร้อม ไม่ใช้ mock capability เป็นการอนุญาต Live production

## 6. API และ UI

เพิ่ม API owner-scoped (ชื่อ routes ต่อไปนี้เป็น contract ของแผนที่จะสร้าง OpenAPI):

| Route | พฤติกรรม |
|---|---|
| `GET /api/paper/bots/status` / `GET /api/live/bots/status` | current run/status/reason, pinned versions, readiness, exposure/protection และ dependency ที่ยังไม่พร้อม |
| `POST /api/paper/bots/requests` / `POST /api/live/bots/requests` | start intent พร้อม idempotency key และ server-validated strategy config reference กรณีแทน run ต้องระบุ run/revisions ตาม §3 ตอบ receipt เมื่อบันทึกคำขอสำเร็จ |
| `GET /api/paper/bots/requests/{request_id}` / Live คู่กัน | อ่าน receipt และผล applied/not-ready/rejected; wrong owner/mode ได้ not found |
| `GET /api/paper/bots/requests/by-key/{key}` / Live คู่กัน | อ่าน receipt เดิมเมื่อไม่ทราบ request ID ใช้ owner จาก session และ mode จาก route ตาม pattern F-19 หากไม่พบใน scope ให้ 404 |

Stop/resume ใช้ F-19 routes/journal/summary เดิม ไม่สร้าง semantics คู่ขนาน
Stop เรียกได้แม้ strategy registry ไม่พร้อม; resume ของ run อัปเดตโดย engine จาก
authority เดิมเท่านั้น GET/POST รับ mode จาก route ไม่เชื่อ body และไม่เปิด Live
start strategy/config reference ต้อง resolve จาก server registry; ไม่มี production definition
ให้ตอบ unavailable ไม่เอา selector หรืองบ draft มาประดิษฐ์ config
session/CSRF/rate controls เดิม; TOTP ใช้เฉพาะการกระทำที่มาตรฐานกำหนด ไม่เพิ่มข้อบังคับเอง

เชื่อมสถานะ/เหตุเริ่มไม่ได้ใน PaperBotPanel และพื้นที่ Live ที่มีอยู่ โดยใช้ component ร่วม
แต่ query keys/page/command paths แยกโหมด ไม่เพิ่มหน้าเต็มหรือย้าย navigation โดยไม่จำเป็น
stop/summary/protection และ SELL modal เดิมยังเข้าถึงได้ ปุ่มเริ่มปกติยัง disabled
จนมีกลยุทธ์และ activation พร้อม ไม่เปิดด้วย feature flag ฝั่ง browser
browser scenarios ที่ต้องเห็น running/paused/resume ใช้ isolated test app/seed ไม่เปิด endpoint
seed ใน runtime UI ไม่เพิ่ม parameter editor หรือเปลี่ยนความหมายช่องงบของ F-21

Query cache แยก owner/account/mode/episode/run; การเปลี่ยนผู้ใช้/logout/episode และ
late responses ต้องไม่แสดงข้อมูลเก่าของ scope อื่น recovery journal เก็บเฉพาะ identity
ของคำขอ โดยบันทึก key และขอบเขตก่อน POST ให้กู้คืนได้หลัง reload หาก lookup ยังไม่พบ
และต้องส่งซ้ำ ให้ใช้ key เดิมกับ payload เดิม การค้นไม่พบเพียงครั้งเดียวไม่ยืนยันว่าคำขอไม่เคย commit
เงิน/เวลาใช้ formatter เดิม
แสดง lifecycle กับ F-19 cleanup progress คนละความหมาย ไม่แสดง stopped complete ก่อนรู้ผล

## 7. ไฟล์ที่จะเพิ่มหรือแก้

| Path | งาน |
|---|---|
| `backend/src/tiewtrade/core/strategies.py`, `core/bots.py` | contracts, transitions, bot policy |
| `backend/src/tiewtrade/strategies/` | exports/boundary เท่านั้น ไม่มี production strategy |
| `backend/src/tiewtrade/infra/bots/` | durable control/run/decisions/readers/proofs |
| `backend/src/tiewtrade/services/engine/bot.py` | orchestration; composition แบบปิดโดยปริยาย |
| `backend/src/tiewtrade/infra/paper_orders/worker.py` และ callers ที่เกี่ยวข้อง | bot-origin fence/common admission โดยคง manual path |
| `backend/src/tiewtrade/services/engine/kill_switch.py`, `infra/trading_stops/` | run stop/resume integration และ strategy-specific proof |
| `backend/src/tiewtrade/infra/platform/effects.py` และ risk/protection callers ที่จำเป็น | durable consumers/acknowledgement ไม่เปลี่ยน business rules |
| `backend/migrations/versions/` | additive schema/constraints/RLS/grants/audit |
| `backend/src/tiewtrade/services/api/bot_models.py`, `bot_routes.py` และ router composition | owner routes/OpenAPI |
| `backend/openapi.json`, `frontend/src/api-types.ts` | regenerate จาก backend contract |
| `frontend/src/PaperBotPanel.tsx`, bot status/hooks/messages และ Live caller ที่มีอยู่ | shared status/control integration |
| `backend/tests/`, `frontend/src/` tests, isolated Playwright config ตาม pattern เดิม | contract, real-DB safety, parity, recovery และ UI |
| feature validation/evidence และ `specs/roadmap.md` | checkpoint/ผลจริง/dependency ไม่ทำสำเนาสถานะหลายแห่ง |

## 8. Milestones และ checkpoints

| ขั้น | ส่งมอบ / ตรวจ |
|---|---|
| M1 | contracts/transitions/versioned codecs; V-01..04 และ architecture checks |
| M2 | migration/RLS/active slot/requests/claim/atomic decision; V-05..08/17 |
| M3 | Paper dispatch/admission/feedback และ risk/stop/catalog/protection; V-09..13 |
| M4 | API/generated types/UI/recovery; V-14..16 และ affected M2/M3 regression |
| M5 | final diff/callers review → แก้ findings → refactor เฉพาะเมื่อมีประโยชน์ → affected checks; V-01..18 ระดับ Feature บน final candidate และ owner UI acceptance |

เมื่อ implementation ครบ แจ้ง **Ready for Code Review** พร้อมผล/งานค้าง/ความเสี่ยง
แล้วรีวิวต่อได้ทันทีตาม AGENTS.md ไม่รอคำสั่งระหว่าง implement/test/review/fix
owner UI acceptance เป็นด่านก่อน merge; การรีวิวอัตโนมัติไม่แทน owner acceptance
ก่อน publication รวมเอกสาร/หลักฐานที่เกี่ยวข้อง จากนั้นใช้ Git authorization เดิมเมื่อด่านครบ
หากแก้เกณฑ์เดิมแล้วยังไม่ผ่าน 3 รอบหรือเจ้าของแจ้งใช้เวลามากเกินไปให้หยุดตาม AGENTS.md

ท้ายชุดที่ 6 หลัง F-20/F-21 พร้อม: V-19/20 full regression และ cross-feature E2E
บน integrated candidate; ชุดที่ 9/ก่อนเปิดจริง: V-21 Live dependencies/notification/activation
ใช้หลักฐาน dependencies เดิมที่ยัง valid ไม่สั่ง workload/endurance/timed smoke เพิ่ม
ท้าย milestone หรือกำหนด SLA/campaign ใหม่ หากต้องมี profile ใหม่ให้เสนอก่อนรัน
ระหว่างรอคง `Pending Full Validation`/`Pending Dependency` และผล Failed/Partial เดิม

## 9. ความเสี่ยงและจุดหยุด

- Admission เปลี่ยนส่วนกลาง: ต้องตรวจ manual/reducing/protection/regression และ full
  regression ก่อน merge หากผลกระทบแบ่งขอบเขตไม่ได้ตาม testing §7
- Lock order/fence ผิดอาจเกิด duplicate orders หรือ deadlock: real PostgreSQL barriers
  และ crash matrix เป็น Feature gates ไม่เลื่อนเป็น Batch
- Dependency ยังไม่พร้อม: ไม่อ้าง F-19/F-37 หรือ Live ผ่านครบจาก fixtures ของ F-20
  F-21 trigger/config และ F-22/F-23 capability ต้องมี spec/หลักฐานของตัวเอง
- Plan/validation ได้รับอนุมัติแล้ว วันที่ 2026-11-19 ด่าน owner UI acceptance และ activation ตามเดิม

## M3 — ลำดับเชื่อม Paper worker

ชุดทดสอบ F-18/F-19 ที่อยู่ในแผนตรวจเดิมสร้าง BOT orders โดยตรงเพื่อทดสอบ
การยกเลิกออเดอร์ค้างและการกู้คืนก่อนมี run authority ตัวอย่างอยู่ใน
`backend/tests/infra/risk_limits/test_stops.py` และ `test_set5_acceptance.py`
จึงแยกการเพิ่ม guard สำหรับคำสั่งที่ผูกกับ F-20 ออกจากการเปลี่ยน fixtures
ช่วงเชื่อมต่อ คำสั่งที่มี decision link ต้องผ่าน run guard ทันที
ก่อนเปิด F-20 และก่อนถือว่า V-09 ผ่าน ต้องย้าย fixtures ให้ใช้หลักฐาน run จริง
และให้ worker ปฏิเสธ BOT intent ที่ไม่มี link เสมอ คง assertions ของ F-18/F-19
และขอบเขต workload ที่อนุมัติเดิม ไม่เปิด bot scheduler ระหว่างที่ guard ยังไม่ครบ

### M3 — หลักฐานสำหรับคำสั่งปิดจาก F-17

ตรวจ callers พบว่า `infra/protections/worker.py::queue_exit` สืบทอด origin
ของ protection ไปยัง SELL ดังนั้นการบังคับ decision link กับ BOT ทุกกรณี
จะปฏิเสธคำสั่งปิดที่ F-17 สร้างให้กับ position ของบอท แก้ตามอำนาจวิศวกรรม
ใน AGENTS.md โดยใช้ immutable `paper_protection_exits` เป็นหลักฐานเฉพาะ
SELL ที่ตรง command, order, owner, episode และ quantity แล้วตรวจ group
และจำนวนที่ลดได้ผ่าน F-17 และ admission เดิม ห้ามใช้แค่ origin หรือ side
เป็นหลักฐาน ไม่เปลี่ยนกฎ TP/SL หรือขยายสิทธิ์ส่งคำสั่งเปิด

### M3 — บันทึกและกู้คืนเมื่อ BOT ตั้ง TP/SL ไม่สำเร็จ

F-17 ระบุ CLOSE_AND_STOP แล้ว แต่ Paper worker เดิมบันทึก FAILED เหมือนเทรดมือ
จึงเพิ่มหลักฐาน setup-failure exit แยกจากการ trigger ตามราคา เมื่อถึง failure
ที่ F-17 กำหนด ให้หยุด run และส่งคำขอ SYSTEM stop กับ exit ของจำนวนที่คุ้มครอง
ใน transaction เดียว ใช้ quantity/market constraints เดิมและ identity ตาม
protection revision หากหลักฐานตลาดไม่พร้อมหรือจำนวนไม่ผ่านให้บันทึก exposure ที่ยัง
ปิดไม่ได้ตามจริง ไม่ส่งคำสั่งที่ไม่ผ่านข้อจำกัดหรือสร้าง MARKET exit ใหม่วนเอง

### M5 — ตรวจ authority ก่อน fill และแสดงผลที่ไม่พร้อม (2026-11-19)

จากการตรวจ `_apply_inputs` พบว่า accepted BUY ใช้ shared pair checkpoint ได้แม้
run เปลี่ยนเป็น PAUSED/STOPPED และคำสั่งอื่นเป็นผู้ขับ checkpoint จึงต้องส่งชุด
order IDs ที่ไม่มี current run authority เข้า pure matcher ก่อนทุก input ภายใต้
owner lock เดิม ไม่ยกเลิก order หรือเปลี่ยน reservation เพียงเพราะ pause และไม่บล็อก
SELL/protection exits เลือกใช้ matcher เดิมแทนสร้าง executor ใหม่ พร้อม real-DB
regression ของ accepted order ก่อนและหลัง pause ตามอำนาจวิศวกรรม AGENTS.md

UI จะอ่านเหตุ SOURCE_NOT_READY/WORKER_TAKEOVER และแสดง status fetch failure
ชัดเจน พร้อมใช้ F-19 summary/control เดิมสำหรับหยุด/เปิดกลับ ไม่เพิ่ม transition
หรือปลด start disabled; exposure/protection ใช้ activity/protection เดิมในหน้า Paper
ประกอบกับ F-19 summary ไม่สมมติว่าหยุดแล้วไม่มี exposure

### M5 — แยก source outage จาก strategy failure

ตรวจ input assembly พบว่า `held_and_reserved` อาจปฏิเสธข้อมูลบัญชีด้วย
SourceUnavailableError นอกขอบเขต pure evaluation จึงต้องเปลี่ยน run เป็น PAUSED
แทนปล่อยให้ทั้ง scheduler round ล้ม เพิ่มการ defer domain admission/conflict ต่อ run
ที่ engine boundary เพื่อไม่ให้บัญชีหนึ่งตัดรอบบัญชีอื่น ใช้ exception เดิม ไม่ retry
โดยสร้าง order identity ใหม่ ไม่จับ database error เป็น strategy failure และไม่ผ่อน admission
ตามอำนาจวิศวกรรมที่อนุมัติไว้

### M4/M5 — status read model สำหรับ exposure/protection

เพิ่มข้อมูล holdings ของ current Paper episode และ protection allocation/state จริงใน
status response ตาม §6 โดยใช้ `paper_wallet_reset_readiness`, position projections
และ protection projections ที่ API มีสิทธิ์อ่านอยู่แล้ว ไม่อ่าน config/state ภายใน run
หาก position proof ไม่พร้อมจะระบุ exposure unavailable แทนรายการว่าง Live ระบุ unavailable
และไม่เรียก venue การแสดง quantity ของ protection ใช้คำว่า allocation ไม่รับรอง executable
coverage จาก ARMED อย่างเดียว ใช้หน้ารายละเอียด F-17 เดิมเมื่อต้องทราบ executable/dust
เป็นการปิดช่องว่าง RQ-13/25 ภายในอำนาจวิศวกรรมเดิม ไม่เปลี่ยน policy การเงิน

### M5 — scheduler assertions ต้องแยก global counts จาก owner oracle

การรันทดสอบซ้ำบน DB isolated เดิมพบ `evaluated=2` เพราะ scheduler มีหน้าที่กวาดทุก
owner รวม fixture ที่ commit จากรอบก่อน จึงแก้ assertion ของยอดรวม round ให้ตรวจว่า
มีงานสำเร็จอย่างน้อยหนึ่งรายการ คง exact assertions ใต้ owner RLS ว่ามี decision เดียว,
state/proof/run/financial effects ตรงเดิมครบ ไม่เปลี่ยน scheduler หรือกลบผลทางการเงิน
ใช้ DB ใหม่สำหรับ final group เพื่อไม่ให้ retained hints เกิน bounded scan ของ fixture
อำนาจแก้ harness ที่วัดผิดตาม AGENTS.md; ผลรอบที่ล้มยังบันทึกไว้

### M5 — ปิด finding เรื่อง strategy evaluation ใต้ financial lock

candidate แรกยังเรียก pure strategy ขณะถือ global/owner locks ซึ่งขัดกับ §4 และ
อาจหน่วง F-19 จึงแยก snapshot preparation กับ decision commit เป็นสอง transactions
service ประเมิน pinned immutable snapshot ระหว่างสอง transaction; transaction หลัง
ประกอบ snapshot ใหม่และตรวจ equality รวม run revision, lease generation, versions,
configuration/state, market/account/feedback ก่อนใช้ผล ถ้าเปลี่ยนให้ discard ไม่ commit
state/intent/proof ทั้ง success และ error ใช้ fence เดียวกัน ไม่ให้ stale error หยุด run ใหม่
นี่เป็นการทำตามแผนที่อนุมัติและอำนาจวิศวกรรมเดิม ไม่เปลี่ยน trigger หรือกฎการเทรด

### M1/M5 — ส่ง deterministic identity ให้กลยุทธ์จาก caller

ตรวจ contract พบว่า StrategyInput ยังไม่ส่ง owner/mode/episode/run/input identity
ให้ pure implementation กลยุทธ์จึงไม่สามารถสร้าง scoped intents และ stable UUIDs
โดยไม่พึ่งค่าจากภายนอก เพิ่ม immutable scope/run/input identity ใน snapshot และตรวจ
ให้ตรง evaluation scope ใช้ UUID5 จากข้อมูลที่ caller ส่งเท่านั้น ไม่เพิ่ม randomness
ใน core หรือสูตรกลยุทธ์จริง แก้ fixtures ให้ใช้ context เดียวกัน พร้อม parity/identity tests
ตาม RQ-01/04/05/16 และอำนาจวิศวกรรมเดิม ก่อนเปิด contract นี้ให้ F-21 ใช้งาน

### M5 — ขยาย Paper isolation gate ให้ครอบ F-20

isolation gate เดิมปฏิเสธ dependency ใหม่ `bots.authority`/`bots.system_stop` แม้ไม่มี
Live/network/credential path เพิ่ม จึงเพิ่ม F-20 source files ใน scanned roots และ
allowlist เฉพาะ imports ภายในที่จำเป็น คง forbidden modules/markers และ transitive
negative fixtures ทั้งหมด ไม่เพิ่ม exception ให้ crypto/venue/network ตาม RQ-23/26
และอำนาจแก้ harness เดิม พร้อม rerun import/purity/isolation gates

### M5 — canonical UUID ที่ขอบเขต DB → pure context

หลังเพิ่ม strict run identity ตรวจ real-DB พบ scheduled fixture ถูก SYSTEM stop
ก่อน decision แม้ input พร้อม สาเหตุคือ asyncpg คืน UUID subclass แต่ core contract
รับ `type(...) is UUID` ตาม pattern เดิม จึง normalize UUID ที่ snapshot assembly
ด้วย `UUID(str(run_id))` ไม่ผ่อน strict contract และเพิ่มการตรวจผ่าน scheduler จริง
คงผล Failed ของรอบก่อนใน evidence รวม safety gate scan ของ F-20 ที่ขยายแล้ว

## Review corrections — owner instructed “แก้ไข” 2026-11-19

แก้ findings ของ deep review ทั้งหกภายใต้อำนาจวิศวกรรม AGENTS.md โดยคง requirement,
trigger ของกลยุทธ์, risk/เงิน และ activation เดิม ทางเลือกปล่อย pending หรือผ่อน tests
ไม่ปิดความเสี่ยง จึงเลือกใช้ implementation/readers และ PostgreSQL patterns เดิมดังนี้:

- Decode/version-check config/state ก่อน duplicate-input fast path และทุก recovery
  readiness transition; schema/version failure ใช้ SYSTEM stop เดิม ไม่เพิ่ม order
- อ่าน indicator จาก F-11 prepared generation/checkpoint/reader เดิมสำหรับ descriptor
  ที่ประกาศ quote/feedback trigger และ timeframe ชัดเจน อ่านหนึ่ง closed point ณ input
  time พร้อม warm-up/source proof โดยไม่สร้าง candle-close/catch-up trigger เพิ่ม
  ย้ายเฉพาะ unsigned read claims และ DatasetChangedError ออกจาก crypto ไป data-only
  module และ re-export ชื่อเดิม เพื่อให้ Paper reader ไม่พึ่ง credential/signing modules
  อ่าน suffix แบบ bounded นอก financial locks; ก่อน commit ถือ source-guard share fence
  ผ่าน engine-only function และตรวจ generation/proof/readiness ซ้ำ ไม่ให้ stale inputs
  เลื่อน state/cursor เพิ่ม read-only grants เฉพาะ public indicator data ใน migration ใหม่
- SYSTEM recovery/proof ผูก unresolved stop generation และ immutable failure linkage
  แยกจาก latest run event; catalog stop ยังอยู่และไม่อนุญาต run เดิมกลับ RUNNING
  เมื่อคู่ถูก add-back อนุญาต pure proof เพื่อ owner acknowledgement/replacement เท่านั้น
  ยังคง readiness/flatness/F-19 transaction ก่อนสร้าง run ใหม่
- เก็บ recovery last-attempt ใน owner-RLS PostgreSQL projection หนึ่งแถวต่อ run และ
  เรียง scan จากรายการที่ยังไม่เคยตรวจ/เก่าสุด จึงไม่ให้ 20 failures แรกกีดกันคนถัดไป
  เป็น scheduling hint ไม่ใช่ stop/proof authority ไม่เพิ่ม infrastructure
- จำกัด status protection summary ตาม page size 20 เดิมของ F-17 อ่านเพิ่มหนึ่งแถว
  เพื่อแจ้งว่ามีรายการเพิ่มเติม และให้ failed/conflicted allocations มาก่อน ใช้ activity
  เดิมดูรายการทั้งหมด ไม่ตัด exposure เงียบ ๆ ไม่เปลี่ยนยอดหรือ protection policy
- เติม process-kill/DB-disconnect ก่อน commit และ lost-ack หลัง commit ด้วย subprocess
  และ database จริง ตรวจ run/decision/commands/links/audit/cash/reservations/positions
  พร้อม barrier races ของ replacement-vs-fill/stop/stale decision และ source/lease
  invalidation/feedback ordering ตาม V-05/07/08/10/13 ไม่ส่ง Live order

บันทึกผล Failed/Partial เดิมไว้ และตรวจ targeted safety/reader/API/UI regressions กับ
migration upgrade/downgrade/grants ที่เปลี่ยน ไม่เริ่ม workload/endurance campaign หรือ
ข้าม owner acceptance/required CI ที่ยังบังคับก่อน merge

### Indicator fixture — owner-approved extra attempt

หลัง fixture ล้มสามรอบ (advance argument, checkpoint boundary และ PostgreSQL timestamp
inference) หยุดตาม AGENTS.md และเจ้าของอนุมัติแก้ `CAST(:now AS timestamptz)`
ใน jobs/generation SQL แล้วตรวจ indicator tests เดิมอีกหนึ่งรอบไม่เกิน 2 นาที
คง assertions/thresholds เดิมทั้งหมด ไม่ลด source/warm-up requirements; เก็บผลล้มเดิม
และผลรอบที่อนุมัติแยกใน evidence เดิม ไม่ขยายเป็น campaign หรืออนุมัติ Live

### Review validation — terminal execution feedback

ขณะเติม V-13 พบว่า F-15 เก็บ FILLED/PARTIALLY_FILLED ใน authoritative order projection
ที่ผูก last_event_id กับ matcher checkpoint (ไม่ใช่ fill event) แต่ F-20 อ่านเพียง raw
FILL fact จึงยังไม่ส่ง actual disposition ให้กลยุทธ์ เพิ่ม read-only feedback จาก
projection และ latest immutable fill ของ order/owner/episode เดียวกัน
ไม่เขียน fill/order/เงินเพิ่มหรืออนุมานสถานะจาก signal ให้ fact มาก่อน disposition
ของ source เดียวกัน ใช้ source sequence กับ phase เป็น monotonic feedback revision
และ durable input identity แยก `order:`/`state:` ป้องกัน duplicate/reordered delivery
ยังไม่มี production strategy ที่ใช้ revision format นี้ และไม่เปลี่ยน identity ของ raw facts
ตรวจ full/partial execution, terminal state, duplicate older receipt และ state ไม่ย้อนกลับ
พร้อม financial oracle เดิม ตามอำนาจวิศวกรรม AGENTS.md ไม่เพิ่มกฎเทรดของ F-21

### Recovery/readiness review corrections — 2026-11-20

เจ้าของสั่ง “แก้ไข” หลัง review พบ 2 High/1 Medium: recovery probe ใช้ duplicate
shortcut จึงไม่ได้ evaluate strategy จริง; PAUSED ที่ lease เดิมยังอยู่ข้าม full
reconciliation/pending-command checks; STARTING ไม่บันทึก pause/reason เมื่อ source หาย
แก้ตามอำนาจวิศวกรรมใน AGENTS.md โดยคง RQ-09/11/20, F-19 และเกณฑ์เดิม:

- จำกัด duplicate no-op shortcut ให้ normal delivery เท่านั้น ทุก recovery probe
  ต้องผ่าน pure evaluation/contract จริงก่อนออก proof และยังไม่ส่ง intent ใด
- บันทึก input identity ที่ทำให้ strategy evaluation ล้มใน immutable failure event
  ใช้ JSON details เดิม ไม่เพิ่มตารางหรือ migration; หากเป็น execution feedback
  ให้ probe อ่าน fact เดิมจาก feedback reader เดิมตาม identity และ scope ถ้าอ่านไม่ได้
  คงหยุด ไม่เปลี่ยนไปพิสูจน์ quote/no-op แทน หากเป็น quote ใช้ current verified quote
  ตาม proof policy เดิม; version/decode failure ที่ยังไม่มี input ใช้ current probe เดิม
- PAUSED ต้องผ่าน full source reconciliation และตรวจ unresolved commands เช่นเดียวกับ
  RECOVERING ก่อนทุก readiness/duplicate path ไม่ใช้ flatness เป็นเงื่อนไข resume
  จึงยังเปิดกลับ run เดิมพร้อม exposure ได้ตาม F-19
- ใช้ STARTING→PAUSED transition เดิม พร้อม fixed readiness reason ที่ไม่เผย raw error
  เมื่อ market/account/risk ไม่พร้อม ไม่เปลี่ยน trigger, risk limit หรือ financial formulas
- เพิ่ม real-PostgreSQL regressions: duplicate quote + broken strategy ต้องไม่มี proof;
  failed feedback ต้องถูกประเมินซ้ำใน dry probe; same-lease PAUSED ต้องไม่เดิน state/
  intent เมื่อ pending command หรือ order proof ไม่พร้อม และ control-created STARTING
  ต้องแสดง pause/reason เมื่อข้อมูลหาย ตรวจ healthy recovery และ financial sources เดิม
  พร้อม targeted tests/diff review ไม่ขยาย indicator campaign ที่อนุมัติไว้หนึ่งรอบ

ทางเลือกใช้ proof/no-op เดิมหรือรอ lease หมดไม่พิสูจน์ safety จึงไม่เลือก; reuse
`feedback.py`, `system_stop.py`, `evaluate_published_quote`, control/start fixtures,
`internal_database` และ F-18/F-19 runtime เดิม เก็บผล Failed/Partial เดิมต่อใน evidence

ขณะ review correction พบ edge ของ feedback ที่อ่าน disposition จาก projection:
หากล้มที่ PARTIALLY_FILLED แล้ว F-19 cancel ส่วนค้าง สถานะปัจจุบันเป็น CANCELED
reader จึงไม่สามารถสร้าง `state:<fill-id>` เดิมได้อีก บันทึก canonical feedback
snapshot เฉพาะ status ที่อ่านและตรวจแล้วไว้ใน immutable failure event เดียวกับ identity
โดย reuse `ExecutionFeedback` contract; raw FILL ใช้ F-15 reader/codec เดิม ไม่คัดลอก
financial arithmetic และไม่ใช้ projection ใหม่
ปลอมสถานะเก่า ตอน probe ต้องตรวจ identity/order lineage และ decode snapshot ตรง
contract ก่อนใช้; legacy event ที่ไม่มี snapshot ใช้ reader เดิมและคงหยุดถ้าอ่านไม่ได้
เพิ่ม partial-fill→failure→cancel→dry-proof regression พร้อม cash/position oracle จริง
หากเป็น legacy evaluation-failure event ที่ยังไม่มี input identity field เลย
จะไม่เดาว่าล้มจาก quote; คงหยุดและบันทึก scheduling attempt เพื่อไม่กีดกัน owner อื่น
ส่วน version-unavailable ที่ cause ชัดเจนยังพิสูจน์การโหลดและ evaluate รุ่นเดิมได้
ใช้ full reconciliation กับ STARTING ด้วย เพราะ account/order proof อาจเปลี่ยนหลัง
control transaction แต่ก่อน evaluation แรก หากยัง unknown หรือมี pending command
ให้บันทึก pause/reason เดิม ไม่คง STARTING เงียบ ๆ เพิ่ม order-source regression

### Scoped recovery/readiness refactor — 2026-11-20

เจ้าของสั่ง review/refactor เฉพาะงานล่าสุด โดยไม่เปลี่ยน behavior/business logic
ตรวจแล้ว runtime ใช้ `ExecutionFeedback`, transition, reader และ writer เดิมอยู่แล้ว
จึงไม่แยก abstraction ใหม่; เปลี่ยน conditional expression ที่เลือก replay/probe และ
saved/live feedback เป็น if/else ให้เห็นขอบเขตชัด และลบ default reason ที่ไม่มี caller ใช้
พบ SQL ตั้ง admission และ order-source state ซ้ำใน regression file ล่าสุด จึงรวมเป็น
private helpers ในไฟล์เดียว ใช้ session/transaction boundary เดิมและ bound parameters
ไม่แก้ fixture ร่วม, migration, UI หรือกฎเงิน/Live/stop/proof; คง financial assertions ทุกข้อ
ตรวจ 12 recovery/readiness cases, scheduled recovery caller และ Paper isolation
ร่วมกับ Ruff/mypy/import checks บน PostgreSQL แยก ไม่รัน indicator campaign เดิมซ้ำ

### Feature validation closure — owner instructed “เริ่มทำ” 2026-11-20

จับคู่ V-01..18 กับหลักฐานเดิมเป็นราย scenario ก่อนตรวจเพิ่ม ไม่ใช้ Partial แบบรวม
เป็นเหตุรันทุกชุดซ้ำ ใช้ผล F-11 indicator รอบที่อนุมัติแล้วต่อ ไม่ขยาย campaign นั้น
ช่องว่างที่ตรวจพบและงานภายในอำนาจวิศวกรรม/ขอบเขต RQ เดิม:

- เพิ่ม negative schema/version/transition tests ที่ยังขาด, replacement rollback
  หลัง retire/resume ก่อน commit, exposure/unknown flatness refusal และ proof binding
  matrix ด้วย real PostgreSQL/locks เดิม ตรวจเงิน/position/order/audit คู่กัน
- พิสูจน์ start receipt ด้วย API process ใหม่หลัง acknowledgement หาย ใช้ key/cookies
  เดิม ไม่ใช้ in-memory application state เป็น authority และคง rejected result เดิม
- RQ-09/25 ต้องแยก pending request จาก RUNNING แต่ status/UI ยังอ่านเฉพาะ run
  จึงเพิ่ม nullable pending_request_id ที่ query จาก inbox/results เดิมภายใต้ owner/mode
  RLS พร้อม index (owner,mode,requested_at,id) สำหรับ status polling ไม่เปลี่ยนการรับ
  คำขอหรือเปิด production registry/Live; บันทึก start-disabled เดิมให้เห็นครบ
  ใช้ `frontend/src/components/ui/Badge.tsx` และ Alert/Button เดิม อ้างอิง
  `references/admin-template/src/components/ui/badge/Badge.tsx` ไม่มี style ใหม่
- ทำ isolated browser harness ใน `backend/tests/` เท่านั้น reuse
  `tests/e2e_risk_app.py::lifespan`, production API/F-19/Paper workers, recorded public
  fixtures และ E2E DB guard เดิม ทุก financial/run/session state อยู่ PostgreSQL
  seed/drive endpoints ไม่อยู่ production; NoopStrategy ใช้เฉพาะ fixtures ไม่ใช่ F-21
- Browser ตรวจ pending/starting/running/paused/stopped/exposure/protection, stop/resume
  และ lost-ack journal เดิม รวม owner/mode/reload, keyboard, Thai/English light/dark
  ที่ 375/768/1280/1440px ใช้ screenshot/ผลจริงให้เจ้าของตรวจรับเป็นขั้นสุดท้าย
- อัปเดต evidence/validation ตามผลจริง ไม่ลดเกณฑ์ ไม่ย้าย Feature safety ไป Batch
  คง owner UI acceptance และ required CI บน final SHA เป็นด่านก่อน merge

Targeted backend/browser validation ประมาณ 45–90 นาที ไม่ใช่ full regression หรือ
workload/endurance และไม่มี Live order; หากพบกฎเงิน/ธุรกิจใหม่ที่ต้องตัดสินยังหยุดตาม
AGENTS.md ส่วนบั๊ก/harness fixes ภายใน scope ทำต่อพร้อมเก็บ Failed history ตามเดิม

Migration harness: เมื่อเพิ่ม 0073 พบ Alembic ใช้ transaction ต่อ revision จึง downgrade
index-only 0073 ได้ก่อนที่ 0072 จะปฏิเสธเพราะมี history แยกตรวจ reversible index step
กับ populated-refusal ที่ boundary 0072 โดยคง snapshot/RLS/facts assertions แล้ว upgrade
กลับ candidate head ไม่ใช้ assertion ว่าทั้ง multi-revision command เป็น transaction เดียว

Browser visual QA: holdings เป็น query snapshot คนละรอบกับ available balance จึงต้อง
แสดง `snapshot_at` จาก read transaction และเวลาที่ UI อ่านจริง ใช้ `MarketTime` เดิม
ตาม frontend standard §4 ไม่เพิ่ม stale-age threshold หรือเปลี่ยน admission policy
สรุปหยุดที่ F-20 reuse จะแสดง reconciled_at ด้วย formatter เดียวกัน (แสดงผลเท่านั้น)
E2E ต้องรอ holdings/protection บน UI ก่อนจับภาพ ไม่ใช้เพียง API-ready เป็นภาพหลักฐาน

Feature closure follow-up (before tests): extend the API restart case with loss of
the explicitly configured disposable test Redis database, using the existing
`TIEWTRADE_TEST_REDIS_URL`/flushdb test pattern. PostgreSQL sessions, accepted and
rejected receipts and financial assertions must survive; no production Redis URL
is selected. Add explicit distinct-pair metadata to the concurrent slot seam and
replay the old catalog withdrawal against the replacement run. These complete
existing V-05/07/12 scenarios without changing runtime rules.

Reviewed the suspected add-back/shared-checkpoint race before changing code:
`paper_orders/worker.py::_cancel_removed_openings` already checks every accepted
BUY's persisted catalog revision before advancing shared matching state, including
orders of another anchor command. The hypothetical bypass is therefore blocked;
no duplicate catalog authority check or production change is warranted.

Close the remaining explicit V-11/13 assertions using existing real-Paper tests:
after the full protected fill, invoke the real missing-version path plus F-19 and
compare the protection document, position and wallet; inspect the actual canceled
event by its immutable identity in the existing failure-recovery case; add linked
command unknown→real filter rejection→single feedback consumption. Keep all
financial assertions and use existing workers/fixtures (no mock executor).

The first V-11 protection-extension run stayed RUNNING because the preexisting
financial-writer fixture seeds no START_REQUEST_APPLIED fact, so the lifecycle
reader correctly returned no run. Supply the pinned entry metadata before invoking
that reader; do not change production behavior or weaken STOPPED/protection checks.
The rejected/unknown and both canceled-feedback cases already passed.

Screenshot QA found mobile locator captures scrolling the panel under the existing
sticky market toolbar. Capture the complete actual page from scroll origin instead
for the responsive matrix; keep overflow/focus assertions and all business checks.
This fixes evidence framing, not application layout or toolbar behavior.

Wire the new isolated F-20 browser config into the existing Chromium CI job before
the existing clean F-18/F-19 boundary, using the existing npm script/step pattern.
No new infrastructure/job or production configuration is introduced. Before UI
captures, also wait for the existing five-second trade snapshot to show 9,900 USDT
after the real 100 USDT fill (cash 10,000→9,900); retain independent status polling.
This distinguishes normal query refresh timing from authoritative financial state.

### Required CI secret triage - 2026-11-20

First publication candidate 8ad901f has one new generic-api-key finding: the fixed
synthetic F-37 idempotency marker at test_bot_catalog.py:130, occurrence identity
38f59f54c402881bfb2d0d027dd95c57ac30530308ecbc92bc42237c01262836.
It is only a request deduplication string in the isolated fixture, never a venue
credential, authentication token or exported secret. The scanner's historical
scan will retain it even if the current fixture changes. No force/rewrite is
authorized or necessary.

Prepared evidence/proposed-secret-exception.json for owner review, without changing
the active security registry or scanner. Recommended change after approval: append
this exact occurrence to the existing exceptions.json registry, retain all rules
and gates, and rerun required CI on the resulting candidate. Alternative is to
leave the PR blocked. Security plan section 5 requires owner approval/review tied
to the exact occurrence; UI acceptance does not supply that exception approval.

Owner approved the exact proposed occurrence on 2026-11-20. Apply only that
registry row and retain the original failure; no scanner/gate/config change or
broader exception. Run existing security policy/model tests before publishing
the resulting candidate and require all remote checks again on its SHA.

### CI-only F-19 test composition flag - 2026-11-20

First remote F-20 browser suite returned 503 at the expected committed stop.
Evidence: isolated config omitted TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED, while
the local launcher supplied it; kill_switch_routes rejects stop/resume unless
it is explicitly 1. Reuse the exact declaration in playwright.risk-limits.config.ts
in the F-20 guarded test environment. Preserve 202/lost-ack/idempotency/financial
assertions and production default closed. This is a harness correction within
the approved engineering authority, not production activation or a relaxed gate.
Check frontend lint/types and require the browser suite on corrected remote SHA.

### Bounded CI stall diagnosis - 2026-11-20

The first candidate is already nonmergeable (one approved false-positive and the
test-only F-19 flag omission). Its backend pytest remained active beyond 30 minutes
with logs unavailable until job completion; the same base's previous pytest took
14m42s. New bot tests use finite barriers/claims, but an exact stalled test cannot
be identified from the jobs API. Browser host is unavailable too.

Under the delegated diagnostic authority, cancel the superseded first run and
publish the prepared corrections with verbose pytest names/durations and a
25-minute interrupt boundary (30-second kill grace) for the main pytest step, plus
a 40-minute backend job budget. This is a failure/diagnostic boundary, not a
passing correctness/SLA threshold, and does not skip a test, change assertion or
turn an incomplete run into success. Existing base pytest fits within the budget
with substantial margin. Preserve cancellation/failed history and require all
checks on the new SHA. Stop and diagnose from the emitted last test/stack if
this boundary is reached; do not blindly repeat or expand the campaign.

### Canceled-run regression diagnosis - 2026-11-20

Canceling released the first backend log: 2,232 completed tests, failures at
collection positions 57/342/1630, then no progress after 38%. Matched the same
5,768-test collection locally (collection only, no campaign):
- secret canary lacks the new bot receipt routes' documented 404 expectation;
- exact renewing-route oracle lacks the two new explicit user-action POST routes;
- the fixed schema0066 checkpoint experiment's preflight test clones latest head
  but its unchanged profile intentionally requires 0066; supply an empty 0066
  clone in that test rather than retargeting the approved experiment;
- within the next page, the parent-poll projection test passes a minimal intent
  without origin into the changed submit_new helper. The child raises before its
  submitted Event, and the parent waits forever. Add the explicit MANUAL origin,
  bound only this in-memory handshake/task wait and preserve all gate/latency
  assertions. No financial writer or production behavior changes.

Use existing route-error patterns and migration helper. Verify the affected
canary/route/preflight/parent-poll tests with disposable PostgreSQL/Redis and static
checks before publishing. No experiment duration/workload/safety threshold change;
no rerun of the original indicator campaign.

Before publication, cancellation logs identified the stalled in-memory handshake.
Remove the prepared broad 25m/40m CI timeout edits: the now-bounded unit-test wait
is sufficient and does not impose a new budget on unrelated tests. Retain verbose
test names/durations for useful CI diagnostics. The canceled run plus targeted
reproduction replaces the speculative whole-suite timeout approach. No broad
timeout modification was published.
