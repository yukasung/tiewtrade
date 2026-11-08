# F-17 manual-acceptance remediation — implementation checkpoint

Date:2026-11-08 Asia/Bangkok. Requirements A and revised plan/validation approved
by owner. Local implementation/checks complete; owner code review, authorized
refactor, current-candidate remote CI and owner manual replacement remain pending.

Base:`e6b32bbd0a5203db2609dacb0de86986dce691d6` (main including PR62).
Branch:`fix/f17-manual-acceptance`, separate worktree `TiewTrade-f17-manual-fix`.
Original recovery/root/3m worktree edits were preserved. No commit/push/PR/deploy.
Runtime/test/contract bytes are pinned in [source-manifest.json](source-manifest.json).

## Changes

- Shared pure `executable_protection_quantity` reuses `align_quantity` and existing
  order filters. It validates a floor-aligned portion without changing allocation,
  acquired/disposed quantities, fee, wallet, positions or historical executions.
- Setup and pre-trigger sizing use the same calculation and current verified
  market metadata. Durable exit identity/quantity is retained after queueing.
  Late-entry work consumes only its own aligned portion; unsellable late remainder
  is retained while the entry can still fill and becomes truthful terminal residual.
  Prior terminal-exit remainder is never recycled into a new MARKET order.
- API adds string executable_quantity and nullable step_residual_quantity. Coverage
  is bounded to validated executable quantity, zero for conflict/unready/other
  states. Missing market metadata does not label an unknown quantity as step dust.
  UI uses existing MarketValue/Alert/template components for the residual warning.
- STOP survives storage getter/getItem/setItem failure using an owner/mode-bound
  component attempt-key hint. Durable business state remains PostgreSQL. Cleanup
  failure cannot turn a known receipt into unknown; retries retain their key.
  Remount recovers server status without automatic request submission.
- Prepared a separate private local launcher pointing at this candidate, with
  explicit stop authority for API only. It was NOT started. Compatibility/actual
  deployment readiness and the approved activation sequence still gate manual use.

## Local evidence

| Scope | Actual outcome |
|---|---|
| Core protection |66passed; exact0.00131868→0.00131/residual0.00000868, aligned/18digit cases, minimum and existing lifecycle/property/Paper-Live fixtures |
| Real-DB protection |54distinct selected cases have passing applicable evidence: original50 passed in first suite; four added setup/metadata/late-race cases passed in affected rechecks. Current collection54/70,16 isolated-migration cases deselected as intended; these are not claimed as rerun |
| New DB sizing/correction |Coarse step before ARMING and after ARMED; exact exit0.99, remaining0.009, exact cash9997.91199; queued quantity retained during a later step change; no additional exit on replay; correction accounting remains exact |
| Late entry races |Both fill-first/cancel-first coarse-step cases passed, with exact remaining0.018/0.009 and cash10015.82398/10007.91199 respectively; original race cases passed in first suite |
| Actual API/auth/isolation |13passed in protection_routes + kill_switch_routes; default-off503, opt-in receipt, exact retry and scope/auth contracts |
| Stop worker fresh DB |3passed with explicit fresh_global_state selection: immediate fence/completion, audit rollback+restart, snapshot-gated resume |
| Frontend components/journals |Four-suite scoped run45passed; later changed control/page pair37passed on final UI. These selections overlap and are NOT summed. Includes storage property/get/set/remove failure, same-key retry, known receipt cleanup, remount/server status and residual display |
| Browser |7distinct protection scenarios have passing applicable evidence: first run5passed/2failed; affected2 then passed25.2s. New residual case passed again on final Alert UI6.0s (10.1s total) |
| Static/contracts |Affected Ruff/format8files and mypy8files passed; import-linter7contracts kept; frontend typecheck and scoped ESLint passed; OpenAPI and TypeScript generated from current schema |

No full workload/endurance or current-head remote CI was run. Older unaffected
safety/workload evidence is reused within its original scope only.

### Initial failures retained

The first integration selection had50passed/1failed: the newly parameterized API
assertion still expected exit0.999 instead of0.99. Actual cash/residual/exit effects
had already passed. Expected quantity was updated for the approved coarse-step
case, preserving default-case assertions; affected setup/metadata cases passed.

First browser run5passed/2failed: one expected two0BTC labels before the new residual
field; the other allowed its recorded5s book lease to expire between creating two
groups. The test now counts the explicit residual and refreshes the existing source
fixture before each group. No production freshness/deadline/financial assertion was
weakened. Only failed cases were repeated, and both passed.

Initial expanded mypy found test comparison/variable-type issues; assertions now
use supported Quantity comparison and distinct market/user session variables.
Final affected8file check passed. A first stop-test invocation selected no tests
because of the existing fresh_global_state marker; it is not a pass. The three
required cases subsequently ran with that marker explicitly on a fresh database.

## Operational boundary / cleanup

Three dedicated databases created for this task were dropped after verifying zero
active connections: unit/integration, browser, and isolated stop tests. No owner DB,
container or volume was reset/deleted; no Redis flush. Temporary dependency links
were removed and the shared venv editable package restored to the recovery worktree.
Only public dev fixtures were used; no automated Live orders or venue credentials.

Owner local DB remains schema0066 with publication/financial/admission/protection
all off; existing positions and FAILED protection history were not changed. The
private candidate launcher is preparation only, not evidence of active STOP readiness
in the owner's current API process. Original manual acceptance remains Failed.

UI artifact: [net-fee residual](ui/paper-net-fee-residual.png). Synthetic fixture
allocation0.999, covered0.99, residual0.009; this is not the owner's account.

## Next checkpoint

Owner `review code` for the implemented fix. Follow finding/refactor/validation
gates in AGENTS.md and the approved amendment. Git publication and required CI need
their existing authorization; owner manual replacement follows the approved
post-review checkpoint. MF-12/13 remain pending; MF-14 full Release/dependencies
are unchanged. Do not call F17 Completed or reopen local Paper from this receipt.

### Review and finding fix — 2026-11-08

Owner review identified one High STOP-key lifecycle finding. Owner authorized the
fix; [exact changes/checks](stop-review-fix.md) resolve it locally. The earlier next
step to request review is superseded: now wait for the owner-authorized refactor
gate, then affected validation. The pre-fix source identity is retained separately;
the current manifest includes the client by-key helper and updated recovery tests.
No remote CI or owner manual replacement has occurred.
