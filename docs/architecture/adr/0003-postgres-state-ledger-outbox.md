# ADR-0003: Postgres State + Append-only Ledger + Transactional Outbox

- Status: **Accepted** (2026-09-22)
- Amended by: [ADR-0011](0011-durable-command-lifecycle.md) (published ≠ processed, inbox)
- Date: 2026-09-22
- Related: FR-PF-06, FR-ACC-11, NFR-09, NFR-20, NFR-22

## Context
ต้องมี audit trail ของเงินครบถ้วน (FR-PF-06), Analytics ต้องแยกเงินเข้า/ออกจากกำไร (FR-ACC-11) และ event ที่ส่งไป process อื่นต้องไม่หายหรือไม่ตรงกับ database

## Decision
- เก็บ **state ปัจจุบัน** ในตาราง (balances, positions, orders) และ **ledger แบบ append-only** ของทุกการเคลื่อนไหวของเงิน
- เขียน state, ledger และ **outbox** ใน transaction เดียว แล้ว relay outbox ไป Redis
- ไม่ใช้ full event sourcing

## Consequences
- อ่าน state ปัจจุบันง่ายและเร็ว; ledger ใช้ตรวจสอบและคำนวณ Analytics
- Event ไม่หายแม้ Redis ล่ม (relay ส่งซ้ำได้ ผู้รับต้อง idempotent)
- ต้องมี property test ว่า ledger รวมแล้วตรงกับ state เสมอ
