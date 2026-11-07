# Recovery candidate publication checkpoint — 2026-11-07

Owner authorized commit/push and required CI after the scoped review fix/refactor.
The recovery commit preserves raw Passed/Failed/Incomplete evidence, including
ignored test logs. Raw diagnostic XML/diffs/logs retain their original whitespace.
Source/spec whitespace checks pass; no historical raw evidence was reformatted.

Integrated origin/main `2f1d047` into the candidate. Conflict resolution retains
the approved UUID boundary fixes, scoped lifecycle/diagnostic tests, amended F17
requirements/plan/validation and current F17 roadmap evidence. Main's frontend
cleanup/security work is retained; mission clarifications from both are preserved.
The six recovery production files retain their reviewed implementation. Main's
other backend changes remove unused APIs/functions; no financial rule changed.

Post-integration Ruff, format and mypy with `MYPYPATH=src` passed all56 affected
Python files; logs `publication-ruff.log`, `publication-format.log`,
`publication-mypy.log`. Retain the prior207/207 mixed test proof where unaffected.
Final integration/full regression is delegated to required CI on the published SHA.

## Known security gate blocker

Local Gitleaks with the unchanged main configuration detects48118 generic-api-key
occurrences in the new evidence history:47305 UUID values (test request/idempotency
identifiers) and813 SHA-256 values (candidate/query fingerprints). No other value
shapes were reported. See `publication-secret-probe.json`. Shape classification is
not an approved exception and does not make the security gate Passed. Raw scanner
matches remain in private temporary storage, not this receipt.

No scanner rule, exception, severity or acceptance threshold was changed. Publish
as a draft for concrete required-CI evidence; do not merge or declare the recovery
candidate/F17 accepted while security or other required checks fail. Handling these
evidence false positives requires a reviewed proposal and owner approval under the
security policy; no broad suppression is authorized by this publication.

Next checkpoint: report final SHA and required-CI run results, including the exact
blocker/logs. No deployment, automated Live order, merge or F17 completion.
