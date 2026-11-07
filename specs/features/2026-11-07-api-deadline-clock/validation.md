# API deadline clock correctness — Validation

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-07**
วันที่: 2026-11-07
Requirements: [Approved](requirements.md) · [Plan](plan.md)

## “เสร็จ” หมายถึง

| รหัส | เกณฑ์ / requirement | วิธีตรวจ | ระยะ | ผล |
|---|---|---|---|---|
| V-01 | offset บวก/ลบไม่เปลี่ยน success และไม่ทำให้ stalled work หลุด timeout; RQ-01/06 | Pure boundary tests สำหรับ live/shared response ใช้ ± offset; async work ที่ได้ yield ต้องสำเร็จก่อนงบหมด และงานค้างต้องถูก cancel จริง พร้อม outer watchdog | Feature | Passed — offset ± regression; before-fix 4 failed, after-fix boundary suite passed |
| V-02 | งบรวมไม่รีเซ็ต; synchronous exact boundary/overrun ถูกปฏิเสธ; RQ-02 | admission + work budget case, already-exhausted remaining duration, serialization ก่อน/เท่ากับ/เกิน deadline; คง tests 29.999/30/30.001 ของ indicator และตรวจ live 2-second boundary | Feature | Passed — live exact boundary, shared remaining/exhausted/admission budget และ indicator exact boundary เดิม |
| V-03 | timeout/disconnect/external cancellation รอ cleanup และคืน budget; RQ-04 | test_indicator_disconnect.py และ boundary tests; assert task termination/resource release รวม repeated cancellation โดยไม่กลืน CancelledError | Feature | Passed — pure cleanup และ real PostgreSQL cancellation/pool reuse; repeated cancel ครอบ offset ±/0 |
| V-04 | API/data/security contracts คงเดิม; RQ-03/05 | test_chart_routes.py + test_indicator_routes.py บน disposable PostgreSQL/Redis: auth/CSRF, session, error codes, exact data, readiness/history/proof; คง DB timeout mapping และ cache-control | Feature | Passed — API/DB/cleanup group 69 passed; error/auth/data contracts เดิม |
| V-05 | recovery ผ่าน default loop; RQ-07 | existing live snapshots recover E2E พร้อม real DB/Redis บน host ที่พบ clock offset; บันทึก Python/uvloop/loop identity และ READY→RECOVERING→READY; standard asyncio compatibility run แยก | Feature | Passed — default auto/uvloop recovery 10.4s; standard asyncio 8.8s; committed config ไม่เปลี่ยน |
| V-06 | source scope/static/architecture ถูกต้อง; RQ-01..05 | Ruff check/format changed Python, mypy ตาม config และ import-linter; diff ไม่เปลี่ยน config/deps/financial/session persistence; git diff --check | Feature | Passed — Ruff, mypy 678 files, import-linter 7 contracts, diff scope และ whitespace |
| V-07 | review/fixes และ CI บน candidate สุดท้าย | Ready notification → owner review → findings closure; refactor ต้องอนุมัติ; required CI พร้อม SHA/run URL เมื่อเปิด PR ตามคำสั่ง | Feature | Partial — code review APPROVED; authorized refactor และ boundary rerun 24 cases ผ่าน; required CI Pending — เจ้าของอนุญาต commit/push/PR แล้ว; ผลพร้อม SHA/run URL จะรายงานหลัง CI จบ |
| V-08 | consumer status ไม่ถูกยกระดับผิด; RQ-08 | ตรวจ roadmap/evidence: งานลบ prices คง V-03 Partial/Failed จน candidate รวมผ่านเกณฑ์เดิม; ผล fix นี้ไม่ใช่ผล candidate รวม | Feature | Passed — ยังไม่ปิด V-03 ของงานลบ prices; ต้องตรวจ candidate รวมภายหลัง |

## การเลือกตรวจตามผลกระทบ

- Pure boundary + disconnect suites พิสูจน์ scheduling/cancellation โดยไม่ต้องข้อมูลใหญ่
- Real DB API suites พิสูจน์ contracts และ deadline propagation ลง query_budget ที่ mocks แทนไม่ได้
- หนึ่ง default-loop recovery flow และหนึ่ง standard-loop run ครอบปัญหา environment โดยตรง
  ใช้ config ชั่วคราวสำหรับ standard loop เท่านั้น ไม่แก้ committed default config
- ใช้ tests เดิมก่อนเพิ่มใหม่; ไม่เพิ่ม tests ที่เพียงสะท้อนโค้ดหรือไม่พิสูจน์ behavior
- ผลก่อน fix เป็น diagnosis เท่านั้น; หลัง fix รันชุดที่กระทบข้างต้น หากแก้ tests/docs ภายหลัง
  ให้รันซ้ำเฉพาะส่วนที่ผลเดิมได้รับผลกระทบ
- ไม่รัน full regression/workload โดยอัตโนมัติ; ถ้าพบ cross-system impact หรือพิสูจน์
  shared boundary ไม่พอ ต้องระบุความเสี่ยงและขยายตาม standards/testing.md §7
- เกณฑ์ Batch/Release ของ F-11/F-12 คง checkpoint/status เดิมใน roadmap;
  ไม่มีเกณฑ์ Batch/Release ใหม่ใน fix นี้ และไม่อ้างว่า fix ผ่านแล้วทำให้เกณฑ์เดิมผ่าน

## Safety และหลักฐาน

ใช้ DB/Redis ใหม่ที่ชื่อผ่าน E2E guard; ไม่แตะ production/dev data หรือส่ง Live orders
บันทึก base/candidate SHA และ uncommitted diff identity ถ้ามี, command, environment,
ผล pass/fail และ relevant logs โดยไม่บันทึก token/secret/query parameters
การใช้ float สำหรับเวลาคงเดิม ไม่ใช่การคำนวณเงิน

เมื่อเกณฑ์เดิมไม่ผ่านสามรอบให้หยุดและเสนอทางเลือกก่อนทดลองต่อ ตาม AGENTS.md
หลังโค้ดครบต้องแจ้ง Ready for Code Review และหยุดก่อน review
ยังไม่ Completed/พร้อม merge จนด่านที่เกี่ยวข้องครบ; local results ไม่แทน required CI

## Implementation checkpoint

[ผลและหลักฐาน](evidence/implementation-checkpoint.md): local checks ผ่าน; รอ review/CI.

[Post-review/refactor checkpoint](evidence/refactor-checkpoint.md): test-only cleanup ผ่าน targeted validation; runtime evidence เดิมยังใช้ได้.
