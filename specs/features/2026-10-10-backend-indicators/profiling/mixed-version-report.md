# F-11 — Mixed-version acceptance evidence

วันที่: 2026-10-11
สถานะ: **Partial — รอ review; R2-D1..D7 ยังไม่ผ่านครบ**

เกณฑ์อ้างอิง: [R2-D1..D7 ที่อนุมัติ](../performance-plan-v2.md)
และ [rollout runbook](../rollout-runbook.md). ไม่มีการเปิด PREPARED ใน application DB.

## R2-D1 first release — Passed after fixes (2026-10-11)

แก้findingsทั้งสองแล้ว — [รายละเอียด](d1-harness-review.md).
[JUnitใหม่](first-release-fixed-tests.xml)1passed21.539s:
numeric READY parityทั้ง8แถว/4หน้าผ่านและmutationnegativecontrolrejectจริง;
[evidenceใหม่](first-release-fixed-evidence.json)มีschema/modeและrouting/HTTP/claim/
negative-control traceครบ. D1ผ่านเฉพาะfirst-release amendment ไม่รับรองD2..D7แทน.
ผลtest20.09sด้านล่างเก็บเป็นประวัติก่อนแก้: parity8แถวนั้นเป็นGAP.

เจ้าของยืนยันfirstreleasebaselineและอนุมัติ [amendment](../d1-amendment-proposal.md)
ด้วยคำสั่ง “approve”. ใช้แทนD1ที่ต้องมีoldF-11binaryซึ่งไม่เคยdeploy;
ข้อจำกัดการหาartifactเดิมด้านล่างเป็นประวัติก่อนamendment ไม่ใช่blockerD1ปัจจุบัน
D2..D7ยังใช้เกณฑ์เดิมและยังไม่รับรองactivationbundle

`profile_first_release.py`: **1 continuous lifecycle test passed / 0 failures/errors/skips**
ใน20.09s — [JUnit](first-release-tests.xml), [image/stage evidence](first-release-evidence.json)

- pre-F-11imageจริง health/auth/OpenAPI/F-09HTTPอ่าน360rows close100.5ตรงMoney
  และoldMDpathเขียนsource/cleanup365วันได้ก่อนstrictproof; indicatorrouteไม่มีในOpenAPI
  และunknownrouteถูกmiddlewareเดิมปฏิเสธ403
- compatibleimagesจริงทั้งสอง LEGACYv1page1/continuation A→B→A→Bหลังrestart,
  ครบ2rows/pageและ8rowsรวมตรงfullscan values/status/seed/finality/digest;
  signedv1claimsตรงidentity/nextposition ไม่มีv2issuance
- builderroleจริง seed0/claimNoneก่อนstagegate. inventoryขาดofflineoldcontainer,
  oldrestart=always และoldimagecapabilityไม่ผ่านถูกปฏิเสธ; proofยังPENDING
- drain/stopAPIทั้งสามและdisposehostpoolsก่อนrealorchestrate LEGACY→PREPARING;
  oldwriterหลังstrictproofได้SQLSTATE TT011จริง; compatibleF-09cleanupจริงทั้งสองผ่าน
  restartเฉพาะcompatibleAPIแล้วหน้าแรก503ตามstagegate ไม่เปิดPREPARED
- teardownลบเฉพาะauxcontainersของtestและคืนisolatedDBเป็นLEGACY/PENDING,
  slotIDLE/runtime sessions0. ไม่แตะapplicationDBหรือcapacityfixtures
- Ruffcheck/formatของharnessและmypy331filesผ่าน; ยังต้องreviewharnessก่อนปิดfinding

รอบพัฒนาharnessก่อนfinalrunพบassertionsที่ต้องแก้ตามพฤติกรรมจริง:
oldunknownroute403, candlequeryไม่รับpage_size, claimต้องใช้nativeownerUUID,
oldcapabilityprobeที่ไม่มีmoduleปฏิเสธด้วยOwnerStopUnverifiedError.
ไม่มีproductioncodechangeหรือเปลี่ยนข้อกำหนดเพื่อหลบfailure

## Current-image follow-up — 2026-10-11

รันlifecycleกับprepared imageจากworkingtreeปัจจุบันผ่าน1กรณี91.449s.
ผลเก่า/imageIDsด้านล่างเก็บเป็นประวัติ; imageIDใหม่และช่องว่างD2–D7อยู่ใน
[auditล่าสุด](d2-d7-coverage-audit.md), [JUnit](d2-current-image-tests.xml).
D3ยังต้องเติมsame-series seed/cleanup/pagination; ไม่ปิดD3–D7จากผลนี้.

## Environment และ artifacts

- Host Python3.12, isolated PostgreSQL16 port55433 และ Redis7 port56379;
  Docker network `tiewtrade-f11-test-net`. Harness ปฏิเสธ URL ของ application DB.
- API A: preserved compatible snapshot image `tiewtrade-f11-rollout-test:latest`,
  immutable Docker ID `sha256:b96ed3cf5c213a887bb5e631958498938f861384a620505425a7d747449d3302`.
- API B: current prepared snapshot image `tiewtrade-f11-mixed-test:latest`,
  immutable Docker ID `sha256:d5e03697b8aafb4eaf145ef30041909600c5d39c1ef548fcce8e0e084c4e3215`.
- Legacy F-09 image `tiewtrade-api:latest`, immutable Docker ID
  `sha256:dd045295cb6c6293f8c602b97f961d2f1a8593474fd2cdd1070b543fbb22d7be`.
  Module inspection ยืนยันว่า image นี้ **ไม่มี F-11 indicator route**;
  market-data/migrate images ที่มีอยู่ก็ไม่มี route นั้น.
- API processes ใช้ code ที่อยู่ใน immutable image จริง ไม่มี source mount หรือ
  decoder stub; DB roles/API authentication/Redis admission/HMAC ใช้งานจริง.
  Key configuration ใช้ public test values เท่านั้น; ไม่บันทึก keys/cookies/cursors.
- Worker สร้าง READY/manifests/checkpoints จริงครบ30seriesตาม365-day bounds:
  BTC/USDT4hมีOHLCVต่อเนื่อง ส่วนอีก29seriesเป็น sparse/empty lifecycle fixtures.
  ชุดนี้ไม่ใช่ full-data C1..C6 capacity evidence. Metadata ไม่ใช่ synthetic head rows.

## Coverage

| Gate | หลักฐานที่ตรวจแล้ว | ยังต้องทำก่อนรับรอง gate เต็ม |
|---|---|---|
| R2-D1 | Passed: approved first-release amendment; actual old F-09, compatible v1 numeric parity/restart, stagegate/inventory และevidence traceครบ | ไม่มีข้อค้างD1; D2..D7ยังต้องตรวจตามเกณฑ์ของแต่ละข้อ |
| R2-D2 | HTTP APIคนละprocess/image: pageA→B→A/randomrouting, full-scan rows parity, restart, validv1→409, tamper/formatspoof/cross-session→422, expired/retiredkey→409, re-enableold epoch→409; shared6/min quotaยังมีผล | ตรวจ release images/keyring configuration ที่จะ deployจริงอีกครั้ง; snapshotsนี้ยังไม่ใช่ production activationbundle |
| R2-D3 | Legacy F-09 cleanupจากimageจริงถูกstrictscopeปฏิเสธ; compatibleimagesทั้งสองลบเฉพาะเก่ากว่า365วัน+6h15m และเก็บboundaryprobe; offlinelegacyF-09ในinventoryบล็อกproofinstallโดยmode/epochไม่เปลี่ยน | Complete S0/S1 mixedstage และ seeddependency/cutoff workloadของ releaseจริงร่วมกับ D1/C |
| R2-D4 | LiveAPIpool/inflightHTTPsource-lock barrier, sourceROsnapshot และ cleanuptransaction บล็อกflip; join/stopก่อนpause; PAUSEDหน้าแรก503/validv2→409แม้checkpointpayloadถูกลบเป็นfaultfixture | Full build/cleanup/HTTP overlap rehearsalของ release workload; ใช้ global-slot/worker evidenceเดิมประกอบ ไม่อ้าง lightbarriersแทนcapacity |
| R2-D5 | Fresh/olderv2→409บนทั้งสองreplicasในPAUSED; sessionexpiry→401; cutoffจากDBและreplayไม่เลื่อน; actualdowngradeก่อน/ที่/หลังcutoff+6h, readerdrain; re-enableผ่านCASใหม่และไม่ฟื้นoldtoken | Full application/schema/key/grace retirement rehearsalตามrunbook; ยังไม่ได้รอ6hของdeploymentจริงหรือถอนapplication schema |
| R2-D6 | Actualruntime rolesไม่มีEXECUTE; graph/stale/replay/cancel/atomicproof tests; realDBcommitแล้วCLIresponseสูญหาย: อ่านstateใหม่และexactreplayALREADY_APPLIEDโดยepochไม่เปลี่ยน | Complete release fault matrixของhalf-installedgrants/controlmissing/unsupportedcodec และoperatorresumeตามrunbook |
| R2-D7 | Docker stop/start/restartจริง, offline/missinglegacyreplica inventorynegativecontrols และ actualCLI gate; ไม่อ้าง zero downtime | RehearsedCompose release deployment และ R2-C/L/F/G/regressionsหลังrollingupdate; capacityยังเป็นขั้นถัดไป |

Acceptance SQL transitions ใน lifecyclefixtureทดสอบ fixedmigrator helper กับ30
actualREADYheadsโดยตรง; ไม่สร้าง evidencebundleปลอมเพื่อให้production CLIเปิดได้.
Docker observationไม่ได้พิสูจน์ unmanaged hosts/offline controllers หรือ actual
productionkeyringdistribution; operatorต้องทำตามrunbook.

## Tests และวิธีรัน

แก้ review harness ทั้งสองข้อ: legacy cleanup ต้องยืนยัน SQLSTATE `TT011`
จาก exception chain (รวม implicit context ของ old release) โดยไม่พิมพ์ข้อความ error;
ข้อผิดพลาดอื่นให้ผล `FAILED` และไม่ผ่าน assertion. HTTP parity ตรวจครบ2แถวต่อหน้า
เทียบ reference ตาม offset ที่กำหนด พร้อมตรวจ signed cursor identity/ตำแหน่งถัดไป
ทุกหน้า. หลัง restart อ่าน input cursor เดียวกันบนทั้งสอง replicas เทียบ reference
และ cursor เดียวกัน แล้วต่อหน้าถัดไปข้าม replica; ไม่ใช้เพียง status200 เป็นหลักฐาน.

ผลล่าสุด: **53 passed / 0 failed / 0 errors / 0 skipped** รวมสองรายงานด้านล่าง.
Ruff lint/format353files, mypy325files และimportcontracts7ข้อผ่าน.
ไม่ได้รัน full-backend/capacity ใหม่ในphaseนี้; ไม่มีproduction code change.

- [HTTP multi-process lifecycle JUnit](mixed-replicas-tests.xml):
  `backend/tests/services/indicator_builder/profile_mixed_replicas.py`.
  **1 passed** ใน89.49s หลังแก้ review ทั้งสองข้อ. หนึ่ง continuous deployment rehearsalมีหลาย assertions;
  ไม่รายงานเป็นหลาย testcases.
- [Barrier/CAS/CLI JUnit](mixed-rollout-barriers-tests.xml):
  `backend/tests/infra/indicators/profile_rollout_barriers.py`,
  `backend/tests/infra/indicators/test_rollout.py` และ
  `backend/tests/services/indicator_builder/profile_rollout_containers.py`.
  **52 passed** ใน13.27s (newbarriercases7 + rolloutmodule44 + actualcontainerCLI1).

สร้าง current test imageด้วย `docker build -t tiewtrade-f11-mixed-test:latest backend`.
ตั้ง role URLsให้ชี้ isolatedPG55433 และ `TIEWTRADE_TEST_REDIS_URL` ไปisolatedRedis56379
ตาม environmentข้างต้น; APIcontainersใช้isolatedDocker networkเดียวกัน.
จาก `backend/` รัน profile filesข้างต้นโดยระบุ pathโดยตรงด้วยpytest.
Profilesไม่ถูก collectในnormal `test_*` suiteเพราะต้องมี Docker/isolatedservices.

Independent cursor rejection scenarios ล้าง test rate bucketsแบบAPI fixturesเดิม;
continuousroutingใช้≤6requests/window และมีแยก assertion6ผ่าน/ครั้งที่7ถูก429บน
อีกreplica. ไม่เปลี่ยน productionthresholdหรือปิดadmissionเพื่อให้testsผ่าน.
Sessionexpiryfixtureใช้API roleภายใต้presented-session RLSตั้งidle deadlineในอนาคต
ระยะสั้นแล้วรอให้หมดอายุจริง และตรวจว่าUPDATEจริงหนึ่งแถว;
ไม่ใช้owner-migratorเพื่อข้ามforced RLS.

คำสั่ง timeout/cancel และ ambiguouscommit test terminateเฉพาะ subprocess/backend
ที่ testสร้างและติดunique application_name. Auxiliarycontainersถูกcleanupด้วยIDs
ของtestเอง. ไม่แตะ applicationcontainer/database, routing หรือ Live Trading.

## ข้อจำกัดที่บล็อกการปิดข้อ1

ยังไม่มี preserved legacy F-11 full-scan artifactในGitหรือDocker imagesที่ค้นพบ.
คำถามเรื่องimage digest/source archiveส่งให้เจ้าของแล้ว; ไม่สมมติว่ารุ่นcurrent
ในLEGACYเท่ากับolddecoder และไม่รับรองR2-D1ด้วยstub.
R2-D7ยังขึ้นกับcapacity/regression release gatesที่ยังไม่ครบ. รายงานนี้จึงใช้แทน
complete R2-D activationevidenceไม่ได้ และ F-11คง In Progress.
