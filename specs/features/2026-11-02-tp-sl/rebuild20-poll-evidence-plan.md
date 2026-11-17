# NC-F17-REBUILD20-POLL-01 — streamed preparation poll evidence

สถานะ: **Approved — owner approve after REBUILD20-02 stop/report, 2026-11-16**
Scope: implementation and targeted safety checks only; no replacement campaign,
four-hour run, Git/CI/merge. Existing F17 amendment/branch. Record before source.

## Problem / requirements retained

REBUILD20-02 stopped at ParentPollGate.permit's100000 in-memory-row guard before full
rebuild. The long fixture selected ParentPollGate() while the full internal workload
already uses a streaming path. Keep poll concurrency4,cadence0.25s,cycle60s,rebuild60s,
all money/source/risk/pool validators. Do not remove/increase the original default guard
or turn interrupted parent ConnectionResourceError/Incomplete into Passed.

## Reuse / implementation

In profile_rebuild20.prepare_economics, parallel_runtime=True selects existing
ParentPollGate(stream_path=output/'parent-poll-attempts.jsonl'), exclusively creating its
file before spawning publisher/worker tasks. Default single-worker gate keeps the
existing in-memory mode/guard. Both modes persist gate.save('parent-poll-gate.json')
after with_publisher has joined seed tasks and finish_mutators has joined workers/
publisher, even on errors. Preserve first exception/cancellation when summary IO or
leak checking fails; still attempt fixture-progress receipt. Reuse current gate.save,
save_partial_result and exception-note pattern, no new pool/recorder abstraction.
Streaming preserves every completed/cancelled poll attempt; no dropped samples or
bounded-ring substitution. Disk error fails closed; unbounded RAM rows remain avoided.

## Validation / checkpoint

Feature: streamed >100000 attempts with zero retained rows and all attempt records,
default100000 guard unchanged,waiting cancellation/concurrency4,stream/summary IO,
primary exception/cancellation preservation,summary attempt after join,receipt on
summary failure,preexisting trace rejection before background tasks. RealPG small
parallel fixture asserts saved gate consistency/trace count and normal financial/
source/no-write/full-small-replay/actual20-worker/pool proof. Retain other proofs with
unchanged semantics; no fake pool acceptance for interrupted run. Run affected tests
plus relevant existing parent-poll cases and scoped Ruff/format/mypy/whitespace.
After checks report scoped findings/fixes checkpoint; owner review/refactor gates apply.
Replacement full-profile run requires separate explicit authorization; none in this
amendment. Historical results/F17notCompleted unchanged. No criterion relaxation.


## Related evidence-error hardening — recorded before shared helper edit

Inspection of the newly used streaming path found that ParentPollGate.permit's finally
write could mask an existing body exception/cancellation if trace IO also fails. This
is directly relevant to the approved primary-error preservation requirement. Under the
owner's delegated engineering authority, retain the active error and attach the trace
IO error type; leave finished_count short of attempts so gate.save still fails closed
on incomplete evidence. Without an active error, propagate the trace IO failure as
before. No memory guard, cadence, concurrency, success semantics or validator relaxation.
Extend the fixture fault matrix with simultaneous operation/cancellation + trace IO;
rerun the affected fixture/parent-gate regressions, including real PG.


2026-11-16 [REBUILD20-POLL-01 harness fix](evidence/endurance20-20261115/rebuild20-poll-checkpoint.md)
scopedimplementation/safety Passed;awaiting ownercode review. Existing streaming poll
path selected only for parallelfixture,default100000 guard/cadence0.25/concurrency4/
allfinancial/timeouts unchanged. Summary after mutatorjoin and partialreceipt onerror;
streamIO retains primaryerror/cancellation while incompletefinishedcount stillrejects.
83targetedtestsPassed including100001attempts and realPG/actual20process/fullsmallreplay;
four-fileRuff/format/mypy/whitespacePassed;testDBindependentlyabsent/0connections/locks.
No replacementcampaign/fullrebuild/4h/Git/CI;REBUILD20-02Incomplete/poolFailed preserved.
Next ownerreview;F17notCompleted andremainingvalidationdependenciesunchanged.


## Review finding M1 — owner authorized fix, 2026-11-16

Owner instructed แก้ไข. Reproduction: permit invoked inside a caller's except block
misidentifies the unrelated handled error via sys.exception and suppresses trace IO.
Before edits: capture only errors raised by this permit/fixture operation into explicit
local state. Pass that state through owned-mutator cleanup and summary/progress writes;
normal completion inside an outer except must still propagate its own evidence errors.
The fixture worker cleanup uses the same explicit-state pattern. Extend the reused
save_partial_result helper with an optional explicit-primary argument while preserving
its omitted-argument behavior for existing callers. This avoids moving or duplicating
its evidence/error handling. Tests: ambient caller error + trace IO, summary IO,
progress IO, cleanup failure, and real current operation error/cancellation identity.
Retain all existing guards/timeouts and incomplete-evidence rejection. Run affected
fixture/parent-gate/replay lifecycle regressions and scoped checks; no timed campaign,
criteria change or Git/CI. No security/risk/session behavior change.


2026-11-16 [POLL-01 review M1 fixes](evidence/endurance20-20261115/rebuild20-poll-m1-fixes.md)
Passed scoped checks:explicit operation/cleanup/summary/progress error state prevents
unrelated caller except from swallowing evidenceIO;legacy omitted partialreceipt arg
retained.113targetedtests including realPG/actual20workers/replay lifecycle Passed;
28focusedfinal cases/five-file Ruff/format/mypy/whitespacePassed;ownedtestDBindependently
absent/0connections/locks. Await ownerrefactor decision. No campaign/fullrebuild/4h/Git/CI;
prior Incomplete/poolFailed/F17notCompleted unchanged.


## Owner-authorized M1 refactor — 2026-11-16

Owner instructed refactor the code. Scope is the latest M1 fix only: replace repeated
fault-name membership checks in its regression matrix with local named flags and
clarify explicit None versus omitted primary-error argument in the helper docstring.
No new abstraction, changed test cases/assertions, exception ordering, runtime logic,
trade rule or evidence semantics. Run final28 focused cases and scoped Ruff/format/
mypy/whitespace; retain prior113 realDB/process/replay safety evidence because runtime
behavior is unchanged. Validation proceeds automatically; no campaign/4h/Git/CI.


2026-11-16 POLL-01 M1 refactor checkpoint

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
