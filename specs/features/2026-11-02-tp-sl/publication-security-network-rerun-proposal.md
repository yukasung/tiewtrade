# PR63 — Security tool-download interruption

สถานะ: **Approved A — owner explicitly approved one Security-only rerun on the same SHA, 2026-11-08**
Date: 2026-11-08 Asia/Bangkok
Candidate: 2475cc7d03726161d1310318590dd28bb60273ef

## Evidence

Security run42465422723 reports TOOL_NETWORK_FAILURE while installing pinned
workflow validator, secret/dependency scanners and CodeQL JS bundle. Policy
unittests47 passed (four existing skips) before the actionlint download failed.
These jobs have not produced valid scan results; this is not a successful scan
or evidence of no findings. CodeQL Python/actions later Passed; the first attempt finished Failed.
CI run42465422721 continues independently on the same candidate.

The downloader already retries transient reads three times and verifies every
successful archive against the pinned checksum. No bypass, new mirror, new
exception, longer timeout or tool/config/workflow change is proposed.

## Approved bounded continuation

After the current Security attempt finishes, rerun the **entire Security workflow
once on this same run/SHA**, not failed jobs only. All manifests must share the
new attempt identity. Preserve the first failure. Track the rerun and current CI
to completion; do not restart CI or publish another commit just for this result.
Expected Security-only duration3–6min (up to existing job limits), can overlap
with backend tests. Stop/report if the rerun fails. No merge or Completed claim.

Approval required because the approved wallet correction scope authorized one
replacement CI round, whose Security attempt has now failed downloading tools.
No code/config change or rerun has been performed for this proposal.

## Final observed checkpoint — 2026-11-08

- Executed the approved full Security rerun once via gh run rerun42465422723;
  connector only supports individual/failed-job reruns. Same immutable head2475cc7,
  no code/pins/config changes and no main-CI rerun.
- Security attempt2: Failed. Tool-download NETWORK_FAILURE persists for secret,
  dependency/workflow tools and CodeQL JS/actions. Python CodeQL Passed. Policy
  unit tests47 Passed (four existing skips), but policy job Failed on actionlint
  download. Gate correctly Failed. No complete scan result is claimed.
- CI42465422721: **Passed all six jobs**. Backend main4821 + isolated protection54
  + fence1 + optional-limit1 + fresh-global27 + rollback16 =4920 Passed.
  Main suite31 deselected/fivewarnings and isolation-specific deselections remain
  as configured. Browser42 Passed:20+2+7+7+6. All required static/contract/container
  checks Passed. The wallet interruption test now passes on the actual candidate.
- Full CI success does not override failed Security or close F17 Release criteria.
  PR63 remains unmerged. Owner wallet/Live behavior and financial rules unchanged.
- No further rerun or edit authorized. Next: investigate/restore tool-download
  connectivity, then obtain approval for another Security attempt. Do not weaken
  scanner pins/checksums, reuse earlier-SHA manifests, or bypass the gate.

This local record is kept without another document-only publication cycle;
final results are reported with SHA and run links per AGENTS.md.

Subsequent owner decision2026-11-08: NC-F17-SEC-NET-01 [official same-asset fallback](security-release-asset-fallback-proposal.md) Approved A; the prior no-edit/no-rerun boundary is superseded only by that exact scope.
