# F18-UI — ล้าง Local Recovery ที่หมดอายุอัตโนมัติ — Validation Amendment

สถานะ: **Approved — เจ้าของตอบ “approve stale recovery plan and validation” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](stale-recovery-auto-clear-requirements-amendment.md),
[Plan](stale-recovery-auto-clear-plan-amendment.md)

## เกณฑ์ตรวจรับ

1. `NOT_FOUND + identity mismatch` ล้างเฉพาะ exact local key, sync snapshotและเปิดแก้ไข.
2. ไม่มี POST, UUID, optimistic amountหรือ cross-owner/mode journal effectระหว่าง auto-clear.
3. Identityตรงหรือ errorชนิดอื่นไม่ล้างและยัง fail closed/exact-key retry.
4. AUTHORIZATION_ONLY/pending/terminal/TOTP/APPLIED revision behaviorเดิมผ่าน regression.
5. Targeted component/shared-caller/session tests, lint, typecheck, buildและ diff checkผ่าน.
6. Local frontend containerส่ง candidateใหม่; browser/E2Eที่ fixtureไม่พร้อมคง Pending.

Critical failureคือการล้าง attemptที่ยังอาจ applyกับ identityปัจจุบัน, สร้าง keyใหม่,
ส่ง attemptเก่าระหว่าง clear หรือปลดล็อกข้าม owner/mode.
