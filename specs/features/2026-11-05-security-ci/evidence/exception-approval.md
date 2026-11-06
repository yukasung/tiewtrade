# Security CI — Owner exception approval

วันที่: 2026-11-05
สถานะ: **Approved — owner replied `approve`**

คำถามที่เจ้าของอนุมัติระบุ exact proposal 92 identities: 70 false positives และ 22
ข้อมูลทดสอบ/พัฒนา พร้อมคำยืนยันว่าคีย์ทดสอบไม่ได้ใช้ในระบบจริง และอนุญาตให้เริ่ม
จัดทำ requirements สำหรับ dependency remediation แยกงาน.

อ้างอิงรายการที่อนุมัติ: proposed-secret-exceptions.json และ secret-triage.md.
ไฟล์ proposal เป็น historical snapshot จึงยังคง approval=null ตามขณะเสนอ;
เอกสารนี้บันทึกคำตัดสินที่ตามมาและ registry อ้างเอกสารนี้เป็น approval evidence.

ใช้กับ 92 identities ที่ระบุเท่านั้น ไม่ใช่การยกเว้น rule/path/value ทั้งหมด;
rename/new occurrence/content changes ยังต้องตรวจและบล็อกตาม policy.
ไม่มีรายการ revoked และไม่ได้ rotate/revoke/test credentials.

คำอนุมัตินี้ไม่ใช่คำสั่ง commit/push/PR/merge และไม่ใช่การอนุมัติ implementation
ของ dependency remediation ซึ่งยังต้องผ่าน requirements และ plan/validation ของงานนั้น.

## ตรวจหลังนำเข้า registry

อ่าน registry ผ่าน schema validator: 92 exact identities. สแกนซ้ำ snapshot origin refs
เดิมครบ 246 commits: excepted=92, blocked=0, needs_triage=0, unmatched approvals=0.
ผลนี้ยืนยันเฉพาะ local snapshot/base tree ไม่ใช่ final candidate หรือ GitHub CI.
หลักฐานและ configuration digest ล่าสุด: [approved-secret-scan.json](approved-secret-scan.json).
Unit/contract suite: 25 passed, 3 optional scanner probes skipped; origin scan จริงรันแยก
ตามหลักฐานนี้. Regression scanner probes เดิมยัง valid เพราะไม่ได้เปลี่ยน detector/helper.
ยังคง dependency blockers, CodeQL/remote/activation และ post-merge validation ที่ค้าง.
