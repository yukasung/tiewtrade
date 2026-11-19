# Exact historical checksum finding — owner decision

สถานะ: **Approved — เจ้าของตอบ “approve” 2026-11-19 ก่อนแก้ policy**
วันที่: 2026-11-19

Owner requested merging four historical branches. Their normal-merge reconciliation
candidate preserves current approved runtime/spec/policy files and records every disposition.
Full pinned Gitleaks history+tree scan on head1bb8ffe reports one new High/blocked identity;
existing approvals account for48490 identities. No push or main merge has occurred.

## Exact proposed decision

Approve one `secret` exception with resolution `false_positive` for identity
`808d86552adc67bb2e828b9a68de1091f794e8a542767597ae1c9eacf6ea7c94`.
It binds generic-api-key to commit267a6776a2f1e6b389d2e25c5715b5fe8ccb84d5,
`specs/features/2026-11-17-picomatch-remediation/evidence/investigation-summary.json:110`.
The value is the SHA256 of Vitest4.1.11 public source file
`dist/chunks/cli-api.CnMVyzaz.js`, not a credential. Re-downloaded official npm metadata
and tarball, verified exact SRI against historical package metadata, then verified the
source-file digest equals the historical JSON value. No credential/network trading probe.

[Public checksum proof](../../maintenance/2026-11-19-history-reconciliation/checksum-false-positive-proof.json)
records original blob, package/integrity/source hash and official URLs. No secret value or
raw scanner payload is published. Proposed reason: public source-file checksum under
source_files_sha256; the cli-api filename and digest triggered generic-api-key.

If approved, add only this identity to the existing `.github/security/exceptions.json`
with explicit owner approval and this evidence link; retain all rules, full history/tree
coverage, exact artifact registry, severity gates and time budgets. Re-scan affected
history/tree and run required CI/Security on final candidate and postmerge SHA before
branch deletion. No broad path/rule exclusion and no approval of other future occurrences.

If declined, all-four merge remains blocked; alternatives are keep the historical
picomatch branch outside main, or explicitly authorize retirement/deletion with verified
backup instead of merging that history. Rewriting the original commit to evade the
finding, false clean claims or bypassing Security is not an option.

## Needs Clarification

Owner decision on this single false-positive exception is outstanding. It blocks
publication/merge of the complete four-branch candidate; general merge authorization does
not change the existing explicit owner-approval requirement for new exception identities.

## Owner approval — 2026-11-19

Owner replied “approve” to the exact one-identity false-positive proposal above. This
resolves the Needs Clarification for identity808d86552adc67bb2e828b9a68de1091f794e8a542767597ae1c9eacf6ea7c94
only. Earlier pending statements retain the preapproval history. Add the exact registry
entry, targeted policy verification and unchanged full-scan/required CI/postmerge gates;
no blanket rule/path suppression, source-history rewriting or other exception authorized.
