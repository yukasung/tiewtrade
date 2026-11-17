# REBUILD20-POLL-01 — review M1 fixes

สถานะ: **Scoped fix and affected validation Passed; awaiting owner refactor decision**.
2026-11-16. [Amendment](../../rebuild20-poll-evidence-plan.md) ·
[Sanitized summary](rebuild20-poll-m1-summary.json).

## Finding and fix

Review reproduced a successful permit body inside an unrelated caller except block:
trace IO failed but sys.exception mistook the handled caller error for the operation's
primary error. The permit returned instead of immediately reporting the evidence error.

ParentPollGate now captures only its own operation error/cancellation in explicit local
state. Fixture preparation does the same for seed/cleanup/summary stages; finish_mutators
accepts an explicit primary error instead of inspecting caller exception state. The
fixture worker cleanup likewise tracks only its own operation failure. A successful
operation inside an unrelated except therefore cannot swallow its own evidence failure.

The reused save_partial_result helper accepts an explicit primary argument; explicit
None means no current error. Omission retains existing active-error lookup compatibility
for other callers. Fixture progress writing passes the explicit state, preserving both
summary/cleanup failures and the original operation failure without touching an unrelated
handled error. Existing replay helper regression tests confirm the omitted-argument path.
No file IO failure becomes Passed; incomplete stream counts still fail summary checks.

## Validation

113 targeted tests Passed in32.744s, including fresh realPostgreSQL,actual20worker fixture,
fullsmallreplay/RLS/source/global/financial/pool checks, existing poll regressions and
replay lifecycle/cleanup tests. Final28 focused cases also Passed after test annotation/
exception-chain style corrections; those corrections do not change production behavior.
Five-file Ruff/format/mypy and whitespace Passed. New matrix tests normal and ambient
caller contexts against actual operation/cancellation,trace/summary/progress IO and
combined failures; error identity and unrelated-error notes checked. Direct mutator
cleanup test rejects ambient exception contamination too. Independent maintenance
connection confirmed owned test DB absent/0connections/0advisorylocks.

No production SQL/API/schema/session/risk/money/Live rule changed. Shared helper changes
are diagnostic exception handling only; tests do not send owner or Live orders. Prior
83-test evidence and REBUILD20-02 Incomplete/parentpoolFailed remain unchanged; F17 is
notCompleted. No workload/replacementfullrebuild/fourhour/Git/CI/merge in this fix scope.
Next: owner decides whether to refactor these reviewed finding fixes; do not start that
phase implicitly. A replacement campaign still requires its own explicit authorization.


## Owner-authorized refactor complete — 2026-11-16

Replaced repeated fault-group membership checks with local operation/trace/summary/
progress flags in the M1 regression matrix. Clarified explicit None versus omitted
primary error in save_partial_result's docstring. Runtime logic, exception identity/
ordering, test cases/assertions, guards and financial behavior unchanged; no new helper
abstraction. Final28 focused tests Passed; scoped five-file Ruff/format/mypy/whitespace
Passed. Prior113 realPG/process/replay safety cases retained within original scope;
no financial/workload acceptance was rerun or inferred. Impacted validation after the
refactor is complete. No replacement campaign/fullrebuild/4h/Git/CI. Next proposed step:
one explicitly approved replacement full-rebuild campaign under the existing20owner/
282cycle/96000history/60s-owner/3600s-total criteria, not automatic execution. F17 remains
notCompleted; previous Incomplete/poolFailed/provenance limitations unchanged.
