# LP-02 — review finding corrections, 2026-11-18

Status: **Corrections implemented; matcher verification Incomplete; stopped**.
Scope: owner instructed แก้ไข after LP01review. No installation/Git/CI/exception.

## Finding disposition

1. High duplicate lexer: removed. Parser's own star branch marks the current extglob;
   close propagates the flag to parent; existing conditions identifies single branch.
   Existing quote/bracket/escape/nobracket tokenization is reused. safeOutput and explicit
   opt-out preserved. This removes the specific duplicate-lexer implementation, but
   matching/security effectiveness has NOT yet been validated by replacement probes.
2. Medium original oracle: frozen LP02matrix corrects literal equality expected=true.
   LP01Failed19/20 receipt unchanged. Ordinary non-extglob cases previously Passed are
   retained as scoped evidence;4new parser-boundary cases replace4ordinary cases in the
   finite20child budget. The new matrix has no effective matcher results yet.
3. Medium success exit on failure: run returns1 for failed matrix and0onlyPassed;
   main uses SystemExit. Actual LP02raw failure exited1. Evidence is saved before return.
4. Medium lifecycle/deadline: monotonic stage deadline,2s per child and2s reserved cleanup,
   finally kill/join, custom cancellation exception, atomic partial evidence and original
   error preservation added. SIGTERM,timeout,deadline and expected-failure controls tested.

## Validation and bootstrap failure

- JavaScript patch syntax check Passed. Only lib/parse.js differs in scratch package;
  package version4.0.7/license unchanged. [Patch](picomatch-4.0.7-lp02.patch),
  [provenance](provenance.json), [frozen matrix](probe-matrix.json).
- LP02matrix attempted once: all20children failed JSON argument parsing BEFORE requiring
  picomatch, because node-e argv offset was carried into file-based invocation.
  Raw [result](probe-results.json) remainsFailed; effective matcher proof isIncomplete.
  No adverse matching result or successful fix may be inferred. All20children joined.
- Fixed probe-child.js argv slice2 after recording problem. Added actual-file CLI smoke
  with harmless fixture modules (no patched library/adversarial input). No matrix rerun.
- Final5runner tests Passed, including success/failure returns,child timeout,overall
  deadline,actual SIGTERM cleanup with primary error retained,and actual-file CLI.
  [Test log](runner-tests-final.log); Ruff/format/mypyPassed for2Python files.
- Intermediate runner cancellation tests failed twice because InterruptedError was
  swallowed as retryable OS interruption by subprocess; custom ProbeCancelledError fixed
  this. One preparation test invocation had a syntax error before running. These are
  retained development failures, not accepted evidence. No hostile-probe retries.
- Audit-owned scratch removed; app source/config/lock/scanner registry unchanged.

## Limits / next step

Parser metadata approach deliberately literalizes some previously matching repeated
wildcard patterns. Parent propagation is conservative; nested alternatives, option
combinations and unsupported glob syntax still need bounded compatibility proof.
Only targeted examples—not full ReDoS or application reachability proof—are planned.
Explicit maxExtglobRecursion:false remains opt-out. StageB and Security exception are
not authorized; OSV/F17 remainBlocked/Pending as before.

Ask owner about refactor per AGENTS.md after these source corrections. Recommended next
scope: narrow refactor if needed, then ONE corrected20case replacement matrix using
current frozen expectations and same time/memory limits, preserve all old failures,
stop for owner review afterwards. Do not install/publish/waive scanner automatically.
