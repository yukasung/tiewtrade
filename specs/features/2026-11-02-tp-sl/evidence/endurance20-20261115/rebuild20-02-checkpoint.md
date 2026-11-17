# NC-F17-REBUILD20-02 — approved single campaign checkpoint

สถานะ: **Incomplete — stopped during economic fixture preparation**.
2026-11-16. [Approved plan](../../rebuild20-parallel-plan.md) ·
[Sanitized summary](rebuild20-02-summary.json).

## Readiness and actual execution

93 targeted tests Passed in 37.789s, including real PostgreSQL and actual20-process
small financial/source/full-replay/pool proof. Three extracted-runner orchestration
checks Passed for successful handoff ordering, lease rejection and monetary failure.
Five-file Ruff/format/mypy Passed. No repository runtime source was changed in this
execution step; a separate runner selected the reviewed parallel preparation path.
Candidate source/diff, config, schema/migrations, copied runner and external helper
copy/hash were pinned. Final source/runner/helper binding check passed.

One 120-second/seven-sample preflight Passed. All400 baseline orders were prepared.
The single approved campaign stopped after **1149.152s (19min09.152s)** at the economic
fixture stage, before any owner completed all282 cycles. Saved partial counters:
17,550 offered/admitted,17,530 completed,0 rejected;7,006 fills,3,506 cancels,
3,509 replays,3,495 completed cycles. These are counters at interruption, not final
committed financial oracles or evidence that every outstanding command was rolled back.
20 commands were outstanding by counter difference. No replacement commands were sent.

## Immediate cause and limits of diagnosis

The terminal traceback ends at profile_parent_poll.ParentPollGate.permit line84.
That line raises NC09_POLL_GATE_TRACE_TRUNCATED when stream_path is None and its
in-memory rows reach100000. profile_rebuild20.prepare_economics constructs
ParentPollGate() without a stream path. This fixture therefore selected the short
in-memory trace mode despite the long preparation shape; the existing full workload
uses streamed traces for internal phases. The final runner records error_type and
stack location, not the exception message; the named error is identified from the
pinned source at that exact raise site. No poll trace/summary was saved by this fixture,
so exact per-owner wait distribution cannot be reconstructed from this result.

This is a harness trace-retention limit, not a measured full-rebuild60s outcome.
No evidence supports changing the financial, poll-concurrency, cycle or rebuild rules.
The source witness after stopping shows committed cursor10170,matching journal count,
owner/generation1 retained. No lease reacquire/retry or source replacement occurred.

**Not Run:** public extension to96000,private padding20x96000,finalfinancial/global
oracles,snapshots/fullreplay20owners. The revised immediate handoff ordering was tested
in orchestration checks but not reached by this campaign. Earlier scoped600-command
Passed and all previous Incomplete grades remain unchanged; this is not another4h run.

## Resources and cleanup — preserve failed evidence

201 resource samples: peak per-process RSS91,078,656 bytes;peak connections64;one peak
lock wait and zero at last sample;observed DB growth563,298,304 bytes. Short/interrupted
resource observations do not substitute for aggregate/endurance acceptance.

All20 owned workers exited0 and their pool reports Passed. Parent report remains
**Failed** (outcome RuntimeError,ConnectionResourceError1): a sibling owner task was
cancelled while awaiting an ENGINE read during failure unwind. Aggregate pool proof
therefore stays Failed/Incomplete (ConnectionResourceError and PoolFinalEvidenceIncomplete).
Do not whitelist/regrade that event merely because it followed the main error. All five
parent pools nevertheless report final checked_out0 and final_disposed true; these facts
and independent cleanup are distinct from the failed aggregate acceptance result.

Normal cleanup removed only the owned DB. Independent maintenance connection confirmed
DB absent/0connections/0advisorylocks and no20ownedworkerPIDs remain. Existing PostgreSQL
healthy/restart0;Redisrunning/restart0. No other-service stop,force drop,newRedis,
owner-account or Live orders. Raw private evidence retained at
validation-artifacts/f17-rebuild20-02-20261116/;do not publish wholesale.

## Next proposal — not implemented or executed

Use the existing ParentPollGate(stream_path=...) pattern for this long fixture so every
completed/cancelled poll attempt is streamed rather than accumulating100000rows in RAM.
Retain semaphore4,poll0.25s,all timeouts/financial/source rules and evidence completeness.
Persist gate.save summary after owned-mutator join,including attempts/finished/active/
truncated,without masking primary exceptions. Do not merely increase/delete the guard.
Test more than100000attempts through streaming,default guard retention,IO/cancellation/
summary failure,primary preservation andactualPG/process regression. Inspect the
interrupted parent pool event without relaxing its validator; prove normal post-fix
completion with original pool rules. Then propose one replacement full-rebuild campaign
with the same profile/budget,not automatic four-hour execution.

The approved single campaign scope has ended. No further source fix, campaign rerun,
performance optimization,4h,Git,CI ormerge performed. F17 remains notCompleted with
full rebuild/financial/resource/W3/Release and dependent gates pending.
