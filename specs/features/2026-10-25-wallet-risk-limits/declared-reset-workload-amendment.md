# F18-R27 — Declare RESET traffic separately from the five-command trading workload

สถานะ: Approved — เจ้าของตอบ “อนุมัติ” วันที่ 2026-10-29
วันที่: 2026-10-29

## หลักฐานและปัญหาที่ข้อเสนอนี้แก้

R26W1ล้ม ordinaryownercycle0 ที่60.052668s ระหว่างRESETท้ายcycle หลังผ่านโค้ด
คำสั่งเทรด5รายการแล้ว. ยังไม่มีtimestampแยกที่พิสูจน์ว่า5รายการนั้นจบ<=60s;
ห้ามถือว่าความเร็วการเทรดผ่านจากตำแหน่งstackอย่างเดียว. Selectedrecoveryถูก
cancelโดยpeerfailureที่45.830s ไม่ได้ชน120s. No new workload in this review.

Fixture.cycleเพิ่มself.mutation(RESET)ท้ายทุกcycle แต่positive counters/rates
นับเพียง5คำสั่งเทรด. จึงเพิ่มRESETโดยนัย~2/sในW1/W3และ~20/sในW2นอกเหนือ
commands10/100/10s. Specระบุdeterministicrisk-mutation scenarios แต่ไม่แยก
ความจุRESETที่ต้องรองรับเป็นตัวเลข. ปัจจุบันR26อนุมัติให้endRESETอยู่ในnormal60s;
จึงต้องเปลี่ยนplan/validationก่อนแก้ ไม่ถือเป็นสิทธิ์ลดโหลดเอง.

ข้อเสนอนี้จัดtestprofileให้บอกว่ารับรองอะไร ไม่พิสูจน์ว่าAPIpool/lockไม่มีบั๊ก
และไม่รับประกันว่าW1จะผ่าน. ยังต้องใช้command/RESET deadlinesและR25gatesจริง.

## ทางเลือก

| ทางเลือก | ความหมายการรับรอง | ต้นทุน/ข้อจำกัด |
|---|---|---|
| คงRESETทุกcycle | ต้องรองรับทั้งเทรด100commands/sและRESETประมาณ20/sพร้อมกันในW2 | ต้องหาคอขวด/เพิ่มประสิทธิภาพให้ถึงเป้านี้ เวลาจบยังประเมินไม่ได้ |
| แยกRESET scheduleตามข้อเสนอ | รับรอง100activewallets/เทรดตามเดิมและRESETทุกownerภายใต้โหลด แต่ไม่รับรองRESET20/s | ลดsyntheticRESETtrafficที่ไม่เคยกำหนดเป็นproductcapacity;ต้องยอมรับขอบเขตที่รับรองอย่างชัดเจน |

## ข้อเสนอสำหรับ Paper integrated acceptance

1. Positivecycleกลับเป็น5คำสั่งเทรดเดิม;ไม่ส่งsyntheticendRESETหลังทุกcycle.
   ทุกnormalcycleยัง60s. คงR26selectedbreach/reset/reseed120s/normal60s/outer180s,
   correction/replayและpartial-filloracleครบ. ไม่เพิ่มtimeoutอีก.
2. เพิ่มproducerของRESETที่มีschedule/expectedcountsแยกชัด:
   **100scheduledRESETsต่อrun,หนึ่งครั้งต่อowner,ไม่เกิน1รายการ/s**.
   เริ่มที่elapsed180s แล้วเรียงownerตามmanifest โดยselectedownerอยู่ท้ายรายการ
   (ปกติdue180..279s). Selectedrecoveryต้องสำเร็จก่อนproducerเริ่มส่งRESET
   เพื่อไม่ให้RESETอีกทางล้างlatchของbreachcaseก่อนตรวจstopครบ;หากยังไม่สำเร็จ
   ที่จุดเริ่มให้Failed ไม่เลื่อนscheduleไปเรื่อยๆเพื่อช่วยให้ผ่าน.
3. Producerเป็นtaskแยกจากpositivecycles;ห้ามหยุด/ชะลอ99ownerอื่นหรือเลื่อนdue
   ของtradingcycles. รอdueตามmonotonicclock และไม่ยิงชดเชยถี่กว่า1/sเมื่อช้า.
   บันทึกscheduled/offered/appliedเวลาจริงครบ หากป้อนscheduleไม่ทันหรือ
   completecountsไม่ครบภายในexistingduration+60sให้Failed ไม่ลดexpectedcount.
4. แต่ละscheduledRESETต้องจบ<=60sรวมAPIpoolwait/submission/resultcommit.
   ไม่สร้างpool/workerเพิ่ม. ใช้mutation/claim/CAS/idempotency/financialfenceเดิม;
   awaitcompletionไม่กักtransaction/connectionไว้ระหว่างpollsleep.
   บันทึกoffered/applied/failed/timeouts/owner/requestidentityแยกจาก5commandcounts.
5. W3ใช้FaultGateเดิม. Freezeactualdue timesก่อนวัดโดยเลื่อนเฉพาะRESETproducer
   ผ่านdeclaredfaultwindows (ไม่เปลี่ยนpositivecycle/sourcefaultschedule).
   ยังคง100รายการ/100ownersและdeadline/drainเดิม;inflightRESETต้องrecoverโดยไม่ซ้ำ.
   ไม่ส่งระหว่างgateปิด ไม่ตัดoutlierหรือสร้างfaultwindowใหม่เพื่อช่วยผ่าน.
6. SetupRESETs,selectedbreachRESETและ100scheduledRESETsต้องนับแยก ไม่เอาsetup
   มาแทนunder-loadcoverage. ทุกfinancialinput/lateframeเข้าระบบoracleR25เดิมครบ.

## ขอบเขตการรับรองและสิ่งที่คงเดิม

- ยังคง100wallets×20activeorders; trading10/100/10commands/s;600/300/1800s;
  45minW1–W3measurement;CPU/RAM/pools/workers/schema/APIและfinancialrulesเดิม.
- คงR25perowner/global99.9%<=3s/ทุกinput<=5s,processingp95500ms/p991s,
  authorization,duplicateeffects0,Money/Quantity,PnL,balances/positionsและstopbounds.
- ความหมายที่ยอมรับ: releaseprofileนี้รับรองscheduledRESETทุกownerระหว่างโหลด
  ด้วยscheduleข้างต้น ไม่รับรองRESET20/sหรือ100RESETพร้อมกัน. หากธุรกิจต้องการ
  ขีดนั้นต้องคงเป็นcapacitytargetแยกและไม่อ้างว่าR27พิสูจน์ผ่านแล้ว.
- นี่ไม่ใช่productionrate-limitใหม่ ไม่มีการจำกัดผู้ใช้ผ่านAPIโดยข้อเสนอนี้;
  ขอบเขตที่ผ่านการทดสอบต้องแสดงตามจริงในการตัดสินใจactivation.

## Implementation/validation หลังอนุมัติ

Test-harnessonly: Fixture.cycle,existingmutation,F15FaultGate/scheduler/oracles.
เก็บeventidentityและtimingของ5-commandcompletionกับscheduledRESETแยกกัน.
Producerใช้taskหนึ่ง/ไม่เพิ่มconnections/pools; errorต้องcancel/joinงานที่เหลือ
และpreservefirstfailure. ไม่เปลี่ยนproductionexecutionpolicy/scheduler.

Targetedtests:cyclesไม่ส่งextraRESET;100uniqueowners exactlyonce,selectedท้าย,
noreset-before-breachcompletion;spacing>=1s/faultgate/60sfullresettimeout;
ไม่หยุดtradingหรือเปลี่ยนpositivecounters;failure/cancellationไม่ทิ้งtask/connection;
concurrentRESET/fill/correction/latch/rollback/idempotencyจากtestsเดิมที่กระทบ.

ประมาณ15–30minimplementation/targetedchecksเบื้องต้น;เมื่อผ่านให้nativeW1หนึ่งรอบ
ประมาณ15–20minรวมsetup/analysis. W1ผ่านจึงW2→W3→W4ตามแผนเดิมและแจ้งเวลา
ก่อนแต่ละชุด. ถ้ายังล้มให้หยุดที่failure ไม่เพิ่มdeadline/ลดcountsหรือรันซ้ำ
อัตโนมัติ. รักษาผลFailedเดิมครบและไม่รับรองCompletedขณะdependenciesยังค้าง.

## Approval boundary

ต้องอนุมัติการเปลี่ยนloadจากendRESETทุกcycleเป็น100under-loadscheduledRESETs
ตามด้านบนก่อนแก้requirements/plan/validation/harness. การขอคำแนะนำว่าจะทำอะไรต่อ
ยังไม่ได้เลือกRESETcapacityแทนเจ้าของ. ขณะนี้ไม่มีcode/test/workloadchange.


Owner approval2026-10-29 authorizes this profile revision before implementation. CHECK remains non-accepting and omits the100-owner schedule; onlyW1/W2/W3 certify it.


R27 fixture restoration detail: selectedowner temporarilyuseslimit5 forbreach/reset/
correctionoracles. Afterthoseanditsfirstfive-commandcyclecomplete,restoretheexisting
standardfixturelimit1000 viaoneexplicitINCREASEreceiptwithF-06/AUTHauthorization,thenmarkrecoveryreadyforproducer.
RecordthisoneINCREASE separately from100scheduledRESETs;noneofthethreshold5oraclesmove
oruse1000instead. Thisrestoresnormalpositive-fixtureconfiguration afterthetest,
withoutchangingdomainrules/productionlimits oraddingper-cycleRESETs. Itsreceipt
mustbeAPPLIEDandrecordedbeforeacceptance. KeepthisinsideR26normalbudget.

## R27-A — Correct restoration authorization (Approved 2026-10-29; owner: เริ่มทำ)

The first native R27 W1 failed at the restoration above: SET cannot replace an
existing limit. The SET wording and corresponding harness implementation were
incorrect. The three selected-owner risk scenarios completed before this error;
this run does not establish acceptance or overall performance compliance.

Proposed correction:

1. Replace only the post-scenario restoration SET with INCREASE to 1000, using
   the current revision and the exact same submission identity for authorization
   and intake. Keep all limit-5 breach/correction assertions before this change.
2. Reuse F-06 TOTP verification and the AUTH transaction pattern in
   `backend/tests/infra/risk_limits/profile_restore.py`; do not forge authorization
   through MIGRATOR or bypass verification. Synthetic fixture credentials only;
   never persist secrets in evidence/logs.
3. Add one harness AUTH pool, size 1 / overflow 0, for this one restoration.
   Include it in the premeasurement inventory (parent count 5 -> 6), declared
   capacity (+1), return evidence, disposal and physical cleanup checks. Existing
   API/engine/monitor pools, workers, CPU/RAM and PostgreSQL connection limits stay
   unchanged. This explicitly amends R27's no-new-pool restriction; it does not
   add RESET-processing capacity or change authorization/business rules.
4. Keep restoration inside the existing normal 60-second cycle budget, record
   its APPLIED receipt separately, and signal recovery_complete only afterward.
5. Before another workload, test the actual fixture path against PostgreSQL:
   verified authorization -> INCREASE APPLIED; missing authorization and changed
   submission rejected; unchanged balances/positions and no duplicate effects.
   Keep the oracle-ordering test, verify AUTH pool accounting/cleanup and affected
   request/worker contracts, then lint/format/types. The previous mock expected
   SET and did not cover this database contract.
6. After these checks, permit one new native W1 only, with frozen source/config
   and the original R25/R26/R27 thresholds. Stop on failure; do not start W2/W3/W4
   or repeat W1 automatically. Preserve the failed first R27 run.

Estimate after approval: 10–20 minutes for correction and targeted checks, then
15–20 minutes for one W1 including setup, 10-minute measurement and analysis.
These are planning estimates, not a promise of acceptance; announce any overrun.
Owner authorized implementation and one further W1 by instructing เริ่มทำ after reviewing R27-A.
