# F17 completion gaps — 2026-11-17

> Historical checkpoint preserved on 2026-11-18. Read current status in [roadmap](../../roadmap.md). This record does not authorize another diagnostic or campaign.

สถานะ: Draft decision record — current criteria retained; not approval to waive gates.
Owner requested continuing until F17 can be Completed. Read current requirements,
validation/roadmap and official advisory/upstream/registry before selecting changes.

## Current evidence

- PR76 merged d3c9eae; all required PR checks Passed on2e51d01.
- Main CI44122272269 Passed; Security44122272392Failed High picomatch4.0.7.
- Internal20 observed four-hour W3 and representative full-history rebuild Passed;
  current W4 actual dump/restore/recovery Passed. Preserve all earlier failed attempts.
- Internal20 proof does not certify original100-account Release capacity.

## Blockers and ordered completion work

1. Security: GHSA-fc5q-39xc-vjpf ReDoS, range<=4.0.7, no patched version listed.
   Registry latest4.0.7; upstream referenced PR194 is open/unmerged. package-lock marks
   picomatch dev=true and it is required by tinyglobby/Vite/Vitest. Dev classification
   alone does not prove harmlessness or justify an exception. No supported fixed
   upgrade is currently available. Investigate reachability and upstream remediation;
   do not pin an unreviewed PR, fabricate version, suppress scanner or approve own
   security exception. Existing remediation DR-1 covers certifi/Vite only; DR-2 says
   other dependency scope changes need owner approval before modification.
2. V18: reconcile retained internal20/burst/restore proof against approved integrated
   acceptance. Original100-account Release obligations remain Pending Full Validation;
   changing capacity/profile acceptance needs explicit owner approval, not repetition
   or relabeling20accounts as100. No new workload launched in this audit.
3. V19: F20/F21 bot runtime/strategy and configured notification channels must exist,
   then real fake/paper integration proves protection failure→close intent→stop and
   actual notifications. Roadmap currently Planned. UI-only Grid Close System work
   does not implement its strategy. New feature requirements/plan/validation approval
   must precede implementation; do not invent Grid Close System business rules.
4. V20: F22/F23/F24 Live adapter/idempotency/reconciliation/readiness dependencies are
   Planned; validate using fixtures/FakeVenue, never enable Live or place real orders
   merely to close this gate. NC14 owner decision also remains prerequisite to F24.
5. Final combined candidate: applicable Feature/Batch/Release criteria and Security
   must all pass, then record Completed. Opening remains separately authorized.

## Decision needed

Prepare a separate picomatch security remediation requirements proposal first, with
reachability/upstream investigation and safe reproducible fix criteria. No exception
or dependency-source change is implied. Then schedule the existing roadmap dependencies
through their own approved specs. Current label remains Pending Full Validation;
Paper verification may be reported Passed within its tested scope.

Sources checked: https://github.com/advisories/GHSA-fc5q-39xc-vjpf,
https://github.com/micromatch/picomatch/pull/194, npm registry picomatch latest.
