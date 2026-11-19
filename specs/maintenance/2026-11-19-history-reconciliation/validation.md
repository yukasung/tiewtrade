# Historical branch reconciliation — validation

สถานะ: **Publication checkpoint closed — PR81 merged; final pre/postmerge checks Passed, verified 2026-11-19.**

| ID | Phase | Acceptance | Status |
|---|---|---|---|
| HR-01 | Feature | Four immutable source heads and every source path hash/disposition audited; backup bundle verified | Passed — local review |
| HR-02 | Feature | Normal merges preserve all four heads in ancestry; actual record clearly distinguishes current implementation, retired proposal/prototype and historical experiments | Passed — local review |
| HR-03 | Feature | Final delta includes reconciliation records, exact approved checksum exception and owner-approved chart/preflight test-harness corrections; production/runtime/locks/scanner logic unchanged; no new workload campaign | Passed — local review |
| HR-04 | Feature | Diff/callers review and JSON/link/whitespace checks pass, no blocker | Passed — local review |
| HR-05 | Feature | Final candidate required CI/Security pass with unchanged severity/coverage and exactly one newly owner-approved identity | Passed — final candidate CI/Security; exact exception retained |
| HR-06 | Feature | Expected-head merge and postmerge CI/Security pass; clean synchronized main and original/integration refs cleaned only under Git rules | Passed — postmerge and final ref inventory verified |

No new Batch/Release criteria or workload; preserve F17 Pending Full Validation. After approval
and checks follow the standing Git authorization without repeated publication permission.
CI results after publication are reported with exact SHA/run links; no recursive report-only PR.

## Local review checkpoint

Four normal merge commits retain all original heads. Audited130 source-path occurrences;
all active baseline files are byte-identical, only this maintenance directory changes.
Source blobs/SHA256s and explicit retired/superseded/current dispositions are recorded.
No old product proposal, prototype parser, disposable lifecycle/marker fixture or workflow
is activated. Original contents remain accessible by immutable commit:path in ancestry.
Fixed quote-only trailing whitespace during docs check and corrected missing-path verifier
to compare existence and bytes rather than rev-parse error text; no runtime/test criterion change.
Required CI/Security and postmerge closure remain Pending.

## Historical secret-scan blocker

Full scan1bb8ffe:359commits, one High/blocked,48490excepted,0unknown;155.02seconds.
Targeted new-history diagnostic identifies exactly one unapproved occurrence in original
267a677 investigation-summary.json line110. Official npm/SRI/file-hash proof establishes
a public Vitest4.1.11 source checksum false positive. Policy remains unchanged; owner
decision required by security requirements. No PR/push/main merge or ref deletion.

## Approval checkpoint — 2026-11-19

Owner “approve” resolves the single checksum finding decision. Failed initial scan remains
recorded above; no other exception approved. HR03 now permits only this exact policy-data
addition; all remaining protected runtime/spec/lock/source/CI bytes remain baseline exact.

## Approved exception implementation and recheck

Owner approval recorded before policy edit. Registry delta is exactly one secret identity,
resolution=false_positive; previous entries unchanged. Existing policy tests9 Passed and
negative checks keep unrelated High secret/dependency findings blocked. Final diff review
found no remaining finding. Full pinned history/tree rescan on8d20070:360commits,
48491excepted,0High/Unknown/blocked,45unchanged artifact bindings;259.85seconds including
local diagnostic summarization. [Safe scan receipt](approved-history-scan.json).
Required CI/Security on final candidate and postmerge remain mandatory and pending.

## Approved bounded chart correction scope

Owner approved chart3m-next-step-proposal.md after three failed hosted attempts. It adds
only current E2E producer/test composition and regression coverage to the original history
reconciliation delta; production readiness/budgets/source remain unchanged. HR03/04 earlier
Passed statements describe the history-only checkpoint. Current affected local checks and
one new required CI round must pass before HR05/06 can close. No old historical fixture
is activated; the existing active chart FakeVenue source is reused.

## Corrected chart local checkpoint

[Results](chart3m-local-results.json): exact missing-prior causal real-DB proof BTC/ETH,
2process-composition cases/default opt-in/cancellation,4reconnect timeframes, original
native browser case under30s, scoped Ruff/format/strict mypy/frontend lint/types Passed.
Implementation review closed; source/CLI/default callers and actual DB/worker lifecycle
covered. Production APIs/readiness/money/session/schema/locks/CI assertions unchanged.
Only test composition/coverage changes plus the approved historical exception remain.
One new required CI round is next; stop/report if it fails before another hosted attempt.


## Ubuntu preflight continuation — owner approved 2026-11-19

Prior b288645 CI44475468423 failed network preflight before chart/E2E execution;
Security44475468399 passed all7. Follow the approved
[bounded retry amendment](../../features/2026-10-26-ci-feedback-time/bounded-ubuntu-preflight-retry-proposal.md).
Helper local policy/static/Linux tests and review passed; one new required hosted round
is authorized on the final candidate. Stop/report on failure; no automatic extra round.
Main merge and original ref cleanup remain Pending until required pre/postmerge checks.


## Process-group continuation — owner approved before code 2026-11-19

D2aefa1 CI44479026954 failed actual descendant-lifetime assertion before E2E.
[Approved correction](../../features/2026-10-26-ci-feedback-time/privileged-process-group-timeout-proposal.md)
replaces host timeout with same-context Python process-group supervision. Offline Linux30
network cases and local policy71/static checks Passed; reviewed, no open findings. Exactly
one new hosted round is authorized; main merge/postmerge/original ref cleanup Pending.


## Publication and ref closure verified — 2026-11-19

[PR #81](https://github.com/yukasung/tiewtrade/pull/81) final head
`477da21eb2c1e9ad359beeb59a60b2d4645bb5da` passed all 18 reported jobs:
[CI 44480852970](https://github.com/yukasung/tiewtrade/actions/runs/44480852970),
[Security 44480852972](https://github.com/yukasung/tiewtrade/actions/runs/44480852972).
Expected-head normal merge produced `81334aa7e50828382822a2bc0339fe3565ee6991`;
[postmerge CI 44484162505](https://github.com/yukasung/tiewtrade/actions/runs/44484162505)
and [Security 44484162445](https://github.com/yukasung/tiewtrade/actions/runs/44484162445)
Passed. HR-05/06 are closed; earlier Failed/Incomplete results above remain history.

The PR publication record reports verified backup bundles, unchanged source heads,
atomic remote ref cleanup, local `git branch -d`, and owned diagnostic-container cleanup.
Read-only verification here independently confirms all four recorded source heads in
merge-results.json are ancestors of main, all original/integration refs absent, only
local/remote main present, zero open PRs and a clean synchronized starting main. No
new deletion or reactivation of historical fixtures occurred in this reconciliation.
HR-03 now states the final owner-approved harness scope; its earlier history-only
Passed statement applies to the original local checkpoint, not the later approved scope.

No further implementation or validation remains for this administrative scope. Continue
with the separate F-17 Paper opening audit; F-17 remains Pending Full Validation and
its owner acceptance/Release/dependency gates are not waived by this merge.
