# F18-UI — ล้าง Recovery เมื่อค่าปัจจุบันตรงคำขอเดิม — Validation Amendment

สถานะ: **Approved — เจ้าของตอบ “approve fulfilled recovery plan and validation” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](fulfilled-recovery-auto-clear-requirements-amendment.md),
[Plan](fulfilled-recovery-auto-clear-plan-amendment.md)

## เกณฑ์ตรวจรับ

1. NOT_FOUND + `500.0` attempt + authoritative `500` ล้าง exact local keyและปลดล็อก.
2. ไม่ POST, ไม่เรียก UUIDและไม่เปลี่ยน snapshot/draftแบบ optimistic.
3. Amountต่างกัน, RESET, invalid amount, identityตรงและ errorอื่นไม่ถูกล้าง.
4. Stale-identity, exact-key retry, TOTP, pending/terminalและ owner/mode isolationเดิมผ่าน.
5. Targeted tests, lint, typecheck, build, diff checkและ served localhost sourceผ่าน.

Browser/E2E limitationเดิมคง Pending.
