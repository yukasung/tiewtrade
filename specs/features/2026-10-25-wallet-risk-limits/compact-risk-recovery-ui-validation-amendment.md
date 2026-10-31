# F18-UI — ซ่อนรายละเอียด Recovery จากฟอร์มเพดาน — Validation Amendment

สถานะ: **Approved — เจ้าของตอบ “pprove recovery plan and validation amendment” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](compact-risk-recovery-ui-requirements-amendment.md),
[Plan](compact-risk-recovery-ui-plan-amendment.md)

## 1. เกณฑ์ตรวจรับ

| รหัส | เกณฑ์ |
|---|---|
| RUI-V-01 | Ready/unsetปกติมี input+Saveตาม compact formเดิม; ไม่มี UNKNOWN, key, check/retry buttonหรือ request disclosure |
| RUI-V-02 | Reloadพร้อม journalแสดง amountเดิมใน inputที่ล็อก; lookup/pendingปิด Saveและมีข้อความสั้นเดียว ไม่มี technical state |
| RUI-V-03 | Unknown retryจาก Saveส่ง exact intent/payload/keyเดิมหนึ่งครั้ง; ไม่เรียก UUIDและไม่ส่ง draft/snapshot amountแทน |
| RUI-V-04 | SET/DECREASE retryไม่มี TOTP; unknown INCREASEเปิด TOTP modal; AUTHORIZATION_ONLY retry keyเดิมโดยไม่ขอ codeใหม่; codeไม่เข้า body/journal/cache |
| RUI-V-05 | APPLIEDรอ matching snapshot revisionก่อนคืน form; REJECTEDไม่ optimistic; conflict/storage/mismatchปิด Saveและไม่ล้าง journal |
| RUI-V-06 | polling/reload/double click/owner-mode-episode changeไม่สร้าง duplicateหรือข้าม scope; Paper/Liveไม่ปะปนและไม่ส่ง Live order |
| RUI-V-07 | keyboard/focus, disabled reason, ไทย/อังกฤษ, mobile/desktop และ light/darkยังใช้งานได้ |

## 2. ชุดตรวจ

1. รัน pure amount, `RiskLimitPanel`, `TradingAccountPanel` และ account/session recovery tests.
2. เพิ่ม assertions ว่า technical recovery copy/UUIDไม่อยู่ใน DOMทุก recovery state.
3. ตรวจ exact same-key retry, double-submit gate, TOTP header/cleanup, APPLIED/REJECTED,
   storage failureและ scope isolation.
4. รัน frontend lint, typecheckและ build.
5. รัน Playwright risk flowและ browser desktop/mobileเมื่อ isolated fixture/browserพร้อม;
   หากไม่พร้อมให้คง Pending ไม่ใช้ unit testsแทน.

## 3. จุดหยุดและหลักฐาน

- Critical: keyใหม่, payloadใหม่, duplicate POST, INCREASEข้าม TOTP, journalถูกล้างก่อน
  terminal หรือแสดง authoritative valueแบบ optimistic.
- บันทึกผลใน checkpointเดิม. Backend/W1–W4 evidenceยัง validเพราะไม่มี dependencyเปลี่ยน.
- required CI/browserที่ไม่มีหลักฐานคง Pendingและไม่เปลี่ยนสถานะ F-18 Completed.
