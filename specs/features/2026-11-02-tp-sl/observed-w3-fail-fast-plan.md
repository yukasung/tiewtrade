# NC-F17-W3-OBS-01 — รอบสี่ชั่วโมงพร้อมหยุดเมื่อหลักฐาน observer ขาด

สถานะ: **Approved A — เจ้าของอนุมัติ implementation/targeted checks; รอ review/refactor ก่อนหนึ่ง W3 campaign**
วันที่: 2026-11-16 (Asia/Bangkok)
ขอบเขต: amendment ของ F-17 ใน branch เดิม ไม่มี feature การเทรดใหม่
ฐาน: [FENCE-02](publisher-fence-endurance-plan.md),
[FENCE-03](publisher-fence-failure-evidence-plan.md),
[refactor/validation](evidence/endurance20-20261115/fence03-refactor.md),
[offline rebuild Passed](evidence/endurance20-20261115/rebuild20-04-checkpoint.md)

## 1. เป้าหมายและคำตัดสินที่เสนอ

ใช้ผล offline ที่ผ่านแล้วเดินต่อสู่ observed W3 โดยตรวจครบโปรไฟล์เดิม และลดการเสียเวลา
รันต่อหลายชั่วโมงเมื่อเก็บหลักฐานที่จำเป็นไม่ได้ ไม่ลดความถูกต้อง เงิน หรือความปลอดภัย

**A — แนะนำ:** เพิ่ม opt-in fail-fast เฉพาะ observed internal20 W3 เมื่อ sampler ล้ม
หรือเสียหลักฐาน ให้แจ้ง supervisor เดิมเพื่อเริ่มหยุด workload/เก็บผล/cleanup โดยเร็ว
ไม่รอจนหมดสี่ชั่วโมง แล้วรายงาน Incomplete การหยุดก่อนครบไม่ถือว่าผ่าน endurance

**B — คงนโยบายเดิม:** sampler หยุดแต่ workload อาจทำต่อถึงจบและจึงเป็น Incomplete
ใช้ได้หากเจ้าของตั้งใจเก็บ partial load evidence ต่อแม้รับรองทั้งรอบไม่ได้ แต่ไม่แนะนำ
สำหรับเป้าหมายปิดด่านนี้ เพราะมีโอกาสเสียเวลาซ้ำเหมือน FENCE-02

ข้อเสนอนี้ใช้Aเป็นฐานส่วนimplementation/validationด้านล่าง ไม่มีการแก้ code หรือรัน
ทดสอบใหม่ระหว่างจัดทำแผน ต้องรอเจ้าของเลือกก่อน

## 2. โปรไฟล์และเกณฑ์ที่คงเดิม

- `PAPER_INTERNAL20_V1 / W3`:20บัญชีจำลอง,20baseline LIMITต่อบัญชี รวม400,
  worker20ตัวพร้อมกัน,282cyclesต่อบัญชี/5640cycles รวม28200คำสั่ง ที่2คำสั่ง/วินาที
  นอกช่วง fault เดิม:11280fills/5640cancels/5640idempotentreplays
- วัดจริง14400วินาที ไม่ตัดช่วงช้า ไม่ใช้ช่วงสั้นแทน4h การเตรียม/ปิดท้ายแยกจากช่วงวัด
- source10Hzbook และ heartbeat/price cadence ของ W3 เดิม ไม่ใช้ราคา10Hzของofflinefixture
- authenticatedfixture HTTP→inbox→bridge→worker,auth/CSRF/session/RLS/riskpolicyจริง
  ไม่ใช้ F15 AllowPaperPolicy ของofflinefixtureแทนเส้นทางนี้
- processing p95≤500ms/p99≤2s ตามinternal20ที่อนุมัติ รายงานtarget250ms/1sควบคู่
  snapshots p95≤250ms/p99≤1s,อ่านครบ20บัญชีนาทีละครั้งและfinal รวม4820samples
- finalreplayทุกบัญชี≤60s,อ่าน/fold/ตรวจเงินและevidenceจริงทั้งหมด รวมsession/query/
  driver/decode/exit;ไม่ตัดให้เหลือ96000เพื่อเลียนแบบofflinefixture และไม่resettimer
- exact Money/Quantity/fee/PnL/cash/reservations/held/cost/global/idempotency/source/
  finaltail/recovery/RSS≤1GiBและW3growth≤20%/pool/lock/connectionเกณฑ์เดิมทั้งหมด
- lease5s,fencing,readinessguard,cycle/recovery/finaltail60s และclockrecoveryเดิม:
  สูงสุด1confirmedrollback event/1retryภายใน1s เฉพาะmeasuredwindow;ห้ามนำsamplererror
  มาเป็นเหตุ retry publication/คำสั่ง หรือเพิ่ม clock tolerance
- ไม่มีowner/Liveorders,production API/schema/session/สิทธิ์/strategy/risk/SQLchange

Fault schedule เดิม7เหตุการณ์ทั้งหมด:
`backend/tests/infra/execution_market/w3_fault_schedule.json`
SHA-256 `f16097ecc926afd48a79af051ca063e17cdb13e6489ea5f1484aeb75bc05cb03`

| นาทีในช่วงวัด | เหตุการณ์ | ระยะ |
|---:|---|---:|
|30|WORKER_RESTART|30s|
|60|CONNECTION_CHURN|30s|
|90|REDIS_OUTAGE|60s|
|120|WORKER_RESTART|30s|
|150|CONNECTION_CHURN|30s|
|180|REDIS_OUTAGE|60s|
|210|WORKER_RESTART|30s|

ไม่เปลี่ยนoffset/duration/exclusion/recovery assertions หรือหยุดบริการอื่นแทนfixture

## 3. Implementation ของ fail-fast หลังอนุมัติA

### แหล่งใช้ซ้ำและขอบเขต

| ของเดิม | วิธีใช้ |
|---|---|
| `profile_publisher_fence.FenceObservation` | monitor/error counters/failed observation/close;เพิ่มoptionalการแจ้ง failure เมื่อcounterถูกตั้งแล้ว โดยคงค่าdefaultเดิม |
| `profile_publisher_lease_load.LoadLeaseObserver` | เป็นเจ้าของfailure signalต่อcampaign และfinalizer;ไม่ย้ายpublisherไปtaskใหม่หรือเปลี่ยนactor/guard isolation |
| `profile_workload.with_publisher` | เพิ่มoptionalfailure signalที่awaitร่วมกับtask/publisher/checksเดิม แทนการpollDBหรือสร้างsupervisionframeworkใหม่ |
| `profile_workload.run/_run/drain_final_tail` | ส่งsignalเฉพาะopt-inผ่านช่วงที่publisherทำงาน และตรวจอีกครั้งก่อนfinalverificationราคาแพง |
| `remaining_paper_campaign.py` | validate/forwardparent-onlyflagและpinrunner/config/faultschedule/evidenceเดิม ไม่forwardให้workers |
| `profile_owned_pools`, `profile_replay_reads` | exactinventory,primary-error/partialreceipt/finalization/ownedcleanupเดิม |

เสนอflag `--publisher-fence-fail-fast` defaultปิด อนุญาตเฉพาะinternal20V1 W3ที่เปิด
lease+fence observers และCLOCK01ตามscopeเดิมครบ Rejectก่อนสร้างfixtureเมื่อใช้กับ
worker/SMOKE/W1/W2/release/controlleddelay/diagnosticอื่นหรือflagsไม่ครบ

Failure signalหนึ่งชุดต่อcampaign เป็นdiagnostic stateชั่วคราว ไม่ใช่session/business
storage ใช้Future/resultหรือprimitiveเดิมที่เทียบเท่า ไม่เพิ่มpool/SQL/polling cadence
เมื่อmonitorพบerror แจ้งหลังเก็บenvelope/counterแล้ว ห้ามส่ง exceptionmessage/SQLtext/
credentials ผ่านsignalหรือreport ห้ามแจ้ง failureจากการcloseปกติเป็นfalsealarm

Supervisorเริ่มหยุดเมื่อได้รับfailure;in-flight transaction/taskต้องคืนcontrolหรือ
rollback/จบตามboundsเดิมก่อนปล่อยresource จึงไม่สัญญาว่าทุกprocessหายทันที
ไม่ยกเลิกกลางช่วงสร้างworkerที่ยังไม่ได้บันทึกownershipจนเกิดorphan:เก็บownership
แบบincrementalหรือรอขอบเขตstartupที่ปลอดภัยและมีboundก่อนหยุด ต้องทดสอบpartialstartup
และearly-failureก่อนmeasurementด้วย ไม่รอไปตรวจhealthเฉพาะphaseสุดท้าย

ครอบคลุมpublisherready/baseline/measurement/faultwait/remainingmeasuredtime/finaltail
และจุดก่อนfinalrebuild;หลังpublisherปิดตามปกติต้องไม่ตีความmonitorจบเป็นerror
Signalที่มาในช่วงfinaltailต้องไม่ทำให้publisherที่หยุดตามแผนถูกกล่าวหาว่าหยุดผิดปกติ

Priorityของerrorต้องชัด:ถ้าpublisher/workloadมีprimaryerrorที่กลับมาแล้วให้คงอันนั้น
และแนบobserverfailure หากobserverเป็นเหตุแรกให้ใช้diagnosticIncompleteเป็นต้นเหตุ
เก็บผลของtaskที่เกิดพร้อมกันแบบdeterministic ไม่กลบprimaryด้วยCancelledErrorที่เรา
สร้างเพื่อshutdownหรือmetadata/IOerror ไม่เพิ่มretry/reacquire/financialcommand

เมื่อerrorต้องcancel/joinเฉพาะงานที่campaignเป็นเจ้าของ เก็บpartialcounters/timewindow/
faultstatus/readiness/lease/fenceenvelopeแล้วคืนconnections/locksก่อนcleanup
Future/taskที่เหลือต้องยกเลิกหรือรับผลตามownership ไม่มีunretrievedexceptionหรือdanglingtask
ผลสุดท้ายต้องเป็นIncomplete/Failedตามหลักฐาน ไม่คงPassedเพราะไฟล์ผลถูกเขียนก่อนflush
Default/ไม่เปิดflagและโหมดอื่นคงbehavior/checkordering/timeoutเดิมทั้งหมด

## 4. ด่าน safety/review/refactor ก่อนรอบยาว

Feature testsที่ต้องครบก่อนทดลอง:

1. Exactoptionmatrix/defaultไม่เปลี่ยน,rejectก่อนsideeffects,parent-onlyforwarding
2. Observerfailureระหว่างbaseline/measurement/faultwait/tail/จุดก่อนrebuild:
   ไม่เริ่มphaseถัดไปและไม่ต้องรอ14400s โดยใช้event/barrierในunit tests ไม่ลดเวลาตรวจรับ
3. Simultaneouspublisher/workload/observererrors,actualerror/cancellationidentity,
   raceที่normalclose,callbackหลังsignalจบ/ยกเลิก,foreigntask/taskisolation/guard counts
4. Fullfailed-observation metadataถูกบันทึกพร้อมIncomplete,IO/summaryfailureไม่กลบ
   primary,ไม่ส่งคำสั่งหรือpublicationทดแทน และไม่ถือว่าทุกin-flightcommandrollback
5. Join/partialstartup/repeatedcancel/disposal/finaltail/regression และrealPG read-only/
   rollback/lockrelease/connectionreturn/realblocker/combinedCLOCK01proofเดิมที่กระทบ
6. Poolinventoryเดิมครบทุกgeneration:20workersพร้อมกัน และทุกrestartgeneration
   ไม่แปล80workerreportsในW3ว่า80concurrentworkers;ไม่มีwaiverของCancelledError

ใช้targetedtestsที่ครอบdiff/callers/contracts,ไม่ใช้mockแทนtransaction/lockproof
Ruff/format/mypy/whitespaceเฉพาะส่วนที่เปลี่ยนก่อนreview ใช้หลักฐาน113/80/28และ
REBUILD20-04ที่ยังvalidต่อเท่าที่behavior/dependencyไม่กระทบ ไม่รันofflineเต็มอีกเป็นพิธี

เมื่อimplementationครบให้รายงานscopedcheckpointและรอowner `review code`;แก้findings
แล้วรอowner `refactor the code` ตามAGENTS.md ไม่ข้ามสองด่านนี้เพราะอนุมัติแผน
หลังrefactorตรวจaffectedvalidationต่ออัตโนมัติ หากแก้เกณฑ์เดิมไม่ผ่าน3รอบหรือเกิน
ขอบเขตความปลอดภัยให้หยุดตามกฎเดิม ห้ามลบassertionสำคัญเพื่อผ่าน

## 5. Campaign W3 หนึ่งรอบหลังด่านก่อนหน้าผ่าน

การอนุมัติAครอบคลุมimplementation/targetedchecksและ**หนึ่งW3campaignหลังreview/
refactor/Featurevalidationผ่านครบ** ไม่ต้องขอเริ่มงานย่อยซ้ำ แต่ห้ามเริ่ม4hก่อนgatesครบ
ก่อนเริ่มแจ้งcandidate/ขอบเขต/เวลารวมตามกฎเดิม หากตอนนั้นenvironmentไม่พร้อมให้หยุด
Incomplete ไม่วนpreflightจนได้สภาพเครื่องที่ดี และไม่ปิดโปรแกรม/บริการอื่นแทนเจ้าของ

คาดพัฒนา/ตรวจharnessประมาณ30–60นาที ไม่รวมเวลารอownerreview/refactorและการแก้finding
ช่วงวัด14400s(4h)คงเดิม คาดcampaignรวม4h20–40min จำกัด18000s(5h)นับจากpreflight
รวมfixture/faults/tail/fullfinancial/snapshots/rebuild/resource/pool/evidence/cleanup
กันcleanup120sในงบรวมเดียวกัน;ไม่ reset deadlineเมื่อย้ายphase และไม่ต่อเวลาเอง

ใช้freshownedlocalDB,migrations/configเดิม และdedicatedRedisที่มีtaskownershiplabel/
portแยก,imageจากของเดิมในเครื่อง ไม่หยุดownerPostgreSQL/Redisหรือcontainersอื่น
ยืนยันownershipทุกครั้งก่อนscheduledfault/cleanup;ไม่prune/reset/deleteimages/volumes

ก่อนpreflightpin HEAD+diff+untrackedsourceinventory,configuration/migrations/schema,
runner/helpercopies+reviewedhashes,faultschedulehashและruntimeflags ใหม่ต้องไม่ใช้
legacyhelperdependencyที่อยู่นอกinventoryแบบที่เคยพบในPREP20;verifybindingsตอนจบ

ลำดับ:runnerchecks → one120s/7samplepreflight → ownedDB/Redis → baseline/authHTTP
→ measured4h+7faults+20snapshots/minute → finaltail → stopownedworkers/resourcesampling
→ positions/snapshots/fullhistoryreplay → finalfinancial/global/sourceตามoraclesเดิม
→ processing/RSS/poolvalidation
→ ownedcleanup+independentDB/connection/lock/containerabsence → report
หากโค้ดเดิมตรวจrebuildก่อนfinalfinancialแล้วerrorทำให้financialNotRun ให้รักษาgradeนั้น
หรือบันทึกamendmentก่อนเปลี่ยนลำดับ ไม่แก้runnerให้ข้ามoracleเพื่อให้จบรอบ

เก็บeveryowner/everyfault/everyrequiredsample;อ่านprivatehistoryจริงทั้งหมดในW3
อาจต่างจาก96000ของofflineproof ซึ่งไม่รับรองขนาดที่ใหญ่กว่าโดยอัตโนมัติ
เก็บoriginalprocessingtarget250ms/1sและaccepted500ms/2sควบคู่ ไม่ยกเว้นslowdataใหม่
หากใช้CLOCK01ให้แสดงwarningและattempt/confirmedrollback/commitwitnessตามจริง

## 6. ผล / จุดหยุดและสถานะ

| ระดับ | เกณฑ์ |
|---|---|
| Feature | opt-in/default/priority/isolation/ownership/DBcleanup/safety/static/review/refactorครบก่อนcampaign |
| Batch | หนึ่งW3instrumentedrunครบ14400s,counts/faults/financial/positions/source/tail/resources/pools/observerevidence/cleanupตามเกณฑ์เดิม |
| Release | original100accountRelease/opening/bot/notification/LiveและremainingF17dependenciesยังแยก ไม่ปิดด้วย20ownerW3 |

เมื่อobserverหรืองานหลักล้มให้เริ่มsafe-stop เก็บเหตุผลและactualmeasuredtime/completeness
หยุดแล้วรายงาน ไม่เริ่มรอบทดแทนอัตโนมัติ ไม่ขยายเวลาหรือเปลี่ยนเกณฑ์กลางรอบ
หากผ่านครบรายงานเฉพาะcandidate/profileนี้;ไม่regradeเก่าหรือถือว่าstallเดิมหายถาวร

ไม่มีcommit/push/PR/CI/mergeในscopeนี้ คงREBUILD20-04offlinePassedและW3Incompleteเดิม
ตามcandidate/หลักฐาน F17ยังไม่CompletedจนBatch/Release/dependenciesครบจริง
บันทึก ณ ฉบับเสนอ: ยังไม่มี source edit/tests/workload/campaign ของ W3-OBS-01 ในขณะนั้น


## 7. บันทึกก่อนแก้ source — 2026-11-16

เจ้าของตอบ `approve` เลือก A ตามข้อเสนอ ใช้อำนาจด้านวิศวกรรมใน AGENTS.md
เลือก Future แบบเก็บผลปกติ (ไม่เก็บ exception ที่อาจไม่มีผู้รับ) ต่อ observer หนึ่งตัว
รับสัญญาณจาก done callback ของ sampler เดิม ไม่มี SQL/poll/task publisher ใหม่
`with_publisher` รอ signal ร่วมกับงานเดิม และตรวจ errors ที่เสร็จแล้วก่อน diagnostic
ใช้ signal เดียวครอบ ready/baseline/cycles/fault wait/duration/tail และตรวจอีกครั้ง
ก่อน final verification โดย tail wrapper ไม่ตีความ intentional publisher stop เป็น failure

ช่วงเริ่ม worker ต้องบันทึก process ทีละตัวและคืน ownership แม้ spawn ถูกยกเลิก
ไม่รับ observer cancellation กลาง startup; ตรวจ signal ทันทีหลัง startup สำเร็จ
ใช้ startup deadline 60s เฉพาะ opt-in รวมการรอ PID ตามเดิม แล้ว cleanup ที่เป็นเจ้าของ
ก่อนส่ง error ต่อ ค่า default/เส้นทางอื่นไม่เพิ่ม deadline

เขียน `publisher-fence-failure.json` หนึ่งครั้งเมื่อจบ observer เป็น receipt แยกจาก
lease/readiness summary เพื่อเก็บ envelope แม้ publication แรกหรือ readiness ยังไม่ครบ
IO failure ต้องทำให้ Incomplete โดยรักษา primary exception เดิม และรักษา Failed ที่พิสูจน์แล้ว
ไม่เขียน disk ต่อ tick ไม่มีการแก้ production/เงิน/lease/guard/retry หรือ resource inventory
การอนุมัตินี้ไม่ใช่ผลตรวจผ่าน: implementation และ tests ยังไม่รัน ณ เวลาบันทึกนี้


## 8. ผล implementation — 2026-11-16

[Checkpoint](evidence/endurance20-20261115/w3-obs01-checkpoint.md): targeted 434 Passed,
Ruff/format/mypy/whitespace Passed และ independent DB/connection/lock cleanup Passed
คง Failed ของ safety attempt แรกตามหลักฐาน implementation gate เท่านั้น
รอ owner `review code` และ refactor gate ก่อน campaign ไม่ได้รัน 4h หรือ Git/CI


## 9. แก้ findings M1/M2 ก่อนลงมือ — 2026-11-16

เจ้าของสั่ง `แก้ไข` หลัง review พบ Medium สองข้อ ใช้อำนาจด้านวิศวกรรมตาม AGENTS
คง scope/เกณฑ์/ค่า default เดิม ไม่อนุมัติ refactor หรือ campaign ก่อนด่านเดิม

- M1: fault injection ยืนยัน publisher ที่ล้มแล้วระหว่าง startup ถูก signal กลบ
  เลือกใช้ `with_publisher` เดิมตรวจ boundary หลัง startup เฉพาะ opt-in เพื่อรักษา
  error priority/cancellation identity โดยไม่ cancel กลาง spawn หรือเริ่ม baseline
  ไม่เพิ่ม helper/supervisor/SQL และไม่ย้าย publisher ไป task ใหม่
- M2: fault injection ยืนยัน receipt write error ทำให้ไม่เรียก lease flush
  ให้ finalizers สองตัวพยายามทำแยกกันใน opt-in แม้ตัวแรกล้ม โดยส่ง error ตัวแรกต่อ
  และแนบชนิด error ของตัวที่สอง; outer finalization ยังรักษา primary/Failed/Incomplete เดิม
  ค่า default คง ordering/exception behavior เดิม ไม่เพิ่ม disk writes ต่อ tick

เพิ่ม tests ของ startup real error/cancellation พร้อม signal และ no-baseline proof;
receipt/summary failure ทั้งแยกและพร้อมกัน รวม primary identity/การเขียนหลักฐานที่เหลือ
รัน targeted supervision/parent/default/finalization และ impacted real-PG tests
ใช้หลักฐานอื่นที่ไม่กระทบต่อ ไม่รัน offline/4h/full suite/Git/CI ในขั้นแก้ findings นี้
หลังแก้/ตรวจให้รายงานแล้วถาม owner `refactor the code` ตามด่านเดิม


## 10. ผลแก้ findings — 2026-11-16

[Checkpoint M1/M2](evidence/endurance20-20261115/w3-obs01-review-fix.md):
แก้ startup error priority และ independent finalizer attempts; เพิ่ม regression 8 กรณี
Local unit 100 Passed และ impacted DB-backed regression 134 Passed (187 distinct)
Ruff/format/mypy/whitespace และ independent DB cleanup Passed
รอ owner `refactor the code` ตามด่าน AGENTS; 4h/CI/Git ยัง Not Run


## 11. Refactor ที่เจ้าของสั่ง — บันทึกก่อนแก้ 2026-11-16

เจ้าของสั่ง `refactor the code` หลังแก้ M1/M2 และ targeted checks ผ่านแล้ว
จำกัดรอบนี้ที่ส่วนแก้ findings: แยกขั้น finalization receipt/summary เป็น method ชื่อชัด
ใน LoadLeaseObserver เพื่อลด nesting ของ context-manager cleanup โดยคงลำดับ/exception
identity/default behavior และการ downgrade status เดิมทุกข้อ ไม่สร้าง generic abstraction
M1 ใช้ with_publisher เดิมอยู่แล้ว ไม่เพิ่ม wrapper อีก ลด ternary/JSON assertion ซ้ำ
เฉพาะ regression tests ที่เพิ่มในรอบ M1/M2 ไม่แตะ publisher/source/เงิน/SQL
ตรวจ affected tests/static ต่อทันทีและใช้หลักฐานที่ยัง valid ตาม plan §4–5


## 12. Refactor/affected validation และเตรียม coordinator — 2026-11-16

[Refactor Passed](evidence/endurance20-20261115/w3-obs01-refactor.md): 134 affected tests,
static checks และ independent cleanup ผ่านแล้ว เริ่มเตรียม validation §5 ตามอนุมัติเดิม
Reuse FENCE02 coordinator เป็นสำเนาที่ pin hash ทั้งไฟล์ (helper functions inline ทั้งหมด
ไม่ exec/import helper นอก inventory) เปลี่ยนชื่อ owned resources/revision, เปิด fail-fast,
และยืนยัน bindings ของ launcher/adapted runner/config/fault schedule ตอนจบ
ถ้า child ยังไม่หยุดให้ retain DB/Redis พร้อม ownership ไม่ cleanup dependency ใต้ child
คง one120s preflight,18000s overall/120s cleanup reserve, original W3 oracles ทั้งหมด
ไม่มีขยาย profile/เกณฑ์/ขอบเขต Git; stop/report เมื่อ phase ล้มตาม §5–6


## 13. One observed W3 — หยุด/report 2026-11-16

[Result](evidence/endurance20-20261115/w3-obs01-result.md) Incomplete:
total2147.1634s/measured1972.8285s, completed3863/28200, firstworkerrestartRecovered;
observer TimeoutError in activity capture triggered opt-in safe-stop. Both evidence files
retained; pool reportfalse/errors2 retained. Independent cleanup Passed/source unchanged.
Final verification/remaining faults NotRun ไม่รันซ้ำ/แก้ source/เกณฑ์เองตาม §6
Next: propose bounded short observer investigation, not another four-hour campaign
F17 ยังไม่ Completed; existing grades retained ไม่มี Git/CI/merge
