# NC-F17-SEC-NET-01 implementation checkpoint — 2026-11-08

Owner explicitly approved Option A for the official fallback, tests, normal
commit/push and one required CI round. Approval recorded in Security CI
requirements/plan/validation before source edits.

- system.py resolves the exact pinned public release asset after transient direct
  download failure. Metadata bounded2MiB/30s, exact filename/URL/uploaded state,
  positive integer ID; binary endpoint constructed from pinned owner/repo and ID.
  No metadata-selected arbitrary URL, token, mirror, cache, new dependency or
  infrastructure. Binary response must be octet-stream and match existing SHA256.
- Shared3-attempt budget, 60s stream timeout,4GiB cap and install/temp cleanup
  unchanged. Permanent HTTP/checksum/metadata failures fail closed without fallback
  retry. Scanner verdict/configuration/exception registries/workflow pins unchanged.
  Per-call retry state is temporary, no shared session/business state introduced.
- Existing tests extended:53 unittest cases OK, four existing opt-in skips.
  Includes transient classes, direct success, binding/duplicate/missing/malformed/
  oversized metadata, invalid IDs/URLs, public headers despite GH_TOKEN presence,
  nonbinary response, wrong hash/no installed partial file, permanent failures at
  each stage and exhaustion without multiplying retry budget.
- Scoped Ruff/format with project100-column config and strict mypy with explicit
  package bases Passed. git diff --check Passed. No financial/owner/Live mutation.
- Real Linux pinned archives all verified using the changed downloader:
  gitleaks8,230,402B and OSV57,725,088B via recovered direct routes;
  actionlint2,080,472B and CodeQL696,320,500B via real504→API metadata→binary fallback.
  All expected checksums matched. CodeQL336.21s; no binary installed or executed,
  temporary archives removed. See fallback-download-results.json for safe routes.
- Earlier direct504 and failed Security attempts retained. Local API success does
  not certify hosted Security. Required CI/Security on publication SHA Pending.

No merge or F17 Completed claim. Existing Batch/Release dependencies retained.
Final CI results will be reported with SHA/run links; no doc-only commit loop.
