# R2-L1–L6 — Source lock protocol validation

วันที่: 2026-10-11
ผล: **Passed** ตามขอบเขต L1–L6; ไม่ปิด G/S/D gates แทน

หลักฐาน isolated PostgreSQL16/Python3.12 Windows:
- [Source/maintenance/F-09 regression](source-lock-validation-tests.xml):
  **179 passed / 0 failures/errors/skips, 92.858s**
- [Actual-role/runner/heartbeat regression](source-lock-role-regression-tests.xml):
  **16 passed / 0 failures/errors/skips**
- Ruff check/formatสองไฟล์และ mypy src/tests333filesผ่าน; git diff --checkผ่าน

## Mapping

Paths ต่อไปนี้ relative ต่อ `backend/tests/`.

| Gate | หลักฐานที่ตรวจครบ |
|---|---|
| L1 | `test_source.py::test_real_ingestion_acquires_scope_before_claim_and_candle_locks` เพิ่มBEGIN/COMMIT trace: startup demand commitก่อนcleanuptransactionใหม่; cleanup scopeก่อนDELETE; ทุกupserttransaction scopeก่อนclaim FOR UPDATE; ทุกvenuefetchอยู่นอกtransaction. `test_source_lock_matrix.py::test_scoped_f09_contender_waits_before_row_locks` ตรวจpg_locksว่าroot/ทุกpartitionได้RowExclusiveก่อนรอguard |
| L2 | matrixใหม่8กรณี root/leaf × single/multiplepartitions × actual F-09 upsert/cleanup; holderมีหลายrowsและcontenderรอguardจริงตามpg_blocking_pids แล้วprogressหลังcommit. Negativecontrol2กรณีroot/leafใช้ลำดับSELECT FOR UPDATEก่อนguard สร้างcycleจริงและได้SQLSTATE40P01โดยไม่ปิดtrigger |
| L3 | matrixใหม่12กรณี DROP/DETACH/TRUNCATE × actual API reader/MD writer × progress/locktimeout: maintenanceรอrelationก่อนguard rowlock; rollbackรักษาepoch/head/topology. อีก6กรณี typedpublisher/GC ทำงานขณะmaintenanceถือAccessExclusiveและรอguard; ตรวจpg_locksว่าpublisher/GCไม่มีcandle relationlock. อีก3กรณีstatementtimeoutหลังDDLจริงย้อนepoch/head/topologyร่วมกัน; publication regressionตรวจmaintenanceทำให้candidateเก่าถูกSUPERSEDED/EXPIREDและsafe release |
| L4 | source testsเดิม root/leaf missing scope, GUCspoof, committedscopeข้ามtransaction และ WRITE→MAINTENANCE rejection; เพิ่มupgradeไม่มีAccessExclusive, actualAPI/MD/builder helper matrix/directscopeownerDMLdenied และไม่มีPUBLIC EXECUTE. APISELECTไม่ต้องscope; maintenanceเฉพาะmigrator |
| L5 | เดิม guard/relation timeout ตรวจlockrelease/timeoutsettingsและphysicalsessionreuse; เพิ่มcancel/querytimeoutหลังwriteตรวจbackendPIDเดิมและscopeเก่าใช้ไม่ได้. Matrixใหม่ stale token/expiredlease/backenddisconnectหลังsource+journal+metadatawrite ยืนยันrollbackcounter/journal/rows/attemptcountและไม่มีrelation/tuple/transactionlockค้าง; stale/leaseใช้PIDเดิม, disconnectเปิดPIDใหม่แล้วเขียนได้ |
| L6 | F-09 actual upsert/batch/claim/retention/ingestion และrolepermissions/runnerregression; builder heartbeat actualrole/spoof/rollout-proof invalidation. ไม่มีproductiongrantเปลี่ยน ไม่มีsuperuserแทนruntimepath. Full-backend2324ผลเดิมเป็นbaselineประกอบ ไม่เพิ่มยอดย้อนหลัง |

`test_source.py` และ `test_source_lock_matrix.py` อยู่ใน `infra/indicators/`.
ชุด179แบ่งเป็น matrix39 + source31 + publication46 + maintenance15 +
F-09 batch5/claim1/retention15/ingestion27.
ชุด16เพิ่ม F-09 permissions/runner และ actualbuilder heartbeat cases.

## วิธีสร้าง barrier และข้อจำกัด

- ใช้ pg_blocking_pids/pg_locks เป็นหลักฐานรอจริง; sleep5msใช้pollแบบมีdeadline2s
  ไม่ใช้เวลานอนเป็นหลักฐานว่าล็อกแล้ว
- Publisher/GC ถือguardผ่าน `gc_indicator_data()` บนactualbuildertransaction
  ก่อนให้maintenanceรอ แล้วเรียกtyped publish/GCจริงในtransactionนั้น;
  builderยังไม่มีสิทธิ์directFOR UPDATEบนguard และไม่ได้เพิ่มสิทธิ์เพื่อสร้างbarrier
- Disconnectใช้MARKET_DATAอีกconnection terminatebackendของroleเดียวกัน
  ไม่เพิ่มpg_signal_backendให้migratorหรือใช้postgresแทนruntimewriter
- Maintenanceอ่านguardเพื่อตรวจWRITE-upgradeก่อนรอrelationได้ แต่ต้องยังไม่มี
  guard RowShare/RowExclusive/Exclusive lock; assertionแยกplaincatalog/readlock
  ออกจากการล็อกแถว ไม่ห้ามAccessShareที่จำเป็นต่อupgradecheck
- DDL testsใช้transactionrollbackเพื่อรักษาpartitionชุดทดสอบ; มีทั้งinjected
  exceptionหลังDDLและactualPostgreSQL statementtimeoutหลังDDL ไม่แก้triggerให้ผ่าน
- Testsใช้ฐานแยก55433เท่านั้น ไม่เปลี่ยนruntime/migration/productionconfiguration.
  หลังชุดหลัก control LEGACY/PENDING, slotIDLE, runtime sessions0

ผลนี้ไม่ครอบคลุม global CPU-slot/crash/networkpartition/fairness หรือcapacity;
G/S และ D2–D7 ที่ยังPartialต้องตรวจตามเกณฑ์ของตัวเอง. ไม่รันทดสอบโหลด/soakชุด9
และยังไม่รับรอง Development Complete/merge/productionactivation.
