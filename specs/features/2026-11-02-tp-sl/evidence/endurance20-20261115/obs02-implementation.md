# NC-F17-OBS-02 — implementation checkpoint

สถานะ: Implementation/targeted checks Passed; diagnostic campaign Not Run
[Approved plan](../../observer-short-diagnostic-plan.md)
[Machine summary](obs02-implementation-summary.json)

เพิ่ม `profile_observer_diagnostic.py` และ `test_observer_diagnostic.py` เท่านั้นใน source
ของ amendment นี้ ไม่แก้ production หรือ observer เดิม ใช้ instance proxy วัด 7 ช่วง
เรียก sample เดิมครั้งเดียว ไม่มี global monkeypatch ขณะ diagnostic ทำงาน
connect รวม driver transaction setup; query/session exit รวม await/scheduling
ห้ามตีความเป็น server execution ล้วน เก็บ loop lag แบบ count/max/sum

Runner function run_captures รัน cold/reused/known-blocker ตามลำดับ 10 captures ต่อชุด
error หยุดก่อนชุดถัดไป รักษา primary exception และพยายามเก็บ partial evidence
ใช้ guard/readonly_admin/fence sessions/save_partial_result/owned cleanup เดิม
ข้อมูลทั้งหมดเป็น fixture ไม่มี publication tick ปลอม ไม่มี orders/บัญชีเจ้าของ/Live
ไม่มี persistent business/session state ใน process; timing เป็นข้อมูลชั่วคราวและเขียนหลักฐานลงไฟล์

## Validation

- ชุดแรก 65 Passed (17 OBS-02 + 48 observer regression), 26.4383s รวม setup/cleanup
- ชุดเพิ่มเติม 35 OBS-02 Passed, 19.0643s รวม setup/cleanup
- มี 17 tests ซ้ำระหว่างสองชุด รวม **83 distinct Passed** ไม่ใช่ 100 distinct
- ครอบคลุม once-only result/exception identity, task isolation/concurrent rejection,
  timing missing/NaN/infinite/malformed, phase error/cancellation ทุกช่วง,
  original 1s timeout, evidence IO failure พร้อม/ไม่มี primary, bounded lag aggregate
- Real PostgreSQL: readonly, actual blocker identity, lock release และไม่มี transaction
  ค้างหลัง fixture failure/cancellation; regression ของ observer เดิมใช้ฐานจริง
- Ruff/check, format/check, mypy สองไฟล์และ git diff --check Passed
- Independent cleanup ของทั้งสองฐาน: database absent, connections0, locks0

Initial static drafting errors (format/type/name) ถูกแก้ก่อน checkpoint; ไม่มี test failure
ในการรันสองชุดนี้ ผล OBS-01 Incomplete และหลักฐานรอบก่อนทั้งหมดคงเดิม

## ค้าง / ข้อจำกัด / จุดหยุด

ยังไม่รัน preflight หรือ diagnostic campaign จริง และไม่อ้างว่าหาสาเหตุ W3 ได้แล้ว
run_captures เป็น inner runner; ตอนเตรียม campaign หลัง review/refactor ต้องประกอบ
coordinator ที่ pin candidate/config/migrations/runner, preflight ก่อน fixture,
600s total/60s cleanup reserve และ independent ownership cleanup ตาม plan เดิม
ยังไม่ใช้ targeted fixtures ทดแทน preflight หรือเวลาทดลอง ไม่เพิ่ม timeout

ขั้นถัดไป: รอเจ้าของสั่ง `review code` ของ OBS-02 ตามแผน หลัง review/fix/refactor
และ affected checks จึงเตรียม coordinator และหนึ่ง campaign ที่อนุมัติไว้
ไม่มี commit/push/CI/merge; F-17 ยังไม่ Completed
