# F-15 NC-F15-12 — Combined-stream receive order for Paper

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-30**

## หลักฐานและปัญหา

Binance TH runtime จริงไม่ตรงกับสมมติฐานเดิมที่บังคับลำดับร่วมระหว่าง depth และ trade:
พบ trade ID กระโดด, trade ID เดิมที่ economic payload เหมือนเดิมแต่ `event_at` ต่าง,
depth event เก่า/ซ้ำที่ payload ต่าง และ trade/depth มาถึงไม่เรียงตาม source event time
เอกสารตลาดรับรอง continuity ของ diff-depth ด้วย `U/u` และระบุ trade ID ว่า unique
แต่ไม่ได้รับรอง trade IDs ว่าต้องต่อกันทีละหนึ่งหรือรับรอง chronological ordering
ข้าม stream ใน combined WebSocket

## ข้อกำหนดที่แก้ไข

- Paper ใช้ลำดับที่รับจาก combined WebSocket เป็น durable merged input order;
  source/trade/event timestamps ยังคงเก็บเป็น provenance และห้ามอยู่ในอนาคต
- Diff-depth คง algorithm ของตลาด: event ที่ `u` ไม่เกิน cursor ปัจจุบันเป็น stale/duplicate
  และไม่ transition; event ใหม่ต้องมี `U = previous u + 1` ไม่เช่นนั้น invalidate/rebase
- Trade ID เป็น dedupe identity และไม่บังคับ monotonic เพราะ venue ส่ง ID ย้อนลำดับได้;
  เก็บ economic identities แบบ bounded 4,096 รายการต่อ generation
- Trade ID ซ้ำที่ symbol, trade time, side, price และ quantity เหมือนเดิมเป็น duplicate
  และไม่ transition แม้ event/receipt time ต่าง; economic identity ใดต่างต้อง fail closed
- ไม่ใช้ receive order อ้างความเที่ยงตรงเท่าตลาดจริง Resting LIMIT Paper อาจได้ผลต่าง
  เมื่อ depth/trade มาถึงสลับ source time; กฎนี้ใช้เฉพาะ Paper และห้ามใช้เปิด Live
- คง generation/lease, book freshness NC-F15-11, bounded buffer, capability, financial,
  idempotency และ disconnect/malformed/future-time failure rules เดิมทั้งหมด

## Validation ที่ได้รับผลกระทบ

เพิ่ม tests สำหรับ non-contiguous/non-monotonic trade IDs, economic duplicate ที่ event time
ต่าง, conflicting economic duplicate, stale depth ตาม `u`, depth gap, receive-order replay
และ runtime recovery โดยยังต้องพิสูจน์ว่าไม่มี duplicate fill/economic effect

## Follow-up approval

หลัง runtime พบ `trade identity time reversal` จาก Binance TH จริง เจ้าของตอบ “approve”
วันที่ 2026-10-30 ต่อข้อเสนอให้ Trade ID ใช้ bounded dedupe โดยไม่บังคับ monotonic
ข้อกำหนดด้าน economic conflict, receive order และ fail-closed อื่นยังคงเดิม
