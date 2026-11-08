# Post-merge pool diagnostic publication — 2026-11-08

Owner explicitly approved Option A for atomic publication, fault/real-DB tests,
normal commit/push, follow-up PR and one required CI round; no auto-merge.
Branch fix/pool-evidence-atomic-publication, base58e2299 (merged PR63).
Approval recorded in the proposal, F17 requirements/plan/validation and owned-pool
amendment before edits. Historical post-merge CI42487118978 Failed is retained.

PoolEvidence.save now stages the exact same JSON in a sibling temporary file,
replaces the final path atomically and cleans temporary data in finally. Existing
readers, schema, pool/overflow/finalized/checked-out criteria, timeouts, sampling,
DB/production financial/runtime behavior are unchanged. Each worker retains its
own evidence path. No new dependency, infrastructure or session/business store.

Validation:
-12 Passed (11.62s): six deterministic incomplete-write/replace/failure cases,
  actual capacity/return/leak proof, both paper/risk worker inventory cases and
  both real CLI R8 parameterizations, including the exact previously failing case.
- During staging, final path is absent or retains previous complete JSON;
  success replaces it with exact expected serialization. Controlled write/replace
  errors preserve prior file, surface OSError and remove temporary data.
- Scoped Ruff check, Ruff format check, mypy (current src path) and diff check Passed.
- Clean isolated DB tiewtrade_e2e_poolatomic20261108, schema current main;
  zero connections confirmed and DB dropped after checks. No owner-account action,
  Live orders, workload/performance campaign or lowered resource/safety criteria.

Unchanged pre-merge candidate e38bf34 had full backend4920/browser42/Security Passed.
On merged58e2299 Security Passed; original browser timeout retained as Failed;
owner-approved3m diagnostic Passed12.5s and E2E-only rerun Passed42. Backend original
race still Failed until new candidate is verified; no old-SHA result substitutes
required CI. Follow-up required CI Pending until observed on publication SHA.
No merge or F17 Completed claim. Release dependencies remain pending.
