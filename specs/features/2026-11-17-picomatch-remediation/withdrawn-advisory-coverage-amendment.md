# Withdrawn advisory coverage amendment

สถานะ: Approved — owner approved exact withdrawal-guard proposal in this session on 2026-11-18.

PROPOSED AMENDMENT — exact withdrawn Picomatch advisory coverage
Status: Approved before implementation. 2026-11-18 Asia/Bangkok.
Existing feature: specs/features/2026-11-17-picomatch-remediation/.

Problem and evidence
PR79 f78b456 Security dependencies failed TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN.
The existing trusted_findings guard requires GHSA-fc5q-39xc-vjpf High/Critical forever.
Both official GitHub and OSV records mark that exact advisory withdrawn at
2026-11-18T15:38:56Z (22:38:56 Bangkok). Current OSV package/version query returns
no advisory for npm/picomatch/4.0.7. No dependency or policy was changed by PR79.
The original guard must continue rejecting unknown/incomplete coverage; deleting it
or treating any missing finding as success is not proposed.

Concrete requirements and plan requested for approval
1. Limit the new disposition to npm/picomatch/4.0.7 and the exact already approved
   LP04 artifact SHA256 9cc97cff17fcae65f9b7e9b249670d38decc451c0210f34678de608a5e8ff39d.
   Keep installed bytes, archive, parser, manifest, license, lockfiles and all inventory
   verification unchanged. No rollback to vulnerable/unreviewed bytes or new patch.
2. Keep full original pinned OSV coverage of both actual locks plus CycloneDX. If the
   expected GHSA High/Critical is present, retain the existing exact finding path.
3. If the expected advisory is absent, require a fresh bounded HTTPS read of the exact
   official OSV advisory record and exact package/version query during that scan.
   Validate exact id, a well-formed actual past withdrawn timestamp, matching npm
   package/version affected identity in the record, and complete package query shape.
   Require query/result consistency; map and gate every other finding normally.
   Missing/malformed/wrong-id/not-withdrawn/network-error/mismatched/inconsistent
   evidence fails closed. No stale memory cache or generic missing-advisory bypass.
4. The withdrawn record is coverage evidence, not a claim of general regex safety.
   Keep the approved LP04 matching restriction, caller/option reassessment and source
   integrity requirements. No High/Critical/Unknown severity threshold relaxation.
5. Preserve the old exact exception registry unchanged; do not approve a new exception,
   remove findings or fake package identity. Retire only through the existing policy.
6. Record the amendment under the existing feature before code changes, after approval;
   reuse existing scanner helpers and add only targeted coverage/HTTP controls.
   No new infrastructure, Live action, workload or parser campaign.

Validation before publication
- Existing scanner/trusted-source tests and default registry-only behavior remain valid.
- Tests cover exact valid withdrawal, unwithdrawn/missing/wrong advisory, invalid/future
  timestamp, missing package identity, query failure/malformed data/inconsistency and
  any other High/Critical/Unknown finding still blocking.
- Real pinned OSV on both actual locks and exact artifact must provide complete inventory
  and honest current findings. Use current data, not mocked acceptance of real scan.
- Scoped Ruff/types/tests, review/fix/refactor as needed; final required CI, expected-head
  merge and postmerge CI/Security. Preserve PR79 failure and previous advisory history.

Alternative
Keep guard unchanged and PR79 blocked. Private backups/cleanup can finish; no merge
or claim of Security Passed until a separately approved safe solution exists.


Implementation detail recorded before source changes: reuse model object/array/string
validation and scanner inventory/evaluation. Add a small bounded OSV evidence reader;
pass its verifier explicitly from scan orchestration, leaving offline adapter callers
fail-closed by default. No new manifest, parser bytes, package or exception registry.


Scoped implementation/review complete. New verifier is passed explicitly by scanner
orchestration; default offline adapter behavior remains fail-closed. Existing model
parsers/counts and source identity verification are reused. No further refactor is
justified. Local acceptance is recorded in validation.md and withdrawn-advisory-scan.json;
required final-candidate CI and postmerge checks are still pending.


CI diagnostic amendment before further publication: `aaabb15` dependencies failed
with the generic public INVALID_POLICY_DATA code, while the exact merge candidate
identity/configuration check and full real local scan pass. Existing redaction hides
the failing invariant and no raw scanner data is retained by design. Add only known
constant advisory/inventory/candidate error codes to the public allowlist, retaining
redaction for arbitrary exception text and all acceptance conditions. This is a scoped
diagnostic under delegated engineering authority, not a policy bypass or blind retry.
The next candidate preserves both failed attempts and must stop/report if the remaining
error cannot be resolved within the existing three-failure bound.
