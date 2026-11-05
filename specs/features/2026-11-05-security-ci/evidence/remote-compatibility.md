# Security CI - Remote compatibility validation

Date: 2026-11-05
PR: https://github.com/yukasung/tiewtrade/pull/48
Status: Third candidate prepared; native settings unchanged

Round 1, head 8d85f7b, Security run 42055350111: real analysis succeeded for all
three languages; evaluation failed because the adapter assumed artifact analysisTarget
roles and an Actions LOC metric. Secret/dependency/policy jobs passed; aggregate failed
closed. No raw SARIF or database was uploaded.

Round 2, head 7ad75df, Security run 42056387783: safe constant/count diagnostics
confirmed Python/JS metrics and successful invocations, but no analysisTarget roles.
Actions has no LOC metric in the pinned query pack. A separate actionlint download
failure occurred; ordinary CI for superseded candidates is cancelled after replacement.

Verified pinned CodeQL action source: CODEQL_ACTION_FILE_COVERAGE_ON_PRS=true enables
baseline information that the action otherwise skips on PRs. Verified pinned query
sources: <language>/diagnostics/successfully-extracted-files enumerates actual extracted
File facts; CodeQL emits locations through invocation diagnostics. Python/JS baseline
expected-file locations must be covered by extracted locations and LOC must be nonzero.
Actions has no LOC query; its extracted-file diagnostic and baseline execution are
required. Empty/missing baseline, missing extraction, omitted expected files and failed
invocations continue to fail closed. No severity threshold or suppression was weakened.

Pinned CLI 2.27.4 was checksum-verified and run on local disposable Linux-amd64 fixtures.
Real Python/JS code-injection fixtures are Critical and blocked; Actions injection is
reported as Medium by the pinned query; the fixed Actions fixture produces no finding.
Paired fixed Python/JS probes are still pending in codeql-compatibility-probes.json.
Fixture source is never executed; no credential, exchange call or Live order is used.

Added bounded network retries for transient tool-download errors only. Each attempt
starts fresh and must match the pinned SHA256; tampered payloads and permanent HTTP
errors fail immediately. Unit regression verifies retries, checksum enforcement and
secret-free diagnostics. Local suite: 34 collected, 31 passed, 3 optional probes skipped;
Ruff/mypy/actionlint passed. Remote candidate verification is still required.

The next remote attempt is the third compatibility round. If the same acceptance
criterion still fails, stop and present options under the repository's three-round rule.
