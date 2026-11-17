# OBS-03 — implementation checkpoint

สถานะ: Targeted checks Passed; รอ owner review code ก่อน refactor/campaign
[Plan](../../observer-short-load-plan.md) / [Summary](obs03-implementation-summary.json)

เพิ่ม shared timing helper จาก OBS02 (standalone callers/testsคงเดิม)
FenceObservation timing defaultoff เก็บ actualmonitor task/PID/stage/tick/spans,
64latest/firstfailure/counters และ boundedlooplag;ไม่มี global instrumentation
flags ส่ง parent-only และจำกัด internal20 SMOKE ที่มี lease/fence/fail-fast ครบ
reject clockrecovery/otherdiagnostics/W3timing; W3 fail-fast เดิมยังใช้ได้
เพิ่ม looplagtask ownership/join/failure propagation ไม่เพิ่ม DBpool/SQL/retry
zero samples รายงาน NO_TRIGGER; cancelled/missing capture เป็น Incomplete
flush ตรวจ timingstatus/counters/lagjoin และรักษา failure receipt/normal summaryเดิม

## Tests / หลักฐาน

- รอบแรก200Passed (ก่อนเพิ่ม report-integrity และ SMOKE parent matrix)
- รอบขยาย211Passed/2Failed: testfixtureเป็นlegacySMOKEแต่พยายาม inject fault/duration
  ที่เส้นทางนั้นไม่มี; คงผล Failed เดิม ไม่ตีความเป็น campaign failure
- แก้เฉพาะtests: fault injectionเฉพาะW3 และเพิ่ม internal20SMOKEจริงในparent/fakeI/O
  เพื่อพิสูจน์ duration wait safe-stop,no-next-phase,dispose โดยไม่รอ5นาที
- รอบแก้79affectedPassed;133unaffectedPassedจากรอบก่อนยังvalid รวม212distinct
- ครอบคลุม option/default/W3 compatibility, task/originalonce/actualidentity,
  memory bounds/error retention,zero triggers,cancelled capture,lagfailure,
  timing missing/countmismatch,failfast startup/cycles/duration/pre-rebuild,
  real-PG readonly/blocker/rollback/lockrelease และเดิม IO/primary/ambiguouscommit
- Ruff/format/mypy8files และ gitdiff whitespacePassed
- Independent cleanupทุกฐาน: absent,0connections,0locks

เป็น transient diagnostic memory ไม่ใช่ session/persistentbusiness storage
ไม่แก้production/API/schema/เงิน/PnL/risk/SQL/lease/timeout/cadence
ไม่ได้ส่งowner/Liveorders ไม่รันpreflight/SMOKEcampaign/4h/Git/CI

## จุดที่ reviewer ควรเน้น / ขั้นถัดไป

เน้น timing task ownership,การต่อ flagsจากcampaignไปparent,lag cancellation/join,
การเก็บ failed evidenceเมื่อ shutdown และ defaultW3/OBS02 regression
ขั้นถัดไปรอ owner review code; หลังแก้ findings/refactorที่เจ้าของสั่งและaffectedchecks
จึงเตรียม pinnedcoordinator/preflight และหนึ่งSMOKEที่อนุมัติแล้ว ไม่เริ่มก่อนด่านนี้
W3/OBS01 IncompleteและF17Pendingยังคงเดิม ผลนี้ไม่ใช่ diagnostic campaignPassed
