# ADR-0009: Workspace เป็นหน่วย Single-Writer (แทน Portfolio)

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Amends: [ADR-0002](0002-portfolio-single-writer-engine.md)
- Related: FR-PLN-04/05, FR-PLN-06, D-11, NFR-21

## Context
ADR-0002 ให้แต่ละ Portfolio มีเจ้าของได้หนึ่งราย แต่วงเงินการเทรด (Open Notional) ตาม Plan คิด**รวมทั้ง Workspace** (FR-PLN-04/05) ถ้า Portfolio ของ Workspace เดียวกันอยู่คนละ engine instance ทั้งสองตัวอาจเห็นวงเงินว่างพร้อมกันแล้วอนุมัติ Order จนรวมกันเกินวงเงิน

## Decision
- เปลี่ยนหน่วยของ lease และการประมวลผลแบบลำดับเดียวจาก **Portfolio** เป็น **Workspace**: ทุก Portfolio ของ Workspace หนึ่งอยู่ใน engine instance เดียวและประมวลผลตามลำดับใน loop เดียว
- fencing token เป็นของ Workspace; ทุก transaction ที่เขียน state ของ Portfolio ใดใน Workspace ตรวจ token ของ Workspace
- **การกันวงเงิน (reservation)** ไม่ต้องมีกลไกแยก: Risk Engine คำนวณ Projected Open Notional จาก state ปัจจุบันของทุก Portfolio ใน Workspace ซึ่งนับ Order ค้างทุกสถานะที่ยังไม่จบ (`PENDING_NEW`, `NEW`, `PARTIALLY_FILLED`) ตาม Calculation §5.2 วงเงินจึงถูก "จอง" ทันทีที่ Order ถูกบันทึก และ "คืน" อัตโนมัติเมื่อ Order ถูกปฏิเสธ, ยกเลิก, หมดอายุ หรือ fill (มูลค่าย้ายจาก Order ไปเป็น Position)
- Order ที่ Risk Engine ปฏิเสธจะไม่ถูกบันทึกเป็น Order จึงไม่กันวงเงิน
- ใช้ loop เดียวกันตรวจ Leverage และจำนวน Portfolio ตาม Plan ด้วย

## Consequences
- ไม่มี race ระหว่าง Portfolio ในการตรวจ Entitlement ระดับ Workspace
- ขยายระบบด้วยการกระจาย Workspace ไปหลาย engine ได้เหมือนเดิม
- Workspace ที่มี Portfolio มาก (สูงสุดตาม Plan) ประมวลผลในลำดับเดียว ต้องอยู่ในเป้า latency NFR-12 — ตรวจด้วย load test (NFR-16)
- ถ้าอนาคตมีระบบทีมหรือ Workspace ขนาดใหญ่มาก ต้องทบทวน
