# F-10 — Distinct trades in the same millisecond

สถานะ: Approved 2026-10-30

## ปัญหาที่พิสูจน์แล้ว

localhost manual acceptance พบ `ORDER_PRICE_UNAVAILABLE` สลับซ้ำ เพราะ core เดิมถือว่า
ราคาแตกต่างกันใน `trade_time` millisecond เดียวเป็น ordering ambiguity โดยไม่ดูว่าเป็น
คนละ public trade. Raw Binance TH `BTCUSDT@trade` และ `ETHUSDT@trade` หนึ่งชุด 20 วินาที
มี 2,255 frames, 2,162 unique `(symbol, trade_id)` และไม่มี trade ID เดิมที่ราคา/เวลาขัดกัน
แต่มีหลาย trade ที่ timestamp เดียวกันตามความละเอียด millisecond.

เอกสาร Binance TH ระบุว่า `<symbol>@trade` ส่ง raw executed trades แบบ real-time,
แต่ละ trade มี Trade ID และ market trade stream ไม่ต้องทำ reconciliation หลัง reconnect:
https://www.binance.th/api-docs/en/

## การเปลี่ยนข้อกำหนดที่เสนอ

- ภายใน WebSocket connection generation เดียว public trades ที่ `trade_id` ต่างกัน
  เป็นคนละ execution แม้ `trade_time` เท่ากัน; candidate ล่าสุดใช้ลำดับ validated frames
  ที่อ่านจาก connection เดียวกัน ไม่ใช้ตัวเลข trade ID เป็น global ordering.
- `trade_id` เดิมภายในคู่/generation เดียวกันแต่ราคา เวลา หรือ identity ต่างกันยังเป็น
  protocol conflict และ fail closed.
- เวลาเดินถอยหลัง, future time, malformed identity, generation เก่า, disconnect,
  stale price และ REST/WS cross-pipe ambiguity ยังใช้กฎ fail-closed/recovery เดิม.
- เมื่อ reconnect เริ่ม generation ใหม่ ยังไม่ใช้ arrival order จากคนละ connection
  เชื่อมกัน; REST snapshot และ readiness/reconciliation guards เดิมยังบังคับ.
- ไม่เปลี่ยน freshness 10 วินาที, Money, risk gates, trading calculations, public API,
  schema หรือ Live trading.

## Validation

- core permutations: distinct IDs/same timestamp/different prices advance in frame order;
  same ID conflict remains unavailable; older/future/generation cases remain fail closed.
- adapter/supervisor: real-shaped combined frames no longer create false ambiguity;
  disconnect/restart and REST recovery retain the existing latch behavior.
- run affected F-10 core/service/adapter tests, F-15 market admission regression, ruff,
  mypy and one read-only localhost readiness observation. Agent must not submit an order.

ประมาณ 10–15 นาทีสำหรับ implementation และ targeted checks; full validation/CI แยกตาม
checkpoint เดิมและผล localhost ไม่แทน acceptance ทั้งหมด.
