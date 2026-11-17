# NC-F17-W3-OBS-01 — implementation checkpoint

สถานะ: **Implementation/targeted checks Passed — รอ owner review code**
วันที่: 2026-11-16 (Asia/Bangkok)
อนุมัติ: เจ้าของตอบ `approve` เลือก A ของ [แผน](../../observed-w3-fail-fast-plan.md)

## การเปลี่ยน

- `profile_publisher_lease_load.py`: flag validation เฉพาะ observed internal20 W3;
  Future หนึ่งตัวรับผลจาก sampler task เดิม ไม่มี publisher task/SQL/polling ใหม่;
  failure receipt แยกจาก readiness/lease summary และรักษา primary/Failed เดิม
- `profile_workload.py`: รอ signal พร้อม source/operation/checks เดิม ครอบ ready,
  baseline, cycles, fault wait, duration, tail และตรวจก่อน final rebuild;
  ไม่เริ่ม coroutine ของ phase ใหม่เมื่อ signal พร้อมแล้ว ไม่ถือ intentional stop เป็น error
- บันทึก ownership ของ worker ทีละตัว รวม spawn ที่รับ cancellation; opt-in startup
  deadline 60s และคืน ownership ก่อน cleanup; finalizers join ผ่าน repeated cancellation
  และพยายาม dispose engines ทุกตัวโดยคง primary error
- `remaining_paper_campaign.py`: เพิ่ม CLI/forward flag เฉพาะ parent ไม่มีการส่งให้ workers
- เพิ่ม `test_publisher_fence_fail_fast.py` และขยาย real publication/ambiguous commit/
  CLOCK01 tests เดิมให้ตรวจเมื่อเปิด flag ด้วย ไม่มี production edit ใน amendment นี้

## หลักฐาน

434 tests Passed ในชุด targeted 11 files รวม fixture setup/cleanup 55.3345s
มี option matrix, phase boundaries, error race/identity, partial spawn/repeated cancel,
failed envelope/IO, expected monitor shutdown, no false Passed, real PG sampler timeout,
rollback/advisory lock release, actual publication/ambiguous commit/readiness/CLOCK01,
owned-pool inventory, final tail และ default/profile/rebuild launcher regressions

Ruff, format check, mypy ของ 5 files ที่เปลี่ยน และ git diff --check Passed
ดู [structured summary](w3-obs01-summary.json); raw logs/runner helper/cleanup ที่
`validation-artifacts/f17-obs01-final-tests-20261116/` และ test runner
`/tmp/tiewtrade-f17-obs01-final-tests.py` ใช้ helper ที่ hash ตรวจแล้วตาม pattern เดิม

Independent admin read ยืนยัน DB ของ test attempts ทั้งสอง absent, 0 connections,
0 database locks ไม่มี force drop หรือหยุดบริการอื่น

## ประวัติและข้อจำกัด

- Local ครั้งแรกมี 3 failures ใน fixtures ของ tests ใหม่ (tail scope และ fake report fields)
  และ static typing/import issues แก้แล้ว ไม่ใช่ผล endurance
- Real-DB safety ครั้งแรก 431 Passed/1 Failed เพราะ rollback-proof query ส่ง xid8 เป็น string;
  แก้ binding เป็น integer แล้ว final 434 Passed เก็บผล Failed เดิมและ cleanup proof ไว้
- Scope ของ phase-sequencing unit tests ใช้ fake I/O/เวลา ไม่ใช้แทน real transaction proof;
  rollback/locks/source/readiness/ambiguous commit มี real PostgreSQL tests แยก
- ยังไม่ได้รัน 14400s W3, pin campaign candidate/config/schema/runner หรือ preflight ของรอบยาว
  และยังไม่ได้ review/refactor ของ amendment นี้ จึงยังไม่ใช่ Batch acceptance
- Reviewer ควรเน้น signal/error priority, startup ownership, cancellation/finalizer ordering,
  pool cancellation evidence และ independent receipt เมื่อ summary เขียนไม่ได้
- ผล offline REBUILD20-04 Passed และ W3 Incomplete เก่าคงตาม candidate เดิม F-17 ไม่ Completed

ขั้นถัดไป: รอคำสั่ง `review code` จากเจ้าของ จากนั้นผ่านด่านแก้ findings/refactor และตรวจ
ผลกระทบตาม AGENTS ก่อนหนึ่ง observed W3 ที่อนุมัติ ไม่มี commit/push/CI/merge ใน scope นี้
