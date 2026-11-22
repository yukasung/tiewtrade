# Paper Test Entry — Validation

สถานะ: **Approved — เจ้าของเลือกเริ่ม implement ตาม plan/validation วันที่ 2026-11-21**
วันที่: 2026-11-21 (Asia/Bangkok)
ฐาน: requirements Approved; partial-fill first anchor เจ้าของยืนยันแล้ว

## เกณฑ์ตรวจรับ

ผลทุกข้อเริ่ม Not Run ไม่มีการใช้ผล F-21/RSI ที่ผ่านมาแทนพฤติกรรมกลยุทธ์ใหม่
ใช้หลักฐานเดิมได้เฉพาะส่วนที่ไม่ได้รับผลกระทบ ระบุ candidate และขอบเขตให้ชัด

| # | เกณฑ์/requirements | วิธีตรวจ | ระยะ | ผล |
|---|---|---|---|---|
| V01 | CLOSED green trigger; RQ01–03 | independent cases green/red/doji/open/unconfirmed, exact equality, wrong pair/timeframe, missing/zero/invalid ATR, stale/gap/warm-up unready; ไม่ใช้ RSI/EMA เป็น entry filter | Feature | Passed — targeted evidence |
| V02 | Pure/deterministic config/state; RQ02/03/07/12 | same input/config/stateได้ผลเดิม, exact codec/version/units, invalid capital/timeframe/unknown max_entries rejected, immutable pin/restart resolution | Feature | Passed — targeted evidence |
| V03 | One position and in-flight guard; RQ06/08 | real PG: pending BUY ก่อน fill, partial/full BUY, rejected/canceled/no-fill, partial SELL/residual, pending/unknown SELL, triggered exit; ไม่มี BUY ใหม่จน exposure และ work เดิมสิ้นสุด | Feature | Passed — targeted evidence |
| V04 | No duplicate/replay/re-entry; RQ08/12 | duplicate/reordered candle/quote/feedback, same candle retryหลังปิดposition, new worker takeover, two instances and lost response; one candleไม่สร้างentryซ้ำ และ next eligible candleเท่านั้นที่เริ่มรอบใหม่ได้ | Feature | Passed — targeted evidence |
| V05 | First-fill numeric oracle; RQ04/05/11 | ตัวอย่างเฉพาะ test: signalATR2, fillแรก100 → TP106/SL94ก่อนกฎ tick; fillต่อมา110/ATRใหม่5 ต้องยัง106/94; verify tick boundaries, exact units, overflow, SL<=0, targets equal/crossed current price ใช้policyเดิม | Feature | Passed — targeted evidence |
| V06 | Atomic anchor/protection; RQ05/10–12 | real PG actual matcher/ledger: faultก่อน/หลังanchor insert/protection setup/commit, rollback+replay, duplicate executionและconcurrent first fills; anchorหนึ่งชุด ไม่มี unprotected silent fill/duplicateledger/oversell | Feature | Passed — targeted evidence |
| V07 | Real TP and SL flow; RQ04/05/10 | actual API + Paper worker สองscenarioแยก: green→BUY→TPexit และ green→BUY→SLexit; verify real quantities/fees/PnL/position/balances ไม่ถือreceiptเป็นfill | Feature | Passed — targeted evidence |
| V08 | Partial/late fills and reduction; RQ05/06/10 | first fill→next fillต่างราคา anchorเดิม, triggerก่อนlate fill, canceled entry remainder, manualpartialSELL, protectioncancel/setupfailure; quantity/exit policyเดิม ไม่มีretargetหรือเปิดentryใหม่จากpartialreduction | Feature | Passed — targeted evidence |
| V09 | Admission/STOP/risk/source fences; RQ03/08–10 | real PG racesระหว่างevaluate/commit/queuedexecutionกับSTOP/risk/catalog/wallet/source/lease changes; targets/updateเก่าไม่หลุดguards ไม่ bypass safetyเพื่อเร่งเข้า | Feature | Passed — targeted evidence |
| V10 | Test-only gate/auth/isolation; RQ09/12 | default production catalogue/configure/startไม่อนุญาต, Live ปฏิเสธ, direct API gate check, unauth/CSRF/crossowner/ref/tamperedversion, gate/API/engine mismatch safely blocked; no real exchange orders | Feature | Passed — targeted evidence |
| V11 | Stateless/recovery/idempotency; RQ08/12 | new API and engine process/DB pools, durablejournal lookup, restartหลังfirstfill/exit, no Redis/process-memory authority; exactsamekey conflict checksรวมstrategyidentity ไม่มีmixedRSIconfig | Feature | Passed — targeted evidence |
| V12 | DB schema/security (ถ้ามีmigration); RQ11/12 | fresh/upgrade/rollback safety, FORCE RLS/FK/check/unique, runtimegrants, crossowner/episode/mode rejected; ไม่ใช้mockพิสูจน์transactions | Feature | Passed — targeted evidence |
| V13 | UI owner flow; RQ02/06/07/13 | selectteststrategy→pair/timeframe/money→start→stop→reload, pinnedconfig, no maxentries input, strategynameชัด, no transientlogin/readiness/empty warnings; desktop/mobile/template/lightdark/locale/keyboard; ownerตรวจภาพจริง | Feature | Partial — owner acceptance pending |
| V14 | Regression/contracts/static | targeted F-17 absolute/manual TP/SL, F-20 lifecycle, F-21 RSI/basket config/TP unchanged; OpenAPI/types exact sync; backendruff/format/mypy/importcontracts, frontendlint/typecheck/build, gitdiffcheckตามผลกระทบ | Feature | Passed — targeted evidence |
| V15 | Review/fixes/owner acceptance | ReadyforCodeReview→diff/callers/financial/security/stateless/concurrency review→fix/refactorเท่าที่จำเป็น→affectedtests; owneracceptanceไม่แทนด้วยautomatedreview | Feature | Partial — owner acceptance pending |
| V16 | Final candidate/required CI | required CI/security/contracts/freshstateตามconfigจริงบนfinalSHA/PRhead; localchecksไม่แทนCI; ไม่mergeก่อนFeatureครบ | Feature | Not Run |
| V17 | Combined cross-feature regression | รวม bot/strategy/protection/risk/STOP/UI end-to-end บนcandidateท้ายชุดที่นิ่ง; reuse unaffected evidence ไม่รันworkloadเพิ่มเอง | Batch | Not Run — Pending Full Validation |
| V18 | Release/activation | ระบบรวม/restore/deployment/approvedworkloadหรือenduranceเมื่อเกี่ยวข้องตามreleaseprofile; teststrategyยังไม่เปิดproduction/Live และไม่ใช้ผลนี้แทนRSI/Livevalidation | Release | Not Run — Pending Full Validation |

## วิธีรันและหลักฐาน

- เริ่ม targeted pure/numeric/config tests ก่อน แล้ว safety integration กับ owned PostgreSQL
  ที่ผ่าน existing E2E database-name/role guards ไม่ใช้ฐานจริงของผู้ใช้หรือ bypass guard
- ใช้ Paper matching/ledger/protection workers จริงสำหรับ V03–12 ที่ mock พิสูจน์ไม่ได้
  controlled market fixtures บันทึก origin/finality ไม่ถือว่าเป็นหลักฐานตลาดจริง
- Browser flow รันใน owned acceptance app opt-in เท่านั้น ไม่เปิด production gate
  ไม่ส่ง Live orders และไม่ replay historical candles เป็นรายการซื้อปัจจุบัน
- ทดสอบ green triggerด้วยfixtureแท่งที่ปิดตามclock/source contracts ไม่เปลี่ยนserverclock
  หรือใส่คำสั่งซื้อจากbrowserเพื่อแทนstrategy signal
- ถ้า target/schema integration เปลี่ยน F-17 ให้ครอบคลุม transaction rollback, trigger vs
  entryfill และ latefill/retry races ก่อนผ่าน Feature ห้ามเลื่อนไป Batch
- รายงาน command/candidate/scope/ผล/ข้อค้างใน checkpoint นี้ ไม่สร้าง evidence PR วนซ้ำ
- ระหว่างพัฒนาใช้ targeted checks ตาม diff; แจ้งขอบเขตและเวลาประมาณก่อนชุดยาว
  Failed/Partial/Not Run คงตามจริง หากแก้แล้วเกณฑ์เดิมยังไม่ผ่านสามรอบให้หยุดเสนอทางเลือก

## ผล local checkpoint — 2026-11-21

Candidate: `feature/paper-test-entry` working tree บนฐาน F-21 e811800; ยังไม่มี published SHA
ผลและ scope รายละเอียด: [checkpoint](evidence/checkpoint.md). ไม่ใช้ผล local แทน required CI

- V01–V12: targeted automated checks Passed ตามขอบเขตหลักฐานด้านล่างและ shared safety regressions
  ไม่อ้างว่าทดสอบทุก permutation ของ failure/cancel/race หรือทุก timeframe ผ่าน browser
- V13: Partial — automated desktop Start/Stop/reload และ actual TP/SL ผ่าน; owner visual acceptance,
  mobile/light-dark/locale/keyboard acceptance ยังรอตรวจ ไม่ถือ screenshot เป็น owner acceptance
- V14: Passed — targeted regression/contracts/static checks; bundle-size warning คงตามจริง
- V15: Partial — Ready for Code Review แจ้งแล้ว; local diff/callers/security/stateless review และ
  refactor/affected tests ผ่าน; owner acceptance ยังไม่ผ่าน
- V16: Not Run — เพิ่ม isolated Paper Test Entry E2E step ใน required CI configuration แล้ว
  แต่ยังไม่ publish/รัน required CI บน final SHA; ไม่พร้อม merge
- V17/V18: Not Run — Pending Full Validation; ไม่เปิด production/Live

ทุกเกณฑ์เริ่มจาก Not Run; ตารางด้านบนปรับเป็นผลล่าสุดจาก checkpoint นี้ ประวัติ failure คงไว้ด้านล่าง
ผลที่เคย Failed: browser รอบแรก control URL ไม่ผ่าน Vite proxy (404); รอบสอง harness
อ้างชื่อ runtime ผิด (AttributeError); แก้ harness แล้วรอบสาม actual TP/SL Passed2/2
fault test เคยคาด SQLAlchemy exception แทน domain NotPermittedError; แก้ assertion โดยไม่
ลดการปฏิเสธของ DB แล้วผ่าน; UI fixture สองข้อผิดที่รอ catalogue/receipt ไม่ถูกต้อง แก้แล้วผ่าน
ไม่ลบ Failed history หรืออ้างผลจาก harness ที่ยังผิดเป็นหลักฐาน runtime

ระหว่าง browser มี `risk monitor deferred ... DATABASE_TIMEOUT` และ retry จนผ่านทั้งสอง flow
คง observation นี้ไว้ ไม่ใช้ผลสี่นาทีนี้แทน performance/workload/ตลาดจริง

## Owner preview correction — 2026-11-21

Owner-facing15121/API18021 now uses `TiewTrade-paper-test-entry` worktree. Previous
preview still served original F-21 and could not show the new option. Applied additive0075
on owned `tiewtrade_e2e_owner`; retained accounts, STOPPED/RETIRED runs and zero positions.
/tmp acceptance composition opts in API and compatible strategy registry; old API/bot
workers stopped before replacement. Public real-market source/risk/protection guards kept.
Authenticated catalogue returns both RSI and paper-green-atr-test; status STOPPED,
replacement_available=true, positions0, no pending request; served TSX includes new option.
No bot start, trade, resume or production/Live activation. Existing local panel/browser
strategy-selection results apply to unchanged application source. CUA browser host unavailable,
so current owner Chrome interaction is not claimed as verified; owner should reload15121.
Owner acceptance/required CI remain pending. This supersedes earlier 'preview unchanged'
observation for this local preview only.

## Start/readiness correction — 2026-11-21

Owner Start was accepted; durable run was PAUSED with INDICATOR_NOT_READY, not STOPPED.
Confirmed local preview omitted indicator-builder service (queued jobs and no builder).
Started existing supervised builder with its narrow role; it computes from real published
candles, no synthetic readiness/price/ATR or forced run state. User's existing Paper Start
remains authoritative; no extra start/stop/resume/order was submitted by the agent.
Compact status now shows existing readiness text below Stop only when confirmed PAUSED
with INDICATOR_/BOT_CANDLE_ reason. RUNNING/STARTING do not show stale readiness text.
Panel targeted suite30/30 Passed (four added cases); ESLint/typecheck Passed. Source review
confirms no mutation/financial/state-machine change; original RSI/general full view retained.
Owner acceptance/required CI remain pending; real-data warm-up remains a runtime prerequisite.

NC-05 Needs Clarification — real-source end-to-end entry remains Blocked: diagnostic
read returned one point, ATR READY, finality UNCONFIRMED; public latest BTC1m rows match.
V01–12 passing fixtures remain valid within recorded scope; they do not prove actual-market
CLOSED availability. F09/F11 forbid relabeling post-end UNCONFIRMED as CLOSED. Owner
choice required before changing admission; current run PAUSED, no new agent-issued trade.
UI readiness text is generic existing wording; does not claim ATR unavailable in isolation.

NC-05 documentation checkpoint: [RM policy proposal](real-market-candle-policy.md) prepared
at owner's request; Proposed, not approved. Checked against F09 RQ6/F11 RQ9+NC31 and
existing finality/source/decision contracts. No runtime changes, no new tests or trade.
Existing local evidence does not validate proposed UNCONFIRMED trading behavior.
Requirements approval, then plan/validation approval, required before implementation.

Timing clarification recorded2026-11-21: owner requests entry on next candle opening
following a completed green signal candle. Future amendment checks must cover no intrabar
signal/lookahead/backdated-open fill and actual-fill-based protection. No runtime changes.
NC05 permission to use post-end-fetched UNCONFIRMED remains undecided.

## NC-05 latest decision - Closed, 2026-11-21

Owner selected the same candle-finality/readiness and MARKET execution rules as RSI
Step Grid. Compared both pure strategies and shared read_bot_indicators: both reject
non-CLOSED candles, unready warm-up and stale/backfill inputs. No runtime change needed.
Paper Test Entry retains green-only entry/one-position/first-fill ATR TP/SL rules.
UNCONFIRMED proposal is Superseded, not approved; earlier pending-decision notes are
historical. No new tests needed for this documentation change; source/spec consistency
and git diff --check reviewed. Real-source entry remains Blocked until CLOSED evidence
is available. Owner acceptance/CI and pending full validation remain unchanged.

Owner explicitly approved the latest NC-05 same-RSI/CLOSED-only decision on2026-11-21.
Read-only preview check after approval: Paper Test Entry PAUSED revision2; latest five
BTC/USDT1m candles UNCONFIRMED. Real-source entry validation remains Blocked, not Passed.
No new Start/order/STOP/resume or source mutation. Documentation checked with diff --check;
prior applicable local test evidence retained. Owner visual acceptance/required CI pending.

## CLOSED-only readiness checkpoint - 2026-11-21

Implemented diagnostic correction under approved engineering scope: a correctly addressed
UNCONFIRMED indicator point now reports BOT_CANDLE_UNCONFIRMED; rejection remains identical.
Wrong slot/missing point/OPEN retain existing failure behavior. Compact/full UI reuse one
translated readiness mapping; show precise candle message only for confirmed PAUSED state,
without stale RUNNING/STARTING or initial-load warnings. No financial or lifecycle change.

Evidence: finality-reason.log4/4 (both strategies, UNCONFIRMED/OPEN); finality-pg.log3/3
actual-DB indicator-input regression; finality-ui.log33/33 panel/readiness tests;
finality-mypy.log, finality-ruff.log, finality-lint.log, finality-types.log Passed.
Affected diff/callers reviewed; guards and source finality unchanged. Earlier lint failure
was a new synchronous test marked async; removed async, all checks then passed.

Restarted only owned local preview API/frontend with compatible existing registry; no new
Start/order/STOP/resume/source rewrite. Authenticated GET confirmed PAUSED,
readiness_reason=BOT_CANDLE_UNCONFIRMED, positions0. User may inspect updated15121 UI.
Real-source entry validation still Blocked by missing CLOSED evidence. Required CI and
owner acceptance remain pending; no publication/merge or Live/production activation.

Owner UI override checkpoint: Paper PAUSED badge and candle-confirmation waiting copy
removed from compact/full views. Deleted unused translation keys; no hidden CSS copy.
Pending/RUNNING/STOP, Live PAUSED display and underlying status/selector locking retained.
Panel suite33/33 Passed, ESLint/typecheck/diff --check Passed. Initial test expected the
compact Stop label in full view; corrected synchronization target without weakening
absence/control assertions. Preview Vite serves updated source via HMR; no backend
restart, new Start/trade or data mutation. Owner/CI and real-source CLOSED blocker remain.

Indicator-copy removal checkpoint: removed rendering and unused en/th indicator waiting
keys, simplified remaining readiness mapping, retained actual status/gates/Stop. Targeted
panel tests35/35 Passed, ESLint/typecheck/diff --check Passed. Exact latest replacement
proof assertion retained; fixed test-only observer-notification synchronization after an
initial flaky revision5-vs6 failure. Browser timer is window.setTimeout per lint globals.
Application financial/replacement logic unchanged. Preview frontend uses HMR; no backend
restart/new order. Owner/CI and original real-source finality blocker remain pending.

Detailed real-market diagnosis (owner request2026-11-21):
[evidence](evidence/real-market-entry-diagnosis-20261121.md). High integration blocker:
installed REST/WS adapters do not produce CLOSED capability while both strategies require
it. Green post-end-fetched real candle exists, ATR READY, but zero strategy decisions/BUY.
This cannot be resolved by waiting alone in the current source pipeline. Medium validation
gap: controlled CLOSED fixtures do not prove real adapter-to-strategy admission.263 targeted
venue/strategy/classification tests Passed, demonstrating unchanged contracts; real-source
entry remains Blocked. No runtime modification or new trading-policy approval inferred.
