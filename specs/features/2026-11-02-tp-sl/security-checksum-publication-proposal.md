# F-17 publication — exact checksum false-positive amendment

สถานะ: **Approved A — เจ้าของอนุมัติ 6 exact exceptions, tests, commit/push และ CI หนึ่งรอบ 2026-11-08**
วันที่:2026-11-08 Asia/Bangkok
Scope: PR63 candidate f5b3449172b4ba1b216bf41ce9e099e9445cb31a only.

## Evidence and problem

Security run42461082621 blocks six generic-api-key identities in three source
manifests, each at lines4and16. Verified all six are SHA256 fingerprints of the
public generated backend contract and frontend types, matching both committed
source bytes and worktree. They are not API credentials. Existing history scanner
still finds the original commit, so removing/renaming the manifests in a new commit
would not resolve it. Preserve the failed result; do not rewrite history.

[Six exact identities, locations and byte-verification proof](evidence/manual-acceptance-fix/security-publication/checksum-verification.json).
No raw credential or raw scanner report retained.

## Approved requirements / plan amendment — NC-F17-SEC-01

Owner approval permits only these six secret false-positive identities in
.github/security/exceptions.json, using its existing schema and exact identity
mechanism. Add reason, actual owner approval and the verification evidence link.
Preserve every existing entry, High/Critical/unknown blocking and all other rules.
No broad path/content ignore, dependency exception, scanner/config/pin/workflow
change, source change, history rewrite, force push or trading activation.
If another identity appears, this approval cannot be extended to it silently.

Reuse the exact identity pattern from the approved security-reference remediation
checksum exception, tools/security/model.py and existing policy/parser tests.
Before editing registry, record owner's actual approval in this document and
feature requirements/plan/validation. Add the six entries only, verify exact set
and evidence proof, and run targeted security policy/parser tests with existing
negative/failure-path coverage. No new abstraction or new infrastructure.

## Validation / continuation on approval

- Registry diff contains exactly six additions matching the verified identities;
  no removed/modified pre-existing entries. Preserve strict scanner verdict rules.
- Existing security policy/parser/failure-path tests pass; an unapproved finding
  remains blocking. Hash proof matches the immutable candidate files.
- Commit/push this scoped correction under the existing publication authorization
  and track one new required CI/Security round on final head/base until finished.
- Reuse unaffected financial/UI/build proof; do not rerun trading workloads.
  Fresh required CI is still mandatory on the published SHA.
- Keep first failed Security run and any other CI failure as historical results.
  Do not merge or mark F17 Completed. Other review/Release dependencies remain.

Owner approval: explicit Option A reply on 2026-11-08. Continue through the scoped registry/tests/publication/CI checkpoint; no merge authorization.
