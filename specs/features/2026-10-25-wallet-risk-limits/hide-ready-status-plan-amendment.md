# F18 — ซ่อนสถานะพร้อมในฟอร์มเพดาน — Plan Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements](hide-ready-status-requirements-amendment.md)

## Implementation

- ปรับ `RiskLimitPanel` ไม่ render status badge เมื่อ `data.reason === "READY"`.
- คง badge/alerts สำหรับทุกสถานะที่ต้องแจ้งผู้ใช้ รวมถึง latched และ unavailable.
- ไม่เปลี่ยน component, API หรือ business logic อื่น.

## Verification

- Component test ยืนยัน READY ไม่มีคำว่า `พร้อม` และไม่มี status badge.
- Regression ยืนยัน unavailable/latched/error alerts ยังแสดง.
- รัน RiskLimitPanel targeted test, frontend lint, typecheck และ build.

ประมาณเวลา **5–10 นาที**.
