# F18 — เพิ่มเพดาน Paper โดยไม่ใช้ TOTP — Requirements Amendment

สถานะ: **Approved — เจ้าของสั่ง “แก้ไข” วันที่ 2026-10-31; plan/validation amendment อนุมัติแล้ว**
วันที่: 2026-10-31

## เหตุผล

Paper Trading ใช้เงินจำลองและไม่ส่งคำสั่งไป exchange. การบังคับ TOTP ทุกครั้งที่เพิ่ม
เพดานทำให้ฟอร์มตั้งค่าที่ควรกรอกแล้วบันทึกได้ทันทีมีขั้นตอนเกินจำเป็น. Live Trading
ยังมีผลต่อเงินจริงและต้องคง step-up authentication เดิม.

## ข้อกำหนด

| รหัส | ข้อกำหนด |
|---|---|
| PIT-RQ-01 | การเพิ่มเพดานในโหมด PAPER ต้องไม่ขอ ตรวจ consume หรือรับ TOTP/recovery grant; ผู้ใช้ authenticated+CSRF กรอกค่าแล้วกดบันทึกได้เหมือน SET/DECREASE |
| PIT-RQ-02 | การเพิ่มเพดานในโหมด LIVE ยังคงต้อง fresh TOTP, ไม่รับ recovery code/grant และ authorizationต้องผูก exact owner/mode/action/key/revision/amount/scope/fingerprintเหมือนเดิม |
| PIT-RQ-03 | PAPER INCREASE ยังต้องผ่าน idempotency key, expected revision, wallet/episode scope, amount>current, engine inbox/worker, auditและ APPLIED authoritative snapshotเดิม; APIห้ามเขียน settingโดยตรง |
| PIT-RQ-04 | Databaseต้องอนุญาต authorization_id=nullเฉพาะ PAPER INCREASE. LIVE INCREASEต้องมี matching authorization; SET/DECREASE/RESETทั้งสองโหมดต้องไม่มี authorizationเหมือนเดิม |
| PIT-RQ-05 | Frontend PAPERต้องส่ง INCREASEตรงโดยไม่เปิด TOTP modalหรือส่ง header. LIVEยังเปิด modalและส่ง codeใน headerชั่วคราวเท่านั้น |
| PIT-RQ-06 | Durable recoveryของ PAPER INCREASE retry exact intent/keyเดิมโดยไม่ขอ code; LIVE AUTHORIZATION_ONLY/unknown recoveryคง policyเดิม ไม่มี duplicate requestหรือ optimistic value |
| PIT-RQ-07 | ไม่เปลี่ยนสูตร loss, Money, latch/reset, risk gates, order admission, Paper/Live isolationหรือเปิด Live execution |

## การแทนข้อกำหนดเดิม

- PIT-RQ-01..07 แทน F-18 RQ-08 และ UI-RQ-04 เฉพาะ **PAPER INCREASE**.
- แทน bullet “เพิ่มเพดานความเสี่ยง” ใน F-08 Paper TOTP amendment เฉพาะโหมด PAPER;
  LIVE INCREASE และการเพิ่ม/เปลี่ยน API key, Live activation, 2FA/admin mutationsยังคง TOTP.
- Endpointและ OpenAPI request/response shapeเดิม; เปลี่ยน authentication behaviorตาม mode.

## Needs Clarification

ไม่มี.
