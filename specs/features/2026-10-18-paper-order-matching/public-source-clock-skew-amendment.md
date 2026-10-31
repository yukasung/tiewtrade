# F-15 NC-F15-14 — Public execution source clock skew

สถานะ: Approved 2026-10-30

## หลักฐานและปัญหา

หลังแก้ NC-F15-11 ให้ใช้ freshness 30 วินาที runtime ยัง reconnect ซ้ำด้วย
`depth source freshness unproven` และ `trade ordering unproven`. Raw Binance TH
combined-stream diagnostic 10 วินาทีพบ depth latency BTC อยู่ระหว่าง -8.8ms ถึง 12.4ms
และ ETH ระหว่าง -9.6ms ถึง 11.4ms. ค่าติดลบหมายถึง source event timestamp นำ local
receipt clock เล็กน้อยตาม clock skew ปกติ แต่กฎเดิมปฏิเสธแม้นำเพียง 1ms.

## การเปลี่ยนข้อกำหนดที่เสนอ

- เฉพาะ public Binance TH execution depth/trade สำหรับ Paper ยอมรับ `event_at` นำ
  local `received_at` ได้ไม่เกิน **100 milliseconds**.
- มากกว่า 100ms ยัง fail closed และเริ่ม recovery; อายุย้อนหลังยังใช้ MAX_BOOK_AGE 30s,
  depth sequence/gap, generation/lease, malformed/conflicting identity และ disconnect
  checks เดิมทั้งหมด.
- trade time ต้องไม่เกิน event time และ source timestamps จริงยังถูกเก็บเป็น provenance;
  ห้าม rewrite timestamp เพื่อทำให้ผ่าน.
- การยอมรับนี้หมายถึง Paper อาจประมวลผล public event เร็วกว่านาฬิกาตลาดได้สูงสุด
  0.1s. ไม่ใช้กับ Live, risk latest-price F-10, signed requests หรือเวลาธุรกรรมการเงิน.
- ไม่เปลี่ยน public API/schema, Money/Quantity, fill formula, risk gates หรือ freshness SLA.

## Validation

- depth/trade boundaries: ahead 100ms ผ่าน, 100ms+1us fail closed; historical 30s boundary
  เดิมยังผ่านและเกิน boundary ยังล้ม.
- sequence gap, duplicate conflict, disconnect/restart, weighted-price metadata และ Paper
  matching regressions เดิมต้องผ่าน.
- runtime read-only observation ต้องเห็น BTC/ETH execution books และ prices READY ต่อเนื่อง
  โดยไม่เกิด clock-skew reconnect; agent ไม่ส่งออเดอร์.

ประมาณ 8–12 นาทีสำหรับ implementation, targeted tests, rebuild และ read-only runtime check.
