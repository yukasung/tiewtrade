# Processing latency population correction — 2026-11-06

Owner selected A after the criteria review: correct the measurement summary and
targeted tests, preserving the workload and250ms/1s/60s thresholds. This checkpoint
contains no production change, workload execution, database mutation or Git publication.

## Implementation

The standalone F15 parent now selects timestamped transactions starting in the
measured interval after baseline preparation and before final drain. Scheduled W3
fault intervals use actual `started`/`restored` boundaries. The shared selector is
moved unchanged from the risk harness into `execution_market/profile_workload.py`;
the old risk import remains available. All raw transaction files remain unchanged.

The interval is half-open: include its start, exclude its end. Keep a selected
transaction's **entire** duration even if it crosses the measurement end or fault
start. Transactions starting during a fault are recorded but excluded from the
non-fault percentile; restoration is inclusive. No extra warm-up/recovery period,
slow-sample removal or fallback to pooled `transaction_seconds` is introduced.
The timer itself still includes connection acquisition, transaction work/finalization
and existing instrumentation; it is not a CPU-only or SQL-only metric.

`processing-window.json` persists the start, end, fault boundaries and attribution.
Failures preserve an Incomplete window and the original failure; they cannot emit a
completed acceptance result. Missing/empty eligible evidence fails. BASELINE remains
PREPARED; the separate negative W2_OVERFLOW case explicitly has no applicable warm
positive-load latency result. Its recovery/economic/resource checks remain, and the
positive W2 performance gate is still mandatory. No old result is relabeled Passed.

## Checks and limitations

- **66 targeted tests passed in5.08s**:16 new population/parent-result cases plus
  existing supervision, standalone runtime and shared risk/fault regressions.
  Parent tests use fake I/O and a controlled clock; they start no real workers,
  database, market feed or timed workload. A redundant function-identity assertion
  and its import were subsequently removed; the behavioral assertions are unchanged.
- Scoped Ruff and format checks passed on all3 changed Python files.
- Mypy passed on the F15 harness and new test file with `MYPYPATH=src`.
- Mypy over all3 files reports **2 pre-existing assignment errors** at the risk
  harness's `f15.submit_new, f15.cycle = fixture.new, fixture.cycle` (current line2116).
  The replacement callbacks lack the optional `poll_gate` keyword in their types.
  A shadow-file check against the saved pre-edit F15/risk files reproduces the same
  2 errors at the old line2139. These callbacks were not modified. This is not a
  clean whole-harness type check and must be resolved before a relevant candidate gate.
- The initial scoped mypy invocation omitted `MYPYPATH=src`, producing88 errors
  dominated by unresolved local package types. Correcting the invocation removed
  those environment errors; it did not remove the2 pre-existing callback errors.
- No production/runtime/stateless/session/storage behavior changed. Production
  file hashes are compared against the pre-edit snapshot in `checks.json`.

## Existing data, no new run

`retained-data-reanalysis.json` applies the same start-time selector to the existing
20-worker diagnostic, from its recorded measurement start through the failing-cycle
deadline. It includes2328 samples, two more boundary-crossing transactions than the
previous fully-contained2326-sample analysis. p95 remains **470.510ms** and p99
**841.634ms**; the p95 target is still250ms. This is analysis of an **incomplete**
run, not new acceptance evidence or proof that all financial/resource criteria passed.
Input file hashes are retained; original artifacts and statuses are unchanged.

## Checkpoint

The authorized measurement correction is implemented and its targeted behavior is
verified. Whole-harness typing retains the2 independently reproduced baseline issues.
F15 workload acceptance and F17 integrated/Release validation remain pending with the
existing Failed/Partial results. No diagnostic or W1 has been rerun.

Next work is to define a bounded performance fix from the retained worker/polling
evidence and address the existing callback typing before the affected candidate
checks. A new runtime change or timed campaign needs an agreed scope under the
three-failure review rule; this checkpoint does not authorize either.
