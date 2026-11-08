# Post-merge58e2299 — atomic pool diagnostic publication

สถานะ: **Approved A — owner explicitly approved atomic publication, targeted tests, commit/push, follow-up PR and one CI round on 2026-11-08**
Date: 2026-11-08 Asia/Bangkok
PR63 merged58e2299e1d179607f5a2e5e4671e48beb7a01009.

## Evidence / scope

Post-merge CI42487118978 backend Failed at test_profile_diagnostics.py:356:
reader observes existing worker-0.pools.json but json.loads receives an empty
string; main4820Passed/oneFailed, isolated downstream gates Skipped. Reader and
writer run in different processes. PoolEvidence.save in
backend/tests/infra/risk_limits/profile_resources.py writes directly to its final
path using Path.write_text (truncate before content). There is a real publication
window, irrespective of whether the first observed race can be reproduced every run.
Security Passed on merge SHA; E2E-only rerun is tracked separately. Do not label
this a financial defect or claim rollback tests passed on the failed backend run.

## Approved requirements / plan amendment

Make only diagnostic pool-file publication atomic. Retain the exact JSON document,
all pool sizes/overflow/configuration/finalized/checked_out criteria, strict readers,
5s polling timeout, sampling cadence and production financial/runtime logic.
Do not catch-and-ignore JSONDecodeError, weaken assertions or extend timeouts.

Reuse same-directory temporary-write + Path.replace publication from
execution_market/profile_workload.py::publish_trace_control. Each worker already
has its own evidence path; no new shared storage, cache or infrastructure.
Update PoolEvidence.save only, writing complete JSON to a temporary sibling then
atomic replace, cleaning temporary data on failure without destroying the prior
complete document. No generic new abstraction. Keep metadata/diagnostics private.

## Approved validation / publication

Add targeted fault-injection tests in existing test_profile_resources.py: during
incomplete staging a reader sees either no final file or previous complete JSON;
replacement exposes complete exact new document; interrupted write/replace retains
prior file and cleans temporary data. Use existing barrier/monkeypatch pattern
from test_trace_control_is_complete_before_existing_readers_can_see_it.
Run both real-worker r8 parameterizations and existing actual pool/return/leak
contract cases on a clean isolated PostgreSQL database, plus scoped Ruff/format/
mypy. No workload campaign, Live orders or owner account mutation.

Use a new follow-up branch/worktree from current main; PR63 is already merged.
Record owner approval in relevant resource/pool validation before source edits.
If targeted checks pass, normal commit/push and new PR, track one required CI/
Security round (about20–25min after about3–5min development/checks), then stop/report.
No auto-rerun or merge of the new PR; owner merge command required separately.
Keep current failed post-merge evidence, pending F17 Batch/Release and code-review
workflow gates. Owner approval recorded before implementation; results remain pending until observed.

## Final prerequisite status

Post-merge Security Passed. Owner-authorized targeted3m diagnostic Passed12.5s;
E2E-only rerun job128756360168 Passed all42cases on the merge SHA. Main CI
42487118978 remains Failed solely due to the retained backend pool-file race.
No source repair or backend rerun has been performed.

Approved implementation/validation: [local checkpoint](evidence/manual-acceptance-fix/postmerge-pool-atomic/checkpoint.md),12 tests and scoped static checks Passed; required CI Pending. Historical no-edit statements above describe proposal preparation.
