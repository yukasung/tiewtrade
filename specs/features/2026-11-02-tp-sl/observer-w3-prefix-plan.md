# NC-F17-OBS-05 — W3 prefix diagnostic ครอบคลุม worker restart

สถานะ: **Approved — implementation/tests; owner review/refactor ก่อนหนึ่ง campaign**
วันที่: 2026-11-16
ขอบเขต: amendment F17 harness diagnostic ใน branch เดิม ไม่ใช่การเปลี่ยนเกณฑ์ W3

## หลักฐาน / สมมติฐาน

[OBS01](evidence/endurance20-20261115/w3-obs01-result.md) หยุดที่measured1972.8285s
หลังWORKER_RESTARTที่1800s(recovery33.194s); samplerTimeoutก่อนactivity/locksครบ.
ความใกล้กันของเวลาไม่พิสูจน์ว่าrestartทำให้ล้ม; อาจเป็นโหลดสะสมหรือเหตุการณ์ชั่วคราวอื่น.
[OBS04](evidence/endurance20-20261115/obs04-result.md) 600commands/10capturesPassed,
cold64.446ms/reusedสูงสุด14.305ms แต่เป็นSMOKE5นาที ไม่มีrestart.
profile_internal.manifestระบุSMOKEเป็นdiagnostic internal commands ส่วนW3เป็นauthenticatedHTTP.
ดังนั้นแค่ขยายSMOKEเวลาอย่างเดียวไม่ใช่การจำลองW3เส้นทางเดิม.

A แนะนำ: สังเกตprefix40นาทีของW3เดิม พร้อมtiming/naturalและscheduledsampler.
B หยุดทดลองและเก็บIncompleteเดิม: ไม่ใช้เวลาเพิ่มแต่ยังปิดW3ไม่ได้.
ไม่เปลี่ยนlease/collector timeoutเพื่อให้ผ่าน และไม่เริ่มfull4hโดยอัตโนมัติ.

## Requirements

- Opt-in `--observer-w3-prefix` defaultoff เฉพาะPAPER_INTERNAL20_V1/W3.
  เปิดlease/fence/fail-fast/clock-recoveryตามOBS01 และtiming/scheduledเฉพาะทางนี้.
  ไม่อนุญาตSMOKE,worker-only,controlleddelayหรือdiagnosticsอื่นผสม.
  OBS03/OBS04SMOKEและW3ที่ไม่มีflagใหม่ต้องทำงานเหมือนเดิมทุกประการ.
- คงW3profile/config/faultscheduleต้นฉบับ:20owners/400baselineorders/20workers,
  282cyclesต่อowner/28200plannedcommandsที่2/s,source/heartbeat cadenceเดิม,
  authenticatedfixtureHTTP→inbox→bridge→worker,session/CSRF/RLS/riskจริง.
  ไม่อ้างว่า28200คำสั่งจะครบใน40นาที รายงานoffered/admitted/completed/inflightจริง.
- คงschedule14400sต้นฉบับและfaultoffset1800sWORKER_RESTART30s.
  ตั้งdiagnostic cutoffที่measurement start+2400s; faultที่3600sขึ้นไปNotRun.
  ไม่เร่งเวลาfault ไม่skipรอบแรก ไม่เปลี่ยนduration/profileเพื่อรายงานW3Passed.
- คงclock recoveryที่อนุมัติของOBS01(สูงสุด1event/1retryและrollbackproofเดิม),
  ไม่เพิ่มretryใหม่/lease reacquire/ส่งpublicationหรือorderทดแทน.
  lease5s/collector1s/statement500ms/lock200ms/rowlimits/financialguardsเดิม.
- Natural samplerคงtriggerstatementช้า≥1s/cadence0.25s เก็บtimingตามOBS03
  แยกactualpublicationidentityจากscheduledfixture; max64recent+failed/countsเดิม.
- Scheduled capture40ครั้งที่offset30,90,...,2370s ใช้measurementmonotonicเดียวกับW3;
  collectorinstance/fixturePIDแยกเหมือนOBS04 เก็บทั้งหมดแบบbounded40records.
  deadlineแต่ละcaptureถึงmin(slotถัดไป60s,2400s)ครอบfixture/session lifecycle;
  คงcollector1sภายใน ไม่มีcatch-up/retry. Missing/failed captureให้Incompleteและfail-fast.
- รายงานphase timings/late slots/looplag aggregate และช่วงก่อนrestart/ระหว่างfault/
  หลังrecoveryแยกกัน โดยใช้faultwindowจริง ไม่อ้างlooplagเป็นper-query attribution.
  timingsรวมdriver/network/scheduling; sessionexitไม่ใช่servercommitล้วน.

## Plan / reuse

1. Reuse `profile_observer_scheduled.py` schedule/lifecycle/primaryexception,
   `profile_observer_timing.py`, `FenceObservation` SQL/monitor และ
   `LoadLeaseObserver` failure/witness/receipts. ส่งschedule/windowแบบexplicit
   validatedconfiguration ไม่เปลี่ยนglobalconstantsหรือpatchข้ามtask.
2. ต่อparent-onlyflagและmeasurementcutoffใน `profile_workload.py` /
   `remaining_paper_campaign.py` โดยใช้with_publisher/supervision/joinเดิม.
   แยกplanned diagnostic cutoffจากfailureด้วยreasonที่ตรวจได้ ไม่ใช้catch-all
   TimeoutErrorเป็นความสำเร็จ. หากerrorแข่งกับcutoff ให้errorมีลำดับเหนือcutoff.
3. ที่cutoffหยุดการเริ่มงานใหม่และยุติproducer/faulttasksผ่านownedcleanupเดิม;
   ไม่ยอมเริ่มfaultที่อยู่หลังcutoff. เก็บpartialcounters/inflightและindependent
   committed cursor/owner/generationก่อนลบฐาน ไม่ถือinflightว่าrollbackหมด.
   ไม่มีreplacementcommandsเพื่อให้จำนวนเต็ม. เก็บsnapshot/resourceที่มีตามจริง.
4. Diagnostic resultแยกจากW3acceptance: Completeได้เฉพาะสังเกตครบ2400s,
   40scheduledcapturesครบ, natural evidenceไม่ขาด, firstrestart/recoveryพิสูจน์ได้,
   bindings/evidenceIO/cleanupครบ. WorkloadW3ยังIncompleteเพราะไม่ครบ4h.
   Finaltail/fullfinancial/global/positions/replayที่ไม่ได้ตรวจให้NotRun.
   Pool/resourcefailuresจากstopต้องเก็บและจัดgradeตามเดิม ไม่waiveเป็นPassed.
   หากหลักฐานบังคับขาดให้diagnosticIncompleteแม้เกิดที่plannedcutoff.
5. ก่อนsourceบันทึกimplementationbinding; targetedchecks → ownerreview → fixes →
   ownerrefactor/affectedchecks ก่อนหนึ่งcampaign. ไม่ข้ามreviewgate.
6. Pin candidate/config/migrations/faultschedule/runnerก่อนonepreflight120s/7samples;
   ไม่ผ่านหยุดไม่วนรอ. ใช้ownedemptyDB/Redisและsimulatedaccountsทั้งหมด.
   งบรวม3600sจากpreflight รวมcleanup สำรองcleanup120s; คาด45–50นาที
   ไม่รวมพัฒนา/tests/review. ติดตามต่อเนื่องจนผลและcleanupเสร็จ.
7. Cleanupต้องjoinownedtasks/processes ตรวจconnections/locksและownershipก่อนลบ;
   ถ้าปิดไม่ได้retain/report ไม่force drop/killหรือหยุดบริการอื่น ไม่แตะowner/Live.

## Validation

Feature:
- flagmatrix/defaultSMOKE/W3regression; sharedschedulevalidationและmemorybounds40;
  exactoffsets/clock, missed/hungslot, noearlycapture/no-catch-up.
- cutoffก่อน/ระหว่างfault/capture/inflight; simultaneousrealerrorชนะplannedstop;
  cancellation/ambiguouscommit/IO failure/primarypriorityและindependentwitness.
- nofaultหลังcutoff/no-next-phase; cleanupทั้งworker generations/natural/scheduled/
  pools/fixturetransaction; receiptระบุpartialอย่างตรงไปตรงมา ไม่อ้างW3Passed.
- PostgreSQLจริงสำหรับrollback/lockrelease/poolreturnและknownblocker regressions;
  targetedauthenticatedintake/supervision testsที่กระทบ ไม่ใช้mockแทนฐานจริง.
- Ruff/format/mypyเฉพาะกระทบ; reuseหลักฐานเงิน/productionที่ยังvalid.
Diagnostic:
- 2400s/40captures/firstfault actualwindow/recovery/evidence/cleanupตามข้อ4;
  รวมmedian/maxและfailedทุกอัน แยกcold/reusedและก่อน/หลังfault ไม่ตัดoutlier.
- ถ้าไม่เกิดซ้ำ: รายงานไม่พบในprefix40นาที ไม่ยืนยันว่าสาเหตุแก้แล้วหรือผ่าน4h.
- ถ้าเกิดซ้ำ: รายงานphase/current/lastcompletedและassociationที่พิสูจน์ได้;
  ไม่มีblockerrowsห้ามสรุปว่าSQLlockเป็นสาเหตุ.
Batch/Release: เก็บW3Incompleteเดิมและผลก่อนหน้าทั้งหมด F17ไม่Completed.

## Approval / stop

OBS04อนุมัติหนึ่งSMOKEแล้วหยุด/report ซึ่งใช้แล้ว. OBS05เพิ่มduration/fault-context/
intakeและplannedcutoff จึงต้องอนุมัติขอบเขตใหม่ก่อนsource/experiment.
หลังหนึ่งcampaignหยุดพร้อมหลักฐาน/ข้อเสนอ ไม่รันซ้ำ/แก้publisher/เริ่ม4hอัตโนมัติ.
ไม่มีcommit/push/CI/mergeในขอบเขตนี้. เอกสารนี้ยังเป็นข้อเสนอ ไม่ใช่ผลตรวจรับ.

## Implementation binding ก่อนแก้ source — 2026-11-17

เจ้าของapproveแล้ว. ใช้explicit scheduleของScheduledObservationสองชุดเท่านั้น
(SMOKE10/W3prefix40) ไม่แก้globalค่าเดิม. เพิ่มowned cutoff taskเริ่มจากmeasurement
clockและตรวจในwith_publisherหลังrealerrors/failurechecks; joinoperationก่อนplannedstop
และไม่กลืนerrorจากcancellation cleanup. ใช้exceptionชนิดเฉพาะสำหรับplannedcutoff
เท่านั้น ไม่catch TimeoutErrorทั่วไปเป็นComplete.
_runบันทึกpartial resultก่อนcleanupแล้วคืนcode2 (W3Incompleteเสมอ); หลังปิดcontext
จึงตรวจpool/witness/receiptsและสรุปdiagnosticแยกจากW3. Failureแข่งcutoffมีpriority.
Faultscheduleเดิมไม่แก้; ส่งcutoffก่อนเริ่มfaultแต่ละeventเพื่อห้ามfaultหลัง2400s
แม้eventloopกลับมาหลังdeadline. reusepool/cleanup/clockrecovery/HTTPเดิม.

### Parent fixture correction ก่อนแก้ test

รอบunit30Passed/1Failed: mock_parentแทนfaultloaderด้วย1cycleของfixtureเล็ก
แต่prefixต้อง282cyclesจริง. คืนloaderต้นฉบับเฉพาะtestนี้เพื่อใช้approvedscheduleจริง
ไม่เปลี่ยนruntime/เกณฑ์ และเก็บผลล้มเดิม.

## Implementation checkpoint — 2026-11-17

[Evidence](evidence/endurance20-20261115/obs05-implementation.md):400targeted/realPGPassed,
static7files/independentcleanupPassed. prior30Passed/1fixtureFailedเก็บตามจริง.
รอowner review code ก่อนrefactor/onecampaign; preflight/campaignNotRun.

## Review M1 fix — ก่อนแก้ source (2026-11-17)

เจ้าของสั่งแก้ไข: fault injectionยืนยันresource taskล้มในfinallyหลังcutoff
แต่gather(return_exceptions=True)กลืนerrorและไม่มีreceipt.
ใช้engineering authorityแก้เฉพาะprefix cleanup: joinทุกownedtaskและตรวจผลจริง
แยกcancellationที่cleanupร้องขอจากunexpected cancellation/error.
เก็บerrorsตามลำดับ ไม่หยุดcleanupของworker/intake/poolsเพราะtaskแรกเสีย
บันทึกชนิดerror/phaseลงreceiptและลดdiagnosticเป็นIncomplete; preserveoriginal
exceptionถ้ามี ไม่เผยmessage/secret. EvidenceIO failureแนบกับprimaryและยังล้างต่อ.
ตรวจresource/position/fault/publisher cancellation errors,หลายerrors,primarypriority,
IO failureและnormalcancel พร้อมregressions/realPGเดิมก่อนรอownerrefactor.

### OBS-05 M1 fix checkpoint — 2026-11-17

[Fix evidence](evidence/endurance20-20261115/obs05-m1-fix.md): 170 targeted/real-PG tests Passed;
Ruff/format/mypy 3 files Passed; independent cleanup Passed. Initial mypy failure retained
in evidence. Cleanup errors now invalidate prefix diagnostic and preserve primary errors.
Campaign Not Run; waiting for owner refactor instruction. W3/F-17 status unchanged.

### Owner-authorized M1 refactor — before source, 2026-11-17

Extract receipt publication into a private helper in profile_observer_prefix.py, separating
task/resource finalization from evidence writing. Reuse existing save callback and first-error
policy; preserve order, cancellation handling and all exceptions. No new abstraction or
production changes. Recheck prefix tests/static; retain prior real-PG regression evidence.
Then proceed to the approved one preflight/campaign, with its original stop conditions.

### OBS-05 authorized refactor checkpoint — 2026-11-17

[Refactor evidence](evidence/endurance20-20261115/obs05-m1-refactor.md): 40 affected tests
and Ruff/format/mypy Passed. Proceed to the approved one preflight/campaign.

### OBS-05 one campaign — stop/report, 2026-11-17

[Result](evidence/endurance20-20261115/obs05-result.md): 2400s observed, 40/40 scheduled
captures, worker restart recovered 32.989s; no natural trigger/timeout. Diagnostic
Incomplete: parent ENGINE borrowed=1 at dispose (final zero); 40 worker pools Passed.
Cleanup independently Passed; total 2558.487s. Prior W3 Incomplete/F17 Pending retained.
Recommend short cutoff/borrow-lifecycle investigation before another campaign.
Approved one campaign consumed; stop/report, no automatic repeat or four-hour run.

## CUT-01 — owner-authorized continuous correction through W3 (2026-11-17)

Owner explicitly requested fixing cutoff borrowing and proceeding through four-hour
validation without repeated questions. This supersedes the previous one-campaign stop
for this correction/execution sequence only; no acceptance/security/financial relaxation,
Live operation, publication or infrastructure changes are authorized.

Evidence: OBS05 parent ENGINE final_disposal_checked_out=1, final checked_out=0;
all 40 worker receipts and independent cleanup passed. Hypothesis to test: group gather
propagates cancellation, then a second cancel in finally interrupts session cleanup.
Do not treat this hypothesis as established historical cause without reproduction.

Reuse existing finish_observed_cleanup supervision and bounded_map/scheduled-cycle
ownership. First add deterministic cancellation/cleanup regression; then real-PG proof
that transactions/locks and borrows are released before disposal. Correct only proven
harness lifecycle bugs, preserving primary errors and recording secondary cleanup errors.
No sleeps/retries/waivers to hide outstanding borrows; no production session changes.
Run affected regression/static checks, review and scoped refactor as part of this explicit
continuous instruction. Before workload pin final source/config/schema/runner and run
original one preflight; failure stops, never loops until host becomes ready.

After short real-PG checks prove cleanup, run one original PAPER_INTERNAL20_V1 W3:
20 owners/400baseline/20workers/282cycles per owner/28200commands, 14400 measured
seconds, original seven fault schedule, approved clock recovery and fail-fast observer.
No prefix cutoff/scheduled diagnostic modification to acceptance. Existing timing,
financial/final-tail/snapshot/rebuild/resource/pool checks remain required. Expected
4h15–30min; use existing 18000s overall budget with reserved owned cleanup. Keep prior
Incomplete results. If run fails, capture evidence/cleanup then stop; no automatic long
rerun, criteria change or claim F17 Completed. Stop/report after this campaign.

CUT-01 reproduction before fix: both bounded_map(join_on_error=True) and scheduled
cycles sent a second cancellation while a child waited in its finally; 2 regression
cases Failed as expected. Fix joins owned children through existing shielded cleanup,
requests cancellation only when no request is pending, and retains child cleanup errors.
This proves a harness bug; original OBS05 exact task attribution remains unproven.

### CUT-01 correction/checkpoint — 2026-11-17

[Checks](evidence/endurance20-20261115/cut01-checks.md): deterministic reproduction
2 Failed before fix; 269 targeted/real-PG Passed after shared owned-join correction.
Review/refactor/static and independent cleanup Passed. Owner authorized proceeding
without repeated questions to one original20 W3 after unchanged preflight.

### CUT-01 four-hour result — 2026-11-17, stop/report

[Evidence](evidence/endurance20-20261115/cut01-four-hour-result.md): full14400s/28200
commands,7faultsRecovered,4820snapshotreadsReturned,finaltail49.641s. Incomplete:
first-owner replay read_execution_inputs exceeded60s; remaining19/finalfinancialoracle
NotRun. Allborrows0beforedispose,80workerpoolsPassed; parentFailed from replay timeout
cancellation, not waived. Cleanup independentlyPassed. F17notCompleted; noautorerun/Git.
Next proposed short replay-read diagnosis with existing observer/representative fixture.
