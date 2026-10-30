# F18-UI — ล้าง Local Recovery ที่หมดอายุอัตโนมัติ — Requirements Amendment

สถานะ: **Approved — เจ้าของสั่ง “แก้ไขตามนี้” วันที่ 2026-10-30; plan/validation amendment อนุมัติแล้ว**
วันที่: 2026-10-30
อ้างอิง: [Hidden Recovery Status Requirements](hidden-recovery-status-requirements-amendment.md)

## เป้าหมาย

ผู้ใช้ต้องกรอกเพดานและกดบันทึกตามฟอร์มปกติ ไม่ต้องเข้าใจหรือดำเนินการกับ request,
idempotency key หรือ recovery. Backend ยังคงใช้ request protocolเดิมเพื่อความถูกต้อง.

## ข้อกำหนด

| รหัส | ข้อกำหนด |
|---|---|
| SRA-RQ-01 | เมื่อ local durable attempt lookupด้วย keyเดิมได้ `RISK_REQUEST_NOT_FOUND` และ authoritative snapshotปัจจุบันมี revision, wallet หรือ episodeต่างจาก expected scopeของ attempt ระบบต้องล้าง local attempt keyเดิมอัตโนมัติและคืน inputเป็นค่าปัจจุบัน |
| SRA-RQ-02 | การล้างทำได้เฉพาะเมื่อครบทั้ง not-found และ scope identityต่างกัน; ห้ามอนุมานจาก amountเท่ากัน, timeout, network error หรือ snapshotอย่างเดียว |
| SRA-RQ-03 | หลังล้างต้องไม่ POST attemptเก่า ไม่สร้าง keyใหม่ ไม่แสดง recovery text และไม่คง draftเก่าหรือ stale warning; ผู้ใช้แก้ inputและกด Saveใหม่ได้ตาม flowปกติ |
| SRA-RQ-04 | หาก keyมี request/authorization/terminal result หรือ scope identityยังตรง ต้องไม่ล้าง; exact-key recovery, TOTPและ APPLIED revision waitเดิมยังมีผล |
| SRA-RQ-05 | Backend request/idempotency protocolยังบังคับทุก Save. การเปลี่ยนนี้ตัดขั้นตอนทางเทคนิคออกจาก UX ไม่อนุญาต direct database writeหรือข้าม engine validation |

## เหตุผลด้านความปลอดภัย

Attempt ที่ expected scopeเก่ากว่า authoritative identityไม่สามารถ applyกับ scopeปัจจุบันได้;
หาก requestเก่าปรากฏภายหลัง engineต้อง rejectด้วย revision/scope conflictเดิม. การล้าง
เฉพาะ local journalจึงไม่เปลี่ยนค่าการเงินและไม่ถือว่า requestสำเร็จ.

## Needs Clarification

ไม่มี.
