# LEASE-01 review correction M1

สถานะ: **Fixed — targeted checks Passed; await owner refactor instruction**

Owner instructed “แก้ไข” after review. M1 allowed an expected WriterLeaseLost to
be classified complete when readiness finalization IO failed and only trace.json
was validated. [Plan recorded before source changes](../../publisher-lease-diagnostic-plan.md#review-correction-m1--owner-authorized-fix).

Changes:
- `profile_publisher_readiness.py`: optional per-context receipt latches write
  failure, including failure after valid bytes reached disk. Existing callers,
  original exceptions, return/yield behavior and guard policy unchanged.
- `profile_publisher_lease.py`: before completion, reject missing/corrupt readiness,
  wrong final reason/count or mismatched tick/owner/input/generation/outcome and any
  reported write failure. Preserve the exact original WriterLeaseLost with a
  sanitized evidence note, no note-text parsing/retry. Saved result stays Incomplete.
- `test_publisher_lease.py`:10case-level real-PG faults cover IO before/after write,
  missing/malformed/mismatched evidence for successful and rejected publications.
  Assert exact lease error, no retry, no complete outcome, no private error content
  and independent lock-release/cursor proof (commit once or rollback respectively).

Final affected checks: **27Passed/23.80s**, no skips:10faults +5real-PG normal/slow/
expired cases +12existing readiness regressions. Log:
`validation-artifacts/f17-clock-recovery-tests-20261115/attempt-1794753351451523000.log`.
Earlier4test failures/33Passed were a fault-injection setup mistake (rejected setup
publication rather than observed attempt), corrected; intermediate22Passed retained.
Scoped Ruff/format/mypy on3files and whitespace Passed. All owned test DBs removed
normally by the isolated launcher. No campaign/4h/Git/CI actions.

[Source bridge and receipts](lease01-m1-summary.json): exactly these3harness/test
files differ from the pinned diagnostic source inventory; other pinned production/
workload/config/migration/frontend sources unchanged. Original five-case diagnostic
remains evidence for its original candidate (all five actual readiness files were
present/readable with correct guard counts). It is not a timed run of the fixed
candidate. No new performance or four-hour acceptance claimed. Existing W3
Incomplete/final financial/rebuild/Release/dependency status and F17 notCompleted
remain unchanged.

Next: await owner's `refactor the code` instruction per AGENTS review-fix gate.
This correction does not authorize another experiment or publication.
