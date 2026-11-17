# REPLAY-05 — correction, review, refactor and test readiness

สถานะ: **Ready for short comparison; performance Not Run** — 2026-11-17

Owner explicitly authorized continuous implementation, review and refactor until ready
to test. No repeated approval requested. No4h campaign, commit/push/CI/merge in this scope.

## Changes and review

- storage.read_execution_inputs: optional scoped immutable SavedExecutionInput continuation;
  total order input_id/generation/decision_kind; rejects mixed/wrong-scope cursor. Scalar
  input-id filter remains compatible but documented as unsuitable for complete pagination.
- Limit narrow keys in materialized CTE before fetching JSON; existing FK/owner RLS,
 4096maximum,decoder/digest and all financial rules preserved. No migration/new index.
- profile_restore.replay_owner_domain passes last_evidence, including ties at4096boundary.
- executions.py authenticates exact evidence ID+timestamp instead of input range/LIMIT1.
  Scoped reader retains key registry membership, full key provenance and original digest
  checks. Complete existing PK join allows indexed registry lookup as history grows.
- ReplayReadObserver records actual composite continuation (input/generation/rebase),
  still task-scoped and original-once, no new runtime process/session state.

Review covered callers, RLS/authorization, transaction lifetimes, cancellation/error
propagation, integrity, duplicate fill prevention, Money/Quantity preservation and
performance implications. Findings fixed: preserve registry membership in exact lookup;
include complete PK provenance for bounded lookup; future runner's foreign-owner probe
must request a nonempty first page, not vacuous end cursor. No unresolved Critical/High
finding identified within this amendment; performance remains unmeasured.

Refactor: reused SavedExecutionInput and existing decoder/fixtures rather than a new
cursor abstraction; explicit None guard, descriptive last_evidence and consolidated
imports. No change to trading behavior or calculation formulas.

## Validation

75 distinct targeted cases covered on applicable final code: latest23pagination/execution
checks Passed;14observer/lifecycle checks retained from immediately prior37Passed run;
38unchanged decoder/evidence checks retained from prior safety run. Proofs include:
INPUT/REBASE and generation ties,1/2/4096pages with no loss/duplicates,complete ordered
baseline equality,full replay oracle counts4097records,strict scalar compatibility,
wrong cursor scope/bounds,foreign owner,repeatable-read append visibility,cross-day
partitions,exact lookup provenance/orphan rejection,digest failure and concurrent fill
retry with exactly one cash/position effect (including tied INPUT/REBASE).

Ruff/format/mypy Passed for6affected source/test files; git diff whitespace checkPassed.
Historical REPLAY04 two failures retained. Intermediate checks68Passed,then73Passed/
1Failed due expected error wording; corrected test to existing normalized error,not
production exception policy. Subsequent37Passed and final23Passed. Individual owned
runs22.32s/26.28s/25.36s/23.39s including setup/cleanup. Rawlogs/pins/summary:
`validation-artifacts/f17-replay05-preparation-20261117/checks-summary.json` and referenced
directories. Independent checks confirm each owned database absent,zero connections/
locks; internal scratch fixture prefix also empty. No owner or Live trade sent.

## Ready next step / remaining limits

Prepared `validation-artifacts/f17-replay05-preparation-20261117/comparison-runner.py`,
with expected final candidate inventory,baseline source and runner hash; syntax and
bindings checked without execution. It reuses reviewed REPLAY03 cleanup/finalization,
original120s preflight,fresh144364-record/two-owner fixture and4096pages. Compare old
reader then new reader once on identical evidence with matching identity/digest streams,
60s per enumeration,900s total including cleanup. If baseline fails stop and retain
partial evidence; no automatic rerun. Read-only first/late EXPLAIN under10s statement
bound; no write or owner leakage. Fixed-order warm-cache effects must be reported;
this is diagnostic,not a performance acceptance claim or full20-owner rebuild.

Expected5–10minutes including preflight/seed/cleanup,maximum15minutes. Ready to start
when instructed; no additional implementation/review/refactor approval needed for this
prepared scope. Keep60s and original safety criteria. Full W3/4h remains Incomplete,
F17 Pending Full Validation; do not infer readiness for four-hour acceptance until
short comparison and applicable prerequisites are evaluated. No change to old results.
