# Security CI - Compatibility decision after three remote rounds

Date: 2026-11-05
Status: Owner-approved extra attempt passed; compatibility blocker resolved

Current PR: https://github.com/yukasung/tiewtrade/pull/48 (draft)
Current head: 7f35a6c30219ffee536e7ab0dcf93c56fcbe3d71
Security run: https://github.com/yukasung/tiewtrade/actions/runs/42060566269

## Confirmed evidence

- Secret, dependency and policy jobs pass on the current candidate.
- Pinned CodeQL analysis completes, but the coverage adapter rejects actual SARIF
  with MISSING_FILE_COVERAGE. The required aggregate remains red, as designed.
- Local CLI 2.27.4 synthetic Python/JS/Actions reports pass the extraction parser.
  Python/JS injection is Critical; Actions injection is Medium and the safe Actions
  counterpart has zero findings. The first Python/JS counterpart removed eval but
  introduced reflected-XSS, which the scanner correctly blocked; safe counterparts
  are not accepted as passed. No further probe is run without the decision below.
- Local invocation did not reproduce every CodeQL Action interpret-results flag,
  notably --sarif-group-rules-by-pack. The action invokes this flag in pinned
  src/codeql.ts. Diagnostic descriptor references may therefore differ from the
  direct id form in local fixtures. This is an inference, not a proven fix.
- No raw SARIF/database was uploaded, no threshold lowered, no dependency exception
  added, no native setting or main protection changed, and no merge performed.

## Option A - one bounded compatibility round (recommended)

Keep CodeQL Action v4, CLI 2.27.4 and security-extended. Reproduce the exact pinned
Action flags on the existing disposable synthetic database, including grouped rule
components. Inspect only structural metadata locally. Fix diagnostic descriptor
lookup only if this evidence proves id/index/toolComponent representation differences;
otherwise stop and report without guessing. Require missing/ambiguous references,
missing extraction/baseline and failed invocations to stay fail closed.

Run targeted schema/privacy regressions and exactly one further remote candidate.
If it still fails, stop again with evidence. No new scanner, raw upload or relaxed gate.
Expected additional diagnostic time: 5-15 minutes plus remote CodeQL/required-CI time.

## Option B - retain the blocked draft for a separate adapter redesign

Keep PR #48 draft and all protections unchanged. Prepare an approved-plan amendment
for explicit CLI-controlled extraction/interpretation and coverage attestation before
any implementation. This is a larger change, needs renewed design/review evidence and
does not unblock the current candidate. Required CI on the current head is still
monitored to completion; native security gate activation stays pending.

## Rule

AGENTS.md requires stopping and presenting options after the same acceptance
criterion remains unsuccessful for three rounds. The owner must choose before the
next compatibility experiment. Existing CI monitoring and evidence collection may
continue, but no fourth attempt is started automatically.

## Approved bounded investigation result

The owner selected Option A. Reproducing --sarif-group-rules-by-pack,
--sublanguage-file-coverage and --no-sarif-include-diagnostics proved that the baseline
notification IDs become cli/expected-extracted-files/{python,javascript,actions} and
that cli/file-coverage-baseline is telemetry that can be omitted. Extracted-file and
expected-file notifications remain available. This explains MISSING_FILE_COVERAGE.

The adapter now resolves diagnostic id/index/toolComponent references and the actual
expected-file descriptor IDs. Every language requires nonempty expected and extracted
sets, and every expected location must be extracted. Missing, conflicting or invalid
references still fail. Python/JS still require LOC metrics. No diagnostic export,
raw upload, suppression or numeric severity threshold was changed.

Regression: grouped references without telemetry accepted for all three languages;
conflicting id/index rejected; missing expected/extracted sets and omitted files stay
blocked. Local suite: 35 collected, 32 passed, 3 optional scanner probes skipped;
Ruff/mypy/actionlint pass. Real Actions insecure/fixed reports using the Action flags
are accepted structurally and show Medium/zero findings respectively.

One additional remote candidate is now authorized. If it still fails coverage,
stop again; do not start another experiment without an owner decision.

## Result of the authorized extra attempt

Head: 10380f4ee9d7aa99850eba72abe01a2ddb25dddd.
Base: a3a86520bc4d363aa747f5cb934cc09a8fbe71d3.
Synthetic merge: 0717fa8d72d70db71897280b45cb7d57114118b2.
Security run: https://github.com/yukasung/tiewtrade/actions/runs/42062182504

All seven jobs succeeded, including the aggregate. All five safe manifests agree on
head/base/merge/run/attempt/configuration and pass. Coverage: Python 836 files, JS/TS
168 files, Actions 3 files, dependencies 464 inventory entries, secrets 235 commits.
Counts: 0 High/Critical/unknown/Needs Triage, 92 exact approved secret exceptions,
11 Medium Actions findings and 4 Medium dependency records. Medium findings remain
reported under the approved policy. No raw SARIF or database was uploaded.

See remote-candidate-manifests.json for safe manifest evidence. This closes the
bounded compatibility investigation, not Feature validation or merge readiness.
Ordinary PR CI 42062182443 and push CI 42062165730 completed successfully (6/6 each).
Activation/rejection/marker evidence remains open. The owner-approved V-12 amendment
retains actual fork execution as Not Run, an accepted evidence gap.
