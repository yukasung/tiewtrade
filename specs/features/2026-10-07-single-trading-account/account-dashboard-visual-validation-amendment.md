# F08/F18 — Account dashboard visual refresh — Validation Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31

## เกณฑ์ตรวจรับ

1. Desktop แสดง account summary เต็มแถว และ wallet/risk เป็น 7/5 columns โดยไม่เกิด
   horizontal overflow; mobile เรียง account → wallet → risk.
2. Cards, typography, spacing, fields, buttons และ states ตรง shared admin-template theme.
3. Balance, initial capital, episode, timestamps และ risk limit ยังแสดงค่าถูกต้อง.
4. Select use, wallet reset/refresh, risk Save/recovery และ disabled reasons ทำงานเดิม.
5. Keyboard focus, alerts, labels และ modal focus ไม่ถดถอยใน dark/light.
6. Targeted component tests, ESLint, TypeScript และ production build ผ่าน.
