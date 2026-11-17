# FENCE-01 review M1/M2 corrections

สถานะ: **Fixed — affected checks Passed; await owner refactor instruction**

Owner instructed “แก้ไข” after review; [plan recorded before source changes](../../publisher-fence-observation-plan.md#review-fixes-m1m2--owner-instructed-แก้ไข).
Only the dedicated fence module/tests changed.

M1: close now owns a shielded cleanup task. Caller cancellation (including repeated
cancellation during monitor join or engine disposal) is deferred until monitor is
cancelled/joined and disposal completes. Propagate the first original cancellation;
sanitized cleanup-error note cannot replace it. Normal monitor grace/timeout retained.
No production driver abort, backend kill or forced resource cleanup introduced.

M2: freeze statement identity before awaiting; capture start/end, separate activity/
locks intervals, statement finish at start/end, and explicit association classification.
Only the same current unfinished statement through capture is ACTIVE_THROUGH_CAPTURE;
already completed and overlapped/unconfirmed cases remain raw evidence with distinct
labels. Views explicitly non-atomic. No guessed exact SQL/blocker attribution, extra
queries, sample deletion or workload/financial threshold change.

Final **42Passed/9.83s**, no skips: fence tests plus load observer regression. Added
single/repeated cancel, cancellation during disposal with disposal IO failure, real
PG pending readonly query cancellation and owned-pool zero-return/disposal proof.
Race cases cover stable, completion during activity/locks reads, already completed,
and changed current statement; original identity/raw views retained. Actual held-lock
integration confirms active association and original publisher commits once after
release. Two intermediate test-setup failures retained in summary (readonly method
patch target and missing fixture parameter), corrected before final checks.
Scoped2-file Ruff/format/mypy/whitespace Passed. Owned isolated parent test DB removed
normally. [Source bridge/receipts](fence01-review-fixes-summary.json) verifies all other
pinned production/workload/lease/pool/config/migration sources unchanged.

No diagnostic/4h/Git/CI rerun and no old grade changed. Original FENCE-01 Passed is
on its original candidate; normal shutdown/0blocker samples did not exercise these
findings. Fixed candidate has targeted proof, not a new performance acceptance.
Historical lease cause/four-hour Incomplete/full financial-rebuild/Release/dependencies
remain unchanged and F17 notCompleted. Next: await owner's `refactor the code` command
under the AGENTS review-fix gate. No automatic timed replacement is authorized.
