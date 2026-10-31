# F18-UI — ซ่อนรายละเอียด Recovery จากฟอร์มเพดาน — Requirements Amendment

สถานะ: **Approved — เจ้าของตอบ “approve recovery UI amendment” วันที่ 2026-10-30; plan/validation amendment อนุมัติแล้ว**
วันที่: 2026-10-30
อ้างอิง: [Compact Risk Limit Form Requirements](compact-risk-limit-form-requirements-amendment.md)

## ทำไมต้องเปลี่ยน

ข้อความ `UNKNOWN`, request key, ปุ่มตรวจสถานะ ปุ่มส่งซ้ำ และ disclosure รายละเอียดคำขอ
ทำให้ฟอร์มตั้งเพดานดูเป็นหน้าดำเนินงานทางเทคนิค ทั้งที่ผู้ใช้ต้องการกรอกเพียง
`เพดานขาดทุน (USDT)` และกด `บันทึก`. กลไก durable recovery ยังคงจำเป็นเพื่อป้องกัน
การเปลี่ยนเพดานซ้ำหรือสร้าง key ใหม่เมื่อผลคำขอเดิมยังไม่แน่นอน.

## ข้อกำหนด

| รหัส | ข้อกำหนด |
|---|---|
| RUI-RQ-01 | หน้าเพดานต้องคงฟอร์มหลักเพียง input `เพดานขาดทุน (USDT)` และปุ่ม `บันทึก`; ห้ามแสดงคำว่า UNKNOWN, request key, state ของ inbox/engine, ปุ่มตรวจสถานะ, ปุ่มส่งซ้ำ หรือ disclosure รายละเอียดคำขอบนหน้าหลัก |
| RUI-RQ-02 | เมื่อมี durable attempt เดิม ระบบต้อง lookup สถานะด้วย owner/mode/intent/key เดิมเบื้องหลังและห้ามสร้าง key หรือ intent ใหม่จน attempt เดิม terminal |
| RUI-RQ-03 | ระหว่าง lookup หรือ request pending ให้คง input/Save ไว้ แต่ปิดการแก้ไขและบันทึก พร้อมข้อความผู้ใช้สั้นเพียง `กำลังตรวจสอบคำขอก่อนหน้า…`; ห้ามแสดงศัพท์ protocol หรือ technical identifier |
| RUI-RQ-04 | ถ้า lookup ยืนยันว่าไม่มีผล terminal ปุ่ม `บันทึก` ต้องใช้สำหรับส่ง **intent เดิมด้วย key เดิม** เท่านั้น; input ต้องแสดงและล็อก amount เดิมเพื่อไม่ทำให้ผู้ใช้เข้าใจว่าเป็นคำขอใหม่. SET/DECREASE ส่งซ้ำตาม contract เดิม; INCREASE ขอ TOTP ปัจจุบันตาม policy เดิม เว้นแต่ server ยืนยัน `AUTHORIZATION_ONLY` ซึ่งส่ง intent เดิมต่อได้โดยไม่ขอรหัสใหม่ |
| RUI-RQ-05 | เมื่อ attempt เดิม APPLIED/REJECTED แล้วจึง sync authoritative snapshot และคืน input/Save ให้สร้างคำขอใหม่. APPLIED ยังต้องรอ matching snapshot revision; REJECTED ต้องไม่แก้ค่าบนหน้าจอแบบ optimistic |
| RUI-RQ-06 | Storage failure, scope/revision conflict หรือคำขอที่ไม่สามารถกู้คืนอย่างปลอดภัยต้องปิด Save และแสดงข้อความสั้นที่ผู้ใช้ทำตามได้; ห้ามล้าง journal หรือถือว่าสำเร็จจาก snapshot amount เพียงอย่างเดียว |
| RUI-RQ-07 | การซ่อน UI ห้ามเปลี่ยน durable journal, receipt matching, idempotency, TOTP, polling, server API, schema, Money, latch/reset หรือ stop processing และห้ามส่ง Live order |

## การแทนข้อกำหนดเดิม

RUI-RQ-01..07 แทนเฉพาะการแสดงและ interaction ของ `UNKNOWN`, pending และ recovery
ใน UI-RQ-08/UI-RQ-10 ของ compact form amendment. ข้อกำหนดด้าน exact-key recovery,
no duplicate, TOTP, owner/mode/episode isolation และ trading safety เดิมยังมีผลทั้งหมด.

## Acceptance ระดับ requirements

- ผู้ใช้เห็น input และ Save เป็น interaction หลัก แม้มีคำขอเดิมที่กำลังกู้คืน.
- ผู้ใช้ไม่ต้องอ่าน UNKNOWN, UUID หรือ state machine ภายใน.
- การกด Save ขณะกู้คืนไม่สามารถสร้าง intent/key ใหม่หรือเปลี่ยน amount ของคำขอเดิม.
- หลังผลเดิม terminal เท่านั้นจึงตั้งค่าใหม่ได้.

## Needs Clarification

ไม่มีข้อที่บล็อก requirements. รายละเอียด state ของ Save, TOTP และข้อความ error จะกำหนด
ใน plan/validation amendment.
