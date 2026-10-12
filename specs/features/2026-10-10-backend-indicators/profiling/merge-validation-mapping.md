# F-11 — Validation mapping ก่อน merge

วันที่ตรวจ mapping ล่าสุด: 2026-10-12
อ้างอิง: performance-plan-v2.md และ amendment ที่เลื่อนโหลด/ระยะยาวไปชุดที่9

Passed = ตรวจหลักฐานตรงเกณฑ์ครบ; Partial = มีผลทดสอบส่วนหนึ่งแต่ยังไม่รับรองทั้งเกณฑ์;
Blocked = ขาดสิ่งจำเป็น; Deferred = อนุมัติเลื่อนเฉพาะส่วนโหลด/ระยะยาว
รายชื่อ test modules ด้านล่างเป็นหลักฐานที่มี ไม่ถือว่าการมีชื่อ test พิสูจน์ทุก clause
ของเกณฑ์แล้ว. ทุก Partial ที่ไม่ใช่ส่วน Deferred ยังค้างก่อน merge

หลักฐานปัจจุบัน: `ad-linux-final-tests.xml` (2514passed/1skip),
`ad-consumer-tests.xml` (19passed รวม Compose ที่ Linux skip),
`ad-frontend-tests.xml` (158passed), `ad-static-checks.json`.
ผล full suite เดิม2324/1skipและE2E10ยังเก็บเป็นประวัติ ไม่ถูกนับเป็นรอบใหม่.
ดูขอบเขตและลำดับการแก้ใน `ad-validation-report.md`; counts overlap ห้ามบวกยอด.

หลังแก้สองข้อรีวิว: `ad-review-fixes-tests.xml` (164passed/1skip),
`ad-review-writer-tests.xml` (70passed), `ad-review-host-tests.xml` (1passed
ครอบคลุมComposeที่skip). ตรวจ static ซ้ำผ่าน; พร้อมรีวิวซ้ำ ไม่อ้างfull-suiteรอบใหม่.

Paths ของ tests เป็น relative ต่อ `backend/tests/`.

ตรวจ Partial รอบรวมแล้ว: [pre-merge coverage audit](premerge-coverage-audit.md).
A–D มีหลักฐานใหม่แล้ว: [current report](ad-validation-report.md),
[baseline RQ/V/PV crosswalk](baseline-coverage-crosswalk.md); audit เดิมเก็บเป็นประวัติ.
ผลเดิมและ release/capacity gates ไม่ถูกเปลี่ยนเป็น Passed ด้วย audit นี้.

| เกณฑ์ | สถานะ | หลักฐานที่มี | ส่วนที่ยังต้องตรวจ/วัด |
|---|---|---|---|
| R2-1 | Passed functional / ready for review | ad-linux-final-tests.xml; ad-consumer-tests.xml: empty-derived → real scheduler/publication → HTTP200 | ดู ad-validation-report.md; ไม่ใช่ capacity acceptance |
| R2-2 | Passed | infra/indicators/test_codec.py, test_checkpoint_parity.py, test_staging.py; independent parity_reference.py | — |
| R2-3 | Passed functional | source-lock/publication/race suites + six identity move commit/rollback cases in ad-linux-final-tests.xml | old/new scopes invalidated on commit, preserved on rollback; unrelated scope valid |
| R2-4 | Passed functional | N1–N3/D3 + exact600s boundary and independent token/generation expiry at entry/response in ad-linux-final-tests.xml | Session fixture update verified through presented-session role |
| R2-5 | Passed functional / Deferred load | G1–G6 fixes + S1–S4/F4/F5/N4; premerge-coverage-audit.md | G7 30series/two-replica capacity ชุด9; ไม่ปิด aggregate |
| R2-6 | Passed | source/role/DDL/replay/downgrade tests; premerge-security-catalog.json | 35 related functions/28 hardened definers, PUBLIC denied, runtime public CREATE denied; deployment catalog ต้องตรวจตอน release |
| R2-7 | Fixture passed / Deferred measurement | exact-fixture-tests.xml; exact-fixture.json: 525600 dense rows, 527 checkpoints, independent digest matches | cold1/warm5/RSS/lag/resource acceptance ชุด9; historical525599ไม่ถูกเปลี่ยนเป็นPassed |
| R2-8 | Passed cold-miss / Deferred capacity | test_missing_ready_never_builds_or_writes_demand; N4 HTTP no-DML/partial | R2-1 lifecycle ผ่านแล้ว; C1..C6 รอบเต็มชุด9; C2Failedเดิมคงไว้ |
| R2-9 | Passed | core/test_indicators.py, test_indicator_arithmetic.py; test_checkpoint_parity.py และ numeric tests | — |
| R2-10 | Passed functional / ready for re-review / Deferred load | ad-review-fixes-tests.xml: stalled rollback/invalidate abort, actual PG transport/pool reuse, original deadline504; ASGI/repeatedcancel and DB/Redis recovery regression | continuous pressure ชุด9; no production release claim |
| R2-11 | Passed structural / Deferred resource acceptance | codec oversized; staging weakref/bounded batches; prepared prefix<=1999; GC<=1000; finite storage pressure | sustained-load disk/resource caps ชุด9; sparse full-M1 scan ไม่แทน dense R2-7 fixture |
| R2-12 | Local gates passed / remote CI pending | backendLinux2514passed+Compose host; consumer19passed; frontend158; static/build/generated checks; ad-validation-report.md | ready for review; remoteCI/owner Git actions remain separate |
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
| R2-N4 | Passed functional (review APPROVED) / Deferred load | n4-validation/README.md; n4-tests.xml 49ผ่าน; n4-final-tests.xml 3ผ่านซ้ำ; n4-review-fixed-tests.xml 7ผ่านแก้review deadline/GC + live M1 | actual 2 replicas/RUNNING/outage/crash/GC/latest-window/HTTP; full-load budgets ชุด9 |
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
| R2-G7 | Passed logical prerequisites / Deferred capacity | G1–G6/S1–S4/F4–F5/N4; premerge-coverage-audit.md | full30series/2replica resource acceptance ชุด9 |
| R2-D1 (approved first-release amendment) | Passed | first-release-fixed-tests.xml; first-release-fixed-evidence.json; d1-harness-review.md | 1lifecycleผ่าน21.539s; numeric READY parityครบ8rows/4pages, mutationnegativecontrol และschema/mode/HTTP/claim/negative-control trace; ไม่รับรองD2..D7แทน |
| R2-D2 | Passed functional / Release inventory pending | d2-current-image-tests.xml; subsequent D3/D4/Compose lifecycle | production image/key inventory เป็น release obligation ไม่ใช่สิ่งที่ public fixture keys รับรอง |
| R2-D3 | Passed functional / Deferred capacity | d3-aged-seed-tests.xml1passed102.331s; d3-aged-seed-evidence.json; D1/D5/D7 | aged same-series seed/cleanup/continuation แก้reviewแล้ว; capacityชุด9 |
| R2-D4 | Functional passed / scoped review APPROVED; capacity Deferred | d47-post-update-regression.xml (213 passed), d4-reviewed-evidence.json; d4-active-build-tests.xml (52 passed), d4-active-build-evidence.json, d4-active-build-report.md; existing mixed-rollout barriers | real active build blocks activate/pause, observed exit/drain before flip, HTTP cutoff/SQL audit; source/cleanup/inflight HTTP companion scenarios separate; production CLI/release rehearsal not certified, workloadcapacityชุด9 |
| R2-D5 | Functional passed | d57-compose-tests.xml / d57-compose-evidence.json; companion mixed-replica/cutoff tests | actual schema/key/grace retirement after support and drain; controlled DB cutoff, pre-F11 binary per D1 baseline; see d47-combined-review.md |
| R2-D6 | Functional passed (NC-36 corrected) | d6-grants-fixed-tests.xml80passed; d57-compose-tests.xml89passed | required privilege matrix, independent catalog inventory, missing trigger/control/codec/protocol, actual inventory/operator inspect/replay; original failure retained as history |
| R2-D7 | Compose functional passed / Aggregate Partial | d57-compose-tests.xml89passed; d47-combined-review.md; F1–F6/N4 ล่าสุด | F/N4ไม่ค้างแล้ว; aggregate ยังขึ้นกับ A–D review + capacity/release |
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

## สรุป audit ล่าสุด — 2026-10-12

N4 ผ่านรีวิวซ้ำหลังแก้ deadline/GC และ live M1 ตามการสนทนาแล้ว.
ข้อความ “รอรีวิว/Partial” ในบันทึกก่อนหน้าที่ไม่ตรงกับหลักฐานล่าสุดเป็นประวัติ;
ใช้แถวเกณฑ์ปัจจุบันร่วมกับ premerge-coverage-audit.md สำหรับงานที่ยังค้าง.
ก่อน merge ยังมีงาน A (API lifecycle/boundaries/failures), B (source identity move),
C (exact fixture prerequisite), D (RQ/V/PV crosswalk และด่านสุดท้าย).
นี่เป็นรายการช่องว่างหลักฐาน ไม่ใช่การพบ production bugs สี่ข้อ.
