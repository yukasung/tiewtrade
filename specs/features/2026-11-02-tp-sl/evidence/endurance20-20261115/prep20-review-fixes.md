# NC-F17-PREP20-01 — review fixes M1/M2

สถานะ: **Scoped fixes and affected checks Passed; awaiting owner refactor decision**.
2026-11-16. Owner instructed แก้ไข after code review. Amendment recorded before source.

## Changes

M1: fixture shutdown now bounds the reused stop helper to 12 seconds, then attempts
termination for each remembered child independently and waits at most 2 more seconds.
Signal failure does not skip siblings. A remaining child is reported through exception
notes with its PID; no forced database drop, service stop or automatic retry. The first
exception/cancellation is preserved, including remaining-PID notes through startup and
outer cleanup. Fixture startup failure uses this bounded path too; ordinary worker
shutdown behavior is unchanged. These bounds cover fixture child shutdown, not a new
claim that every external operation is guaranteed to finish by the campaign deadline.

M2: load_fixture_helpers requires the expected SHA-256 of reviewed external helper
bytes, creates an exclusive copy and digest receipt in the campaign root, rechecks that
copy and executes only its five selected functions. Missing/duplicate helper inventory,
changed digest or reused output fails before execution. A separate revised runner pins
this dependency before preflight/fixture creation; its AST parses successfully. Original
runner/evidence were not edited or rerun. Revised runner retained locally at
validation-artifacts/f17-prep20-review-fixes-20261116/runner-next.py (Not Run).

## Validation and limits

32 targeted lifecycle/journal/launcher/helper tests Passed; 3 real-DB cases deselected.
Scoped three-file Ruff, format and mypy Passed. Existing real-DB financial/source/
20-process/pool evidence from the earlier 82-case run is retained within its original
scope, not claimed as rerun on this candidate. New shutdown faults use controlled
process doubles; successful actual process/DB cleanup was already observed previously.
No domain, SQL, schema, session, financial/risk, Live or production source change.
Transient process handles and pinned files are harness evidence, not application state.

The original 600-command capacity result and 20-owner financial checks remain recorded.
Its helper dependency was not pinned at execution: source_unchanged did not cover that
external launcher. The revised loader fixes future evidence binding only; it cannot
retroactively prove that historical dependency. Previous Incomplete results stay intact.
No workload, full rebuild, four-hour run, Git, CI or merge performed. F17 not Completed.
Next: owner decision whether to refactor these source changes; do not start it implicitly.


## Authorized refactor checkpoint — 2026-11-16

Owner instructed refactor the code. Flattened the exited-child branch in the fixture
termination loop; signal order, timeout values, primary exception and evidence notes
unchanged. Reused one never-finishing coroutine in shutdown fault tests and consolidated
hashlib imports; all test assertions retained. No new abstractions or unrelated changes.
32 affected tests Passed (3 real-DB cases deselected); scoped three-file Ruff, format,
mypy and whitespace Passed. Automatically completed impacted validation after refactor;
unaffected real-DB financial/process proofs remain scoped historical evidence, not rerun.
No workload/full-history/four-hour/Git/CI. This amendment's stop/report checkpoint is
complete. Next proposed work is the bounded representative full-history/rebuild plan
using the corrected preparation runtime; it needs a new explicit start/scope before
execution. F17 remains not Completed and all prior grades/provenance limits are retained.
