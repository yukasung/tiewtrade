# Exact tree occurrence extension — proposal

สถานะ: **Approved A — owner replied approve,2026-11-07; exact100-identity update/checks/publication authorized, no merge/deploy/Live**
วันที่: 2026-11-07
อ้างอิง: [approved Option A](publication-evidence-policy-proposal.md)

## Observation and stop

The approved implementation completed pinned local full history/tree scanner and
mapping stages in169.73s (history scan99.29s, mapping1.94s, export7.24s, tree
scan48.28s, mapping12.97s). This is local evidence, not required remote CI.
The exception validator then correctly failed EVIDENCE_BINDING_MISMATCH.

The same immutable lines sometimes have different reported Start/EndColumn in
history and tree modes. For example the W1 trace line1067 reports53..96 in history
and53..85 in tree; line1290 reports53..96 versus20..63. Existing identities include
columns, so these are distinct identities even though their line locators agree.
The implementation retains existing identities; it does not normalize or merge
these differences. The underlying scanner cause has not been established here.

Per-file tree reconciliation of all39 fixed blobs found:

| Scope | Count |
|---|---:|
| Original approved history identities |48118|
| Tree identities |48067|
| Tree identities absent from approved set |100|
| Proposed history/tree union |48218|
| Bindings needing updated count/set digest |8 of39|

Every tree matched value was independently verified as a whole/subsequence of an
original UUID or SHA-256 producing JSON value in the same fixed blob;0unmapped
values. No actual credential was tested. The per-file tree count48067 plus91
existing ordinary findings equals the completed full-tree report count48158.
The full-history report count was48209. Count agreement is not a substitute for
the next full identity-set validation.

Complete new identities, columns, paths, original blobs and proposed counts/set
digests are in [the proposed extension](evidence/recovery-20261106/proposed-tree-occurrence-extension.json).
It is not an active exception registry. The old active48118-identity approval is
unchanged. Regression proves a tree column variation cannot silently expand it.

## Option A — approve only these additional100 identities

Authorize updating only the8 affected approved entries to the exact listed union
counts and occurrence-set digests, with this owner approval recorded. Other31
bindings, commit/path/blob/rule, matching code, identity construction, existing
approvals, severity, complete history/tree scans and15-minute deadline stay fixed.
No generalized UUID/hash exception, column normalization or tolerance is authorized.

Then validate the actual registry with a complete pinned local history/tree run;
require exact counts/digests and0blocked/triage findings. If it passes, record the
evidence, publish the combined prepared candidate and track required CI to completion.
Use prior scoped tests/checks in their unchanged scope; run affected registry tests.
If any further new identity or policy gap appears, stop/report without expanding
the approved set. No merge/deploy/Live or F17 completion.

This is the proposed data-only amendment to the approved Option A registry scope;
owner approval of A authorizes the exact update/checks/publication above as one
checkpoint. Estimated check time: local scan about3min, required CI about20–25min,
subject to runner conditions/failures. No trading workload campaign.

## Option B — retain the blocker

Keep the old registry and the PR draft. Local scanning/mapping performance proof
and scoped safety tests remain useful, but exception validation and required CI
cannot be declared Passed. Do not publish another known-blocked candidate merely
to rerun this failure.

## Owner decision

Owner approved Option A on2026-11-07. Apply only the8listed count/set-digest changes,
record this approval, then perform the conditional checks/publication above.
The earlier proposal/failed-scan records remain historical evidence.
