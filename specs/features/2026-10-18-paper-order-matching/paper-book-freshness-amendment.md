# F-15 NC-F15-11 — Paper Order Book freshness

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-30 ด้วยคำสั่ง “เริ่มทำ” หลังได้รับข้อเสนอค่าที่ชัดเจน**

## หลักฐานและปัญหา

runtime จริงของ Binance TH ส่ง depth update แบบตามการเปลี่ยนแปลง ไม่ได้ส่งทุก 100ms
ตลอดเวลา แม้ WebSocket ยังเชื่อมต่ออยู่ หลักฐานวันที่ 2026-10-30 พบช่วงห่างประมาณ
1.5–7 วินาที กฎเดิมที่ปฏิเสธ book เมื่ออายุเกิน 1 วินาทีจึงทำให้ producer invalidate
และ reconnect ซ้ำด้วย `book readiness cannot be proved` จน Paper order ใช้งานจริงไม่ได้

## ข้อกำหนดที่แก้ไข

- เฉพาะ **Paper execution Order Book** เปลี่ยน freshness boundary เป็น **ไม่เกิน 30 วินาที**
  ณ จุดใช้; อายุเท่ากับ 30 วินาทียังผ่าน มากกว่า 30 วินาทีต้อง fail closed
- คง stream target 100ms, sequence/generation/lease verification, bounded buffer,
  snapshot bridge, source timestamp และ capability checks เดิมทั้งหมด
- feed disconnect, sequence gap, time reversal, malformed/conflicting identity หรือ
  provenance ที่พิสูจน์ไม่ได้ยัง invalidate ทันที ห้ามรอครบ 30 วินาที
- latest-trade readiness ของ F-10 คงเกณฑ์เดิม ไม่ใช้แทน depth และไม่เปลี่ยนกฎ Live Trading
- ยอมรับว่า Paper simulated fill อาจใช้ verified depth ที่มีอายุได้สูงสุด 30 วินาที;
  ห้ามอ้างความเที่ยงตรงเท่าตลาดจริงและห้ามนำ amendment นี้ไปเปิด Live orders

## Validation ที่ได้รับผลกระทบ

แก้ boundary tests ให้ 30 วินาทีผ่านและมากกว่า 30 วินาทีไม่ผ่าน พร้อมตรวจ disconnect,
gap/recovery, duplicate/conflicting input, market-data composition และ Paper matching
regression โดยไม่ใช้การเปิด risk gates เป็นทางลัดในการทดสอบ

## Follow-up approval

หลัง runtime จริงพบช่วงไม่มี depth update 15.4–15.8 วินาทีทั้งที่ feed ยังทำงาน เจ้าของ
ตอบ “approve” วันที่ 2026-10-30 ให้ปรับ Paper boundary จาก 10 เป็น 30 วินาที
กฎ fail-closed อื่นและ latest-trade freshness 10 วินาทียังคงเดิม
