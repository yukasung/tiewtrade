# F-21 — RSI Step Grid + EMA filter / Single Basket TP — Plan

สถานะ: **Approved — เจ้าของตอบ “approve” ฉบับแก้ F21-R01/R02 วันที่ 2026-11-20**
วันที่: 2026-11-20 (Asia/Bangkok)
Branch: `feature/f-21-first-strategy`
ฐานข้อกำหนด: [requirements.md](requirements.md) Approved 2026-11-20

## 1. แนวทาง

เพิ่มกลยุทธ์ pure ภายใต้ F-20 และต่อ input/config/feedback/protection เท่าที่จำเป็น
ไม่คัดลอก runtime Desktop, indicator calculator, Paper matcher หรือ PnL มาอีกชุด
ใช้ identity `rsi-step-grid-ema-single-tp` version1/configuration1/state1 แยกจาก
Desktop `rsi-step-grid-v1` เพราะ entry filter, single-group และ cooldown ต่างกัน
รายการใน registry เป็น code/schema ที่ immutable เท่านั้น Config ของผู้ใช้อยู่ PostgreSQL

คง approved BUY predicate, max_entries1–10/default10, เงินต่อไม้, timeframe default5m,
กลุ่มเดียว, ATR multiplier3 และไม่มี cooldown/strategy SL ตาม requirements
รายละเอียดที่เป็นกฎธุรกิจไม่ตัดสินใหม่ใน implementation

## 2. ผลตรวจของเดิมและสิ่งที่ต้องเติม

- `core/strategies.py::StrategyInput` มี quote/indicator/feedback แต่ไม่มี candle OHLC,
  closure identity และหลักฐาน250แท่ง; `infra/bots/inputs.py::read_bot_indicators`
  อ่าน indicator แท่งปิดหนึ่งจุดโดยตั้งใจ ไม่ใช่ candle-trigger/catch-up scheduler
  ต้องเพิ่ม typed input และ source proof แบบ additive ไม่ใช้ quote เป็น candle signal
- `PublishedConfiguration`/`StrategyRegistry` ปัจจุบันรับ deployment-owned config
  และ `BotStartInput` มีเพียง reference; จำนวนเงินจากผู้ใช้จึงต้องมี owner-scoped
  persisted config และ engine-side validation/resolution ไม่สร้างรายการเงินทุกค่าใน memory
- `StrategyDecision.brackets` อ้าง entry intent และ F-17 มี bot bracket/fill hooks
  แต่ยังไม่มี F-21 basket/entry membership และ target revision ร่วมทุก entry
  ต้องเพิ่ม durable projection/linkage และผล retarget โดยรักษา F-17 financial protocol
- `PaperBotPanel.tsx` เป็น draft ที่ใช้ชื่อ Grid Close System/start disabled
  จะเปลี่ยนให้เลือกค่ากลยุทธ์จริงและแสดง readiness แต่ไม่ยกเลิก production activation gates

## 3. ของเดิมที่จะใช้ซ้ำ

| Path / API | ใช้ทำอะไร |
|---|---|
| `core/strategies.py`, `core/bots.py` | immutable input/config/state/decision, scope/version checking และ lifecycle |
| `core/money/` | Money/Quantity/Scalar, quantity_for_budget, money_for_quantity, price_for_notional, times และ rounding เดิม |
| `core/positions.py::apply_execution`, `infra/positions/` | net acquired quantity, fee treatment, execution facts/rebuild; ไม่ทำบัญชีหรือ PnL ซ้ำใน basket |
| `core/protections.py`, `infra/protections/storage.py`, `worker.py` | TP-only prices, allocation, bot bracket, fill accounting, trigger→MARKET, failure policy |
| `infra/bots/start.py`, `claims.py`, `requests.py`, `decisions.py`, `feedback.py`, `evaluation.py` | start/replace, claims/fences, command receipts, decision journal, actual feedback และ two-phase evaluation |
| `services/engine/bot.py` | registry/composition, bounded worker rounds, pause/recovery/system-stop proofs |
| `infra/bots/paper_admission.py`, `infra/paper_orders/` | common admission/dispatch, reservations, matching/fees และ linked order IDs |
| `infra/bots/inputs.py`, `infra/indicators/prepared.py`, `read_contract.py` | central indicator generation/proof/rollout fencing และ bounded prepared reads |
| `core/timeframes.py`, `infra/market_data/` | shared timeframe enum, candle closure/gap/catalog provenance |
| `infra/db/session.py`, `infra/risk_limits/`, `infra/trading_stops/` | PostgreSQL RLS, owner transaction, financial lock order, stop cutoff และ risk proof |
| `services/api/bot_models.py`, `bot_routes.py` | authenticated owner endpoints, strict input, receipts/by-key and mode scope |
| `frontend/src/PaperBotPanel.tsx`, `BotRunStatus.tsx`, `paperBotMessages.ts` | settings/status/control panel, locale และเหตุไม่พร้อม |
| `frontend/src/components/ui/{Input,Select,Label,Button,Alert,Table}.tsx` | controls กลาง ไม่คัดลอก styling ต่อหน้า |
| `backend/tests/core/test_bot_contract.py`, `tests/infra/execution_market/test_bot_*.py`, `tests/infra/protections/` | fixtures, real-PG lifecycle/feedback/concurrency/protection regression |
| `frontend/tests/PaperBotPanel.test.tsx`, `frontend/e2e/bots.spec.ts`, `paper-bot-panel.spec.ts` | component และ actual-API isolated browser flows |

UI source: `references/admin-template/src/pages/Forms/FormElements.tsx`,
`components/form/form-elements/{DefaultInputs,SelectInputs,InputStates}.tsx`,
`components/form/input/InputField.tsx`, `pages/UiElements/{Buttons,Alerts}.tsx`
และ `pages/Tables/BasicTables.tsx`; ใช้ component กลางที่ปรับแล้วก่อน
ต้องเทียบ label/spacing/focus/disabled/error/light-dark/responsive กับต้นทาง

## 4. Pure strategy และ state

เพิ่ม `strategies/rsi_step_grid/` สำหรับ implementation และ `core` contracts/state
ที่ต้องแชร์ ชุด indicator เป็น EMA20, EMA50, RSI14, ATR14 จาก F-11 เท่านั้น
Config validate เงินผ่าน Money, max_entries เป็น strict integer1–10 (ปฏิเสธ bool),
คู่ผ่าน catalog BTC/ETH และ timeframe ผ่าน shared enum; unknown keys/version ไม่ fallback

State ระบุ reset_close, last processed closed-candle/source identity, pending entry identity,
entry sequence, current basket identity, exit-candle guard revision และ held TP/reference ที่จำเป็น ใช้ state version
และ exact codec เดิม ไม่เก็บ business state ใน strategy instance

บน closed candle ที่250ขึ้นไปและ indicators พร้อม ให้ใช้ลำดับ pending→ARM→FIRE
ตาม predicate ใน requirements เมื่อ FIRE สร้าง BUY MARKET intent ผ่าน F-20
FIRE ต้องผ่าน exit-candle guard ในหัวข้อ5ด้วย แม้ช่องจำนวนไม้เพิ่งว่างหรือ Basket เพิ่งปิด
ใช้ quantity_for_budget/lot/fee admission เดิม ไม่คำนวณจากราคา open ในอนาคต
คำขอไม่ผ่าน admission ไม่ถือว่าได้ซื้อ; identity แยก run/basket/candle/entry ordinal
คง identity เมื่อ retry และใช้ input revision ตรวจ payload conflict

หนึ่ง logical entry ต่อ accepted BUY intent; partial fills เพิ่มปริมาณให้ entry เดิม
ไม่กิน max_entries เพิ่มและไม่เพิ่มเลขไม้ตามจำนวน fills Pending คงอยู่จนได้ terminal
outcome ที่ authoritative; เมื่อเกิด fill จริงให้จดว่า ARM ถูกใช้และต้อง ARM ใหม่
ก่อน entry ถัดไป ไม่ล้าง reset เพราะ status accepted อย่างเดียว
Rejected/canceled ที่ไม่มี fill คง reset ตามต้นฉบับ; canceled หลัง fill คง inventory จริง
Unknown รอ reconciliation ไม่สร้าง replacement intent หรือเดาผลเอง
Feedback ซ้ำไม่เปลี่ยน state/เงิน; ตรวจ entry identity + revision + fill fact identity

## 5. Candle inputs, warm-up และ fencing

เพิ่ม closed-candle input path ใน F-20 แบบ additive และ default ที่ไม่เปลี่ยน fixtures
เดิม Quote ยังใช้ readiness และ F-17 trigger; quote ใหม่ของ candle เดิมไม่ทำให้ BUY ซ้ำ
Feedback มี durable cursor ของตนเองเพื่อให้ partial fill/protection ทำงานแม้ไม่มีแท่งปิดใหม่

อ่าน CLOSED OHLC กับ EMA20/50/RSI14/ATR14 ของแท่งเดียว คู่/timeframe/central generation
เดียวกัน พร้อม proof ว่ามี250 completed candles ต่อเนื่อง ไม่เริ่ม seed ใหม่ที่250
ใช้ prepared generation/checkpoints/metadata ให้ bounded; หาก metadata ยังพิสูจน์
จำนวนต่อเนื่องไม่ได้ ให้เพิ่ม count/proof ใน existing prepared pipeline ไม่ scan retention
ทั้งหมดทุก poll ไม่เพิ่ม network/indicator service ใหม่และไม่เปลี่ยนสูตร F-11

หลัง disconnect/start/recovery ใช้ backfill เฉพาะสร้าง readiness/indicator state
ไม่ออก BUY จาก historical candles; durable progress ป้องกัน delayed/reordered input
เป็นสัญญาณสด ไม่ replay ARM/FIRE เพื่อซื้อย้อนหลัง และไม่ใช้ forming candle
ที่ไม่ได้ CLOSED; after reconnect ต้องผ่าน reconcile และ loss check ตาม F-20
หากแยก live/backfill provenance ไม่ได้ ให้พักไม่เดา

### Exit-candle guard — แก้ finding F21-R02 (Medium)

ข้อกำหนด SR-08 ห้ามสร้าง BUY signal จากแท่งที่เพิ่งมี exit ไม่ใช่ time cooldown
ผูก confirmed SELL execution ที่ลด inventory ของ run นี้กับ run/pair/timeframe และ
candle interval [open_at, close_at) โดยใช้ execution time ที่ authoritative กับ
`core/timeframes.py::align_floor/next_open` รวม calendar1M ไม่ใช่เวลาที่ worker อ่าน
ครอบคลุม TP exit, manual SELL และ partial exit ทุกครั้งที่มี confirmed quantity>0
การกดขาย/รับคำขอเฉย ๆ ยังไม่ใช่ exit fact

เขียน unique exit-fact linkage และ guard revision ใน transaction ที่รับ disposal fact
พร้อม basket/entry updates ไม่รอ strategy feedback poll หรือ Redis message
guard อยู่ระดับ run/pair/timeframe และไม่หายเมื่อ Basket ว่าง จึงกัน new Basket
เข้าซ้ำบนแท่งเดิมหลังขายไม้สุดท้ายได้; เก็บ source identity เพื่อ rebuild/dedup ได้
API/engine restart, feedbackซ้ำ/มาช้า และข้อมูลแก้ไขต้องใช้ authoritative facts/proof
หากยังพิสูจน์ progress ของ disposal ไม่ครบให้ยังไม่มีสิทธิ์ BUY ไม่เดาว่าแท่งปลอด exit

Pure input บอกว่าแท่งนี้มี confirmed exit หรือไม่และ guard revision ที่อ่านมา
ยังอัปเดต indicator/ARM ตามกฎเดิมได้ แต่ห้ามคืน BUY intent เมื่อ guard ของแท่งนั้นปิด
ก่อน persist decision ตรวจ guard revision อีกครั้งใต้ financial owner locks เดิม:
ถ้า exit commit ก่อน BUY decision ให้ทิ้ง intent เก่า; ถ้า BUY commit ก่อน exit
ให้ยึด authoritative transaction order ไม่แก้ประวัติย้อนหลังหรือสร้างคำสั่งชดเชยเอง
ตรวจ guard อีกครั้งก่อน queued BUY เข้าสู่ execution ตาม F-20 fence เพื่อไม่ให้
decision ที่ค้างจากแท่งที่มี exit เพิ่มความเสี่ยงโดยหลุดผ่านช่วง prepare/execute
เมื่อแท่งถัดไปไม่มี exit เปิดโอกาสให้ FIRE ได้ตาม state/ARM และ gates อื่นตามเดิม

ก่อน commit ตรวจ run/lease/stop/risk/catalog/config/candle/generation/rollout revisions
อีกครั้งตาม two-phase pattern ของ F-20 Inputs เปลี่ยนให้ทิ้งผลเก่า ไม่ advance cursor
ข้ามข้อมูลที่ยังไม่พร้อม หลักฐาน250แท่งไม่พร้อมให้แสดง reason และไม่มี intent
รวมกรณี 1w/1M ที่ retention/history ไม่พอ ไม่เพิ่ม retention หรือผ่อน250เอง

## 6. Basket เดียวและ TP ร่วม

หนึ่ง open basket ต่อ run/pair/episode; ทุก entry อยู่กลุ่มเดียว ราคาสูงขึ้นไม่แยกกลุ่ม
คำนวณ weighted average จาก confirmed open entry quantities/prices ตาม requirements
ใช้ net available quantity และ fee treatment จาก position/execution contracts เดิม
ไม่ใช้ fee-free Desktop quantity หรือเขียน realized PnL ledger ใน basket

หลัง entry fill/partial fill หรือ disposal ที่ยืนยันแล้ว สร้าง target revision ใหม่จาก
รายการที่ยังเปิดและ ATR signal ของ entry ที่ล่าสุดตาม filled_at/entry_number
ใช้ numeric/rounding primitives เดิม คูณ ATR ด้วย3แล้ว floor-to-tick ตาม approved rules
หากต้องเพิ่ม arithmetic adapter ให้อยู่ `core.money` และประกอบกฎเดิมพร้อม oracle tests
ไม่เพิ่ม scale/range/rounding policy ใหม่

TP ของ basket เป็น min(candidate, held TP) จน basket ปิดจริง ไม่ reset เพราะ restart,
partial exit, manual reduction หรือเพิ่ม entry แพงขึ้น จบ basket เมื่อ quantity/allocations/
orders ที่เกี่ยวข้องกระทบยอดว่าปิดครบแล้ว New basket ใช้ target ใหม่และ identity ใหม่

### Basket trigger authority และ atomic retarget — แก้ finding F21-R01 (High)

ใช้ per-entry F-17 allocation เป็น execution units โดยมี basket target authority
เพียงหนึ่งเดียว ไม่สร้าง allocation อีกก้อนที่จอง quantity ซ้ำ เพิ่ม append-only
basket trigger fact ที่ผูก owner/mode/episode/run/basket, target revision/price,
TriggerEvidence source/generation/sequence/time และ membership revision
พร้อม unique constraint หนึ่ง winning TP trigger ต่อ basket

การรับ fill/disposal→entry/basket projection→target revision→ทุก allocation ที่ยัง
แก้ได้ ต้อง commit ใน owner/episode financial transaction เดียวกัน ไม่ใช้ async
retarget outbox ที่ปล่อย protection บางไม้ใช้เป้าเก่าขณะ basket ใช้เป้าใหม่
จำนวน logical entries ไม่เกิน10 จึง lock/update ทั้งชุดแบบ bounded ได้; ลำดับ locks
ต้องสอดคล้อง financial protocol เดิมและ sort allocation IDs เพื่อไม่สร้าง deadlock
F-21-linked protection workers ต้องตรวจ basket membership/target revision ใต้ locks
เดียวกันก่อน evaluate หรือ queue exit ไม่ทำ independent latest-price trigger ทีละไม้
การเปลี่ยน target ต้อง invalidates observed cursor ของ target เก่าหรือผูก observation
กับ target revision เพื่อประเมิน target ใหม่ได้แม้ market cursor ยังไม่เปลี่ยน

เมื่อ fresh authoritative last trade ถึง target และ F-17 readiness/quantity checks พร้อม
ให้ persist basket trigger fact, transition/exit work สำหรับ eligible confirmed remaining
allocations ทุกไม้ ด้วย TriggerEvidence เดียวกันใน transaction เดียว
ไม่ตัดสินซ้ำว่าไม้ B ถึงเป้าหรือไม่จากราคาที่อ่านภายหลังไม้ A; ราคากลับต่ำกว่า TP
ไม่ล้าง winning trigger และไม่ทำให้ไม้ที่เหลือกลับเป็น ARMED
ใช้ F-17 evaluate_trigger/queue_exit และ admission เดิมเป็นขอบเขต domain/execution
outbox/worker ทำได้เฉพาะ dispatch/recover งานที่ durable แล้ว ไม่ตัดสิน trigger ใหม่

แยกการยืนยันว่าเคยถึง TP ออกจาก execution readiness ปัจจุบัน: retry หลัง restart
ใช้ winning trigger ที่บันทึกไว้ตัดสินว่าต้องออก แต่การส่ง/จับคู่ MARKET ต้องมี current
authoritative readiness ตาม F-15/F-17 ไม่ปลอม historical evidence ให้เป็นราคาสด
หาก allocation บางไม้ส่งไม่ได้ ให้บันทึกผลและใช้ existing F-17 failure/residual policy
โดยรักษา winning trigger และงานของไม้ที่ยังค้าง ไม่ทิ้ง trigger เพราะ worker ถัดไปอ่าน
ราคาต่ำลง และไม่ถือว่าทั้ง Basket ปิดแล้วเพียงเพราะสร้าง exit work

Exit command linkage ใช้ unique basket trigger/allocation/work identity และ reuse
F-17 command/idempotency keys ไม่เปลี่ยน key ทุก retry; target revision ที่เปลี่ยน
หรือ worker ซ้ำต้องไม่สร้าง MARKET ใบที่สองสำหรับ quantity เดิมที่อยู่ระหว่าง exit
late entry fill หลัง basket trigger ต้องผูกกับ basket เดิมและ durable remaining-exit
work ภายใน fill transaction ตาม F-17 late-fill accounting ไม่เปิดกลับไป ARMED
และไม่สร้าง entry/Basket ใหม่เพื่อรับ late fill; กู้คืนได้จาก DB โดยไม่มี Redis hint
actual SELL fill อัปเดต exit-candle guard ในหัวข้อ5ด้วย

ใช้ bot fill hook และ existing worker composition ไม่ให้ infra import strategy/services
และไม่ให้ strategy เรียก protection worker การเปลี่ยน orchestration นี้ใช้เฉพาะ
F-21-linked allocations; F-17 ของ manual/strategy อื่นยังผ่าน path/contract เดิม

ก่อน retarget/exit ตรวจ F-17 state/revision/reservations; TRIGGERED/exit-in-flight
ไม่ถูกย้อนเป็น ACTIVE เมื่อ target เปลี่ยน ไม่ยกเลิกแล้วสร้าง MARKET ใหม่วนเอง
ถ้าราคาเคลื่อนข้าม target ใช้ accepted-bracket immediate-trigger semantics ที่ F-17
อนุญาต; การแก้ protection ที่ไม่ผ่าน creation/amendment constraints ต้องไม่แอบข้าม
ให้ใช้ rejection/failure/stop policy เดิมและแสดงเหตุผล หากจำเป็นต้องเปลี่ยน contract
ต้องหยุดบันทึก amendment ขอเจ้าของก่อน ไม่ให้ tests ผ่อนเกณฑ์เพื่อผ่าน

การขายมือ/TP ที่แข่งกับ fill ต้องหักได้เฉพาะ confirmed remaining quantities และไม่รวม
holdings นอก run นี้; atomic allocation/financial protocol เป็นหลักฐานจาก PostgreSQL จริง

## 7. Persistence, API และ UI

เพิ่ม migration จาก Alembic head ที่ตรวจจริงก่อน implementation (ไม่จองเลขล่วงหน้า):

| ข้อมูล | การเก็บและ constraints |
|---|---|
| Owner configurations | immutable normalized parameters + schema/strategy version, payload hash, owner/mode and opaque ref; strict range1–10/positive money ใช้ domains เดิม |
| Basket/entry projections | owner/mode/wallet/episode/run/pair keys, basket/entry sequence, confirmed fill linkage, open quantities, ATR provenance และ target revision |
| Source/feedback/retarget progress | unique run/input/fill or command keys, target revision and applied protection revisions; authoritative facts append-only, mutable projections rebuildable |
| Basket trigger/exit work | unique winning triggerต่อbasket, immutable target/source/membership evidence และ per-allocation work identity ที่ไม่ซ้ำ; trigger/exitงานทุกไม้ commit ด้วยกัน ไม่อาศัย price poll ถัดไป |
| Exit-candle guard | owner/run/pair/timeframe + execution/candle identity, unique exit fact linkage และ guard revision; เก็บต่อเมื่อ Basket ปิดเพื่อกันเข้าใหม่ในแท่งเดิม |

ทุกตาราง FORCE RLS และ composite FK ป้องกัน cross-owner/mode/episode, partial unique
open basket ต่อ run; API ไม่มีสิทธิ์เขียน fill/basket/TP และ scan role อ่านเฉพาะ due hints
Financial writer/owner lock order เดิม, no sticky sessions/process memory authority,
Redis เป็น wake-up hint เท่านั้น DB restore/restart ต้องอ่าน config/state ได้ครบ
Migration additive ไม่ rewrite ledger หรือข้อมูลเดิม; downgrade ปฏิเสธเมื่อยังมี live
references/active runs เพื่อไม่ทำลาย state ต้องหยุดและ retire ผ่าน flow เดิมก่อน rollback

เพิ่ม owner-scoped config create/read และ strategy catalog/schema routes ใน bot router
ใช้ authentication/CSRF/idempotency/throttle patterns เดิม Decimal amount เป็น string
ก่อน start อ้าง persisted config ref เดิม; engine โหลดและ validate independently
Registry resolve implementation กับ versioned config ที่อ่านจาก DB สร้าง stateless descriptor
ตาม pair/timeframe; ห้ามเก็บ config ref เฉพาะ API instance หรือสร้าง resolver ที่รับ
import path/executable code จาก browser คง API/engine tests ของ deployment configs เดิม
client timeout อ่าน config/start receipt เดิมได้ ไม่สร้าง run/config/order ซ้ำ

UI เปลี่ยน selector เป็นกลยุทธ์จริงและฟอร์มเงินต่อไม้/max_entries1–10/timeframe
แสดง pair/mode/pinned config, common basket TP และเหตุ readiness ไม่ผ่าน
ไม่มี cooldown/SL editor/การจูน RSI/EMA ในรุ่นนี้ การเปลี่ยน chart ไม่แก้ active run
Start ยัง disabled เมื่อ protocol/source/BOT/risk/production admission ไม่พร้อม
เปิดกดได้เฉพาะใน authorized isolated validation environment หรือเมื่อ activation gates
พร้อมตามสิทธิ์เดิม ไม่แก้ flags/deployment ในงานนี้ Stop/SELL/TP-SL เดิมยังเข้าถึงได้
ต้องแยก request pending/running/partially filled/exit remaining ชัดเจน
สร้าง OpenAPI และ TypeScript types ใหม่จาก backend ไม่เขียน contract ซ้ำด้วยมือ

## 8. Milestones และตรวจรับ

| ขั้น | ขอบเขต | หลักฐานใน validation |
|---|---|---|
| M1 | pure strategy/config/codec, single basket math และ boundary inputs | V01–04, V06 |
| M2 | migrations/config API, closed-candle proofs/worker resolution และ start pin | V04–05, V07–09 |
| M3 | real execution feedback, basket linkage/shared TP, races/fault recovery | V06, V09–13 |
| M4 | UI/templates, generated contracts, actual-API isolated browser and config recovery | V08, V14–16 |
| Candidate | Ready for Code Review→review/fix/refactor/affected checks, owner UI acceptance และ final-SHA required CI | V17–18 และ Feature ทั้งหมด |
| ท้ายชุดที่6 | full integrated bot/strategy regression รวม F-20 V19/20 และ affected protection/risk/STOP | V19 Pending Full Validation จนรันจริง |
| Release/ชุดที่9 | integrated workload/endurance/activation dependencies ตาม profile เดิมที่อนุมัติ | V20 Pending Full Validation |

ไม่รัน workload/timed smoke อัตโนมัติหลัง milestone; targeted checks เล็กที่สุดที่พิสูจน์
diff/callers/contracts/concurrency เพียงพอ แก้แล้วตรวจเฉพาะ failure/new diff/regression
ก่อน full regression/cross-feature E2E/ชุดจับเวลา แจ้งขอบเขต/หลักฐาน/ประมาณเวลา
กรอบวางแผน1–2ชม.ไม่ใช่เวลาที่ใช้ตัด correctness; คงเกณฑ์และจำนวนรอบเดิม
หยุดเมื่อแก้และตรวจเกณฑ์เดิมไม่ผ่าน3รอบ หรือเจ้าของระบุใช้เวลามากเกินไป

ก่อน merge ต้องผ่าน Feature, owner UI acceptance, review และ required CI ตาม testing §7
ใช้ CI configuration ปัจจุบัน ไม่ข้าม fresh-global-state/Security/contract jobs ที่บังคับ
การอนุมัติ plan ไม่ใช่ owner UI acceptance/production opening และไม่รับรอง Completed
Git publication/merge ต่อเนื่องเมื่อครบเงื่อนไข AGENTS.md เท่านั้น

## 9. จุดหยุดและความเสี่ยง

ตอนนี้ requirements Approved; plan/validation Proposed ไม่เขียน runtime ก่อนอนุมัติ
แผนนี้ไม่เปิด production/Live ไม่รัน campaign ใหม่ และไม่แก้ F-20 gates ที่ยังค้างแทนงานนั้น
ก่อน implement ตรวจ branch/base และ dependency diff ล่าสุด อ่าน roadmap/gates ของ F-20
ตามจริง ไม่ถือว่าการเริ่ม F-21 ทำให้ F-20 ผ่าน CI/merge โดยอัตโนมัติ

ความเสี่ยงหลัก: shared TP แข่งกับ partial fills/exit และ source/stop changes;
single target ที่คง min อาจต่ำกว่าต้นทุนใหม่ได้ตามสูตรที่อนุมัติ ห้ามยก target เพื่อรับรองกำไร
target/position qty ต้องยึด authoritative facts ไม่อ้างค่า summary หรือ browser
ถ้าพบช่องว่างธุรกิจ/เปลี่ยน risk/security/architecture เกินมาตรฐานให้หยุดขอคำตัดสิน
การแก้รายละเอียดวิศวกรรมตามอำนาจ 2026-11-14 ต้องบันทึกหลักฐานก่อนแก้และรักษาประวัติแผน

### ตรวจเอกสารก่อนส่งอนุมัติ — 2026-11-20

ตรวจเทียบ approved requirements/paths/callers แล้ว: single basket, no cooldown,
count1–10/default10, shared Web execution,250 readiness และ version pin ครบในแผน
validation V01–V20 แยก Feature/Batch/Release และคง Not Run ทุกข้อ
relative links/source paths/whitespace ผ่าน; ยังไม่รัน runtime tests/build/CI
จุดที่ต้องพิสูจน์ใน implementation คือ source fencing กับ shared target transaction
ไม่มีการใช้ผลอ่าน source แทน correctness proof หรือการอนุมัติ plan/validation

### หลัง deep review — 2026-11-20

เจ้าของสั่ง “แก้ไข” หลัง review-only findings; แก้เฉพาะแผน/validation ภายใน
requirements ที่ Approved ตามอำนาจวิศวกรรมใน AGENTS.md วันที่2026-11-14

| Finding | หลักฐาน/ทางเลือก/การแก้ | สถานะเอกสาร / หลักฐาน runtime |
|---|---|---|
| F21-R01 High | F-17 process_group อ่านราคาทีละallocation จึงพลาดไม้ถัดไปเมื่อราคากลับตัว; การตั้งราคาให้เท่ากันหรือ async retarget อย่างเดียวไม่รับประกัน TP ร่วม เลือก basket trigger authority+atomic retarget/trigger work ตามหัวข้อ6 ใช้ DB/financial locks เดิม ไม่เพิ่ม infrastructure/สูตรหรือผ่อน F-17 readiness | Addressed in proposed plan; V11/V12/V13เพิ่มproof; implementation/real-PG tests Not Run |
| F21-R02 Medium | SR-08ห้ามBUYบนแท่งที่มีexit แต่แผนเดิมไม่เก็บguard; ใช้เฉพาะin-memory/lastpollจะหายหลังrestart จึงเลือก fact-backed run-level guard พร้อม prepare/commit/execution fences ในหัวข้อ5 ไม่เพิ่ม timed cooldown | Addressed in proposed plan; V01/V05/V10/V12/V15เพิ่มproof; implementation/tests Not Run |

ผลกระทบจำกัด F-21และshared hooks ที่จำเป็น ต้องคง regression ของ manual/F-20/F-17
หลังแก้ตรวจเฉพาะ findings/ข้อความใหม่/consistency และ links ไม่รันfullsuite/workload
plan/validation ยังคง Proposed; ขออนุมัติฉบับแก้แล้วก่อนเขียน runtime

## Implementation authorization — 2026-11-20

เจ้าของอนุมัติฉบับแก้deep-reviewแล้ว เริ่ม implementation/targeted tests/review ตามแผนได้
ข้อความ Proposed/รออนุมัติก่อนหน้านี้เป็นประวัติ; owner UI acceptance/required CI
และ Batch/Release/production gates ยังคงบังคับ ไม่เปิด Live หรือ production เอง

### Engineering detail before M1 — 2026-11-20

ตรวจ `OrderIntent` พบ MARKET BUY ใช้ QuoteBudget อยู่แล้ว จึงใช้เงินต่อไม้แบบ
QuoteBudget โดยตรง ให้ matcher เดิมทำ sizing/fees ไม่แปลงเป็น BaseSize ที่ contract
ไม่รองรับ; ไม่เปลี่ยนความหมายงบหรือเพิ่ม ceiling ใหม่
F-20 requires_protection ตรวจ bracket ก่อนส่ง แต่สูตร basket ใช้ actual fill:
declare TP-only bracket จาก current authoritative quote+signalATR×3 เป็นระดับตั้งต้น
ก่อนมีfill แล้ว hook รับfillปรับ targetจากactualentriesและheldTPใน transactionเดียวกัน
ก่อน protection trigger path ตามหัวข้อ6 ไม่ถือ quote เป็นราคาซื้อจริงหรือเก็บ provisional
targetเป็นheldTPของBasketที่ยังไม่มีfill หากตั้ง/แก้ไม่ผ่านคง F-17 failure policy
บันทึกก่อนเขียนimplementationตามอำนาจวิศวกรรม AGENTS.md 2026-11-14

### Needs Clarification NC-F21-08 — manual multi-entry partial disposal

ตรวจ `infra/protections/worker.py::prepare_admission/commit_admission/record_fill`
พบmanual SELLปลดselected protection allocationsตอนadmission และactualSELLfill
ไม่มีper-entry disposal attribution ส่วน position ledger ของ F-14 เป็นaggregate
จึงไม่พิสูจน์ว่าpartialSELLจากหลายallocationsขายไม้ใดแล้วด้วยผลเดิม
F-21 ต้องทราบremaining entriesเพื่อตัดสินweighted targetและlatest remaining ATR
FIFO/LIFO/proportionalให้ผลต่างกัน จึงเป็นกฎธุรกิจ ไม่ใช้ engineering authority เลือกเอง
เสนอคำถามเจ้าของแล้ว: เลือกตัดไม้เก่า/ไม้ใหม่/ตามสัดส่วนที่เลือก
หยุด implementation ของdisposal attribution/TPที่พึ่งคำตอบ ไม่สร้างกฎปัดใหม่หรือ
อ้างmanualreleaseล่วงหน้าเป็นconfirmedSELL; config/purecontractตรวจต่อได้อิสระ
requirementsฉบับApprovedเดิมยังเป็นฐาน ไม่เปลี่ยนกฎย้อนหลัง; ก่อนเริ่มส่วนนี้
ต้องบันทึกคำตัดสินใน amendment และเพิ่มoracle/race/partial regressionให้ครบ

NC-F21-08 Closed: เจ้าของยืนยัน “ใช้ FIFO ตามที่แนะนำ” 2026-11-20
บันทึกrequirements amendmentแล้ว ใช้selectedallocation budgetsตามคำขอเดิม
ตัดactualfillสะสมตามentry_numberเก่าก่อน พร้อมuniqueexecutionreceipt ไม่ถือ
F-17 manualreleaseตอนadmissionเป็นdisposal และไม่restoreprotectionเองเมื่อcancel

### Engineering findings during M3 — 2026-11-20

ตรวจ callers ก่อนเพิ่ม integration proof พบ F-21 basket delegation อยู่ก่อน F-17
WAITING_ENTRY/ARMING setup path ทำให้ rejected-entry cleanup และ bounded setup failure
ไม่ถูกเรียก เลือกย้าย delegation ไปหลัง setup เดิมและก่อน independent trigger evaluation
เพื่อคง F-17 safety/failure policy; ไม่เพิ่มกฎธุรกิจหรือ retry policy ใหม่
พบ recovery whitelist รองรับเฉพาะ quote/feedback identity แต่ F-21 ใช้ candle identity:
เพิ่มเฉพาะ candle proof ของ F-21 ที่มี authoritative candle input พร้อมเดิม
พร้อม regression และ tighten source_revision ให้เป็น string จริง
ใช้ engineering authority AGENTS.md 2026-11-14; ขอบเขตเฉพาะ shared hooks ที่ F-21 กระทบ
FIFO ต้องพิสูจน์ selected caps/หลาย fills/duplicate receipt และ guard จากฐานข้อมูลจริง
ไม่ถือ pure FIFO tests เป็นหลักฐาน ledger หรือ real indicator pipeline

M3 integration รอบแรกหยุดที่ fixture พยายาม UPDATE config ที่ pin immutable (42501):
แก้ harness ให้ INSERT run พร้อม config ตั้งแต่ต้น ไม่เพิ่มสิทธิ์ DB
รอบถัดไปพบ audit contract ปฏิเสธ kind ใหม่ของ retarget; เลือกใช้ kind เดิม
REPLACE/TRIGGER ร่วมกับ durable basket trigger/target revision แทนขยาย audit allowlist
คง financial transaction rollback และตรวจ real writer ต่อ; ไม่ผ่อน assertion/constraint

M3 readiness review: การบันทึก eligible_after เฉพาะตอนเริ่ม pause ไม่พอเมื่อ worker เดิม
กลับมาหลังขาดการเชื่อมต่อและแท่งปิดระหว่าง gap เลือกเลื่อน boundary ก่อนเตรียม input
ของ F-21 ทุกครั้งที่ยังไม่ RUNNING ให้แท่งที่ปิดก่อน readiness กลับมาเป็น backfill
ใช้ progress row/owner lock เดิม ไม่เพิ่ม cooldown และไม่เปลี่ยน central indicators

Source correction review: F-17 reconcile_allocations fold effective facts แต่ F-21
entry projection ยังมาจาก original fills; การปล่อย BUY/retarget ต่อจะใช้ต้นทุนเก่า
เพิ่ม fail-closed reconciliation marker ของ basket ที่เกี่ยวข้องเมื่อ effective source
ของ allocation เปลี่ยน ภายใน transaction เดิม พร้อม regression ของ correction path
ไม่เลือกลดไม้/ล้าง conflict/restore protection เอง; การกู้ projection จาก corrected
manual FIFO facts และการยืนยัน owner repair ยังเป็นงาน M3 ที่ต้องพิสูจน์ก่อนผ่าน V12

Correction hook refinement: quantity-only detection misses price-only corrections and
corrections to a CLOSED basket. Use original execution receipts to invalidate the
run-level progress authority in correct_fill (APPLIED/CONFLICTED, never replay),
including price-only changes. A persistent run marker fences prepare/queued BUY
and basket trigger paths; no guessed costs or automatic conflict clearing.

### NC-F21-09 Closed — owner decision before implementation

เจ้าของยืนยันห้ามแก้ TP/SL รายไม้ของ F-21 ใช้สูตรร่วมเท่านั้น
เพิ่ม strategy_managed owner-scoped field ใน protection read model และ generated types;
ใช้ shared protection admission/worker ตรวจ F-21 membership (ไม่เชื่อ browser flag)
ปฏิเสธ REPLACE แต่คง CANCEL/SELL เดิม UI ซ่อน edit พร้อมอธิบายสูตรร่วม
เพิ่ม direct-admission/queued-engine/UI regression และคง manual/F-20 regressions

### M3 review — selected inventory boundaries

manual SELL ที่เลือก F-21 ผสม allocation อื่นไม่มี entry_number ร่วมที่อนุมัติไว้
ห้ามนำ fill ทั้งหมดไปลง F-21 ก่อนโดยเดา; ใช้ reconciliation-required เมื่อ attribution
ไม่พิสูจน์ได้ตามแผนเดิม ถ้าไม่เลือก F-21 และปริมาณ F-21 ทั้งหมดยังถูกจองไว้ใน
active linked protections การขาย free inventory ไม่ลดไม้ของ run และไม่สร้าง exit guard
ของ run นี้ ตรวจ caps ด้วย Money/Quantity เดิมภายใต้ financial owner lock

Basket close review: quantity เป็นศูนย์อย่างเดียวยังไม่พิสูจน์ว่า exit work settled
เพิ่มตรวจ unsettled per-allocation exits และ reconciliation marker ก่อน CLOSED
เรียกปิด basket หลัง F-17 settle exit ใน transaction เดิม ใช้สถานะ/quantity เดิม
ไม่ปล่อย new basket ระหว่างคำสั่งปิดยังไม่กระทบยอด

### M4 replacement wiring — engineering detail before code

พบ UI เดิมไม่มีช่องส่ง F-20 BotReplacementInput แม้ engine รองรับอยู่แล้ว
ทำให้หลัง STOPPED เปลี่ยน config เริ่ม run ใหม่ผ่าน UI ไม่ได้ เลือกคืน replacement
acknowledgement ใน owner status เฉพาะ PAPER/explicit activation/STOPPED/flat readiness
และไม่มี pending request ใช้ get_wallet/read_status/position revision เดิมใน snapshot เดียว
UI แสดงสถานะ/holdings เดิมและฟอร์มค่าตั้งใหม่ ปุ่มชัดเจนว่าเริ่ม run ใหม่
จด proof กับ request journal ก่อน POST และ retry key/payload เดิม; engine ตรวจ flat,
run/stop/summary/reconciliation revisions และ atomic retire/start ผ่าน F-20/F-19 เดิม
ไม่ปลด STOP ด้วย endpoint ใหม่ ไม่อนุญาต replace ขณะยังมี position/order และไม่ใช้
ค่าจาก UI เป็น authority ไม่เปิด production/Live

Checkpoint codec review: reset_close ติดลบและ pending/date string ที่ไม่ canonical
ผ่าน type-only validation ได้ จึงเพิ่ม semantic checkpoint validation ตาม exact codec
ที่อนุมัติไว้ (positive Money, UUID, aligned UTC candle identity, pending invariants)
ไม่เปลี่ยน valid signal state; corrupted state ต้องเข้าสู่ F-20 evaluation failure แทน BUY
Checkbox replacement ใช้ template form/input/Checkbox.tsx เป็น component กลางใหม่
เพิ่มเฉพาะ keyboard focus และ glyph ตาม checked จริงเพื่อ accessibility เมื่อ disabled

### M3 durable late-fill work review

พบ late fill ของ allocation ที่ยังไม่มี trigger ตอน basket ชนะจะกลับ ARMING จน poll
ถัดไป ขัด R01 เลือกใช้ F-17 extra_exit เป็น durable pending close allocation เดิม:
ใน fill transaction หลัง retarget ให้อ่าน winning trigger และ adopt EXITING+extra_exit
สำหรับ confirmed quantity โดยไม่อ้าง historical price เป็น current readiness
process_group EXITING เดิมตรวจ current source/filters ก่อน queue และคง residual policy
initial fanout ก็ adopt งานทุก eligible allocation ก่อน dispatch; หาก source ส่งไม่ได้
งานยัง durable ไม่กลับ ARMED ไม่สร้าง queue identity ใหม่เมื่อ retry

Bounded basket review: trigger query ดึง allocation ของไม้ที่ปิดแล้วทั้งหมดด้วย
ปรับใช้ shared open-entry predicate/lookup (confirmed quantity หรือ pending order)
ร่วมกับ admission cap/empty check และ sort protection IDs ก่อน fanout ตามแผน
ใช้ max(entry_sequence)+1 จาก index เดิมแทน count ประวัติทั้ง Basket เพื่อเลขไม้ถัดไป
ไม่เปลี่ยน FIFO/จำนวนไม้ที่ยังเปิดหรือสูตร TP

### F-21 entry pin review

register_entry เดิมเชื่อ pure decision จึงไม่ตรวจ pair/side/kind/QuoteBudget กับ run pin
เพิ่ม validation ซ้ำที่ financial registration boundary เพื่อปฏิเสธผิดคู่/ผิดเงิน/ผิดชนิด
ก่อน commit แม้ caller มี bug; ไม่เปลี่ยน approved sizing/admission
พบ integration fixture ใช้งบ85/90ทั้งที่ run pin100 เพื่อทำ equal-quantity oracle:
แก้ harness ให้ใช้100ต่อไม้ทุกครั้งและใช้ราคา86.37เพื่อ retarget106→101ตาม lot rounding
คง independent expected target101และเพิ่ม expected actual cash299.93009 ตาม F15
กรณีสองไม้100/90ใช้target100.73ตามactualunequalquantity ไม่อ้างequalquantityแทนfixedbudget

### Exit-guard pending-order finding — engineering fix before code

real writer test พบ guarded MARKET คง ACCEPTED เพราะ risk_allows=False ไม่ expire
จึงกัน fill แต่ค้าง reservation/pending ถาวรสำหรับ signal candle ที่ invalidated แล้ว
เพิ่ม admission authority check ของ F-21 และ queue cancel ของ accepted invalidated
entries ผ่าน submit_cancel เดิม ใช้ uuid5(protection_id,'cancel-entry') ร่วมกับ F-17
ไม่ทำ cancellation/ledger arithmetic อีกชุด; ระหว่างรอ cancel matcher ยัง fence BUY
ทดสอบก่อน/หลัง admission, ยกเลิก/retry, released reservation และไม่มี extra fill
คงการ pause/recover ของ F-20 ที่ไม่ใช่ F-21 ไม่ยกเลิก orders เหล่านั้นเอง

### Source readiness / prepared-tail findings — engineering amendment before code

หลักฐาน: F-11 scheduler รักษา READY head จนช่วง refresh470/600วินาที;
read_prepared(explicit_range=True) ปฏิเสธแท่งใหม่ที่อยู่นอก head จึงไม่รองรับ
F-21 M1 ทุกแท่งด้วยการรอ head ใหม่อย่างเดียว และ PUBLIC candle demand ไม่ขยาย
ตาม bot timeframe ถ้าผู้ใช้ไม่ได้เปิดกราฟนั้น
เลือก reuse coalesce_demand/enqueue กับ last-closed window ขนาด1แท่งใน phase prepare
(ให้สิทธิ์ ENGINE เฉพาะ demand columns เดียวกับAPI ไม่แตะcandles/claims/attempts)
พร้อม bounded tail adapter: ตรวจ READY head/codec/source proof เดิม, restore checkpoint
ท้าย generation ผ่าน F-11 codec, ย้าย exact state เข้า IndicatorStream(as_ofปัจจุบัน)
แล้วใช้ read_indicators เดิมคำนวณเฉพาะ suffixน้อยกว่า1000slotsตามขอบเขตF11เดิม
ไม่มีseed250ใหม่/สูตรใหม่/เพิ่มความถี่globalbuilder; เก็บ SourceFence ครอบ full calculation
และตรวจ PROOF_SQL เดิมอีกครั้งภายใต้ hold_bot_indicator_source ก่อน commit
hash typed point values ให้ input identity คงเดิมเมื่อ sourceอื่นเปลี่ยน แต่ proofแยกตามจริง

พบ cutoff ที่เลื่อนทุก PAUSED ข้ามสัญญาณสดเมื่อรอ prepared generationตามปกติ
แยก normal INDICATOR_NOT_READY/WARM_UP ออกจาก real recovery โดย progress.recovery_required
และ durable market_candle_demand.bot_recovery_at (DB trigger บันทึกfailure/repair,
recovery และ expired-lease takeover ไม่อาศัยmemoryหรือpollเห็นทัน)
true recovery/เริ่ม/takeover ยังคง backfill-only จน reconcile/ready และตั้ง cutoffที่ready
normal indicator wait ที่ sourceยังต่อเนื่องคงcutoffเดิม; ไม่มี replayแท่งเก่าหลายแท่ง
final fence ถือ source guard ก่อน demand FOR SHARE ตาม producer lock order guard→demand
เพิ่ม migration/source-fault/tail-vs-fresh-generation oracle และ central reader regression
ก่อน actual-API browser flow ไม่เปิดproduction/Live ไม่เพิ่มinfrastructure/retention/สูตรเงิน
แทนเฉพาะรายละเอียด unconditional non-RUNNING cutoff ที่บันทึกไว้ก่อนหน้า เก็บประวัติเดิม

### ARM source-correction fence — engineering amendment before code

พบ reset_close ใน checkpoint ไม่มี candle provenance: หาก source แก้ราคา ARM เดิม
ค่าที่เก็บอาจทำให้ BUY ผ่าน threshold ที่ไม่ตรงข้อมูล authoritative ปัจจุบัน
ภายใต้อำนาจ engineering/safety ที่มอบหมาย เลือกเก็บ reset_open_at คู่กับ reset_close
และตรวจ historical ARM point จาก F-11 generation เดียวกับ FIRE (RSI<30 และ closeตรงเดิม)
ก่อนอนุญาต FIRE; หากพิสูจน์ไม่ได้ให้ fail closed รอ ARM สดตามกฎเดิม ไม่แก้ reset ย้อนหลัง
ใช้ source proof ครอบ calculation เดิมและ commit fence เดิม ไม่เปลี่ยนสูตร/trigger/เงิน
เพิ่ม pure no-proof test และ real-PG correction test ไม่ใช้ memory เป็น authority

### Approved harness measurement repair — before code (attempt5)

Owner “approve” หลังattempt4แสดงว่าตัวนับpaper_order_commandsรวมCANCELด้วย
แก้เฉพาะtest-onlymetricsและbrowseroracleให้ordersอ่านpaper_orders, แยกNEW/CANCEL,
ตรวจUUID5cancel-entryตามF17และterminalresults; คงBUY2/SELL2/execution4,
cash10895.4715175/PnL895.4715175/flat/zeroreservationและTP434.98
reuseRLSuser_session/get_wallet/positionprojectionsเดิม ไม่เพิ่มproductionAPI/ตรรกะการเงิน
ไม่แก้executorหรือเลิกCANCELเพื่อให้เทสต์ผ่าน; อำนาจengineeringในการแก้harnessที่วัดผิด
และownerอนุมัติหนึ่งรอบทดลองเพิ่ม5–7นาที หยุดทันทีหากล้ม ไม่retryเอง

### Owner authorization — finish implementation and review

เจ้าของสั่ง “approve แก้ไขให้จนเสร็จ และแจ้ง review code” หลังattempt5
อนุมัติแก้fixture schedulingตามproposalและทำงานที่เกี่ยวข้องต่อเนื่องถึงcheckpoint:
ตรวจpreflight→actualflow→targeted safety/validationที่ค้าง→Ready for Code Review→review/fix
คงกฎธุรกิจ/financialoracleและประวัติFailedเดิมทั้งหมด ไม่เปิดproduction/Live
เตรียมfixtureหลังrealUTCminutecloseแล้วseed250; ก่อนปล่อยsignalแรกต้องตรวจ
actualRUNNING/eligible_afterและtarget>endของข้อมูลที่ถือว่าbackfill ไม่มีtimewarp/ย้อนARM
คงรอบactualflowใหม่ตามproposalหนึ่งรอบ 5–7นาที และกฎหยุดเมื่อไม่ผ่านตามAGENTS
owneracceptance/finalCIยังเป็นด่านแยก ไม่ถือว่าคำสั่งนี้แทนผลตรวจเหล่านั้น

### Projection cross-run linkage review — engineering fix before code

พบbot_strategy_entriesมีbasket(run/owner/mode/episode)FKและorderlink(owner/episode/order)FK
แยกกัน แต่ยังไม่ผูกrunของorderlinkกับrunของentryโดยตรง จึงUPDATEprojectionให้โยง
คำสั่งเดิมไปbasketของอีกรุนของowner/episodeเดียวกันได้หากcallerมีbug
เพิ่มUNIQUE(command_id,run_id)บนbot_order_linksและFKคู่เดียวกันจากentry
reusecompositeFKpattern0068; ไม่เปลี่ยนbusinessadmission/เงิน/permissions และไม่เพิ่มinfrastructure
ทดสอบcrossrun/episode/mode rejectionและownerRLSด้วยrealPG พร้อมfreshschema/roundtrip
underengineeringauthorityด้านcorrectness/security. migration0074ยังเป็นuncommittedfeature
E2Eattempt6ใช้validlinkageเดิมและไม่ถูกเปลี่ยนbehavior; ตรวจconstraintบนfactsจริงของรอบนั้น
และfreshmigrationเพื่อปิดschemaส่วนเพิ่ม โดยไม่รันfullflowใหม่เพียงเพราะเพิ่มFK

### Review finding — wallet refresh after position changes (before code)

ภาพactualflowหลังexitแสดงpositions0แล้วแต่availablebalanceยัง4391ชั่วคราว เพราะbotstatus
poll2sและtrade/walletquerypoll5sแยกกัน เป็นUIcachelag (DBcash10895.4715175ถูก)
แก้เฉพาะcachecoherence: เมื่อverifiedbotpositionsเปลี่ยน ให้อinvalidateowner-scoped
tradequeryผ่านmanualKey(owner)เดิม ไม่คำนวณ/ปรับbalanceในbrowser ไม่POSTอัตโนมัติ
ไม่invalidateownerอื่น และไม่เพิ่มtimer/globalcache. เพิ่มquery-cacheintegrationtest
คงUI/TailAdminเดิม ไม่ต้องรันfinancialflowเดิมซ้ำเพราะไม่เปลี่ยนAPI/engine/ledger
ภาพเดิมเก็บตามจริง; owneracceptanceยังPending

### Review finding — execution metadata tick (before code)

พบrecord_executionเก็บbasket.price_tickด้วยcoalesceจึงตรึงtickจากfillแรกตลอดbasket
หากmetadataเปลี่ยนtickแล้วมีfill/disposalใหม่ candidatefloorอาจใช้tickเก่า (เช่น
100.73บนtick0.01แทนfloor100บนcurrenttick1). ตามapprovedfloor-to-tick/metadata rules
ให้ส่งtickจากactualF15executionrecordเข้าsynchronize_basketและบันทึกtickที่ใช้ในrevision
ทุกfill/disposal คงmin(candidate,held)เดิม ไม่ยกheld/เปลี่ยนscaleหรือroundingpolicy
fallbackสำหรับcallerที่ไม่มีtickใช้storedproofเดิมหรือsharedsource reader; ย้ายpersist
ออกจากBUY-onlyrecord_executionเพื่อลดซ้ำและครอบSELLด้วย. ทดสอบrealPG100→90,
fixed100ต่อไม้, metadata tick0.01→1, target106→100ทั้งกลุ่ม พร้อมaffectedFIFO/TP/recovery
เป็นengineeringcorrectnessfix ไม่เพิ่มกลยุทธ์/เงิน/เพดานriskใหม่

### Review finding — realtime reconnect between bot polls (before code)

ตรวจset_connectedเดิมพบdisconnect/reconnectใช้FeedLeasegenerationเดิมได้ และwrite_price
ล้างunavailable_sinceหลังreconcile ดังนั้นF21ที่ไม่ทันpollช่วงRECOVERINGอาจไม่เลื่อน
backfillcutoff แม้candledemandยังCOMPLETE. เพิ่มdurablebot_recovery_atบนpricefeed
ด้วยDBtriggerเมื่อconnected/generationเปลี่ยน และprogress.price_recovery_atที่ackเมื่อready
reusecandle recovery marker pattern/DBclock/source fencเดิม ไม่เพิ่มsessionmemory/Redis
ไม่เปลี่ยนF11/F15priceสูตรหรือการเทรด; เพิ่มspecificrealPGquickreconnecttestและsourceinput
regression. เป็นsafety/source-readinessengineeringfixตามอำนาจที่มอบหมาย

### Amendment — deep review fixes (2026-11-21)

Under the approved engineering delegation, apply the existing basket, F-17 and F-20 policies at their shared boundaries. An ARMED dust allocation can reject the observation before its siblings latch TP, and a sibling's fanout can classify that same dust as a BOT setup failure. Evaluate the basket against the authoritative observation before individual sizing, preserving ARMING setup policy and durable triggered work. Validate checkpoint semantics at decode before any indicator I/O because an unzoned ARM timestamp can escape the worker. Allow a candle SYSTEM probe to prepare dependencies, retaining final source and snapshot fencing before issuing proof. Register the isolated F-21 actual-browser suite in required CI. These are ordering, validation and test wiring changes within the approved scope. No strategy thresholds or financial formulas change. Verify with real PostgreSQL residual, recovery and malformed checkpoint cases, existing affected tests and CI discovery.

### Follow-up refactor of the deep review changes

Under the delegated engineering scope, simplify the candle recovery predicate, reuse the converted basket target, and consolidate the recovery regression's setup and probe calls. Preserve the existing decision for every input kind, F-17 transaction and retry ordering, and the two-owner assertions. Reuse the current database tests and existing stop/proof APIs.

### V05 amendment — risk change during candle evaluation

The PostgreSQL positive control committed one BUY. Quote, catalog and lease changes discarded it. A real DECREASE request applied revision 2 before the final check, yet the worker still committed the revision-1 BUY. The existing risk-owner lock protects each transaction separately and the prepared snapshot omits the setting revision. Under the delegated engineering authority, carry the already-read post-replay risk revision across F-21 candle evaluation and compare it through the existing snapshot equality check. Holding the lock during pure evaluation would unnecessarily serialize account work. A compatible change allows a fresh evaluation of the same candle. Keep feedback handling, admission thresholds and financial calculations as approved.

### V05 amendment — published indicator generation at candle commit

PostgreSQL reproduced two stale BUYs after pure evaluation. Replacing the ready head with a new generation of identical candles preserved the old source proof. F-11 also retained the old head after a newer numeric failure. In both cases the locked source proof alone passed, although the current F-11 reader would choose a different generation or reject the input. Under the delegated engineering authority, reuse the prepared reader's head selection and newer-failure precedence at F-21 candle commit under the existing source guard, which serializes normal publication and rollout. Rechecking bounded metadata avoids replaying indicators under financial locks. Keep cursor continuation and strategy formulas intact. Validate the stale writes, unchanged-input control, fresh replacement, reader behavior and existing candle/tail proofs.

### V05 amendment — queued F-21 BUY authority

The local PostgreSQL worker accepted five stale queued BUYs (corrected candle, edited risk setting, replaced prepared generation, newer numeric failure, rotated rollout). A normal quote update still permitted execution. Under delegated engineering authority, store the decision's validated generation, rollout, source fence, risk revision and lease generation in the existing immutable decision provenance. At initial Paper admission compare run revision, lease and risk, lock the existing source guard and check the active indicator authority and bounded source journal. Reject absent or invalid proof using the existing terminal command path. Use the signal timeframe and existing publication/ledger policies. Do not re-run the strategy or invalidate an already admitted fill on each incoming price. Reuse accounting fixtures with real database authority for their synthetic signals.

A candle-demand row lock can delay admission after reading the run lease. Check database time again after the potentially blocking source reads, so a lease or generation expiring during that wait cannot authorize the BUY. Use the order link's indexed order identity when locating the entry. Cover expiry inside this window with a real database clock.

### Main-screen stop button presentation

Reuse PaperBotPanel, BotRunStatus and KillSwitchControls with the existing TailAdmin Button/Badge components. On a server-confirmed pending start or run without replacement, render compact status and the existing F-19 stop action in the main panel. Hide the expanded exposure/configuration form for this presentation. Retain the full status view for other callers and retain uncertain-start recovery when no server receipt exists. No new stop API or financial transition. Verify pending/running/paused/stopped, error/retry and unchanged start recovery.

Owner clarified that Stop belongs on the same main screen as Start. Keep one PaperBotPanel section and one action region, switching its Start control to the existing stop control when the server confirms the request. Keep the compact status in that same region and retain the previous presentation scope and recovery rules.

Owner clarified the screenshot is the settings sidebar, not the main chart controls. Move the active F-21 stop action into TradingWorkspace's chart header, and collapse the settings sidebar while that action is present. Reuse the shared bot-status query and keep PaperBotPanel mounted to preserve start-receipt recovery. Extend the existing grid layout to a single chart column when the sidebar is hidden. This replaces the previous interpretation of same-panel placement.

Final owner placement clarification: Stop belongs in the order card containing Reduce / close holdings. Move the active stop/status there, remove its chart-header slot, and retain the collapsed settings sidebar. Render that same order-card action even if the wallet snapshot is temporarily unavailable. This supersedes the previous header placement.

Owner answered the location question explicitly: the order-entry form card, not the order list. Preserve the right-hand form card and its disabled pinned configuration, replace Start with Stop in its action region, and omit the expanded run detail. Remove the speculative header/order-list placement and sidebar-collapse changes. This supersedes the earlier location interpretations.

Owner reported Start missing after Stop. A STOPPED/RETIRED run must render the start action (disabled while replacement proof is unavailable), not the active Stop action. Retain full stopped-run summary and existing replacement acknowledgement/readiness. Active pending requests remain distinct from a completed stop. Diagnose the local owner-preview worker independently before changing runtime behavior.

Owner's repeated start requests resolved BOT_NOT_READY because USER STOP remains active without an existing bot run. Reuse the shared kill-switch status query and StopSummaryModal in PaperBotPanel to show the active stop and its existing resume flow before Start. Disable ordinary start while that stop is active; retain the approved replacement proof path. Map known terminal start failure codes to readable reasons instead of treating every rejection as invalid settings. No automatic stop clearing or new resume endpoint.

Owner requested a short notice below the action after stopping instead of the expanded run snapshot, configuration and holdings summary. On confirmed STOPPED render the notice below Start, retaining stop-summary access when resuming is required. If holdings exist or cannot be verified, the short message must reflect that. Keep backend-authoritative stop state and pending/error handling.

Remove PaperBotPanel's replacement checkbox and its local acknowledgement state. Reuse the existing Start submission, persisted replacement proof and backend revalidation. Update the regression to verify direct Start uses the current proof after a revision change, and absence of a valid start/replacement capability still disables submission.

Owner requested removing the explanatory RSI/EMA sentence from the bot card. Remove that paragraph and its unused Thai/English translations. This is presentation copy only.

Owner requested removal of “บอทหยุดแล้ว”. Remove the flat stopped notice and its unused translation, retaining only existing remaining/unverified holdings notices without that prefix. Remove dangling notice descriptions when no message is rendered. Stop and start transitions continue to use server state.

Owner requested deletion and refactor after the hidden-text audit. Remove PaperBotPanel's unreachable/obsolete expanded status call and its screen-reader-only duplicate updating text (the balance already has aria-live). Remove the now-unused showControls option from shared BotRunStatus, consolidating notice-description selection in the panel. Retain the full status body used by LiveTradePage and background manual-request tracking, which are active callers/dependencies. Keep errors, risk/stop recovery and holdings warnings.

Owner reported a notice flashing below Start during Chrome reload and disappearing after data arrives. The panel initially treated an unknown run as idle and rendered its generic settings notice. Require successful bot/stop status reads before deriving notices or stop-block warnings, while keeping initial Start disabled. Bind aria-describedby only to a rendered notice. Add delayed-response cases for active and stopped runs to prove the initial reload has no such transient message.

### Reload-state audit across frontend — 2026-11-21

Owner requested checking the same transient-message problem throughout the UI. Under the
2026-11-14 engineering delegation, inspect all frontend renderers and asynchronous reads,
reusing existing React Query states, shared messages and template components. Confirmed
issues: StopControl renders noStopDetails before status resolves; platform stop summary
fabricates zero pending/failed counts without a response; activity claims another page
while initial orders/protections are loading; shared workspace labels an unknown initial
price unavailable before the chart snapshot arrives. Gate factual copy on its existing
read proof, render platform loading/read-error explicitly, and use a neutral dash for
unknown prices. No change to queries, sessions, permissions, mutation admission, retries,
financial data or persistent state. Existing empty-state gates and intentional static
Live capability/placeholder notices remain as specified. Add deferred-response regression
tests using the existing QueryClient/fetch harness and inspect affected callers.

### Remove standalone chart — 2026-11-21

Owner explicitly requested removal of the chart menu/page and its code. Remove chart
from accountNavigation registry, AuthPanel route branch and AccountNavigation links;
reuse currentPage fallback and native-link behavior to resolve old URLs to paper/trade.
Update AccountLayout and PageBreadcrumb home accordingly. Remove standalone-only
CandlestickChartPanel branches, TradingWorkspacePlaceholders, unused copy/icon/styles;
retain chart renderer/data hooks and embedded Paper/Live consumers. Reuse supported
catalog selection via existing onBaseChange. Update navigation/chart regressions and
E2E callers to the retained trading workspace; preserve market-data safety assertions.
Targeted tests/static checks, affected diff/caller review and browser visual check.
No exchange/database/session/financial changes or new infrastructure.

### Review fixes — exact entry cost and query outages (2026-11-21)

Owner requested fixing all three review findings. Under the 2026-11-14 engineering
delegation, preserve RQ04/11 arithmetic and existing rounding: retain each entry's
gross_notional/gross_quantity ratio through weighting by remaining net quantity.
Reuse money/basket_arithmetic.py::basket_take_profit with optional typed entry costs,
perform exact rational arithmetic inside core.money only and round once at the existing
tick boundary. Existing callers without cost facts retain their behavior. No migration
is needed; baskets already persist gross_notional/gross_quantity. Existing held target
remains authoritative (do not move a historical TP away to repair rounding).

Reuse BotRunStatus error alert/retry and BotStopControls: keep Stop available when the
last successful result proves a run/pending request, without claiming that cached status
is current. PaperBotPanel must show sanitized errors/retry for its status, stop and
catalogue reads; keep initial loading neutral and Start disabled until ready. Use shared
buttons/messages/query identities. Regression tests cover RUNNING→GET failure→Stop and
each initial read failure→retry→ready, without automatic start/trading.

Tests: numeric oracle 200/3 and100/3, ATR1/tick0.01 should give53.00 (old52.99); fees/net
quantities, partial reduction, tick/held boundaries, invalid costs; actual PG matcher
with multi-price partial entries and cancellation of remainder; existing basket/fill/TP
race regressions plus affected frontend suites/static checks. No new risk/strategy rule.

Affected test static checks also exposed pre-existing F-21 typing gaps in the same
basket integration file (untyped proof helper/wrapper, optional load results and SQL row
conversion). Add annotations/narrowing and import the wrapped save from its defining
module, retaining every assertion and fault injection; no runtime policy changes.
