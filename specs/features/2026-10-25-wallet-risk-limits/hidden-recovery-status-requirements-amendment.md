# F18-UI — ซ่อนข้อความ Recovery Status — Requirements Amendment

สถานะ: **Approved — เจ้าของตอบ “approve hidden recovery status amendment” วันที่ 2026-10-30; plan/validation amendment อนุมัติแล้ว**
วันที่: 2026-10-30
อ้างอิง: [Compact Risk Recovery UI Requirements](compact-risk-recovery-ui-requirements-amendment.md)

## ข้อกำหนด

| รหัส | ข้อกำหนด |
|---|---|
| HRS-RQ-01 | หน้าหลักต้องไม่แสดงข้อความ `กำลังตรวจสอบคำขอก่อนหน้า…`, `คำขอก่อนหน้ายังไม่เสร็จ…` หรือ recovery/protocol status อื่น ผู้ใช้เห็นเพียง input เพดานและปุ่มบันทึกในส่วน form |
| HRS-RQ-02 | ระหว่าง lookup/pending inputและSaveยังต้อง disabled; เมื่อ exact-key retryพร้อม Saveจึง enabled โดยไม่สร้าง intent/keyใหม่ |
| HRS-RQ-03 | เหตุ disabled/recovery stateต้องยังสื่อให้ assistive technology ผ่านข้อความ `sr-only`, `role=status` และ `aria-describedby`; ห้ามลด keyboard/accessibility เพื่อซ่อนข้อความ |
| HRS-RQ-04 | ไม่เปลี่ยน durable journal, lookup, exact-key retry, TOTP, APPLIED revision wait, idempotency, API/schema/Money/latch/reset หรือ Live safety |

HRS-RQ-01..04 แทนเฉพาะข้อกำหนด **ข้อความที่มองเห็นได้** ใน RUI-RQ-03 และ
compact recovery plan. พฤติกรรม recovery และ safety เดิมยังมีผลทั้งหมด.

## Needs Clarification

ไม่มี.
