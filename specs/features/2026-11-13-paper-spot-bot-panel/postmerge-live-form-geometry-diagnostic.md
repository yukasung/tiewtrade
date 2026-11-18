# Post-merge Live form geometry diagnostic

> Historical checkpoint preserved on 2026-11-18. Read current status in [roadmap](../../roadmap.md). This record does not authorize another diagnostic or campaign.

สถานะ: **Approved — เจ้าของสั่งเริ่ม และอนุญาต diagnostic ทดแทนหนึ่งครั้ง วันที่ 2026-11-14**
วันที่: 2026-11-14 Asia/Bangkok

PR69 merged as5a3002a. CI43554376408: main browser35 Passed/1Failed at
frontend/e2e/top-navigation.spec.ts:507, dense workspace case. Live form bottom
alignment differs8px, criterion<=1px. Later catalog/manual/protection/risk browser
stages skipped. Backend main/isolated stages Passed; frontend/API/Docker and
Security43554376419 Passed. No rerun or source change performed.

The test reads bar/form/workspace boundingBox separately immediately after resize
through1024/1440/2553px. Log lacks failed width and individual rectangles; cannot
establish a persistent layout defect or measurement timing race. Do not widen
1px tolerance, add sleeps, change timeout or call the failure harmless.

## Bounded proposal

Run only the failed dense-workspace case once on merge SHA using a fresh isolated
fixture database with retain-on-failure trace. Keep production, test assertions,
viewport sizes and timeout unchanged. Use existing screenshots/error context and
trace to inspect the failed phase and layout; no owner/Live trading commands.
Check cleanup and report Passed/Failed/Incomplete against that SHA, retaining the
original Failed CI. Stop/report even if it passes; no automatic CI rerun, source
fix, commit/push or follow-up PR in this diagnostic scope. Estimate5–10minutes.


## Diagnostic attempt — 2026-11-14

Owner instructed publication of the delegation rules followed by the pending
layout diagnosis. One diagnostic attempt on5a3002a: Incomplete. The private
runner placed its temporary config inside Playwright test-results; output cleanup
removed it before the worker could import it. This does not reproduce or clear
the original8px layout failure. Log /tmp/live-geometry-browser.log. Fresh database
and dedicated Redis were cleaned; zero DB connections before drop. Owner runtime
untouched. No production/assertion/timeout changes.

Prepared config outside output cleanup; not rerun. The proposal limits this
campaign to one attempt and stop/report even on pass. Standing engineering
delegation explicitly preserves such plan stop points; a replacement attempt
requires owner direction. No diagnostic fix commit, PR or CI rerun.


## Owner-authorized replacement result — 2026-11-14

Owner selected A for exactly one replacement attempt after the config-cleanup
Incomplete. Merge SHA5a3002ae037027d233999e13febf0853d66413b0, detached worktree;
production and test assertions/timeouts unchanged. Private config outside output
changes only isolated ports/baseURL/origins and retain-on-failure tracing.

Result:1 Passed(14.3s). Exact dense workspace case, same1024/1440/2553 viewport
sequence and1px tolerance. No8px failure reproduced. Trace retention was configured
for failures; because this attempt passed, no failure trace was retained. Do not
claim trace proves the CI failure cause or that CI is fixed. Original CI failures
on5a3002a andfa2c8d1 remain Failed. Original diagnostic remains Incomplete.

Private replacement log:/tmp/live-geometry-replacement.log. First log retained as
/tmp/live-geometry-first-incomplete.log and first artifacts copied to
/tmp/live-geometry-first-incomplete-artifacts. Replacement screenshots/report in
the detached worktree frontend/test-results. Isolated database and dedicated
Redis removed; zero connections before database drop. Owner runtime untouched.

Stop/report reached. No source fix, commit/push, CI rerun or acceptance change.
Recommended next proposal: failure-only width and single-read bar/form/workspace
rectangles plus resize timing, retaining existing assertions/timeout, to identify
which viewport and layout state produce8px in CI. Not implemented or executed.
