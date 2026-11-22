# Shared Candle Closure Proof — Validation

สถานะ: **Approved - owner replied approve2026-11-21; implementation authorized within this plan**
วันที่: 2026-11-21 (Asia/Bangkok)
ฐาน: CP-01–CP-16; ตารางนี้เป็นเกณฑ์ของ implementation ใหม่ ไม่ใช้ researchผ่านแทน

## เกณฑ์และหลักฐานที่ต้องได้

| ID | Criteria / requirements | วิธีพิสูจน์ | ระยะ | ผล |
|---|---|---|---|---|
| V01 | Native proof strictness CP01–03 | actual recorded BTC/ETH payload + mutated negative: x=false/typeผิด, wrongmarket/source/symbol/timeframe/t/T, invalidOHLCV/progress, UTC/calendar1w/1M; ไม่เกิดCLOSEDจากclock/REST/ATRอย่างเดียว | Feature | Passed — native/parser/calendar targeted evidence |
| V02 | Exact matching CP04/05 | BTC recorded identity/OHLCV matches; ETH recordedvolume611.04950000 vs610.94450000ต้องCONFLICT; equivalent decimalformatผ่าน, mismatchทุกfield/volumeไม่ใส่tolerance, nonfinite/overflow/unitผิดปฏิเสธ | Feature | Passed — recorded positive/negative, exact OHLCV mutations and typed numeric guards |
| V03 | Post-end fetch CP04/05 | fetch_started_at<endแม้responseหลังendไม่ผ่าน; equality boundaryผ่านเมื่อเงื่อนไขอื่นครบ; missing/request timesสลับ/rowไม่committed/stale claimไม่ผ่าน | Feature | Passed — temporal boundaries and real-PG claim regression |
| V04 | Warm-up/ATR CP08/12 |250eligiblecontiguoushistoryตามF11NC31, missinggap/249/sourceunready/numericfailureไม่ผ่าน; signalต้องCLOSED+currentproof; ATRsamecanonicalrevision ไม่แก้cachedfinalityหลบproof | Feature | Passed — scoped warm-up/indicator/Paper composition; current proof required |
| V05 | Closure-only metadata CP02/06/09 | OHLCV/progressเท่ากันแต่native xfalse→trueต้องpersistcandidate; exactduplicate/Eเปลี่ยนไม่publish/entryซ้ำ; stickypreviewhintหรือtime-derivedhintไม่ใช่nativeproof | Feature | Passed — metadata-only native close and duplicate PG tests |
| V06 | Ordering/conflict CP06 | cumulativeNEWER/OLDER/DUPLICATE/CONFLICT, sameprogressdifferentOHLC, lateclose/reopen/oldbar, noE/arrival-price-tiebreaker; conflictต้องพักก่อนnewentry | Feature | Partial — progression/conflict targeted checks passed; complete late-event matrix pending CI |
| V07 | Atomic publication CP07/09 | PGจริง faultหลังevent/proof insert, ก่อน/หลังcanonicalpromotion, ก่อน/หลังcommit/ackloss; proof/row/journalconsistent ไม่มีhalf-promotedCLOSED; retryหนึ่งlogicalresult | Feature | Passed — fault before/after promotion, rollback source fence, duplicate replay |
| V08 | Multi-instance/lease CP02/07/09 | PGจริงtwo writers, samecandleclaims, stale/disconnectedepoch, heartbeat/claimexpiry, crash/takeover; noacceptedoldlease ไม่พึ่งmemory/Redis; durablependingหลังrestart | Feature | Partial — concurrent writers, pool restart/takeover and four real process-kill commit boundaries passed; full deployment/failover matrix and CI for new tests pending |
| V09 | Corrections/invalidation CP06/08/13 | RESTchangedvalueถึงrowCLOSEDต้องไม่ถูกskip; invalidation+demotion+sourcejournalatomic; before/aftercommitconsumer races, acceptedhistoryไม่ลบ;repairต้องnewproofครบ ไม่เลือกOHLCจากtimestamp | Feature | Passed — correction before CLOSED skip, blocked series and fresh matching repair |
| V10 | Admission/queued BUY CP08/11/12 | PGจริงcorrection/invalidproof/STOP/risk/catalog/wallet/source/leaseเปลี่ยนระหว่างevaluate→commit→match;0unintendedBUY/duplicate/oversell;latestproof/fingerprintrechecked | Feature | Passed — queued window boundaries, accepted/SELL-driven proof invalidation, exit guard revisions and source/authority regressions |
| V11 | First-fill financial invariants CP12/13 | actualPaper matcher/ledger: partial/latefill, manualreduction, unknown/retry/TP/SL; proofcorrectionหลังfillไม่rewriteexecution/PnL/testATRfrozenlevels; quantities/reservations/balanceexact | Feature | Passed — scoped first-fill/PnL/protection regression and post-fill correction invariance |
| V12 | Candle entry timing CP09–12 | Aclosedproof→BMarketwhenfresh, nointrabar/lookahead/backdatedopenfill;afterStart/recoverycutoff, exit-samecandle, revision/replayedhistoryไม่entryซ้ำ;lateproofหลังBต้องskip | Feature | Partial — corrected-candidate PG boundary/cross-boundary guards passed; parent attempt4 verified next-candle command only, no fill |
| V13 | DB/schema/security CP07/15 | fresh/upgrade/emptydowngrade;historydowngraderefusal;unique/FK/check/domain/appendonly/grants;engine/API/indicatorrolecannotpromote/writeproof;publictablesไม่เปิดusersecret;retentionไม่ทำลายpinnedauditหรือบล็อกpartitionตลอดชีวิต | Feature | Passed — fresh/upgrade/downgrade refusal/roles/append-only/trigger inventory checks |
| V14 | Migration/protocol compatibility CP15 | OFFpreservesoldbehavior;oldwriterrestart/missinginventory/proofguard/sourceproofnotREADY/unsupportedconsumerต้องactivationrejected;knowncompatiblemixedversionsมีหลักฐาน ไม่ยอมoldwriterเงียบskipcorrection | Feature | Partial — local typed-inventory/source readiness/subprocess OFF-legacy, ON-rejected-legacy and ON-v1/deactivation matrix passed; actual deployed inventory/old-binary compatibility and final-head CI pending |
| V15 | Source costs/recovery CP05/10/14 | existingcoalescing/ratebudget/backoff underduplicateevents;noHTTPintransaction;pendingbounded;WSdisconnect/missingclose/REST429/5xx/timeoutsrepairไม่promoteหรือretryhotloop;resumeไม่replayentry | Feature | Partial — retry-exhaustion regression passed; public boot/source readiness incomplete |
| V16 | End-to-end deterministic composition CP01–16 | rawactualadapterpayload→PGnativeproof→RESTpublication→F11→strategy→actualPaperBUY/protection;BTCpositive/ETHnegative plus syntheticedgefixtures clearlylabelled;RSIpositiveARM/FIREregressionและtestgreenoneposition | Feature | Partial — deterministic path passed; actual API/proof/strategy/command chain verified, actual fill/protection not reached |
| V17 | Current-candidate real public-source campaign CP01–16 | oneboundedownedPapercampaignตามด้านล่าง actualWS+REST/PG/API/engine;closedproofchain+testgreenBUYจริงถ้าเกิดeligiblegreen;RSIevaluateตามactualconditions ไม่มีforceARM;noLive/useraccountorders | Feature | Partial — parent attempt4:8 proofs/7 decisions, one green100USDT BUY command rejected; corrected candidate public campaign Not Run; no further attempt authorized |
| V18 | Static/contracts/targeted regression | ruff/format/mypy/importcontracts, migrations/source-triggerinventory, APItypesเมื่อcontractเปลี่ยน;targetedF09/F11/F12/F20/F21/Paper/F17 dependencies;UIhiddenmessages/defaultsไม่เปลี่ยน | Feature | Passed — final full mypy804, Ruff/format885, import contracts7, unchanged API contract; prior90-error failure retained |
| V19 | Stable candidate full regression/required CI | common sourceแก้หลายระบบ:fullbackendcorrectness/security/financial regressionและexistingfreshstate/migration/securityjobsที่บังคับบนfinalcandidate;candidateSHA/runlinks, noLocalแทนCI | Feature | Partial — required CI44990595087 and Security44990595105 Passed on e193fd32; later local process-crash tests not yet covered by final-head CI; historical failures retained |
| V20 | Review/owner acceptance/rollout | ReadyforCodeReview→diff+callers+DB/financial/stateless/concurrencyreview→fix/refactor→affectedchecks;ownerตรวจscope/candidate/activationความหมายจริงก่อนmerge ไม่ใช้automatedreviewแทนowner | Feature | Partial — Ready for Code Review announced, review/fixes done; owner/independent acceptance pending |
| V21 | Combined source/strategy cross-feature E2E | candidateรวมF09/F11/F12/F17/F20/F21/Paperที่นิ่ง พร้อมfullfront/cross-featureprofilesตามBatchscope ไม่รันซ้ำทุกpatch | Batch | Not Run — Pending Full Validation |
| V22 | Production/Live/release gates | approvedrestore/deployment/rate/load/endurance/venuecontractcoverageที่เกี่ยวข้อง;ไม่activateproduction/Liveในงานนี้ ไม่เรียกCompletedก่อนReleasecriteriaครบ | Release | Not Run — Pending Full Validation |

## Targeted implementation checks

เริ่มจาก existing tests ก่อนเพิ่มเท่าที่มีriskgap:

- Venue/core: `tests/venues/binance_th/test_candle_stream_mapping.py`, `test_candles.py`,
  `test_candle_feed.py`, `tests/core/test_market_data.py`, existingcandlepreviewcomparisontests
- Public source: `tests/services/market_data/test_candle_realtime.py`, `test_ingestion.py`,
  `tests/infra/market_data/test_claims.py`, `test_batch_write.py`, `test_storage.py`,
  `test_permissions.py`, native3m/calendar/partition testsตามdiff
- F11: `tests/infra/indicators/test_source.py`, `test_source_lock_matrix.py`, prepared/
  checkpoint/tail/recovery/retentiontestsตามcontractที่เปลี่ยน
- Bot/financial: strategy_commit_fences/exit_races/recovery/tail_inputs/indicator_inputs,
  bothpurestrategies และ Paper Test Entry first-fill/protection testsจากdependencycandidate
- เพิ่ม pureclosuretestsและ realPG closure atomicity/role/lease/correction/rollout tests
  ใช้isolatedownedDB/rolesตาม existingguards ไม่ใช้mockพิสูจน์transaction/locking

ก่อนชุดยาวแจ้งscope/เวลาประมาณจากผลเดิมบนenvironmentนั้น; ไม่รันfullsuiteเป็นพิธีทุกpatch
รายงานFailed/Partial/NotRunตามจริง หลังแก้รันเฉพาะfinding/failure+affectedregression
fullstablecandidatechecksยังต้องครบตามV19ก่อนmerge ไม่เลื่อนfinancialsafetyไปBatch

## Public-source Paper campaign ที่ขออนุมัติในแผนนี้

- **หนึ่ง attempt สูงสุด6นาที** (หลังboot/readiness) + gracefulcleanupตามtimeoutsเดิม
  ใช้BTC/USDTและETH/USDT1m ในownedDBใหม่ที่ผ่าน E2E-name/role guards ของrepo
  publicnetworkเฉพาะBinanceTHผ่านexistingrate/connectionbudget ไม่มีsecret/privatevenueAPI
- disposablePaperfixtureทุน10000USDTและcapital100USDTตามfixture/ค่าที่เจ้าของใช้อยู่
  ไม่แก้wallet/runของเจ้าของ กลยุทธ์testถือครั้งละหนึ่งposition;RSIใช้configที่approved
- เปิดproofprotocolเฉพาะownedvalidationinstanceหลังP1–P3safetychecks/reviewผ่าน
  เก็บcandidatefingerprint, sourceevent/REST/request-start, proofID, canonicalrevision,
  ATR/sourceadmission, decision/order/fill/protection/position/reservationจากเงินจริงPaperledger
- ทดสอบentryผ่านactualstrategy/API/engine ไม่มีfixtureที่ปลอมfinalityหรือสั่งBUYแทนsignal
  RSIถ้าARM/FIREไม่ครบต้องไม่ซื้อ:บันทึกNO_SIGNAL ไม่ถือว่าได้พิสูจน์realpositiveRSIentry
  positiveRSIlogicใช้deterministiccompositionแยกตามV16และเก็บreal-entrygapตามจริง
- หากไม่มีeligiblegreen/หลักฐานไม่ตรง/ข้อมูลหรือnetworkไม่พร้อมภายใน6นาที ให้Partial/Blocked
  พร้อมเหตุ ไม่รอเพิ่ม/วนcampaign/เปลี่ยนpair/timeframe/ลดguardเพื่อให้ผ่าน
  V17ไม่Passedโดยไม่มีactualtest-strategyBUY+fillและproofchainที่ตรวจย้อนกลับได้
- หลังหยุดcapture:ใช้existingstop/drainเฉพาะownedtestservices เก็บสถานะ/ledgerจริงแม้ยังมี
  position;ไม่forcefillTP/SL ไม่ซื้อขาย/closepositionของเจ้าของ การล้างdisposableDBทำตามguards
- การทำattemptเพิ่ม/ขยายเวลา ต้องส่งผลรอบเดิมให้เจ้าของเลือกก่อน ไม่ใช้CIrerunขยายcampaignแฝง
- requiredCIหลักใช้deterministictestsบนrecordedpositive/negative+PG;venue/publiccampaign
  แยกจากnormalunitCI แต่หลักฐานV17ต้องผูกcandidateเดียวและมีผลก่อนผ่านFeature

Probeวิจัยก่อนหน้านี้หนึ่งรอบ59.847วินาทีเป็นหลักฐานpublicsemanticsและfixtureเท่านั้น
ไม่ใช่ผลV17และไม่ถือว่าอนุญาตทดสอบซื้อขายกับบัญชีของเจ้าของ

## Checkpoint ก่อนอนุมัติ (ประวัติ; สถานะปัจจุบันอยู่ด้านล่าง)

Requirements Approved; plan/validation Proposed. ยังไม่มีimplementation/migration/protocol
activationใหม่จากงานนี้ ผลV01–V22ยังNotRun;researchBTCpositive/ETHvolumeconflictคงตามจริง
หลังเจ้าของอนุมัติสองเอกสารจึงเริ่มimplement→targetedchecks→review/fix/refactorต่อเนื่อง
หยุดตามAGENTSเมื่อเกณฑ์เดิมล้ม3รอบ/เกินขอบเขต/พบnewbusinessหรือLivepermissiondecision
Owneracceptance/requiredCIต้องครบก่อนmerge;Batch/ReleaseคงPendingFullValidation

## Initial implementation review checkpoint —2026-11-21 (historical)

Requirements/plan/validation Approved. Implementation and scoped review/fixes are present
in `feature/candle-closure-proof`; overall Feature validation remains incomplete, not Completed.
See [review](review.md) for file-level findings, fixes, exact commands/evidence and remaining risks.
Historical research/campaign manifests are separate from the reviewed final candidate manifest.

- Final targeted regression149 passed; venue/core/strategy289 passed, exact-field26 passed;
  closure PG17 passed plus rollback2 passed; existing migrations4 passed; service units15 passed.
  Counts overlap and must not be summed as unique cases.
- Ruff/format for21 changed Python files passed, source mypy287 passed, scoped changed-file
  mypy20 passed, import contracts7 kept. **Full mypy Failed90 errors in10 unchanged dependency
  test files**; `evidence/full-typecheck-failed.txt` retained. Full type success/required CI is not claimed.
- One public attempt ended Partial during boot08:09:06–08:10:49UTC: actual source history
  fetched, F11 READY then SUPERSEDED/SOURCE_CHANGED; book readiness unavailable. Protocol
  stayed OFF; API/strategy entry validation was not reached;0orders/positions/proofs. No retry.
- Final CP06 contradiction/recovery correction was tested with PG after that attempt; V17
  is therefore also Not Run on the final runtime. Do not reuse the Partial run as its pass.
- Owner preview15121 and owner account were not activated/started/stopped by this feature.
  No Live, publication, commit/push/PR/merge. Owner/independent acceptance, required CI and
  remaining Feature matrices are pending; Batch/Release stay Pending Full Validation.

Next: combined-candidate type/CI blockers must be resolved in their owning scope; another
bounded public campaign needs owner authorization under the one-attempt rule above.
Only after gates and owner checkpoint may preview activation proceed; do not auto-resume
an already-started Paper run or relax exact matching/financial/admission rules.


## Owner continuation checkpoint —2026-11-21 (historical; corrections below)

Owner authorized CI dependency cleanup and one additional bounded public campaign.
Current reviewed candidate: `evidence/continuation-reviewed-candidate-manifest.json`.
Campaign2 ran the preceding `continuation-candidate-manifest.json`; subsequent changes
are harness diagnostics/tests only, no production code or trading-rule change.

- Full mypy now **Passed804 files** after correcting the ten dependency test files. Final
  Ruff and format Passed885 files; import contracts7 kept; API export remained identical.
- Full backend completed **6012passed/7failed/32deselected in2157.74s**. Preserve that raw
  Failed result, not a green full-run claim. Six failures were outdated route/import/mock/
  fixture inventories; the seventh received a public Redis event from the shared instance.
  Logical Redis databases do not isolate Pub/Sub. Final affected regression **16passed**
  on fresh PostgreSQL and a dedicated temporary Redis, including all seven failed cases
  and both protection timing cases. No assertion, timeout, threshold or safety rule relaxed.
- Initial isolated protection suite Failed2 timing cases under concurrent full regression;
  their unchanged cases Passed in final16. Four other isolated CI phases exited0: writer
  downgrade guard, optional-limit guard, fresh-global state, protection rollback guard.
- Secret route canary2passed; harness scheduling/diagnostic tests6passed. The last harness
  change only adds controlled API path/status and file/function/line, excluding exception
  text/locals/bodies/secrets; it preserves exclusive attempt markers. A test-only scoped
  mypy invocation without src roots produced import-untyped errors; correct full src/tests
  invocation Passed804 without changing configuration or code to silence them.
- Public attempt2 **Partial**,09:21:42–09:22:51UTC: actual BTC/ETH1m history, both F11 builds
  READY, execution preflight passed and closure activated in the owned test DB. Failure
  occurred at OWNED_API_SETUP, recorded as RuntimeError. Read-only inspection found0users,
  wallets, orders and positions. No strategy began, no real BUY was proved. Offline API-only
  registration subsequently succeeded in a different fresh DB; original failure cause is
  **not established**. Historical report is unchanged; no third public campaign was run.
- Campaign2's original harness lacked safe failure context. Fixed diagnostics/tests after
  preserving that report and its manifest. Future campaign authorization must explicitly
  permit a new attempt; no retry or extension is inferred from this checkpoint.
- No owner preview/account activation or trade, no Live, commit/push/PR/merge. Temporary
  validation workers stopped; disposable Redis cleaned up. Owned evidence DBs retained.

See `evidence/continuation-checks.json` and `review.md`. Full earlier failures remain in
separate evidence files. V06/V08/V12/V14–17/V19–20 retain Partial/Not Run gaps as listed;
local reruns do not substitute for required CI or owner/independent acceptance. Batch/
Release remain Pending Full Validation. Feature is **not Completed or ready to merge**.

Next: owner decision on another bounded public attempt using the corrected diagnostics;
then resolve actual failure evidence and remaining Feature/acceptance/required-CI gates
on the final combined candidate before publication/merge. No automatic public rerun or
owner-preview activation is authorized.


## Completion/code-review checkpoint —2026-11-21 (historical)

Owner approved continuation to finish and announce code review. One additional bounded
attempt was executed; the three-attempt stop rule then applied. Current reviewed files are
bound by `evidence/completion-candidate-manifest.json`. Production runtime is unchanged
from the preceding source review; latest modifications are validation harness/tests only.

- Attempt3 ran09:29:50–09:31:23UTC, actual BTC/ETH1m builds both READY, owned closure
  activation/preflight succeeded, then RSI configuration was rejected HTTP422. Harness sent
  strategy_name to the RSI model, which forbids it. Fixed by reusing the existing API input
  models for both strategies. Both payloads passed actual HTTP/PG tests with idempotency.
- **Correction to prior zero-user/wallet claims:** FORCE RLS filtered migrator reads. They
  were not evidence of absence. Independent read-only test-admin recollection confirms
  **attempts2 and3 each have2users/2wallets/2capital-ledger rows,0runs/0orders/0positions**.
  Original reports/manifests remain unchanged. See `public-paper-campaign-2-audit-corrected.json`
  and `public-paper-campaign-3-audit-corrected.json`, with original report hashes/timestamps.
  The original attempt2 exact HTTP status was not captured; do not backfill it as proven.
- Fixed inventory/evidence reading uses test-admin only in strictly local owned campaign
  DBs, with read-only transactions and parameter hiding. Runtime writers retain narrow roles.
  Actual PG regression proves a real ledger hidden by migrator is visible to evidence and
  audit writes are refused. Guard tests reject owner DB, remote DB and different DB names.
- Latest affected regression **14passed** (real API/config/PG audit plus existing harness),
  final harness/guard **9passed**; overlap must not be summed. Full mypy **804files Passed**,
  Ruff/format Passed. One guard test initially imported os via a non-exported module;
  corrected to direct import and full strict mypy passed, without ignores/config relaxation.
- Previous full6012passed/7failed and affected16passed evidence remains applicable to
  unchanged runtime. No second full regression merely for harness/test corrections.
  API contract and production trading/financial/session/stateless behavior unchanged.
- **Ready for Code Review** announced; follow-up review covers payloads, evidence privilege/
  RLS boundaries, exclusivity, cleanup and callers. No new unresolved source-code finding.
  Real public BUY/TP/SL acceptance remains unproved; V17 remains Partial, not NO_SIGNAL.
- Asked owner for a new bounded attempt or review with validation open, explicitly because
  AGENTS mandates a decision after three failed attempts. No fourth public attempt, no Live,
  no owner-preview activation, no commit/push/PR/merge. Temporary workers/Redis stopped;
  owned evidence databases retained, no destructive cleanup.

Next: code review is ready now. A fourth public attempt requires the pending explicit owner
choice; owner/independent acceptance and required CI remain open under P6/AGENTS, so this
is **not Completed or merge-ready**. Remaining Feature matrices keep their prior Partial
status; Batch/Release remain Pending Full Validation.


## Authorized attempt4 checkpoint —2026-11-21 (historical parent candidate)

Owner explicitly approved one further actual-source Paper attempt after the three-attempt
stop. Candidate remains `evidence/completion-candidate-manifest.json`, fingerprint
51f6519346fe9bf92bf5a4d53568678375b8198024fc99936762b955d3867566.
No implementation changed this turn; previous static, review and affected tests remain
applicable. Only plan authorization, evidence and checkpoint documentation changed.

Attempt4 boot12:51:38UTC; actual campaign12:53:15–12:59:16UTC,360s capture plus normal
cleanup. Result **Partial**, not Passed and not NO_SIGNAL. Two real API starts succeeded,
8MATCHED closure results and7decisions were persisted. Offline re-verification reconstructed
all8 actual native/REST pairs with existing Money/Quantity/Candle/ClosureCandidate and
verify_closure; identities, fingerprints, exact OHLCV and post-end request bounds Passed.

Actual green BTC12:54 candle produced one100USDT MARKET BUY command in the next candle,
requested12:55:41.081358UTC. Its decision references a verified proof and ATR; there is one
linked command, no duplicate. It was **REJECTED / ORDER_SAFETY_UNAVAILABLE**, recorded
12:56:24.323755UTC. No matched order projection/fill/execution/position/reservation exists.
The first-fill anchor remains unresolved (no execution/price/TP/SL); TP/SL and PnL therefore
remain unexercised by this public attempt. Both wallet ledgers retain only their original
10000USDT capital entries; no fee/trade/balance mutation was observed.

Commit-timestamp evidence: BUY decision committed12:55:41.701637, resulting runrevision8;
INDICATOR_NOT_READY pause revision9 committed12:56:00.684285; rejection committed
12:56:24.448782; resume revision10 committed12:56:28.294247. Thus the durable run was
PAUSED with a newer revision at rejection. Existing paper_bot_authority requires RUNNING
and queued proof checks pin the decision revision, so this state blocks that command.
This is evidence-backed code/timeline analysis; the generic rejection did not record an
individual sub-guard. No stop requests exist. The cause of roughly43seconds queue/
processing latency remains unproved; indicator/source readiness gaps, book warnings and
risk-monitor DATABASE_TIMEOUT deferrals occurred. Do not infer a root latency cause or
change freshness/admission/STOP/risk rules from these observations.

Evidence: `public-paper-campaign-4.json`, `public-paper-campaign-4-diagnostics.json`,
`public-paper-campaign-4-authority-timeline.json`, `public-paper-campaign-4-verification.json`
and raw log. FEED_DISCONNECTED in final execution state follows producer cleanup and
alone is not evidence of source state at admission. Original reports are preserved.

Owned workers stopped; temporary Redis cleaned up; owner preview/accounts/Live untouched.
No fifth public attempt, extension, synthetic signal/fill, business-rule relaxation or
commit/push/PR/merge. V17 remains Partial: real signal-to-command is now proved, but actual
fill/first-fill protection is not. Remaining owner/independent/required-CI and other Feature
matrices remain open; Batch/Release Pending Full Validation. Code-review readiness remains,
not Completed or merge-ready.

Next: review current code/evidence and diagnose command-dispatch/source readiness latency
before proposing any further bounded public attempt. Another attempt needs explicit owner
authorization; no automatic retry is part of this checkpoint.

## Review correction validation —2026-11-22 (planned before edits)

Reopen V06/V10/V12 coverage for the three High findings in the read-only review.
Add actual-PG boundary/accepted-order/capture-order regressions and run affected authority,
source and financial safety tests, then scoped Ruff/mypy/import checks and review the fix.
Until those pass, earlier Passed V10 does not cover these gaps. Public V17 remains Partial;
required CI, mixed-process/recovery matrices and owner acceptance remain pending. No
additional public campaign is authorized by this fix request.

## Review fixes checkpoint —2026-11-22 (current)

Candidate51ab7d36cf1e2bd02b49cab5deaa6255c74117c41ba22f1bd0b2c7383eecdbba,
39 Python files bound by evidence/review-fix-candidate-manifest.json. The parent completion
manifest/reports are preserved. No public run on this corrected candidate is claimed.

- V06: actual close conflicting with an OPEN slot, including an older cumulative snapshot,
  is persisted INVALIDATED without reconciling/promoting; a concurrent real-PG reader cannot
  obtain a tradable receipt before or after commit. Full ordering matrix remains Partial.
- V10/V12: queued BUY rejects end(B), after B, and crossing end(B) during proof reads; healthy
  just-before-B-end passes. Timestamp boundary is deterministic SQL CAST in the real-PG
  test; this is not an observation from the public venue. Lease/source/risk checks remain.
- Accepted BUY and a reducing SELL driving the same matcher cannot acquire a new fill
  after closure invalidation while the bot still reports RUNNING. Manual inventory in the
  SELL fixture comes only from actual Paper matching. Privileged metadata setup is confined
  to the isolated test DB, not a new production account-use capability.
- Existing exit race assertions revealed missing pinned guard_revision validation and an
  A/B exit-slot mismatch after the accounting fixtures were corrected to CLOSED signals.
  Reuse one signal_exit_guarded helper for context/registration; queued and accepted BUYs
  retain the current guard revision. No cooldown or financial formula changed.
- Initial63-case run:51passed/12failed (OPEN/fixed-date accounting fixtures). Affected rerun:
  14passed/1failed exposed the guard-revision race; its two writer orders then passed.
  Broader87-case run:83passed/4failed exposed current-entry-slot registration. All four
  failures passed after the shared A/B lookup fix. Preserve every raw failed report.
- Final affected PostgreSQL regression **67passed**, four failed basket/recovery cases
  **4passed**, pure strategy/source/harness **116passed**, isolation/reason gates **6passed**.
  Counts overlap; do not sum as unique coverage. Scoped mypy8files, Ruff/format8files,
  import contracts7 and git diff --check passed. See evidence/review-fix-checks.json and
  review-fix-final-*.txt, review-fix-entry-slot.txt and review-fix-gates.txt.

Scoped review of these fixes/callers found no remaining High finding in this correction.
Durable source/financial locks and PostgreSQL authority remain in use; no local session or
persistent business authority added. Existing facts, first-fill levels, PnL and reducing
orders remain protected by the real financial regressions. API/UI/Live scope unchanged.

V17 and other Partial Feature matrices, required CI and owner/independent acceptance remain
open. Parent full/backend/public evidence does not substitute for required CI or a public
fill on this candidate. Roughly43s parent dispatch latency remains undiagnosed. No additional
campaign, owner-preview activation, Live order, commit/push/PR/merge. Batch/Release remain
Pending Full Validation; not Completed or merge-ready. Next: owner/independent review of
this correction and the remaining Feature/required-CI gates; any new public attempt needs
separate explicit authorization under the existing campaign stop rule.


## Scoped refactor checkpoint —2026-11-22

Owner requested refactor of the latest review correction only. Changed two production
files: authority.py names signal_end/entry_end and reuses the native calendar boundary;
candle_realtime.py uses an early generation/lease return and one prior observation to
remove repeated tuple access. Existing shared closure/exit helpers remain reused.
No new abstraction, financial formula, SQL, lock/transaction order, branch priority,
exception behavior, strategy or activation rule changed. The scoped before/after diff is
evidence/refactor-scoped.diff; this is separate from the larger uncommitted feature diff.

Candidate 9d77fa16b8932916fee62483208db15b49e966b4697ff9d3c830403cfdab1860 (39 Python files) is bound by
evidence/refactor-candidate-manifest.json; all previous manifests/reports are preserved.
Real PostgreSQL closure and commit-fence tests: **53 passed**. Realtime unit tests:
**15 passed**. Scoped Ruff/format and mypy (2 files), import contracts
(7 kept) and git diff --check passed. Raw test logs and static check summary are in
evidence/refactor-*. No public-source experiment was run. Dedicated disposable local
test services were used; owner preview/accounts and Live were untouched.

Review of the scoped refactor found no new issue. Persistent authority remains in
PostgreSQL; no session cache, process-local business authority or infrastructure was
added to the application. No test assertions or safety conditions were removed.
Previous Feature Partial gates, public-fill evidence, independent/owner acceptance and
required CI remain open; Batch/Release Pending Full Validation. Not Completed or
merge-ready. No commit/push/PR/merge. Next: remaining owner/independent acceptance and
required CI under the approved gates; another public campaign needs explicit approval.


## Local recovery continuation —2026-11-22 (planned)

V08: add targeted real PostgreSQL WAITING_REST pool-restart and expired-writer takeover
regressions. Run these and the adjacent duplicate/disconnect/rollback proof tests, then
scoped static checks. Preserve earlier results and all external gates. No public campaign
or preview activation authorized; draft-PR/CI exception awaiting owner response.


## Local recovery checkpoint —2026-11-22 (current)

Candidate237084189846896b85ff4dc70389a2c2b1fc46b498e641480cebf226fe5cfc2a
is bound by evidence/local-recovery-candidate-manifest.json. Only two tests were added
after refactor; production source hashes are unchanged. Actual PostgreSQL6passed/20deselected
(local-recovery-tests.txt): pending native evidence survives pool disposal and claimed REST
completion with one proof/result; an expired writer cannot submit, and its pending receipt
cannot reconcile after takeover until new current-writer evidence arrives. Adjacent duplicate,
disconnect and atomic-rollback tests also passed. Pool recreation is not a process-kill test.

Scoped Ruff/format passed1test file; mypy passed3source/test roots (local-recovery-types.txt).
An initial test-only mypy invocation failed import-untyped because src was not a root;
rerunning with source roots passed without suppressions/config changes. One long test SQL
line was split after Ruff E501, then passed. git diff --check passed. No runtime change,
safety assertion removal, public campaign, owner account/preview operation or publication.

Offline preserved attempt4 analysis is local-dispatch-evidence-analysis.json: measured
42.747145s from decision commit to rejection commit; pause commits before rejection.
Terminal attempts=0 is reset by finish_claim and cannot prove no deferrals occurred.
Historical per-claim/worker-phase timing is absent; latency root cause remains unproven.
No timeout/admission/risk rule changed to make the command pass.

V08 remains Partial for the full process-crash/deployment matrix. Public fill, other Feature
gates, independent/owner acceptance and required CI remain open. Owner was asked whether
to authorize publication solely for a draft PR/CI; no answer is assumed. No fifth public
attempt or merge is authorized. Next: after explicit publication exception, bind and push
one draft candidate for required CI; owner acceptance remains a separate gate.


## Draft PR/CI continuation —2026-11-22 (planned before publication)

Owner authorized draft publication and required CI with “เริ่มทำ”; earlier unanswered
publication status is superseded for this purpose only. Integrate main005ec483 F17 refactor,
run affected protection safety regression and static checks, then publish one combined
draft candidate for the existing full CI/security workflows. No merge, public campaign5,
owner acceptance or preview/Live activation is inferred. V19 remains Partial until actual
required CI passes on the final SHA; report subsequent run links without a document loop.


## Draft publication candidate —2026-11-22

Owner publication exception is authorized; earlier pending-publication notes remain
historical. Integrated origin/main005ec483 F17 refactor without conflicts, preserving
EntryAtrProtection. Affected protection/paper-test/basket-target units118passed and actual
PostgreSQL first-fill/protection tests10passed. Scoped Ruff/format/mypy2files passed;
git diff --check passed. Logs: publication-protection-units.txt, publication-first-fill-pg.txt.
No new runtime correction or trading-rule change was needed for integration.

Final reviewed commit will bind the combined F21/Paper dependencies plus closure source,
fixes/refactor/tests and all existing evidence. publication-candidate-manifest.json binds
changed runtime/test/config file content against main005ec483; previous manifests remain
historical. Draft PR only, no merge. Required CI has not yet passed and will be reported
with final SHA/run links after publication, without a documentation-only commit loop.

Owner/independent acceptance, remaining Partial matrices and public actual fill remain
open. No campaign5, owner-preview/account operation, Live activation or merge is authorized.
Batch/Release remain Pending Full Validation; not Completed or merge-ready.


Publication check clarification: once previously untracked raw evidence was staged, the
all-file whitespace check reported historical pytest/import-linter output and unified-diff
context whitespace. Preserve those raw failure logs byte-for-byte; they are not source
formatting changes. `git diff --check origin/main HEAD -- .
':!specs/features/2026-11-21-candle-closure-proof/evidence'` passes for the integrated
source/docs candidate. Do not report the raw-evidence-inclusive whitespace check as passed.
No scanner, CI gate or runtime safety criterion is bypassed or reconfigured.


## Exact Security exception correction —2026-11-22

Draft PR85 published c864411eb730d200cbb8dad3410a356e20579e88. Initial Security run
44985466615 failed secrets/gate for two new generic-api-key occurrences; other Security
components passed. Owner explicitly approved only those two Paper order UUID occurrences
(lines12/17, exact commit/blob/count/digest recorded in plan.md). Added one entry to the
existing immutable-evidence registry; scanner/matcher/severity/coverage are unchanged.

Existing resolver unittest suite:11passed/1skipped (12run; optional real-scanner fixture
not configured). Evaluating the complete captured pinned history/tree findings against
the updated registry yields0blocked/0triage,48494deduplicated approved occurrences. No
credential values were displayed or tested against any service. Full pinned scan must
still run on the correction commit before push, then required CI on the final SHA.
Runtime/trading source is unchanged; earlier manifests and first Security failure remain
historical. CI outcome will be reported with links/SHA without a doc-only commit loop.
No merge, owner acceptance, public campaign5 or preview/Live activation is authorized.


## E2E failure correction —2026-11-22 (planned)

CI44986019642 on607736ac: general browser suite34passed/2failed (ambiguous Timeframe
locator and obsolete strategy-disabled expectation). Security44986019665 passed all
components. Correct only those two test expectations/selectors as documented in plan.md;
keep zero order mutation and all budget/responsive/keyboard assertions. Rerun both locally
on disposable E2E services, retain original failure and use final-SHA CI for V19.


## Browser fixture correction checkpoint —2026-11-22

Corrected only two E2E files: chart Timeframe lookup uses exact:true like the existing
locators; strategy selector is required to be enabled/focusable when no run is pinned,
with Shift+Tab/Tab assertions through it. All Start-disabled,16UI combinations, budget
persistence, no-form/no-tabs and zero-mutating-request checks remain. Actual isolated
local browser regression2passed in23.7s; scoped ESLint and frontend typecheck passed.
See evidence/publication-e2e-corrections.txt. No runtime, strategy, trading safety,
timeout or environment guard was loosened. Original CI44986019642 E2E34/2 result is
preserved. Push this in-scope test correction and evaluate required CI on the final head;
no merge/public campaign5/owner-preview activation. Other acceptance gates remain open.


## F16 budget-label regression —2026-11-22 (planned)

CI44987001408 on a6859fb7: corrected general browser suite passed; subsequent F16 suite
7passed/1failed while locating the former bot-budget label. Planned stable-control locator
correction only, preserving every reset/idempotency/episode refusal assertion. Original
run retained; next targeted local result and final-SHA CI must be evaluated independently.


## F16 stable draft-control checkpoint —2026-11-22

The one failing reset/recovery browser case passed locally in10.5s on disposable services.
Scoped ESLint and frontend typecheck passed. The existing test already used the bot-card
draft field; use one #paper-bot-budget locator instead of the pre-F21 label at all three
assertions. Reset/409/UNKNOWN/original-body-and-key/404/empty-journal checks are unchanged.
No runtime/safety/timeout change. See evidence/publication-manual-draft-correction.txt.
Search found no remaining E2E references to that obsolete label or the corrected loose
Timeframe/strategy-disabled expectations. Push the test-only fix and follow final-SHA CI;
keep previous failures, owner/independent/public-fill gates and no-merge scope unchanged.


### Owner-approved bounded E2E continuation —2026-11-22

CI44988072782/c7cd1e4a: general browser36passed, catalog2passed, F16eightpassed,
F17sevenpassed; F20onepassed/onefailed at stale pending Start expectation. Later suites
not run by this CI. Backend still running when diagnosed. Security44988072777passed.
Owner permits test-only corrections, isolated remaining-suite checks and one additional
required CI candidate run. No owner acceptance, public campaign or merge waiver.


Bounded local continuation results: F20two passed; F21actual five-candle financial
case passed, initial two recovery races failed then both affected cases passed after
waiting for unchanged request/receipt assertions; Paper Test TP/SLtwo passed;
F18/F19risk/STOPsix passed. Scoped ESLint and frontend types passed. Test-only diff
review confirms exact keys/counts, real receipt/run, balance, position/protection,
STOP recovery and owner/mode isolation retained. No runtime change or timeout increase.
See evidence/publication-remaining-e2e.txt. Temporary local configs/services are removed
after validation. One new required CI candidate run is authorized; do not substitute
these local checks for it or for outstanding owner/Feature/public-source evidence.


Prior CI backend completed after this local E2E checkpoint:44988072782reports
6031passed/1failed/2skipped/32deselected in1534.84s. Failure is the unchanged
TOTP setup helper (test_totp_flow.py91) called before API-key retry-quota assertions;
HTTP403invalid code. Previous-step code generation may cross a30s boundary; this is
an inference, not a proven diagnosis. A single targeted real-PostgreSQL rerun of
that unchanged retry-quota test passed on the correction candidate. No authentication,
TOTP helper, test expectation or security window was changed. Preserve the CI failure;
only the one authorized new CI run can establish its final-head outcome.


## Post-CI Feature recovery continuation —2026-11-22 (planned)

Final runtime candidate e193fd3237a489f152a0643ff25105227c4e82f6 passed required
CI44990595087 and Security44990595105, including66browser E2E cases. Historical failures
remain Failed. V19 CI component is Passed on that SHA; other Feature gates are not waived.
Next local work targets V08 real process death before/after pending/publication commit,
reusing existing isolated-PG/subprocess patterns. V08 remains Partial pending results
and uncovered deployment cases. No additional CI/public attempt or owner acceptance implied.


## Local process-crash recovery checkpoint —2026-11-22

Added four actual child-process kill cases using the existing marker/role/source-write
patterns. First targeted run7passed/2failed due to a new harness call missing source
scope; corrected all four affected cases passed. Five related existing concurrency,
pool-restart/takeover and rollback cases passed in the initial run and were not rerun
without impact. Source scope rejection is preserved; no production changes. Scoped
Ruff/format and MYPYPATH=src mypy passed; the first440import-resolution errors are
preserved as diagnostic failure. Evidence: evidence/process-crash-recovery-checks.txt.

Review of the new diff found no remaining correctness/safety finding: tests use real
PostgreSQL transactions/runtime roles, kill before/after commit, clean children in
finally, and require exact durable proof/dedup/source-revision results. The test CHILD
constant is a fixture only; PostgreSQL remains the business authority. V08 remains
Partial for deployment/failover coverage. V06/V12/V14–17/V20 retain outstanding matrices,
public-source fill and owner/independent acceptance. V19 passed only on published
runtime head e193fd32; these new local tests have not been published or run in CI.
Batch/Release remain Pending Full Validation. Not Completed or ready to merge.


## Local deployment compatibility checkpoint —2026-11-22

Owner authorized continuation of the remaining deployment/mixed-version matrix.
Added21cases in test_candle_closure_compatibility.py; all passed with four related
existing activation/default-OFF/roles/history-migration regressions (25selected).
Rejections preserve activation state; separate runtime-role subprocesses distinguish
OFF legacy-style writes, ON rejection and current v1 proof publication; deactivation
retains evidence while consumers fail closed. Scoped Ruff/format and strict mypy
passed2files. Initial one-line Ruff diagnostic corrected before tests. See
 evidence/deployment-compatibility-checks.txt for matrix, fingerprints and limits.

Review found no correctness/security/statelessness issue in the added tests. No runtime
or approved business-rule change. V14 remains Partial because the legacy SQL fixture
is not historical-binary certification and cannot prove actual deployed process
inventory/drain/restart-disable policy. Existing process-crash tests and this matrix
remain unpublished/local; e193fd32CI success does not cover these new files.
No new CI or public campaign was run. Owner/independent acceptance, remaining Feature
gates and public actual fill remain open. Batch/Release Pending Full Validation.


### Authorized publication of local recovery/compatibility tests —2026-11-22

Owner permits one commit/push and one additional required CI run for both reviewed local
test batches. Fingerprints in process-crash-recovery-checks.txt and deployment-compatibility-
checks.txt match the staged Python files. Prior e193fd32CI success remains historical;
new candidate is not CI-Passed until its required workflows finish. No tests rerun merely
for publication because source/test dependencies and environment contracts are unchanged.
No merge, public campaign or owner acceptance waiver. Final CI result will be reported
with SHA/run links; other Partial gates and Batch/Release stay unchanged.
