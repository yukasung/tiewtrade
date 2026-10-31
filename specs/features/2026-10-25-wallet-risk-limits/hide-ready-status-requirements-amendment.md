# F18 — ซ่อนสถานะพร้อมในฟอร์มเพดาน — Requirements Amendment

สถานะ: **Approved — เจ้าของสั่ง “ลบคำว่าพร้อมออก” และอนุมัติ plan/validation วันที่ 2026-10-31**
วันที่: 2026-10-31

## ข้อกำหนด

1. เมื่อ risk snapshot มีสถานะ `READY` ฟอร์มเพดานขาดทุนต้องไม่แสดง badge หรือคำว่า
   `พร้อม` / `Ready`.
2. สถานะไม่พร้อม, stale, latched, stop, loading และ error ยังต้องแสดงข้อความหรือ alert
   ที่จำเป็นตามเดิม.
3. การซ่อนข้อความต้องไม่เปลี่ยน API, risk state, polling, recovery, idempotency,
   TOTP, latch/reset หรือกฎการเงิน.

## Needs Clarification

ไม่มี.
