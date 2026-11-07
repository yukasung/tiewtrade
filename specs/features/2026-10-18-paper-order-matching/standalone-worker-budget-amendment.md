# F15 standalone worker claim budget

สถานะ: **Approved — owner selected option A on 2026-11-06**
วันที่: 2026-11-06

## Problem established by the diagnostic

The existing standalone W1 uses20candidate scans with no per-round claim budget.
The failed cycle timeline shows24.0s for MARKET BUY,9.2s for LIMIT SELL admission,
about7.4s for replay/cancel, then19.4s for the final MARKET SELL before the whole
cycle60s bound expires. Admission/status waits dominate, not one60s pool checkout.

Matching the actual worker transactions to this cycle shows admission processing
starts seconds after submission; parent receipt polling follows worker commits
within about0.11–0.28s for these commands. The final fill transaction commits about
0.187s after the cycle deadline. Its event timestamp alone is not commit visibility.

During the captured window,45745committed claim transactions comprise30481failed
owner try-lock paths,11697no-claim UPDATE/CAS paths and3567successful claims.
The no-claim UPDATE path's exact failed guard is unknown. These safety guards are
correct and must remain. This demonstrates costly contention/redundant attempts;
it does not prove that a particular tuning change will satisfy all W1 criteria.

Evidence: [failed owner analysis](../2026-11-02-tp-sl/evidence/batch-20261106/diagnostic-3-failed-owner-analysis.json),
[claim path proof](../2026-11-02-tp-sl/evidence/batch-20261106/diagnostic-3-claim-branch-summary.json),
[DB timeline](../2026-11-02-tp-sl/evidence/batch-20261106/diagnostic-3-db-timeline.json).

## Approved option A — reuse the existing R8 budget, opt-in only

Reuse `tests/infra/execution_market/profile_workload.py::run_worker_process`'s
existing `claim_limit` parameter and the shared engine's implemented R8 behavior:
scan at most20candidates and obtain at most1non-None claim per phase, counted
before commit even when subsequent processing fails or defers. A claim returning
None does not consume this budget; continue within the same20candidate bound.
Keep the existing20ms tick and rescan. Do not invent a new claiming protocol.
Forward an explicit opt-in argument through the standalone
parent/worker/restart launcher and record the actual configuration in the manifest.

The existing F15 plan explicitly keeps standalone20/no budget, while F18's R8
exception is approved only for its integrated runtime. Therefore this option
required this amendment's approval before code or a workload using it. The owner
approved option A, including the acceptance mapping below, before implementation.

Scope:
- Test-harness worker configuration only; no production default/configuration change.
- Keep current disabled behavior intact and retain the old standalone failures.
- Use a separate runtime identifier such as `F15_STANDALONE_R8_OPTIN_V1`; retain the
  unchanged synthetic capability/financial dataset version/digest. Never label a
  changed scheduler as the old runtime or retroactively relabel old W1 as Passed.
- Preserve owner locks, CAS/due fencing, FIFO/eligibility, SKIP LOCKED, leases,
  reset/correction safety, idempotency and every financial/trading assertion.
- No new DB grants/infrastructure, in-memory business authority, pool enlargement,
  process-count increase, command retry or source-freshness bypass.

## Approved acceptance mapping

The owner's approval makes the explicitly recorded R8 opt-in runtime the candidate
runtime for the remaining F15 V19 W1–W4 checks. It changes the runtime under test,
not the load/financial/SLA thresholds. The original no-budget runtime remains Failed.
If the original runtime must itself meet acceptance, do not approve this mapping;
choose option B and preserve20/no budget while developing another plan.

Unchanged criteria:
- W1:100owners×20baseline orders,10commands/s,36cycles/owner,30minutes,18000commands.
- W2:100commands/s,10minutes; original independent overflow/fault checks.
- W3: original4-hour duration and pinned fault schedule; no shortened acceptance.
- Original independent financial oracle, per-cycle60s progress bound, processing
  p95<=250ms/p99<=1s, resource/cleanup/restore assertions and zero Live orders.
- Reuse W4 only where schema/fixture/recovery paths remain unaffected; otherwise
  rerun its original verifier. Never claim F17 history from the F15-only fixture.

## Validation before and after implementation

1. Targeted real-PostgreSQL/shared R8 tests: a non-None claim consumes the budget
   before commit even when later processing fails/defers; None skips do not consume
   it; stale/delayed hints cannot reclaim a later round; same-owner concurrent workers
   serialize safely; other owners progress; cancellation/restart/reset/retry preserve
   identities, money, reservations and positions. Reuse existing dispatch/R8 tests.
2. Verify opt-in/default CLI forwarding, restart configuration and credential
   filtering; manifest names actual candidate/claim limits and runtime ID.
3. Relevant Ruff/format/mypy and changed-source review; no unrelated refactor.
4. One fresh full W1 with unchanged dataset/rates/oracles, explicitly using the
   approved opt-in runtime. Keep all raw failures. If it fails, diagnose and report
   before another run. If it passes, proceed to authorized W2/W3/W4 checkpoints,
   announcing the original long durations; do not treat diagnostic-only evidence
   as acceptance. No commit/push/merge without an owner instruction.

No guarantee of passing is made. This budget does not directly cap failed claim
attempts, and it may reduce throughput or expose fairness issues. Correctness and
all original thresholds take precedence over performance.

## Alternative B — not selected

Keep the original standalone20/no-budget runtime mandatory. Do not implement or
benchmark option A. Use the now captured timing/claim evidence to prepare another
correctness-preserving plan before any further runtime change or workload.
