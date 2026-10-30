# F18-UI — ล้าง Recovery เมื่อค่าปัจจุบันตรงคำขอเดิม — Plan Amendment

สถานะ: **Approved — เจ้าของตอบ “approve fulfilled recovery plan and validation” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](fulfilled-recovery-auto-clear-requirements-amendment.md) **Approved 2026-10-30**

## แผน

- ขยาย predicate auto-clearใน `RiskLimitPanel` จาก identity mismatch เป็น
  `identity mismatch OR exact canonical amount equality` เฉพาะ non-RESET.
- ใช้ `parseRiskLimitAmount` กับ snapshotและ attempt amount แล้วเทียบ bigint coefficient.
- ใช้ `discard` exact-keyเดิมและ sync authoritative draftเหมือน stale-scope path.
- เพิ่ม testsสำหรับ equivalent text (`500.0`/`500`), amountต่างกัน, RESETและ invalid amount.
- รัน targeted shared recovery/caller/session tests, lint, typecheck, build, diff check
  และ rebuild frontend container.

ประมาณเวลา **10–20 นาที**. ไม่เปลี่ยน backend/API/schemaและไม่รัน W1–W4.

## Needs Clarification

ไม่มี.
