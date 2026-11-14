# PR70 post-merge catalog viewport check

สถานะ: **Approved — เจ้าของเลือก A วันที่ 2026-11-14: test, targeted checks และ follow-up PR/CI หนึ่งรอบ**
วันที่: 2026-11-14 Asia/Bangkok

## หลักฐาน

PR70 merged ตามคำสั่งเจ้าของเป็น 67b02ff8ade51193c0233ddb38932526a394d42f.
Pre-merge dd4a793 CI/Security Passed. Post-merge CI43547966651: main browser35
Passed; catalog1 Passed/1Failed at supported-symbols.spec.ts:92. Later manual,
protection and risk browser steps skipped. Security43547966598 Passed.

At viewport375px, document scrollWidth382px. Failure-only bounds show desktop
account-primary/account-nav still rendered to right382px. The test measures
immediately after setViewportSize, without waiting for responsive navigation.
AccountHeader uses a matchMedia listener to update React state; CSS responds to
viewport directly. This supports a resize/measurement race hypothesis, but does
not prove stable mobile layout is correct. Do not dismiss as harmless flakiness.

## Proposed bounded follow-up

1. Separate follow-up branch from merge SHA; preserve other worktrees/runtime.
2. Reuse the existing expected-breakpoint visibility pattern in
   frontend/e2e/helpers/ui.ts (navigationLink/captureUi) before catalog geometry
   measurement. Keep375/768/1440 widths,120s test limit, strict scrollWidth<=width,
   overflow evidence and all catalog/TOTP/API/database assertions unchanged.
   No fixed sleep, production CSS/source change or wider acceptance tolerance.
3. Run both supported-symbol catalog browser tests once against a fresh isolated
   fixture database, with trace on failure; check targeted lint/typecheck.
   Do not use owner or Live account. If it fails, stop and inspect evidence.
4. If targeted checks pass, commit/push and open a follow-up PR; monitor one
   required CI candidate. Do not merge automatically or rerun after failure.

Estimated time: targeted browser/setup5–10min plus required CI20–25min.
No backend workload or Security rerun on the old merge SHA. Existing failure
remains Failed; follow-up evidence is tied to its own candidate.


## Implementation and targeted checkpoint

Shared waitForNavigationBreakpoint in frontend/e2e/helpers/ui.ts extracts the
existing trigger-visibility assertion; captureUi/navigationLink reuse it and
catalog invokes it immediately after resize, before measuring. No fixed sleep,
changed timeout, tolerance, production code or catalog assertions.

Targeted catalog E2E2 Passed(43.2s), scoped ESLint and frontend TypeScript Passed,
git diff --check Passed. Fresh tiewtrade_e2e_catalogviewport20261114 database
bootstrapped/migrated; zero remaining connections before drop. Dedicated Redis
container removed. Owner runtime untouched. Private log:
/tmp/catalog-viewport-browser.log; screenshots /tmp/catalog-viewport-screenshots.
Tracked historical screenshots restored; no screenshot baseline changes.

Required CI remains pending on the follow-up candidate. PR70 merge CI failure
remains Failed; backend result tracked separately. Owner approved publication
and one candidate, but not automatic merge or rerun after failure.
