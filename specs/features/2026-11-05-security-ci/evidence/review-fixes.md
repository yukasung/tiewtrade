# Security CI — Review fixes

วันที่: 2026-11-05
สถานะ: แก้ findings ทั้งสองแล้ว; targeted verification ผ่าน; รอ owner refactor decision

## High — Secret exception ตาม rename

- `secrets.py`: จำกัด blame ที่ commit สร้าง path ล่าสุด โดยมอง rename เป็น delete/add.
  identity จึงไม่ย้อนข้าม rename/move และไม่คืน exception เก่าเมื่อย้ายกลับชื่อเดิม.
- `scan.py`: history scan ใช้ `--no-renames` เพื่อไม่ให้ rename ถูกยุบจน occurrence
  ใหม่หายจากประวัติเมื่อไฟล์ถูกลบภายหลัง.
- Real Gitleaks regression: original approval ไม่ครอบคลุม rename; approval ใหม่ตรง path
  ใช้ได้และยังใช้ได้หลัง unrelated commit; move-back และ subsequent deletion ยังบล็อก.
- ไม่มีการเพิ่ม exception หรือเปลี่ยน secret remediation policy.

## Medium — Invalid severity metadata ผ่านได้

- `severity.py`: ตรวจชนิด/เวอร์ชัน CVSS, required base metrics, metric values,
  duplicate/unknown fields และ optional metrics ของ v3.0/v3.1/v4.0.
- `dependencies.py`: advisory ใดมี vector ใช้ไม่ได้ ทำให้ทั้งกลุ่มเป็น Needs Triage;
  ไม่ยืมคะแนนกลุ่มที่มีจาก advisory อื่นมาปล่อยผ่าน.
- Numeric score ยังคงมาจาก OSV; ไม่มีสูตรคำนวณ CVSS ใหม่ ไม่มี dependency เพิ่ม.
- Regression ครอบคลุม malformed/type mismatch/missing/duplicate/unknown metrics,
  valid vectors และกลุ่มผสม valid/invalid ที่คะแนน 0, 3, 5, 9.
- Unsupported types/versions รวม CVSS v2 คง fail closed ต้อง triage ไม่เดาคะแนน.

อ้างอิงรูปแบบ metadata: [FIRST v3.1](https://www.first.org/cvss/v3.1/specification-document#Vector-String),
[FIRST v4.0](https://www.first.org/cvss/v4.0/specification-document#Vector-String).

## หลักฐานและสถานะ

- 28 tests ผ่าน รวม real Gitleaks/OSV probes; หลังปรับ history ให้ไม่ยุบ rename
  รันซ้ำเฉพาะ rename/deletion regression และ Gitleaks history/tree regression.
- Ruff check/format และ mypy strict ผ่าน; actionlint ใช้ผลเดิมเพราะ workflow ไม่เปลี่ยน.
- Configuration digest หลังแก้: `5514617784751b448d68c2638b63ceeb49cc9e7882d5d61cb7826707b983e9a5`.
- ผล full scanner/remote/activation ที่ยังค้างใน feature-candidate.md ยังคงค้าง.
  ไม่ใช้การปิดสอง findings นี้แทน CodeQL จริง, origin scan, required CI หรือ merge proof.
- ไม่เปลี่ยน trading/application/DB/session behavior, GitHub settings หรือ dependencies.
  ไม่มี commit/push/PR/merge.

ขั้นถัดไป: ถามเจ้าของว่าจะ `refactor the code` ต่อหรือไม่ตาม AGENTS.md และรอคำตอบ.
