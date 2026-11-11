# ลดเวลารอ CI — Validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-11**
วันที่: 2026-10-26
ปรับแผนตรวจ: 2026-11-11 — docs-only/full โดยคงด่านก่อน–หลัง merge

ผล implementation/review/refactor และ local validation ล่าสุด: [checkpoint 2026-11-11](evidence/checkpoint.md).
Local Passed ไม่แทน formal review, GitHub pilot หรือ required CI.

## เสร็จหมายถึงอะไร

ทุกเกณฑ์ด้านล่างเป็นระดับ `Feature`; ระบุจังหวะก่อน/หลัง merge แยกกัน.
งานนี้ไม่เพิ่มเกณฑ์ Batch/Release ของ application และใช้เกณฑ์เดิมของแต่ละ feature ต่อ.

| รหัส | เกณฑ์ / สิ่งที่พิสูจน์ | วิธีตรวจ | ระยะ / Checkpoint | ผล |
|---|---|---|---|---|
| V-01 | Trigger ไม่สร้าง feature-push run ซ้ำ PR; main/manual ยังตรวจได้ | workflow assertions/actionlint และ GitHub pilot PR/main/manual | Feature — local และก่อน/หลัง merge | Partial — local trigger assertions Passed; GitHub pilot Pending |
| V-02 | PR candidate เก่าถูกยกเลิก ส่วน main/manual แยก run identity และไม่ถูกยกเลิกเพียงเพราะมีรอบใหม่ | static expression checks และ pilot synchronize PR ระหว่างรอบแรกยังทำงาน; ตรวจ main/manual grouping | Feature — local และ GitHub pilot | Partial — local concurrency wiring Passed; real cancellation Pending |
| V-03 | Docs whitelist ไม่เรียก application services; executable/generated/runtime inputs ไม่ถูกจัดเป็น docs | helper tests: docs-only, specs Python/JSON/config, unknown Markdown path, runtime-input exceptions, mixed docs+runtime | Feature — development | Passed — review R1 fixed; four operational/contract exceptions and git/CLI regression |
| V-04 | ทุก non-docs PR เรียก backend/frontend/API-contract/E2E/container ครบตามเดิม ไม่ข้ามชุดแยก backend/frontend | table-driven cases สำหรับ frontend tests/source/assets, backend/core/API/migrations/tests, generated types, lockfiles, Compose, config และ workflow | Feature — development | Passed — local full-selection matrix และ baseline worker inventory |
| V-05 | Rename/deletion/path พิเศษไม่ทำให้หลุด tests และ diff failure ไม่เป็น empty-success | disposable git fixtures: rename runtime→docs และกลับกัน, deleted files, spaces/newlines, missing base, failed diff, empty diff | Feature — development | Passed — real git rename/delete/path/base/fetch/shallow fixtures หลัง refactor |
| V-06 | docs-only ต้องผ่าน whitelist ทุก path; full mode/main ไม่ถูกลดตาม diff แม้เป็นเอกสารล้วน | mixed-path cases, full+docs, main+docs และ manual affected merge-base cases | Feature — development | Passed — local docs/full/main/manual/mixed cases |
| V-07 | Selector fail หรือ output ขาด/ผิดรูปแบบไม่ทำให้ required checks เขียว | negative verdict tests ทุก selected/unselected × success/failure/cancelled/skipped/missing/unknown; selector failure/output invalid | Feature — development | Passed — 294-case verdict matrix และ CLI failure propagation |
| V-08 | ชื่อ required checks คงเดิม, verdict ไม่หลบ failure และตรวจ PR merge candidate ตาม protection ปัจจุบัน | compare baseline names, needs/always()/worker conditions และ checkout/base selection; remote protection readback และ pilot check SHA/results | Feature — candidate ก่อน merge | Partial — local names/wiring and strict seven-context protection readback Passed; pilot Pending |
| V-09 | Runtime commands/assertions/services/versions และ Live isolation ไม่ถูกลด รวม safety tests เดิมทั้งหมด | review focused diff เทียบ baseline; inventory E2E, isolated migration/global-state guards, role URLs, no continue-on-error; ใช้ผลเดิมของ suites ที่ไม่เปลี่ยน | Feature — candidate ก่อน merge | Passed — five execution blocks preserved; review/R1/refactor impact verified locally |
| V-10 | Workflow syntax และ helper code ใช้งานได้โดยไม่ bootstrap app | actionlint, standard-library unittest สำหรับ helpers, lint/format เฉพาะ Python ใหม่ และ diff whitespace | Feature — development/candidate | Passed — post-refactor 28 tests, Ruff lint/format, strict mypy; actionlint reused; ShellCheck not run |
| V-11 | Docs-only PR จบด้วย required checks ครบ โดยไม่ provision application DB/Redis/browser/container | GitHub pilot logs และ check results ของ SHA จริง | Feature — ก่อน merge | Pending GitHub pilot — owner authorized commit/push/PR |
| V-12 | Non-docs PR เรียกชุดเดิมครบ; selected failure ไม่ถูก verdict แปลงเป็น success | ใช้ PR ของงานนี้ซึ่งแก้ workflow/helper เป็น full pilot; ใช้ bounded negative helper case บน GitHub โดยไม่แก้ application ให้พัง; เทียบ commands/results กับ baseline และ negative matrix | Feature — ก่อน merge | Pending required CI — owner authorized commit/push/PR |
| V-13 | Manual full และ post-merge main เรียกทุกชุดเดิม ไม่ลดเป็น smoke หรือข้ามเพราะ docs-only | local assertions ก่อน merge; GitHub manual full เมื่อ default branch พร้อม และ CI บน merge SHA; คงผลล้มเดิม ไม่รัน workload เพิ่ม | Feature — local ก่อน merge; main/manual หลัง merge เมื่อเรียกได้ ก่อนปิดงาน | Partial — local forced-full assertions Passed; main/manual pilot Pending |
| V-14 | งานอื่นไม่สูญหาย และ final combined workflow คงชุดตรวจใน baseline จริง รวม F-17/F-18/F-19 ตามที่มีอยู่ | inventory working tree ก่อน/หลัง, isolated branch baseline SHA; ตรวจ command/config และ selector/verdict dependencies บน final combined candidate; รายการยังไม่รวมคง Pending | Feature — development/integration ก่อน merge | Passed — latest-main integration inventory/pending-work preservation; recheck if baseline changes |
| V-15 | สถานะและเวลาไม่กล่าวอ้างเกินหลักฐาน | checkpoint บันทึก SHA/diff/commands/elapsed ที่วัดจริง; เทียบ setup/queue/run แยกกันถ้ามี baseline เทียบได้ | Feature — ทุก checkpoint | Partial — local evidence recorded; GitHub timing/results Pending |
| V-16 | รวมการแก้/เอกสาร/หลักฐานก่อน push และไม่เพิ่มรอบ CI โดยไม่มีเหตุ; คง review/อนุมัติ Git และ merge ตามเดิม | ตรวจ checkpoint/commit/run history ที่เกิดขึ้นจริง: คำสั่งเจ้าของ, Ready for Code Review → รอ review code, คำตอบ refactor เมื่อเข้าเงื่อนไข, local gates, เหตุผลของแต่ละ push/rerun; ไม่สร้าง commit เพียงเพื่อบันทึก CI | Feature — candidate และปิด checkpoint | Partial — review/R1/refactor/local validation complete; Git/pilot authorized and in progress |

## ขอบเขตตรวจระหว่างพัฒนา

เปลี่ยน orchestration และการเลือก tests จึงต้องตรวจ policy/failure propagation โดยตรง.
ใช้ Python unittest standard library กับ disposable git repositories สำหรับ diff parsing;
ไม่ใช้ mock-only assertions ที่แค่เทียบข้อความ implementation.
ใช้ actionlint ตรวจ YAML/expressions/jobs และ review shell handling ของ untrusted input.
ไม่รัน backend/frontend full suites หรือ workload เพื่อยืนยัน selector ถ้า runtime commands
และ application dependencies ไม่เปลี่ยน; หาก diff ขยายถึงพฤติกรรม runtime ให้ประเมินใหม่.

## ตรวจด้วยมือ / GitHub pilot

หลังได้รับคำสั่ง Git จึง commit/push/เปิด PR และใช้ workflow_dispatch.
Local tests ไม่รับรอง scheduler, cancellation หรือ branch-protection จริง.
เก็บ run URL, SHA, selected sets, check conclusions และ cancelled superseded run.
ใช้ PR ของงาน workflow นี้เป็น full pilot แทนสร้าง runtime PR เพิ่มเพื่อพิสูจน์ selector;
docs-only pilot และ bounded synchronize สำหรับ cancellation รวมหลักฐานร่วมกันได้.
รวมการเปลี่ยนที่ต้องใช้ในแต่ละ pilot ก่อน push ไม่สร้างหลายรอบเพื่อเก็บหลักฐานซ้ำ.
กรณี workflow_dispatch ต้องมี workflow บน default branch ก่อน GitHub เปิดให้เรียก
ให้บันทึก Pending จน merge/owner-authorized pilot พร้อม ไม่อ้าง local simulation เป็น Passed.
ก่อน merge ต้องมี V-11/V-12 และ Feature candidate gates ที่เกี่ยวข้อง รวม static checks
ของ V-13; ก่อน merge อ่าน required protection และตรวจ candidate ให้เป็นปัจจุบัน.
V-13 ส่วน post-merge/manual ที่ยังเรียกไม่ได้คง Pending และยังไม่ Completed.
หลังเจ้าของสั่ง merge ให้ติดตาม CI บน merge SHA ครบทุกชุดตามเดิม; manual full
เรียกเมื่อได้รับคำสั่ง dispatch. ไม่ปิดงานเพียงเพราะ actionlint หรือ pre-merge CI ผ่าน.

## E2E parallelism

แผนนี้เลือก fallback คง E2E sequential ตาม RQ-08 จึงไม่อ้างว่าพิสูจน์ parallel isolation.
คง `workers: 1` และ service isolation เดิม. การแยกขนานเป็น amendment ภายหลัง
ไม่เพิ่ม endurance/timed smoke เพื่อพิสูจน์ประเด็นที่แผนนี้ไม่ได้เปลี่ยน.

## ความหมายของผล

Not Run/Pending/Failed ต้องคงตามจริงจนมีหลักฐาน. ผลรวม helper tests ผ่านไม่แทน
GitHub pilot หรือ release validation ของ feature อื่น. ไม่ลด required branch protection,
ไม่ส่ง Live orders และไม่เปิด production เพื่อทดสอบ CI.

## สถานะเอกสารรอบนี้

รอบปรับแผน 2026-11-11 เป็น documentation-only: ตรวจความสอดคล้องกับ requirements,
plan, AGENTS.md และ testing §6–7 พร้อม Markdown references/whitespace เท่านั้น.
ไม่รัน application tests หรือ CI เพื่อยืนยันการแก้เอกสาร และไม่เปลี่ยนผล V-01–V-16
เป็น Passed จากการตรวจเอกสาร. เจ้าของอนุมัติ plan/validation แล้วในวันที่
2026-11-11; บันทึกผล implementation/pilot แยกตามหลักฐานจริงใน checkpoint.
