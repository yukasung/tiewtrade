# D20 identity replacement — 2026-11-09

Status: **Passed — aggregate campaign** on production base de3bdcb plus pinned
current harness. Owner approved one replacement with one-shot backend identity.

Preflight revision2 Passed;20owners/400baseline,600offered/admitted/completed,
0rejected;240fills/120cancels/120replays/120cycles. Measured300s and book inputs
3000/3000. Diagnostic internal-command intake, not an HTTP workload claim.
Engine processing p95/p99=95.948/128.225ms; pilot and original target passed.
Financial/global invariants and owned pool contract Passed, no worker failures.
Campaign 453.472s including preflight/fixture/measurement/verification/cleanup,
within1200s cap. Candidate/runner unchanged. Cleanup one-shot0connections/0locks
and empty backend list; separate process-exit observation also empty. Source
fixture removed normally; no owner state, Live or Git action.

Original SMOKE campaign Incomplete remains unchanged. This passing replacement
does not establish the identity/cause of its historical transient connection,
or prove recurrence impossible. No production fix, threshold exception or retry
was added. W4 follows only this aggregate campaign pass under owner approval.
