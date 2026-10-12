# R2-G1–G6 — Global build slot validation

วันที่: 2026-10-11
ผล: **Passed ตามผลทดสอบหลังแก้ review 4 ข้อ — พร้อมรีวิวซ้ำ**; G7 capacity ยังคง Deferred / Partial

ใช้ PostgreSQL16 แยกที่ port55433 และ worker containers บน
`tiewtrade-f11-test-net`. ไม่เปลี่ยน production code, migrations หรือ grants.

## หลักฐานล่าสุดหลังแก้ review 4 ข้อ

[รายงานการแก้และหลักฐานใหม่](global-review-fixed/README.md): **44passed/0failed/errors/skips**,
container/lease20กรณี269.233s + regression24กรณี11.115s.
G4ลองoldidentityทั้ง5operationsขณะsuccessor RUNNING/STAGINGบนphysicalowner sessionจริง
พร้อมstate equality/positiveheartbeat+READY; G3pause151.000sแล้วไม่มีcheckpoint/READY/
numeric attemptและcheckpoint/head rowsไม่เปลี่ยน; G1เพิ่มsourcecleanup barrierรวม15กรณี;
G2ตรวจcontenderระหว่างcleanup/actualunlockSQL/pg_locks; G6เพิ่มtable+columnprivileges
และactualzero-rowINSERT/UPDATE/DELETE. Ruff/formatและmypy338filesผ่าน.
แก้เฉพาะtests/harness/evidence ไม่เปลี่ยนproductioncodeหรือแผนที่อนุมัติ.

## หลักฐานรอบแรกก่อน review (ประวัติ)

ผลด้านล่างยังเก็บไว้ แต่ช่องว่างทั้ง4ข้อใช้หลักฐานใหม่ด้านบนปิด ไม่ใช้ยอด223เดิม
เป็นหลักฐานว่าการแก้ใหม่ผ่าน และไม่เพิ่มยอดผลรันย้อนหลัง.

- [Container barriers/faults](global-container-handoff-tests.xml): **16 passed, 94.594s**,
  ประกอบด้วย G1 จำนวน12 และ G4 จำนวน4; 0 failures/errors/skips
- [Real lease pause](global-real-pause-tests.xml): **1 passed, 157.356s**;
  หยุด container จริง **151.016s**, ไม่แก้ DB clock/lease เพื่อเร่งเวลา
- [Targeted regression](global-regression-tests.xml): **206 passed,
  0 failures/errors/skips, 91.053s**
- Ruff check/format ทั้ง5ไฟล์ใหม่ผ่าน; mypy src/tests **338 files** ผ่าน
- [L1–L6 evidence](source-lock-validation-report.md) เป็นหลักฐาน source-writer
  และ maintenance/F-09 protocol ประกอบ G5 ไม่เพิ่มยอด test เดิมเป็นผลรันใหม่

Paths ของ tests ด้านล่าง relative ต่อ `backend/tests/`; ตารางนี้เป็น mapping รอบแรก
โดย G1/G2/G3/G4/G6 ใช้รายละเอียดแก้ไขในรายงานล่าสุดด้านบนแทนส่วนที่ review พบช่องว่าง.

| Gate | หลักฐานและ assertions |
|---|---|
| G1 | `services/indicator_builder/profile_global_handoff.py`: 4 barriers before scan / in-flight synchronous core call / after checkpoint / before publish × same series / different series / different formula metadata. Actual contender คืน LOCK_BUSY ไม่มี claim/source/hash/core event; slotไม่เปลี่ยน, RUNNING jobหนึ่งตัว, pg_locks key711/1หนึ่ง owner. หลัง holder ปิด CPU/source/writer แล้ว successor จึงเริ่ม CPU และได้ READY. JSON `g1-{target}-{stage}.json` มี monotonic interval traces |
| G2 | `test_global_shutdown.py` 6 exit classes success/numeric/operational/timeout/cancel/no-job ตรวจ source+CPUปิดก่อน writer cleanup, checkout peak=2 (no-job=1), คืน connectionครบและ pool reacquireได้. `test_claims.py` ตรวจ committed claim, rollback/no-jobไม่กินattempt/round, serialized heartbeat physicalPIDเดิม, fresh acquisition และ reentrant/inherited-lock discard. `test_attempt.py` ครอบคลุม10 typed failures, claim uncertainty, publication lost acknowledgement, cleanup commit/rollback/close × timeout/cancel; `test_staging.py` ตรวจ heartbeat join, cleanup stall และ closed source. ไม่มี background CPU thread ใน implementation นี้ |
| G3 | `g3-real-pause.json`: paused holderยังมี writer backend หลังlease+deadlineหมด, contender LOCK_BUSYและverified reapปฏิเสธก่อนprocessจบ. Resumeได้ ORPHANED/OWNERSHIP_LOST ไม่publish; sourceปิดหลัง synchronous callคืนและก่อนwriterปิด. หลังcontainerจบจริง verified reapได้ REAPED; successor READYด้วยfence3 > fence1 และCPUเริ่มหลังold writerปิด. Expired/stale writes ถูกปฏิเสธโดย claim/staging/publication regression |
| G4 | container faults process kill / writer backend kill / network disconnect / isolated DB restart. หลังadvisoryหลุดแต่durable slot RUNNING ตัวใหม่ได้NO_JOBโดยไม่มีscan. Live ownerห้ามreap; หลังdocker kill/waitและverified stopจึงREAPED. Cycle/attempt/fair-round/eligibility/deadlineไม่reset. Fenceใหม่แล้ว old epoch/fence/owner/job/generation/token เรียกheartbeat/checkpoint/READY/numeric failure/releaseทั้ง5อย่างถูกปฏิเสธ. JSON `g4-{fault}.json`; ambiguous terminal commit/claim acknowledgementอยู่ใน `test_attempt.py`, ไม่อ้างว่าจำลองnetwork packet lossระหว่างCOMMITทุกจุด |
| G5 | `infra/indicators/test_global_lock_order.py` 15 real row-lock barriers: claim control→slot (jobใช้SKIP LOCKED), heartbeat slot→job, publication guard→control→slot→job, retry job (และrequest identityก่อนjob), GC guard→jobs, reap guard→control→slot→jobตามmigration0019. ใช้pg_blocking_pidsยืนยันwaitแล้วprobeFOR UPDATE NOWAITยืนยันprefixและabsenceของlocksที่ไม่ควรถือ. Cancelคืนrowlocks; reapคืนsession advisoryด้วย. G1ทั้ง12กรณีprobeว่าไม่มีguard/control/slot/job rowlockค้างระหว่างscan. L1–L6ครอบคลุมF-09 relation→guardก่อนclaim/candle locks, timeout/querytimeout/rollback/sessionreuse และไม่มีbuild slotในF-09 path |
| G6 | `test_global_permissions.py` 3 actualroles builder/API/market-data ตรวจครบ34indicator functions: exact allowlist, ไม่มีPUBLIC EXECUTE, forbidden entrypointsเรียกจริงได้42501 (รวมmigrator reap), directDELETEทุกindicator tableแม้WHERE falseก็42501. `test_claims.py` และstaging/publication regressionตรวจ owner/token/fence/backend/GUC spoof, stalelease, overflowทุกcounter, directDML, unsupportedpoolerก่อนconnect, rollout/proof invalidation และbackendlossไม่reconnectเพื่อresumeclaim |

## วิธีรันซ้ำ

ใช้ environment ของ isolated test DB/Redis ตาม test setup เดิม, cwd `backend`:

```text
uv run pytest tests/services/indicator_builder/profile_global_handoff.py -k "not paused_cpu" -q
uv run pytest tests/services/indicator_builder/profile_global_handoff.py -k paused_cpu -q
uv run pytest tests/infra/indicators/test_global_permissions.py tests/infra/indicators/test_global_lock_order.py tests/services/indicator_builder/test_global_shutdown.py tests/infra/indicators/test_claims.py tests/services/indicator_builder/test_attempt.py tests/infra/indicators/test_staging.py tests/infra/indicators/test_publication.py tests/services/indicator_builder/test_maintenance.py tests/services/indicator_builder/test_recovery.py -k "not full_m1" -q
```

ตั้ง `TIEWTRADE_GLOBAL_EVIDENCE_DIR` เมื่อต้องการ JSON traces. Container harness
ต้องเรียก explicitly; ไม่เพิ่ม151sเข้าnormal CI collection. Base image
`tiewtrade-api:latest` ให้ dependencies และ mount current workspace read-only
ผ่าน PYTHONPATH; codeที่ทดสอบเป็น working tree ปัจจุบัน ไม่ใช่ F-11 codeในimageเก่า.
G3หลักฐานเก่าก่อนเพิ่มsource PIDในtraceยังเก็บไว้โดยไม่เขียนทับเวลา/ยอดย้อนหลัง.

## ขอบเขตและข้อจำกัด

- CPU barrierอยู่ในwrapperรอบ synchronous `feed_batch` หลังเรียกcoreจริงหนึ่งbatch
  และยังไม่คืนcall; ไม่สร้างCPUthreadหรือstubผลคำนวณ. ไม่มีการอ้างว่าเป็นloadbenchmark.
- Different-formula caseพิสูจน์global exclusionเมื่อmetadata keyต่างกัน;
  restoreเป็นsupported formulaก่อนรันsuccessor ไม่อ้างว่าระบบรองรับformulaใหม่.
- Network disconnectอาจทิ้งread-only source backendฝั่งPostgreSQLไว้จนTCP keepalive
  หมดแม้containerหยุดแล้ว. Harness teardownยืนยันหยุดcontainersที่ตัวเองสร้างก่อน
  terminateเฉพาะsource PIDที่บันทึกไว้ของpartitioned probe. ผลนี้พิสูจน์fencing/
  verified stop/reap ไม่พิสูจน์ว่าproductionจะล้างsevered read sessionทันที;
  sessionนั้นอาจทำให้maintenanceรอ timeout ระหว่างnetwork outage.
- รอบพัฒนาแรกของnetwork caseผ่านassertionsแต่teardownรอsevered source session;
  แก้เฉพาะharnessให้cleanupแบบเจาะจงแม้testล้ม แล้วรันcontainer matrixใหม่.
- Regressionเลือกไม่รัน `test_full_m1_scan_is_bounded_and_has_at_most_527_checkpoints`;
  ยังไม่ปิดR2-7/exact525600/resource gateด้วยผลนี้. G7/full30series/two-replica
  capacity, loadและsoakอยู่ชุด9ตามอนุมัติเดิม.
- ไม่ปิด S1–S4, D2–D7 หรือ RQ/V/PV ที่ยังPartialแทน และไม่รับรอง Development
  Complete, merge, production PREPARED activation หรือ Completed.
