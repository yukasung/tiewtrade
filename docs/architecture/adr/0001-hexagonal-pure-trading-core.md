# ADR-0001: Trading Core แบบ Hexagonal และ Pure Python

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Related: P-03, P-04, P-07, NFR-03, FR-STR-13, NFR-15

## Context
Paper และ Live ต้องใช้ Trading Core ร่วมกัน (P-03) การคำนวณต้อง deterministic (P-07) และต้อง replay ได้หลังระบบล่ม (NFR-15) Trading Core ต้องไม่ผูกกับ FastAPI (NFR-03)

## Decision
- `tiewtrade_core` เป็น pure Python: ไม่มี I/O, ไม่อ่านนาฬิกาเอง (เวลามากับ event), ใช้ Decimal
- ติดต่อโลกภายนอกผ่าน port เช่น `ExecutionAdapter`; adapter จริงอยู่นอก core
- `PaperExecutionAdapter` อยู่ใน core เพราะเป็นการคำนวณล้วน
- บังคับ dependency rule ด้วย import-linter ใน CI

## Consequences
- ทดสอบ core ได้เร็วโดยไม่ต้องมี database หรือ Binance; ผลเหมือนเดิมทุกครั้ง
- ต้องออกแบบ event ให้มีข้อมูลเวลาและข้อมูลที่ต้องใช้ครบ
- services ต้องทำหน้าที่ประกอบ (wiring) เอง
