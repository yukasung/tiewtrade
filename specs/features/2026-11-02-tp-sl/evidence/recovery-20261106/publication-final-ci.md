# Published recovery CI result — 2026-11-07

Published head: `0961f7893226ba1e1641e5138e46f78dbe50f6cf`.
Draft PR: https://github.com/yukasung/tiewtrade/pull/59 . No merge/deploy/Live.

## Required results on that head

- CI https://github.com/yukasung/tiewtrade/actions/runs/42362300917 : Failed.
  Frontend, containers, PostgreSQL config, API contracts and complete browser E2E
  passed. Backend Ruff/format/mypy/import checks passed, then the main pytest run
  reported4756passed /5failed /31deselected in913.35s. Later isolated backend steps
  did not run, so full Feature/required-CI acceptance remains unproven.
- Backend job: https://github.com/yukasung/tiewtrade/actions/runs/42362300917/job/128373126226 .
  Failures: checkpoint real-preflight used the ambient `tiewtrade` name instead of
  its required scratch prefix; one stale-hint test processed a foreign fixture's
  owner; three commit-reply-loss cases hardcoded55432 while CI PostgreSQL uses5432,
  so their injected failure was never reached. Assertions remain valid.
- Security https://github.com/yukasung/tiewtrade/actions/runs/42362300837 : Cancelled;
  aggregate gate Failed.
  Policy, dependencies and all3 CodeQL languages passed. Secrets job128373173552
  exceeded15minutes (GitHub annotation), was cancelled and emitted no manifest.
  Aggregate job128376419616 failed INVALID_POLICY_DATA. Do not call this a completed
  remote secret scan;48118 UUID/checksum matches are separate local probe evidence.

## Prepared local fixture fixes after the remote result

Keep production and assertions unchanged. Reuse the existing fresh DB factory for
all controlled queued-owner tests; allow exactly the2 existing guarded prefixes
(`internal20` and checkpoint `set4_iso`) for owned clones. Checkpoint real-preflight
uses its own actual-role scratch DB. Commit-loss proxies now derive the upstream
host/port from the role engine, matching existing test_worker behavior.

105targeted checkpoint/claim/database/routing/pool cases passed together in23.18s.
Ruff/format passed3changed files; Linux mypy passed5affected source/caller files.
See `publication-ci-fixture-fix.log`, `.xml` and `publication-ci-fixture-mypy.log`.
These local results do not replace remote CI. No automatic third full CI run:
the security policy decision is still required; combine the next authorized fix
before republishing rather than run the same known-blocked gate again.

Prepared security proposal: [immutable evidence handling](../../publication-evidence-policy-proposal.md),
with39specific proposed bindings, all PENDING approval. It includes safe timeout
diagnostics/identity-parity optimization, unchanged deadline, strict exceptions and
negative tests. No registry/rule/severity/timeout change is implemented here.

Next: owner approval of that proposal (or retain the blocker), then the next
combined candidate and required CI. F17 and the internal opening/Release/dependency
gates remain pending. Current remote head remains0961f78 until that checkpoint.
