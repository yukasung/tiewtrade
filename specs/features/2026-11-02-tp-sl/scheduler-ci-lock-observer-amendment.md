# PR66 scheduler CI lock observer

สถานะ: **Approved — เจ้าของสั่ง “เริ่มทำ” วันที่ 2026-11-12 หลังเสนอเก็บหลักฐาน lock บน CI ก่อนเลือกวิธีแก้**

## Scope and reuse

Extend only the diagnostic checkpoint for the unchanged indicator scheduler
PREPARING test blocking PR66. Existing F17 requirements/validation and trading
rules remain unchanged. Reuse the exact test/coalesce calls and PostgreSQL
`pg_stat_activity`, `pg_blocking_pids`, `pg_locks` observation patterns from
`backend/tests/services/indicator_builder/profile_fair_scheduler.py` and the
owner-approved local diagnostic receipt. Existing helpers access raw query text
or require different workload guards, so they are not imported into this narrow
test observer. Reuse SQLAlchemy async engines and existing test-admin URL; add no
dependency, schema, persistent business state or infrastructure.

## Implementation and validation

- Opt-in report path in backend CI; only the PREPARING parameter uses a separate
  admin observer matching migrator host/port/database. Observer transactions are
  read-only. Do not change builder sessions, role privileges or timeouts.
- Poll at10ms for at most2s/200 samples. Bound startup/sample/cleanup separately;
  retain type-only errors and incomplete status. Record sampling intervals to
  expose event-loop observation gaps. Observer must not mask the original test
  exception/cancellation or change original assertions, retry or test outcome.
- Allowlist numeric PID/blockers, role/state/wait metadata, transaction/query ages
  and lock identities. No SQL text/parameters, credentials, account identifiers
  or exception messages. Limit each database view to64rows and mark truncation.
- Preserve a bounded JSON artifact on success or failure for7days using existing
  upload-artifact action pattern. This is diagnostic evidence, not a new test
  acceptance rule. Missing/incomplete observation does not prove no contention.
- Test matching-target guard, redaction/allowlist, caps, read-only setup, observer
  errors, original failure/cancellation preservation and resource disposal. Run
  exact PREPARING case on disposable PostgreSQL with opt-in enabled, then scoped
  Ruff/format/mypy. No production or unrelated test fixes in this amendment.
- Combine existing local checkpoint/status evidence, commit/push same PR66 and
  follow one candidate's required CI. Expected CI20–30min. Do not merge. If this
  candidate fails, inspect its evidence and stop/report before further changes
  or another CI attempt. Do not relax timeouts/assertions or add retries.

The local passing diagnostic does not establish the reason for the failed CI
wait>200ms. A passing CI attempt does not establish that root cause or close F17
Full Validation/dependency gates. Preserve all earlier Failed results.

## Local implementation checkpoint

Observer helper and15fault/redaction/bounds/resource tests added; exact original
test gains only the opt-in fixture parameter, no assertion/coalescer changes.
CI enables the path and retains the bounded report with upload-artifact. No
security registry, production, schema or dependency change.

Disposable PostgreSQL16.15: all four original control modes plus15observer tests
Passed19/19 in1.05s. Captured three snapshots without observer errors, cleanup
zero connections and database/container removed normally. After tightening the
collector's total deadline, the15affected observer cases Passed again in0.14s;
SQL/fixture behavior unchanged, real-DB proof retained. Scoped Ruff/format/mypy
Passed. CI policy58Passed; security evidence/policy21run,20Passed/1optional
scanner testSkipped. System Python3.9 could not import tomllib for security
checks; rerun on the repository's Python3.12.15 Passed as above. Initial mock
context-manager/type-resolution issues were corrected before publication.

No actionable finding in the scoped inspection of original outcome preservation,
read-only observer setup, retained bounds/allowlists, fixture activation and
cleanup. Existing local sync/failure/diagnostic receipts are combined with this
related publication, not a separate documentation PR. Required CI on the new
candidate remains pending; a4217a1 failure and the unconfirmed CI root cause are
retained. No claim that local Passed resolves the prior CI failure.

## Candidate3426b28 — workflow validation failure / proposed correction

[CI43156400968](https://github.com/yukasung/tiewtrade/actions/runs/43156400968)
Failed before any CI job/test started. `runner.temp` was incorrectly placed in
job-level `env`; that context is permitted in step-level `env`, not job-level
`env`. Local actionlint1.7.12 confirmed the precise error at ci.yml104:49.
Earlier58CI policy tests did not validate context availability. No scheduler
test/lock observation or isolated database validation ran on GitHub for this
candidate. Prior a4217a1 scheduler failure remains unresolved.

**Proposed, not applied:** move the single report env variable from backend job
env to the existing main pytest step's env. Artifact path remains unchanged.
Exact reviewable patch: `/tmp/tiewtrade-actionlint-1.7.12/workflow-context-fix.patch`.
The corrected temporary workflow passes actionlint1.7.12 (shellcheck integration
disabled because unavailable; not a shell check claim). The repo workflow is
still unchanged on3426b28. Existing15observer/static and19real-DB/mode proof
remain valid because this correction changes only CI env expression placement.

Next proposed authorization: apply only that env placement correction, run
actionlint/diff check, combine this related evidence, commit/push samePR66 and
follow one new required CI/Security candidate (approximately20–30min). No
production/test/timeout/assertion changes, automatic rerun or merge. Must obtain
owner approval before proceeding: this amendment explicitly requires
“If this candidate fails, inspect its evidence and stop/report before further
changes or another CI attempt.” GitHub Security for3426b28 is monitored to
completion independently of this stopped CI attempt.

### Correction approved A — 2026-11-12

Owner explicitly approved moving the report variable to step env, related
commit/push and one new required-CI candidate. Applied only that reviewed env
placement correction to the repo workflow; actionlint1.7.12 and diff check
Passed. Earlier “Proposed, not applied” text describes the preapproval checkpoint.
Original observer tests/SQL/timeouts/assertions/production unchanged; valid local
proof retained. New candidate CI pending, no merge authorized. Stop/report after
this candidate on failure; no automatic additional attempt.
