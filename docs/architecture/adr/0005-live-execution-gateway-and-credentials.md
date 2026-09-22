# ADR-0005: Live Execution Gateway แยก Process และเข้ารหัส API Secret แบบ Sealed Box

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Related: P-04, P-10, FR-SEC-01..12, D-04, NFR-25

## Context
API Secret ต้องถอดรหัสได้เฉพาะ component ที่ส่ง Order และ api / frontend ห้ามเห็น (FR-SEC-02) ขณะที่ engine รัน Strategy และรับ event จำนวนมาก

## Decision
- สร้าง process `execution` เป็นที่เดียวที่ถอดรหัส Secret, ส่ง Order, เปิด User Data Stream และตรวจ Key ตอนเชื่อม
- Browser เข้ารหัส Secret ด้วย **public key ของ execution (sealed box)** api และ Postgres เก็บแค่ ciphertext
- Private key: VM ใช้ไฟล์ที่ mount เข้า container execution เท่านั้น; GCP ใช้ Cloud KMS asymmetric key ที่ให้สิทธิ์ decrypt เฉพาะ service account ของ execution (เปลี่ยนด้วย config)
- engine ใช้ `BinanceExecutionAdapter` ที่ส่ง command ไป execution ผ่าน Redis

## Consequences
- ช่องโหว่ใน api หรือ engine เข้าถึง Secret ไม่ได้
- เพิ่ม hop ระดับมิลลิวินาทีต่อ Order (ยังอยู่ในเป้า NFR-12)
- ต้องจัดการ rotation ของ key pair และการเข้ารหัสใหม่
