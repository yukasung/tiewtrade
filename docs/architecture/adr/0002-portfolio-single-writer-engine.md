# ADR-0002: Portfolio เป็น Single-Writer ใน Engine (Lease + Fencing Token)

- Status: **Accepted** (2026-09-22)
- Amended by: [ADR-0009](0009-workspace-single-writer.md) (หน่วย single-writer เป็น Workspace), [ADR-0010](0010-execution-dispatch-fencing.md) (fencing ของการส่งไป Binance)
- Date: 2026-09-22
- Related: P-02, P-05, D-02, NFR-19, NFR-21, NFR-24

## Context
ทุก Order ต้องผ่าน Risk Engine และ Order Manager (P-02) และ margin คำนวณระดับ Portfolio (P-05) ถ้ามีหลาย process แก้ Portfolio เดียวกันพร้อมกัน จะเกิด race และ Order ซ้ำ ระบบต้องขยายเป็นหลายเครื่องได้ (NFR-21) และต้องใช้กับ Cloud SQL + connection pooling ได้ (NFR-24)

## Decision
- ทุกการเปลี่ยน state ของ Portfolio ทำโดย engine ที่เป็นเจ้าของ Portfolio นั้นเท่านั้น; api และ jobs ส่ง command
- ภายใน engine ประมวลผล event ของ Portfolio เดียวตามลำดับ
- ความเป็นเจ้าของใช้ lease ในตาราง Postgres (owner, expires_at, fencing_token) และทุกการเขียนตรวจ fencing token
- ไม่ใช้ Postgres advisory lock เพราะใช้กับ connection pooling แบบ transaction ไม่ได้
- ใช้กลไก lease เดียวกันกับ market-data leader ต่อ Venue และ execution ต่อบัญชี Binance

## Consequences
- ไม่มี race ภายใน Portfolio และขยาย engine เป็นหลาย instance ได้
- Manual Order มี hop ผ่าน Redis เพิ่ม (ระดับมิลลิวินาที)
- ต้องจัดการการย้ายเจ้าของเมื่อ lease หมดอายุ (recovery ตาม NFR-14 / NFR-15)
