# LP-03 review-finding corrections — 2026-11-18

Status: **Targeted correction checks Passed; awaiting owner refactor decision**.
Owner instructed แก้ไข following LP02R1review. No install/exception/Git/CI.

## Findings addressed

- High branch classification: introduced hasTopLevelAlternative per extglob; native pipe
  handling sets it only at state.parens===extglob.parens+1. Existing conditions remains
  unchanged for original behavior. Guard now uses the new flag. Ordinary nested-group
  pipes no longer disable single-top-level-branch protection. No duplicate lexer.
- Medium test readiness/cleanup: child publishes complete ready/witness values with
  temp-file rename. Parent runner is in a new owned session/group. Finally cleans the
  owned group before reaping when cancellation/setup fails and PID is unavailable;
  when already reaped, fallback verifies known child still belongs to that owned group.
  Added deliberate pre-readiness failure control; witness PID read only AFTER cleanup
  to independently verify absence. No other services/process groups touched.

## Evidence

[Exact patch](picomatch-4.0.7-lp03.patch), [source/license provenance](provenance.json),
[runner controls](runner-tests.log), [frozen matrix](probe-matrix.json),
[results](probe-results.json), [binding](execution-binding.json), [summary](summary.json).

6runner test methods Passed, including SIGTERM and pre-PID failure cleanup. Ruff/format/
mypyPassed for2Python files; patchedJSsyntaxPassed. One9case targeted matrixPassed,
0.637s<30s,2s/child and256MiB, no hostile baseline execution. All9children joined/PIDs
independently absent, owned scratch removed. Source/matrix/runner remained pinned.
Earlier LP01/LP02failures and LP02R1scopedPassed remain unchanged.

Coverage includes +((*a|b)) adversarial and literal equality, harmless ordinary-group
alternatives, nested extglob alternative followed by wildcard, top-level alternatives,
quoted/bracket pipe plus wildcard, original single-branch attack and short benign
multi-branch control. The multi-branch short control preserves existing behavior; it is
NOT a denial-of-service test and establishes no safety of wildcard multi-alternatives.

## Limits and next step

Still a local prototype, not global/advisory remediation proof. Newly literalized pattern
semantics, conservative nested propagation and maxExtglobRecursion:false opt-out remain.
Broader nested/wildcard multi-alternative safety, full caller reachability and installed
packaging/toolchain acceptance are unproven. OSV still flags upstream4.0.7; no exception
or stageB approval implied. F17 remainsPending Full Validation.

Stop after this correction checkpoint; ask owner whether to refactor per AGENTS.md.
No extra matrix, installation or publication without applicable scope. After authorized
refactor, run only affected validation and preserve existing evidence where unchanged.
