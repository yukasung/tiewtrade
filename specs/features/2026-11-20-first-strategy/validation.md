# F-21 — RSI Step Grid / Single Basket TP — Validation

สถานะ: **Approved — เจ้าของตอบ “approve” ฉบับแก้ F21-R01/R02 วันที่ 2026-11-20**
วันที่: 2026-11-20 (Asia/Bangkok)
ฐาน: requirements/plan/validation Approved; implementation อยู่ระหว่างตรวจ Feature บน branch `feature/f-21-first-strategy`

## 1. เกณฑ์ตรวจรับ

ผลเริ่มต้นทุก Feature เป็น Not Run; การอ่านโค้ด Desktop หรือ tests ของ F-20 ไม่ใช่
ผล Passed ของกลยุทธ์ใหม่ การ reuse หลักฐานระบุ candidate/scope เดิมให้ชัด

| # | เกณฑ์ / ที่มา | วิธีตรวจ | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V01 | ARM/FIRE + EMA/RSI filter; RQ02/03, BUY01–04, SR08 | independent truth table: RSI<30/reset latest, RSI=30/60, EMAเท่ากัน, doji, closeเท่ากับEMA/reset, pending, can_enter false; ทุก AND ต้องผ่านและไม่มี crossover requirement; exitบนแท่งเดียวห้ามBUY แม้มีresetพร้อมและslotว่าง แท่งถัดไปไม่มีexitจึงกลับมาประเมินได้ | Feature | Passed — 54 pure strategy/target/FIFO cases รวม strict thresholds, pending, guards และ next-candle behavior |
| V02 | Determinism/purity/version; RQ03/06/08 | same input/config/state/timeให้ผลเดิม Paper/Live core parity, no I/O/random/float; exact codec unknown keys/version rejected; ไม่โหลด Desktop canonical เป็นกลยุทธ์ใหม่ | Feature | Passed — determinism/exact codec/pure Paper–Live parity; import contracts 7 kept; ไม่มี Live execution |
| V03 | Parameters/immutable config; RQ01/04/05/06 | เงินpositive exact USDT string; count1/2/3/9/10ผ่าน,0/11/bool/fractionปฏิเสธ; default10/5m; คู่/timeframeจากshared contracts; ค่าเงินไม่มีdefault; configเปลี่ยนrunเดิมไม่ได้ | Feature | Passed — strict config/count1–10/immutable pin และ owner/idempotency tests; actual browser pin 2804.5/3/1m |
| V04 | CLOSED inputs +250 warm-up; RQ02/07, Web data table | 249แท่งไม่ประเมิน/250พร้อมจึงผ่าน; EMA20/50/RSI/ATRและOHLCตรงแท่ง/รุ่น; forming/gap/stale/backfill/retention不足ไม่BUY;250ไม่overrideF11 readiness/seed | Feature | Passed — real PG 249/250, prepared source/tail equality, correction/recovery fences และ actual fresh M1 flow |
| V05 | Input/source/stop/exit fences; RQ07/08, SR08 | real-PG mutate prepared generation/rollout/catalog/lease/run/stop/exit-guardระหว่างprepare/evaluate/commit และก่อนqueuedBUYexecution ผลเก่าต้องทิ้ง; inputซ้ำ/ผิดลำดับไม่BUYซ้ำ ไม่advance cursorข้ามunready; verifyทั้งสองcommit ordersของexit/BUY | Feature | Passed (local) — real PG ทั้งก่อน commit และก่อนรับ BUY จากคิว, delayed replay, source recovery, lease expiry ระหว่างอ่าน และ BUY/exit ทั้งสอง commit orders; ดูหลักฐาน V05 ด้านล่าง |
| V06 | Single basket numeric oracle; RQ04/11 | มือคำนวณแยกจากimplementation: ซื้อแพงขึ้น/ถูกลงยังกลุ่มเดียว; unequal quantities, latest ATR, partial disposal/fill, heldTP=min, floor tick, zero/overflow/unit mismatch, ไม่สร้างPnL ledgerซ้ำ | Feature | Passed — independent numeric boundaries/tick/split/units/overflow; actual fees/PnL/FIFO/held target; current metadata tick case |
| V07 | Migration/isolation/permissions; RQ08 | fresh/upgrade existing F20DB, FORCE RLS/FK/unique/check constraints, owner/mode/episode crosslinks rejected; runtimeไม่เป็นmigrator; rollbackไม่ลบactive refs; no secret access | Feature | Passed — fresh/roundtrip/history refusal/FORCE RLS, narrow grants และ cross-run/episode/mode/owner boundaries 5 cases |
| V08 | Config/start API + idempotency; RQ05/06/08/09 | strict server validation/CSRF/auth/owner scope, unknown ref, timeoutก่อน/หลังcommitอ่านreceiptเดิม; new API instance resolve config/startได้ ไม่สร้างrun/orderซ้ำ | Feature | Passed (local) — owner/config/idempotency/CSRF, API process restart, actual browser timeout/reload before and after start commit; evidence below |
| V09 | Entry sizing/reservation/max entries; RQ04/07/11 | real-PG actual Paper matcher/fee model: เงินต่อไม้ไม่หารจำนวนไม้, lot/minimum/insufficientเงินปฏิเสธ, fee reserveตามเดิม, partialหนึ่งintentนับหนึ่งไม้, pendingจองslotและbudgetไม่ซ้ำ | Feature | Passed — actual fixed per-entry sizing/net fees, partial/cap1&10/pinned budget rollback และ browser two-entry totals |
| V10 | Actual feedback/state/rebuild; RQ07/08/11, SR08 | full/partial/reject/cancel/unknownและduplicate/reorderedfacts, netqty/fee/basefee, no-fillrejectคงreset, filledต้องARMใหม่; crash/restart/replayให้basket/heldTP/trigger/exitguard/ledgerเหมือนoriginal facts; exitfactมาช้าหรือซ้ำไม่เปิดBUYบนแท่งเดิม | Feature | Passed (local, combined evidence) — full/partial/reject/cancel/expiry feedback, pending/reset, FIFO/dedup, delayed fill after closure, correction replay and lost SELL COMMIT recovery; see closure evidence |
| V11 | Shared TP via F17; RQ07/11; F21-R01 | actual-PG atomic target revisionครบทุกallocationหลังnew/partialfill/manualreduction; basket winning triggerใช้source evidenceเดียวสร้างexit workทุกไม้ ราคากลับตัวก่อนworkerถัดไปไม่ทิ้งไม้ที่เหลือ; targetcrossed/rejection/setupfailureใช้policyเดิม ไม่ใช้staleevidenceแทนcurrentexecutionreadiness | Feature | Passed (local) — atomic shared targets, trigger/fanout faults, both fill/TP commit orders, delayed fill notification and restart; late-fill interpretation documented below |
| V12 | Races/atomicity/financial safety; RQ07/08/11, SR08; F21-R01/R02 | PostgreSQLหลายsessions: retarget vs trigger/price reversal, exit vs candledecision/queuedBUY, entryfill vs TP/manualSELL/cancel/stop/risk/catalog/takeover; faultทุกcommit boundaryของretarget/trigger/fanout/latefill; no mixed effective targets/lostexit/oversell/duplicateexit/negativebalance/doubleallocation; oldworkerหมดสิทธิ์ | Feature | Passed (local) — PostgreSQL contention barriers for BUY/SELL, match/TP and match versus risk/catalog/takeover in both commit orders, target rollback and durable replay |
| V13 | Restart/stateless/safety regression; RQ08/10; F21-R01/R02 | API+engine restart/Redisloss/secondinstance recover config/cursor/heldTP/baskettrigger/exitwork/exitguard; samecandleหลังBasketว่างยังห้ามBUY; retryworkidentityเดิมหลังresponseหาย; no cross-mode/owner leakage, noPaperLive network และ manual/F17/F20 unaffected regressions | Feature | Passed (local, combined evidence) — API process timeout/restart, new ENGINE pool, Redis-independent trigger recovery, same-candle guard and distinct next-candle basket; see restart evidence |
| V14 | UI/template/locale/accessibility; RQ09 | component+375/768/1280/1440 browser: เงินต่อไม้/count1–10/timeframe/actualconfig/commonTP, no cooldown, readonlyสูตร; keyboard/focus/error/default/disabled/lightdark/THENตรงtemplate; chartไม่แก้run | Feature | Partial — component/template/locale/responsive checksผ่าน; owner visual acceptance ค้าง; wallet cache lag แก้และตรวจแล้ว |
| V15 | Complete feature flow; RQ02–11; F21-R01/R02 | isolated actualAPI+PostgreSQL+Paperexecution: config→start→ARM/FIRE→BUYpartial/full→singlebasketTP→addสูง/ต่ำ→triggerราคากลับตัว→commonexitครบ→closed; ไม่BUYบนexitcandleเดิมหลังrestart ก่อนเริ่มnewbasketบนแท่งถัดไปที่มีsignal;250unready/pause/stop/exactretry | Feature | Passed (local, combined scenarios) — actual API browser attempt6 plus separate partial-fill, timeout/restart, rejection, warm-up and real exit-candle/new-basket cases; owner visual acceptance is V14/V17 |
| V16 | Contracts/static checks; RQ03/05/09 | Ruff/format/mypy/import-linter, frontend lint/typecheck/build, regenerated OpenAPI/types exact sync, doc/diff check; fresh-state/affected migration fixturesไม่พึ่งลำดับtests | Feature | Passed (local) — affected Ruff/format/mypy, import contracts, generated contracts sync, frontend type/lint/build และ diff checks; CI แยก V18 |
| V17 | Review + owner visual acceptance; RQ09/10 | Ready for Code Reviewเมื่อfeatureครบ→review diff/callers/security/stateless/tradingsafety→fix/refactorเท่าที่จำเป็น→affectedchecks; เจ้าของตรวจภาพ/flowจริงในisolatedenvironment | Feature | Partial — Ready for Code Review แจ้งแล้ว; review diff/callers + fixes/affected checksแล้ว; owner acceptance ค้าง |
| V18 | Final candidate CI/publication | final-SHA required CI/Security/contract/freshstateตามconfigจริง, branch/PRheadตรงcandidateก่อนmerge, postmergeผลจริง; localไม่แทนCI | Feature | Not Run — ยังไม่มี final SHA/required CI; ไม่ commit/push/merge ใน checkpoint นี้ |
| V19 | ชุดที่6 full integrated regression; F20 V19/20 | full bot/config/strategy/UI cross-feature E2E+protection/risk/STOP บนcandidateรวมที่นิ่ง พร้อมnegative/fault oracle; reuse unaffectedก่อนขยาย ไม่ใช้FeaturemockปิดBatch | Batch | Not Run — Pending Full Validation; checkpointท้ายชุดที่6 |
| V20 | Combined release/activation dependencies | ระบบรวม/Liveexecutor/reconcile/notifications และ workload/endurance/resourceตามprofileเดิมที่อนุมัติ (รวม100-accountเมื่อเกี่ยวข้อง); ไม่คิดตัวเลข/ระยะเอง ไม่ส่งLiveorderในautomation | Release | Not Run — Pending Full Validation; checkpointชุดที่9/ก่อนเปิดใช้งาน |

## 2. Independent financial cases

เลือก fixture ที่ค่า exact และใช้ Money/Quantity ตาม types กลาง ตัวอย่างoracleเหล่านี้
ไม่ใช่จำนวนเงินจริง/default และไม่ใช้ production helper คำนวณexpected:

- tick0.01: Entry1 price100, qty1, signalATR2 → TP106;
  Entry2 price80, qty1.25, signalATR2 → weighted200/2.25,
  floor-to-tick target94.88; ทั้งสองไม้กลุ่มเดียว
- ซื้อแพงขึ้น: Entry1 price100/qty1/ATR10→TP130;
  Entry2 price110/qty1/ATR10→candidate135 แต่heldTP130คงเดิม;
  ต้องไม่สร้างกลุ่มใหม่หรือขยับTPขึ้น
- ซื้อถูกลงแต่ATRเพิ่ม: price100/qty1/ATR2→106;
  เพิ่มprice90/qty1/ATR10→candidate125 แต่targetยัง106
- ขายไม้ที่มีATRล่าสุดออก คำนวณจากรายการที่ยังเปิดและATRของlatestremaining
  แต่คงheldmin; เมื่อbasketปิดแล้วbasketใหม่ไม่รับheldtargetเก่า
- actual execution cases แยกตรวจ fees/net acquired/reservations/PnL ด้วย independent
  position/ledger assertions ตาม F14/F15 ไม่ใช้ no-feeตัวอย่างแทน real financial proof
- properties: targetไม่เพิ่มภายในbasketเดียว, การsplit partialfillไม่เพิ่มlogicalentry,
  sumallocated≤confirmedremaining, repeatfeedbackไม่เปลี่ยนเศรษฐกิจ,
  state+heldTPหลังrestoreเท่าก่อนrestart, noinputหรือunreadyไม่ออกintent

## 3. เลือกตรวจตามผลกระทบ

### Regression ที่เพิ่มจาก deep review — ทุกข้อเป็น Feature / Not Run

ใช้ V เดิม ไม่สร้าง campaign หรือเกณฑ์ราคา/เงินใหม่:

- **F21-R01 / V11–13:** มีอย่างน้อยสองentry allocations targetร่วม106;
  source sequenceSให้ราคา107ที่freshและมีreadinessครบ ต้องได้winningbaskettrigger
  เดียวและ durable exit work ครบทุกeligibleallocation จากevidenceS
  ต่อมาsourceS+1ลดราคา104ก่อนdispatchไม้ถัดไป งานไม้ที่เหลือต้องไม่หายหรือre-arm
  ตรวจcurrentexecutionreadinessใหม่ และตรวจยอดที่ขายจริง/เหลือจริงตามF-17
- **Atomic retarget / V11–12:** target106เปลี่ยนเป็น101หลังfill; barrierเปิดให้
  triggerworkerแข่งระหว่างretarget ตรวจว่าเห็นoldrevisionครบชุดหรือnewrevisionครบชุด
  ไม่เห็นeffective targetsปะปน; rollbackก่อนcommitคงoldstateและไม่มีorphanwork
  targetใหม่ต้องถูกประเมินแม้marketcursorเดิมเคยถูกอ่านแล้ว
- **Durable trigger/fanout / V12–13:** injectfaultก่อน/หลังcommit trigger/exitwork
  และทิ้งresponseหลังcommit; restartworkerโดยไม่มีRedis hintต้องกู้trigger/workเดิม
  ครบทุกallocationโดยuniqueconstraint/idempotencyตรวจไม่เกิดexitcommandซ้ำ
  lateentrypartialfillหลังtriggerต้องเพิ่มexitworkเฉพาะdeltaตามF-17ไม่สร้างBasketใหม่
  รวมallocationที่reserved/exit-in-flight/ส่งไม่ได้เพื่อพิสูจน์failure policyและnooversell
- **F21-R02 / V01/V05/V10/V12/V15:** เตรียมresetและBUYfiltersครบพร้อมslotว่าง
  แล้วทำactualTPexit,manualSELLและpartialexitในแท่งCทีละกรณี; เมื่อCปิดห้ามสร้างBUY
  ครอบคลุมlastentryexitที่ทำให้Basketว่าง, duplicate/delayedfeedback และengine restart
  หลังexitก่อนevaluate; persistedguardต้องอยู่ต่อและไม่อาศัยbrowser/in-memory state
- **Guard ordering / V05/V12:** two-sessionbarrierให้exitcommitก่อนBUYdecision
  และสลับลำดับ; oldguardrevisionห้ามpersistหรือexecutequeuedBUYข้ามexitที่commitแล้ว
  ตรวจauthoritativetransactionorder ไม่rollbackconfirmedfillหรือสร้างcompensatingtrade
  คำขอขายที่ยังไม่มีfillต้องไม่ถูกนับเป็นexitfact
- **Candle boundary / V01/V10/V15:** exit timeตรงcandleopen/close, timezoneUTCและ1M
  mapเข้า[open,close)จากexecutionfactถูกต้อง; C+1ที่ไม่มีexitกลับมาพิจารณาBUYได้
  เมื่อARM/state/filtersและgatesเดิมพร้อม ไม่เพิ่มวันพักหรือบังคับcooldown

ตรวจข้อเหล่านี้ด้วยpuretestsร่วมreal-PostgreSQL financial assertions ไม่ใช้mockพิสูจน์
transaction/locks; ฟอร์ม/UIfixturesไม่ใช้แทนtrigger/guardproof

| เปลี่ยนส่วนใด | หลักฐาน/ชุดเดิมเริ่มต้น | ตรวจเพิ่มเฉพาะช่องว่าง |
|---|---|---|
| Pure contract/numeric | core bot contract/money/protections tests | new signal truth table/singlebasketoracles/partialstate/codec |
| Candle inputs | F20 test_bot_indicator_inputs + F11 prepared/generation tests |250proof/OHLCidentity/backfill/fenceและboundedread |
| Config persistence/API | infra/bots/test_requests, API/test_bot_routes, F20migration/restart | owner refs/schema/ranges/multiinstance/recovery |
| Basket/TP | execution_market/test_bot_decisions, feedback/races และ protections/tests | sharedtargetatomicity/partialfills/entrysequence/TPactualexit |
| UI | PaperBotPanel/BotRunStatus tests, bots/paperbot/protection E2E | newform/disabledreason/actualsingleTP/owneracceptance |

เมื่อ contract/migration/numeric/shared worker เปลี่ยน ให้ขยาย targeted regression ไปยัง
callers ที่ใช้จริงก่อน; full regressionเมื่อกระทบหลายระบบ/กำหนดขอบเขตไม่ได้ตามtesting§7
ผลF17/F20เดิมใช้ต่อเฉพาะสิ่งที่ไม่ถูกกระทบ ไม่อ้างว่าผ่านกลยุทธ์ใหม่นี้
Feature financial/concurrency correctness ตรวจทันที ไม่เลื่อนไปBatch/Release

## 4. Checkpoint และข้อจำกัด

สถานะปัจจุบัน: Feature **Partial / Incomplete** ตามตารางและหลักฐานด้านล่าง
ยังไม่ Ready for Code Review, ไม่ Completed และไม่พร้อม merge
หลังอนุมัติplan/validation ทำ M1–M4/targetedchecks→review/fix/refactor→ownerUIacceptance
และrequiredCIตามAGENTS.mdก่อนmerge; ownerUIacceptanceต้องเป็นหลักฐานจริง
ทุกstepรายงานผล/checkpointเดิมและnextstep ไม่สร้างreview approvalย่อยเพิ่ม

ก่อนfullregression/crossfeatureE2E/workloadแจ้งscope/สิ่งที่พิสูจน์/ประมาณเวลา
ไม่รันcampaignใหม่โดยไม่มีapprovedprofileหรือเกินจำนวนรอบที่อนุมัติ
หยุดเมื่อfailureเกณฑ์เดิม3รอบหรือเจ้าของแจ้งใช้เวลามากเกินไป; ไม่ลดassertions/safety
คงFailed/Partial/Incomplete/NotRunตามจริงและบันทึกcandidate/sourcepins/cleanup
realDBfixturesต้องเป็นownedisolatedDB ไม่แตะaccountหรือproductionflagsของเจ้าของ
ไม่เปิดLive ไม่ส่งเงินจริง ไม่เปิดadmissionหรือเปลี่ยนdeploymentจากงานvalidationนี้
Featureผ่านไม่แปลว่าCompletedจนBatch/Releaseที่เกี่ยวข้องครบ

## 5. Review-fix checkpoint — 2026-11-20

F21-R01 High และ F21-R02 Medium แก้ขอบเขตแผน/เกณฑ์ตรวจแล้วตามคำสั่งเจ้าของ
statusนี้หมายถึงเอกสารกำหนดวิธีแก้และproofครบ ไม่ใช่runtimefindingถูกแก้หรือtestsผ่าน
ทุกV01–V20คงNot Run, V19/V20คงPending Full Validation ไม่มีfullsuite/workload/CI
หรือruntime/sourcechangeในรอบเอกสารนี้; plan/validationยังProposedรออนุมัติ

## Implementation authorization — 2026-11-20

เจ้าของอนุมัติฉบับแก้deep-reviewแล้ว เริ่ม implementation/targeted tests/review ตามแผนได้
ข้อความ Proposed/รออนุมัติก่อนหน้านี้เป็นประวัติ; owner UI acceptance/required CI
และ Batch/Release/production gates ยังคงบังคับ ไม่เปิด Live หรือ production เอง

## 5. Implementation checkpoint — 2026-11-20 (working tree)

ผล local ต่อไปนี้ผูกกับ diff ที่กำลังพัฒนา ไม่ใช้แทน final-SHA CI:

- `/tmp/f21-source-safety-regression.xml`: **55 passed / 34.938s** หลัง source-readiness,
  ARM provenance และ financial guard changes; pure38 + actual basket/fees/FIFO/retarget/
  atomicity/capacity/queued cancel/protection readonly + central input regression
- `/tmp/f21-tail-first.xml`: **6 passed / 11.182s**; central tail equality, source-prefix
  and suffix correction fences, normal indicator wait vs actual failure/recovery
- `/tmp/f21-arm-source-first.xml`: **43 passed / 10.717s**;
  `/tmp/f21-arm-correction-first.xml`: **1 passed / 7.087s** ตรวจ ARM ราคา310ที่sourceแก้311
  แล้ว generation ใหม่ไม่รับรอง reset เก่าและไม่สร้าง BUY
- `/tmp/f21-migration-first.xml`: **2 passed / 6.994s**, fresh migration จาก scratch,
  head→0073→head schema roundtrip, narrow demand-only ENGINE grant,
  history downgrade refusal และ forced RLS rollback
- API/config/status/protection targeted ครั้งก่อน `/tmp/f21-managed-regression.xml`:
  **52 passed / 25.099s**; root DB/schema เปลี่ยนหลังผลนี้ ต้องตรวจ affected API อีกครั้ง
- `/tmp/f21-affected-regression.xml`: **172 passed / 1 failed / 103.757s**;
  F17 latency case111=1.426226s เกิน1s; focused rerun บนDBเดิมผ่าน0.607584s
  (`/tmp/f21-f17-latency-second.xml` 1passed). คงผลรอบแรกเป็น Failed ไม่อ้างทั้งชุดPassed
- frontend PaperBotPanel/PaperTradingActivity **25 passed**, typecheck/lint/build ผ่าน
  ก่อน source-only amendment; existing bundle >500k warning คงเดิม
- readonly actualAPI responsive browser **1 passed / 8.5s**, 16locale/theme/width combinations;
  ภาพ375pxจากlocatorมีstickytoolbarทับส่วนบน ต้องเก็บfull-pageภาพที่อ่านได้ก่อนowner acceptance
- actual F21 browser attempt1 หยุดก่อนstartเพราะกรอกก่อนwallet scopeพร้อมและremountล้างdraft;
  ปรับ harness รอ actual balance ก่อนกรอก ไม่ลด assertion/ไม่บังคับenableปุ่ม
- attempt2 serverไม่เริ่มเพราะ source proof ที่เปิดแล้วถูกactivateซ้ำ
  (`SOURCE_ACTIVATION_STAGE_REQUIRED`); ไม่มีtrade/testflowเกิดขึ้นในรอบนี้
  ปรับ fixture ให้ตรวจREADYก่อนactivation; เก็บผลเดิม ไม่อ้างเป็นPassed

การแก้จาก review ก่อนถึง checkpoint นี้ใช้ plan amendments เดิม รวม input tail/source recovery,
immutable entry budget pin, accepted guarded BUY cancel ผ่านF17 cancellation identity,
late-fill durable extra_exit work, strict checkpoint และ owner-approved NC-F21-08/09
ไม่มีLiveorderหรือproductionactivation ไม่มีการผ่อนcorrectness/security/safety criteria

### Final local checkpoint / stopped campaign

- Latest schema API/config/isolation: `/tmp/f21-api-latest.xml` **9 passed**
- Backend changed Python files: Ruff format/check ผ่าน39ไฟล์, mypy **27 source files**ผ่าน,
  import-linter **7 contracts kept**; OpenAPI+TypeScript regeneration hashesตรงกับworkingtree
- Frontend latest TypeScript/ESLintผ่าน; component **25 passed / 1.93s** หลังแก้test-only
  strict array accesses. React checklist: owner-scoped query keys/shared GET dedup,
  durable request IDsก่อนPOST, explicit click/retryเท่านั้น, noautoPOST,
  pinned fields disabled, label/focus/template reuse; receipt completion ยังใช้explicit recovery
- F20 actualAPI regression: first **1 passed / 1 failed (29.6s)**;
  lifecycle keyboard assertionอ้างdetailsปุ่มที่ไม่มีเมื่อยังไม่STOP จึงแก้harnessให้Tab
  ไปreduce/close buttonจริงและShift+Tabกลับstop โดยคงdisabled-fields assertion
  focused rerun **1 passed (26.2s test / 30.7s total)** ครบ16responsive combinations,
  actualstop/retry/recovery/exposure; owner/mode isolation อีกtestผ่าน8.6sในรอบแรก
  ภาพ375TH-lightแบบfullpageอ่านแผงได้ ตรวจแล้ว ไม่มีstickytoolbarทับหัวแผง
- F21 browser attempt3: **Failed (3.6s)** หลังactualAPIstart/RUNNING แต่ก่อนstep1
  metrics fixtureเรียกชื่อตาราง `position_events` ที่ไม่มี (42P01)
  แก้ชื่อเป็น `paper_position_events` ตามระบบจริงไว้แล้ว แต่ **ไม่รันทดลองรอบ4**
  ไม่มีactualBUYเกิดขึ้นก่อนจุดล้ม จึงไม่พิสูจน์ARM/FIRE/TPจากbrowserในรอบนี้
- F21 flowนับ3attemptsรวมstartup failureอย่างระมัดระวังแล้วหยุดตามAGENTS/testing§7
  ไม่resetcounterเมื่อเปลี่ยนชื่อfile/turn. เวลาของtestที่เข้าtestbodyรวม11.1s
  (7.5+3.6s), startup/server/diagnostic wall-clockรวมไม่ได้จับแยก จึงไม่อ้างเวลารวม
  ยังคง V15 **Incomplete** และ V17/V18 **Not Run**; ยังไม่ Ready for Code Review

### Owner decision required before the next F21 browser attempt

แหล่งเกณฑ์: V15/RQ02–11 ต้องพิสูจน์production strategy/domain pathผ่านactualAPI,
PostgreSQLและPaperexecutor; measured assertionsคือfreshclosedM1 RSI ARM/FIRE,
fixed2804.5ต่อไม้/count3, unequal7.8921+7.0929BTC, heldTP434.98,
actualcashหลังซื้อ4391และหลังexit10895.4715175, 4positionfacts/4ordercommands,
ไม่มีduplicate/remainingposition; recordeddata250+5bars, realUTCclose ไม่timewarp
ทุกค่าเป็นfixtureไม่ใช่defaultหรือเงินจริง. การรันใช้test-onlycomposition/localownedDB
เท่านั้น; fullV15ยังมีpartial/restart/exitcandle/newbasket coverageที่ยังต้องปิดต่างหาก

ทางเลือกที่แนะนำ: **คงเกณฑ์ทั้งหมด** ตรวจfixture/session/schemaแบบไม่ส่งtradeก่อน
แล้วอนุมัติ **หนึ่งรอบ** actualbrowserflowประมาณ5–7นาทีบนfreshownedDB;
หยุดทันทีหากไม่ผ่านและรายงานphase/DBfactsก่อนเสนอรอบใหม่ ไม่วนretryเอง
สาเหตุ3รอบที่ทราบเป็นharness/startupทั้งหมด; ความถูกต้องของfullstrategyflowยังไม่พิสูจน์
ไม่มีหลักฐานรองรับการลดfinancialoracleหรือใช้mockแทนtransaction

ทางเลือกอีกทาง: พักเฉพาะbrowsercampaignไว้และเก็บFeatureเป็นIncomplete;
ทำindependenttargetedvalidationที่อนุมัติแล้วต่อได้ แต่ห้ามยอมรับcomponent/infrafixtures
แทนV15 หรือmerge/activate. การปรับเกณฑ์ลดflowให้เหลือmock/unitไม่แนะนำ เพราะ
ทำให้ขาดหลักฐานการต่อAPI→engine→ledgerจริงและยังไม่มีหลักฐานว่ารองรับความต้องการเดิม
ต้องให้เจ้าของอนุมัติscopeใหม่ก่อน; ไม่เสนอค่าcapacity/SLAใหม่เพราะfailureไม่ใช่load

การตัดสินใจนี้ต้องขอตามAGENTS.mdและtesting.md: “เมื่อแก้และตรวจเกณฑ์เดิมแล้วยังไม่ผ่าน
3 รอบ ... ให้หยุดและเสนอทางเลือก ... ก่อนทดลองรอบถัดไป” ไม่ใช่จุดอนุมัติย่อยที่agentเพิ่มเอง

Cleanup checkpoint: ลบเฉพาะ2containersที่ตรวจlabel`tiewtrade.task=F21`แล้ว
และ4temporaryrole/keyenvironment files; เก็บtestlogs/ผลเดิมไว้ ไม่แตะDockerapp
ไม่commit/push/merge ไม่มีproduction/Liveactivation

### Owner-approved next attempt — 2026-11-20

เจ้าของตอบ “approve” ให้คงเกณฑ์เดิมและรันเพิ่ม **หนึ่งรอบ (attempt4)**
ตามข้อเสนอข้างต้น: ตรวจharness/schema/sessionแบบไม่ส่งtradeก่อน, freshownedDB,
realM1closedbars, ประมาณ5–7นาที; หากไม่ผ่านหยุดและเก็บphase/DBfacts ไม่retryเอง
การอนุมัตินี้ไม่แทนผลPassed, ไม่อนุมัติmerge/Live/productionactivation

### Approved attempt4 result — Failed; stopped without retry

Run: `npx playwright test --config=playwright.strategy.config.ts --retries=0`
บนfreshowned PostgreSQL16 (migration0074/track_commit_timestamp=on) และRedis7,
realAPI+workers+recordedclosedM1barsตามprofileเดิม. Preflightตรวจschema/engine metric
SELECT grants/signup/cookieผ่านโดยไม่ส่งtrade ก่อนเริ่มหนึ่งรอบที่เจ้าของอนุมัติ

ผลจริง: **1 failed**, elapsed **282.530s (4m42.530s)** ต่ำกว่าประมาณ5–7นาที
เพราะเริ่มใกล้minutecloseและหยุดที่assertionหลังขายปิด ไม่ได้รันซ้ำ
log `/tmp/f21-strategy-e2e-attempt4.log`, read-only DB audit
`/tmp/f21-attempt4-db-audit.json`, trace/ภาพ `/tmp/f21-attempt4-artifacts/`

สิ่งที่ผ่านassertionก่อนจุดล้ม: actualbrowserconfig/start→RUNNING→freshARM310→BUY355,
ARM260→BUY395, netBTC7.8921+7.0929=14.985, budget2804.5ต่อไม้/count3,
heldTP434.98ไม่เพิ่ม, cashหลังซื้อ4391, basketCLOSED,
cashหลังขาย **10895.4715175**, positionfacts4

จุดล้ม `frontend/e2e/strategy.spec.ts:54`: `metrics.orders` ใช้
`count(*) FROM paper_order_commands` แต่คาด4 จึงได้6
read-only auditหลังหยุดพบ **actualpaper_orders4 = BUY2+SELL2, NEWcommands4+CANCELcommands2**
CANCELทั้งคู่เป็นของentryBUYที่FILLEDแล้ว ผลSUCCEEDEDและkeyตรง
`uuid5(protection_id,'cancel-entry')` ทุกตัว ตามF17cancel-before-exitเดิม
(protections/worker.py process_basketและprocess_groupใช้identityเดียวกัน)
ไม่มีduplicateBUY/SELL, failedcommand0/nonterminaldispatch0, winningtrigger1,
exitguards2, heldquantity0/cost0, realizedPnL **895.4715175**, quote/base reservations0,
ทั้งสองentryremainingquantity0. ค่าเหล่านี้ตรวจจากฐานข้อมูลจริง ไม่ใช้mock/compensatingtrade

ข้อจำกัด: assertionสุดท้ายAPIpositions=[] และภาพclosedไม่ได้รันเพราะหยุดก่อน,
แม้DBยืนยันquantity0; suiteยังเป็น **Failed**, V15 **Incomplete** ไม่แปลงผลย้อนหลังเป็นPassed
ภาพtwoentriesดูactualpin1m/budget2804.5/count2of3/sharedTP434.98ได้ แต่แผงscroll
มีส่วนcontrolsอยู่นอกlocatorภาพ จึงไม่ใช้แทนowner visual acceptance
หยุดcampaignตามขอบเขตหนึ่งรอบที่อนุมัติ ไม่แก้runtimeหรือoracleหลังfailureในรอบนี้

### Concrete next-step proposal (awaiting owner selection)

คงRQ08/no duplicateorders และRQ11/F17executionpolicyเดิมทั้งหมด;
แก้เฉพาะharnessให้วัด **actualordersจากpaper_orders=4**, ตรวจ **NEW4/CANCEL2**
แยกกัน, ตรวจcancel-entryidentityครบทั้งสองและผลterminalSUCCEEDED,
คงexecution4/cash/PnL/flat/reservation assertionsเดิม; ไม่ลบCANCELเพื่อให้ตัวนับผ่าน
แล้วรันเพิ่มหนึ่งรอบบนfreshownedDB ประมาณ5–7นาที หยุดทันทีหากล้ม ไม่retryเอง
การแก้testที่วัดผิดอยู่ในengineeringauthority แต่รอบทดลองใหม่ยังต้องได้รับอนุมัติ
เพราะowner-approved attempt4 กำหนดให้หยุดเมื่อไม่ผ่าน

อีกทางเลือก: คงFailed/Incompleteและพักbrowsercampaignไว้ ตรวจindependentงานอื่นได้
ห้ามใช้evidenceบางส่วนหรือเปลี่ยนexpect6อย่างเดียวเพื่อประกาศfullflowPassed
ไม่เสนอปรับสูตรเงิน/ลดsafety/ข้ามV15: failureนี้เป็นmeasurement bugที่ระบุได้
ไม่มีหลักฐานว่าต้องเปลี่ยนความต้องการผู้ใช้หรือcapacity/SLA

Attempt4 cleanup: ลบ2ownedcontainersและtemporaryrole/keyenvironment fileแล้ว
เก็บaudit/log/trace/ภาพไว้; ไม่commit/push/merge และไม่เปิดproduction/Live

### Owner approval — attempt5

เจ้าของตอบ “approve” ให้แก้measurementตามproposalและรันเพิ่ม **หนึ่งรอบ attempt5**
คง financial oracle/strategy/F17policyเดิม, ประมาณ5–7นาที freshownedDB;
หยุดทันทีหากไม่ผ่าน ไม่retryเอง. ผลattempt1–4คงเดิม ไม่ย้อนเปลี่ยนเป็นPassed
ตรวจactualpaper_orders4/NEW4/CANCEL2แยกกัน พร้อมcancel-entryidentity/terminalresults,
actualPnL895.4715175, zeroheld/cost/reservations, APIpositions[] และwinningtrigger1

### Approved attempt5 — Failed before ARM; no retry

Owner-approved measurement repair implemented only in test-only harness:
actualpaper_orders count, NEW/CANCEL separate, cancel-entryUUID5/terminalresults,
PnL/zeroheld/cost/reservations/winningtrigger assertions. Productionruntime unchanged.
Preflight: **11 metric SELECTs passed under real ENGINE/RLS**, count serialization
and UUID5runtime types passed withoutorders; Ruff/targetedESLint/frontendTypeScriptpassed

Run: `npx playwright test --config=playwright.strategy.config.ts --retries=0
--output=/tmp/f21-attempt5-artifacts`, freshownedPostgreSQL16/Redis7, sameprofile/oracles
**1 failed, test8.1s / total12.953s** (stopped early vs estimate5–7min), no rerun
log `/tmp/f21-strategy-e2e-attempt5.log`, audit `/tmp/f21-attempt5-db-audit.json`,
trace `/tmp/f21-attempt5-artifacts/strategy-real-API-start-fr-010ca--and-shared-actual-TP-exits/trace.zip`

Failure: step1 expectsARM310 but reset_close remainsnull after5s
DB timestamps prove firstfixturecandleended **2026-11-20T16:55:00Z** while bot
eligible_after=**16:55:00.722967Z** (Asia/Bangkok23:55:00 vs23:55:00.723)
START_REQUEST_APPLIED16:55:00.508307Z; RUN_READY event16:55:00.691427Z;
seed250 prepared16:54:59.338626Z; fixtureappendedARMcandle16:55:01.410714Z
Thus candle was alreadyclosed before actualreadiness, and approved backfillguard
correctly declinedARM. Sourcefailure/recovery markerNULL, recovery_requiredfalse,
RUNNING, actualorders0/commands0/positionfacts0; no economic changes occurred

Root cause: fixtureanchorsfirstsignalclose atprepare time beforebrowserstart;
preparecrossedrealminute boundary duringactualstart, so signalbecamebackfill
inthisrun. No runtime policy should allow this staleARM. Attempt4 startedwithenoughtime
and thereforedidnotexercisethisfixtureboundary. Correctedcommand-count oracle has
preflightproof but final6commandcase not reached inattempt5; do not markitPassed
V15 remains**Incomplete/Failed**; previousattempts unchanged; campaignstopped

Next concrete proposal (awaiting owner approval): keepallstrategy/backfill/financial
criteriaandthe5barprofile unchanged; alignfixturepreparation immediatelyaftera real
UTCminuteclose (waitupto60s beforeseed250), givebrowserstartafullminutebeforefirst
signalclose, and checkfirstsignalend>persistedeligible_after beforepublishingit
with explicitfixtureerrorifnot (no retry/backfillARM/timewarp). PrepareHTTPtimeout70s
forrealwait; overalloneadditionalrun5–7min, stopimmediatelyifitfails.
Thisrepairchangesonlyharnessscheduling, notsignalformula/TP/quantity/expectedcash.
Alternative: retainFailed/Incompleteandpausebrowsercampaign; independentapprovedwork
cancontinue. RelaxingbackfillguardoracceptingnullARMisnotrecommended becauseitwould
permitunintendedhistoricaltrades; nofinancial/safetycriterionmaybereducedhere.

Attempt5 cleanup: ลบ2ownedcontainersและtemporaryrole/keyenvironment fileแล้ว
เก็บaudit/log/traceไว้ ไม่commit/push/merge ไม่เปิดproduction/Live

### Owner authorization — finish implementation and review

เจ้าของสั่ง “approve แก้ไขให้จนเสร็จ และแจ้ง review code” หลังattempt5
อนุมัติแก้fixture schedulingตามproposalและทำงานที่เกี่ยวข้องต่อเนื่องถึงcheckpoint:
ตรวจpreflight→actualflow→targeted safety/validationที่ค้าง→Ready for Code Review→review/fix
คงกฎธุรกิจ/financialoracleและประวัติFailedเดิมทั้งหมด ไม่เปิดproduction/Live
เตรียมfixtureหลังrealUTCminutecloseแล้วseed250; ก่อนปล่อยsignalแรกต้องตรวจ
actualRUNNING/eligible_afterและtarget>endของข้อมูลที่ถือว่าbackfill ไม่มีtimewarp/ย้อนARM
คงรอบactualflowใหม่ตามproposalหนึ่งรอบ 5–7นาที และกฎหยุดเมื่อไม่ผ่านตามAGENTS
owneracceptance/finalCIยังเป็นด่านแยก ไม่ถือว่าคำสั่งนี้แทนผลตรวจเหล่านั้น

### Remaining Feature proof selection — before tests

เพิ่มเฉพาะช่องว่าง V11–13 ที่เดิมยังไม่ครอบคลุม: realPG trigger/fanout failure
ก่อนcommitและlostactualCOMMITacknowledgement, กู้ด้วยnewENGINEpoolจากdurableDB
เมื่อราคากลับต่ำกว่าTPโดยไม่มีRedis hints, ตรวจworkidentityไม่ซ้ำและactualledgerผลเดิม
reuseF15drive/runtime, F17process_group และexistingcommit_proxy; injectfaultหลังrealwrites
ไม่mockfinancialresults. เพิ่มnumericreject/unit/roundingboundariesของbasket_take_profit
และmigration crossowner/mode/FK checksที่ยังขาด; ไม่รันfullregressionเป็นพิธี

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

## Latest implementation/review checkpoint — 2026-11-21 (Asia/Bangkok)

**Implementation: Ready for Code Review** แจ้งใน commentary แล้ว และรีวิวต่อทันทีตาม
workflow ไม่รออนุมัติย่อย. **Feature: Partial / Pending Feature Validation**,
owner acceptance และ final-SHA required CI ยังไม่ผ่าน จึงไม่ Completed/พร้อม merge
ผล Failed ทุก attempt ก่อนหน้านี้คงเดิม ไม่ถือว่า approval หรือผลใหม่ลบประวัติเก่า

### หลักฐานใหม่และขอบเขต

- Approved attempt6: **1 passed / total326.448s (5m26.448s)** เทียบประมาณ5–7นาที
  actual API/browser/PG/Paper workers, real closed M1 profileเดิม ไม่มีเวลาเสมือน
  config2804.5ต่อไม้/count3/1m→ARM310/BUY355→ARM260/BUY395→TP434.98คงเดิม
  →closed; NEW4/CANCEL2 แยกกัน, cancel-entry identity/terminal results ถูกต้อง
  executions4, cash4391หลังซื้อ→10895.4715175หลังขาย, realizedPnL895.4715175,
  held/cost/reservations0, winningtrigger1, APIpositions=[] ผ่าน assertion
  log `/tmp/f21-strategy-e2e-attempt6.log`, audit `/tmp/f21-attempt6-db-audit.json`,
  result `/tmp/f21-attempt6-result.json`, ภาพ `/tmp/f21-attempt6-artifacts/`
  บันทึก transient DATABASE_TIMEOUT/protection deferred ใน log ตามจริง; workers retry
  สำเร็จภายใน flow โดยไม่เกิด duplicate order และไม่ต้อง rerun campaign
- `/tmp/f21-recovery-first.xml`: **56 passed / 17.060s** = pure54 + real PG fault2
  ก่อนcommit fanout rollbackครบ และ proxyตัดactualCOMMITackหลังDBcommitจริง
  new ENGINE poolค้นworkจากDBเมื่อราคาลด107→104 ไม่มีRedis hint, identityเดิม,
  trigger1/exits2/positionfacts4, cash/PnLเท่าindependentoracle ไม่มีheld/costค้าง
- `/tmp/f21-lineage-first.xml`: **5 passed / 9.401s**, หลังเพิ่มentry→orderlink run FK
  ครอบfresh schema/roundtrip/history refusal และrun/episode/mode/owner boundaries
  constraintเพิ่มเติมยัง validate กับfactsจริงของ E2Eattempt6 ผ่าน โดยไม่เปลี่ยนข้อมูลเงิน
- `/tmp/f21-trigger-admitted-first.xml`: **1 passed / 7.562s**,
  pending BUY ที่admitแล้วถูกcancelหลังbasketชนะโดยไม่มี BUY fillเพิ่ม
- `/tmp/f21-review-affected.xml`: **12 passed / 17.246s**,
  recovery3 + API/config/status/owner isolation9 บนschemaที่แก้แล้ว
- `/tmp/f21-tick-review-first.xml`: **16 passed / 40.235s**,
  full affected basket13/recovery3 หลังแก้current execution metadata tick;
  tick0.01→1 ใช้งบ100ต่อไม้ ราคา100→90 target106→100ทั้งกลุ่ม
  คงheld-min/FIFO/fee/PnL/atomic retarget/guard/setup-policy tests เดิม
- Frontend wallet refresh: first run **25 passed / 1 failed** เพราะ test cacheตั้งgcTime0
  ทำให้unobserved fixture cacheถูกเก็บก่อนassert; แก้test fixtureเป็นretainedcacheตาม
  production behavior ไม่ลดassertion. Focused second run **10 passed / 1.36s**;
  PaperTradingActivity16กรณีผ่านรอบแรก และ sourceไม่เปลี่ยนจึงreuseผลนั้น
  ตรวจowner-scoped invalidation, ownerอื่นไม่ถูกinvalidate, GET only/no automatic POST
- Local static: backend Ruff/format42 changed Python filesผ่าน; existing27-source mypy
  และ7 import contracts reuseตามscopeเดิม, latest monetary hook files mypy2ผ่าน
  frontend latest typecheck/targeted ESLint/buildผ่าน (build1.88s), existing >500k bundle
  warningคงเดิม. OpenAPI/types exact sync จากcheckpointเดิมไม่ถูกเปลี่ยนหลังจากนั้น
  doc/diff whitespace checkผ่าน ไม่มีการเปลี่ยนcontractแล้วใช้ผลเก่าแทน

### Review findings และการปิด

| Severity | Location | Problem / impact | Fix / evidence |
|---|---|---|---|
| Medium | migration0074 / bot_strategy_entries | order lineage FK เดิมไม่ยืนยันrunตรงกับbasket; programmer errorอาจโยงprojectionผิดrunของownerเดียวกัน | เพิ่ม(command_id,run_id) FK+unique; real cross-run rejection/roundtripผ่าน |
| Medium | e2e_strategy_app / strategy.spec | นับCANCELเป็นออเดอร์ซื้อขาย ทำให้false duplicate finding; fixtureเริ่มใกล้ขอบนาทีทำให้signalกลายเป็นbackfill | แยกactualorders/NEW/CANCEL, เตรียมหลังrealminutecloseและตรวจpersistedready cutoff; attempt6ผ่าน |
| Medium | infra/protections/worker.py / infra/bots/baskets.py | basketตรึงtickจากfillแรก ทำให้candidate roundingใช้metadataเก่าเมื่อtickเปลี่ยน | ส่งcurrent confirmed execution tickให้shared synchronizerทั้งBUY/SELL; affected16 testsผ่าน |
| Medium | frontend/PaperBotPanel.tsx | holdingsแสดงflatก่อนwallet balancerefresh เพราะpollคนละรอบ; ภาพactualflowแสดงcached4391ชั่วคราว | invalidateexistingowner-scoped trade queryเมื่อverifiedpositionsเปลี่ยน; targeted10ผ่าน ไม่มีclient money calculation/POST |

รีวิวครอบ requirements/plan/validation, diff และchanged files รวมcallersของF15/F17/F20:
architecture/import directions; pure strategyแยกsubmission; Money/Quantity/rounding;
RLS/auth/CSRF/error sanitation; transaction owner locks/source fences;
idempotency/duplicate work/corrections; stateless session/config/progress;
partial quantities/fee/PnL; default Paper/Live activation และ UI/template/accessibility
ไม่พบ Critical/High code finding ที่ยังเปิดใน diff ที่ตรวจ
Futures leverage/margin/liquidation ไม่อยู่ใน F21 Spot delta และไม่มีการเปลี่ยนสูตรเหล่านั้น

### Requirements / validation / test coverage และ remaining risks

- RQ01–11 มีimplementationและtargeted proofตามmappingในตาราง; ไม่ใช้ผลDesktop
  หรือtest strategyแทนactualF21. Snapshot/backfill/min250/sourcecorrection/heldTP,
  FIFO และper-entry TP/SLreadonlyมีหลักฐานตรงที่เปลี่ยน
- Validation ที่ยัง Partial ต้องปิดก่อนmerge: V05/full ordering matrix,
  V08/complete timeout/recovery qualification, V10–13/late-fill/restart matrix,
  V15/same-exit-candle→restart→new-basket complete profile และ owner acceptance V14/V17
  หลักฐานใหม่ลดช่องว่างบางส่วน แต่ไม่อ้างว่าmatrixทั้งหมดหรือFeatureผ่านแล้ว
- Testsใหม่เสริมเฉพาะช่องว่าง ไม่รวมจำนวนซ้ำข้ามregressionเป็นยอดunique
  full regression/combined E2E/workloadเป็น V19/V20 Pending Full Validation ตามระยะเดิม
- V18ยังNot Run: ไม่มีcandidate commit/SHA/requiredCI จึงไม่publish/merge;
  localchecksไม่แทนCI และautomatedreviewไม่แทนowneracceptance
- Monetary tick fix ใช้same tickในE2Eprofileเดิม จึงreuseactualflowproofและตรวจdeltaด้วย
  realPGmetadata-change case ไม่รันcampaignเดิมซ้ำโดยไม่มีช่องว่างใหม่
  UIwallet fixไม่มีAPI/engine/ledgerchanges; financialproofเดิมยังใช้ได้
- ไม่มีNeeds Clarificationด้านกฎธุรกิจค้างจากNC-F21-08/09; ไม่มีproduction/Liveactivation

Checkpointนี้ปิดimplementation/review findingsที่ระบุแล้ว ขั้นต่อไปคือปิดFeature validation
ที่ยังPartialและowneracceptanceก่อนfinalCI/publication; ไม่เรียกFeatureCompleted

### Review finding — realtime reconnect between bot polls (before code)

ตรวจset_connectedเดิมพบdisconnect/reconnectใช้FeedLeasegenerationเดิมได้ และwrite_price
ล้างunavailable_sinceหลังreconcile ดังนั้นF21ที่ไม่ทันpollช่วงRECOVERINGอาจไม่เลื่อน
backfillcutoff แม้candledemandยังCOMPLETE. เพิ่มdurablebot_recovery_atบนpricefeed
ด้วยDBtriggerเมื่อconnected/generationเปลี่ยน และprogress.price_recovery_atที่ackเมื่อready
reusecandle recovery marker pattern/DBclock/source fencเดิม ไม่เพิ่มsessionmemory/Redis
ไม่เปลี่ยนF11/F15priceสูตรหรือการเทรด; เพิ่มspecificrealPGquickreconnecttestและsourceinput
regression. เป็นsafety/source-readinessengineeringfixตามอำนาจที่มอบหมาย

### Final affected review checks — 2026-11-21

Realtime recovery finding: **High — fixed**. source reconnect between polls could
leave a historical ARM eligible after reconciliation cleared transient state.
Durable price-feed recovery marker + per-run acknowledgement now invalidate that
candle and establish a new live cutoff; no strategy/financial threshold changed.
`/tmp/f21-realtime-recovery-first.xml`: **12 passed / 19.303s**,
including actual quick disconnect/reconcile, normal source wait, source corrections,
ARM provenance, 249/250 start readiness and fresh/downgrade migration roundtrip.
Updated restored-run fixture pins both source recovery proofs to model an already-ready
run; no assertion or authoritative data-source gate was removed.
Affected source Ruff and mypy3 passed. No repeated financial E2E campaign was run:
healthy feed marker remains stable in that profile; actual start/live-input and recovery
delta are verified against fresh PostgreSQL by the affected tests.

Final review result: reported code findings resolved and targeted checks pass.
No open Critical/High code finding found in the reviewed diff; **pre-merge approval is
not granted** while the explicitly Partial Feature validation/owner acceptance/final CI
items above remain open. Implementation/review checkpoint is ready for owner code review.

Cleanup: removed only the two F21-owned containers and temporary role/sealing-key
environment file; logs/audits/screenshots retained. No commit/push/merge or production/Live activation.

### Deep review remediation checkpoint — 2026-11-21

- **High / Medium, shared TP and setup failure** — a real manual sale leaves 0.005 BTC ARMED alongside a sellable allocation. Both polling orders produce one latched basket trigger and one sibling exit across the price reversal. The small allocation retains its quantity in FAILED and does not stop the bot. A separate ARMING case rejects the setup, preserves the SYSTEM stop and queues no invalid sale. ARMED allocations adopt the durable winner before current sizing; ARMING allocations use the existing F-17 retry deadline and setup policy before adopting it.
- **High, checkpoint isolation** — the shared semantic validator rejects the unzoned reset at decode. In the same worker scan a second owner reaches a committed decision. A malformed run cannot prove recovery until repaired.
- **High, candle recovery proof** — a failure injected at actual F-21 candle evaluation records a candle identity. After the strategy is healthy, the dependency-read and final fencing stages produce a proof while the run remains STOPPED with zero order commands. An explicit resume using the stop/reconciliation revisions then clears the stop.
- **Medium, browser CI** — the required E2E job now bootstraps a separate local database for the strategy suite. The same npm command with Playwright `--list` discovered one strategy flow. No new local browser campaign or hosted candidate-SHA CI run was performed at this checkpoint.
- First affected run (including pure strategy tests) **76 passed**, `/tmp/f21rev-tests.xml`. After consolidating F-17 sizing and adding the two-owner scan and ARMING failure checks, the final affected PostgreSQL suite **29 passed**, `/tmp/f21rev-final.xml`. Counts overlap. Changed-file Ruff/format, source mypy, seven import contracts, frontend typecheck, config ESLint and diff whitespace checks passed.
- Reviewed the amended paths and their callers. All five review findings have local fixes. The outstanding Feature matrix and owner acceptance listed above remain open; V18 awaits required CI on the final candidate. Batch/Release validation remains pending.

Follow-up refactor verified on local PostgreSQL 16. The candle input, basket, and F-20 readiness/recovery suites passed (32 tests, 54.24s; `/tmp/f21-refactor-checks.xml`). Ruff lint/format passed for the three affected Python files, and strict mypy passed for both runtime modules. Existing Feature, owner acceptance and candidate CI gates remain as recorded above.

### Follow-up Feature validation — exit fill and start recovery (before checks)

Reuse the real F-15 matcher, F-17 protection worker, F-20 API process fixture and PostgreSQL lost-COMMIT-reply proxy. Existing fault coverage ends at basket trigger fanout. Exercise a crash on the actual SELL fill transaction, independently verify committed cash/held quantity/remaining target and replay the old claim from a new pool. Delay the sibling SELL until recovery; check exact final facts and the same-candle guard after closure. Exercise F-21 start request timeout on both sides of persistence using the pinned configuration and fresh API process. These checks extend the existing approved Feature criteria without changing financial policy.

For the exit-candle boundary, reuse the existing restored F-11 source fixture with an actual Paper entry/TP sale. From a new ENGINE pool observe two consecutive real 1m closes, both satisfying FIRE after a proven ARM; assert the guard is the decisive predicate on the exit candle and that the next eligible candle creates a distinct basket. This targeted backend case is separate from the prior browser campaign.


### Start timeout and SELL recovery results — 2026-11-21

- V08: isolated HTTP API process terminated while awaiting the start reply, both before and after durable acceptance. A fresh server resolved the pinned configuration and the original start key, persisted one run, and generated zero order commands. Chromium exercised both network-loss cases against the actual API, then reloaded the page. Before persistence it retried with the identical key; after persistence it recovered the existing receipt by GET. The account retained its 10,000 USDT and had zero executions. Existing config/access-control coverage remains applicable. The dedicated browser cases passed 2/2 in 11.0s (`/tmp/f21-reload-browser-2.log`); the first invocation failed at test-file parsing before running a browser case.
- V10–13: forced rollback and lost PostgreSQL COMMIT acknowledgement at the first actual TP SELL fill transaction, then resumed from a fresh ENGINE pool. The old claim was rejected after accounting; before commit, its still-valid claim could finish the rolled-back fill. After the first sale, the second allocation remained 0.999 BTC at TP 106 and cash was 9,898.802099 USDT. After delayed execution of its original SELL, the basket was CLOSED with four execution receipts/facts, four NEW commands, zero position/cost/reservations and realized PnL −2.395802 USDT. A BUY on the exit candle was rejected even with the current guard revision. The two new fill cases passed; the affected API restart and basket recovery modules together passed 8/8 in 26.93s (`/tmp/f21-start-exit-recovery.xml`).
- V13/V15 exit-candle boundary: using a restored F-11 history and a seeded original Paper BUY, the real matcher filled its TP SELL. A new connection pool reloaded the same run; RSI ARM, both later FIRE evaluations and the next BUY used the actual F-21 implementation. On the first real 1m close the signal satisfied every BUY condition except the exit guard (positive control with only that flag toggled). No new BUY command was recorded. On the immediately following eligible closed candle there was exactly one new BUY link, a distinct OPEN basket and an actual fill with a fresh target above the original 106. No added cooldown or synthetic clock advance. Passed in 131.58s (`/tmp/f21-next-basket-3.xml`). Earlier runs failed in fixture setup (protocol fixture ran before database isolation) and the reset polling assertion (Money compared to None); fixed the harness and kept the financial assertions. An earlier command used an incorrect test path and collected no cases.
- This closes the targeted restart/same-candle/new-basket scenario. The first basket in this backend case is seeded at the intent boundary. Use attempt6 for the full initial browser flow. Outstanding ordering, late entry/correction and source-fence matrix cases in V05/V10–13 and full V15 qualification remain Partial. V14/V17 require owner visual acceptance. V18 awaits a final candidate. No application runtime or Live setting changed. Changed test files passed Ruff/format, frontend typecheck/targeted ESLint, affected runtime mypy and diff checks.

### Concurrent BUY/exit and delayed BUY correction — before verification

Use independent PostgreSQL writer sessions and observe the actual lock wait before releasing the first commit. Exercise both orders for a BUY decision versus an actual manual SELL fill, and for an admitted BUY match versus the basket TP observation. Compare confirmed fills, durable exits and net allocations; an accepted but unfilled BUY must be canceled once TP wins. After a basket has closed, replay a price correction to its original BUY, checking wallet, position, realized PnL, reconciliation fences and immutable effect counts. Reuse F-15 matching, F-17 protection and existing correction entry points.

### BUY/exit ordering and delayed fill results — 2026-11-21

- V05/V12: two independent ENGINE sessions proved contention using PostgreSQL's actual blocking PID. With BUY decision first, the decision committed and its queued opening was rejected at admission after the SELL filled. With SELL first, the stale decision rolled back without a BUY link. Both ended with only the original BUY and manual SELL, 0.599 BTC held and cash 9,939.5604 USDT.
- V11/V12: when the second BUY match committed before the TP observation, TP created two exits of 0.999 BTC each. When TP committed first, the already accepted BUY was canceled without a fill and there was one exit of 0.999 BTC. Both retained one winner after the price fell below target.
- V10/V11: genuine partial Paper execution of 0.4 BTC gross, 0.3996 BTC net, generated by an intent from typed strategy signal fixtures. The Paper matcher and protection worker sold the net amount and closed the basket before strategy feedback was consumed. The engine delivered ACCEPTED, FILL and EXPIRED from durable facts, cleared the reset/pending identity, and exhausted available feedback. One basket, two orders, flat holdings and cash 9,999.5208396 USDT. This covers delayed notification of a committed fill, separately from ordering at match time.
- V10/V12: correcting the original BUY cost from 100 to 80 USDT after the TP sale retained the closed basket, marked the basket and run for reconciliation, and yielded realized PnL 18.802099 USDT, zero remaining quantity/cost and cash 10,018.802099 USDT. Replaying the exact correction left one correction event and one exit.
- Evidence on local PostgreSQL 16: initial five new cases passed (`/tmp/f21-buy-exit-1.xml`). Expanded run 21 passed / one failed in the new test fixture before matching because its episode ID used a driver UUID subclass (`/tmp/f21-buy-exit-2.xml`). Converted the fixture value to the strict domain UUID, drained the real entry-cancel command before recovery and checked the persisted pre-feedback state. Focused rerun passed (`/tmp/f21-buy-feedback-2.xml`). This covers six new cases and sixteen existing basket cases. Targeted Ruff, format, mypy on four affected runtime dependencies and diff whitespace checks passed. Changes are confined to tests and validation evidence.
- This closes the specific BUY/exit ordering and delayed BUY/correction scenarios above. Remaining Feature matrix (including prepare/commit source, catalog, risk and worker authority changes), owner visual acceptance and required CI still gate merge.

### V05 follow-up — decisions in flight

Exercise a genuine armed BUY through the worker. Before its final transaction reads the database, commit a new quote, a catalog withdrawal, a reduced but still admissible risk limit, or a lease takeover in another session. Compare each case with unchanged input, including the financial rows and strategy checkpoint. Use a freshly evaluated BUY to verify recovery after a compatible revision change.


- Baseline on PostgreSQL 16: four of five cases passed. A DECREASE from 1,000 to 500 USDT returned an applied revision 2, yet the worker persisted the revision-1 BUY (see `/tmp/f21-buy-fences-first.xml`).
- After pinning the risk revision on F-21 candle evaluation, all six cases passed, including a correction of the published candle. Each test observed a real BUY intent before the interleaving. Stale attempts left zero decisions, order links, commands, orders, reservations, position events and baskets. Wallet balance, wallet revision and strategy checkpoint were preserved. The corrected source paused the run. With unchanged inputs or after a fresh evaluation against a compatible quote or risk update, replay retained one decision and one order command.
- The six cases plus existing indicator and corrected-arm regressions passed (10 total, `/tmp/f21-buy-fences-final.xml`). V05 remains Partial for the rest of its authority and execution matrix. Required CI and owner visual acceptance remain pending.
- A final targeted rerun passed with the replacement quote pinned to the original exchange timestamp and a higher trade ID, so a minute boundary cannot accidentally move the recovery signal to another candle (`/tmp/f21-buy-fences-quote.xml`). Ruff lint/format, mypy on the changed runtime module, and whitespace checks passed.

### V05 — indicator authority, run revision and STOP before commit

Reuse the armed BUY and separate committed writer in test_strategy_commit_fences. Replace the ready generation with equivalent candle data, publish a newer numeric failure, change the rollout epoch, pause the run or submit a user STOP. Check each stale attempt against the original strategy checkpoint, wallet and empty order/position tables. Preserve the unchanged-input positive control.


- Baseline on PostgreSQL 16 (`/tmp/f21-authority-before.xml`): 4 of 6 passed. The old BUY committed after a replacement READY generation and after a newer numeric failure with a retained old head. The original source proof still validated in the replacement case. The unchanged control, rollout epoch, paused run revision and user STOP behaved as expected.
- Final targeted worker suite: 19 passed (`/tmp/f21-authority-after.xml`). In all five new interleavings the evaluated BUY produced no decision, command, order, reservation, position event or basket, and preserved the strategy checkpoint and wallet. A fresh evaluation after equivalent generation replacement created one linked BUY, including after replay. Rollout epoch and retained numeric failure metadata were isolated database fixtures; run pause and STOP used the existing application entry points.
- Three authenticated prepared-reader regressions passed against PostgreSQL and isolated Redis, including a real builder numeric failure, expired failed manifest and signed cursor continuation (`/tmp/f21-authority-reader.xml`). Targeted Ruff lint/format, mypy and whitespace checks passed. The next V05 checkpoint covers authority changes after decision commit and before queued BUY execution. Owner visual acceptance and required CI remain pending.

### V05 — committed BUY awaiting Paper execution

Use the strategy worker to commit a real BUY, then change authority in a separate transaction and drive the existing Paper command. Compare equivalent ready-generation replacement, a numeric failure, candle correction, rollout change, lease loss, run pause, risk revision, STOP and catalog removal against an unchanged command. Check the durable result and actual orders, reservations, wallet and position events.

- Baseline on PostgreSQL 16: 6 of 11 queued cases passed. The Paper worker accepted the stale command after a corrected candle, a risk DECREASE, generation replacement, newer numeric failure or rollout-epoch change (`/tmp/f21-queue-before.xml`). Persisting the original decision proof and checking it at initial admission made the first 22 decision/queue cases pass (`/tmp/f21-queue-after.xml`).
- Initial ledger/replay matrix: 17/17 passed (`/tmp/f21-queue-ledger.xml`). Unchanged inputs, an ordinary subsequent trade, and a valid checkpoint suffix each produced one filled order and one position event; wallet cash decreased by the actual position cost. Candle and suffix corrections, source/feed outage followed by recovery, catalog withdrawal, changed risk revision, worker takeover, expired lease, replaced generation, superseding numeric failure, rollout change, paused run, STOP and legacy decisions lacking proof all ended in terminal rejection. None created an order, reservation or position event, or changed the wallet balance or revision after enqueue. A second worker could not claim terminal work. After a risk rejection, the strategy consumed the rejection; delayed delivery of the previous evaluated BUY and replay of the signal candle preserved a single command. The pure rejected-entry regression also checks an older eligible candle leaves the checkpoint unchanged.
- Affected financial, restart, exit ordering and indicator suites passed (61/61 on the first fix, including the real 1m pool restart, `/tmp/f21-queue-regression.xml`). After adding source/feed recovery checks the focused run had 31 passes and one fixture setup error because the shared F-20 database had not been migrated (`/tmp/f21-queue-final.xml`). After migrating the disposable database, the unlinked BOT regression and authenticated indicator API freshness/continuation checks passed 5/5 (`/tmp/f21-queue-reader.xml`).
- The extra ledger/retry assertions initially queried status on the immutable order instead of its projection and compared the wallet against its revision before enqueue (`/tmp/f21-queue-replay.xml`). Paper command insertion advances wallet revision. The 17/17 result above checks the order projection, compares wallet state against a snapshot after enqueue, and retains the terminal, cash and position assertions.
- Both decision and queue tests use independent committed PostgreSQL transactions. Corrected-candle and ready-head fixtures, rollout epoch and retained numeric failure are controlled database mutations; the Paper matcher, risk request, STOP and registry use application entry points. Tests use an isolated Paper account. Existing V10–V13 financial/recovery matrices, owner visual acceptance and required CI have separate status.
- Final candidate queue matrix passed 18/18 (`/tmp/f21-queue-final-clock.xml`), including a live lease expiring during a deliberately delayed source read under PostgreSQL's clock. The read confirmed the lease was initially live; the command was terminally rejected before any financial effect. The affected real-candle restart and both BUY/SELL transaction orders also passed 3/3 after adding the source recovery checks (`/tmp/f21-queue-restart.xml`). Targeted Ruff lint/format (11 files), mypy (4 runtime modules), 7 import contracts and diff whitespace checks passed. This closes V05 locally. V12 still requires its separate fill-versus-risk/catalog/takeover race evidence.

### Final Feature qualification

Close remaining V12 evidence with actual accepted BUY matching versus a loss-limit latch or worker takeover, using the existing PostgreSQL blocking-PID barrier in both commit orders. Reuse completed browser, restart, feedback, FIFO and protection evidence when its contract is unchanged. Review the final affected diff and reconcile each outstanding Feature row with named evidence before preparing owner acceptance and CI.

Final review of V11's late-fill condition uses both financial commit orders: an actual BUY fill committed first is included in the single basket trigger and exit fanout; if TP committed first the admitted entry is canceled without a second fill. Delayed delivery of the already committed BUY fill is covered after TP closure. These are the supported Paper execution paths under the shared owner lock. Combined with trigger/fanout rollback and lost-ack recovery, these cases cover the late-fill criterion without manufacturing a financial fact after cancellation.

- V12 final ordering matrix uses two independent sessions and pg_blocking_pids, with real risk DECREASE and catalog-removal entry points. A second accepted BUY versus risk latch, catalog withdrawal or worker takeover passed all six commit orders (`/tmp/f21-final-race-verified.xml`). Match-first preserved two fills, 1.998 BTC and cash 9,800 USDT. Authority-first preserved the original fill, 0.999 BTC and cash 9,900 USDT. Costs were respectively 200 and 100 USDT. The fixture deducts fees in BTC. An initial test query incorrectly assumed order_id existed on position events; it was corrected to count the isolated account's actual facts. Additional ledger assertions initially assumed quote fees; the verified assertions use the documented base-asset fee. Earlier failed runs are retained in /tmp/f21-final-races.xml and /tmp/f21-final-race-money.xml.
- Final local static checks passed for all backend source Ruff and strict mypy (282 modules). Frontend typecheck and ESLint passed, 42 files / 718 component tests passed, and Vite build passed. Vitest printed React act warnings and Vite reported its existing large-chunk advisory; neither command failed. Seven import contracts remain kept.
- Closure review of the new race fixture and callers found no new runtime finding. The only source changes in this final checkpoint are test assertions and the barrier's ability to use the API role for catalog removal.

### Owner screen and CI handoff

Owner acceptance is still required for V14/V17. Review the Paper Spot bot settings and active run in Thai and English, light and dark themes, and 375/768/1280/1440 widths. Verify positive per-entry budget, max entries 1–10, immutable pair/timeframe/config after start, actual entry count and shared TP, rejection of per-entry TP/SL edits, stop state and no holdings after the shared exit. Existing screenshots from browser attempt6 are historical flow evidence. Their wallet display predates the tested wallet-cache fix, so use the current UI for wallet acceptance.

Required CI is V18 on the eventual final commit. The workflow already includes the isolated F-21 Paper strategy browser suite. This checkpoint prepares local evidence for owner acceptance and CI; publication and merge remain subject to the owner gate in AGENTS.md. Batch V19 and Release V20 retain Pending Full Validation.


- The final affected Feature suite passed **110/110**, zero skipped, on PostgreSQL 16 (`/tmp/f21-ready-feature.xml`). It includes pure strategy, real account basket/fee/PnL, all commit and queue authority cases, candle/tail inputs, recovery, exit ordering and database boundaries. The final additional six race financial assertions passed separately as recorded above. Source runtime was unchanged during this run. No new review finding remains in the affected final diff.
- Current checkpoint is **Ready for owner visual acceptance and required CI preparation**. V01–V13, V15 and V16 have local evidence. V14/V17 still require the owner's current-screen acceptance and V18 requires final-SHA CI. V19/V20 remain Pending Full Validation.

### Owner preview chart data correction — 2026-11-21

The initial owner-preview environment omitted the frontend chart flag. After enabling it, its strategy test harness still supplied no chart history. A temporary repeating synthetic price fixture was then loaded at 110–121 USDT with exaggerated wicks. This produced the owner's incorrect repeating BTC graph. The earlier claim that a READY response established chart correctness was insufficient. Those sample-chart screenshots are not owner acceptance evidence.

The owner preview now uses the production API and public Binance TH market-data composition instead of the strategy harness publisher. Both synthetic publishers were stopped. The owned test database contained zero bot runs and zero position events before removing its generated market history and previews. The real collector initially encountered missing historical partitions during calendar ingestion (TT012). The isolated database's history partitions were provisioned under the existing maintenance scope, and public collection resumed. This is local preview provisioning; no repository runtime change was made.

Current verification compares closed OHLCV values from the authenticated chart API with Binance TH public klines, inspects the rendered browser chart, and checks database OHLC constraints and absence of the old 100–131 USDT sample rows. The account and 10,000 USDT Paper wallet were retained. The current owner screen must be used for acceptance.

### Compact F-21 main-panel stop action — owner request, 2026-11-21

Server-confirmed F-21 pending/active runs render compact status and the existing stop action on the main Paper Spot page. The expanded settings, holdings and detail summary are hidden in that presentation. Full legacy/Live status callers retain their view. Unknown-start recovery remains available until the server confirms receipt. A confirmed run resolves the original start receipt by GET before clearing its draft identity, preserving subsequent replacement behavior.

Targeted component tests cover pending/running/paused/stopped compact states and the existing stop POST with an idempotency key. Existing stop lost-response, replay, scope and start recovery tests are reused. The actual-browser presentation check intercepts only the bot status response for a pending scenario and verifies the main stop button and hidden budget field; it does not assert execution. The long strategy campaign is not repeated for this presentation change. Its timeout assertions were updated for automatic recovery of already committed starts. Required CI and owner acceptance remain pending.

Owner clarified same-screen placement. PaperBotPanel now keeps one section and one action group, swapping Start for the compact Stop control there. A regression clicks the real component Start handler, receives a pending server response, and verifies the same action group contains Stop while the URL is unchanged. The affected component/stop suites passed 35/35, TypeScript and targeted ESLint passed, and diff checks passed. Owner visual acceptance remains pending.

The latest owner screenshot clarified that the settings sidebar itself must disappear after start. The main PaperTradePage now reads the shared server bot-status query and renders the stop action in TradingWorkspace's chart header. The sidebar stays mounted but hidden for receipt recovery, and the chart grid expands to one column. Component coverage confirms Stop is inside the chart header and outside the hidden sidebar. Four affected suites passed 78/78, TypeScript and targeted ESLint passed. Browser presentation fixtures confirmed header placement and sidebar collapse at 1440 and 375 widths, with screenshots /tmp/f21-stop-chart-header.png and /tmp/f21-stop-chart-header-mobile.png. The browser used an intercepted pending-status response solely for this layout check. Owner acceptance and required CI remain pending.

The owner explicitly selected the order-entry form card. The final layout therefore retains that right-side card and pinned form fields, replaces its Start action with Stop, and removes the expanded run detail. Header/order-list actions and the temporary collapsed-sidebar layout were removed. Four affected suites passed 78/78 with TypeScript, targeted ESLint and diff checks. The placement regression initially held a DOM element detached by StrictMode/pair-scope remount; it now asserts the current rendered control. Browser fixtures confirmed the stop button is inside the visible order-entry card, pinned input is disabled and the chart header has no stop button, at desktop/mobile widths (/tmp/f21-stop-order-entry.png, /tmp/f21-stop-order-entry-mobile.png). Browser bot status was intercepted for this layout verification. Owner acceptance and required CI remain pending.

### Start action after Stop — 2026-11-21

STOPPED/RETIRED F-21 runs now display Start instead of the active stop action. Replacement acknowledgement, risk/flatness proof and can_start remain enforced. The stopped F-21 summary omits its duplicate stop control. The start journal also resolves a terminal receipt when there is no run, so a rejected queued start cannot leave the UI stuck on recovery. Tests cover stopped-but-not-ready Start, replacement acknowledgement and terminal rejected receipt cleanup; the three affected suites passed 72/72 with TypeScript, targeted ESLint and diff checks.

The owner-preview bot task had been called without its required cursor argument and never consumed the pending request. Corrected the local launcher and started the cursor-aware worker. The existing pending request then resolved as BOT_NOT_READY under the existing USER STOP, with no run or trade created. A browser check against the actual preview confirmed Start is visible again. This preview-runner failure was separate from the application UI condition. Required CI/owner acceptance remain pending.

### Start refusal explained and stop recovery exposed — 2026-11-21

The preview's terminal start receipts reported BOT_NOT_READY. Authenticated browser inspection confirmed USER STOP, progress STOPPED and resume_ready=true with no bot run. PaperBotPanel now reads the existing shared stop status, explains that the account remains stopped, disables ordinary start and opens the existing StopSummaryModal from the order-entry card. The owner can review and explicitly resume through the existing proof-checked flow. Known readiness/risk/pair start failures have specific messages; unknown failures retain the sanitized fallback. The replacement proof path remains intact. Three suites passed 73/73 plus typecheck/targeted ESLint/diff checks. The initial affected run failed only a test allowlist that omitted the newly reused read-only kill-switch GET; it was updated without relaxing the no-POST assertion. Actual-browser verification opened the stop summary with resume readiness confirmed; no automatic resume or trade was submitted. Owner acceptance and required CI remain pending.

### Owner preview Paper activation readiness — 2026-11-21

Two starts failed BOT_RISK_UNAVAILABLE. The isolated preview had a 1,000 USDT limit, no latch, zero loss and a READY evaluation, but all three risk protocol switches and protection protocol enabled were false after the prior test harness shut down. Re-enabled the existing switches only in the owned tiewtrade_e2e_owner database and corrected the local preview launcher to preserve market history and these local settings on restart. No source code or financial limit changed. Authenticated API verification returned risk reason READY, amount 1000, loss 0, latched false and a current price watermark. Zero position events existed. No new bot start or trade was submitted by this diagnostic. The separate trade admission response still reported MANUAL_USE_REQUIRED (this account uses BOT) and ORDER_BOOK_UNAVAILABLE; it is not evidence of executable order-book readiness. Owner acceptance and required CI remain pending.

### Short stop notice below the button — owner request, 2026-11-21

Confirmed STOPPED now shows a short notice immediately below Start instead of the expanded snapshot/run/holdings summary or pinned-settings alert. Flat verified exposure says “บอทหยุดแล้ว”; remaining or unverified exposure uses a short corresponding notice. The existing explicit stop-summary/resume action remains accessible when needed. Tests verify the three exposure states, notice position and absence of the expanded summary. Three affected suites passed 75/75 plus TypeScript, targeted ESLint and diff checks. A browser with a STOPPED status presentation fixture verified the notice below Start and no expanded holdings summary (/tmp/f21-stop-short-notice.png). Owner acceptance and required CI remain pending.

### Remove replacement confirmation option — owner request, 2026-11-21

Removed the checkbox and its local acknowledgement state. Start now directly journals and submits the current replacement proof supplied by the server. Backend flatness, reconciliation and stale-proof checks remain in place. Removed the unused F-21 Checkbox component and unused confirmation translations. The replacement regression confirms there is no checkbox, direct Start becomes enabled with valid settings and the updated proof is sent after a status refresh. Its first two runs clicked before React Query delivered its batched replacement update; the test now awaits the actual refetch inside act before clicking. Three affected suites passed 75/75, TypeScript, targeted ESLint and diff checks passed. Owner acceptance and required CI remain pending.

### Hidden/dead presentation refactor — 2026-11-21

Removed the redundant Paper updating text hidden with sr-only, the obsolete showControls option and its contradictory caller predicate. F-21 no longer reaches the expanded status view; legacy nonconfigured runs and Live retain their active full-view callers. Consolidated the duplicated aria-describedby predicate as noticeDescription. No removed RSI/confirmation/stopped translations or controls remain. Background manual request tracking remains active and is not dead UI.

Three affected suites passed 75/75, TypeScript, targeted ESLint and diff checks passed. The initial run exposed two expected test dependencies: legacy status rendering and the removed hidden updating text. Kept the active legacy caller and updated refresh synchronization to wait for the actual in-flight request, preserving balance-node, disabled SELL and no-POST assertions. The shared Live view, error/retry paths and financial request handling retain their existing behavior. Required CI and owner acceptance remain pending.

### Reload notice flicker — 2026-11-21

The idle settings notice previously rendered before bot status loaded, then disappeared when the actual run was active or stopped. Require successful bot and stop status before displaying that notice or deriving the stop-block warning, and keep Start disabled during those reads. Delayed-response tests cover RUNNING and STOPPED, including stop status arriving first. Three affected suites passed 77/77 plus TypeScript, targeted ESLint and diff checks. Chromium navigation and page reload with a deliberately delayed status response both displayed no transient idle notice (/tmp/f21-reload-notice-browser.log). Browser status was intercepted for this loading scenario. Required CI and owner acceptance remain pending.

### Frontend reload-state audit — 2026-11-21 (Feature)

Scope: all frontend TSX renderers and their async hooks, focusing on initial unknown state
versus confirmed empty/denied/unavailable state. Before fixes: confirmed premature copy
in stop settings, platform stop counts, activity pagination and shared workspace price.
Pending: deferred GET regressions for stop/no-stop/failure, platform nonzero counts/error,
initial activity versus actual next page, unknown versus known price; relevant existing
frontend tests, lint/type checks and affected-diff review. Auth and PaperBotPanel delayed
reload evidence above remains applicable. Owner acceptance and required CI remain pending.

Results for the frontend reload-state audit: local Passed. Reviewed all 47 TSX
renderers, including auth/session shell and navigation, credentials/TOTP/account/wallet,
risk and stop summaries/effects, supported symbols, chart and Paper/Live workspace,
bot status, manual request recovery, activity/orders and shared UI primitives. Existing
authoritative empty/loading gates were retained in the unaffected panels; static Live
capability and chart placeholder text are intentional, not inferred read failures.
Four additional presentation issues fixed as planned. No changes to persistent session
storage or business state; QueryClient remains a per-identity presentation cache, with
server reads retaining authority. No new infrastructure.

- Targeted existing activity/orders/trade/stop suites: 78/78; platform delayed success
  and failed-read cases: 2/2. Regressions cover no-stop, existing-stop and failed-stop
  reads; initial orders versus real pagination; unknown price after changing pair.
- Final full frontend Vitest: 43 files, 739/739 Passed, 20.18s.
  Evidence: `/tmp/f21-ui-audit-all.log`.
- ESLint and TypeScript: Passed. Evidence: `/tmp/f21-ui-audit-lint.log`,
  `/tmp/f21-ui-audit-typecheck.log`. `git diff --check` Passed.
- Chromium on local preview: delayed real GET responses for Paper/Live stop status
  and Paper orders, observing visible DOM mutations while reads were held. No premature
  no-stop/pagination/login notices. No trading mutation submitted.
  Evidence: `/tmp/f21-ui-reload-browser.log`. First diagnostic teardown encountered
  an in-flight route closure; fixed diagnostic cleanup with unrouteAll and reran Passed.
- Affected render conditions/callers reviewed: no duplicate queries, changed mutation
  guards, new session authority, swallowed errors or financial calculations introduced.
  The platform now reports failed status reads explicitly instead of fabricated zeros.

Owner visual acceptance and required CI on the final candidate remain Pending; these
local checks do not replace either gate. No backend behavior changed in this audit.

Final static-check follow-up: initial ESLint run identified require-await in three
new deferred-response tests. Explicitly flush their async resolution using the existing
act pattern, then rerun affected three suites: 28/28 Passed
(`/tmp/f21-ui-audit-tests-final.log`). ESLint and TypeScript reruns Passed. Runtime
source is unchanged since the 739/739 full-suite and Chromium evidence above.

### Remove standalone chart — 2026-11-21 (Feature)

Pending: no chart link at desktop/mobile widths; /chart redirects to Paper only after
authentication; no standalone component/placeholders/styles left; existing Paper/Live
chart, timeframe/reset/price and rendering tests retained. Navigation auth/admin/history
regressions, frontend lint/typecheck and browser confirmation. Required CI and owner
acceptance remain pending.

Removal checkpoint: local Passed. Standalone route, menu, layout branches, placeholder
components/translations, chart-only asset/styles and unused frontend menu flag removed.
Chart data/renderer and financial/trading paths retained. Full frontend: 43 files,
736/736 Passed, 28.85s (`/tmp/f21-chart-removal-all.log`). Four retired standalone-only
tests removed (pair selector, placeholder order/history and standalone layout); added
legacy-flag/retired-route coverage; retained chart numeric/rendering/paging tests.
Initial targeted run failed three retired-UI assertions, updated for the explicitly
removed UI, and the chart rerun Passed 25/25. Final minor cleanup removes an unused
translation export and updates the standard-layout assertion to the retained trade class.

Lint/typecheck and production build Passed; build retains its >500kB bundle warning.
Chromium Passed on real local preview: /chart?from=bookmark resolves to Paper, no
standalone menu/page/placeholders; actual Paper OHLC/canvas visible, timeframe/reset
retained, Paper/Live charts mount, desktop1440/mobile375 have no horizontal overflow.
Evidence `/tmp/f21-chart-menu-browser.log`, screenshots `/tmp/f21-chart-menu-removed-1440.png`
and `/tmp/f21-chart-menu-removed-375.png` (desktop inspected). No trading mutations submitted.

Affected E2E selectors/default routes migrated to retained Paper/Live charts. Chart
workload now targets Live workspace (execution remains unavailable) instead of removed
standalone route; previous workload measurements are not a result for the new harness.
Full E2E/workload Not Run in this checkpoint. A listing attempt was rejected by the
existing E2E_DATABASE_REJECTED environment guard before starting any server; guard
retained, no database configuration bypassed. Required CI and owner acceptance Pending.
Affected diff/caller review found no added order/financial/session persistence changes.

### Review fixes checkpoint — 2026-11-21

High: entry-price rounding before basket weighting reproduced52.99 versus exact53.00
(200/3 and100/3, ATR1/tick0.01, held69.66). V06 requires new evidence; earlier passed
cases remain historical, not proof of this boundary. Medium: status outage hides card
Stop; initial status/stop/catalogue failures silently disable Start. Owner requested fixes.
Pending: exact-cost oracle and invalid/unit/net-quantity/held tests; actual PG matcher
regression and affected basket/protection races; frontend outage/recovery/Stop regression;
related lint/types/contracts, affected review. No UI or runtime changes made before this
amendment. Owner acceptance and required CI remain pending.

Diagnostic setup follow-up: first PG invocation stopped in setup because the local
container admin password differs from CI. Read the owned container configuration into
the runner's environment (no credential changes). Initial new matcher case then failed
because its replaced book omitted proof that consumed old levels were empty. Retain
explicit zero-quantity old levels in the controlled fixture, keeping coverage guards
unchanged. Neither failure is recorded as a passed safety case.

Matcher oracle correction before third new-case run: the multi-price arithmetic and
fee/net quantities passed, but the test expected CANCELED after trying to cancel the
remainder of a Market IOC order that had already EXPIRED. Require EXPIRED explicitly,
remove the redundant cancel command, and keep the target/quantity assertions. This
preserves the production matching policy and does not weaken the arithmetic oracle.

Final review-fix checkpoint (local): all three findings addressed.

- V06 new boundary: use persisted gross cost ratios through weighting by remaining
  net quantities, round once to tick. Numeric oracle53.00 now passes, plus net base-fee,
  partial reduction, invalid costs and held-min cases. Existing held targets are never
  raised retroactively. All60 pure strategy/disposal/target tests Passed
  (`/tmp/f21-review-fixes-strategies.log`).
- Actual PostgreSQL matcher proves multi-price entries:100/3 and50/3, net2.997 each,
  ATR1/tick0.01 → shared28.00 on both allocations. Market IOC partial remainder is
  explicitly EXPIRED. Basket/race/recovery suite34/34 Passed after fixture corrections
  (`/tmp/f21-review-fixes-pg.log`). Every test uses existing scratch DB isolation;
  preview account data not used as test fixtures.
- UI targeted suites84/84 Passed; PaperBotPanel25/25 rerun after TypeScript test-option
  correction. Cases prove Stop POST remains available after RUNNING→status failure,
  no stale RUNNING claim/raw error, and each status/stop/catalogue failure can retry
  without automatic start. Logs `/tmp/f21-review-fixes-frontend.log`,
  `/tmp/f21-review-fixes-ui-final.log`. No whole frontend rerun needed after test-only
  option removal; runtime source unchanged from84/84.
- Ruff/format, source plus affected-test mypy284 files, ESLint, TypeScript and7 import
  contracts Passed. Initial mypy invocation exposed affected-test typing gaps and
  integer power Any inference; corrected using existing Money coefficient scale and
  annotations/narrowing. Selecting only a test module without src also produced
  installed-package/stub noise; final invocation includes src and retains strict rules.
  Evidence `/tmp/f21-review-fixes-{ruff,mypy-all,eslint,tsc,imports}.log`.
- Focused review covered exact ratio scale/units/held policy, fill caller and transaction
  boundaries, stale status without stale authority, shared query identities and retry
  guards, React checklist and stateless rules. No new finding identified in the fixed
  diff. No new migration, session authority, infra, API contract or Live activation.

PG preparation/fixture correction took longer than the original2–4minute estimate;
the final34-case run completed before12:07 Asia/Bangkok. Earlier setup/oracle failures
remain recorded above; the passed result belongs to the corrected final scenario.
Owner visual acceptance and final-SHA required CI remain Pending. Batch/Release status
unchanged. This checkpoint fixes F-21; it does not approve/implement Paper Test Entry.
