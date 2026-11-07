# Approved Option A implementation — 2026-11-07

Owner replied approve to the immutable-evidence/security-timeout proposal. Security
requirements/plan/validation amendments are recorded before implementation.
No trading logic, scanner rules, workflow timeout, severity or coverage exclusions
changed. No merge/deploy/Live or F17 completion.

## Changes and safety

- Scan-local Git metadata caching and bounded512-line blame batches preserve the
  original occurrence identity/locator, birth/rename/reintroduction and fail-closed
  semantics. Neither source/secret text nor business/session state is cached.
- Stage observations expose only constant stage names, elapsed time, status and
  counts. Raw scanner/error content stays private; complete history/tree scanning
  and the15-minute CI budget remain binding.
- Exactly39 approved immutable commit/path/blob/rule bindings cover48118 reviewed
  occurrences. All values matched producing JSON fields (test keys/source digests)
  and the fixed blobs. A digest of sorted expected occurrence identities binds the
  exact set as well as its count, preventing same-count substitution. This digest
  is independently derived from the original scanner report/approved blobs, not
  inferred from whichever findings happen to pass the new parser.
- Existing exact approvals/counting remain. New/renamed/changed-content findings,
  unknown/duplicate/tampered data, missing approvals and mismatched identity sets
  cannot borrow approval. The policy configuration digest includes the registry.
- Public summaries group only those resolved approved artifact rows, with explicit
  binding/count metadata; all unapproved findings remain reported and blocked.
  The existing900KiB public-output bound is unchanged.

## Scoped evidence before full candidate scan

Original and optimized implementations give identical identities/locators on147
existing occurrences, in both history/tree modes. The original sample used147 Git
calls for history and441 for tree (3.428s /13.053s). Optimized sample0.806s /2.745s.
These are local bounded measurements, not a reconstruction of the exact remote
timeout phase. Safe stage observations now separate complete-scan phases.

Policy tests:46run,42passed/4opt-in skipped; pinned real Gitleaks probes3passed
separately (history/tree, rename/reintroduction, and new credential inside approved
file plus new UUID-shaped credential outside it). Unchanged OSV network probe is
not rerun locally; required remote dependency scan remains mandatory.
Ruff/format passed7 affected files; strict mypy passed6 affected source/test files.
The separate prior CI-fixture fixes retain105passing targeted cases.

Full pinned local history/tree scan, actual-registry resolution and bounded public
summary checks must complete before pushing the combined candidate. Their receipt
will be added before publication; required CI on the final head remains pending.
Historical Failed/Incomplete runs remain unchanged.
