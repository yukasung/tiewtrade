# REPLAY-01 — review M1/M2 corrections

สถานะ: **Both scoped findings fixed; targeted verification Passed**
2026-11-16, owner requested แก้ไข after read-only review.
[Pre-source amendment](../../replay-read-diagnostic-plan.md#review-corrections-m1m2--authorized2026-11-16-before-source).

M1: finalize_replay_run independently attempts source verification, ownership-checked
cleanup and result save. Sourcehash exception/drift/cancellation cannot skip cleanup
or save. The first error/cancellation retains identity; secondary errors are type/
stage records and exception notes,not exception messages/secrets. Failure always
marksIncomplete. Cleanup failure retains database identity,does not retry/forceDROP.
Missing ownership receipt after creation intent retains resource rather than guessing.

M2: save_partial_result preserves the exception already active in the readfinally.
An IO error adds secondaryevidence while the originalTimeoutError/CancelledError
continues to propagate. If no primary exists,the IOerror itself propagates. Finalsave
failure likewise cannot replace an existing read/source/cleanup error or declarepass.
Patterns reused from existing commit/lease observers. No production reader,decoder,
SQL,financialrule,lease,sessionarchitecture or persistentstorage change. Diagnostic
callback references/reports are transient test state,not application/business state.

Helpers are in profile_replay_reads.py; negative tests in test_replay_reads.py.
Original executed runner/result/hash are immutable. A separate **unexecuted**
corrected runner calls the tested helpers; exactold/newdiff/hash and wiringproof:
validation-artifacts/f17-replay01-review-fixes-20261116/.
That workingcopy is private diagnostic material,not a new campaign/result or code
that depends on private artifacts in CI. Collected pytest tests need no rawartifacts.

## Verification

14tests Passed:4unchanged observer/RLS/real-PG/financial-no-write regressions plus
10new cases for sourceexception/drift,cleanupfail,finalsavefail,normalpath,partialIO
with/withoutprimary,Timeout/cancelidentity and multiple secondaryfailures.
Log validation-artifacts/f17-replay01-tests-20261116/attempt-1794795465307874000.log.
Scoped2-file Ruff/format/mypy Passed. The finalteststyle-only withblock consolidation
occurred afterpytest loaded the file; same contexts/assertions/behavior,staticpassed.

Separate private binding proof executes **actual corrected runner AST finally bodies**
with controlled sourcehash failure/IO failure (no preflight/DB/workload): cleanup
then save both called; originalreadTimeout survives partialIO; oldrunnerhashunchanged.
This proves corrected runner wiring,not a fresh96000read/4h performance result.
HistoricalDiagnosticComplete and FENCE-02Incomplete remain on originalcandidates.
No campaign,productionoptimization,samplerchange,timeoutrelaxation,Git or CI run.

## Checkpoint

Scoped review findings corrected and affected validation complete. F17 remains
notCompleted; finalfinancial/global/rebuild20/resource/Release dependencies unchanged.
Next is owner instruction whether to refactor these fixes,per AGENTS review/fix gate.
Do not start a new diagnostic or4h run from this checkpoint alone.
