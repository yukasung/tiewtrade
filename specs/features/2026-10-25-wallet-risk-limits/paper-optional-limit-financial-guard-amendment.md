# F-18 R35 — Unconfigured Paper Financial Boundary Amendment

สถานะ: **Approved — เจ้าของอนุมัติ R35 วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements](paper-optional-limit-requirements-amendment.md),
[Plan](paper-optional-limit-plan-amendment.md),
[Validation](paper-optional-limit-validation-amendment.md) — Approved 2026-10-31

## หลักฐานที่พบหลัง implementation

Production-composition test ผ่าน request → command → order แต่ fill ถูก PostgreSQL
ปฏิเสธด้วย `SQLSTATE TT028`. ต้นเหตุคือ migration `0052_risk_unconfigured_writer.py`
มี guard ที่ปฏิเสธ Paper BUY ทันทีเมื่อไม่มี `risk_limit_settings` ตามกฎเก่า
ก่อนจะตรวจ financial boundary. ดังนั้นการแก application code อย่างเดียวไม่สามารถ
ทำให้ requirement ใหม่ใช้งานจริงได้

## การเปลี่ยนแปลง

- เพิ่ม migration `0060` แทน function `risk_require_financial_boundary()` โดยลบเฉพาะ
  การปฏิเสธ BUY เพราะ unset.
- Unconfigured financial writes ยังต้องถือ publication shared lock, ใช้ `F18_V1`,
  มี owner/wallet/episode boundary claim ที่ตรง transaction และ finalize boundary ก่อน commit
  เหมือน configured writer; ไม่กลับไปใช้ behavior ก่อ migration 0052 ที่ bypass fence.
- Capital-only wallet lifecycle exemption เดิมคงเดิม; configured-limit path ไม่เปลี่ยน.
- Downgrade คืน guard 0052 ได้เฉพาะเมื่อ protocol ปิดและไม่มี unconfigured BUY/economic history
  ที่กฎเก่ารองรับไม่ได้; ถ้ามีให้หยุดโดยไม่ลบ/แก้ข้อมูล.
- ไม่เพิ่ม table/column/index, public API หรือสิทธิ DB; เป็นการแก trigger contract
  ที่จำเป็นต่อ requirement ที่อนุมัติแล้ว.

## การตรวจ

1. Real-DB unconfigured request → command → order → fill ผ่านภายใต้ boundary
   และไม่สร้าง setting/evaluation/baseline.
2. Legacy/unfenced writer ยังได้ `TT028`; wrong owner/wallet/episode, unfinalized claim
   และ publication lock ที่ไม่ถูกต้องยังปฏิเสธ.
3. Configured setting/latch/source/price และ cash/position/idempotency regression เดิมผ่าน.
4. Migration up/down/up บนฐานว่างผ่าน; downgrade หยุดเมื่อมี unconfigured
   economic history; roles/grants ไม่เปลี่ยน.

## เวลา

เพิ่มจากแผนเดิมประมาณ **15–25 นาที** หาก migration และ safety tests ผ่านครั้งแรก.
