# Native3m failure-only browser evidence — 2026-11-08

Owner explicitly approved Option A before source edits: bounded failure evidence,
targeted checks, normal commit/push, new PR and one required CI round; no auto-merge.
Branch fix/chart-3m-failure-evidence from main29e3946 (PR64 merged).

Only executable change is frontend/e2e/candlestick-chart.spec.ts:
- Existing fetch observer records up to32 request lifecycle entries: started,
  headers/body completion, aborted/failed/pending, public path/base/timeframe,
  HTTP/status/row counts and elapsed browser-clock values. Diagnostic truncation
  does not change original completed16/abort16/shape checks or verdicts.
- Failure-only afterEach captures at most16 completed/32 lifecycle entries and
  public selection. Paths/base/TF/status/failure/outcome are allowlisted; unknown
  strings redacted, invalid timing numbers null. No headers, cookies, account
  data, raw response bodies, credential values or arbitrary URL/query retained.
- Read bounded to2s; unavailable marker and attachment errors cannot mask original
  failure. A real JSON output file under test-results is attached by path, so the
  existing CI artifact upload persists it even without HTML/JSON reporter.
- Original30s test timeout, BTC/ETH assertions/READY/precision/no-order checks,
  fixtures, production/API/schema/trading behavior remain unchanged. Title text
  unchanged, now shared with the hook filter. No response replacement or API probe.

Checks:
- Four controlled private cases exercise the exact hook extracted from current
  TypeScript AST, transpiled and registered as a real Playwright afterEach.
  Original assertion/unavailable failures and a deliberate1.5s synthetic timeout
  remain failures (three total); the passing synthetic case has no attachment.
  Three persisted file artifacts verified, two bounded allowlisted snapshots and
  one unavailable marker. Extra sensitive sentinel fields omitted. See sanitized
  controlled-results.json; raw private runner/report never published.
- Initial body-only attachment verification exposed that default CLI reporters
  do not persist body attachments. Corrected to file+path, reran affected private
  proof and verified files exist in artifact output. No product/test criteria change.
- Original affected real-DB3m case:1 Passed (11.2s), unchanged30s. Clean isolated
  PostgreSQL tiewtrade_e2e_3mfailure20261108 and Redis DB10(initial size0), separate
  local ports18013/15113. Later file-persistence edit affects failure branch only;
  successful case evidence remains valid and was not rerun.
- Scoped ESLint/typecheck and git diff --check Passed on final source.
- DB dropped after zero connections; temporary dependency links removed.
  No owner account action, Live order, workload campaign or threshold relaxation.

Intermittent3m root cause remains OPEN. Historical timeouts on58e2299/29e3946
retained as Failed, old successful reruns not called a fix. Current main29e3946
has backend4926/Security Passed; E2E19Passed/oneFailed and later suites Skipped.
This diagnostic candidate still requires remote CI on its actual SHA. If CI passes,
report instrumentation checked, not root cause resolved. No auto-rerun/merge or
F17 Completed claim. Release dependencies unchanged.
