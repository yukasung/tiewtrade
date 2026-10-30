# F18-UI — ซ่อนข้อความ Recovery Status — Validation Amendment

สถานะ: **Approved — เจ้าของตอบ “approve hidden status plan and validation” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](hidden-recovery-status-requirements-amendment.md),
[Plan](hidden-recovery-status-plan-amendment.md)

## เกณฑ์ตรวจรับ

1. Pendingและretry-readyไม่มี recovery copyที่มองเห็นได้; formมีเพียง input+Save.
2. Pendingปิด input/Save; retry-readyล็อก inputและเปิด Save.
3. Input/Saveอ้าง `aria-describedby` ไปยัง `sr-only role=status` ที่ถูกต้อง.
4. Exact intent/key retry, no-new-UUID, INCREASE TOTP, AUTHORIZATION_ONLY,
   APPLIED/REJECTEDและ owner/mode isolation testsยังผ่าน.
5. Targeted tests, lint, typecheck, buildและ diff checkผ่าน.

Browser/E2E ที่ fixtureไม่พร้อมคง Pending; ไม่ใช้ unit testsแทน.
