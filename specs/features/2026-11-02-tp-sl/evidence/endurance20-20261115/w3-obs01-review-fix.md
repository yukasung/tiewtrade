# NC-F17-W3-OBS-01 — แก้ review findings M1/M2

สถานะ: **แก้ findings และ targeted checks ผ่าน — รอคำสั่ง refactor**
วันที่: 2026-11-16 (Asia/Bangkok)
อนุมัติ: เจ้าของสั่ง `แก้ไข`; ขอบเขตบันทึกก่อนแก้ใน [แผน §9](../../observed-w3-fail-fast-plan.md)

- **M1:** boundary หลัง worker startup ใช้ `with_publisher` เดิมก่อนเริ่ม baseline
  เฉพาะ opt-in จึงรักษา completed publisher error/CancelledError identity ก่อน signal
  โดยไม่ยกเลิกกลาง spawn ไม่เพิ่ม SQL หรือย้าย publisher task
- **M2:** finalizers พยายามเขียน failure receipt และ lease summary แยกกัน แม้ตัวแรกล้ม
  รักษา primary/first evidence error พร้อมชนิด secondary error และสถานะ Failed/Incomplete
  Default ที่ไม่เปิด flag ยังคง ordering และ fail-on-first-error เดิม

เพิ่ม regression 8 กรณี: publisher error/cancellation พร้อม signal ระหว่าง startup
และยืนยันไม่เริ่ม baseline/rebuild; receipt/summary failure แยก/พร้อมกัน โดยมี/ไม่มี
primary พร้อมตรวจ exception identity และเนื้อหาไฟล์ที่ยังเขียนได้จริง

## ผลตรวจ

- Local units/supervision/parent/default: **100 Passed** (ยกเว้น real-PG case)
- Impacted observer/lease/fence/clock/transaction regression: **134 Passed** รวม real PG
  rollback/lock release/connection return และ ambiguous commit, elapsed รวม setup/cleanup 22.3003s
- สองชุดมี 47 cases ซ้ำ รวม **187 distinct cases** ไม่บวกเป็น 234 cases
- Ruff/format/mypy เฉพาะสามไฟล์ที่แก้ และ `git diff --check`: Passed
- Normal owned test DB cleanup และ independent admin check: DB absent/0 connections/0 locks

ดู [summary/fingerprints](w3-obs01-review-fix-summary.json) และ raw logs/helper/result ที่
`validation-artifacts/f17-obs01-review-fix-tests-20261116/` runner:
`/tmp/tiewtrade-f17-obs01-review-fix-tests.py` ใช้ helper จาก hash เดิมที่ตรวจแล้ว

คงหลักฐานเดิม 434 Passed ตาม candidate เดิม และ Failed/Incomplete ประวัติเดิม
ใช้ผลเก่าต่อเฉพาะ behavior/dependency ที่ไม่กระทบ ไม่ได้รัน full suite/offline rebuild/
W3 4h/CI หรือ commit/push/merge ไม่มี production/เงิน/risk/lease/guard/retry change
F-17 ยังไม่ Completed

ขั้นถัดไป: รอเจ้าของสั่ง `refactor the code` ตาม AGENTS.md จากนั้นตรวจ affected validation
ก่อนหนึ่ง observed W3 ตามแผน ไม่เริ่ม refactor หรือรอบยาวเองจากคำสั่งแก้ findings
