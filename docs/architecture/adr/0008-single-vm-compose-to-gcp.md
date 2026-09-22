# ADR-0008: Docker Compose บน VM เดียว และแผนย้ายไป GCP

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Related: NFR-01, NFR-02, NFR-16, NFR-17, NFR-19..25, R-18

## Decision
- ช่วงทดลอง: docker compose บน VM เดียว (4 vCPU / 16 GB) รวม proxy, api, engine, market-data, jobs, notifier, postgres, redis (+ execution ใน Phase 2); backup Postgres ออกนอก VM ทุกวัน
- Production: api → Cloud Run, jobs → Cloud Scheduler + Cloud Run Jobs, Postgres → Cloud SQL, Redis → Memorystore, key → Cloud KMS, egress → Cloud NAT
- Process ที่ต้องทำงานตลอด (engine, market-data, execution, notifier): เลือกระหว่าง Cloud Run แบบ always-on, worker pools หรือ GKE Autopilot ตอนย้าย
- ย้ายเมื่อถึงเกณฑ์ NFR-17

## Consequences
- ต้นทุนช่วงทดลองต่ำ; ออกแบบตาม NFR-19..25 ทำให้ย้ายได้โดยไม่เขียนใหม่
- VM เดียวเป็นจุดเสียจุดเดียว (R-10) ยอมรับได้ตามเป้า availability 99% (NFR-13)
