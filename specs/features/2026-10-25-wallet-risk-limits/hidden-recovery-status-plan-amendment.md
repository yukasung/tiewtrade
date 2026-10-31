# F18-UI — ซ่อนข้อความ Recovery Status — Plan Amendment

สถานะ: **Approved — เจ้าของตอบ “approve hidden status plan and validation” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](hidden-recovery-status-requirements-amendment.md) **Approved 2026-10-30**

## แผน

- เปลี่ยน recovery status element ใน `RiskLimitPanel` จากข้อความ visible เป็น `sr-only`.
- คง id, `role=status` และ `aria-describedby` ของ input/Save เพื่อ screen reader.
- ไม่แก้ recovery state machine, retry handler, journal, TOTP หรือ API.
- ปรับ component tests ให้ยืนยันว่า copy ไม่อยู่ใน visible content แต่ accessible
  descriptionและ disabled/enabled stateยังถูกต้อง.
- รัน targeted RiskLimitPanel/caller/session tests, lint, typecheckและ build.
- Rebuildเฉพาะ frontend containerและตรวจ sourceที่ localhostส่งจริง.

ประมาณเวลา **10–15 นาที**. ไม่รัน backend workloadหรือ W1–W4.

## Needs Clarification

ไม่มี.
