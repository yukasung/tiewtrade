# F18-R5 — ลดช่วงถือ publication fence ใน matching

สถานะ: **Approved** — เจ้าของสั่ง “ทำต่อ” หลังเสนอ R5 วันที่ 2026-10-27; อนุมัติแยกจากการลดเวลา workload

## หลักฐานและขอบเขต

W1 เดิมยัง Failed/Partial ก่อนปิดเกณฑ์วัด ส่วน diagnostic ที่ supervise producer
ครบ (`batch-supervised2-partial-diagnostic`) ยัง timeout รอ partial order เป็น FILLED
บนข้อมูล100owners/2,000ordersจริง ไม่ใช่ผลตรวจรับ ทั้ง586 transaction มี
p50 0.272485s/p95 1.031072s/max 2.085003s โดย selected order ยัง PARTIAL0.5
จึงยังพิสูจน์ throughput/latency/SLA เดิมไม่ได้ การลด runtime ไม่แก้ปัญหานี้

ปัจจุบัน `TransactionalRiskPolicy.execution_context` จับ `risk_financial_fence()`
ก่อน replay/read evidence ของ BUY และ `_apply_inputs` ถือจน transaction จบ
แม้ input บางรายการไม่มี BUY เปลี่ยนสถานะ ทำให้มีช่วงขวาง publisher ที่เสนอให้ลด
หลักฐานนี้ยังไม่พิสูจน์ว่าแก้จุดนี้แล้ว workload จะผ่าน ต้องตรวจผลจริง

## วิธีที่ขออนุมัติ

1. คง owner lock/catalog lock และ serial owner scheduling เดิม แต่ทำ bounded
   owner risk replay และ pure matching preview ก่อนจับ publication fence ได้
   preview ไม่มีผล authoritative: ห้ามใช้เป็นหลักฐานยืนยัน BUY หรือเขียนเงิน
2. หาก preview มี BUY เปลี่ยน order state หรือมี BUY fill ให้จับ publication
   fence แล้วอ่าน controls/settings/risk evidence และ drain committed frames ใหม่
   จากนั้นคำนวณ matching ซ้ำจาก state ก่อน input ด้วยเวลาปัจจุบัน จึง persist
   ผลจริงแบบ atomic รวม order/position/cash/boundary/cursor หาก final recheck
   block/unavailable ต้องไม่มี BUY effect จาก preview หลุดเข้า commit
3. Input ที่ไม่มี BUY เปลี่ยน state/fill ไม่ต้องจับ global publication fence
   เพียงเพื่องาน checkpoint ของ matching แต่ financial writer ของ SELL ยังคง
   protocol reduction เดิม หาก preview ไม่ครบหรือจำแนกไม่ได้ใช้ทาง fenced เดิม
4. New-order admission คง fully fenced; context cache ใช้ได้เฉพาะเมื่อจับ fence
   จริงแล้วใน transaction นั้น และ invalidate หลังทุก fill ตรวจ controls ต่อ input
   ไม่ cache ผล preview เป็น authorization และไม่เปิดช่องคืนข้อมูล stale

เปลี่ยนเฉพาะ lock/replay protocol นี้ ไม่เพิ่ม worker/pool/hardware ไม่เปลี่ยน
Money/Quantity, quantity/fee/PnL/loss formula, reservations, freshness หรือ SLA
เก็บทุก committed price frame รวม transient breach ไม่ coalesce/ข้าม frames
ไม่มี Live orders และ production admission ยังปิดจนผ่าน activation gates

## หลักฐานที่ต้องผ่านก่อนรับการเปลี่ยน

- Barrier tests: price breach/recovery, source unavailable, freshness expiry และ
  global admission disable ระหว่าง preview กับ final recheck ต้อง block ถูกต้อง
  ไม่มี fill/order/position/cash effect จาก preview และไม่มี transient breach หาย
- Reset/decrease/correction และ owner isolation: baseline/holdings/cursors ไม่มี
  stale authorization หรือ deadlock จาก lock order ใหม่
- No-op input ไม่มี financial change; SELL/cancel ยังลดความเสี่ยงได้ขณะข้อมูลขาด
  lost ACK/retry ไม่สร้าง duplicate order/fill/cancel/allowance use
- ตรวจ affected safety/contracts ก่อน เมื่อชุดแก้นิ่งใช้ full regression ตามผลกระทบ
  แล้วรัน W1/W2/W3 profileV2 ทีละชุดและ W4 ส่วน recovery ที่ได้รับผลกระทบ
  ใช้หลักฐานเดิมที่ยัง valid ต่อ คง Failed/Partial เดิม และไม่ลดเกณฑ์เพื่อให้ผ่าน

ผนวก protocol นี้ใน plan และปิด NC-F18-09 แล้วก่อน implementation
หากยังพิสูจน์ไม่ได้ให้คง Failed/Partial และ admission ปิดตามเดิม
