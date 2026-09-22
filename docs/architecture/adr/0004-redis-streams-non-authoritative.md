# ADR-0004: Redis Streams สำหรับ Command/Event และ Redis ไม่ใช่ Source of Truth

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Related: NFR-20, NFR-22, NFR-23, FR-STR-17

## Context
process ต้องสื่อสารกันโดยไม่เรียกกันตรง (NFR-20) ทั้ง command ที่ต้องส่งถึงแน่นอน และราคาที่ต้องกระจายเร็วแต่หายได้

## Decision
- **Redis Streams + consumer group** สำหรับ command และ event ที่ต้องประมวลผล (`cmd.*`, `exec.*`, `evt.*`)
- **Redis Pub/Sub** สำหรับราคาแบบรวบและ event ไปหน้าจอ ซึ่งหายได้
- ข้อมูลใน Redis ต้องสร้างใหม่ได้จาก Postgres หรือส่งซ้ำได้ด้วย id; ห้ามเป็นที่เก็บข้อมูลหลัก

## Consequences
- ใช้ Redis ตัวเดียวทั้ง cache, bus และ rate limit ลดจำนวน component บน VM
- ย้ายไป Memorystore ได้โดยไม่เปลี่ยน design
- ถ้าอนาคตต้องการ bus ที่ทนทานกว่า (เช่น Pub/Sub ของ GCP) ต้องเปลี่ยน adapter ใน `fasttrade_infra`
