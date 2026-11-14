# Refactor checkpoint — 2026-11-13

สถานะ: targeted validation Passed; required CI Pending. เจ้าของสั่ง refactor โดยตรง.

## Scope

- PaperBotPanel: จัด JSX และ balance rendering ให้อ่านง่าย โดยใช้ components เดิม.
- PaperTradePage: ตั้งชื่อ availableQuote expression และแก้ comment ของ draft scope.
- ManualOrderForm: setter ชื่อตรงกับ selectedSide.
- e2e/helpers/paperOrders.ts: postFixtureBuy ใช้ payload เดิมร่วมกันใน manual-orders/protections ลดโค้ดซ้ำ.
- ไม่เปลี่ยน behavior/business rules หรือ persistent state.

## Verification

- Frontend ESLint: Passed.
- Frontend typecheck: Passed.
- Vitest: 6 files / 80 tests Passed (4.28s): PaperBotPanel, PaperTradePage, ManualOrderForm, useManualAttempt, PaperTradingActivity, KillSwitchControls.
- Real-DB browser: 3 tests Passed — MARKET BUY/SELL + LIMIT partial/cancel; bracket fill/reload/replace/cancel; partial bracket trigger. ใช้ isolated fixture databases ไม่ส่งคำสั่งเจ้าของหรือ Live.
- git diff --check: Passed.
- Private logs: frontend/test-results/bot-runtime/refactor-checks.log, refactor-manual.log, refactor-protections.log.
- หลักฐานเดิม build/UI matrix/recovery/risk ใช้ต่อสำหรับส่วนที่ refactor นี้ไม่กระทบ; ไม่รัน full suite/workload/CI.

ผล Failed/Incomplete เดิมยังอยู่ใน checkpoint เดิม ไม่ถูกแทนที่. V10/required CI และ owner visual acceptance ยัง pending; F-20/F-21 ไม่ Completed. ไม่ commit/push/merge.
