# F08/F18 — Account dashboard visual refresh — Requirements Amendment

สถานะ: **Approved — เจ้าของสั่ง “ปรับ UI ให้สวยงาม” และอนุมัติ plan/validation วันที่ 2026-10-31**
วันที่: 2026-10-31

## ข้อกำหนด

1. หน้า `จัดการบัญชี` ต้องใช้พื้นที่ desktop อย่างสมดุลและลดพื้นที่ว่างด้านขวา โดยคง
   content width ตาม admin template.
2. ข้อมูลบัญชีเทรดอยู่การ์ดสรุปด้านบน; กระเป๋า Paper และเพดานความเสี่ยงอยู่ grid
   สองคอลัมน์บนจอกว้างและเรียงหนึ่งคอลัมน์บนจอเล็ก.
3. ลำดับชั้นตัวอักษร, spacing, border, radius, disabled state และสีต้องใช้ shared
   components/pattern จาก `references/admin-template/`.
4. ข้อมูลสำคัญ เช่น balance และเพดานขาดทุนต้องเห็นง่าย; metadata รองใช้ label ที่เบา
   และ alignment สม่ำเสมอ.
5. ห้ามเปลี่ยน API, schema, ค่าการเงิน, Paper/Live policy, reset, recovery,
   idempotency หรือ TOTP.

## Needs Clarification

ไม่มี.
