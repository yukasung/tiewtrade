# NC-F17-OBS-04 — Scheduled sampler ขณะรับโหลด 20 บัญชี

สถานะ: **Approved — implementation/tests; review/refactor ก่อนหนึ่ง campaign**
วันที่: 2026-11-16
ขอบเขต: amendment diagnostic ของ F-17 ใน branch เดิม ไม่ใช่ feature trading ใหม่

## หลักฐาน / ทางเลือก

[W3 OBS-01](evidence/endurance20-20261115/w3-obs01-result.md): sampler เริ่มหลัง price_renew
ช้า1.031s; ถึง activity หลังเริ่ม capture0.587s โดย price_renew จบแล้ว รวม1.569s.
Captureจบด้วย TimeoutError หลัง1.280s ซึ่งรวม cancellation/cleanup ไม่ใช่ server query time.
ไม่มี activity/locks rows จึงไม่รู้ blocker หรือส่วนที่ใช้ budget ก่อน activity อย่างละเอียด.
[OBS-02](evidence/endurance20-20261115/obs02-result.md) เก็บ30capturesในfixtureเล็กได้;
[OBS-03](evidence/endurance20-20261115/obs03-result.md) โหลด600commandsผ่าน แต่ sampler0triggers.

A แนะนำ: เก็บตามตารางขณะโหลดจริง เพื่อให้ได้ phase timings โดยไม่รอ rare trigger.
B คงหลักฐานเดิม: ไม่มีค่าใช้จ่ายทดลองเพิ่ม แต่ช่องว่าง timing ใต้โหลดคงอยู่.
ไม่แนะนำรัน SMOKE แบบเดิมซ้ำหรือ4hทันที; รอบนี้ไม่จำลองเหตุการณ์หลัง32นาทีทั้งหมด.

## Requirements

- คง PAPER_INTERNAL20_V1 / SMOKE:20บัญชีจำลอง,400baseline orders,20workers,
  6cycles/owner,600commands ที่2/s,วัด300s; poll4/claim coordination และ checksเดิม.
- เพิ่ม opt-in `--observer-scheduled-samples` defaultoff เฉพาะ profile/phase นี้;
  ต้องใช้ lease/fence/timing/fail-fast ของOBS03ครบ ปฏิเสธ recovery,controlled delay,
  diagnosticsอื่น,worker-only,W3 และ profileอื่นก่อนfixture. Defaultเดิมไม่เปลี่ยน.
- เก็บ10scheduled captures ที่ offset15,45,75,105,135,165,195,225,255,285s
  จาก monotonic measurement start เดียวกับ workload ไม่ใช่เวลาเริ่มprocess/preflight.
  บันทึก target/start/finish/lateness ทุกครั้ง ไม่ยิงย้อนหลังเป็นชุดหรือ retryชดเชย.
  หากมีรอบค้างเมื่อถึง slotถัดไป หรือ measurementจบก่อนครบ ให้ Incomplete.
- ใช้ observer instance แยกจาก natural-trigger monitor เพื่อไม่เปลี่ยน threshold1s,
  cadence0.25s หรือแย่ง engine/current statement; samplerแต่ละinstanceทำงานทีละหนึ่ง.
  ทุกscheduled sampleเรียก original sample ครั้งเดียวในowned task; ไม่มีglobal patch.
- อ้าง PIDจริงของ idle fixture session ที่ไม่ถือ business/advisory lock;
  ใช้ label `scheduled_fixture_idle`, publication_tick=null และไม่อ้างเป็น publisher stall.
  เปิด fixtureเฉพาะแต่ละcaptureแล้วคืนconnection ไม่ค้างtransactionตลอด5นาที.
  ต้องผ่าน isolated database/role guards ก่อนสร้างengine/sessionทุกเส้นทาง.
- Collector SQL/timeout1s/statement500ms/lock200ms/rowlimits128และ8192เดิม;
  lease5s/fencing/production SQL/สูตรเงิน/cadenceเดิม ไม่เพิ่มretry/reacquire.
- แยกscheduledและnatural evidence/counts/pool inventoriesชัดเจน บันทึกทุก10captures
  รวมpartial/failedพร้อม7phase timings; natural evidenceคง64ล่าสุด/failedเดิม.
  Loop lagใช้bounded aggregateเดิม ไม่อ้างว่าcorrelateเฉพาะquery.
- Sampling/fixture/evidence IO failure, cancellationที่ไม่ใช่normal stop หรือข้อมูลไม่ครบ
  ให้Incompleteและsafe-stopตามsupervisionเดิม; preserve primary exception/Failedเดิม.
- เก็บเฉพาะข้อมูลเดิมที่อนุญาต ไม่บันทึกSQL text,URL,secret หรือrawexceptionmessage.
  ผลเป็นdiagnosticเท่านั้น ไม่ใช้แทนperformance/endurance acceptance.

## Plan / reuse

1. ใช้ `profile_observer_diagnostic.py` capture/idle fixture pattern และ
   `profile_observer_timing.py` primitives; ค้นและใช้ helperเดิมก่อนเพิ่ม.
   หากจำเป็นย้ายhelperให้sharedแบบเล็กที่สุดเพื่อไม่สร้างcircular importกับworkload.
   `profile_publisher_fence.py` sampleSQLไม่คัดลอกหรือเปลี่ยน.
2. ต่อparent-only optionผ่าน `remaining_paper_campaign.py` / `profile_workload.py`;
   reuse measurement-start contract, LoadLeaseObserver supervision/failure signal,
   finish_observed_cleanup, independent witness และ save_partial_result.
   ลงทะเบียนทุกpoolที่เพิ่มในowned pool evidence และปิด/joinทุกownedtask.
3. ตรวจtargeted tests/staticก่อน review → แก้ findings → owner refactor ตามAGENTS.
4. Pin candidate/config/migrations/runner; preflight120s/7samplesหนึ่งครั้งก่อนfixture.
   ถ้าไม่ผ่านหยุด ไม่วนรอและไม่หยุดบริการอื่น.
5. สร้างฐานว่าง/Redisติดownershipเฉพาะงาน รันหนึ่งcampaign; เวลาคาด10–15นาที
   จำกัด1200sจากเริ่มpreflight รวมcleanup สำรองcleanup120s.
   ไม่ส่งคำสั่งในบัญชีเจ้าของหรือLive ไม่มีscheduled worker faults.
6. Failureให้หยุด workload ไม่ส่งpublication/commandทดแทน; เก็บindependent witness
   cursor/owner/generationก่อนcleanupตามflowเดิม. Join/ตรวจpool/locksและลบเฉพาะowned
   resources; retain/reportเมื่อพิสูจน์ownershipไม่ได้หรือchildยังอยู่ ไม่force drop.

## Validation

Feature:
- option matrix/default/W3 unchanged; isolation guardก่อนengine, task isolation,
  once-only/exception identity, fixed10slotsและclockเดียวกับmeasurement,
  late/missed/overlapping slotsไม่ถูกชดเชยหรือรายงานComplete, ไม่มีcaptureก่อนวัด.
- no fake publication identity, bounds, natural/scheduledพร้อมกันไม่สลับengine,
  cancellationก่อนเริ่ม/ระหว่างsample/ก่อนclose, ambiguous commit/source failure,
  evidenceIO failureและprimary priority, no-next-phase/join/cleanup.
- PostgreSQLจริง: readonly/actualPID/transactionrollback/lockrelease/poolreturn;
  reuse known-blocker regressionเดิม ไม่ฉีดbusinesslockในcampaignจริง.
- Ruff/format/mypyเฉพาะกระทบ และ regressions OBS02/OBS03/readiness/supervision;
  ใช้หลักฐานเงินที่ไม่ได้รับผลกระทบต่อ ไม่ใช้mockแทนฐานจริง.
Diagnostic:
- รายงานครบ10หรือจำนวนจริงก่อนหยุด ทุกphase/outcome/late slot และcold firstกับ
  reused samplesแยกกัน ไม่ตัดoutliers; timingsรวมdriver/network/scheduling/sessionexit.
- รายงานworkload/เงิน/order/final-tail/resourceตามchecksเดิมครบและcleanupแยกผล;
  snapshot/rebuild/positionsส่วนที่SMOKEไม่ตรวจให้NotRun ไม่อนุมานPassed.
- หากไม่มีtimeoutให้รายงานไม่เกิดซ้ำในscheduled samplingใต้โหลด5นาที ไม่ใช่แก้สาเหตุW3.
Batch/Release: คงW3Incompleteและผลเดิมทั้งหมด F17ยังไม่Completed.

## จุดอนุมัติ / จุดหยุด

OBS03ระบุไม่มีforced/periodic capture และจบหนึ่งcampaignแล้วหยุด/report.
OBS04จึงเปลี่ยนขอบเขตการเก็บหลักฐานอย่างชัดเจน ต้องอนุมัติก่อนsource/ทดลอง.
เมื่ออนุมัติทำimplementation/testsถึงreview gate; หลังreview/refactorจึงหนึ่งcampaign.
เมื่อจบให้สรุปและหยุด ไม่แก้publisher/เกณฑ์ ไม่รัน4hหรือcampaignเพิ่มอัตโนมัติ.
ไม่มีcommit/push/CI/mergeในขอบเขตนี้. การเขียนแผนยังไม่ใช่การอนุมัติหรือผลทดลอง.

## Implementation binding ก่อนแก้

เจ้าของ approve แล้ว ใช้ scheduled observer แยกinstance/task พร้อมfixture MARKET_DATA pool1/0
หนึ่งชุด ใช้sessionใหม่ทุกcaptureและreuse capture helper OBS02 ผ่านlocal importเพื่อไม่สร้าง
import cycle. เพิ่มinventoryเฉพาะopt-in: ADMIN_OBSERVER5/10และMARKET_DATA1/0.
measurement-start callbackจาก _run ส่งmonotonicจริง ไม่อ่านไฟล์แบบpoll.
closeก่อนmonitorเดิมและfinalizeบังคับ10records/taskสำเร็จจริง แยกfailure receipt.

### Test fixture path correction ก่อนแก้

Expanded checks57Passed/1Failed: assertionอ่านprocessing-windowจากtmp root แต่ mock_parent
กำหนดargs.output=tmp/run. แก้testให้อ่านargs.outputตามcontract ไม่เปลี่ยนruntimeหรือassertion
measurement startตรงกับwindow; ใช้อำนาจengineeringแก้testที่วัดผิดและเก็บผลFailedเดิม.

## Implementation checkpoint

[Checks](evidence/endurance20-20261115/obs04-implementation.md):302distinct evidence
(58affected+244unchanged),static7files/independentDBcleanupPassed.
เก็บexpanded57Passed/1testpathFailedและผลแก้ไว้ตามจริง. รอowner review code;
preflight/campaignNotRun ไม่มีGit/CI/mergeและไม่เปลี่ยนW3Incomplete.

## Review M1–M2 fix — ก่อนแก้ source

เจ้าของสั่งแก้ไขหลังreview: M1 slotตรวจหลังcaptureคืนค่าเท่านั้น จึงไม่safe-stop
เมื่อfixture/sessionค้าง; M2 disposeที่ล้มตามหลังทับexceptionแรกของclose.
ใช้engineering authorityแก้ให้ตรงแผนเดิม: timeoutด้วยเวลาคงเหลือถึง
min(next slot,measurement end)ครอบcaptureทั้งlifecycle คงcollector1sเดิม
และpost-checkกันoperationที่กลืนcancellationหรือblock eventloop.
closeเก็บexceptionแรก พยายามjoin/close/disposeครบแล้วraiseตัวเดิม
แนบเฉพาะชนิดข้อผิดพลาดถัดไป ไม่เก็บmessage/secret.
ตรวจhungcapture/cancellation/finalslot/failure signal/dualcleanupfailure
พร้อมrealPGreturn/rollbackเดิมและstatic. ยังไม่รันcampaignหรือGit; หลังแก้รอownerrefactor.

### OBS-04 review fixes M1–M2

[Fix evidence](evidence/endurance20-20261115/obs04-review-fix.md):165targeted/realPGPassed,
5test-double rechecksPassed,static2files/independentcleanupPassed.
M1deadlineครอบcapture/M2preservefirstcleanup exception. รอownerrefactor;campaignNotRun.

## Refactor M1–M2 — ก่อนแก้

เจ้าของสั่งrefactor: runtime deadline/cleanupใช้โครงสร้างตรงไปตรงมาแล้ว คงไว้.
รวมcleanup testsสองฟังก์ชันเป็นตาราง5casesเดียว ใช้mock/assertionsร่วมกัน
คงexception identity/cleanupครบ/notesไม่เผยmessageและทุกcaseเดิม.
ตรวจ7casesที่กระทบ(M1สอง/M2ห้า)และstatic; reuse165realPG evidenceที่runtimeไม่เปลี่ยน.
จากนั้นหนึ่งOBS04campaignตามอนุมัติ ใช้coordinatorOBS03เดิมเปลี่ยนownedชื่อ/receipt
และเพิ่มscheduledflag/configเท่านั้น คงpreflight/budget/cleanup/pinsเดิม.

### OBS-04 one campaign result — stop/report

[Result](evidence/endurance20-20261115/obs04-result.md):refactor7tests/staticPassed;
oneSMOKE600commands/10scheduledcapturesPassed,total458s;source/cleanupPassed.
ไม่เกิดtimeoutซ้ำใน5นาที ไม่พิสูจน์สาเหตุW3;คงIncompleteและF17Pendingเดิม.
หนึ่งcampaignใช้แล้ว ไม่มี4h/Git/CI/mergeหรือauto-rerun.
