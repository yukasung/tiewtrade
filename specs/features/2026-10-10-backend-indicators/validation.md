# F-11 — คำนวณ indicator ที่ backend — Validation

สถานะ: **Approved** — เจ้าของอนุมัติทั้งฉบับเมื่อ 2026-10-10 ตามคำสั่ง “approve”; เริ่มตรวจ implementation แล้ว แต่ยังไม่ผ่านครบทุกด่าน; รวมNC-35 amendmentsที่อนุมัติเมื่อ2026-10-10
วันที่: 2026-10-10
Branch: feature/f-11-backend-indicators

## F1–F6 correction / functional validation — 2026-10-12

เจ้าของสั่ง “แก้ไข” ปิด NC-37 โดยใช้ snapshot เดิมสร้าง metadata สำหรับ numeric
publication หลัง source/heartbeat ปิด; ไม่คำนวณซ้ำหรือ reset retry budget.
ผล regression **241 ผ่าน / 0 failed / 0 error / 0 skipped ใน 137.754s**;
ตรวจ F4/F5 ซ้ำหลังเพิ่ม fresh snapshot/stream assertions **8 ผ่าน**.
Ruff/format, strict mypy 347 files และ architecture 7 contracts ผ่าน.
F1/F2/F3/F6 functional Passed สำหรับสูตร v1 ที่อนุมัติ; F4/F5 functional Passed
แต่ full-load deadline/capacity ยัง Deferred ชุดที่ 9. รีวิว correction: APPROVED.
[รายละเอียดรายข้อ/ขอบเขต/หลักฐาน](profiling/f1-f6-review.md).
ไม่ปิด N4 หรือ aggregate F-11; ไม่รัน load/soak. ผล Failed ด้านล่างเป็นประวัติก่อนแก้.

## ประวัติก่อนแก้: F1–F6 audit — F1 Failed / NC-37 — 2026-10-12

เพิ่ม fault injection typed numeric ก่อน/หลัง STAGING commit ตาม R2-F1:
ก่อน commit ได้ RELEASED/OPERATIONAL แทน FAILED_NUMERIC; หลัง commit ผ่าน.
ผล **1 failed, 1 passed** — [JUnit](profiling/f1-staging-boundary-tests.xml).
เป็น injected boundary case ไม่ใช่หลักฐานว่าข้อมูล production ปกติกระตุ้น path นี้ได้.
ยังไม่แก้ production code; หยุดตาม AGENTS.md และบันทึก NC-37.
[รายงาน/แนวแก้/coverage F1–F6](profiling/f1-f6-review.md).
ไม่ปิด F1–F6 หรือ N4; ไม่รัน load/soak.

## D4–D7 combined implementation review — APPROVED เฉพาะขอบเขต functional — 2026-10-12

ไม่พบ finding ค้างในการรีวิวรวม; NC-36 แก้และ regression ผ่านแล้ว.
Compose/rollout/grant suite **89 passed / 117.997s** และ post-update D4/L/F/G/API
regression **213 passed / 165.597s**, ทุกชุด 0 failure/error/skip.
Ruff/format, mypy344files, architecture7contracts และ git diff --check ผ่าน.
Teardown: schema0023, LEGACY, slotIDLE, API SELECT คืนครบ, runtime sessions0,
ไม่มี Compose rehearsal containers ค้าง.
[รีวิวรวม](profiling/d47-combined-review.md) ·
[Post-update JUnit](profiling/d47-post-update-regression.xml) ·
[D4 current-image trace](profiling/d4-reviewed-evidence.json).
D7 aggregate ยัง Partial ตาม F/C acceptance ที่ค้าง; ไม่อนุมัติ production activation,
merge หรือ F-11 Completed. การทดสอบยาวยังอยู่ชุดที่9.

## D5–D7 implementation / NC-36 correction — 2026-10-12

เจ้าของสั่งแก้ NC-36 แล้ว: migration0023 ตรวจ required SELECT/EXECUTE ของ
API/F-09/builder ก่อน transition ที่ไม่ใช่ PAUSED; grants ไม่ครบได้ POLICY_UNSUPPORTED
และ mode/epoch ไม่เปลี่ยน. Matrix ถอนสิทธิ์ทุกรายการ/คืนสิทธิ์/PAUSE/replay ผ่าน;
ตรวจ catalog อิสระกัน manifest ตกหล่น และ trigger/control/codec/protocol faults ผ่าน.

Compose rehearsal + grant/rollout/barrier regression **89 passed, 0 failures/errors/skips,
117.997s**. มี compatible rolling update สอง images, cursor parity, actual inventory
negative controls, operator inspect/replay และ retirement/schema/key/grace ตามลำดับ.
[รายงานรีวิวรวม/ข้อจำกัด](profiling/d47-combined-review.md) ·
[JUnit](profiling/d57-compose-tests.xml) · [trace](profiling/d57-compose-evidence.json).
ผลแก้ grants รอบแรก80ผ่าน9.908s: [JUnit](profiling/d6-grants-fixed-tests.xml).
ไม่ใช่ production activation; D7 aggregate ยังขึ้นกับ F/C gates ที่เหลือ,
capacity/soak ยังคงชุดที่9. F-11 ยัง In Progress.

## D6 partial-grant fault — ประวัติ Failed ก่อนแก้ NC-36 — 2026-10-12

ตรวจ actual SQL transition หลังถอน SELECT ของ API บน indicator_ready_generations:
grants ไม่ครบแต่ยังได้ APPLIED และเปิด PREPARED ขัด R2-D6.
Regression **1 failed**; คืน grants/control ผ่าน transaction rollback แล้ว.
[หลักฐาน/แนวแก้](profiling/d6-partial-grant-report.md) ·
[JUnit](profiling/d6-partial-grant-tests.xml).
รอบพบปัญหาหยุดตาม AGENTS.md; เจ้าของอนุมัติแก้แล้ว ผลแก้และรีวิวรวมอยู่หัวข้อใหม่ด้านบน.

## D4 active build / rollout barriers — ผ่าน / พร้อมรีวิว 2026-10-12

เพิ่ม real CPU-build barrier ทั้ง PREPARING→PREPARED และ PREPARED→PAUSED:
ขณะ worker ทำงาน transition ได้ NOT_DRAINED และ control/slot ไม่เปลี่ยน;
หลัง worker exit, API stop และ DB sessions drained จึงเปลี่ยน epoch ได้.
ตรวจ cursor ก่อน pause เทียบ DB cutoff และ HTTP หลัง pause ทั้งสอง images
ได้ 503/409; SQL observer มี positive control และไม่พบ payload read/indicator DML
ใน PAUSED พร้อม derived-row snapshot ไม่เปลี่ยน.

ผลรวม harness ใหม่และ rollout/barrier regression **52 passed, 0 failures/errors/skips,
91.981s**; Ruff/format และ mypy 341 files ผ่าน. Teardown: slot IDLE, API/auth/builder
sessions 0. [รายงาน/ข้อจำกัด](profiling/d4-active-build-report.md) ·
[JUnit](profiling/d4-active-build-tests.xml) · [trace](profiling/d4-active-build-evidence.json).
ใช้ restricted SQL helper สำหรับ positive activation บนฐานทดสอบ ไม่ใช่การรับรอง
production orchestration/capacity gate. ไม่แก้ production code หรือรัน load/soak.
รอรีวิว D4; D5–D7 ยังไม่ครบ และ capacity ยังคงชุดที่ 9. F-11 ยัง In Progress.

## D3 same-series cleanup/pagination — ผ่าน / พร้อมรีวิว 2026-10-11

แก้reviewเรื่องseedยังไม่ข้ามcutoffแล้ว: controlledclockที่seed+365วัน+1µs
สำหรับcleanupและAPIทั้งสองreplicas ตรวจอายุgenerationจากHTTPตรงเวลาทดสอบ,
cursor/generationเดิมยังไม่หมดอายุ และseedจริงยังอยู่ในgrace.
ผลรอบแก้ **1passed102.331s/0failed/errors/skips** —
[JUnit](profiling/d3-aged-seed-tests.xml) · [trace](profiling/d3-aged-seed-evidence.json).
Ruff/format/mypy340filesผ่าน; พร้อมรีวิวซ้ำ. ผล125.024sด้านล่างเป็นประวัติก่อนแก้.

เติมcursorก่อนcleanup BTC/4h seriesเดียวกัน ตรวจseedทั้งแถวไม่เปลี่ยน,
grace probeยังอยู่ และcontinuationบนทั้งสองreplicasตรงfullscan/cursorclaims.
Legacycleanupได้TT011; lifecycleรวมD2/D3/D4/D5เดิม **1passed125.024s**, ไม่มีfailure/error/skip.
Ruff/formatและmypy340filesผ่าน; ไม่แก้productioncode ไม่รันload/soak.
[รายงาน/ข้อจำกัด](profiling/d3-same-series-report.md) ·
[JUnit](profiling/d3-same-series-tests.xml) · [trace](profiling/d3-same-series-evidence.json).
รอรีวิวหลักฐานD3ร่วมกับD1เดิม; D4–D7และcapacityยังไม่ปิด. F-11ยังIn Progress.

## D2 current-image verification / D2–D7 coverage audit — 2026-10-11

สร้างprepared test imageจากworkingtreeปัจจุบันและรันคู่compatibility imageเดิม:
actualPG/Redis/HTTP lifecycle **1passed/0failed/errors/skips91.449s**.
หลักฐาน [JUnit](profiling/d2-current-image-tests.xml) และ
[auditรายเกณฑ์/imageIDs/ข้อค้าง](profiling/d2-d7-coverage-audit.md).
D2 functionalchecksผ่านบนtest deployment; release image/keyringจริงยังต้องตรวจ
ก่อนdeploy ไม่ใช้publictestkeysรับรองproductionactivation.
D3–D7ยังPartial; งานถัดไป D3 cleanupระหว่างpaginationของseriesเดียวกัน
พร้อมseed dependency. ไม่แก้productioncodeหรือรันcapacity/soak.

## R2-S1–S4 scheduler validation — Passed / พร้อมรีวิว 2026-10-11

แก้review S3แล้ว: DB barrierยืนยันcoalesce transactionยังไม่commitขณะclaim/reap
รอlockจริง พร้อมPID/lock graph/traceและตรวจround/token/counter.
รอบแก้30กรณีอื่นผ่าน; S3แก้timestamp assertionแล้วrerunเฉพาะจุดผ่าน1กรณี10.911s
ตาม `profiling/scheduler-validation/review-fix-tests.xml`; พร้อมรีวิวซ้ำ.
ยอด179ด้านล่างเป็นผลก่อนแก้ ไม่ใช่การรัน179กรณีใหม่.

เพิ่มหลักฐาน fairness สอง worker จริง, mixed retry budget/backoff, atomic round/
rollback/lost acknowledgement, crash/reap และ source-event/cooldown/manual CLI.
**31กรณีใหม่ผ่าน73.594s + regression148ผ่าน36.959s = 179passed/0failed/errors/skips**.
Ruff/formatสองไฟล์และmypy340filesผ่าน; ไม่แก้productioncode.
[Mapping, traces และข้อจำกัดการควบคุมเวลา](profiling/scheduler-validation/README.md).
S5/full-load/soakยังเลื่อนไปชุด9; รอรีวิวharnessนี้และปิดด่านที่ไม่เลื่อนอื่น
รวมD2..D7ก่อนDevelopment Complete. F-11ยังIn Progress.

## R2-G1–G6 global build slot validation — Passed หลังแก้ review 2026-10-11

แก้harnessครบ4ข้อและพร้อมรีวิวซ้ำ: active-successor staleidentity, expired-owner
mutation assertions, actualunlock/cleanup contender และtable+columnDMLpermissions.
ผลใหม่ **44passed/0failed/errors/skips**: container/lease20กรณี269.233s
(รวมrealpause151.000s) + shutdown/ACL/lock-order regression24กรณี11.115s.
Ruff/format4ไฟล์และmypy338filesผ่าน.
[รายละเอียดการแก้/หลักฐานใหม่](profiling/global-review-fixed/README.md).
ผล223passedรอบก่อนคงเป็นประวัติใน[รายงานเดิม](profiling/global-slot-validation-report.md)
ไม่ใช้แทนการทดสอบการแก้ใหม่. ฐานแยกหลังจบLEGACY/PENDING, slotIDLE, builder sessions0.
ไม่เปลี่ยนproductioncode/grants; G7/full-load/soakอยู่ชุด9, ณรอบGนี้ S1–S4/D2..D7
และด่านPartialอื่นยังคงค้าง จึงยังไม่Development Complete/Completed.

## R2-L1–L6 source lock validation — Passed 2026-10-11

ปิดL1–L6ด้วยactualPostgreSQL barrier/lock graph, startup/fetch transactiontrace,
root/leaf/multirow/partition, old-order40P01negativecontrol, DDL×writer/reader/
publisher/GC, timeout/cancel/disconnect/claimrollback/sessionreuseและactualroles.
**179+16passed/0failed/errors/skips**, ชุดหลัก92.858s;
Ruff/formatและmypy333filesผ่าน.
[mapping/ข้อจำกัด/หลักฐาน](profiling/source-lock-validation-report.md).
ไม่แก้productioncode/grants; G/S/D2..D7ยังไม่ถูกปิดด้วยผลนี้ และไม่รันทดสอบยาวชุด9.

## R2-N1–N3 numeric window validation — Passed 2026-10-11

ปิดN1–N3ด้วยcontrolled DB clockครบ6TF, durable suppressionหลังreconnect/newowner/
globalfence/metadata/GC และactual worker→HTTP422/503/200ตรงoracle/fullscan/DBdigest.
**52passed/0failed/errors/skips38.353s**, Ruff/formatและmypy332filesผ่าน.
[รายงานและข้อจำกัดfault injection](profiling/numeric-window-report.md) ·
[JUnit](profiling/numeric-window-tests.xml).
ไม่เปลี่ยนproductioncode; N4/L/G/S/D2..D7ที่ยังPartialคงค้าง; ไม่รันทดสอบยาวชุด9.

## R2-D1 first-release amendment — Approved 2026-10-11

เจ้าของยืนยันว่าไม่เคยdeploy F-11 full-scan เดิม และอนุมัติ
[D1 first-release amendment](d1-amendment-proposal.md) ด้วยคำสั่ง “approve”.
ใช้เกณฑ์ทั้ง5ข้อใน amendment แทน R2-D1 legacy-F-11-binary เดิมเฉพาะส่วนนี้:
ทดสอบ pre-F-11 API/F-09จริงก่อนstrictproof และ compatibleF-11สองreplicas
ในLEGACYด้วยv1cross-replica/restart/fullscanparity พร้อมstagegate/drain/inventory
negativecontrols. ห้ามstubและไม่ผ่อนD2..D7/capacity/productionactivation.
D1เป็นPendingจนหลักฐานครบ ไม่ถือว่าการอนุมัติคือPassed


## เปลี่ยนลำดับการตรวจรับ — Approved 2026-10-11

เจ้าของยืนยันให้เลื่อนการทดสอบโหลดและความเสถียรระยะยาวไปตรวจรับระบบรวม
**ชุดที่ 9 — ตรวจรับระบบก่อนใช้งานจริง หลังพัฒนาชุดที่ 8 เสร็จ** ตาม [roadmap](../../roadmap.md#ชุดที่-9--ตรวจรับระบบก่อนใช้งานจริง)
ข้อความนี้แทนลำดับเดิมที่ให้รันทดสอบยาวทันทีท้าย implementation ของ F-11;
ไม่เปลี่ยนสูตร งบ ระยะเวลาวัด workload หรือเกณฑ์ผ่านของการตรวจรับ

ระหว่างพัฒนายังคงทดสอบความถูกต้อง ความปลอดภัย การคำนวณเงิน และ regression
ที่เกี่ยวข้อง ผล Failed/Partial เดิมและ API lag ที่พบยังเป็นงานค้าง ไม่ถือว่าผ่าน
R2-C2/C3/C5 รอบเต็มและการตรวจรับ capacity/ความเสถียรที่ต้องใช้ผลเหล่านั้น
ให้รวมในชุดที่ 9; การ profile สั้นและการแก้ปัญหาที่ทราบทำได้ระหว่างพัฒนา

เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบ จึงใช้สถานะ
Development Complete (พัฒนาเสร็จ รอตรวจรับระบบ) ตาม roadmap ได้ ไม่ใช่ Completed
เจ้าของอนุมัติ 2026-10-11 ให้ merge เพื่อพัฒนาต่อได้เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบ ตาม [testing standard](../../standards/testing.md#1-ต้องเขียวก่อน-merge);
ข้อความนี้แทนเงื่อนไขก่อน merge ใน baseline ด้านล่างเฉพาะการตรวจรับโหลด/ระยะยาวและผลรวมที่พึ่งรอบนั้น; รายการอยู่ใน [ทะเบียนชุดที่ 9](../../roadmap.md#ทะเบียนงานค้างสำหรับชุดที่-9) ไม่ยกเว้นด่านอื่นหรือผล regression ที่ล้ม และไม่ใช่คำสั่งให้ commit/push/merge ตอนนี้ เงื่อนไข Completed และ production prepared activation เดิมยังมีผล
ต้องผ่านชุดที่ 9 ก่อน F-25 ใช้เงินจริงหรือเปิดให้คนนอก ระหว่างนี้ทดลองภายในด้วย Paper
ก่อนเริ่มทดสอบยาวให้ตกลงเวลากับเจ้าของอีกครั้ง


## R2-D1 approved first-release harness — 2026-10-11

ผลหลังแก้ **D1 Passed / findingsทั้งสองClosed** — [D1 review](profiling/d1-harness-review.md).
numeric READY parityครบ8แถว/4หน้าและmutationnegativecontrolผ่าน พร้อมschema/mode/
HTTP/claim/negative-control trace. [JUnitใหม่](profiling/first-release-fixed-tests.xml)
1passed/0failed/errors/skips21.539s; Ruff/formatและmypy331filesผ่าน.
R2-10/Partialอื่นยังคงค้าง; ปิดเฉพาะD1ตามamendmentที่อนุมัติ.
ผลรันทดสอบ20.09sด้านล่างเป็นประวัติก่อนแก้ เก็บแยกจากหลักฐานใหม่.

เจ้าของอนุมัติamendmentและยืนยันไม่เคยdeployoldF-11. Harnessจริงผ่าน1continuous
lifecycleใน20.09s สำหรับfirstrelease/v1 GAP parity/restart/drain/proof/inventorynegativecontrols;
[รายละเอียด](profiling/mixed-version-report.md), [JUnit](profiling/first-release-tests.xml).
Ruff/formatและmypy331filesผ่าน; D1รีวิวแล้วพบสองข้อข้างต้น ไม่ค้างหาoldartifactตามเกณฑ์ใหม่.
D2..D7/Partialในmappingยังต้องปิดตามเกณฑ์ที่ไม่เลื่อน; ไม่productionactivate/commit.

## Review ด่านก่อน merge — 2026-10-11 (ก่อน D1 amendment)

แก้finding1แล้ว: ตรวจmonotonicหลังserialize/encodeก่อนคืน200 ใช้504เดิม;
regressionขอบก่อน/ตรง/หลัง30sและslotreleaseผ่าน. ชุดroute6ผ่านบนhost,
route+preparedAPI **32passed** บนLinux — [JUnit](profiling/serialization-prepared-regression.xml).
Ruffcheck/formatไฟล์ที่แก้และmypy330filesผ่าน ไม่รันfullsuiteซ้ำโดยไม่มีเหตุใหม่.

finding3มี [mapping รายเกณฑ์](profiling/merge-validation-mapping.md) แล้ว แต่รายการ
Partialที่ไม่เลื่อนยังต้องเติมหลักฐาน ไม่ถือว่าmappingทำให้เกณฑ์เหล่านั้นผ่าน.
finding2ยังBlocked; มี [ข้อเสนอ D1 first-release](d1-amendment-proposal.md)
สถานะProposed ต้องยืนยันdeploymentbaselineและอนุมัติก่อนแทนเกณฑ์เดิม.
ไม่commit/merge/activate และไม่รันทดสอบยาวของชุดที่9ในรอบนี้.

ผล **CHANGES REQUIRED** — [รายงานและขอบเขตรีวิว](profiling/development-final-review.md).
พบ serialization อาจคืน200หลังdeadline (Medium; in-memory control10ms/50ms
คืน200หลัง~63ms), R2-D1ขาดlegacyartifact (High) และต้องรวบรวมmapping
รายเกณฑ์ที่ไม่เลื่อนให้ครบ (Medium). ไม่มีการแก้productioncodeในรอบรีวิวนี้
และยังไม่รับรอง Development Complete/merge แม้backend/frontend/E2Eผ่านแล้ว.

## Browser E2E — 2026-10-11

**10 passed / 0 failed / 0 errors / 0 skipped ใน52.2s** ด้วย Linux Chromium,
Node22.23.3, package lock หลังแก้ dependency security และ Python3.12/backend ปัจจุบัน
[JUnit](profiling/frontend-e2e-tests.xml) · [log](profiling/frontend-e2e.log)

- รัน npm run test:e2e -- --reporter=line,junit ตาม playwright.config.ts เดิม;
  Playwright เริ่ม API/Vite เอง ใช้1worker ไม่เปลี่ยน assertions/retry/timeout
- ครอบคลุม health, auth, TOTP, API-key/mobile, trading account, market history
  และ actual quote producer → PostgreSQL → Redis → API → browser/recovery
  worker ใช้ FakeVenue ตามเทสต์เดิม ไม่ส่งคำสั่งไปตลาดจริง
- สร้างฐาน tiewtrade_e2e_f11 บน isolated test PostgreSQL, bootstrap และ migrateถึงhead;
  Redis test DB15; runner ใช้ localhost TCP forwarding ภายใน container เพื่อรักษา
  e2eEnvironment allowlist เดิม ไม่ bypass database safety check
  [runner ที่ใช้](profiling/e2e-run.py); keys เป็น public test fixtures แยก3purpose
- แก้ .github/workflows/ci.yml เฉพาะ E2E env เพิ่ม TIEWTRADE_SEALING_KEY_INDICATOR_CURSOR
  เพราะ app lifespan อ่าน F-11 key เสมอ; ค่า fixture เป็น I32bytes แยกจาก TOTP/venue
  ไม่มี production secret หรือเปลี่ยน application logic
- หยุด validation containers แล้ว; ตรวจฐาน E2E sessions0, modeLEGACY, slotIDLE
  เก็บฐานทดสอบแยกไว้ ไม่แตะฐานแอป ไม่เปิด Live หรือ production prepared mode
- diffcheck ผ่าน; ไม่รันโหลด/soakชุดที่9 และยังไม่ commit/push

ผลนี้ปิด browser regression ของ flow ที่มีอยู่ ไม่ใช่หลักฐาน prepared indicator UI
(ยังไม่มี F-12) หรือ mixed-version acceptance; D1 legacy artifact และ final review
ของด่านที่ไม่เลื่อนยังต้องปิดก่อนรับรอง Development Complete/merge

## Dependency security remediation — 2026-10-11

เจ้าของสั่งเริ่มคัดกรอง/แก้ dependency findings หลัง frontend validation:
ปรับ frontend/package.json และ package-lock.json เท่านั้น ไม่เปลี่ยน application logic
หรือเกณฑ์เทสต์ ใช้ Linux Node22.23.3 ตาม engines เดิม

| รายการเดิม | ผลคัดกรอง / การแก้ |
|---|---|
| vitest3.2.4 / @vitest/mocker3.2.4 | ใช้ใน test runner; scripts ใช้ vitest run ไม่มี UI/API/browser server หรือ standalone mocker plugin ที่ตั้งค่าไว้ จึงยังไม่มีหลักฐานเปิดเส้นทางโจมตีตาม advisory ใน flow นี้; อัปเดตเป็น4.1.11 เพราะ3.xไม่มีแพตช์ล่าสุด |
| tinypool1.1.1 | dependency ของ Vitest เดิม; ไม่พบการใช้ตรงใน application; รุ่นใหม่ถอด dependency นี้ออกจาก lock/tree จึงไม่ override ข้าม major ของ worker pool |
| source-map-js1.2.1 | ผ่าน build tooling (Tailwind/PostCSS) ไม่พบเส้นทางรับ source map จากผู้ใช้ใน app; อัปเดตเป็น1.2.2 ภายในช่วง dependency เดิม |

อ้างอิงผู้ดูแล: [Vitest mocker](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9),
[Vitest UI](https://github.com/vitest-dev/vitest/security/advisories/GHSA-5xrq-8626-4rwp),
[Tinypool](https://github.com/tinylibs/tinypool/security/advisories/GHSA-85c8-ppgw-ccpr),
[source-map-js patch](https://github.com/7rulnik/source-map-js/releases/tag/v1.2.2),
[Vitest migration](https://vitest.dev/guide/migration/).
ข้อสรุปเรื่อง exposure เป็นการตรวจ config/source ปัจจุบัน ไม่ใช่การพิสูจน์ว่าทุก deployment ปลอดภัย

- npm10.9.9 resolver ล้มด้วย edgesOut ระหว่าง update; ใช้ npm11 สร้าง lock ใน container
  แล้ว **npm ci ด้วย npm10.9.9 ผ่าน** ไม่มี --force/--legacy-peer-deps หรือ security override
- Vitest4.1.11 รองรับ Node22/Vite6เดิม จึงไม่เปลี่ยน Vite หรือ Node requirement;
  เปลี่ยน transitive dependencies ตาม Vitest และ source-map-js โดยคง direct packages อื่นเดิม
- **npm audit: 0 vulnerabilities** ณรอบตรวจนี้ — [audit](profiling/frontend-security-audit.json)
  [installed tree](profiling/frontend-security-tree.json), [install log](profiling/frontend-security-install.log)
- **158 tests / 16 suites ผ่าน**, 7.48s รวม positive/negative API contract gates;
  ไม่แก้ assertions/config เพื่อให้ Vitest รุ่นใหม่ผ่าน — [JUnit](profiling/frontend-security-tests.xml)
- [Lint](profiling/frontend-security-lint.log), [typecheck](profiling/frontend-security-types.log),
  [production build](profiling/frontend-security-build.log) ผ่าน; generated types สร้างใหม่แล้ว cmp ตรง
- นำ package files ที่ทดสอบแล้วกลับ workspace; หยุด container แล้ว ไม่เปลี่ยน dependencies
  ของ application container ที่กำลังรัน ไม่ commit/push และยังไม่รัน browser E2E

ปิด findings ทั้ง4รายการจาก audit รอบก่อนเฉพาะ dependency tree ที่อัปเดตแล้ว;
ยังไม่ใช่ final security review หรือ F-11 Completed และยังค้าง E2E/mixed-version D1/final review

## Frontend และ API contract — 2026-10-11 (ก่อนอัปเดต dependencies)

ใช้ source snapshot ปัจจุบันใน isolated Linux container/Node22.23.3 และ npm ci
ตาม package-lock.json ไม่ใช้ Node24 ของ host และไม่เปลี่ยน frontend source/dependencies

- npm run lint และ npm run typecheck ผ่าน — [lint](profiling/frontend-lint.log), [types](profiling/frontend-types.log)
- Vitest **158 passed / 16 suites**, ไม่มี failed/skipped ใน8.06s;
  รวม contract gate ทั้งกรณีสัญญาถูกต้องและเปลี่ยนชื่อ field แล้วต้อง compile ไม่ผ่าน
  — [JUnit](profiling/frontend-tests.xml), [log](profiling/frontend-tests.log)
- npm run build ผ่านใน2.52s — [build log](profiling/frontend-build.log)
- ส่งออก OpenAPI จาก app ปัจจุบันลงไฟล์แยก แล้ว SHA256 ตรงกับ backend/openapi.json
- สร้าง api-types ใหม่จาก schema เดียวกันในไฟล์ชั่วคราว แล้ว cmp ตรงกับ src/api-types.ts
  แบบ byte-for-byte — [hashes](profiling/frontend-contract-hashes.txt), [generation log](profiling/frontend-generated.log)
- เปรียบเทียบกับ working tree ที่กำลังพัฒนา ไม่ใช่ git HEAD ซึ่งยังไม่มี F-11;
  ไม่เขียนทับ generated files ที่แก้ค้างไว้ และยังไม่ได้ commit
- หยุด container tiewtrade-f11-frontend-validation แล้ว ไม่เปิด dev server หรือ deploy

**ข้อค้นพบเพิ่มเติม:** npm audit รายงาน4packages: @vitest/mocker moderate,
source-map-js high, tinypool critical และ vitest critical — [raw audit](profiling/frontend-audit.json)
ยังไม่ได้ประเมิน exploitability/ผลกระทบหรืออัปเดต dependencies; การผ่าน frontend checks
ไม่ใช่การรับรองว่า dependency security ผ่าน ต้องคัดกรองรายงานนี้ก่อน final review

ไม่ได้รัน browser E2E ในรอบนี้ และไม่อ้างว่าผลนี้แทน E2E/mixed-version หรือชุดที่9;
ยังคงงานก่อน merge ที่เหลือตาม validation โดยเฉพาะ D1 legacy artifact และ final review

## Full backend regression หลังแก้ fixture — 2026-10-11

ผลล่าสุดแทนสถานะ full regression เดิมที่มี Redis admission failure:
**Linux Python3.12 / isolated PostgreSQL16 / Redis7: 2,324 passed, 0 failed,
0 errors, 1 skipped, 2 deselected ใน344.10s**.
[JUnit](profiling/resume-linux-final-tests.xml) · [log](profiling/resume-linux-final-tests.log)
กรณี skipped คือ Compose image resolution เพราะ container ไม่มี Docker CLI;
รันกรณีเดียวกันบน host ผ่าน **1 passed** ใน0.23s — [JUnit](profiling/resume-compose-test.xml)
สอง deselected เป็น venue_contract ที่ออกตลาดจริง ตามค่า CI เดิม ไม่ใช่ด่านที่ซ่อนไว้

- แก้ architecture fixtures good/bad ให้มี indicator_builder ตาม import contract F-11;
  bad fixture มี forbidden service import เพื่อให้พิสูจน์การปฏิเสธจริง
- แก้ fixture clear_market_tables ให้ dispose connection หลังล้างข้อมูลก่อน yield;
  migration downgrade จึงเริ่มโดยไม่มี runtime session ค้างตาม verified-drain เดิม
  ไม่แก้ production guard, permissions, timeout หรือเกณฑ์ทดสอบ
- ชุดแก้เฉพาะจุด61passed/1skip ก่อน full rerun — [JUnit](profiling/resume-regression-fixes.xml)
- Redis admission และ scheduler deadline ทั้ง4กรณีผ่านใน full Linux run ล่าสุด;
  ไม่อ้างว่าสาเหตุของ Redis failure เก่าพิสูจน์แล้ว หรือแก้ production Redis ไปแล้ว
- Ruffcheck/format358files, mypy330files, importcontracts7ข้อ และ diffcheck ผ่าน
- เก็บรอบ Windows ที่ไม่ผ่านแยกไว้ใน resume-full-tests.xml/log:
  2,156passed/15failed/154errors; มี Windows timezone/encoding/toolpath/eventloop failures
  รอบ Linux ก่อนแก้ใน resume-linux-full-tests.xml/log: 2,303passed/21failed/1skip;
  รวม fixture failures และไฟล์ประกอบ repo ที่คัดลอกไม่ครบ ซึ่งเติมก่อนรอบสุดท้าย
- ใช้ container tiewtrade-f11-regression-resume กับ source snapshot ปัจจุบันและ
  uv sync --frozen; หยุดแล้ว ตรวจ DB runtime sessions0, buildslotIDLE, advisory711/1=0
  ไม่แตะฐานแอปหรือ capacity fixtures และไม่รัน capacity/soak ของชุดที่9

ยังไม่รับรอง F-11 พร้อม merge/Development Complete: ต้องปิด mixed-version
ด่านที่ไม่เลื่อน (รวม D1 ที่ขาด legacy artifact), frontend/API contract และ final review
ตาม validation ที่เหลือ ผล backend ผ่านไม่แทน production activation หรือชุดที่9

## กลับมาทำด่านก่อน merge — 2026-10-11 (หลักฐานก่อน full run ล่าสุด)

- ตรวจ Redis admission failure เดิมจาก source-proof-tests.xml: varied requests ได้117แทน160;
  หลักฐานเดิมเก็บเพียง boolean จึงแยก DENIED กับ UNAVAILABLE ไม่ได้ ยังไม่ยืนยันสาเหตุ
- รัน Redis test เดิมแบบสั้น6รอบผ่านทุกครั้งบน Redis แยก port56379;
  ไม่ใช้ผลนี้ปิด failure ของ full regression หรือสรุปว่าแก้ production แล้ว
- ปรับ tests/infra/realtime/test_admission.py ให้ตรวจจำนวน ACCEPTED/DENIED ชัดเจน
  และรายงาน UNAVAILABLE เมื่อผิดคาด โดยคงจำนวนคำขอ/เกณฑ์/timeout เดิม;
  เพิ่มเทสต์ timeout ที่ตรวจ cancellation ของ eval ที่ค้าง ไม่เปลี่ยน production code
- ชุด admission/core arithmetic/indicators/cursor **30 passed, 0 failed/error/skipped**
  ใน4.278s — [JUnit](profiling/resume-short-tests.xml)
- Codec และ independent-oracle parity **92 passed, 0 failed/error/skipped**
  ใน28.789s — [JUnit](profiling/resume-codec-tests.xml)
- Mypy330files, Ruff check/format ของไฟล์ที่แก้ และ importcontracts7ข้อผ่าน
  รอบแรกของ API tests ขาด AUTH DB env และ import-linter ขาด UTF-8 output;
  แก้สภาพแวดล้อมแล้วรันซ้ำผ่าน ไม่มีการแก้ application เพื่อหลบ failure
- ตรวจ Git history/images อีกครั้ง ยังไม่มี preserved legacy F-11 full-scan artifact
  ตามข้อจำกัด D1 ใน mixed-version-report; ขอ path/image digest จากเจ้าของแล้ว
- ยังต้อง full regression และ mixed-version ด่านที่ไม่เลื่อนก่อน merge;
  ไม่รัน capacity/soak ของชุดที่9 และไม่เปลี่ยนสถานะ F-11 เป็น Development Complete

## Capacity acceptance — เริ่มวัดจริง (2026-10-11)

Dedicated PostgreSQL/Redis + actual Linux API/launcher/supervisor/worker,
5pairs×6TF/sourceเต็ม365วัน; ไม่แก้production budgetsหรือเปิดpreparedในapplication DB.
R2-C1 รอบ instrumented ผ่าน30/30: correctGETสุดท้าย365.406s,
attemptสูงสุด49.026s, API lag96.291ms/RSSupper65,761,280bytes.
R2-7 cold1/warm5 ผ่าน200/1,000rows/full-scan digestและงบ; HTTPสูงสุด0.281s,
lag63.374ms/RSSupper10,018,816bytes แต่generationมี525,599slots จึงยังขาด
exact525,600-slot case และสถานะR2-7เป็นPartial. หลักฐานและข้อจำกัดอยู่ใน
[capacity report](profiling/capacity-report.md).
C2 **Failed / API_RESOURCE_LIMIT** ที่3,251.031s: APIlag109.465msเกิน100ms.
Measured326observer rounds/55HTTP roundsครบ30series; HTTP1,650ครั้งเป็น200,
233unique response signaturesผ่านfull-scanทั้งหมด แต่ไม่ครบ60นาทีและผิดresourcegate.
C3/C5ไม่ได้รันต่อ, C4ยังต้องทุกphaseและR2-S1..S5; C6Failed.
API/workerทดสอบหยุด, slotIDLE/globaladvisory0; เก็บtraceและsourcehashesครบ.
Lint/format358files, mypy330files, importcontracts7ข้อผ่าน; ไม่ใช่fullbackend rerun.

## Implementation — mixed-version acceptance harness (2026-10-11)

เพิ่ม HTTP multi-process Docker rehearsal และ reader/cleanup/ambiguouscommit
barriers โดยใช้ actual roles/Redis/immutable images และ30 actualREADY checkpoints.
ขอบเขตและผลรายด่านอยู่ใน [mixed-version report](profiling/mixed-version-report.md).
R2-D1..D7 ยังไม่ผ่านครบ: ไม่มี preserved legacy F-11 full-scan binary สำหรับD1,
และ D7 ยังขึ้นกับ Compose release/capacity/regression gates. ไม่ใช้ currentdecoder
หรือ stub แทน oldbinary และไม่สร้าง production activationbundleจาก sparsefixtures.
แก้ review ทั้งสองข้อแล้ว: legacy cleanup ต้องยืนยันSQLSTATE TT011; ทุกหน้าและหลังrestart
ต้องครบ2แถวและตรงfull-scan พร้อม signed cursor identity/ตำแหน่งถัดไป.
ล่าสุด **53 passed / 0 failed / 0 error / 0 skipped**: HTTP rehearsal1ผ่านใน89.49s
และ barrier/CAS/CLI52ผ่านใน13.27s. Ruff lint/format353files, mypy325files,
importcontracts7ข้อผ่าน. รายละเอียดผลรันและข้อจำกัดของแต่ละ gate บันทึกใน report;
รอ review ซ้ำ harness. ไม่อ้างว่า53กรณีทำให้D1..D7ครบหรือfull-backend/capacityผ่าน.

## Implementation — rollout/rollback orchestration (2026-10-11)

Review **APPROVED** เมื่อ2026-10-11; reviewerรันซ้ำ45กรณีผ่าน
(rolloutmodule44 + actualDockerCLI1). Implement ตาม S0..S5 / ADR-002:
- Migration0023เพิ่มmigrator-only typed compare-and-set transition กับ replay identity;
  allowedgraph LEGACY→PREPARING→PREPARED→PAUSED, PREPARING→PAUSED และ
  PAUSED→PREPARING. Runtime/PUBLICไม่มีEXECUTE; lock order guard→control→slotเดิม.
- Activateต้องslot/advisory lockว่าง, ไม่มีRUNNING job, strict proof/grace/protocolผ่าน
  และfresh valid headsครบ30 พร้อมretained checkpoints. ไม่แก้READY/expiry/build epoch,
  ไม่resetjob attempts/fairness/episodeและไม่clearorphanเพื่อให้ผ่าน.
- Pauseเพิ่มepochและบันทึกDB cutoffเมื่อออกจากPREPARED; replayไม่เลื่อนcutoff,
  reprepareแล้วpauseก่อนออกv2รอบใหม่รักษาcutoffเดิม. Pauseยังทำได้เมื่อproof/configเสีย.
- CLI rollout-status / rollout / rollout-retire-check ใช้migrator credentialเท่านั้น.
  VerifiedComposeinventoryครอบstopped/offline containersของapi/market-data/builder,
  exact image ID/project/service/restart no/PID0/timestamps, ตรวจซ้ำหลังcapabilityprobe;
  DBruntime connectionsรวมidle poolต้องปิด. Legacyimageและinventoryที่ละreplicaถูกบล็อก.
- Capabilityprobeใช้immutable local image, no network/credentials/read-only,
  CPU/memory/PID limits และcleanupเฉพาะauxiliary probeหลังtimeout/cancel.
  Operatorรับผิดชอบexternal routing/direct access/cron/offline restart inventory และ
  actualverificationkeyringdistributionตาม[runbook](rollout-runbook.md);
  ไม่อ้างDocker/DBตรวจexternaldeploymentแทนoperatorได้.
- Initialprepareใช้source activation0015ในtransactionเดียวกับCAS;
  ถ้าCASถูกบล็อกsourceproof/reset/trigger installationrollbackพร้อมกัน.
  Timeout/cancelปล่อยtransaction และคำสั่งถัดไปผ่านได้; ไม่มีautomaticretry/ambiguouscommitretry.
- Activationต้องowner-reviewed gate bundleที่ผูกimage set/keyring config กับ
  R2-L/F/G,C1..C6,D1..D7,REGRESSION,READY-API reports (JUnit/hash/zero failures/skips).
  Gate mappingเป็นexplicitoperatorattestation; synthetictestsไม่ใช่capacityevidence.
- Retirementcheckไม่ทำDDL; บล็อกจนmodeLEGACY/PAUSED, cutoff+6hและreader/slot drainผ่าน.
  Schema removalใช้existingAlembic/maintenance protocolหลังcheckภายใต้closedrouting/restart.
  คงcontrol/views/decoder/keyring/graceระหว่างsupportwindow ไม่เปิดlegacyfallback.

หลักฐาน regression และactualDocker/CLIบันทึกใน
[rollout regression JUnit](profiling/rollout-regression-tests.xml) และ
[orchestration/actual container CLI JUnit](profiling/rollout-orchestration-tests.xml).
Regression isolatedLinuxPython3.12/PG16/Redis7 **681 passed / 0 failed / 0 error /
0 skipped** ใน186.03s. หลังเพิ่มschema-retirementguardตรวจล่าสุดบนhost/isolatedPG
**45 passed** ใน10.20s รวมactualDocker image/inventory/CLI gate1กรณี;
ตรวจguardปฏิเสธmode/cutoff/liveAPIpoolก่อนDDLและfunctionยังอยู่หลังrollback.
Migration down/up ล่าสุดหลังปรับexisting3testsให้disposeAPIpoolก่อนretirementตาม
สัญญา: **7 passed** ใน14.63s บนLinux —
[migration JUnit](profiling/rollout-migration-tests.xml).
Ruff lint/format351files, mypy323files, import contracts7ข้อ และgit diff checkผ่าน.
รายงาน681เกิดก่อนเพิ่มdowngradeguard;45+7เป็นหลักฐานล่าสุดของส่วนที่เพิ่มนั้น
ไม่อ้างว่ารันfullbackend/finalcapacityแล้ว.
Positive30-head transitionfixtureเป็นsyntheticmetadataเพื่อทดสอบpredicateเท่านั้น;
ไม่ใช่full365parity/capacityหรือproduction activationbundle.
R2-D1..D7 fullrelease/mixed-version acceptance, C1..C6 capacity, continuousGCpressure
และfullbackend/finalgatesยังต้องทำก่อนactivate/merge/Completed.
Schema0023ใช้เฉพาะisolatedtestDB; buildเฉพาะtestimage, ไม่เปลี่ยนappdeployment/mode.

## Implementation — prepared API routing (2026-10-11)

Implementตามapproved prepared read/cursor/error contracts; reviewผ่าน APPROVED เมื่อ2026-10-11:
- LEGACYยังใช้full-scan/v1เดิม; PREPAREDใช้READY/checkpoint/source proofในAPI-role
  REPEATABLE READ READ ONLY snapshotเดียว ไม่build/enqueue/fetchvenueด้วยGET.
- First requestตรวจsanitizednumeric failureก่อนใช้head; numericพิสูจน์ได้คืน422,
  desiredkeyเปลี่ยน/proofขาด/manifestGCคืน503 Retry-After10 ไม่fallbackoldhead;
  manifestของcandidateอื่นไม่เปลี่ยนvalidcontinuationเป็นnumeric422.
- Headต้องage<=600s/proof/expiryผ่าน; defaultend=U, explicitend>U503ไม่clamp;
  restorecheckpoint<=page_startและprefix<1,000 ใช้reader/coreเดิมไม่เกิน1,999slots,
  fetchbuffer<=1,000/CPU slices16/query500ms/lock200ms/deadline30sเดิม.
- Responseเพิ่มgeneration_id/prepared_at/generation_age_seconds;
  continuationอ้างgenerationเดิม ไม่เลือกheadใหม่ ไม่ใช้600s freshnessเปลี่ยนชุด;
  source mutation/epoch/floor/GC/rollout mismatch/token expiry409,
  malformedcheckpoint503 ไม่แปลงเป็นnumeric422.
- Cursorv2เพิ่มgeneration/codec/rollout identity ใช้canonicalclaims/session binding
  และHMACdomainv2; selectorเลือกexact schema/domainก่อนverify ไม่fallbackdomain;
  v1canonicalbytes/domainเดิมคงเดิม validv1ในnonLEGACY409, invalidschema/MAC422.
- ตรวจDB time/session/token/generationexpiryก่อนcommit ไม่มีsession renewal;
  responsebodyส่งหลังtransactionจบ ไม่มีpartial rowsหรือautomatic retry.
- Migration0022ขยายviewsเดิมด้วยimmutable candidate sequence และsanitized
  manifest_available เพื่อแยกunprovable numeric episodeหลังGC;
  ไม่มีAPIอ่านSTAGING/FAILED base tablesหรือDML/transition privilegesใหม่.
- OpenAPI/frontendgeneratedtypesอัปเดตและfrontendtypecheckผ่าน.

เกณฑ์validationของส่วนนี้: actual auth/Redis/API-role/worker flows,
checkpoint-page parityกับfull-scan/digest, prefix budgets, concurrent source writeหลัง
snapshot, numeric mask/postGC/desiredbounds, v1/v2 lifecycle/domain/canonical,
first/continuation freshness/expiry/epoch/floor/codec/missingcheckpoint,
no GET demand/build และ migration downgrade/upgrade/actualrole regressions.
Prepared activation/rollout/capacity/continuous GC recovery/full final gatesยังไม่รวม.

ผล isolatedPG16/isolatedRedis7/LinuxPython3.12: **639 passed / 0 failed / 0 error /
0 skipped** ใน179.72s — [JUnit](profiling/prepared-api-tests.xml).
รวม regression610กรณี, actual prepared API25กรณี, legacyAPI2กรณี และcursor2กรณี;
numeric manifestGC marker/view ordering, snapshot race, freshnessกับcontinuation,
no demand/build, response/session expiry, v1/v2 lifecycle, canonical v1 bytesและdomain isolation.
TF-boundary gateเพิ่มเติม **1 passed** ใน1.10s บนhostPython3.12/isolatedPG/Redis —
[JUnit](profiling/prepared-api-boundary-tests.xml):
headas_ofก่อนboundary1µs, DBtimeตรงboundary, default200และexplicitend>U503;
fixtureปรับidentitytime/session lifetimeสำหรับclock probeเท่านั้น ไม่ใช่capacity session extension.
Ruff lint/format346files, mypy319files, import contracts7ข้อ,
OpenAPI/frontend types generationและfrontendtypecheck/git diff checkผ่าน.
Schema0022ใช้เฉพาะtest DB; ไม่เปิดpreparedmodeกับแอป/ไม่deploy/commit/push.

## Implementation — manual retry CLI และ GC (2026-10-11)

แก้ review High เรื่อง allocated pages ทำให้ eviction ไม่หยุด:
- Migration0021 แทนเฉพาะ pressure predicate ของ GC; migration0020 คง definition
  เดิมสำหรับ downgrade และ existing0020 DBอัปเกรดได้ ไม่แก้ claim/retry/source protocol.
- Pressure ใช้ bytes ของ live tuples พร้อม conservative heap/index/TOAST reserves:
  checkpoint payload storage size+512 bytes และ128/TOAST chunk1996 bytes,
  generation tuple+1024, head tuple+512 และ retry tuple+256;
  รวม retained request identitiesด้วย ไม่ใช้ n_live_tup/n_dead_tup estimates.
  Threshold3GiBและ batch1,000/10,000/query500ms/lock200ms/transaction2sคงเดิม.
  Recompute pressureทุกbatch; DELETEลด live charge และ batchถัดไปหยุด early eviction
  แม้allocated filesยังอยู่ ไม่มีVACUUM/full-scan-source/connectionเพิ่มในruntime.
- Allocated relation sizes ยังต้องวัดใน disk/vacuum/capacity acceptance;
  live chargesไม่ใช่คำรับรองว่าDELETEคืนdiskทันที หรือว่าfullcapacityผ่านแล้ว.

Regression gateสำหรับข้อแก้: explicit
`tests/services/indicator_builder/profile_storage_pressure.py` บนisolatedPG:
สร้าง225,000 padding checkpointsใน450 READY manifests ให้จริงเกิน3GiB
(padding fixtureใช้สำหรับstorageเท่านั้น ไม่decodeเป็นoracle checkpoint),
เรียก actual GCด้วย budgetsจริงและยืนยันลบcheckpoint1,000;
reclaim fixture rowsโดยยังเก็บallocated pages แล้วให้coalesce/workerจริงสร้างREADYใหม่,
เรียกGC3รอบต้องไม่expire/remove READYหรือเปลี่ยนjobและhead ต้องยังอยู่.
Fixtureคืนcolumnstorage/autovacuum settingsและล้างmetadataเมื่อจบ.

ผลหลังแก้: regression **610 passed / 0 failed / 0 error / 0 skipped** ใน151.59s
บนisolatedPG16/LinuxPython3.12 รวม migration down/up —
[JUnit](profiling/gc-pressure-regression-tests.xml).
Full-size pressure gateรันแยกแบบexplicitบนhostPython3.12/isolatedPG16:
**1 passed** ใน55.13s — [JUnit](profiling/storage-pressure-fix-tests.xml);
propertiesบันทึกallocated bytesก่อน/หลัง recoveryเท่ากันที่3,786,072,064bytes
(ยังเกิน3GiB), READYใหม่อยู่รอดหลังGC3batch.
Ruff lint/format343files, mypy317files, import contracts7ข้อ และgit diff checkผ่าน.
แก้Highแล้วรอreviewซ้ำ; ไม่อ้างfull-backend/API continuation/capacity gatesผ่าน,
ไม่มีapplication DB migration/activation/commit/push.

Reviewซ้ำผ่าน APPROVED เมื่อ2026-10-11 หลังpressurefix0021;
rerun maintenance15กรณีผ่านและตรวจ610+fullstoragegate1หลักฐานแล้ว.
Implement ตาม approved error/retry/retention contracts ใน performance-plan-v2
และ ADR-002:
- Migration0020 เพิ่ม `retry_indicator_build_job(uuid,uuid)` กับ
  `gc_indicator_data()` เป็น fixed-search-path SECURITY DEFINER,
  revoke PUBLIC และ grant เฉพาะ builder; runtime ไม่มี direct DML reset.
- CLI `indicator-builder retry --job-id <uuid> --request-id <uuid>`
  ใช้ builder credential; request/result และ terminal→QUEUED commit atomic.
  รับเฉพาะ FAILED_TRANSIENT/FAILED_SUPERSEDED/FAILED_OPERATIONAL หลัง600s;
  duplicate request คืนผลเดิมทั้ง QUEUED/REJECTED ไม่สร้าง cycle ใหม่;
  ไม่ล้าง numeric identity, fair marker, unavailable episode หรือ global owner.
- CLI `indicator-builder gc` เรียก collection หนึ่ง batch;
  scheduler เรียก batch ก่อน coalesce/dispatch โดยไม่มี connection ที่สามใน attempt.
  query500ms/lock200ms/transaction2s ไม่มี automatic retry ambiguous commit.
- Journal เป้าหมาย6h15m/cap2,000,000 entries; prune≤10,000ต่อtransaction,
  expire dependent generations และ advance floor atomic แม้หนึ่ง revision มีหลาย events.
  `created_at` เป็น retention metadata เท่านั้น, epoch/revision ยังเป็น source proof เดิม.
- Derived GC ลบ checkpoint≤1,000 และ generation≤1,000ต่อbatch;
  expire ก่อนลบ/head removal, เก็บ candidate ของ RUNNING job สำหรับ cleanup/reap;
  numeric manifest GC ไม่ล้าง failed calculation key/input version ใน job.
  Numeric checkpoints ถูก discard โดยเก็บ manifest ที่ยังไม่หมดอายุ.
  Pressureของ0020ใช้allocated sizes; supersededด้วยlive-tuple chargesใน0021
  ตามข้อแก้ด้านบน; early eviction ทำให้ resource miss failclosed ตามแผน.
- Retry records ไม่ถูก GC เพื่อรักษา idempotency ข้าม cycle;
  PostgreSQL allocated size รวม reusable/dead pages จึงต้องตรวจ actual storage/
  vacuum/resource pressure ใน capacity gate; ไม่อ้างว่าการ DELETE ลด disk allocation ทันที.

เกณฑ์ review จาก approved contracts: concurrent duplicate/rejected requests,
cooldown/category/numeric suppression, preserved episode/fairness/fence,
bounded checkpoints/journal floor, expired lease/orphan cleanup, publication race,
actual role restrictions และ CLI fixed output; migration upgrade/downgrade ผ่าน.
Full pressure/capacity, API continuation409 และ rollout gates ยังต้องตรวจในขั้นถัดไป.

ผล isolated PostgreSQL16/LinuxPython3.12: **610 passed / 0 failed / 0 error /
0 skipped** ใน149.76s — [JUnit](profiling/manual-retry-gc-tests.xml).
รวม maintenance15กรณีใหม่และ regression595กรณีเดิม:
duplicate/concurrent CLI retryทั้ง4failure reasons, rejected idหลังcooldown,
numeric manifest GC/suppression, live ownerและexpired-lease candidate preservation,
10,000 journal events/partial revision floor, 1,000 checkpoint batch,
actual publication concurrent GC, API permission denial และ lock timeout/session reuse.
Ruff lint/format341files, mypy316files, import contracts7ข้อและgit diff checkผ่าน.
Migration0020 applyเฉพาะisolated test DB; ไม่applyฐานข้อมูลแอป,
ไม่เปิดprepared mode, ไม่commit/push และยังไม่ผ่าน final/full-backend/capacity gates.

Operator: หลังแก้ fault และยืนยัน handoff สำหรับ orphan ให้รัน retry ด้วย
request UUID ใหม่; QUEUED(exit0)/REJECTED(exit12) เป็น committed fixed result.
คำขอที่เคย REJECTED คงผลเดิมแม้ cooldown ผ่านแล้ว ต้องใช้ request UUID ใหม่.
Ambiguous error(exit13) ให้ตรวจ DB/result ด้วย request identity เดิมก่อนตัดสินใจ,
ไม่ส่ง UUID ใหม่เพื่อข้ามความไม่แน่นอน; retry ไม่แทน verified stop/reap.

## ผล implementation — launcher/supervisor และ verified stop/reap (2026-10-11)

Review ผ่าน APPROVED เมื่อ2026-10-11; rerun launcher/recovery29กรณีและ
actual Docker/operator CLI1กรณีผ่าน โดยไม่ได้แก้ implementation ในรอบreview:
- `indicator-builder run`สร้างowner UUIDต่อbootและsupervise childหนึ่งตัว;
  signal handlersติดตั้งก่อนworker_started (ไม่ใช่data readiness);
  signalหยุดให้drain attemptเดิม, supervisorมีขอบเขตรอ126sแล้วkill/wait2s
  ไม่ต่อ DB deadline120s; cancellation kill/waitและไม่มีauto restart/reap
- Childใช้buildercredential/pool2เดิม ไม่รับmigrator/auth/engine/venue credentials;
  schedulerคืนORPHANEDแล้วworkerหยุด, failure/config/stopผลเป็นfixedrecords/exitcodes
  ไม่มี exception/URL/driver textใน output
- `indicator-builder reap`เป็นoperator pathแยก ใช้migrator role/helperเดิม;
  ตรวจ64-hex immutable containerID, exited/PID0/restart=no, timestamps,
  boot ownerหลังStartedAtตรงexpectedUUID และinspectซ้ำก่อนDB transaction
  ไม่รองรับการอ้างPID/alias/lease/advisorylockว่างแทนstop evidence
- Docker probesจำกัด2s/64KiBและkill/waitเมื่อtimeout/cancel;
  DB transactionจำกัด2s/query500ms/lock200ms ไม่มีretry ambiguous commit
  helperคืนREAPED/STALE/LOCK_BUSY, fencing/cycle/budget/episode/roundใช้ของเดิม
- Compose profile `prepared-indicators`เป็นopt-in, restart=no, stop_grace_period130s;
  ตรวจ compose config แล้วdefaultไม่มีbuilder ไม่มีการstartบริการแอปหรือflipcontrol

ผล regression: **595 passed / 0 failed / 0 error / 0 skipped** ใน136.19s
บน isolated PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/launcher-supervisor-tests.xml)
รวม launcher/recovery29กรณีใหม่และ regression566กรณีเดิม รวม migration down/up;
Ruff lint/format338files, mypy314files และ import contracts7ข้อผ่าน

Actual Docker/hostPython3.12 gate: **1 passed** ใน2.83s —
[JUnit](profiling/launcher-container-recovery-tests.xml)
รัน `tests/services/indicator_builder/profile_container_recovery.py`แบบexplicit
กับisolatedPG/containerที่สร้างและลบเฉพาะเทสต์:
writer backendถูกตัดแต่source/CPU processยังอยู่→contenderNO_JOB/reapreject;
kill/waitcontainerจริง→wrongownerreject→operatorCLIจริงREAPED→budget/round/episodeเดิม
→freshworkerได้fenceใหม่และpublishREADYจริง

Unit/process testsครอบownerใหม่ทุกboot, signal startup barrier, real-child force/cancel/wait,
drain→READY, redaction/environment separation, 13unverifiedstatesก่อนเปิดDB,
Docker probe timeout/outputlimit/stderr/cancel, actual runtime-role denial,
LOCK_BUSY/STALEและreal-process backendloss→verifiedstop/reap→staletokenreject
ไม่ได้รัน full backendใหม่หรือapply migrationกับฐานข้อมูลแอป
ยังเหลือ review, manual retry/GC, prepared API/rollout/capacity/full-backend gates

### Operator runbook สำหรับขั้น stop/reap ที่ implement แล้ว

ใช้กับcontainer deploymentที่บันทึกimage/process inventoryตามADR-002;
runtime containerได้รับเฉพาะbuildercredential ส่วนreapรันจากoperator context
ที่มีDocker accessและmigratorcredential ไม่ส่งmigratorcredentialเข้าworker

1. บันทึก full containerID และboot ownerจากlog/inventory เทียบowner_instanceในslot
   อ่าน expected owner/slot_epoch/fenceด้วยmigrator ก่อนหยุดเพื่อใช้compareidentity
2. ปิดrestartของcontainerนั้น แล้วหยุดและwaitให้จบ:
   `docker update --restart=no <64-hex-container-id>`
   `docker stop --time 130 <64-hex-container-id>`
   `docker wait <64-hex-container-id>`
   อย่าเริ่มreplacementจากleaseหมด/PIDหาย/lockว่างเมื่อยังไม่ยืนยันownerหยุด
3. รัน `indicator-builder reap --container <64-hex-container-id> --owner <uuid>
   --slot-epoch <uuid> --fence <integer>` ในoperator context;
   CLIตรวจstate/bootownerซ้ำเองก่อนเรียกhelper ไม่มีforce/skip-verification option
4. REAPED (exit0)หมายถึงcompareidentity/terminalcommitสำเร็จ;
   STALE/LOCK_BUSY (exit12), unverified/config/driver/ambiguous error (exit13)
   ต้องตรวจinventory/DBใหม่ ไม่blindretryหรือresetbudget/ownerด้วยrawDML
   interruption (exit12/STOP_UNCONFIRMED)ไม่ใช่หลักฐานว่าreapcommitสำเร็จ
5. หลังverifiedhandoffจึงเริ่มbootใหม่ (ownerใหม่); eligibility/backoff/cap/cooldown
   ยังใช้DBstateเดิม ไม่ถือว่าreapคือmanualretryหรือเปิดpreparedmode

Native-process/PID recoveryไม่ได้ใช้CLIนี้; สำหรับcontainerที่ข้อมูลstop/bootowner
ตรวจไม่ได้ให้failclosedจนoperatorยืนยันinventoryได้ ไม่มีfallbackจากlease/PID

เกณฑ์จากADR-002/R2-G2..G6ที่ใช้กำหนดขอบเขตก่อนimplementation:

หลักฐานต้องครอบ:
- owner UUIDใหม่ทุกboot, supervised childครั้งเดียว, ไม่มี automatic restart/reap;
  childได้รับเฉพาะ builder credential, ใช้pool2เดิม และไม่มี HTTP/venue/Live activation
- SIGTERM/stop drainงานปัจจุบัน; forced stopต้องรอ process waitยืนยันสิ้นสุด;
  cancellation/ORPHANED/config/errorจบด้วยfixedstatus ไม่มี exception/input/URLใน output
- operator CLIใช้ immutable containerID ตรวจ stopped state/PID0/restart=no,
  boot ownerตรง expected UUID และตรวจ stateซ้ำ; alive/unknown/wrong owner/daemonfailure
  ต้องไม่เรียก DB reap ไม่ใช้ PID/leaseexpiry/advisorylockว่างเป็นหลักฐาน stop
- reapใช้actual migrator roleและhelperเดิม owner/epoch/fence, query/lock/cleanup budgets;
  REAPED/STALE/LOCK_BUSYเป็นfixedresult ไม่retry ambiguous commitหรือresetattempt/episode/round
- actual subprocess/PG testsต้องยืนยัน contenderไม่buildก่อน ownerหยุดและreap,
  หลัง verified stop+reapได้fenceใหม่; old tokenใช้ไม่ได้และbudget/served markerคงเดิม
- Composeให้เป็นopt-in profileและrestart=no; implementationไม่applyแอปDBหรือเปิดpreparedmode

## ผล implementation — scheduler/coalesce (2026-10-11)

แก้ review เรื่องหลักฐาน numeric recoveryแล้ว และ reviewซ้ำผ่านก่อนเริ่มlauncher:
- เพิ่ม `test_numeric_windows.py`9กรณี: เวลา DB ก่อน/ตรง/หลัง alignment boundary
  ทุก6TF, Lเลื่อนจนแถวที่เสียหลุดจาก window, Lเลื่อนแต่แถวเสียยังอยู่ และ appendนอกU
  เดิมที่ไม่ปลุกชุดเดิมจนเวลา DB ขยายU
- Fault injectionใช้ oversized high ใน isolatedDB โดยขยายชนิดคอลัมน์เฉพาะเทสต์;
  production money domain ปฏิเสธข้อมูลนี้ตั้งแต่เขียน แต่เทสต์ให้ reader ปกติอ่านถึง
  `Money` ของ core แล้วเกิด `OutOfRangeError` จริง ไม่mock error/core/publisher
  และไม่แก้ failed key/inputversion/status เพื่อให้ recovery ผ่าน
- ใช้ test-only DB clockใน function bodies เดิมกับ source snapshot; ทุกcaseคืน
  function definitions/column domain และลบ clock objects ผ่าน fixture cleanup
  ไม่มี clock override/fault injection ใน runtime code หรือฐานข้อมูลแอป
- หลังแถวที่เสียหลุด L ใช้ coalesce→claim→scan→publication จริงจน READY;
  เปรียบเทียบทุก point กับ independent rounded-Fraction oracle/full-scan,
  ตรวจ DB digest และ restoreทุก checkpoint พร้อม suffix/state parity
  sourceแถวเดิมยังอยู่ ไม่มีการแก้ราคาที่เสียหรือ restore stateของFAILED
- Tests boundary/new inputยืนยันชุดเดิมไม่computeซ้ำ, ชุดใหม่ที่ยังมีแถวเสีย
  ได้ numeric failureใหม่และ suppressionใหม่, episode deadlineคงเดิม
  ส่วน API GET422/503/200 ปิดแล้วตาม numeric-window-report.md เมื่อ2026-10-11;
  capacity/concurrency gatesที่เกี่ยวข้องยังติดตามแยก ไม่ใช้ผลสั้นนี้แทน

ผลหลังแก้ review: **566 passed / 0 failed / 0 error / 0 skipped** ใน129.64s
บน isolated PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/scheduler-numeric-review-fix-tests.xml)
รวม numeric window9กรณีใหม่และ regression557กรณีเดิม รวม migration down/up;
Ruff lint/format330files, mypy306files และ import contracts7ข้อผ่าน
ไม่ได้รัน full backend ใหม่หรือ apply migration กับฐานข้อมูลแอป

Implementation เดิม:
- Migration0019เพิ่ม restricted `coalesce_indicator_build_jobs()` ใช้ DB time และ
  catalog30seriesเดิม; duplicatepoll/replicasอัปเดต desired ล่าสุดใน job เดียว
  ไม่สร้าง claim/source scan และไม่เปลี่ยน owner/fence/served round
- READY ที่ proof เสียหรือ head ขาดเข้าคิวตาม unavailable episode;
  head ที่ยัง valid เริ่ม refresh เมื่ออายุ470s โดย deadlineคง head.as_of+600s
  QUEUED/RUNNING/FAILED ไม่ reset episode จาก poll/bounds/retry
- Numeric suppression ใช้ helper เดิม เก็บ failed key/inputversion แม้ manifest GC;
  ชุดใหม่จาก bounds/relevant input เท่านั้นที่เริ่ม cycle ใหม่ได้
  FAILED_TRANSIENT/FAILED_SUPERSEDEDต้องมี event หลัง terminal boundary และ cooldown600s;
  FAILED_OPERATIONALไม่ถูก poll ปลุกเอง
- เก็บ failure source epoch/fence ขณะ terminal transition; release/reapใช้ guard
  ก่อน slot/job ตามลำดับเดียวกับ publication เพื่อแยก event ก่อน/หลัง failure
  เก็บ recovery event ระหว่าง cooldownให้ไม่หายเมื่อ journalถูกGC
  terminal records ก่อน migration ที่ไม่มี boundary ไม่ถูกเดาว่ามี event ใหม่
- รวม SQL aligned365-day bounds ของ seed/staging/coalesceไว้ helperเดียว
  migration downgradeคืน function definitionsเดิมและต้อง drainก่อน
- Schedulerใช้ worker attemptเดิมและ dispatchต่อเมื่อยังมีงาน; idle/contentionรอ10s
  ระหว่าง scan poll10sใช้ pinned writerเดิมที่ serializeกับ heartbeat/checkpoint
  ไม่มี connectionที่สาม; stop signal drain attempt, task cancellationส่งต่อหลัง cleanup
  ORPHANEDหยุด loopเพื่อให้ launcher/operatorจัดการ verified stop/reap

ผลก่อนแก้ review: **557 passed / 0 failed / 0 error / 0 skipped** ใน125.01s
บน isolated PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/scheduler-coalesce-tests.xml)
รวม scheduler33กรณีและ regression524กรณีเดิม, migration down/up,
roles/sourceproof/claims/staging/publication/codec/parity/Money/F-09;
Ruff lint/format329files, mypy305files และ import contracts7ข้อผ่าน
ไม่ได้รัน full backend ใหม่หรือ apply migration กับฐานข้อมูลแอป

Tests ใหม่ครอบ control gate, duplicate replicas, bounds, RUNNING identity,
backoff/fair-round preservation, refresh/deadline-miss, dirty proof,
numeric suppression/GC/new input, terminal cooldown/evidence/GC,
trigger damage/guard timeout/API permission, pool2/pinned poll,
orphan stop, drain/cancel และ dispatchสองseriesในroundเดียว
ยังเหลือ review, launcher/supervisor/manual retry/GC, prepared API routing,
rollout, multi-process/capacity และ full-backend gates ก่อนปิด F-11

## ผล implementation — worker หนึ่ง attempt (2026-10-11)

แก้ review ทั้ง2ข้อแล้ว และ review ซ้ำผ่านก่อนเริ่ม scheduler/coalesce:
- Source cleanup รักษา cancellation ทั้งจาก scan body และระหว่าง commit/rollback/close;
  หลัง bounded abort/terminate/join/invalidate ส่ง CancelledError ถึง caller
  watchdog deadline จึงเป็น OWNERSHIP_LOST และ external cancel ไม่กลายเป็น TRANSIENT
  tests เดิมที่ stalled rollback หลัง body cancellation ตรวจ CancelledError ตามสัญญานี้
- Timeout scope ครอบ claim query/commit/result ก่อน scan/publication;
  เมื่อ descriptor ยังไม่ยืนยัน ไม่สร้าง identity เพื่อ release/retry และไม่เปิด source
  คืน ORPHANED สำหรับ timeout หรือ propagate cancellation; committed owner ที่ไม่ยืนยัน
  คง durable slot/fence/budget ให้ verified stop/reap ไม่ถูก contender overwrite
- เพิ่ม10 regression cases ด้วย actual-role DB และ barriers:
  cancel/deadline ระหว่าง source commit/rollback/close6กรณี ตรวจ physical connection ปิด,
  caller outcome, reason, retry budget และ pool reuse;
  cancel/deadline ก่อน/หลัง claim commit4กรณี ตรวจ bounded completion,
  ไม่มี scan/attempt เพิ่ม และ committed orphan ยังบล็อก contender

ผลหลังแก้: **524 passed / 0 failed / 0 error / 0 skipped** ใน122.47s
บน isolated PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/worker-attempt-review-fixes-tests.xml)
รวม worker31กรณีและ regression493กรณีเดิม รวม migration down/up;
Ruff lint/format, mypy302files และ import contracts7ข้อผ่าน
ไม่ได้รัน full backend ใหม่หรือ apply กับฐานข้อมูลแอป

เพิ่ม `services/indicator_builder/attempt.py` สำหรับ review ตามแผนรอบ2:
- ใช้ pinned claim→bounded scan→READY/numeric publication→terminal cleanup เดิม;
  ไม่มี retry/reconnect/reap ภายใน attempt และไม่ reset shared budget/episode
- จำกัด scan/publication ด้วย120s รวมจากก่อน claim query; cancel รอ source/heartbeat
  ปิดก่อน compare-identity release และ propagate cancellation ให้ caller หยุดงาน
- แยก typed numeric, source/ownership loss, transient infrastructure และ operational;
  SQLSTATE40001/40P01 มี typed retryable error ไม่ตีความ exception message
  local scan deadline ส่ง ownership error โดยตรง ไม่ถูกแปลงเป็น connection failure
- คืน fixed result/category กับ job/generation UUID; ไม่ส่ง exception/input/driver text
  ถ้า terminal commit/cleanup ไม่แน่นอนคืน ORPHANED ให้ caller หยุด worker
  ไม่ข้าม durable slot และไม่ claim/rebuild ต่อจาก state เดิม
- Factory ใช้ builder role/pool2/nooverflow/250ms pool timeout;
  import contract ครอบ service ใหม่และห้ามพึ่ง API/engine/market-data
- Tests21กรณีครอบ actual-role READY/nojob/contention, numeric suppression,
  fault categories, cancellation/deadline, retry cap3, safe release failure,
  source maintenance หลัง scan และ uncertain publication acknowledgement

ผลก่อนแก้ review: **514 passed / 0 failed / 0 error / 0 skipped** ใน116.02s บน isolated
PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/worker-attempt-tests.xml)
รวม worker21กรณีและ regression493กรณีเดิม รวม migration down/up;
Ruff lint/format, mypy302files และ import contracts7ข้อผ่าน
Review worker attemptซ้ำผ่านแล้ว: รัน145กรณีผ่านและตรวจหลักฐาน524กรณี;
ไม่ได้รัน full backend ใหม่หรือ apply กับฐานข้อมูลแอป

ส่วนนี้ยังไม่รวม scheduler/coalesce/poll/process launcher, manual recovery/GC,
prepared API routing, rollout, multi-process/capacity และ full-backend gates

## ผล implementation — atomic publication (2026-10-11)

แก้ review ทั้ง2ข้อแล้ว และ review ซ้ำผ่านก่อนเริ่ม worker attempt:
- Ownership identity ตรวจ slot/job/generation/token/sequence/rollout เดิม โดยแยก
  STAGING eligibility ไว้ใน live-claim check; generation ที่ maintenance เปลี่ยนเป็น
  EXPIRED จึงไม่ผ่าน heartbeat/staging writes แต่เจ้าของเดิม terminal release ได้
  Publication จบเป็น SUPERSEDED/reason SOURCE_CHANGED โดยไม่สร้าง READY/failure
  ใช้ shared retry budget/backoff เดิม ไม่ล้าง cycle/fair round/episode deadlines
- Typed numeric error ปิด source แล้วส่ง stop signal และ bounded join heartbeat
  ที่เริ่มแล้วก่อนคืน error ให้ caller เผยแพร่ manifest; heartbeat failure จริง
  ยังแทน numeric outcome และห้าม publish ไม่ใช้ cleanup cancellation สร้าง ownership loss
- เพิ่ม5 regression cases: maintenanceจริงก่อน READY/numeric/release,
  ปฏิเสธ heartbeat/stale token หลัง expiry และ reacquire advisory lock หลัง terminal commit;
  core MoneyError ระหว่าง heartbeat พร้อมตรวจ FAILED_NUMERIC/NULL digest/hidden payload/no retry
  กับกรณี heartbeat ล้มจริงที่ต้องไม่เผย manifest

ผลหลังแก้: **493 passed / 0 failed / 0 error / 0 skipped** ใน115.82s
บน isolated PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/publication-review-fixes-tests.xml)
รวม publication46กรณีและ regression447กรณีเดิม รวม migration down/up;
Ruff lint/format, mypy299files และ import contracts7ข้อผ่าน
ไม่ได้รัน full backend ใหม่ และไม่ได้ apply กับฐานข้อมูลแอป

เพิ่ม migration0018 และ typed publication บน pinned writer เดิม สำหรับ review:
- READY และ numeric failure ใช้ source guard→rollout control→slot→job/generation;
  ตรวจ actual advisory lock/identity/lease/deadline, rollout และ journal proof
  โดยไม่อ่าน candles ขณะถือ guard
- READY ตรวจ digest และ checkpoint boundaries/count ครบก่อนเปลี่ยน generation/head
  พร้อมจบ job/คืน slot ใน transaction เดียว; reset attempt cycle เฉพาะ READY สำเร็จ
  ไม่ล้าง fair-round marker หรือหลักฐานเวลาของ unavailable episode
- Numeric failure รับ typed MoneyError ที่ Python boundary ไม่ส่งข้อความ exception เข้า DB;
  เก็บ fixed manifest และ failed calculation key/input version แบบ atomic,
  ไม่เปลี่ยน READY head และไม่ตั้ง retry; incomplete scan คง NULL digest
  payload ที่ล้มเหลวยังมองไม่เห็นผ่าน API และรอ bounded GC ในขั้นถัดไป
- Proof เปลี่ยนหรือ owner หมดอายุคืน SUPERSEDED ผ่าน shared retry budget เดิม;
  identity ที่ไม่ตรงถูกปฏิเสธ และ ambiguous commit ไม่ปลด ownership ฝั่ง Python
- Tests ครอบ atomic visibility/rollback, source writer commit/rollback และ lock timeout,
  proof/trigger damage, stale identity ทั้ง6ส่วน, deadline/lease/rollout,
  incomplete checkpoints, numeric suppression/old head และ function privileges

ผลก่อนแก้ review: **488 passed / 0 failed / 0 error / 0 skipped** ใน112.25s บน isolated
PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/publication-tests.xml)
รวม publication41กรณีและ regression447กรณีเดิม รวม migration down/up;
Ruff lint/format, mypy299files และ import contracts7ข้อผ่าน
ไม่ได้รัน full backend ใหม่ จึงไม่แทนหลักฐาน full-suite/capacity ที่ยังค้าง

ยังไม่รวม worker orchestration/scheduler, bounded GC, API prepared routing,
rollout หรือ capacity; การเรียก publication ต้องทำหลัง source ปิดและงาน/heartbeat join แล้ว
ไม่ apply migration กับฐานข้อมูลแอป ไม่เปลี่ยน prepared mode และไม่ commit/push

## ผล implementation — source scan/STAGING/checkpoint writer (2026-10-11)

แก้ review ทั้ง3ข้อแล้ว และ review ซ้ำผ่านก่อนเริ่ม publication:
- จบ scan ปกติส่ง stop signal แล้ว join heartbeat ที่เริ่มแล้ว โดยไม่ cancel
  transaction ที่ยังทำงาน; ตรวจ heartbeat error/ownership/deadline หลัง join
  ก่อนคืนผลสำเร็จ เทสต์ barrier ครอบทั้ง heartbeat สำเร็จและ failure ช่วงท้าย
- Source session ใช้ cleanup เฉพาะที่จำกัดทั้ง commit/rollback/close ในงบ2s;
  เมื่อเกินงบ terminate asyncpg physical connection, cancel cleanup และจำกัด
  เวลารอ join/invalidation; ส่ง typed failure ไม่รอ shield task ต่ออย่างไม่จำกัด
  Fault injection ครอบ commit, rollback และ cancellation พร้อมตรวจ physical
  connection ปิดจริงและ pool ใช้งานต่อได้ ไม่เปลี่ยน helper ของ session ประเภทอื่น
- ปล่อย rows/raw/decoded-row/slice references หลังจบ batch ก่อน fetch ถัดไป
  Dense fixture ใช้ weak references ตรวจว่า batch เก่าถูกปล่อยจริง และ input
  rows ที่ยังถูกเก็บสูงสุด1,000 แถว รวมช่วงเปลี่ยน batch

ผลหลังแก้: **447 passed / 0 failed / 0 error / 0 skipped** —
[JUnit](profiling/staging-review-fixes-tests.xml); staging22กรณี (เพิ่ม6กรณีจากreview)
และ regression ชุดเดิมด้านล่าง บน isolated PostgreSQL16/LinuxPython3.12
Ruff lint/format, mypy และ import contracts7ข้อผ่าน; ไม่ได้รัน full backend ใหม่
หรือ apply กับฐานข้อมูลแอป และยังไม่ใช่ผล complete worker/publication/capacity ผ่าน

Review ส่วนนี้ผ่านแล้ว; หลักฐาน complete worker/capacity ยังไม่ครบ

- Migration0017 เพิ่ม restricted initialize/append/seal functions; ทุก write ตรวจ
  actual pinned session lock, slot/job/generation identity, rollout/proof policy,
  lease/deadline ก่อนและหลังเปลี่ยน metadata ใช้ลำดับ slot→job/generation
  ไม่รอ source guard จาก writer transaction และไม่มี runtime direct DML grant
- Source ใช้ session RR/READ ONLY เดิมหลัง claim commit; capture DB as_of/source
  epoch/fence/rollout ใน snapshot เดียว แล้ว derive UTC365-day L/U ด้วยกฎเดิม
  initialization derive bounds ซ้ำจาก as_of ใน SQL ไม่ใช้ desired bounds เก่าหรือ
  source fence สมมติ; current_candidate ชี้ STAGING หลัง initialize commit
- Reuse `infra/market_data/indicator_reader.py` fetch/decode/query budgets;
  แยก canonical `IndicatorDigest` ให้ full-scan reference และ builder ใช้ bytes
  ชุดเดียวกันโดยไม่เปลี่ยนสูตร/rounding/การอ่าน API เดิม
- `infra/indicators/scan.py` เก็บ input ไม่เกิน1,000ต่อ fetch/core sliceไม่เกิน16;
  ไม่สะสม output points ใช้ codec เดิมเขียน initial/ทุก1,000/ท้าย partial
  SQL append บังคับ identity/boundary/order/size และไม่ overwrite checkpoint
- Heartbeat20s serialized บน pinned writer; failure ตั้ง ownership-loss flag
  CPU slicesตรวจ flag/local deadline และไม่ resume claim เดิม หลัง error/cancel
  source ปิดและ heartbeat task join ก่อนคืน control ให้ caller terminal release
- เมื่อ scan ครบ ปิด source ก่อน seal digest; status ยังคง STAGING ไม่มี READY/head
  หรือ numeric failure publication อัตโนมัติ และ API READY views ไม่เห็น partial data
- Tests16กรณีใหม่: DB digest/full-scan/independent Fraction oracle และ restoreทุก
  checkpoint (warm-up1/14/199, OPEN/UNCONFIRMED/gap/refresh); ordered append,
  incomplete seal, expiry/stale identityทั้ง6fieldsใน SQL; cancel/backend loss,
  heartbeat failure/no resume, snapshotคงเดิมเมื่อ source write commitภายหลัง
  และ1mเต็ม365วันสร้าง527checkpoints (fixtureว่าง ไม่ใช่ capacity benchmark)

หลักฐาน isolated PostgreSQL16/LinuxPython3.12:
**441 passed / 0 failed / 0 error / 0 skipped** —
[JUnit](profiling/staging-scan-tests.xml); รวม staging16, claims46, codec/parity,
core Money/Quantity, roles/sessions/migrations และ F-09 regression ที่เกี่ยวข้อง
Migration upgrade/rebuild regression, Ruff lint/format, mypy และ import contracts7ข้อผ่าน
ยังไม่ได้รัน full backend ใหม่ และไม่ได้ apply migration/เปิด prepared modeบนฐานข้อมูลแอป
ส่วนที่ยังต้องทำ: atomic READY/numeric publication, scheduler/coalesce/recovery/CLI/GC,
complete worker orchestration/API/rollout/capacity และ full merge gates

## ผล implementation — claims/global build slot (2026-10-11)

แก้ review: reap จับ `query_canceled` แยกจาก `OTHERS` เพื่อคืน session advisory
lock แล้วส่ง error เดิมต่อ ทั้ง statement timeout และ explicit query cancellation
ทดสอบใหม่ทั้งสองกรณี fail กับ function เดิมเพราะ lock ค้าง และผ่านหลังแก้:
metadata/orphan/attempt/served-round ไม่เปลี่ยนเมื่อยกเลิก, contender รับ lock ได้
แต่ยัง claim orphan ไม่ได้ และ physical reaper session เดิม retry สำเร็จ
Claims46กรณีรวม migration regression เป็น **53 passed / 0 failed** บน isolated
PostgreSQL16/LinuxPython3.12 — [JUnit](profiling/reap-cancellation-tests.xml).
ทดสอบ downgrade0016→0015→upgradehead ก่อนรัน; ไม่ได้ apply กับฐานข้อมูลแอป
หรือรัน full backend ใหม่ ผลนี้ยังรอ review การแก้ไข ไม่ใช่การรับรอง worker ทั้งชุด

ส่งส่วน claims/global-slot foundation สำหรับ review; ยังไม่ใช่ผล worker/publish/
capacity ผ่านครบ และ F-11 ยัง In Progress ตาม roadmap

- Migration0016 เพิ่ม fixed SECURITY DEFINER functions สำหรับ seed/claim,
  heartbeat, terminal release และ migrator-only reap; runtime ไม่มี direct DML
  บน slot/jobs/generations และไม่มี PUBLIC/API/market-data EXECUTE ใหม่
- Seed เฉพาะ catalog30series/formulaเดิม ใช้ DB clock และ UTC365-day bounds;
  duplicate seed ไม่ reset status/counter/deadline/suppression
- Pinned physical writer ถือ session advisory key(711,1) ตั้งแต่ก่อน claim;
  หนึ่ง pinned scope dispatch ได้ครั้งเดียว ใช้ serialized short transactions,
  query500ms/lock200ms/cleanup2s และไม่ reconnect claim เดิม
- Claim commit slot fence/job sequence/token/attempt/served-round พร้อมกัน
  และสงวน generation UUID; current_candidate=NULL จนขั้น initialize STAGING
  จาก sourceRO snapshot ที่จะทำต่อ ไม่สร้าง generation ด้วย as_of/fence สมมติ
- Durable dispatch_round และ dispatch_cursor ใน singleton slot บังคับ
  deadline/catalog round-robin; unserved series ได้สิทธิ์ก่อน retry ของ series
  ที่ served แล้ว และ locked unserved jobs ไม่ถูกถือว่า serve สำเร็จ
- Heartbeatตรวจ actual pg_locks/backend/slot/job identity, rollout/protocol/proof/
  retention policy, lease และ deadline; ต่อ lease150s แต่ไม่ต่อ deadline120s
- Terminal cleanup หลัง expiry ยัง compare identity ได้; transient/superseded
  ใช้ shared cap3/backoff30/60 โดยไม่ refund attempt หรือ reset episode/round
  Operational failure หยุด; READY/numeric manifests ยังไม่มี publisher ในส่วนนี้
- Lease expiry และ advisory key ที่ว่างไม่อนุญาต overwrite orphan owner;
  migrator reap ต้องทำหลัง operator ยืนยัน owner process หยุดแล้วตาม ADR-002
  Reap compare owner/epoch/fence, invalidate fence และรักษา budget/deadline/round
- Failed numeric key/input version ถูกตรวจอีกครั้งก่อน claim: token/restart,
  revision จาก seriesอื่น/appendนอกU/epochหรือcoverageสูญหายอย่างเดียวไม่ปลุก
  ชุดเดิม; changed bounds หรือ relevant committed journal event จึงเปิด claim ได้
  Internal manifest encodingใช้ source/base/quote/timeframe/formula_version/start/end
  พร้อม canonical UTC timestamps และ input version `{epoch,fence}`; failure writer
  ในขั้นถัดไปต้องใช้ encoding นี้ ไม่มี manifest จาก HTTP
- Failed/reentrant acquisition หรือ unknown lock count ทิ้ง physical connection;
  active scope ที่ถูกยกเลิก/connectionหายคง durable orphan ไม่ clear owner แทน
  การ stop/join CPU/source ที่ worker ต้องทำในขั้นถัดไป

หลักฐานบน isolated PostgreSQL16/LinuxPython3.12:

- **423 passed / 0 failed / 0 error / 0 skipped** —
  [JUnit](profiling/build-claims-tests.xml); รวม claims44กรณี, source proof,
  codec/parity/Fraction oracle/DB digest, Money/Quantity และ F-09/roles/sessions/migrations
- มี actual two-process contender test ก่อน claim/ระหว่าง attempt/หลัง metadata
  releaseแต่ก่อน unlock, foreign PID/GUC/token, live lease expiry, backend loss,
  cancellation+reap, pool reuse/reentrant count, numeric suppression และ counter overflow
- Downgrade0016→0015→upgradehead/replay และ migration regression ผ่าน;
  Ruff lint/format, mypy และ import contracts7ข้อผ่าน

ส่วนที่ยังต้องทำ: source scan/STAGING initialization/checkpoint writer,
  atomic READY/numeric publication, scheduler coalesce/recovery/CLI/GC/rollout
  และ complete worker CPU/source stop/join lifecycle; R2-G/C/N/S/D ทั้งชุดยังไม่ผ่าน
  หลักฐาน claim lock ไม่ใช่ proof ของ full-build CPU intervals/capacity
  ไม่ได้รัน fullbackend ใหม่ จึงไม่ปิด Redis admission failure เดิมด้านล่าง
  ไม่มีการเปิด prepared mode/deploy/commit/push

## ผลimplementationรอบ2 — migration/roles/source proof (2026-10-10)

ส่งส่วนfoundationสำหรับreviewแล้ว ไม่ใช่ผลvalidationรอบ2ผ่านครบหรือF-11Completed

แก้reviewซ้ำ High — trigger integrity กลับลำดับล็อก (2026-10-10):
- indicator_source_triggers_validอ่านpg_class/pg_namespace/pg_inherits/pg_trigger
  ผ่านrecursivecatalogqueryแทนpg_partition_tree จึงไม่ขอrelationlocksบนcandles
  หลังsourceguard; ตรวจrootว่ามีจริงก่อนยืนยันcoverageและคงtriggerchecksเดิม
- regressionสองconnectionsถือguardแข่งกับmaintenanceจริง ตรวจpg_blocking_pids
  ให้ยืนยันว่าmaintenanceรอguardแล้ว ก่อนเรียกPROOF_SQL; proofต้องผ่านโดยไม่มี
  candle relationlocksในpg_locks จากนั้นปล่อยguardให้maintenanceจบและinvalidateepoch
- negativecontrolเรียกpg_partition_treeในสถานการณ์เดียวกันต้องlocktimeout
  ภายใต้savepoint เพื่อพิสูจน์ว่าtestจับลำดับล็อกเดิมได้ ไม่อาศัยsleepเดาความพร้อม
- Linux/PostgreSQL16 targeted **146ผ่าน/0ล้ม/0error/0skip**;
  downgrade0014→upgradehead, Ruff/check+format, mypy, importcontractsและdiffcheckผ่าน
- หลักฐาน: [JUnit](profiling/source-proof-lock-fix-tests.xml); เป็นtargetedregression
  ไม่ใช่fullbackend/capacityหรือผลR2-L3ทั้งหมดของpublisher/GCที่ยังไม่ได้implement

แก้reviewข้อ1 High — journal trigger coverage (2026-10-10):
- ตรวจcatalogของstatement/rowtriggersบนrootและทุกpartition: enabled, handler,
  events/timing/level, arguments, WHENและcolumnfilter; sourceproofตรวจจริงแม้flagค้างREADY
- DROP/DISABLE/CREATE OR REPLACE TRIGGERนอกmaintenanceถูกปฏิเสธ;
  maintenanceที่ทำให้coverageขาดเปลี่ยนเป็นPENDING การactivateซ่อมtriggersและเปลี่ยนepoch
  จึงไม่ชุบproofเก่า; healthyactivationซ้ำคงepochเดิม
- bootstrap10-event-trigger.sqlเพิ่มCREATE TRIGGER eventhook; ต้องรันbootstrapฉบับนี้
  ก่อนmigration0015/activationบนDBทดสอบหรือdeploymentที่ผ่านdrainตามแผนแล้ว
- Linux/PostgreSQL16 targeted **133ผ่าน/0ล้ม/0error/0skip**, รวมsourceproof23กรณี
  (regressionใหม่14กรณี), F-09storage/ingestion/migrationและroles —
  [JUnit](profiling/source-trigger-fix-tests.xml)
- downgrade0014→upgradeheadและmigrationregressionผ่าน; Ruff/mypy/importcontractsผ่าน
  รอบนี้ไม่ได้รันfullbackendใหม่ ผลfullrunและRedisfailureเดิมด้านล่างยังไม่ถูกปิด
  ผลแก้ข้อ2 Mediumเรื่องsource-guard timeoutอยู่ในบันทึกถัดไป

แก้reviewข้อ2 Medium — bounded source-guard waits (2026-10-10):
- F-09ตั้งtransaction-local lock_timeout200ms/statement_timeout500msก่อนขอ
  relation/sourceguardและคงไว้จนtransactionจบ; rollback/commitไม่ทำให้ค่ารั่วเข้าพูล
- SQLSTATE55P03/57014แปลงเป็นDatabaseTimeoutErrorโดยไม่ส่งข้อความdriverออกมา
- cleanup timeout rollbackแล้วจบรอบ ไม่มีfetchหรือconsumeattempt;
  schedulerใช้รอบปกติเดิม ไม่มีhot retry
- timeoutหลังfetch rollbacksource/journal/progressแล้วบันทึกfailureในtransactionใหม่
  ใช้attempt/backoff/capเดิม; transactionบันทึกfailureก็มีtimeout หากยังติดล็อก
  จบรอบและคงattempt reservation/leaseให้reclaimตามเดิม ไม่refundหรือเลื่อนcursor
- regressionตรวจguard/relation blockers, querytimeoutหลังเขียนcandles+metadata,
  cancellation, คืนlocks, reusephysicalconnectionเดิมและไม่มีscope/settingsรั่ว
  รวมrun_roundจริงทั้งcleanup/postfetch/failure-record contention
- Linux/PostgreSQL16 targeted **145ผ่าน/0ล้ม/0error/0skip**, รวมregressionใหม่7กรณี;
  Ruff/check+format/mypy/importcontractsและgit diff --checkผ่าน
- หลักฐานการรัน: [JUnit](profiling/source-timeout-fix-tests.xml); ไม่ใช่fullbackend
  runใหม่ และไม่ปิดRedisadmissionfailureหรือcapacity/worker/API gatesที่ยังค้าง

- revision0015เป็นexpandstage: สร้างderivedschema/views/sourceguard/journalและ
  rolloutcontrol=LEGACY/sourceproof=PENDING ไม่มีstricttriggerเปิดเองเมื่อupgrade
- bootstrap00-rolesเพิ่มtiewtrade_indicator_builderแบบไม่superuser/ไม่bypassRLS
  อ่านpubliccandles/proofได้ แต่ไม่อ่านusers/sessions/APIkeys/F-09demandและไม่
  directDMLderivedmetadata; writerfunctions/workerยังอยู่ขั้นถัดไป
- activationเฉพาะmigratorผ่านactivate_indicator_source_proof()หลังdrainตามS2
  ตรวจbootstrapddl/sql_drop event hooksก่อนเปิดproof; relation→guard→control
  root/leaf/futurepartitionมีstatementguardและclonedrowjournal ภายใต้maintenance
- F-09run_roundเรียกsourcewrite helperก่อนlock_claimในwrite transaction
  startupseedcommitแยกจากcleanup; write_candlesตรวจscopeโดยไม่acquireย้อนหลัง
  cleanupใช้physical365วัน+6h15m; GET/POST/ingestยังlogical365วัน
- builderมีsourceREADONLY/RRและwriter sessionชนิดแยกจากAPI/market-data
  ตั้งtransaction characteristicsก่อนSELECTแรกและใช้roleassertion/errortranslationเดิม

หลักฐานจากisolatedPostgreSQL16/RedisและLinuxPython3.12:

| ด่าน | ผล |
|---|---|
| Upgrade/downgrade0015/replay | ผ่านบนDBทดสอบ; legacyexpandไม่ติดstricttrigger |
| Sourceproof testsใหม่9ข้อ | ผ่าน: actualroles, spoof/no-scope, rollback/ABA, appendนอกU, watermark, RRsnapshot, writerbarrier, leaf/futurepartition/DDL/TRUNCATE และSQLorderของrun_roundจริง |
| Targetedregression | **121ผ่าน/0ล้ม/0error/0skip** — [JUnit](profiling/source-proof-targeted-tests.xml); รวมsourceproof/F-09storage+ingestion+migrations/roles/Redisadmission |
| Missingbootstrap negativecheck | ปิดsql_drop hookในDBทดสอบแล้วactivationถูกปฏิเสธTT013 และsourceproofยังPENDING; restorehookแล้ว |
| Ruff/check+format/mypy/imports | ผ่าน; mypy288files, importcontracts7ข้อ; git diff --checkผ่าน |
| Fullbackendล่าสุด | **1,899ผ่าน/1ล้ม/0error/1skip** จาก1,901cases — [JUnit](profiling/source-proof-tests.xml); test_actual_redis_atomic_limits_and_bounded_keysยังล้มในfullrun แม้targetedrunผ่าน จึงไม่ถือว่าด่านfullregressionเขียว |

แก้test_realtime_migrationให้upgradeกลับheadหลังตรวจrevision0014 เพื่อไม่ทิ้ง
schemaเก่าให้testsถัดไป หลังแก้ไม่มีmissing-source-helper failuresในfullrun
รอบแรกที่mountrepoไม่ครบมีharnessfailures ไม่ใช้เป็นหลักฐานผ่าน
รอบfullล่าสุดใช้repoครบและisolatedDocker network; Redisadmissionfailureยังเหลือ
ไม่ได้ผ่อนquota/timeoutหรือแก้productadmissionเพื่อให้เทสต์ผ่าน

ส่วนที่ยังต้องทำ/พิสูจน์: fencedclaim/publish/GC/rollouttransition functions,
checkpointcodec/parity, worker/globalbuild/fairround/retries, dualformatAPIและ
rolloutdrain/recovery/capacity R2-C/N/S/G/D ครบทั้งหมด รวมแก้fullregressionก่อนmerge
R2-L/permissions/sourceproofมีหลักฐานพื้นฐานข้างต้น แต่ยังไม่อ้างว่าทุกbarrier/
publisher/GC/maintenancecaseผ่านครบก่อนส่วนworker/APIจะถูกimplement
ยังไม่เปิดpreparedmodeหรือdeployไปDBแอปที่กำลังทำงาน และไม่มีcommit/push

การใช้งานกับDBที่มีอยู่แล้วต้องbootstrap00-roles.sqlและ10-event-trigger.sql
ก่อนalembicupgradeheadตามขั้นS0; ห้ามเรียกactivationบนdeploymentที่ยังไม่ได้
drain/upgradecompatibleAPI/F-09ตามS2 แม้functionจะมีอยู่แล้ว

เกณฑ์เพิ่มเติมสำหรับแผนperformanceอยู่ใน
[performance-plan.md — PV-1..10](performance-plan.md) เป็น **Approved / NC-34 Closed**
เจ้าของอนุมัติเมื่อ 2026-10-10; ต้องผ่านทั้ง PV-1..10 และ V-1..18 เดิม
การอนุมัติแผนและผลprofileไม่ใช่ผล validation ผ่าน

Prepared-generation amendmentsและเกณฑ์R2-1..12 อยู่ใน
[performance-plan-v2.md](performance-plan-v2.md) — **Approved / NC-35 Closed**
รวมการแยกcold miss/buildออกจากcold APIที่มีprepareddata; ยังไม่ได้รันและไม่ใช้
ยกผลV-15ที่ล้มให้กลายเป็นผ่านด้วยการอนุมัติการเปลี่ยนสัญญาเพียงอย่างเดียว
แก้reviewรอบ2ข้อ2: เกณฑ์capacity R2-C1..C6อยู่ในเอกสารเดียวกัน ต้องผ่านรายseries
ครบทั้ง30 และไม่มีทางเลือกนับNOT_READYเป็นผลผ่าน; Approved/ยังไม่ได้รัน
แก้reviewรอบ2ข้อ3: R2-F1..F6ในแผนเดียวกันตรวจnumeric422/noautomaticretry,
failureproof/sanitizedviewและboundedtransient/manualrecovery; Approved/ยังไม่ได้รัน
เกณฑ์numeric NC-33เดิมยังใช้ครบ ไม่ถูกแทนด้วยเกณฑ์coldmiss503
แก้reviewซ้ำข้อ1: เพิ่มR2-N1..N4ในแผนรอบ2สำหรับalignedbounds/seedwindowใหม่,
Lเลื่อนพ้นแท่งที่errorและกลับREADY/200, durablefailedkeysและcoalesceหลายreplicas
พร้อมnoautomaticretryชุดเดิม; Approved/ยังไม่ได้รัน
แก้reviewซ้ำข้อ2: เพิ่มR2-S1..S5ในแผนรอบ2สำหรับAถูกSUPERSEDEDต่อเนื่องแต่B/
อีก29seriesไม่starve, sharedattemptbudget/pause/fairround/crash/recovery และ
deadlineเดิมยังนับunavailable; Approved/ยังไม่ได้รัน ไม่ผ่อนcapacity acceptance
แก้reviewรอบ2ข้อ4: R2-G1..G7ในแผนรอบ2ตรวจglobalbuild=1ข้ามseries/replica,
sessionlock/poollifecycle/lease-loss/fencing/safehandoffและcapacityจริง; ยังไม่ได้รัน
แก้reviewรอบ2ข้อ5: R2-D1..D7ในแผนรอบ2ตรวจmixed-versioncursor/keys/epoch,
oldF-09cleanup, drain/activation/rollbackและจริงprocess inventory; ยังไม่ได้รัน

เกณฑ์นี้เขียนก่อน implementation ตาม `standards/testing.md`
ตัวเลขอ้างอิงและค่าปัดของ NC-33 ได้รับอนุมัติพร้อม requirements แล้ว
งบทรัพยากรและเกณฑ์ benchmark V-15 ได้รับอนุมัติแล้วเมื่อ 2026-10-10
ตามบันทึกใน requirements ส่วน NC-32; ยังไม่ได้รัน benchmark

## “เสร็จ” หมายถึง

| # | เกณฑ์ | ตรวจอย่างไร |
|---|---|---|
| V-1 | รองรับ EMA20/50/200, RSI14, MACD12/26/9, ATR14 บน 5 คู่/6 timeframe เท่านั้น | core/API parameter matrix; invalid input ได้รหัสที่กำหนด |
| V-2 | สูตร seed warm-up หารศูนย์และหน่วยตรง requirements ที่อนุมัติ | ชุดตัวเลขอ้างอิงที่คำนวณแยกจากโค้ด พร้อมที่มา/expected ทุกจุดแรกและจุดต่อไป |
| V-3 | ตัวเลขให้ผลคงที่และไม่ขึ้นกับ ambient decimal context | เปลี่ยน context ของผู้เรียก/ลำดับคำขอแล้วเทียบข้อความผล; ไม่มี float หรือ financial Decimal เปล่า |
| V-4 | กราฟและบอทที่อ่านชุดเดียวกันเห็นค่า/สถานะของแท่งเดียวกันตรงกัน | เทียบช่วง 200 กับ 1,000 จุดและหน้าที่ทับซ้อนกัน รวม warm-up และ gap |
| V-5 | Input มีตัวตน/source/pair/timeframe/UTC/รุ่นสูตร/รุ่นข้อมูล/seed ตรวจซ้ำได้ | roundtrip schema, rerun ด้วย input/รุ่นเดิม; ไม่ใช้แท่งอนาคต |
| V-6 | แท่งก่อนจบช่วงหรือยังเปิดไม่เข้าคำนวณ | controlled timestamps ก่อน/เท่ากับ/หลัง `end_at`; แยก `fetch_started_at` จาก `observed_at`/`last_checked_at` |
| V-7 | REFRESH_REQUIRED ไม่เดิน seed/state และไม่ถูกแอบแปลงเป็น gap | refresh pending/failure/commit tests; downstream ยังไม่มีค่า; ผลก่อนหน้ายังอยู่ |
| V-8 | ผลที่อาศัย UNCONFIRMED ไม่ถูกอ้างว่า confirmed | seed UNCONFIRMED ตามด้วยแท่ง CLOSED; ตรวจสถานะสะสม |
| V-9 | ช่วงข้อมูลขาด/ไม่พอรายงานตรง ไม่เติมศูนย์/แท่งจำลอง | gaps ต้น/กลาง/ท้าย, reset warm-up หลัง gap จริง, retention ที่ไม่ครบ |
| V-10 | การแบ่งหน้าใช้รุ่นข้อมูลเดียว และเปลี่ยนรุ่นแล้วได้ 409 ไม่มีแถวผล | backfill/refresh/retention/formula-version และ race ระหว่างตรวจรุ่นกับอ่าน |
| V-11 | ตัวอ้างอิงอ่านต่อผูกขอบเขต/เวลา/รุ่นและถูกตรวจ | tamper, reuse กับคนละคู่/timeframe/ช่วง, expired, fallback ถูกปฏิเสธ |
| V-12 | จำกัด output และ input รวม warm-up แยกกัน | 1,000/1,001 ผล, EMA200 1,199 input, ทุก timeframe ที่เพดานและเกินเพดาน |
| V-13 | อ่านต้นทางหลายช่วงโดยไม่ reseed หรือปนรุ่น | fake/PG rows มากกว่า 1,000, gap ข้ามช่วง, write ระหว่างสองช่วง |
| V-14 | F-11 ใช้ transaction READ ONLY ภายใต้ API role เดิม ไม่เพิ่ม/ถอนสิทธิ์เดิม และไม่ต่ออายุ session | unauthenticated/revoked/active session, read-only transaction, actual grants/RLS, regression สิทธิ์ F-07/F-08, routing inventory, ไม่อ่าน secret ที่เก็บไว้ |
| V-15 | ชุดสูงสุดสำเร็จภายใน30s, RSSเพิ่ม<=128MiB, event-loop lag<=100ms; งาน1/process, rate6/user/30รวมต่อนาที | benchmark 525,600ช่อง, Redisหลายprocess, deadline/disconnect/cleanup<=2s และ overload tests ตามรายละเอียดด้านล่าง |
| V-16 | OpenAPI/frontend types ตรง API ใหม่และด่าน repo เขียว | regenerate/check generated files, CI gates ด้านล่าง |
| V-17 | refresh ทำครบทางผ่าน F-09 โดย GET indicator ไม่มี side effect และไม่อ้างว่าพร้อมก่อน commit | integration consumer, auth/CSRF, duplicate POST,202/200,poll budget,failure,rollback และการเริ่ม indicator ชุดใหม่ |
| V-18 | Tokenมีอายุสูงสุด6hผูกsession, MACถูกตรวจ และหมุนkeyได้โดยไม่ยืดอายุหรือข้ามauth/revision | codec fixtures, expiry boundaries, tamper/replay, multi-replica rotation, startupconfig และ logredaction ตามด้านล่าง |

## เทสต์ที่ต้องมี

### ตัวเลขอ้างอิงแยกจาก implementation

- เตรียมชุดราคาแบบคงที่ที่คำนวณด้วยมือ/worksheet แยกจากสูตรในโค้ด:
  EMA ทุก period ที่แท่งก่อน seed, แท่ง seed, แท่งถัดไป; MACD line/signal/histogram
  ที่ขอบแท่ง 26/34; RSI/ATR ที่ขอบ 14 ช่วง และหลัง smoothing หลายแท่ง
- กรณี RSI gain/loss ศูนย์ทั้งสอง, มีเพียงฝ่ายเดียว, ราคาเปลี่ยนทิศ,
  ATR gap ด้วย previous close และค่าที่ต้องปัด/หารไม่ลงตัวหลังปิด NC-33
- ค่าละเอียดสุด ขอบช่วงที่ Money/Quantity รับได้ และ overflow ต้องได้ผล/error
  ตาม numeric contract ฉบับอนุมัติ ไม่คัดลอก expected จาก implementation
- บันทึกคำตอบ expected เป็นข้อความและอธิบายการคำนวณต้นทางใน test fixture
  ตาม NC-30/33 ที่อนุมัติแล้ว; expected ข้างล่างอนุมัติแล้วแต่ยังไม่ได้รันเทสต์

ข้อเสนอ expected สำหรับปิด review ข้อ1 (อ้าง NC-33 เป็นสัญญาหลัก):

| การคำนวณ | Expected string |
|---|---|
| 1/3 | `0.333333333333333333` |
| −1/3 | `-0.333333333333333334` |
| ค่าเฉลี่ย 1,2,2 | `1.666666666666666666` |
| EMA20 หลัง previous=100, close=101 | `100.095238095238095238` |
| RSI avg gain=1, loss=2 | `33.333333333333333333` |
| ค่าเฉลี่ย 9×10^19 สองค่า | `90000000000000000000` |
| 10^-18/3 | `0` |
| histogram: 9×10^19 − (−9×10^19) | OutOfRangeError; API 422 INDICATOR_NUMERIC_ERROR ไม่มีแถวผล |

อ้างอิง expected ด้วยเศษส่วน exact และหารจำนวนเต็มลงล่างที่ scale 18
ใน test oracle ที่เขียนแยกจาก production; ไม่ใช้ operation ใหม่คำนวณ expected
ทำ properties ว่าผลอยู่ไม่เกินผล exact และต่างน้อยกว่า 10^-18 ต่อ operation
ทั้งค่าบวก/ลบและหารลงตัว; ไม่อ้าง error bound นี้กับ series สะสมทั้งชุด

- ราคา close คงที่100/high101/low99: EMA=100 หลัง seed, MACD line/signal/
  histogram=0 เมื่อแต่ละค่าพร้อม, RSI=50 ตามข้อเสนอ NC-30, ATR=2 ตั้งแต่แท่ง15
  ตรวจ exact seed boundaries 20/50/200, 26/34 และ15 แยกแต่ละผล
- พิสูจน์ EMA ใช้ weighted mean ปัดครั้งเดียว และ RSI ไม่ปัด RS ก่อน;
  ใช้ชุด fractional prices ที่สองวิธีให้ผลต่างกันอย่างน้อยหนึ่งหน่วย scale
- ตรวจ Scalar ไม่มีหน่วยและไม่ผสม arithmetic กับ Money/Quantity;
  reject bool/nonfinite/น้ำหนักเกินขอบ/หน่วยต่าง/ตัวหารศูนย์หรือค่าลบ
- ตรวจ exact result ก่อน rounding ไม่ให้ overflow ถูกปัดกลับเข้าช่วง;
  numerator ภายในที่เกิน MAX_ABS แต่ค่าเฉลี่ยไม่เกินต้องสำเร็จ
- RSI branch ใช้ rounded state: tiny positive gain/loss ที่ปัดเหลือศูนย์
  ต้องได้ zero branch ที่ระบุ ไม่ใช้ unrounded state ลับหรือ clamp
- เปลี่ยน ambient precision, rounding และ traps แล้วผล/ชนิด error ต้องเหมือนเดิม
  และ context ภายนอกกลับค่าเดิม; รันเทสต์ Money/Quantity เดิมทั้งหมด
- Error กลางหน้าหลังคำนวณบางจุดแล้วต้องได้ error ทั้งหน้า ไม่มีค่าเก่าหรือ
  partial success; retry input/รุ่นเดิมได้ error เดิมโดยไม่ออกเครือข่าย

### คุณสมบัติและความปลอดภัยข้อมูล

- Input/รุ่นเดียวกันได้ output เดียวกัน; สลับ decimal context/thread/การแบ่งช่วง
  ไม่เปลี่ยนผลหรือสถานะ; ไม่มี future candle ทำให้ผลอดีตเปลี่ยน
- output ที่ทับซ้อนกันจากผู้ใช้ผลต่างกันและ page size ต่างกันต้องตรงกัน
  เมื่อใช้รุ่นข้อมูลเดียว; ชุดใหม่หลัง backfill ไม่ถูกปนกับหน้าเก่า
- `fetch_started_at < end_at` แม้ response มาหลังปิดแท่ง ยังใช้ไม่ได้;
  ตรง `end_at` จึงผ่านเกณฑ์เวลาแต่ยัง UNCONFIRMED
- refresh fail/rollback ไม่ให้ค่า; หลัง commit ใหม่ให้คำนวณซ้ำจาก input ที่ผ่าน
  และยังไม่ยกระดับ CLOSED; pending ไม่เป็น gap จริง
- missing slot ทำให้ segment ใหม่และ warm-up ใหม่ตาม requirements;
  `REFRESH_REQUIRED` ไม่ถูกข้ามเพื่อ restart seed; ไม่แสดงศูนย์แทนไม่มีค่า
- revision เปลี่ยนหลังหน้าแรกจาก backfill/refresh/retention ต้องได้
  `409 INDICATOR_DATASET_CHANGED` ไม่มีแถวผล; ผู้ใช้ผลเริ่มใหม่จากหน้าแรก
- จำลอง race ภายในหน้า: mutation หลังตรวจรุ่นก่อนอ่านช่วงถัดไป
  ต้องได้ภาพข้อมูลเดียวหรือ 409; ไม่มีผลที่ปนสองรุ่น
- อ่านต้นทาง 1,199 แท่งเพื่อคืน 1,000 จุด EMA200 ไม่ถูกตัดโดย
  `LIMIT 1000` ของ reader เดิม; ผ่านทุกเพดาน input/output แบบ exact boundary
- query/tokens ผิดรูป, ขยายขอบ/สลับคู่หรือ timeframe, เกิน retention,
  ช่วงเกินเพดาน ถูกปฏิเสธเป็นรหัส ไม่เผยข้อมูลผู้ใช้หรือ stack trace

### ฐานข้อมูลและการต่อครบทาง

เพิ่มเกณฑ์หลังแก้ deep review ข้อ2 สำหรับ V-4/5/10/11/13/14:

- ใช้ PostgreSQL16 กับ API role จริง ตรวจ SQL ลำดับแรกใน transaction เป็น
  SET TRANSACTION REPEATABLE READ, READ ONLY ก่อน role check/เวลา/user setting
  และตรวจ SHOW transaction_isolation/transaction_read_only ว่าตรงแผน
- ใช้สอง connections กับ barrier: reader สร้าง snapshot แล้วอ่านช่วงแรก;
  writer แก้ OHLC/เติม gap/เปลี่ยน finality/refresh/ลบแท่งต้น seed และ commit;
  reader อ่านช่วงที่สองต้องเห็นภาพเดิมทั้งชุดพร้อม digest เดิม ไม่มี mixed page
  เริ่มอ่านหน้าถัดไปหลัง commit ต้องได้409ไม่มีแถวผล
- สลับลำดับให้ writer commit ก่อน reader สร้าง snapshot: first request ได้
  input/digest ใหม่ทั้งชุด และ continuation ของรุ่นเก่าต้องได้409
  writer rollback ไม่มีผลต่อ digest ของ reader ใหม่
- สแกน/hash ทั้ง [L,U) รวมก่อน seed และหลังหน้าที่ขอ; เปลี่ยนเพียงหนึ่ง field
  ใน record ที่กำหนดใน plan ต้องเปลี่ยน digest และ invalidates continuation
  ส่วนเพิ่มแท่งนอก U หรือเปลี่ยนเพียง queue metadata/last_checked_at ต้องไม่เปลี่ยน
  รุ่นค่าคำนวณ และ metadata ประกอบต้องมีเวลาอ่านตามจริง
- canonical bytes fixture ต้องคงที่ข้าม process/context; roundtrip เลข/เวลา
  ไม่เปลี่ยน digest; gap marker ต่างจากแท่งที่มีค่าเป็นศูนย์; page size/ช่วงผล/
  user_id ไม่เปลี่ยน digest ถ้า bounds/input เดิม
- สองคำขอที่ตรึง L/U เดียวกันแต่ขอช่วงผลต่างกันต้องเลือก seed เดียวกัน
  เติมแท่งใน leading gap ภายใน L ก่อน seed เดิมทำให้ revision เปลี่ยน
  และแท่ง REFRESH_REQUIRED ต้น segment ต้องไม่ถูกข้ามไปเลือก seed ใหม่
- ใช้ DB clock ที่ควบคุมได้ทดสอบหน้าแรกทั้งตรงขอบนาทีและกลางนาที:
  continuation หลัง cutoff เลย L ต้องสำเร็จเมื่อ auth/token ยังใช้ได้และ
  records/digest เดิม ทั้งกรณี leading MISSING slots และแถวเก่าที่ยังไม่ถูกลบ
  bounds/as_of/seed/revision ต้องคงเดิม; ทำซ้ำกับทั้งหก timeframe
- จำลองเวลาหลายหน้าข้ามขอบแท่งและขอบ rate window ภายใต้งบ30s/หน้า
  และ6คำขอ/user/นาที โดย session ยัง active, token ไม่หมดอายุ และข้อมูลคงเดิม:
  ต้องอ่านจนครบช่วงผลที่ขอได้โดยไม่มี409จากเวลาเลื่อน ไม่มีแถวซ้ำหรือขาด
  ใช้ fixture ที่ข้อมูลจริงอยู่หลัง cutoff ตลอดการอ่านและมี leading gaps;
  แยกจาก benchmark เต็ม525,600ช่อง ไม่ใช้ frozen clock ซ่อนปัญหาการอ่านต่อ
- cleanup ลบ record ที่เคยอยู่ใน [L,U) รวมก่อน seed/นอกหน้าปัจจุบัน:
  reader snapshot หลัง commit ต้องได้409 ไม่มีผลบางส่วน; snapshot ก่อน commit
  ยังคืนหน้าเดิมได้และคำขอถัดไปตรวจพบการลบ ห้ามเลื่อน L/reseed ใต้ token เดิม
  cleanup ที่ไม่เปลี่ยน record ใดในช่วงต้องไม่ invalidate token
- หน้าแรก/raw start/end ที่หลุด retention ปัจจุบันยังถูกปฏิเสธตามเดิม;
  token ปลอม/หมดอายุ/ต่างsession ใช้ข้ามการตรวจนี้ไม่ได้ และ public GET/POST
  ของ F-09 ยังใช้ retention ปัจจุบัน ไม่ได้รับข้อยกเว้น signed continuation
- จำลอง query/commit failure และ task cancellation: ไม่มี partial body,
  rollback/connection release สำเร็จ; ต่อ connection เดิมให้คำขอถัดไปตรวจ
  isolation/read-only/user setting ไม่รั่วจาก F-11 session
- DB unavailable ไม่ถูกปลอมเป็น DATASET_CHANGED; content digest ที่กลับมา
  เท่าเดิมหลัง writer เปลี่ยนแล้วคืนทุก field เดิมถือเป็น input รุ่นเดิมตามแผน
- พิสูจน์ session ใหม่ปฏิเสธ DML ด้วย READ ONLY และตัวอ่านไม่มีการ enqueue
  refresh ภายใน transaction; ไม่อ้างว่าทุก session ของ API role เป็น read-only

แก้ deep review ข้อ4: แยกการตรวจ transaction ของ F-11 ออกจากสิทธิ์ API role
โดยใช้ PostgreSQL จริงและ fixtures ของผู้ใช้ในฐานทดสอบ:

- **ภายใน `indicator_read_session`:** อ่าน public candles ได้ และ READ ONLY
  ปฏิเสธ DML แม้เป็นคำสั่งที่ role มีสิทธิ์ตามปกติ ทดสอบด้วย INSERT preference
  ของเจ้าของที่ fixture ถูกต้องและยังไม่มีแถว เพื่อให้แยกได้ว่าไม่ได้ล้มเพราะ
  RLS/constraint/permission; ตรวจ read-only transaction violation ใน DB test harness
  และตรวจว่าไม่มีแถวเพิ่มจริงหลัง rollback
- **ภายใน `user_session` ปกติ:** การ INSERT `secret_sealed`/`key_version`
  ผ่านทางเข้ารหัสของ F-07 และ INSERT preference ของเจ้าของใน F-08 ยังสำเร็จ
  ใช้ fixture secret สำหรับเทสต์เท่านั้น ไม่แสดงค่าลับในผลทดสอบหรือ log
  สิทธิ์ DELETE key/UPDATE retry_requested_at ที่อนุมัติไว้ยังคงเดิม
- **ข้อห้ามระดับ role ที่ยังต้องจริง:** API อ่าน `secret_sealed`/`key_version`
  หรือ SELECT * ที่รวมคอลัมน์เหล่านี้ไม่ได้ และเขียน market_candles ไม่ได้
  ผู้ใช้หนึ่งอ่าน/เขียนข้อมูลที่ RLS ผูกกับผู้ใช้อื่นไม่ได้
  ไม่เพิ่มสิทธิ์ DML เพื่อให้ F-11 ผ่าน และไม่ถอนสิทธิ์ของ F-07/F-08
- **หลังคืน connection:** ใช้ pool_size=1 ทดสอบ normal→F-11→normal ทั้งทาง
  success/error/cancellation; user setting ไม่รั่ว และ transaction ปกติยังทำ
  authorized INSERT ได้หลัง F-11 จบ ไม่ค้าง READ ONLY จาก connection เก่า
- **ขอบเขตเส้นทาง F-11:** spy/audit SQL ของ GET ต้องไม่มี DML หรือการเรียก
  ฟังก์ชันที่มี side effect; READ ONLY ของ PostgreSQL อย่างเดียวไม่ใช้รับรอง
  ว่าไม่มี side effect ทุกชนิด refresh ยังคงผ่านทาง F-09 ที่กำหนดไว้
- แนวทางปัจจุบันไม่มีตาราง indicator จึงไม่ทดสอบ permission ด้วยการเขียน
  ตารางที่ไม่มีอยู่ เพราะ undefined-table ไม่ใช่หลักฐานว่าป้องกันการเขียนได้
- รัน regression เดิมใน `backend/tests/infra/api_keys/test_permissions.py`,
  `backend/tests/infra/trading_account/test_permissions.py` และ
  `backend/tests/infra/market_data/test_permissions.py` รวม route tests ของ F-07/F-08
  ไม่แก้ expected permissions ของเทสต์เดิมเพื่อให้ข้อความ F-11 ผ่าน

- เรียก API หลัง login กับแท่ง fixture, อ่านหลายหน้า, ตรวจ status/gap/finality;
  revoke session แล้วอ่านต่อไม่ได้; polling ไม่ต่ออายุ session
- เทสต์ปกติใช้ fixtures/FakeVenue และ disposable PostgreSQL;
  ไม่มี network call ไป Binance TH และไม่ส่งออเดอร์
- ตรวจ peak memory, elapsed time และงานพร้อมกันบนข้อมูล 1m เต็มขอบเขต
  ตามงบทรัพยากรที่อนุมัติใน plan และเกณฑ์ V-15 ด้านล่าง
- หากต้องเพิ่ม migration หรือแก้ DB roles ต้องเพิ่ม actual-role/upgrade/
  downgrade/replay tests และเกณฑ์ review ก่อนเจ้าของอนุมัติแผนใหม่

## ตรวจด้วยมือ

### เกณฑ์ V-18 — Token lifecycle

1. ใช้fixed test keys/identity/claimsสร้างtokenแบบkid.payload.mac;
   oracleคำนวณHMACแยกจากcodecและเทียบknown bytes ตรวจformat/base64url/canonical
   JSON/digestlength; encode/decodeคงclaimsครบและไม่ใส่cookie/token_hashในpayload
2. issued_atจากDBtimeและexpiry=min(issued+21600s,absolute sessionexpiry);
   ตรวจ expiry−1µs ผ่าน, expiryตรง/หลังได้409ไม่มีแถว; re-sign/pageต่อไป
   คงissued/expiryเดิม และrequestที่เริ่มก่อนexpiryแต่คำนวณจบหลังexpiryต้องได้409
3. Sessionเดิมreplayหน้าเดิมได้เมื่อdatasetเดิมและไม่หมดอายุ; sessionอื่นของuser
   เดียวกันหรือuserอื่นได้422, revoked/expiredsessionได้401ผ่านmiddlewareเดิม
   ทุกหน้าไม่ต่ออายุsessionและไม่ข้ามadmissionแม้tokenมีsignatureถูก
4. tamperทีละfieldและkid/payload/mac, signatureความยาวผิด, paddingไม่canonical,
   duplicate/unknownfields, boolแทนint, invalidtime/bounds/cursor,
   clientoverridequery, tokenเกิน4096bytes:ปฏิเสธก่อนquerycandles ไม่มีrawinputในerror
5. Tokenที่MACถูกแต่formula versionเลิกใช้ได้409ตามdataset invalidation;
   format versionที่ไม่รองรับปฏิเสธ422 INPUT_REJECTED ไม่เลือกdecoderตามclientเอง
6. configหาย/ไม่ใช่base64/keyไม่ครบ32bytes/kidผิดรูป/ซ้ำ/เกิน3รุ่น/bytesซ้ำ
   ภายในringหรือกับTOTP/venue:startupล้มพร้อมรหัสที่ไม่แสดงsecret
   รันKeySource/sealing testsเดิมเพื่อพิสูจน์behaviorเดิมไม่เปลี่ยน
7. Replica A/B มีcurrentเก่าและverificationใหม่:ตรวจtokenเก่าได้ทั้งคู่;
   หลังสลับAเป็นcurrentใหม่ Bยังตรวจtokenใหม่ได้ แล้วสลับBตาม
   ตรวจnext tokenที่ลงนามด้วยkeyใหม่ยังexpiryเดิม
8. ถอดkeyเก่าหลังทุกreplicaเลิกออกtokenเก่าอย่างน้อย6h; unknown/removedkid
   ได้409ไม่มีrows ไม่fallbackcurrentkey; emergencyremovalทำให้tokenรุ่นนั้น
   ใช้ไม่ได้ในทุกreplicaที่โหลดconfigใหม่ ไม่มีการอ้างrevocationก่อนrolloutครบ
9. runtimecrypto failureได้503ไม่มีpartial response; MACผิดไม่เผยรายละเอียด
   หรือrawcursor; expiry/keyremoved/datasetchangedใช้retrybudgetร่วมกันสูงสุด1restart
10. Capture API/uvicorn/error logsด้วยtest key/token sentinel:ไม่พบค่ากุญแจ
    หรือrawcursor; responseเป็นprivate,no-store และไม่มีtokenในerrorbody
11. Tokenใช้seed/fullinput boundsเดิมทุกหน้าแม้pagecursorขยับ;
    ลงนามถูกไม่ทำให้inputที่เปลี่ยนผ่านdigestcheck; ไม่มีcursor single-use DB writes

เกณฑ์นี้ได้รับอนุมัติแล้ว แต่ยังไม่ได้รัน เช่นเดียวกับข้ออื่น ๆ ของ F-11

### เกณฑ์ V-17 หลังแก้ deep review ข้อ5

- เตรียมแท่งที่ fetch ก่อน end_at ใน seed ก่อนช่วงผล: GET indicator ต้องมี
  REFRESH_REQUIRED และ target ที่รวม dependency นั้น ยาว<=1,000ช่อง
  ตรวจ SQL/DB ว่า GET ไม่สร้าง demand หรือแก้ watermark; ไม่มี queue row
  ต้องคืน queue_status/failure_code เป็นnull ไม่สร้างสถานะPENDINGขึ้นเอง
- integration consumer ใช้ target POST endpointจริงของ F-09 พร้อม session/CSRF;
  ได้202แต่ยังไม่ให้ค่า indicatorก่อนworker commit ทดสอบmissing/bad CSRFและ401ด้วย
- ทำสอง concurrent POST ผ่านconnectionsแยก: มี demandกลางต่อseriesเดียว
  targetถูกcoalesceตามF-09; active lease/cursor/attempt/backoffไม่ถูกreset
  ใช้fixtures/FakeVenueเดิมและตรวจworker behaviorจริง ไม่ตีความ202ว่าjobใหม่สองงาน
- POSTได้200จากraceที่writerแก้เสร็จก่อนPOST: callerอ่าน indicatorหน้าแรกใหม่
  และใช้เกณฑ์finality/fetchของF-11 ตัดสิน ไม่ใช้accepted=falseเป็นREADY
- writerคืนsuccessแต่transactionยังไม่commit/rollback: GET indicatorยังไม่พร้อม
  หลังcommitให้ค่าได้จากdigestใหม่แต่ยังUNCONFIRMEDตามinput
- worker COMPLETEแต่ยังมีแท่งใช้ไม่ได้ต้องคงREFRESH_REQUIRED;
  queue metadata เป็นseries-wide ไม่อ้างว่าคำขอของcallerเสร็จโดยเฉพาะ
- fake clock ของconsumerพิสูจน์ pollingทุก10sสูงสุด6ครั้ง/60sและPOST1ครั้ง/รอบ
  FAILED/UNAVAILABLE/401/errorหยุดรอบ, POSTtimeoutไม่blind-retry,
  more_requiredไม่ทำให้auto fan-outไปทุกช่วง; rate limitindicatorเดิมยังบังคับ
- เมื่อpollชี้ว่าrefreshตอบแล้ว ต้องทิ้งหน้าที่เก็บและเริ่มGET indicatorใหม่
  ถ้ายังไม่พร้อมไม่POSTวน; continuationรุ่นเก่าหลังinputเปลี่ยนได้409ไม่มีแถว
- ทดสอบtargetนอกretentionหลังเวลาผ่านได้errorF-09เดิม ไม่clamp;
  ทดสอบgapจริงไม่กลายเป็นREFRESH_REQUIRED และbackfillใช้ทางเดิม
- ตรวจOpenAPI refresh metadata และrerun candle route/ingestion/claim testsเดิม
  ไม่เพิ่มorder/secret callsหรือbrowser UIเพื่อให้integration scenarioผ่าน

### เกณฑ์ V-15 — Approved (2026-10-10)

อนุมัติแนวทางและเกณฑ์นี้พร้อม plan/validation ก่อน implementation โดยยังไม่ต้อง
มีผล benchmark; รันกับ implementation จริงหลังได้รับอนุมัติครบและบันทึกผลวัด
ทุกข้อด้านล่างต้องผ่านก่อน merge หรือเปลี่ยนสถานะเป็น Completed
หากต้องเปลี่ยนแนวทางหรือผ่อนเกณฑ์หลังผลไม่ผ่าน ให้ขออนุมัติเอกสารที่เกี่ยวข้อง
ใหม่ก่อนเปลี่ยน implementation หรือเกณฑ์ ไม่ถือว่าการอนุมัติแผนคือผลทดสอบผ่าน

1. Benchmark API Linux container2vCPU/1GiB/หนึ่งprocess โดย PG16/Redis7 แยก
   container บน host เดียว; บันทึก hardware, versions, idle baseline และข้อมูล fixture
   ใช้525,600ช่อง/ครบทุก indicator และ output1,000ช่อง ทำ cold1/warm5 requests
   ทุกครั้งต้องสำเร็จพร้อม digest/ค่าถูกต้องภายใน30s ไม่ผ่านด้วยการคืน504
   peak RSSเพิ่ม<=128MiB, event-loop lag<=100ms, response<=2MiB
2. งานพร้อมกัน10คำขอในprocessเดียว: candle jobทำได้สูงสุด1,
   อีก9คำขอได้503 INDICATOR_BUSY โดยไม่ query candles และไม่มีคิวรอ
   ตรวจ physical slot ยังถูกถือระหว่าง rollback/query cancellation
3. ใช้2 API processes กับ Redisเดียวกัน: งานได้สูงสุด1/process,
   รวม2งานเป็นพฤติกรรมที่ยอมรับ; user counterและglobal counterใช้ร่วมกัน
   ไม่อ้าง global concurrency1 และบันทึกpoolรวม2connections
4. หน้าต่าง60sจาก Redis TIME: attemptที่7/user หรือ31รวมถูกปฏิเสธ429
   ไม่ query candles; ทดสอบ boundary burst ตาม fixed-window semantics,
   counter expiry120s, ไม่refundเมื่อdeadline/numeric failure และแยก WS namespace
5. Redisล่ม/ตอบเกิน500ms:503 ADMISSION_UNAVAILABLE ไม่ fallback local;
   denyจริง:429 RATE_LIMITED พร้อม Retry-After60; F-10 admission regressionเขียว
6. ใช้ barrier/injected clock ทำให้เวลาครบ30sระหว่าง query, decode, hash,
   calculate และ serialization:504ไม่มี partial body; deadlineไม่เริ่มใหม่ต่อbatch
   client disconnectกลางงานหยุด reader และไม่มี background computationต่อ
7. ตรวจ statement_timeout<=500ms/lock_timeout<=200ms ตามเวลาที่เหลือ,
   pool_size1/max_overflow0/pool_timeout250ms; pool/query failureเป็น503
   เมื่อdeadlineยังเหลือ ไม่แปลงเป็น409; ใช้ DBจริงตรวจqueryถูกcancel
8. cleanup<=2sในfailure tests; จำลองcloseติดค้างเกินงบต้องinvalidate connection
   และไม่คืนslotก่อนยืนยันว่าทรัพยากรหยุด งานใหม่ยังถูกปฏิเสธแทนการซ้อนงาน
   ตรวจ reuse connection ไม่มีsnapshot/RLS/read-onlyค้าง
9. เพิ่ม concurrent refresh/backfill writer และ rejected-request loadระหว่าง
   benchmark; ต้องยังผ่าน30s/128MiB/100msและsnapshot semanticsของข้อ2
10. ตรวจ serverไม่มี auto retry; ผู้ใช้ผลrestartหลัง409สูงสุด1ครั้งและทิ้งหน้าเก่า
    ก่อนอ่านใหม่; 429/503/504ไม่วนอัตโนมัติ ตรวจ body ไม่มีข้อมูลลับ

ผลล่าสุดของด่านนี้อยู่ในหลักฐาน implementation ด้านล่าง; เกณฑ์ที่ยังไม่มีหลักฐาน
ถือว่ายังไม่ได้รัน ถ้าfull-size benchmarkไม่ผ่านต้องแก้แผนและขออนุมัติ
ไม่ปรับตัวเลขเกณฑ์หรือขอบinputตามผลที่ล้มโดยไม่แจ้งเจ้าของ

### ขั้นตอนตรวจผลด้วยมือ

1. Login แล้วเรียก endpoint สำหรับหนึ่งคู่บนข้อมูล fixture ที่มี 1,199 แท่ง;
   ตรวจค่า EMA200 จุดแรก/จุดสุดท้ายและเวลา UTC กับ expected fixture
2. อ่านหน้าแรก จากนั้นให้ market-data เติมแท่งที่เคยขาดก่อนหน้าที่อ่าน;
   อ่านหน้าถัดไปต้องได้ 409 แล้วเริ่มใหม่เห็นรุ่นข้อมูลใหม่ครบชุด
3. ใช้แท่งที่ดึงก่อนปิดช่วงและยังไม่ refresh; ต้องเห็น REFRESH_REQUIRED
   เมื่อ refresh commit แล้วคำนวณได้โดยยังบอกว่า UNCONFIRMED
4. ทดลองสองช่วงผลที่ทับกันและหน้า 1,000 ช่อง; ค่าของแท่งเดียวกันตรงกัน
   พร้อมสถานะ warm-up/finality ตรงกัน

## ด่านที่ต้องเขียวก่อน merge

จาก `backend/`: `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy`, `uv run lint-imports`, `uv run pytest`
รวม pure-core/architecture/network/actual-role tests เดิมทุกด่าน

จาก `frontend/`: `npm run lint`, `npm run typecheck`, `npm run test`,
`npm run build`; ตรวจ `npm run gen:api` แล้ว generated types ไม่มี diff
ส่งออก `backend/openapi.json` ด้วยคำสั่ง CI แล้วไม่มี diff
รัน browser E2E ตาม CI หากเปลี่ยนเส้นทางหรือ flow ที่ browser ใช้
ตรวจ `git diff --check` และ review mapping RQ-1..RQ-15 กับ V-1..V-18

## ก่อนเริ่ม implementation

เงื่อนไขอนุมัติด้านล่างครบแล้วเมื่อ 2026-10-10 ตามคำสั่ง “approve”:
requirements/plan/validation เป็น Approved และ NC-30..33 ปิดครบ
พร้อมเริ่ม implementation โดยยังไม่ถือว่าผลทดสอบหรือ benchmark ผ่าน

requirements ต้องเป็น Approved; NC-30..33 ต้องปิดและไม่เหลือคำถามที่เกี่ยวข้อง
plan กับ validation ต้องปรับตัวเลข expected, numeric contract, revision
และเพดานเวลา/concurrency ตามคำตัดสินจริง แล้วเจ้าของอนุมัติทั้งคู่
จนกว่าจะครบ ให้ผล validation ทุกข้อเป็น **ยังไม่ได้รัน** ไม่อ้างว่าผ่าน

## หลักฐาน implementation รอบแรก — 2026-10-10

- core arithmetic/indicator/purity tests ที่เพิ่ม: 12 ผ่าน; cursor codec: 1 ผ่าน;
  PostgreSQL snapshot/writer commit และ API auth/pagination tests: 3 ผ่าน
  รันรวมกับ canary secret ทุก route หลังแก้ query แล้วได้18ผ่าน (canary2ข้อ)
- backend Ruff check/format, mypy และ import contracts 7 ข้อผ่าน
- full backend regression ยังไม่ผ่านครบ: หยุดรันหลังพบ failures/errors;
  canary ตรวจทุก route เพิ่ม query ของ indicator route และรันซ้ำผ่านแล้ว;
  ยังไม่ได้รัน full regression จบหลังแก้ จึงไม่อ้างว่า failures/errors อื่นปิดแล้ว
- frontend types/lint/build ผ่าน; Vitest 156 ผ่าน/2 ล้มจาก Windows symlink EPERM
  ของ API contract gate; ยังต้องตรวจด่านนี้บน Linux ตาม CI
- benchmark ใช้ Linux API container image `tiewtrade-api` (Python3.12), จำกัด
  2vCPU/1GiB, PostgreSQL16 และ Redis7 บน Docker host เดียวกัน แยกจากฐานแอป
  fixture INSERT 525,600 ช่อง 1m ราคา100/high101/low99 และเรียก API จริงหลังสมัคร
  รัน cold request ได้ HTTP504 INDICATOR_DEADLINE_EXCEEDED ที่30.109763s;
  measured event-loop lag สูงสุด0.208018s เกินเกณฑ์0.100s
- V-15 **Failed**: จึงหยุด benchmark ก่อน warm5 runs ไม่อ้างว่ารองรับชุดสูงสุด
  หรือว่า RSS ผ่าน (ค่า high-water mark หลังเตรียมfixtureไม่ใช่ idle RSS ที่เพียงพอ)
  ยังไม่ได้พิสูจน์ rejected-load/writer-load และ cleanup ทุก failure case
- ยังขาด validation ครบทุก numeric series/property, cursor/security edge cases,
  disconnect/cleanup/admission multi-process, retention clock matrix และ refresh
  integration consumer; งานนี้ยังไม่พร้อม merge/Completed
- ตัวรัน benchmark อยู่ใน `backend/tests/api/test_indicator_budgets.py`
  เรียกโดยตรงเฉพาะ Linux กับฐาน disposable; fixture ลบ market_candles ในฐานนั้น
- ตาม plan “เกณฑ์รับผล benchmark” ต้องเสนอและรับอนุมัติแผนใหม่ก่อนเปลี่ยน
  แนวทาง revision/state หรือผ่อนเกณฑ์; ยังไม่มีการเปลี่ยนแนวทางดังกล่าว
- Profile ตามคำสั่งเจ้าของ “เริ่มทำ 1” เสร็จแล้ว: [รายงานและวิธีวัด](profiling/report.md)
  พร้อม raw JSON/cProfile; ยืนยันรอบ API ปกติยังได้504และlagเกินเกณฑ์
  ต้นทุนหลักเป็นcore/decode และ decodebatchถือeventloopเกิน100msได้
  ผลนี้เป็นหลักฐานเสนอแผนขั้นถัดไป ไม่เปลี่ยนเกณฑ์หรืออนุมัติแนวทางใหม่

## ผล implementation ตาม NC-34 — 2026-10-10

ปรับkernel/sharedvalidation/fetch-decode slicesตามแผนbatchที่อนุมัติแล้ว
ผลและraw artifactsอยู่ใน [รายงานbatch](profiling/batch/report.md)
cold APIยัง504ที่30.071056s; lag27.593ms/RSSเพิ่ม62.6MiBต่ำกว่าเพดาน
ในคำขอที่ล้มนี้ แต่V-15ยัง **Failed** และหยุดก่อนwarm5
fullregression/PV/Vที่เหลือยังไม่ผ่านครบ ไม่เปลี่ยนเกณฑ์หรือเริ่มarchitectureใหม่
