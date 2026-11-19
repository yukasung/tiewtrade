# Historical branch reconciliation — merge plan

สถานะ: Owner instructed “merge ทั้ง 4 branches” on 2026-11-19; engineering resolution recorded before merge.

## Scope and authority

Merge the four named heads into one reviewed integration branch, then main through required
CI/Security and expected-head merge. This is historical reconciliation, not approval to
reactivate old product proposals, install prototype packages or rerun validation campaigns.
Use normal merges, not an ours strategy, fabricated commits or force pushes. Preserve original
commits in ancestry and record every source path and disposition. Do not claim that retired
branch trees replace the current implementation. Owner's current merge instruction supersedes
retaining these four branch refs; existing feature approvals and security gates remain binding.

Under AGENTS engineering delegation2026-11-14 choose current approved main for stale/conflicting
implementation and specs. Review evidence before resolving; current F37, LP04 artifact and
withdrawal guard, scanners, exceptions, workflows, financial/session/trading behavior stay exact.
Each normal merge integrates its source inventory, historical purpose and disposition record.
Original source bytes remain available by the recorded immutable commit:path in merged history;
no branch content is silently called applied when its disposition is retired or superseded.

| Source branch | Resolution |
|---|---|
| feature/f37-supported-pairs-management | Retire Oct21 plan/proposal in favor of approved Oct24 supported-symbol-management; retain current mission/roadmap; preserve original history and path hashes |
| security/picomatch-remediation-20261117 | Retain original investigation/prototype history; current PR77/79/80 LP04 bytes, policy and validation prevail. Do not promote blocked/earlier patches, old status or archived campaign source to active files |
| validation/ci-docs-only | Integrate pilot source as explicitly historical text in this record; PR68 was intentionally closed without merge and its temporary fixture is not an active requirement |
| validation/security-ci-rejection | Current security implementation already integrated via recorded squash74ca1f4 and later fixes. Preserve current implementations/specs. Retain disposable PR49 fixture/history by immutable commit references; no lifecycle or marker script promoted to main filesystem |

Existing archive proofs: specs/maintenance/2026-11-18-local-reconciliation/checkpoint.md and
inventory.json. Existing fixed rejection proof: security-ci validation V16, PR49 closed
unmerged. Original branches are backed up in a verified external Git bundle before changes.

## Feature validation and publication

- Before merge: audit all source deltas, verify path SHA256/disposition, validate JSON and
  documentation, assert final tree differs from baseline only under this maintenance folder,
  and verify every source head is an ancestor of the candidate.
- Review actual diff and conflict resolutions. No production code, fixtures, policy or
  assertion change; no new business rule or trading decision. Required CI selection stays
  unchanged. Reuse unaffected runtime/real-DB proofs from main fea1579; no campaign reruns.
- Required CI/Security must pass on final candidate, including full reachable-history secret
  scan with unchanged policy. Any new High/Critical/Unknown/secret coverage blocker remains
  blocked; no exception, suppression or source-history rewriting authorized here.
- Merge by expected head after head/base recheck; follow postmerge CI/Security. Only after
  merged/pushed/green, verify ref heads unchanged, delete the four original refs and integration
  ref; local git branch -d only. Keep verified bundle and final branch inventory externally.
- Preserve existing Failed/Incomplete and F17 Pending Full Validation. Three unsuccessful
  correction rounds or owner time-stop triggers the original stop rule.

Local documentation checks take minutes. The unchanged selector treats new JSON receipts as unknown inputs and runs full CI; main
push always runs full postmerge CI. Expect roughly20–30minutes per round (40–60minutes
total), plus queue/full-history scan variance. No changes to CI rules, receipt formats or
deadlines to avoid those existing checks. No extra requirement/plan approval for a new
product feature is inferred from this administrative merge command.

## Owner-approved exact data amendment — 2026-11-19, before policy edit

Pinned full-history/tree scan found one High identity not in existing approvals. Official
npm/SRI/file-hash verification proves it is a public Vitest4.1.11 source checksum. Owner
approved the exact proposal in security-ci/history-reconciliation-checksum-exception.md
with “approve”. Amend only `.github/security/exceptions.json` by one immutable secret
identity/resolution=false_positive; preserve every prior entry, scanner/coverage/rule,
artifact registry and severity/time budget. This is the sole approved policy-data delta
to the original baseline-preservation rule. Reuse original proof and existing model/tests.
