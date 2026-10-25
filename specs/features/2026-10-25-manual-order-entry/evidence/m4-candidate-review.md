# M4 — Local candidate review and validation

วันที่:2026-10-25 · branch `feat/f16-manual-order-entry` · uncommitted working tree

**สถานะ: Partial — ยังไม่พร้อม merge/Completed.** Required CI บน final commit
ยังต้องผ่านก่อน merge; local Chromium และ Docker gates ผ่านแล้วตาม follow-up ด้านล่าง.
V-18 Pending Dependency F-18; V-20 Pending Full Validation ที่ release checkpoint.

Ready for Code Review แจ้งใน session ทันทีหลัง implementation ครบ โดยสรุป code/tests/
pending/risks ก่อนเริ่ม formal review. ไม่ได้ขออนุมัติ implementation ซ้ำและไม่มี Git mutation.

## Findings — reviewed diff/new files และ relevant dependencies

ตรวจ schema/RLS/audit, inbox/replay/views, claim/bridge, F-15 dispatch/worker, API/auth/
throttle/routing, generated contracts, UI/session/journal/queries/navigation, tests/harness/CI
และกฎ Money/Quantity/catalog/wallet reset ที่ใช้ร่วมกัน. ไม่เพิ่ม refactor นอก scope.

| ID / Severity | File/location / Problem | Impact | Fix / verification |
|---|---|---|---|
| F16-C1 **Medium** | `infra/paper_orders/views.py::_read_cursor`: JSON cursor ที่ UUID partเป็นobject/numberอาจทำให้UUID()โยนAttributeError | ผู้ใช้ส่งcursorผิดรูปแล้วได้500แทนcoded refusal | ตรวจทุกpartเป็นstrก่อนparse; เพิ่มHTTP regression6ชนิด รวมnull/bool/object/list; ไม่เผยcursorหรือSQL |
| F16-C2 **Medium** | `services/engine/manual_order.py::run_manual_order_round`: scanfailurepropagateก่อนF-15; scan/deferไม่มีlocaltimeout | inboxใหม่อาจขวางการดูแลออเดอร์/cancelเดิม | จำกัดscan/defer5sและจับscanoutageแยกจากfinancialround; logไม่มีexception/payload; เพิ่มregressionscanfailureไม่หยุดloop |
| F16-C3 **Medium** | `layout/AccountHeader.tsx`: modebadgeอยู่แต่ในcontent | เลื่อนหน้าแล้วอาจไม่เห็นPAPER/LIVEตามtrading-safety | แสดงbadgeในstickyheaderจากpageที่server/clientแยกไว้; ไม่เปิดmodeจากpayload |
| F16-C4 **Low** | `PaperOrderList.tsx`/sidebar: mobiletableแคบจนแตกตัวอักษร; routeที่มีslashไม่มีiconmapping | อ่านจำนวน/สถานะยากและไม่ตรงtemplate | ใช้BasicTableOne horizontal-scroll/nowrap/spacing, sharedtradeicon; Modalcallbackstableและคืนfocus; image/browserinspection |
| F16-C5 **Medium** | `trade_views.py::trade_snapshot`/PaperTradePage: มีsnapshotclockแต่ขาดเวลาของpriceobservationเดิม | ไม่เห็นอายุsourceเมื่อfeedเก่า | เพิ่มoptionalmarket_observed_atจากreceived_atจริงและแสดงแยกจากsnapshot; HTTPtestหยุดfeedแล้วยืนยันเวลาราคาเดิมไม่ถูกเปลี่ยนเป็นเวลาปัจจุบัน |
| F16-C6 **Medium** | `ManualOrderForm.tsx`: เปลี่ยนpairแล้วจำนวน/ราคาเดิมยังอยู่ | อาจส่งจำนวนที่ตั้งใจใช้กับอีกasset | ล้างamount/priceเมื่อเปลี่ยนpair; regressionยืนยันunits/draftไม่ถูกใช้ต่อโดยเงียบ |
| F16-C7 **Medium** | `PaperTradePage.tsx`: terminalแล้วdraftเดิมยังส่งด้วยkeyใหม่ได้ทันที | fast second clickอาจกลายเป็นคำสั่งใหม่ที่ไม่ตั้งใจ | remountlocalformด้วยcompletedattemptidentityเมื่อรู้terminal; ต้องกรอกใหม่ก่อนส่ง; UNKNOWNไม่ถูกล้างและretryยังใช้journalเดิม |

Findings ข้างต้นแก้ใน scope แล้ว; final verification/results อยู่ส่วนถัดไป.
ไม่พบ Critical/High ใน F-16 diff. การไม่มี findings ระดับนั้นไม่ใช่การผ่าน validation/CI.

Review F16-R1/R2/R3 จาก document review มี runtime evidence แล้ว: revisionเดิมถึงF-15
ก่อน/หลังremove→re-add; downstreamcommandrejectionอ่านได้แม้ไม่มีorderrow; write-before-send,
reload/keylookup/discoveryและsame-keyreplayกับcommitจริง. ดูM1/M2/M3และbrowsertests.

## Requirements/plan coverage

| Requirements | Coverage |
|---|---|
| RQ-1/2 | strictSpotvariants, exactMoney/Quantity, formหน่วยถูกต้อง, generatedcontracts; ไม่เพิ่มสูตรเงิน/float/plainDecimal |
| RQ-3/4/5 | ownerRLS/compositeFKs, authenticatedroutes, owner/PAPER/episodequerykeys, แยกPaper/LiveURLsและLiveไม่มีmutationbinding; Paperใช้F-15และisolationgateห้ามLiveexecutor/credentials |
| RQ-6/7 | ManualAccountPolicyตรวจauthoritativeheldหลังreservationsและaccountuse; coremodeparity; bridge/executionrecheck; productionriskintegrationยังรอF-18 |
| RQ-8/9/10 | catalogrevisionpin/executionfences; fingerprint/replayคงidentity; cancelใช้authoritativefill; APIเขียนdurableinbox/auditก่อนengine/F-15และrollbackเมื่อบันทึกไม่ได้ |
| RQ-11/12 | fingerprint/replay/lease/CAS, immutabletransferresult, processkill/commit-ackloss, journalrecovery; intake/command/orderแยกสถานะ ไม่optimisticfill/cancel |
| RQ-13/14/15 | readiness/เวลา/unavailableจริง, Livedirect-exchangeguidance, template/sharedcontrols, th/en/theme/responsive/keyboard; รูปและfinalchecksด้านล่าง |
| RQ-16/17 | audittypedactions+DBCHECKs, append-only/RLS/owner/mode, rollback/crash/catalog/reset/cancel/fill/concurrency tests; ไม่มีLiveorder |
| RQ-18 | ProductionAPI/engineคงpolicy=None; NEW503ก่อนสร้างexecutableinbox; testpolicyเฉพาะtestsapp; ไม่มีenvironmentbypass |

M1–M3 implementationตามapprovedplan. M4เป็นlocalcandidate checkpoint ไม่เปลี่ยนapproved
scope/criteria; ไม่ถือtestpolicyแทนV-18และไม่เลื่อนcorrectnessไปreleaseworkload.
ไม่มีPNL/leverage/margin/liquidation/Livevenue/WebSocket-order-executionlogicใหม่ในdiff;
financialmatching/fees/ledger/positionยังใช้F-15เดิมและต้องผ่านsafetyregressionที่เกี่ยวข้อง.

## Test ledger / failures and recovery

Environment: PostgreSQL isolatedcompose`tiewtrade-f16`, fresh`tiewtrade`สำหรับmigration/full
regression; E2Eใช้`tiewtrade_e2e_f16`แยกDBและports; Redis56379. ไม่มีLiveorders.

- Full frontend candidateแรก:283 passed/25.06s. Final affected checks:37 passed/3.91sก่อน
  presentationfollow-up. ไม่บวกจำนวนซ้ำและไม่อ้างจำนวนเก่าเป็นfinalfullsuite.
- Browserก่อนขยายภาพ:5 passed/36.4s รวมrealAPI/DB/bridge/F-15; finalfollow-upบันทึกด้านล่าง.
- BackendfullattemptแรกบนDBที่มีM2history:13 failed/45 passed/63.19sก่อนinterrupt.
  Migrationfailuresเกิดจากsafetyguardปฏิเสธdowngradeที่มีhistory; ใช้freshisolatedDBแก้environment.
  Secretcanaryเดิมไม่รู้จักnewpathparamsจึงเติมparams/expected404ให้ครอบendpointใหม่โดยไม่ลดcanary.
- Freshfullattempt:123 passed/139.58sแล้วsetuperrorเพราะขาดTIEWTRADE_TEST_REDIS_URL;
  ตั้งtestRedisURLตามfixture ไม่เปลี่ยนproductionconfig/testthreshold.
- Resumeจากexactcollectionboundary:29 passed/48.85sแล้วchartretentiontesttimeoutSQLSTATE57014.
  รันกรณีนั้นแยกเมื่อไม่มีbrowserworkload:1 passed/2.81s; เก็บผลtimeoutเดิมไว้ ไม่แก้chartนอกscope.
- Resumeส่วนถัดไป:1847 passed/493.19sแล้วlegacyengine-preferencepermissionassertionล้ม.
  F-16approvedgrantให้อ่านuser_id/useแบบowner-bound; ปรับtestให้ยังปฏิเสธcreated_atสำหรับengine,
  บทบาทอื่นยังอ่านไม่ได้; read-only/ownerisolationregressionในmanualsuiteยังคงอยู่.
- Finalresumeเลือกส่วนที่ยังไม่ผ่านและaffectedtestsที่sourceเปลี่ยน; prefixที่ยังvalidใช้ต่อ
  ตามtesting§7. Temporaryrunnerตรวจnodeidboundaryและบันทึกselected/reusedidentitiesก่อนรัน;
  ไม่commit skiplistหรือเปลี่ยนpytestcollectionของrepo. RequiredCIยังต้องรันfullsuiteตามปกติ.

เวลาข้างบนคือpytestelapsedที่วัดได้; ช่วงอ่าน/เขียน/reviewไม่ได้วัดแยกครบและไม่แต่งเวลารวม.


## Final local results

| Check | Result |
|---|---|
| Final backend remaining+affected regression | **1427 passed /240.19s**, with **1917 valid reused cases**; collection ledger covered3344 cases. All previous failures that affected F-16 were fixed and retested. This was composite coverage, not a claim that one uninterrupted full command passed. |
| Price observation contract follow-up | **58 passed /41.08s** for manualAPI/inbox/read/input dependencies after source timestamp addition; **1 new test passed /0.69s** proving the original received_at survives feed disconnection. Final backend collection3345 cases is covered by the prior3344 plus this new test; overlapping58 are not added again. |
| Final frontend full candidate suite | **286 passed /45.09s**,31 files; after source-time/presentation follow-ups, affected37 passed/7.48s and final trade-page/a11y13 passed/1.67s. Unchanged full-suite evidence remains valid; no server state is copied into component state. |
| Chromium real Paper flows | **5 passed /34.4s**; language/screenshot follow-up: existing owner-switch/login case passed in a1passed/1failed17.1s run. The failure was a test probe expecting a specific DB exception subclass: PostgreSQL57P01 maps to generic InfraError in the existing translator. Probe now independently verifies the terminated PID is absent from pg_stat_activity. New disconnect-before-commit case **1 passed /13.0s**; modified receipt-loss/back/forward case **1 passed /9.0s**. All6 scenarios have passing final evidence; no claim of a single6-test invocation. |
| Final backend static checks | Ruff check/format, strict mypy496 files, import-linter7 contracts passed. |
| Final frontend static/build | lint, typecheck, production build passed; final build1.10s after completed-draft/pair-unit fixes. |
| Generated contracts | Production OpenAPI export byte-equal to backend/openapi.json; regenerated TypeScript byte-equal to src/api-types.ts. |
| Config / whitespace | docker compose config --quiet and git diff --check passed. |

The reused-node ledger and exact collection boundaries were checked by temporary runners;
all affected source/tests were rerun. These runners are not production files and do not change
CI selection. Logs are environment-local `/tmp/f16-m4-*.log`; earlier M1/M2 evidence remains
valid where its inputs/dependencies did not change. Original failed/partial runs above are
preserved, including the transient chart timeout; an isolated pass does not erase that history.

ภาพ final อยู่ [ui/](ui/), ครบThai/English×light/dark×375pxmobile/1440pxdesktop.
ตรวจภาพจริงหลังแก้tableและsidebaricon, headerPAPERอยู่ในstickyheader; screenshotsเลื่อนกลับtop
ก่อนcaptureเพื่อไม่ให้stickyheaderไปอยู่กลางภาพ. Browserยืนยันtableoverflowอยู่ในcontainer,
ModalEscape/returnfocusและpageไม่ล้นจอ. Message-layerlanguagechangeใช้layout rerenderตาม
breakpointในtest; ไม่เพิ่มlanguagepicker/appearanceนอกscope. Statusannouncementsใช้polite/
atomicเฉพาะintake/command/orderstates, ไม่ประกาศsnapshotclockซ้ำทุกpoll.

## Validation coverage / remaining gates

- V-1–V-17: **Passed for local F-16 development composition**, using approved test policy
  only where required. Persistence/API/core/role/property/concurrency/crash tests plus the
 6 browser scenarios jointly cover the boundaries; none certifies production risk readiness.
- V-15 coverage uses the approved template paths, shared controls and eight final screenshots;
  keyboard/labels/disabled/loading/error/status tests cover accessibility changes. Financial
  display remains exact server text, no browser arithmetic.
- V-18 remains **Pending Dependency — F-18**. NEW production admission stays503/policy=None;
  no Live mutation/executor/credential access was introduced.
- V-19 remains **Partial**: local review/findings/checks above are complete, but existing
  Chromium suites, container/Docker gates and required CI on a final commit must still pass.
  Local results do not replace them; no commit/push was authorized or performed.
- V-20 remains **Pending Full Validation** with the original release profile/duration/thresholds;
  no shortened workload/endurance run was used as acceptance.
- Monitor the chart retention SQLSTATE57014 seen under the earlier candidate run in CI;
  the isolated diagnostic passed without changing chart code or loosening thresholds.
- No open Critical/High/code finding in the reviewed F-16 scope. No merge, production activation
  or Completed claim. Final checkpoint is M3 implemented + M4 local review/validation complete,
  pending the remaining V-19 gates and tracked dependencies.


### Final follow-ups after review

- Pair change clears the previous asset's amount/price. Terminal receipt clears the local draft
  using a client tracking identity, so a second click cannot silently create a new-key order.
  UNKNOWN and same-key retry behavior remain unchanged. Final form/trade tests: **16 passed /1.97s**,
  including one new test (final frontend collection287 cases; prior full286 reused where valid).
- Status changes announce through a polite/atomic live region; final trade/a11y tests before the
  draft fix:13 passed/1.67s. Static lint/types/build rerun after final draft fix passed.
- The DB-disconnect harness verifies the terminated API backend PID is absent from PostgreSQL,
  with inbox/order rollback and same-key recovery; it never terminates the DB server or another
  process. This helper is test-only and not packaged in the production application.
- Mypy initially requested an annotation on the helper's `alive` count; added `int`, then final
  Ruff/format/mypy passed. This annotation does not change the already-tested runtime behavior.
- Final affected browser MARKET BUY/SELL→LIMIT partial→cancel rerun after draft reset:
  **1 passed /14.6s**. Existing other browser evidence remains valid; no new financial logic.

### Deep-review remediation — closed episodes and draft scope (2026-10-25)

Owner requested fixes for two additional Medium findings after the independent review.
This is within the approved replay/reset/recovery scope; no financial rule, schema,
production admission policy, or Live execution behavior changes.

- **Closed-episode recovery:** `requests.py` checks the existing immutable, owner/wallet-bound
  episode closure only after same-key replay/fingerprint inspection under the wallet lock.
  An absent request for a permanently closed episode returns the specific
  `409 MANUAL_ORDER_EPISODE_CLOSED`. Existing receipts still replay first, including after
  reset. Random/foreign episodes and generic idempotency conflicts cannot produce this proof.
  The proof also works with production policy unavailable; it cannot admit an order.
  A lost refusal can be recovered by explicit same-key retry after reload, using the durable
  closure again. No new refusal table or invented order outcome is needed.
- **Frontend recovery:** only that exact status/code resolves the closed-episode attempt;
  generic409, lookup404 and transport failures retain UNKNOWN and the exact original payload.
  Resolution clears the unsent form and explains the refusal in Thai/English.
- **Draft scope:** form identity includes wallet/episode as well as completed/refused attempt.
  Replacing the scope clears amount/price before another submit. TanStack placeholder data
  preserves scope during pair-query transitions; the existing base/readiness/fetching checks
  still prohibit submission from placeholder data. UNKNOWN journal payloads are never rebased.

Affected validation: V-3/V-7/V-10/V-13/V-14/V-16. Existing financial matching, source,
reservation, audit, lease and reset evidence remains valid where unchanged.

Checks on the remediation:
- Backend API + complete manual inbox/bridge/recovery suite: **49 passed /37.41s** on newly
  bootstrapped isolated `tiewtrade_f16_review` database, schema0042. Includes NEW/CANCEL
  closure refusal, repeated retry with policy unavailable, foreign/random scope negatives,
  and replay of an existing receipt after reset.
- Frontend form/trade/journal/session regression: **23 passed /4.06s**. New cases cover
  definitive refusal, generic409 retention, draft reset on episode change and unchanged
  UNKNOWN retry payload after a subsequent scope change.
- Backend Ruff/format passed; strict mypy496 files passed. Frontend lint/types/build passed
  (build1.43s). No OpenAPI shape changed; response detail was already a string.
- Failed attempts retained: first frontend run10 failed because pair loading temporarily
  removed scope; fixed with guarded placeholder data. Next run1 failed due to asserting
  before TanStack's scheduled notification; regression now awaits the rendered state.
  First backend run48 passed/1 failed on the accumulated old test DB because a bounded global
  scanner batch did not reach the new request; fresh isolated DB passed all49. No production
  scanner behavior or thresholds were changed. Initial new browser test raced reload against
  its still-running reset helper and hit403; corrected its response-loss barrier before reload.

Ready for Code Review was announced before the remediation review. Review checked replay
precedence, closure ownership/immutability, fail-closed policy, form scope and preservation of
ambiguous attempts. V-19 existing E2E/Docker/required CI and V-18/V-20 remain pending as above.
- Final Chromium reset/lost-refusal/reload/same-key recovery scenario: **1 passed /8.9s**
  (scenario3.8s), using real API/PostgreSQL reset and original request replay. Confirms
  unsent draft clearing, explicit closed-episode result, no receipt creation and journal
  resolution after response loss. Both new Medium findings are resolved; no new finding
  in the affected review. No commit/push/merge or production activation performed.

### Scoped refactor — 2026-10-25

Reviewed only the latest closed-episode/draft-scope fix. Backend closure checks already
reuse one helper and remain unchanged. Frontend refactor shares journal cleanup between
terminal completion and definitive refusal, names the refused attempt key explicitly,
extracts the form identity from JSX, and reuses TanStack keepPreviousData. Error predicates,
cleanup ordering, scope identity and UNKNOWN/retry behavior are unchanged. No extra abstraction
or unrelated code change. Final affected review found no behavior change.

Validation: existing form/trade/journal/session tests **23 passed /2.55s**; frontend lint,
typecheck and git diff --check passed. No new tests needed for this behavior-preserving
refactor; backend/browser evidence remains valid for unchanged contracts and financial paths.
V-18/V-19/V-20 pending gates remain unchanged; no Git commit/push.


### V-19 local gate follow-up — 2026-10-25

Continued on the same uncommitted candidate; no production activation or Git publish.
Isolated PostgreSQL schema0042 and Redis; Node22.20.0/Chromium. No release workload,
endurance or Live orders. Existing application containers were not removed or stopped.

- **Container gate passed:** repository Compose images built, migration exited successfully,
  services became healthy/running, API `/health` returned200/statusok and frontend returned200.
  Used temporary port overrides55460/18061/15161 and project `tiewtrade-f16-gates`.
  Default Docker address pools were exhausted; temporary explicit subnet10.216.16.0/24
  allowed the gate to run. The temporary project was removed with its volumes afterward.
  Repository Compose was unchanged. Logs: `/tmp/f16-container-gates-resume.log`,
  `/tmp/f16-container-gates-network.log`, `/tmp/f16-container-gates-cleanup.log`.
- **Catalog Chromium:** `npm run test:e2e:supported-symbols` **2 passed /32.4s**.
- **F-16 Chromium:** `npm run test:e2e:manual-orders` **7 passed /35.3s**, after catalog
  tests on the same gate DB. Includes the new reset/lost-refusal/reload recovery scenario.
- **Existing Chromium remains partial:** first completed default run **11 passed/7 failed
  /2.3m**. Diagnostic retry of the7 failures: **2 passed/5 failed /1.3m**. Initial interrupted
  run had incorrect browser origins; corrected before the completed runs. Some failures
  occurred in F-12 seed preparation (`F12_FIXTURE_REJECTED`), while endpoint diagnostics
  also showed504 `CHART_DEADLINE_EXCEEDED`; these are not counted as passes.
- **One F-16-related test fix:** the chart test's broad `/orders` URL pattern falsely matched
  the newly imported Vite module `/src/components/OrderStatus.tsx`. Added route boundaries
  to preserve the prohibition of actual orders/trading-account-use/indicator requests and
  Binance access without matching that source filename. No application behavior changed.
  On a fresh schema0042 DB, targeted chart-pane/live-snapshot run: **1 passed/1 failed
  /18.4s**; the chart-pane assertion now passes. Frontend lint/types and diff check passed.
- **Remaining chart blocker:** live-snapshot recovery still fails on the fresh DB.
  Repeated that case with backend sources extracted from base commit `f6bd712`, using
  verified `PYTHONPATH=/tmp/f16-baseline-review/backend/src`: **1 failed** at the same
  READY-status assertion. This comparison uses the current frontend and schema0042;
  it is evidence that removing F-16 backend changes does not resolve the failure, not a
  complete historical checkout result. Direct actual-role `read_live` passed in0.08s;
  a diagnostic TestClient request returned200/NO_DATA. These do not prove the failing
  live-preview/browser path healthy. Root cause remains unresolved; do not relax deadlines
  or suppress the failing tests. Relevant existing paths are
  `frontend/e2e/candlestick-chart.spec.ts:180,200,242,255` and
  `backend/src/tiewtrade/services/api/chart_routes.py::live`.
- Re-running the chart fixture after catalog/manual suites can see a changed catalog;
  one diagnostic seed stored1000 rather than its required2000 rows. The final targeted
  comparison therefore used a fresh separate database. The first baseline extraction
  attempt used the wrong working directory and is excluded as baseline evidence.

Logs retained locally: `/tmp/f16-existing-e2e-corrected.log`,
`/tmp/f16-existing-e2e-chart-retry.log`, `/tmp/f16-chart-request-guard.log`,
`/tmp/f16-chart-clean.log`, `/tmp/f16-chart-baseline-confirmed.log`,
`/tmp/f16-catalog-e2e.log`, `/tmp/f16-manual-gate-e2e.log`.
Generated F-10/F-12/F-37 screenshots were archived under `/tmp/f16-gate-generated-images`
and previous tracked evidence restored; only F-16 screenshots remain in feature evidence.

**V-19 remains Partial:** four chart cases still lack passing evidence, and required CI
on a final commit has not run. No additional application-code change was made to the
existing chart subsystem. V-18 Pending F-18 and V-20 Pending Full Validation are unchanged.


### Resumed chart verification — 2026-10-25 (Asia/Bangkok)

Owner authorized continuing the chart investigation. The previous temporary runner/log
files were no longer present, and Docker plus the dedicated F-16 PostgreSQL/Redis were
stopped. Restarted Docker and those two existing F-16 test containers; recreated only the
temporary environment runner and Node22.20.0 runtime. Did not stop or change other projects.
Used the existing isolated `tiewtrade_e2e_f16_clean` database at schema0042, explicit chart
flags/browser origins and actual runtime DB roles. No application source change this turn.

Diagnostics using the existing seed/preview fixture and real TestClient session returned
HTTP200/STALE for the aged preview: pair check0.001s, read_live0.037s, session check0.002s.
Then the real Chromium live-snapshot recovery case passed **1/1 /6.8s**, including newly
seeded preview READY → disconnect → recovery → READY. These measurements only describe
this run; they do not establish the root cause of the prior504 failures.

The complete existing Chromium gate, `npm run test:e2e`, subsequently passed
**18/18 /1.7m**, including all four previously outstanding chart cases, with unchanged
application code, deadlines and test assertions (other than the route-boundary correction
already recorded above). No tracing instrumentation was enabled in these browser runs.
Raw output is retained in [2026-10-25-existing-e2e-passed.txt](2026-10-25-existing-e2e-passed.txt).
Previous failures remain in this ledger; do not describe their cause as proven or claim
that a chart production defect was fixed. The earlier broad source-URL regex false positive
remains the only chart test correction. Its lint/typecheck evidence remains valid because
no source code changed since that check. Final git diff --check passed.

Generated F-10/F-12 screenshots were archived outside the repository and restored to the
previous tracked versions. Reused passing catalog2/2, manual-order7/7 and Docker evidence;
their code/contracts were unchanged, so no additional rerun was needed.

**Local V-19 gates now have passing evidence. V-19 remains Partial pending required CI on
an explicitly committed/pushed candidate.** Prior intermittent504/fixture failures remain
a reproducibility risk to monitor in CI; this run does not justify relaxing deadlines or
skipping tests. V-18 Pending F-18 and V-20 Pending Full Validation are unchanged. No commit,
push, merge, release workload or Live order was performed.
