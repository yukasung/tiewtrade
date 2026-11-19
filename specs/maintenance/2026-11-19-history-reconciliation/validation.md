# Historical branch reconciliation — validation

สถานะ: Execution authorized by owner merge instruction; checks pending.

| ID | Phase | Acceptance | Status |
|---|---|---|---|
| HR-01 | Feature | Four immutable source heads and every source path hash/disposition audited; backup bundle verified | Passed — local review |
| HR-02 | Feature | Normal merges preserve all four heads in ancestry; actual record clearly distinguishes current implementation, retired proposal/prototype and historical experiments | Passed — local review |
| HR-03 | Feature | Final delta only reconciliation documentation/JSON plus owner-approved exact checksum exception; baseline runtime/active specs/locks/artifacts/scanner logic unchanged; no campaign or fixture execution | Passed — local review |
| HR-04 | Feature | Diff/callers review and JSON/link/whitespace checks pass, no blocker | Passed — local review |
| HR-05 | Feature | Final candidate required CI/Security pass with unchanged severity/coverage and exactly one newly owner-approved identity | Pending rescan/required CI — owner approved exact identity |
| HR-06 | Feature | Expected-head merge and postmerge CI/Security pass; clean synchronized main and original/integration refs cleaned only under Git rules | Pending |

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
