# LP-02R1 — scoped refactor and replacement Passed, 2026-11-18

Status: **Scoped prototype validation Passed; stopped for owner review**.
No installation/security exception/Git/CI. F17 remains Pending Full Validation.

## Refactor scope

Copied corrected LP02 artifacts into this distinct receipt directory; preserved old
LP01Failed19/20 and LP02bootstrapFailed0/20. Names now describe capture_probe,
run_matrix and handle_termination; child/stage/cleanup timing values centralized.
No new abstraction, parser behavior, expected-result change or broader feature.
The frozen20case matrix, child bootstrap and parser patch are byte-identical to the
corrected LP02 versions, verified before and after execution via execution-binding.json.

## Evidence

- [Parser patch](picomatch-4.0.7-lp02.patch) is unchanged: token metadata reused instead
  of duplicate lexer. Original/patched source and archive integrity match LP02pins.
  Only lib/parse.js changes in scratch; upstream version/license unchanged.
- [Runner tests](runner-tests.log):5test methods Passed, covering success/failed expected
  return,timeout,overall deadline,SIGTERM primary/cleanup and actual-file harmless CLI.
- Ruff/format/mypyPassed for2refactored Python files; patchedJSsyntaxPassed.
- [Replacement matrix](probe-matrix.json) executed once: [results](probe-results.json)
  **20/20Passed**,1.598s total<60s. Per-child2s and256MiB heap caps; sequential children.
  Original adversarial stalls now return expectedfalse; ordinary and newly added quote/
  class/nested-bracket/POSIX/nobracket boundaries meet expectations. Corrected original
  equality oracle passes. Explicit opt-out behavior remains preserved on short input.
- All20children joined and PIDs independently absent. Owned scratch removed; pinned
  source/code/matrix unchanged through execution. [Cleanup](cleanup.json).
- App manifest/lock/config hashes unchanged. Installed dependencies, services, owner
  accounts, trading rules and Security registry were not touched.

## Limits retained for review

This finite20case result does not establish comprehensive ReDoS safety or all glob
compatibility. The patch intentionally literalizes a class of previously matching
patterns; conservative nested flag propagation and combinations of options still need
review. maxExtglobRecursion:false remains an explicit bypass by design; full caller
option/reachability mapping remainsPartial. No application-integrated toolchain/build
or source packaging/bypass proof has been performed.

OSV still identifies upstream4.0.7 as affected. No severity downgrade/exception or
published fixed release is implied by the prototype result. PV07 and stageB remain
Blocked/Not Authorized. F17's original V18/V19/V20 dependencies remain as declared.

## Next checkpoint

Owner requested stop after this replacement: ready to review this amendment's exact
patch/runner/tests and evidence. Await `review code`. Do not auto-install, continue
packaging, request a scanner exception or run another matrix. A later approved stageB
must define reproducible packaging and full installed caller verification separately.
