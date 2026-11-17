# NC-F17-REBUILD20-05 — representative full replay20

สถานะ: Approved execution scope by owner เริ่มทำ following REPLAY05 result and
recommendation for full financial replay20 at144364 inputs (2026-11-17).

## Scope before runner edits

Reuse REBUILD20-04 full offline economic fixture and all original oracles,with current
reviewed/refactored REPLAY05 reader/cursor and CUT01 cleanup corrections.20owners,
400baseline,282cycles/owner,28200commands,11280fills/5640cancels/5640idempotent replays.
Increase public/private fixture head96000→144364 to match CUT01 observed volume;
private total2887280. This is representative volume,not a reproduction of every W3
market condition or historical state. No trading amount/risk/fee/financial rule change.

Retain original4200s total budget/reserve120s/workdeadline4080s,60s per full owner replay,
snapshot p95≤250ms/p99≤1s,RSS≤1GiB,all pool/financial/global/source/post-rebuild economic
digests,lease5s and no retry/reacquire. Expected65–70min from measured REBUILD04 phases
plus larger history and REPLAY05 reader; narrow margin is disclosed,not an extension.
If deadline/failure occurs,cleanup and stop; no automatic rerun or4h continuation.

## Reuse and binding

Use unchanged profile_rebuild20.prepare_economics(parallel_runtime=True),publisher.extend,
pad_history,verify_rebuild;original PositionChecks.final,profile_restore.replay_owner_domain,
OwnedPools,streamed poll evidence,resource sampler and owned fixture helpers. Existing
head parameters accept144364 (tail bound144513),no source modification needed.
Current candidate must equal the final REPLAY05 pinned inventory; retained helper safety
fingerprints remain mandatory except profile_replay_reads whose updated cursor-observer
binding is covered by14Passed tests plus current75case safety evidence. No waiver of
cleanup helpers; only read_page observer changed since the old binding.

Runner changes only identity/head/counts and explicit current-candidate safety binding.
Preserve all original operation ordering,source lease handoff,final verification receipt
only after post-rebuild digest,exception preservation and ownership cleanup. Validate
AST-equivalence of campaign operations after substituting96000→144364 and unchanged
budget/reserve,plus syntax/parameter support/source hashes before running.

## Execution / stop

One120s/seven-sample preflight before fresh database or workers. Pin candidate/config/
schema/runner/helpers. Economic fixture → public extension → prehistory financial/global
→ private history/economic digest →20snapshots/fullfinancialreplays/postdigest →resource/
pool →cleanup → independent DB/process/connection/lock absence. Do not stop other apps,
forceDROP,remove volumes or send owner/Live trades. Report original Failed/Incomplete
unchanged. Once this run finishes/fails,stop/report; no Git/CI/merge or4h in this scope.

## Completed execution — 2026-11-17

[Evidence](evidence/endurance20-20261115/rebuild20-05-result.md): Passed scoped offline
rebuild20,total3784.202s within4200. All28200commands/20financial oracles/20snapshots/
20fullreplaysPassed;144364records each,44.047–46.732s≤60. Postdigest/21pools/resource/
source/independentcleanupPassed. Stop/report,no4h/Git;historicalW3Incomplete retained.
