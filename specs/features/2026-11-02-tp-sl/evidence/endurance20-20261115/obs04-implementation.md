# OBS-04 implementation checkpoint

สถานะ: Implementation/targeted checks Passed — รอ owner review code ก่อน refactor/campaign

## Changes

- `profile_observer_scheduled.py`: opt-in scheduled fixture sampler 10slots(15..285s),
  actual measurement monotonic, missed/crossed slotไม่catch-up/retry, owninstance/task,
  idle fixtureactualPID/no publicationtick, originalcapture helper/SQL/timeoutsเดิม.
- `profile_publisher_lease_load.py`: scheduled lifecycle/failure signal/cleanup/receipt,
  finalizeปฏิเสธเมื่อไม่ครบ10หรือtaskไม่สำเร็จ; preserveprimaryตามflowเดิม.
- `profile_workload.py`, `remaining_paper_campaign.py`: defaultoffflagและmeasurement-start
  callbackตรงกับprocessing window; defaults/W3ไม่เปลี่ยน.
- `profile_owned_pools.py`: trustedinventoryเพิ่มเฉพาะopt-in ADMIN_OBSERVER5/10และ
  MARKET_DATA1/0; guards/cleanupใช้ของเดิม. ไม่เพิ่มpersistentstate/infrastructure.
- tests scheduledใหม่และassertioncallback/windowในOBS03 duration supervision.

## Checks / limitations

[Summary](obs04-implementation-summary.json): initial297Passed; expanded57Passed/1Failed
เพราะtestอ่านprocessing-windowจากtmpแทนargs.output; แก้pathแล้วเฉพาะcasePassed.
รวม58affected+244unchanged=302distinct evidence. Runtimeไม่เปลี่ยนหลังinitialrun.
Ruff/format/mypy7filesPassed; correctedtestRuff/mypyPassed; git diff --checkPassed.
RealPGตรวจactualPID, readonlycollectorเดิม, rollback/ไม่มีtransaction/advisorylockค้างหลัง
RuntimeError/CancelledErrorและpoolreturn; reuseblocker/supervision/evidenceIO/primary tests.
Independent auditทั้งสองฐาน: absent/0connections/0locks. Rawpathsอยู่ในsummary.

## Review focus / next gate

เน้นmeasurement-start callback, scheduleไม่ชดเชยslot, natural/scheduled engineแยกกัน,
cancellationกับfailure receipt, poolinventoryและprimary exception preservation.
ยังไม่รันpreflight/campaign; ยังไม่มีperformanceหรือW3acceptanceใหม่.
ขั้นถัดไป owner `review code` → แก้findings → ownerrefactor → affectedchecks
แล้วหนึ่งcampaignตามApprovedOBS04. ไม่มี4h/commit/push/CI/mergeในขอบเขตนี้.
คงW3IncompleteและF17notCompleted รวมประวัติFailedเดิม.
