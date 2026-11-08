# Compact protection table implementation checkpoint

Date:2026-11-08 Asia/Bangkok. Owner approved protection-table-ui-plan.md.

Implemented compact current/issues and history tabs using shared Table/Tabs,
existing form and new read-only details Modal. Only CLOSED/CANCELED without
conflict are history; FAILED/unknown/conflicts stay visible. Quantity strings,
residual/unverified coverage warnings, exit state and source-unavailable messages
remain explicit; full residual/exit information is in details. Details derives
facts from current rows by id and scope, updates on refresh and closes if removed
or owner/wallet/episode/base changes. No backend, financial, session, permission,
mutation payload, revision/idempotency or API/schema changes. Existing modal form
and mutation gates retained; history rows have no mutation controls.
Shared Tabs selected button had native background; restored transparent background
per existing TabWithUnderline template. No new style system or UI dependency.

## Local checks

- ProtectionPanel10 + PaperTradePage/ManualOrderForm33 =43passed; final typecheck
  and scoped ESLint passed, including affected existing E2E selectors.
- New component proof: state partition/unknown/conflict, scope filter, residual,
  refresh/missing/scope-change details, tab keyboard and Escape/return focus,
  exact edit/cancel payloads and expected revision, mutation disabled gates,
  historical exit facts with monitoring off.
- Isolated browser: actual Vite component/theme/recovery hook, synthetic rows and
  read-only intercepted request-discovery response; no owner session. Two locales,
  widths1440/375, light/dark; no document overflow, contained table scroll,
  details visible at both widths, keyboard focus/trap/Escape/return, refreshed
  data and disappearing selection.10 scenario groups passed,0mutations.
  Screenshots and browser-result.json retained; desktop/mobile dark views inspected.
- First browser attempt could not connect to stopped owner-local5173. Retained as
  infrastructure failure, not product failure. Started isolated Vite15118 and ran
  the same UI checks successfully; no test criteria reduced. Temporary preview
  removed and isolated server stopped after proof.
- Initial new test lint had an unsafe expect.any assignment; removed unnecessary
  key matcher, retained payload/revision assertions. Final lint passed.
- Existing real-DB browser cancellation/closed selectors now select History and
  inspect Details. Those real-DB browser cases were NOT rerun: Docker unavailable.
  Do not claim new full financial E2E or required CI. Prior unchanged backend and
  owner STOP/replace/cancel proofs remain scoped to their original candidate.

## Runtime and remaining gates

Owner local5173/API8000 are not running; Docker daemon unavailable at inspection.
No containers restarted/reset, no owner-data mutation or runtime gate opening.
The last verified cleanup state had all four gates off; unavailable DB means this
checkpoint does not claim a fresh flag readback. Current source needs local service
startup before owner sees it. Keep preview artifacts distinct from real account UI.

UI implementation/checks complete within this amendment. Next owner-commanded
review of the final UI diff; no automatic review/refactor/commit/push/merge. Required
CI needs authorized Git publication; F17 Batch/Release dependencies still pending.


## Owner-requested local startup

Owner requested run project and URL after this checkpoint. Opened Docker normally
and started only existing project PostgreSQL/Redis containers; waited for recovery
and verified healthy. Started current worktree UI/API/public market-data and three
Paper workers using existing private launchers. Database unchanged; CANCELED1/FAILED1
retained, all four gates false on readback. Browser /paper/trade200 renders login,
proxy health200, served module includes new table, no page errors. No owner login
forged or order/STOP submitted. This supersedes runtime-unavailable status above
only; final UI review/required CI/Release pending. Local URL127.0.0.1:5173.
