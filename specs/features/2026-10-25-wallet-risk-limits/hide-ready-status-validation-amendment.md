# F18 — ซ่อนสถานะพร้อมในฟอร์มเพดาน — Validation Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31

## เกณฑ์ตรวจรับ

1. READY ไม่แสดง `พร้อม` / `Ready` หรือ status badge ในฟอร์มเพดาน.
2. Unavailable, stale, latched, stop, loading และ error ยังสื่อสารตามเดิม.
3. Save, Paper no-TOTP, Live TOTP, exact-key recovery และ reset behavior ไม่เปลี่ยน.
4. Targeted component tests, ESLint, TypeScript และ production build ผ่าน.
