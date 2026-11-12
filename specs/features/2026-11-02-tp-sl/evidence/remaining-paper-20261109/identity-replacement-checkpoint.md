# F-17 — approved D20 identity replacement and conditional W4

Date:2026-11-09 Asia/Bangkok. Status: **Approved scope complete — Passed**.
Owner approved [this bounded plan](../../remaining-paper-d20-identity-proposal.md).
Production base de3bdcb unchanged, current uncommitted harness/tests bound by source
inventories/Git-diff/runner hashes in each phase. No new published SHA/CI claim.

## Changes and checks

D20 final cleanup SELECT now uses one materialized backend snapshot for connection
count plus allowlisted PID/role/state/backend_type/transaction-open and timestamp;
lock count retained. Generated fixture-name guard rejects other/injected targets.
Malformed/missing identities never produce Passed. Zero connections/locks still
required; no wait, retry, ignored connection or performance-threshold change.
A separate post-process observation on postgres DB does not override that snapshot.
No sampling queries added during the measurement window.

22targeted tests Passed4.80s, including real PostgreSQL evidence that one open
fixture backend is identified and still blocks acceptance; empty-only, wrong count,
missing/extra/malformed data, duplicate PID, unsafe target and existing root/output
isolation checks. Scoped Ruff/format/mypy Passed. Controlled20 prior passing proof
reused for unchanged domain/runtime. No full suite or unrelated refactor.

## Outcomes

| Gate | Current evidence |
|---|---|
| controlled20 | Retained current-base Passed20/20,400baseline,max0.255965s; no repeated workload |
| D20 identity replacement | **Passed**:600/600 commands,300.000508s,book3000/3000,0rejected/duplicate effects;240fills/120cancels/120replays; engine p95/p99=95.948/128.225ms; pilot and target passed |
| D20 economic/resource proof | Financial/global invariants and owned pool contract Passed; no worker failures; one-shot cleanup0connections/0locks/empty backend list |
| D20 envelope |453.472s including120s preflight/setup/verification/cleanup, within1200s cap; candidate/runner unchanged; source schema0066 recorded |
| W4 integrated restore | **Passed**:canonical equality, RLS/grants, pending F16/F17 receipt/retry/exit recovery and source unchanged;21episodes/59evidence records/20checkpoints/18positions, expired claim recovered once without economic changes |
| W4 envelope |145.858s including120s preflight; backup1,828,938bytes; candidate/runner/support unchanged |
| Final cleanup | Both W4source/target0connections/0locks; process-exit observations empty. D20/source DBs removed normally by launcher. Restored target retained by the harness was explicitly checked0/0 then dropped normally; all three current campaign DBs confirmed absent. No force termination or volume/container reset |

Both new timed phases used fresh isolated databases and passed their7-sample
revision2 preflight. D20's SMOKE intake is diagnostic internal commands, not an
HTTP load acceptance claim. No owner account/session/order/gate mutation or Live.

Links: [D20 analysis](d20_identity/analysis.md),
[D20 aggregate](d20_identity/campaign-result.json),
[D20 cleanup identity](d20_identity/cleanup.json),
[W4 analysis](w4/analysis.md), [W4 aggregate](w4/campaign-result.json),
[W4 domain/restore](w4/run/restore/result.json),
[final database removal](identity-replacement-final-cleanup.json).

## Historical result and limitations

The earlier [SMOKE aggregate Incomplete](smoke/campaign-result.json) and
[non-reproducing cleanup diagnostic](cleanup/analysis.md) remain unchanged.
This replacement found no leftover connection; it does not identify the old one,
establish a root cause or prove recurrence impossible. No production fix claimed.

This closes the scoped current controlled20/D20/restore evidence gap. It is not a
full20-owner W1/W2/overflow/shortW3 pass on this candidate, not100-account/4h proof,
not owner visual sign-off/internal opening and not bot/notification/Live integration.
F17 V-18 remains Partial / Failed / Pending Full Validation overall; MF-13 Partial,
V-19/20 Not Run/Pending Dependency. F17 is not Completed or released.

## Next checkpoint

No further timed work within this approval. Related harness/tests/evidence remain
uncommitted. Recommended next: owner code review of this scoped harness before
Git publication; commit/push/PR/merge need explicit instructions and relevant CI.
B/load and remaining manual/opening/Release gates retain separate authorization
and dependencies. Do not automatically run B or another D20/W4 for confidence.
