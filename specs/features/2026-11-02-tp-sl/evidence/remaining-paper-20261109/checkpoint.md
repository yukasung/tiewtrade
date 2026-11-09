# F-17 remaining Paper validation — approved A checkpoint

Date:2026-11-09 Asia/Bangkok. Status: **Stopped — D20 campaign Incomplete**.
Owner approved A and confirmed unrelated build/test/workloads paused. One
controlled20 and one D20 were executed; no automatic retry or W4/B execution.
Production base:`de3bdcb6b9d9187ee9a06b5f7dcb43387f5d8e98` plus uncommitted
runner copies/tests. Source inventories/bindings/diffs and runner snapshots are
retained per phase; this is not CI on a newly published SHA.

## Preparation

Missing venv restored with Python3.12.15 and frozen uv.lock. Docker Desktop started,
then only existing PostgreSQL and dedicated fixture Redis containers started.
Owner app/API/order/risk/wallet workers were not started; no operator gate or data
mutation. Fresh local generated `tiewtrade_internal20_*` databases used throughout.
No database/container/volume reset or prune; no Live orders or owner trading actions.

Reused archived campaign22/W4-23 runners, preserving old artifacts. New copies
resolve this worktree ROOT and import the actual support module. Added type
annotations/QueuePool casts, formatting and candidate Git-diff/inventory binding.
No production/domain/API/schema/dependency source changed. Added tests for root/
restore support wiring, refusal of reused output before services/workload and
candidate binding. A final test-only adjustment removes reliance on runner remaining
untracked after a future commit; no runtime/harness/financial behavior changed and
no timed phase was repeated. Per-phase source manifests retain original test bytes.

Checks: initial preflight/profile/wiring125passed; final wrapper/binding5passed
(overlap4, adds1); real-DB targeted52distinct cases have passing evidence: initial
50passed/2failed because fixture Redis URL was absent; affected2passed after local
fixture config supplied. Both test databases removed. Ruff/format/mypy passed the
three new files (MYPYPATH=src for scoped mypy). Inherited untyped archived runner/
format/import errors and initial command/config errors were corrected before timing;
none is presented as a campaign pass. See [preparation](preparation.json).

## Outcomes

| Phase | Result | Observed scope |
|---|---|---|
| controlled20 | **Passed** |20owners/400baseline, observed20/20, max input-ready→start0.255965s≤1s; financial/exit/cash/position/audit/replay passed; no worker failures;224.423s including preflight |
| D20/SMOKE measured workload | Inner result **Passed**, subordinate to campaign below |600/600 completed,0rejected,240fills/120cancels/120replays/120cycles;300.000595s; book3000/3000; p95/p99 processing96.598/130.219ms; target250ms/1s and pilot500ms/2s passed |
| D20 campaign | **Incomplete**, exit1 |451.814s within1200s cap; source/runner unchanged; cleanup observed1connection/0advisorylocks; do not promote inner workload pass to overall Passed |
| W4/restore | **Not Run** |Stopped by A's conditional gate; old W4 only retains its original candidate scope |
| B/W1/W2/overflow/shortW3 | **Not Run** |Not authorized by A |

D20 used the existing diagnostic internal-command intake, explicitly recorded in
its manifest; it is not an authenticated HTTP acceptance claim. HTTP-intake log is
empty as expected for this SMOKE path. Shared Feature HTTP tests and W1/W2/W3 intake
proof remain separate. End-to-end command p95/p99=1.043888/1.078642s is distinct
from the engine-processing criterion above and is retained without substitution.

D20 global invariants passed: invalid reservations/positions/wrong-mode/unlinked
fills/duplicate fill effects0; expected760orders/400baselinepending retained.
Final-tail input lag3 was within original assertion. Peak RSS89,489,408bytes,
connections57→59/peak59, no lock waits. Owned pool contract passed for parent plus
20workers, no missing reports/errors/violations. These observations do not waive
separate final cleanup, hence overall Incomplete.

Sources: [controlled result](controlled20/run/result.json),
[controlled campaign](controlled20/campaign-result.json),
[D20 workload](smoke/run/result.json),
[D20 pool contract](smoke/run/pool-contract.json),
[D20 campaign](smoke/campaign-result.json),
[original cleanup](smoke/cleanup.json).
Both phases retain7-sample revision2 preflight Passed, host/config/schema/source/
runner bindings and resource samples. Raw console/test logs remain local ignored
.log files; synthetic fixture IDs only, no owner sessions/credentials used.

## Cleanup and cause boundary

Original D20 outer cleanup observed one connection and could not drop its fixture.
After all campaign/launcher processes exited, read-only inspection of **only this
fixture** found0connections/0advisorylocks. The fixture was then dropped normally,
without terminating any backend or forcing a drop. This later cleanup is recorded
in [post-exit-cleanup](smoke/post-exit-cleanup.json); original cleanup and Incomplete
result remain unchanged. Controlled20 source was also dropped normally. No
campaign database is intentionally left behind.

The original connection's PID/role/state was not captured, so its owner and cause
are **not established**. A transient server/backend shutdown race or an observer
lifecycle issue is a hypothesis, not a finding of a permanent production leak or
proof that one can be excluded. No extra wait, retry or resource exception added.

## Status and next step

A stopped at its authorized checkpoint. Current controlled20 proof is refreshed;
D20 aggregate is Incomplete and current W4 remains Not Run. F17 V-18 remains
Partial / Failed / Pending Full Validation overall; MF-13 Partial; original100-user/
4h and bot/notification/Live dependencies retained. F17 is not Completed.

Next proposal: [one isolated cleanup lifecycle diagnostic](../../remaining-paper-cleanup-diagnostic-proposal.md),
with no trading workload or automatic D20/W4 rerun. Wait for owner approval under
A's stop-on-failure rule. No commit/push/PR/merge/deploy performed or authorized.
