# F-11 — Validation mapping ก่อน merge

วันที่: 2026-10-11
อ้างอิง: performance-plan-v2.md และ amendment ที่เลื่อนโหลด/ระยะยาวไปชุดที่9

Passed = ตรวจหลักฐานตรงเกณฑ์ครบ; Partial = มีผลทดสอบส่วนหนึ่งแต่ยังไม่รับรองทั้งเกณฑ์;
Blocked = ขาดสิ่งจำเป็น; Deferred = อนุมัติเลื่อนเฉพาะส่วนโหลด/ระยะยาว
รายชื่อ test modules ด้านล่างเป็นหลักฐานที่มี ไม่ถือว่าการมีชื่อ test พิสูจน์ทุก clause
ของเกณฑ์แล้ว. ทุก Partial ที่ไม่ใช่ส่วน Deferred ยังค้างก่อน merge

หลักฐาน full suite: `resume-linux-final-tests.xml` (2324passed/1skip),
`resume-compose-test.xml` (skipนั้นผ่านบนhost), frontend-security-tests.xml,
frontend-e2e-tests.xml. การแก้ serialization เพิ่มหลักฐานเฉพาะจุดภายหลัง full suite;
ผล full suite เดิมไม่ถูกเปลี่ยนยอดย้อนหลัง

Paths ของ tests เป็น relative ต่อ `backend/tests/`.

| เกณฑ์ | สถานะ | หลักฐานที่มี | ส่วนที่ยังต้องตรวจ/วัด |
|---|---|---|---|
| R2-1 | Partial | api/test_prepared_indicators.py; services/indicator_builder/test_attempt.py | ยืนยัน empty-derived → scheduler → actual HTTP READY ใน traceเดียวครบ clause |
| R2-2 | Passed | infra/indicators/test_codec.py, test_checkpoint_parity.py, test_staging.py; independent parity_reference.py | — |
| R2-3 | Partial | infra/indicators/test_source.py, test_publication.py, test_staging.py | mapping ทุก barrier/root-leaf/publication-read permutation กับ clause |
| R2-4 | Partial | api/test_prepared_indicators.py; infra/market_data/test_retention.py | รวม fakeclock ทุกTF/oldestseed/expiry boundary evidence |
| R2-5 | Partial / Deferred | global-slot-validation-report.md: G1–G6Passed; claims/attempt/recovery regression | G7 full30series/two-replica capacityในชุด9; ไม่ปิดaggregateด้วยfunctionaltests |
| R2-6 | Partial | infra/indicators/test_source.py, test_rollout.py; infra/db/test_migrations.py | ตรวจทุก actual-role/DDL/replay privilege clause ใน matrix |
| R2-7 | Partial | capacity-report.md และ r2-7-coverage.json | exact525600fixtureยังขาด; เตรียม/ตรวจสั้นได้ก่อนรวมresourceacceptanceชุด9 |
| R2-8 | Deferred / Partial | capacity-report.md C1ผ่าน; C2Failed | capacityรอบเต็มชุด9; cold503 correctnessยังเป็นด่านก่อนmerge |
| R2-9 | Passed | core/test_indicators.py, test_indicator_arithmetic.py; test_checkpoint_parity.py และ numeric tests | — |
| R2-10 | Partial / Deferred | api/test_prepared_indicators.py; test_source.py/test_attempt.py/test_maintenance.py; serialization-prepared-regression.xml | serialization fix review Closed ตาม d1-harness-review.md; resource/continuouspressureในชุด9; outage/disconnect clausesยังต้องmapping |
| R2-11 | Partial / Deferred | test_codec.py; test_staging.py; test_maintenance.py และหลักฐานstoragepressureเดิม | resource/diskcap under continuousloadในชุด9; structuralboundsไม่เลื่อน |
| R2-12 | Passed | full backend2324+host1; frontend158; E2E10; lint/types/build/generated checks | หลังแก้ deadlineใช้ targeted regression; CI remoteยังไม่รัน |
| R2-L1 | Passed | source-lock-validation-report.md; source-lock-validation-tests.xml | startupcommit/cleanup/ทุกupsert/fetch trace และrelation-before-guard barriers |
| R2-L2 | Passed | test_source_lock_matrix.py; source-lock-validation-tests.xml | root/leaf, multirow/partition, upsert/cleanup; old-order cycleได้40P01จริง |
| R2-L3 | Passed | source-lock-validation-report.md; publication/maintenance regression | DDL×writer/reader/publisher/GC, progress/timeout และepoch/head/topology rollback |
| R2-L4 | Passed | source tests + helper privilege matrix/PUBLIC/upgrade tests | scope owner/transaction/root-leaf/API permissionsครบ |
| R2-L5 | Passed | source tests + staleclaim/expiredlease/disconnect matrix | timeout/cancel/rollback/locks/journal/counter/metadata/PIDreuseครบ |
| R2-L6 | Passed | source-lock-validation-tests.xml; source-lock-role-regression-tests.xml | actual-role F-09 regression/permissions และbuilderheartbeat ผ่าน; ไม่มีgrantผ่อน |
| R2-F1 | Passed | f1-f6-review.md; f1-f6-regression-tests.xml; worker/API failure_contracts + numeric_windows | NC-37 corrected; pre/post commit, outside-page numeric, 422/no retry/no old-head fallback |
| R2-F2 | Passed (current v1) | f1-f6-review.md; scheduler/numeric_windows/publication barrier matrix | same-input suppression and source/bounds changes; future formula revision requires its own approved validation |
| R2-F3 | Passed | api/test_failure_contracts.py + test_prepared_indicators.py; f1-f6-regression-tests.xml | proof/expiry/GC/candidate precedence and valid/invalid continuation |
| R2-F4 | Passed functional / Deferred load | test_failure_recovery.py + test_attempt.py; f45-final-tests.xml | exact 30/60s, fresh snapshot/state/session, fixed budget/deadline; full-load deadline ชุด9 |
| R2-F5 | Passed functional / Deferred load | test_failure_recovery.py + test_maintenance.py; f45-final-tests.xml | actual CLI 600s boundaries/duplicates/concurrency/crash/READY; full-load deadline ชุด9 |
| R2-F6 | Passed | f1-f6-review.md; global permissions/publication/maintenance/API errors/core Money regression | actual-role ACLs/PUBLIC, UUID injection rejection, sanitized errors, codec503/numeric422 |
| R2-N1 | Passed | numeric-window-report.md; numeric-window-tests.xml; worker/API test_numeric_windows.py | ครบ6TF boundary/samebounds, reconnect/newowner/globalfence/metadata/GC suppression; HTTP422/503 |
| R2-N2 | Passed | numeric-window-report.md; numeric-window-tests.xml | realMoney range failure→windowใหม่503→READY/200ตรงindependentoracle/fullscan/DBdigest; failedmanifest/sourceเดิมไม่แก้ |
| R2-N3 | Passed | numeric-window-report.md; numeric-window-tests.xml | Uexpand/Lseedchange/error-retainedเทียบfullscan; appendนอกU/proofmissingไม่ปลุกkeyเดิม |
| R2-N4 | Partial / Deferred | test_claims.py suppression/fairround; scheduler coalesce | 2replica/crash/GC/window matrixไม่เลื่อน; full-loadbudgetsชุด9 |
| R2-S1 | Passed (พร้อมรีวิว) | scheduler-validation/README.md; s1-expired.json; s1-unexpired.json | 2replicas, A supersededต่อเนื่อง, Bก่อนA2, round/CPU/shutdown traces |
| R2-S2 | Passed (พร้อมรีวิว) | scheduler-validation/tests.xml; regression-tests.xml | mixed failures, exact30/60, budget3, reconnect/workerrestart, ไม่มีclock-only revival |
| R2-S3 | Passed (แก้reviewแล้ว/พร้อมรีวิวซ้ำ) | scheduler-validation/README.md; review-fix-tests.xml; s3-crash-round.json | rollback/lostack/crash/reap, locked-unserved round barrier, DB barrierยืนยันclaim/reapรอcoalesce transactionจริง, nohotspin; pool2/timeout regression |
| R2-S4 | Passed (พร้อมรีวิว) | scheduler-validation/README.md; s4-lease-retry.json | 18event/cooldown + 3duplicateCLI boundaries; actuallease-loss/verifiedreap/retry; episode/missed preserved |
| R2-S5 | Deferred | capacity-report.md | full30seriescontinuoushistoricalwrite/29healthyชุด9 |
| R2-G1 | Passed (แก้reviewแล้ว/พร้อมรีวิวซ้ำ) | global-review-fixed/README.md; container-tests.xml20passed; regression-tests.xml24passed; global-regression-tests.xmlเดิม | 15 container barriersรวมsourcecleanup; actualunlockSQLหลังsourceclosed; contenderLOCK_BUSY |
| R2-G2 | Passed (แก้reviewแล้ว/พร้อมรีวิวซ้ำ) | global-review-fixed/README.md; container-tests.xml20passed; regression-tests.xml24passed; global-regression-tests.xmlเดิม | 6 exitclasses; contenderระหว่างsource/writercleanup; actualunlockSQL/pg_locks/poolreuse + regressionเดิม |
| R2-G3 | Passed (แก้reviewแล้ว/พร้อมรีวิวซ้ำ) | global-review-fixed/README.md; container-tests.xml20passed; regression-tests.xml24passed; global-regression-tests.xmlเดิม | realpause151.000s; resumed mutation attempts0; checkpoint/head rowsไม่เปลี่ยน; verifiedREAPED→READY |
| R2-G4 | Passed (แก้reviewแล้ว/พร้อมรีวิวซ้ำ) | global-review-fixed/README.md; container-tests.xml20passed; regression-tests.xml24passed; global-regression-tests.xmlเดิม | 4actualfaults; oldidentity5operationsบนactive successor owner session; stateไม่เปลี่ยน; positiveheartbeat+READY |
| R2-G5 | Passed | global-slot-validation-report.md; global-container-handoff-tests.xml; global-real-pause-tests.xml; global-regression-tests.xml | 15 row-lockprefix barriers + scanไม่มีrowguard + L1–L6 sourcewriter/timeout protocol |
| R2-G6 | Passed (แก้reviewแล้ว/พร้อมรีวิวซ้ำ) | global-review-fixed/README.md; container-tests.xml20passed; regression-tests.xml24passed; global-regression-tests.xmlเดิม | 34functions×3roles; table/columnINSERT/UPDATE/DELETE/TRUNCATE ACL; actualzero-rowINSERT/UPDATE/DELETEdenied |
| R2-G7 | Deferred / Partial | claims/recovery tests + capacity-report.md | full30series2replica capacityชุด9; logical retry/fenceไม่เลื่อน |
| R2-D1 (approved first-release amendment) | Passed | first-release-fixed-tests.xml; first-release-fixed-evidence.json; d1-harness-review.md | 1lifecycleผ่าน21.539s; numeric READY parityครบ8rows/4pages, mutationnegativecontrol และschema/mode/HTTP/claim/negative-control trace; ไม่รับรองD2..D7แทน |
| R2-D2 | Partial (functional current-imageผ่าน) | d2-current-image-tests.xml1passed91.449s; d2-d7-coverage-audit.md; mixed-replicas-tests.xml | deployment image/keyring configurationจริงยังต้องตรวจ |
| R2-D3 | Partial / Deferred | mixed-version-report.md cleanup TT011/grace; D1firstrelease | aged-seedข้ามcutoff365วัน/cleanup/continuationผ่าน1กรณี102.331s แก้reviewแล้ว/พร้อมรีวิวซ้ำตามd3-same-series-report.md; fullcapacityชุด9 |
| R2-D4 | Functional passed / scoped review APPROVED; capacity Deferred | d47-post-update-regression.xml (213 passed), d4-reviewed-evidence.json; d4-active-build-tests.xml (52 passed), d4-active-build-evidence.json, d4-active-build-report.md; existing mixed-rollout barriers | real active build blocks activate/pause, observed exit/drain before flip, HTTP cutoff/SQL audit; source/cleanup/inflight HTTP companion scenarios separate; production CLI/release rehearsal not certified, workloadcapacityชุด9 |
| R2-D5 | Functional passed | d57-compose-tests.xml / d57-compose-evidence.json; companion mixed-replica/cutoff tests | actual schema/key/grace retirement after support and drain; controlled DB cutoff, pre-F11 binary per D1 baseline; see d47-combined-review.md |
| R2-D6 | Functional passed (NC-36 corrected) | d6-grants-fixed-tests.xml80passed; d57-compose-tests.xml89passed | required privilege matrix, independent catalog inventory, missing trigger/control/codec/protocol, actual inventory/operator inspect/replay; original failure retained as history |
| R2-D7 | Compose functional passed / aggregate Partial | d57-compose-tests.xml89passed / d57-compose-evidence.json; d47-combined-review.md | real Compose stop/drain/start + compatible rolling images + inventory negatives; remaining F acceptance and full capacity/release dependencies not certified, load/soakชุด9 |
| R2-C1 | Passed (รอบเดิม) | capacity-c1-v2 | เก็บผล365.406s/30series; ต้องตรวจรับรวมตามreleaseชุด9 |
| R2-C2 | Deferred / Failedเดิม | capacity-c2-v2 | lag109.465ms; ต้องแก้และวัดรอบเต็มชุด9 |
| R2-C3 | Deferred | capacity-report.md | ยังไม่รัน |
| R2-C4 | Deferred / Partial | fairness-resources.json; scheduler-validation/README.md | S1..S4 testsสั้นผ่าน/รอรีวิว; fullcapacity fairnessยังอยู่ชุด9 |
| R2-C5 | Deferred | capacity-report.md | ยังไม่รัน |
| R2-C6 | Deferred / Failedเดิม | capacity-gates.json | ต้องครบ C1..C5/R2-7/resources/parityก่อนactivation/Completed |

## การใช้ตารางนี้

ตารางทำให้ coverage ที่ยังไม่ครบมองเห็นได้ ไม่ปิด findingsด้วยยอดtestรวม.
ปิดD1harnessสองข้อแล้วตาม d1-harness-review.md และN1..N3ตามnumeric-window-report.md;
ปิดL1..L6ตามsource-lock-validation-report.mdแล้ว;
G1–G6แก้review4ข้อแล้วและผลใหม่44passedตามglobal-review-fixed/README.md; พร้อมรีวิวซ้ำ;
S1–S4เติมหลักฐานแล้ว179passedตามscheduler-validation/README.md; รอรีวิวharness.
S1–S4รีวิวผ่านหลังแก้S3; D2current-image lifecycleผ่าน1กรณี91.449s.
ตรวจช่องว่างD2–D7แล้วในd2-d7-coverage-audit.md; D3 same-series
seed/cleanup/paginationแก้reviewaged-seedแล้วผ่าน1lifecycle102.331s; รีวิวD3ซ้ำก่อนดำเนินD4..D7.
ก่อน merge ต้องตรวจrequirements RQ และ baseline V/PV ที่คงมีผลร่วมด้วย;
ตาราง R2 นี้ไม่ใช่การยกเว้น baseline criteria หรือสัญญา NC-30..33
