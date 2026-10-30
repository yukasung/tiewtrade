# F18-UI — ฟอร์มเพดานขาดทุนแบบสั้น — Validation Amendment

สถานะ: **Approved — เจ้าของตอบ “approve plan and validation amendment” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements Amendment](compact-risk-limit-form-requirements-amendment.md),
[Plan Amendment](compact-risk-limit-form-plan-amendment.md)

## 1. “เสร็จ” หมายถึง

| รหัส | เกณฑ์ | ตรวจอย่างไร |
|---|---|---|
| UI-V-01 | UI-RQ-01/07: formสั้น | Ready renderมี status, inputค่าปัจจุบันและปุ่มบันทึกเพียง actionเดียว; ไม่มี summary/calculation/more-actions/technical IDs |
| UI-V-02 | UI-RQ-02/03: validation/action | unset→SET, lower→DECREASE, higher→INCREASE; unchanged/blank/zero/negative/invalid/exponent/comma/scale>18/range≥1E20 disabledและไม่สร้าง key/POST |
| UI-V-03 | UI-RQ-03: exact comparison | `1`, `1.0`, leading/trailing zerosเท่ากัน; smallest unit, 18 decimals และ max-below-boundaryผ่าน; เปรียบเทียบด้วย bigintโดยไม่มี floating point |
| UI-V-04 | UI-RQ-04: TOTP | INCREASEเปิด modalหลัง Save; cancelไม่สร้าง journal/POST; confirmส่ง codeใน headerครั้งเดียวและ body/journal/cacheไม่มี code; SET/DECREASEไม่มี TOTP |
| UI-V-05 | UI-RQ-05/06: authority/concurrency | pollingไม่ทับ dirty draft; revision/wallet/episode changeทำ staleและบล็อก submit; APPLIEDรอ matching snapshotก่อน sync; REJECTEDไม่ optimistic |
| UI-V-06 | UI-RQ-08/10: recovery | pendingปิด form; reload/UNKNOWN/check/retry/AUTHORIZATION_ONLYใช้ intent+keyเดิม; no duplicate request; technical detailsแสดงเฉพาะ uncertain/problem state |
| UI-V-07 | UI-RQ-09: latch/reset | resetไม่มีใน Ready; latchedแสดง warning+reset, modal warningเดิม, no TOTP; increaseไม่ล้าง latch; stop failureยังเข้าถึง per-order evidence |
| UI-V-08 | UI-RQ-11/12: accessibility/scope | Enter submit, focus trap/return, aria descriptions, keyboard; ไทย/อังกฤษ, mobile/desktop, light/dark; Paper/Live query/journalไม่ปะปนและไม่ส่ง Live order |

## 2. Tests ที่ต้องแก้หรือเพิ่ม

### Pure amount helper

- valid: `0.000000000000000001`, `1`, `001.2300`, `.5`, `+5`,
  `99999999999999999999.999999999999999999`.
- invalid: blank/space-only, zero/negative, alphabetic, comma, exponent, NaN/Infinity,
  nonzero decimalเกิน18 และ `100000000000000000000`.
- equality/order: equivalent textได้ coefficientเดียว; ตัวเลขยาวเปรียบเทียบถูกโดยไม่ผ่าน
  JS Number.

### Component

- Ready/unset form shapeและ disabled reasons.
- SET/DECREASE direct submitกับ payload/action/keyที่ถูกต้อง.
- INCREASE modal/TOTP header/cleanup/focusและ frozen amount.
- Dirty polling, stale identity, `ใช้ค่าล่าสุด`, revision/scope rejection.
- APPLIED/REJECTED/pending/UNKNOWN/AUTHORIZATION_ONLY/storage failureและ reload journal.
- unavailable/pause/latch/stop problem/reset/RiskStopEffects contextual visibility.
- mode/language/render responsive assertionsที่ componentรองรับ.

### Callers/E2E

- `TradingAccountPanel` ยังแสดง cardตำแหน่งเดิมและไม่สร้าง panelซ้ำ.
- Account/sessionเปลี่ยน ownerล้าง scopeเดิม ไม่ใช้ draft/recoveryข้ามผู้ใช้.
- Playwright risk-limit flowปรับ selectorเป็น input+Save; ตรวจ keyboardและ mobileหนึ่งชุด,
  ไม่ส่ง Live order.

## 3. Commands และลำดับตรวจ

หลัง implementationนิ่ง แจ้งเวลาโดยประมาณก่อนเริ่ม แล้วรันตามลำดับ:

1. `npm test -- --run tests/RiskLimitPanel.test.tsx tests/TradingAccountPanel.test.tsx tests/AccountSession.test.tsx` พร้อม pure helper test.
2. Tests ของ callers/recoveryที่ diffกระทบ และ `npm run test:e2e:risk-limits` เมื่อ local
   browser fixtureพร้อม; หาก fixtureไม่พร้อมให้บันทึก Pending ไม่แทนด้วย unit test.
3. `npm run lint`, `npm run typecheck`, `npm run build`.
4. ตรวจ browser desktop/mobile, light/dark, ไทย/อังกฤษและ keyboardจาก candidateสุดท้าย.

ไม่รัน backend tests, W1–W4 หรือ full trading workloadเพราะ API/schema/business logic
ไม่เปลี่ยน. หาก implementationแตะ shared client/recoveryนอกแผน ให้ประเมินผลกระทบใหม่
และขยาย testsตาม testing §7.

## 4. หลักฐานและจุดหยุด

- บันทึก command/result/timeและภาพ Ready, INCREASE TOTP, latched reset และ mobile
  ใน checkpointเดิม; ไม่สร้าง acceptance reportซ้ำ.
- Critical failureคือ actionผิด, TOTPรั่ว/ถูกข้าม, duplicate key/request, draftข้าม owner,
  optimistic value หรือ resetหายเมื่อ latched; ต้องแก้ก่อน browser acceptance.
- Required CI ที่ไม่มีหลักฐานคง Pending. ผล UIนี้ไม่เปลี่ยนสถานะ Paper validation,
  F-18 Completed หรือ Live activation.

## 5. หลักฐานเดิมที่ยังใช้ได้

Backend Money/risk domain, API mutation, durable worker, W1–W4 และ financial safety
ไม่ได้เปลี่ยน จึงใช้หลักฐานเดิมต่อ. Component/browser evidenceของ `RiskLimitPanel` เดิม
หมดอายุและต้องตรวจใหม่เฉพาะรายการ UI-V-01..08.
