# Security gate helpers

Python 3.12, standard library only. Policy source of truth:
[`requirements.md`](../../specs/features/2026-11-05-security-ci/requirements.md) and
[`plan.md`](../../specs/features/2026-11-05-security-ci/plan.md).

Run offline contracts from the repository root:

```sh
python -m unittest discover -s tools/security/tests -v
```

Install checksum-verified tools into a temporary directory, then opt into real
scanner probes (Gitleaks synthetic temporary Git history; OSV network scan of both
application lockfiles):

```sh
python -m tools.security.cli install --tool gitleaks --directory /tmp/security-tools
python -m tools.security.cli install --tool osv --directory /tmp/security-tools
SECURITY_SCANNER_PROBES=/tmp/security-tools python -m unittest discover -s tools/security/tests -v
```

A scanner probe passing means its invocation/schema/coverage contract worked. It
does **not** mean the repository has no vulnerabilities. The workflow separately
applies policy and fails on unresolved secrets, High/Critical and unknown severity.

The workflow provides candidate/run identity via GitHub environment variables.
For PRs, helpers verify the synthetic merge parents and current PR API state before
and after scanning. Partial reruns across different attempts cannot combine stale
manifests; rerun the whole workflow when the aggregate reports missing components.
The configuration digest includes pins, configs, helper sources and workflow.

Public summaries contain severity, identity and locator metadata only. Locator order:

- Secret: rule, originating commit, relative path, start line, end line.
- Dependency: ecosystem, package, version, advisory ID (aliases may be separate records).
- CodeQL: language, rule, relative path, line. Coverage is analyzed source file count;
  nonzero CodeQL lines-of-code metrics are also required.

Raw scanner reports and diagnostics stay in temporary local storage; the workflow
uploads only manifests with one-day retention. It never uploads raw SARIF or CodeQL
databases. CodeQL action logs/redaction still require remote validation before
activation. Never attach raw reports when recording a potential real secret.

`exceptions.json` starts empty. An entry must contain exactly `kind`, `identity`,
`resolution`, `reason`, `approval`, `evidence`; identity comes from the safe summary.
Secret resolutions: `used_in_tests`, `false_positive`, `revoked`. Dependency/CodeQL:
`false_positive`, `owner_exception`. Approval/evidence reference the owner's exact
review and redacted proof. Nonempty strings are structural validation, not proof of
human approval: the owner must review each registry diff before merge. Never add an
exception just to make onboarding pass. A new occurrence/content/package version
requires a new decision. Rename boundaries are treated as new occurrences, including
a move away and back; history scanning disables rename collapsing so a subsequent
deletion does not hide the moved occurrence.

CVSS metadata validation supports v3.0/v3.1 and v4.0 vector metrics without computing
scores. Unknown versions/types, malformed or duplicate metrics and incomplete base
vectors become Needs Triage; CVSS v2 is currently unsupported and fails closed.
OSV remains the sole source of the numeric group score.

The two code-review findings are fixed and the authorized refactor is complete.
Remote validation and activation remain pending.
No helper changes GitHub settings, rotates credentials, sends orders or installs
application dependencies. Native settings and required-check activation follow the
approved plan only after review and the owner's Git instructions.
