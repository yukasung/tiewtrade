# NC-F17-SEC-NET-01 — official Release Asset API fallback

สถานะ: **Approved A — owner explicitly approved official fallback, tests, commit/push and one CI round on 2026-11-08**
Date: 2026-11-08 Asia/Bangkok
Base candidate:2475cc7d03726161d1310318590dd28bb60273ef, PR63

## Diagnosis / limits

[Read-only local diagnostic](evidence/manual-acceptance-fix/security-network-diagnostic/result.json):
GitHub root/API200; all four pinned Linux release/download routes504. All four
release assets exist, uploaded, unique and their URLs match the registry exactly.
Changing User-Agent/no-cache did not fix the routes. Official Release Asset API
returned gitleaks/actionlint binaries200 with exact existing pinned SHA256 matches.
No tool installed/executed by those probes. No token, signed redirect or raw
credential retained. This is local evidence; hosted runner logs only establish
TOOL_NETWORK_FAILURE, not the same exact HTTP cause. OSV/CodeQL fallback downloads
still need real verification. Do not call Security Passed or rerun it prematurely.

## Approved requirements amendment

Allow only an alternate official GitHub API transport to the **same exact pinned
release asset** after a transient direct-download failure. Keep original registry
URLs, versions, hashes, archive members, severity/exception rules and workflow
pins/budgets. A tool is usable only after the existing expected checksum passes.
No mirror, latest-version lookup, token, new dependency, cache, infrastructure,
API/trading/financial change or bypass. This explicitly amends downloader transport
in the approved Security CI plan; the approval to diagnose did not authorize it.

## Approved implementation / reuse

Touch tools/security/system.py, existing tools/security/tests/test_contracts.py,
and approval/evidence docs only. Reuse download_verified/install, current validators,
PolicyError sanitized reporting, pinned registry and existing mocked download tests.

- Keep direct pinned URL as first attempt. On transient HTTP408/429/500/502/503/504
  or network/timeout failure only, remaining attempts may resolve the same asset
  through GitHub release metadata and request its binary via official Asset API.
- Parse only expected HTTPS github.com owner/repo/releases/download/tag/filename.
  Query corresponding public GitHub API release tag (bounded JSON, bounded timeout).
  Require exactly one uploaded asset matching both exact filename and original
  browser_download_url. Require a positive integer asset ID; construct API endpoint
  from the expected owner/repo and ID, not an arbitrary returned URL. Never use a
  caller-selected mirror or credential. Request octet-stream with public headers.
- Share the current total3-attempt budget across transports; no nested retry loop.
  Keep 60s stream timeout,4GiB cap, fresh temporary writes and checksum verification
  for every successful binary. Never fallback on permanent HTTP failure, checksum
  mismatch, malformed metadata, wrong/duplicate/missing asset or nonbinary response.
  Fail closed with bounded sanitized diagnostics. Final archive install unchanged.
- Preserve statelessness: no persistent process memory, global cache or session.

## Approved validation / publication checkpoint

Feature: existing47 policy/parser tests plus focused cases for direct success,
transient fallback/exhaustion, unchanged total retry budget, exact metadata binding,
malformed/oversized metadata, ID/type/path mismatch, no arbitrary URL/token,
JSON-instead-of-binary, wrong hash, permanent failure and no installed partial file.
Run scoped Ruff/format/mypy as applicable, preserving unchanged scan verdict tests.

Verify all four pinned Linux archives via new path against existing checksums;
CodeQL is about696MB. Public downloads only, no Live/owner actions. Budget for
these downloads and targeted checks about3–6min (stop/report on failure).
If all pass, normal commit/push and one required CI/Security round, about20–25min
on the final SHA. Preserve original504 and failed attempts; reuse unaffected
financial proof but never substitute old SHA manifests for required CI.
Stop/report on new failure; no automatic rerun, merge, or F17 Completed claim.
Record approval in Security CI requirements/plan/validation before helper edits.
Owner approval recorded before source edits. Implementation/checkpoint results remain pending until observed.
