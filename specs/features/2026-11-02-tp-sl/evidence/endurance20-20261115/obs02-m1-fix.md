# OBS-02 — M1 fix checkpoint

สถานะ: M1 fixed / affected validation Passed; รอ owner refactor

ใช้ profile_internal.guard_database เดิมก่อนสร้าง engine ใน fixture_statement
ทั้ง cold/reused และ known-blocker ไม่เปิด transaction ก่อนตรวจ local isolated target
และความตรงกันของ endpoints ทุก role ไม่มี production/SQL/timeout change

เพิ่ม 12 negative cases: missing URL, remote host, nonisolated database,
role database/port/host mismatch × idle/blocked; engine และ session factories ต้องไม่ถูกเรียก
47 targeted tests Passed รวม 35 tests เดิมและ real PostgreSQL readonly/blocker/rollback/
lock-release proof ใช้เวลา21.7898sรวม setup/cleanup ไม่มี test failure
Ruff/format/mypyสองไฟล์และ whitespace Passed
Independent cleanup: database absent,0connections,0locks
[Summary](obs02-m1-fix-summary.json)
Raw: validation-artifacts/f17-obs02-m1-tests-20261116/

หลักฐาน observer regression 48 cases เดิมยังใช้ได้สำหรับส่วนที่ไม่เปลี่ยน
ไม่ถือว่าเป็นการรันใหม่ทั้งหมด ไม่รัน preflight/diagnostic campaign/4h หรือ Git/CI
OBS-01 Incomplete และ F17 Pending คงเดิม
ขั้นถัดไป: รอคำสั่ง refactor the code ตาม AGENTS ก่อนดำเนิน affected validation
และเตรียม coordinator/หนึ่ง campaign ที่อนุมัติไว้
