# F-08 Amendment — Paper Trading ไม่บังคับ API key/TOTP ตอนเลือกประเภท

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-30
วันที่: 2026-10-30

Implementation plan และ validation ที่รออนุมัติ:
[paper-trading-totp-plan.md](paper-trading-totp-plan.md) และ
[paper-trading-totp-validation.md](paper-trading-totp-validation.md)

## เหตุผล

F-08 RQ-5 ปัจจุบันบังคับให้การเลือก `MANUAL` หรือ `BOT` ครั้งแรกต้องมี API key
สถานะ `ACTIVE` และ fresh TOTP แม้ว่าการเลือกประเภทเพียงอย่างเดียวยังไม่ให้สิทธิ์ส่ง
Live order หรือรันบอท ข้อกำหนดนี้ทำให้ผู้ใช้ Paper Trading ต้องตั้งค่าบัญชี Binance TH
และ 2FA ก่อนทดลองระบบ ซึ่งขัดกับขอบเขต Paper wallet ที่ตั้งใจให้ใช้งานได้โดยไม่พึ่ง
venue credential หรือ TOTP

## ข้อกำหนดที่อนุมัติ

1. แทนที่ F-08 RQ-5 ด้วยข้อความต่อไปนี้:

   > การเลือก `MANUAL` หรือ `BOT` ครั้งแรกต้องเป็นการเลือกโดยชัดแจ้งของผู้ใช้ที่
   > authenticated และผ่าน CSRF protection เก็บที่ server และ audit ใน transaction
   > เดียวกัน การเลือกไม่ต้องมี API key, TOTP, recovery grant หรือ TOTP grace และ
   > **ไม่ให้สิทธิ์เทรด Live, เพิ่ม/เปลี่ยน credential หรือรันบอทโดยตัวมันเอง**

2. Paper Trading ต้องสร้าง/ใช้ Paper wallet และเลือก `MANUAL` หรือ `BOT` ได้โดยไม่มี
   Binance API key และโดยไม่เปิดหรือกรอก TOTP ห้ามเรียก venue private API,
   อ่าน credential หรือส่ง Live order ในเส้นทางนี้

3. การเปิด manual order ที่เพิ่มความเสี่ยงยังต้องใช้ authoritative account use:
   เปิดได้เฉพาะ `MANUAL`; `BOT` และ `null` ต้องถูกปฏิเสธเหมือนเดิม การลดความเสี่ยง,
   cancel และ stop คงข้อยกเว้นเดิมตาม trading-safety

4. TOTP ยังคงบังคับตามข้อกำหนดเดิมสำหรับ:
   - เพิ่มหรือเปลี่ยน API key
   - เปิด Live Trading
   - เพิ่มเพดานความเสี่ยง
   - ปิด/เปลี่ยน 2FA และ administrative mutations ที่กำหนดไว้

   ข้อยกเว้นล่าสุด: [F-18 Paper Increase No-TOTP Requirements](../2026-10-25-wallet-risk-limits/paper-increase-no-totp-requirements-amendment.md)
   แทนรายการ “เพิ่มเพดานความเสี่ยง” เฉพาะโหมด PAPER ตั้งแต่ 2026-10-31;
   LIVE INCREASE ยังคง fresh TOTP.

5. Live Trading ต้องตรวจ API key ที่พร้อม, TOTP/2FA และ Live safety gates ของตนเอง
   ก่อน activation เสมอ ห้ามใช้การเลือกประเภทที่ทำใน Paper เป็นหลักฐานแทนด่านเหล่านี้

6. คง F-08 RQ-4/RQ-6 เรื่องไม่เลือกประเภทให้โดยปริยายและเงื่อนไขเปลี่ยนประเภท
   ไม่มีการเปลี่ยน schema, financial calculation, risk formula, order semantics หรือ
   idempotency ใน amendment นี้

## ผลกระทบที่ต้องวางแผนหลังอนุมัติ Requirements

- เอา key/TOTP precondition ออกจาก initial-use API และ route classification เฉพาะ endpoint นี้
- ปรับหน้า Trading Account ให้แสดงตัวเลือกทันที และอธิบายว่า API key/2FA จำเป็นเมื่อใช้ Live
- คง API-key setup และ Live activation เป็น step-up authentication คนละด่าน
- ตรวจ Paper no-key/no-TOTP, MANUAL/BOT/null admission, cross-user isolation, CSRF,
  atomic audit/rollback และยืนยันว่า Live/API-key routes ยังบังคับ TOTP
- ตรวจ callers ของ authoritative account use ใน manual order, risk admission และ bot boundary

## ไม่อยู่ในขอบเขต

- ไม่ยกเลิก TOTP/2FA ทั้งระบบ
- ไม่เปิด Live โดยปริยาย และไม่ส่ง Live order ในการทดสอบ
- ไม่เพิ่ม SMS, email OTP หรือ Passkey ใน amendment นี้
- ไม่เปลี่ยนกฎการเปลี่ยน `MANUAL`/`BOT` หลังเลือกแล้ว
