# Reference dependency remediation — Code review

วันที่: 2026-11-06
คำสั่งเจ้าของ: `review code` หลัง Ready for Code Review
ผล: **APPROVED — code review เท่านั้น; ยังไม่ใช่ merge approval**

## ขอบเขตที่ตรวจ

ตรวจ git diff, changed/untracked spec/evidence files ทั้งหมด, template manifest/lockfile,
relevant toolchain callers/config, existing security inventory/evaluator และ application
runtime boundary เทียบ requirements/plan/validation ที่อนุมัติรวม NC-SEC-REF-01.
ตรวจ PR #48 closing evidence ที่รวมมาด้วยกับ immutable run outcomes.
ไม่มีการแก้ไฟล์ในขั้น review.

Candidate lock SHA256:
`8a8ee180aaa1ea184cbbbd8f241b0c922c9d451874366591908ee6ef9613e9ca`

## Findings และ coverage

ไม่พบ new actionable findings ระดับ Critical/High/Medium/Low จาก diff.
Lock semantic diff จำกัด 5 packages ตาม scope; versions/resolved/integrity และ
release metadata ตรง official npm registry ใน independent readback.
Requirements/plan ตรง implementation; RV-01..08 local evidence สอดคล้องกัน:
ledger template 373 occurrences/372 unique pairs, OSV inventory 426/426 รวม backend
54 supplemental, High/Critical/unknown 0, clean install/build, caller probes 10 และ
browser dev/preview desktop/mobile 20/20. Hashes ของ scanned/installed/built/browser
candidate และ repository ตรงกัน; retained commands ตรง executable probe digests.

ไม่มี changes ต่อ application source/locks, shared session storage, database/migrations,
transactions/concurrency/idempotency, money/quantity, orders/balance/position/risk,
Paper/Live isolation หรือ exchange behavior. ไม่เพิ่ม infrastructure/in-memory
persistent state และไม่ส่ง Live orders.

## ข้อจำกัดที่คงอยู่

- Medium 3 records ที่บันทึกไว้ตาม policy ไม่ใช่ new code-review findings.
- Browser block external Google Fonts; local assets/page behavior ผ่าน แต่ external
  font availability ไม่ได้รับการทดสอบ.
- Source-map indexed column-zero boundary behavior เหมือน baseline; ไม่แก้ในงานนี้.
- ไม่ reproduce Windows exploit/resource exhaustion และไม่ใช้ local แทน required CI.
- RV-09 ยัง Partial จน required CI บน final candidate ผ่าน; RV-10 Pending Full Validation
  ที่ post-merge checkpoint. ไม่ประกาศ Completed/release/Live ready.

## ขั้นถัดไป

เจ้าของตอบ `เริ่มทำ` หลังเสนอ commit/push/open PR จึงอนุญาต publication ขั้นนี้แล้ว.
รวมหลักฐานที่มีอยู่ก่อน commit, push/open PR และติดตาม required CI ของ SHA ล่าสุดจนจบ.
รายงาน SHA/run URLs ใน PR body/ข้อความปิด checkpoint; ไม่สร้างเอกสาร commit วน
เพื่อบันทึก CI ของเอกสารตัวเอง. Merge ต้องรอคำสั่งเจ้าของแยก.

## Targeted review หลัง approved CI finding — NC-SEC-REF-02

Owner อนุมัติ exact checksum exception และ scope amendment ก่อน registry change.
ตรวจ diff: เพิ่ม entry เดียวตาม approved identity, reason/evidence/approval ครบ schema,
92 entries เดิมไม่เปลี่ยน; ไม่เปลี่ยน rules/pins/workflow/thresholds. Proof เทียบ current
และ committed public source SHA256 ตรง. Existing policy contracts 35 tests (3 opt-in
skipped) ผ่าน และ full template OSV scan ผ่านภายใต้ digest ใหม่. Targeted review:
APPROVED สำหรับ approved follow-up; fresh required CI ยัง pending บน commit ใหม่.
