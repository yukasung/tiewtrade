# Prepublication follow-up findings — fixed and validated

Date:2026-11-09 Asia/Bangkok. Owner instructed “แก้ไข” after asking to consolidate
remaining changes into one PR. Status: **Two follow-up findings fixed; targeted checks Passed**.
No commit/push/PR/required CI initiated. All related changes remain on the same branch.

## Changes

- W4 cleanup now requires exactly connections/advisory_locks, both nonnegative
  integers (bool/string/missing/extra fields rejected), with both zero to pass.
  D20 and W4 reuse one strict counter validator; D20 retains its additional
  timestamp/backend identity checks. W4 malformed observation is Incomplete unless
  workload was already Failed, which remains Failed. Allowlisted rejected data
  remains separate from error_type. No retry, waiting or cleanup exception added.
- Diagnostic observer disposal failure/cancellation no longer skips writing
  pool-events/result artifacts. Result records Incomplete and a separate
  observer_disposal_error type. An existing body error/cancellation remains the
  primary exception with a type-only secondary note. If disposal is the first
  failure, it is re-raised after evidence is saved. Successful unchanged disposal
  and observation retain their existing behavior. No private error text persisted.

## Validation

Combined affected selection **65passed in6.69s**:

-23new publication regressions:16malformed W4 outcome combinations,1valid zero
  cleanup,6observer disposal error/cancellation with/without primary error/cancellation.
-42previous review/diagnostic/identity/root-isolation cases retained and rerun;
  includes actual PostgreSQL held-backend rejection and parent interruption cases.

Ruff, format and scoped MYPYPATH=src mypy Passed4affected files (three harness
modules and the new regression file). Test fixture source/template/clones removed;
launcher confirmed source removal. No workload/D20/W4/endurance/full-suite rerun.
No production/domain/API/schema/dependency, financial, authorization/session,
profile/rate/resource threshold or operator gate change. Immutable tuples/sets
and local observations are test configuration/evidence, not persistent business state.
Final source hashes: [publication-fix-source-manifest.json](publication-fix-source-manifest.json).

## Evidence and next step

Earlier campaign/refactor/review manifests/results are not overwritten. Passing
D20/W4 had complete valid counters and no observed disposal failure, so retained
proof remains within its original candidate/runtime scope; it is not relabelled
as execution on these new harness bytes. Original Incomplete/unknown connection
cause remains historical. F17 overall Full Validation/dependencies/manual/opening
remain pending. No new CI or Completed/merge-ready claim.

Follow-up fixes and impact checks are complete. Per owner AGENTS.md, ask whether
to `refactor the code` for this source-changing finding fix and wait before that
step. Consolidate related source/tests/spec/evidence in one future PR after the
owner's Git instruction; no separate PR or CI round was created for this checkpoint.
