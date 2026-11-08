# PR63 — F17 E2E empty-state correction

สถานะ: **Approved A — owner explicitly approved test correction, targeted checks, commit/push and one further CI round on 2026-11-08**
Date: 2026-11-08 Asia/Bangkok
Candidate: ab9c57a17f4c2db214840077823a06b31cb96a24

## Observed result

[Replacement CI](https://github.com/yukasung/tiewtrade/actions/runs/42461978437)
failed in frontend/e2e/protections.spec.ts:321. Six F17 cases passed; the failed
standalone-request case expected the retired standalone-panel text after reload.
F16 passed all seven cases. Security passed all jobs, including the exact six
approved exceptions. Backend result remains pending until completion.

## Concrete proposed correction

Change only the exact empty-state assertion at protections.spec.ts:321 from
`ยังไม่มี TP/SL` to `ไม่มีออเดอร์เปิดอยู่หรือ TP/SL ที่กำลังทำงานหรือมีปัญหา`,
which is protectionMessages.emptyActivity rendered by PaperTradingActivity.tsx:99
when both current order/protection collections are complete and empty.
Keep the rejected request, reload, exact balance/held/reservation/allocation,
no-SELL assertions and all production behavior unchanged. The later financial
assertions were not reached on this failed candidate and are not claimed passed.

Reuse the existing real-DB browser case. Run that one case on a fresh isolated
E2E database (about 1–3 minutes), scoped ESLint and typecheck. If these pass,
normal commit/push and one further required CI round (about 20–25 minutes), then
stop/report. No automatic rerun, scanner change, production source change, merge,
owner-account mutation or trading-rule relaxation. Preserve both failed CI runs.
This test-only correction needs no source refactor stage.

Reason for approval boundary: the latest Option A explicitly authorized one
replacement CI round, which has now produced a new F17 E2E failure. AGENTS.md
requires preserving checkpoint limits and stopping after the approved scope.
