# OBS-05 implementation checkpoint

สถานะ: Targeted checks Passed — รอ owner review code ก่อน refactor/campaign
วันที่: 2026-11-17

## Changes

- profile_observer_prefix.py: owned cutoff2400s และdiagnostic-completion checksแยกจากW3.
- profile_observer_scheduled.py: explicit two-profile schedule (SMOKE10/W3prefix40),
  own offsets/window/slot fields ไม่patchglobalหรือเปลี่ยนcollector timeout/SQL.
- profile_publisher_lease_load.py: exact opt-in W3+timing+scheduled+clock-recovery;
  ส่งprofileให้sampler instance ไม่เปลี่ยนlease/clock retry policyเดิม.
- profile_workload.py: cutofftaskเริ่มmeasurementclockเดิม ตรวจrealerrorsก่อนplannedstop;
  cancel/joininflightก่อนหยุดและpreserveerrorจากcancelcleanup. ห้ามfaultหลังcutoff.
  prefixpartialresultคืนcode2/INCOMPLETEเสมอ ไม่มีfullfinancial/replayacceptanceปลอม;
  ownedcleanup/witness/poolเดิม แล้วแยกdiagnostic COMPLETE/INCOMPLETEหลังfinalizers.
- remaining_paper_campaign.py: forwardflag,3600s budgetและdiagnostic gradeแยกจาก
  workloadIncomplete; sourcebindings/cleanupต้องครบก่อนdiagnosticComplete.
- Tests: scope, schedule, cancellation/errorpriority, nofaultหลังcutoff, partialgrades,
  realparent sequencingและrealPGrollback/lockrelease. OBS04testsใช้instanceoffsets.

## Validation

[Summary](obs05-implementation-summary.json):400 targetedPassedรวมrealPG/HTTP/supervision/
sampler/pools/campaignregressions,45.610s. Ruff/mypy7filesPassed; format/diffcheckPassed.
Independentcleanup: DBabsent,0connections/0locks; raw `validation-artifacts/f17-obs05-tests-20261117/`.
ก่อนหน้านี้unit30Passed/1Failedเพราะmock_parentตั้งfaultloader1cycle; คืนactualapproved
scheduleloaderเฉพาะtestนั้นแล้วPassed ไม่แก้runtimeเพื่อให้ตรงfixtureที่ผิด.
Sourcehashesเก็บในraw checked-source.json ไม่อ้างว่าเป็นcommitใหม่.

## Review focus / remaining

เน้นcutoff/realerrorrace, ไม่มีfaultหลังdeadline, taskjoin/primarypreservation,
partialgradeไม่กลายเป็นW3Passed, scheduled40/measurementclockและpool/witnessfinalization.
ยังไม่ได้preflightหรือ40mincampaign ไม่มี4h/commit/push/CI/mergeในขั้นนี้.
คงW3Incomplete/F17notCompletedและผลก่อนหน้าทั้งหมด.
ขั้นถัดไป owner review code → fixes → ownerrefactor → affectedchecks
ก่อนหนึ่งcampaignตามOBS05ที่อนุมัติ. ไม่ทดลองก่อนreviewgate.
