# ADR-001 — Public market ingestion demand

สถานะ: **Approved** — เป็นการบันทึกการตัดสินที่เจ้าของอนุมัติใน plan F-09 วันที่2026-10-07

ที่มา: [requirements RQ-12/13/16](../features/2026-10-07-market-data/requirements.md)
และ [plan PostgreSQL/Sessions/grants](../features/2026-10-07-market-data/plan.md)

API และ market-data ติดต่อผ่าน PostgreSQL โดยใช้ market_candle_demand หนึ่งแถวต่อ series
เพื่อรวมคำขอและเก็บ cursor, lease, retry และ refresh watermarks ให้ทำต่อหลัง restart ได้
metadata นี้ควบคุม ingestion ของข้อมูลตลาดสาธารณะ ไม่เก็บ user_id/email/key/secret

API อ่าน observations และเขียนได้เฉพาะ request columns ของ demand;
market-data ควบคุม ingestion metadata และเขียน observations โดยไม่มีสิทธิ์ข้อมูลผู้ใช้/secret/audit/ออเดอร์
ไม่มี runtime role เป็นเจ้าของตารางหรือมี DDL; migration ใช้ migrator และ runtime role assertions แยกชนิด session
สองตารางนี้ไม่มี RLS เพราะไม่มีข้อมูลผู้ใช้; ตารางผู้ใช้ยังใช้ RLS ตามมาตรฐานเดิม

นี่เป็นข้อยกเว้นจำกัดของคำว่า "ตารางราคาและแท่งเทียน" ใน database §5
ไม่อนุญาต market-data เขียนตารางงานทั่วไปหรือสถานะการเทรด
ทิศทางการพึ่งพาเดิมคงอยู่และตรวจด้วย import-linter; infra ไม่พึ่ง venues และ services ไม่ import กันเอง
