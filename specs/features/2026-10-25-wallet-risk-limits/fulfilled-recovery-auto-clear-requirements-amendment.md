# F18-UI — ล้าง Recovery เมื่อค่าปัจจุบันตรงคำขอเดิม — Requirements Amendment

สถานะ: **Approved — เจ้าของตอบ “approve fulfilled recovery auto-clear” วันที่ 2026-10-30; plan/validation amendment อนุมัติแล้ว**
วันที่: 2026-10-30
อ้างอิง: [Stale Recovery Auto-clear Requirements](stale-recovery-auto-clear-requirements-amendment.md)

## ข้อกำหนด

| รหัส | ข้อกำหนด |
|---|---|
| FRA-RQ-01 | เมื่อ exact-key lookupได้ `RISK_REQUEST_NOT_FOUND` และ attemptเป็น SET/DECREASE/INCREASE ซึ่ง canonical amountเท่ากับ authoritative snapshot amount ระบบต้องล้าง local attemptและปลดล็อก formอัตโนมัติ แม้ scope identityยังตรง |
| FRA-RQ-02 | ต้องเปรียบเทียบ amountด้วย exact parser/coefficientเดิม ไม่ใช้ Number/floatและไม่เปรียบเทียบ raw textเพียงอย่างเดียว |
| FRA-RQ-03 | การล้างต้องไม่ POST, ไม่สร้าง UUID, ไม่เปลี่ยน authoritative amountและไม่ถือว่า requestเคย APPLIED; เป็นเพียงการยืนยันว่า desired stateมีอยู่แล้ว |
| FRA-RQ-04 | RESET, amountต่างกัน, invalid amount, network/storage error หรือ serverพบ authorization/request/result ห้ามใช้กฎนี้และคง recoveryเดิม |

ข้อกำหนดนี้เพิ่ม safe auto-clear predicateให้ SRA-RQ-01 โดยไม่เปลี่ยน backend request,
idempotency, TOTP, revision/scope validationหรือ financial rules.

## Needs Clarification

ไม่มี.
