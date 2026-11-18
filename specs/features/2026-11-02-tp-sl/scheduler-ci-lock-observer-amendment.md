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

## Final candidate47d8042 checkpoint — 2026-11-12

Head `47d804289855a010246567ff463085f2dab488a2`, PR66 remains Open/Blocked,
not merged. All started workflows have completed. Earlier3426b28 Security
43156407926 also completed7/7Passed; its CI never started tests and remains
Failed, not replaced by a success claim.

- [CI43156704084](https://github.com/yukasung/tiewtrade/actions/runs/43156704084):
  Failed solely on browser E2E. Config/frontend/API contract/container/backend
  required verdicts Passed.
- [Security43156703969](https://github.com/yukasung/tiewtrade/actions/runs/43156703969):
  all7jobs Passed on47d8042.
- Backend static checks Passed; main4,907Passed/31deselected/5warnings in901.70s,
  followed by isolated54+1+1+27+16Passed, total5,006passed test executions.
  Original PREPARING scheduler test Passed with the observer enabled.
- [CI lock report](evidence/remaining-paper-20261109/scheduler-ci-lock-47d8042.json):
  Captured,3samples,no errors,no original test exception,untruncated views,
  maximum sampling interval34.852ms. One sample shows coalescer9569 waiting on
  transaction25754 held by coalescer9568, confirmed by an ungranted transaction
  ShareLock versus the holder's ExclusiveLock. At that sample waiter query age
  was8.208ms; this is not total wait duration. Views are sampled separately.
  No200ms timeout occurred in this candidate, so historical CI delay cause is
  still unconfirmed. Self-contention is observed, not a proven performance fix.
- Browser main19Passed/1Failed in2.1min. Unchanged
  `frontend/e2e/realtime-prices.spec.ts:137` expected closeCode after browser
  offline/socket.close, but it remained undefined over5s. Later catalog/F16/F17/
  wallet-risk dedicated E2E steps were Skipped, not Passed on this candidate.
  The browser job never enables/imports the scheduler observer. Private browser
  artifact downloaded; error-context confirms the assertion, but contains no
  event trace explaining close timing. No WS source or test change made.

The authorized candidate attempt is complete. No additional test attempt, CI
rerun or fix was started after its failure. These outcome notes and safe lock
artifact remain local for the next related change; no CI-only document commit.
Existing F17 campaign evidence, Full Validation/manual/dependency gates and
historical failures retain their scope.

**Proposed next scope, awaiting owner instruction:** run only the failed realtime
WebSocket case once on a disposable database with private trace, keeping90s test
and5s assertion limits and all original assertions. Reuse existing isolated E2E
setup/diagnostic pattern; allow approximately7–12min including preparation and
cleanup. Stop/report whether it passes or fails; do not automatically rerun CI,
change source/thresholds, or merge. Choose a fix only after that evidence. This
scope is not authorized by the completed scheduler observer approval.

### Isolated WebSocket trace diagnosis approved — 2026-11-12

Owner subsequently instructed “เริ่มทำ” after the7–12min single-case diagnostic
proposal. This authorizes that one exact original realtime WebSocket case on
disposable PostgreSQL/Redis with private Playwright trace, unchanged90s/5s limits
and assertions, then cleanup and stop/report. No source changes, full E2E or CI
rerun, commit/push or merge are authorized by this diagnostic instruction.
Reuse existing playwright.config.ts, e2e environment guards, real quote producer,
bootstrap/migration and locked dependencies. Keep credentials/cookies/raw traces
private and publish only a sanitized result. Existing local checkpoint edits
are retained; no unrelated code modifications.

### Isolated WebSocket trace result — 2026-11-12

[Sanitized result](evidence/remaining-paper-20261109/ws-isolated-trace-47d8042-20261112.json):
one test, one attempt, retries0, **Passed**, no skips/flaky attempts. Exact unchanged
`e2e/realtime-prices.spec.ts` on47d8042, original90s test/5s assertion limits,
workers1, `--trace=on`, existing config/environment guards and quote producer.
Node22.23.4/Python3.12.15/Playwright1.63.0/Chromium1243 on macOS arm64; frozen uv
sync and npm ci used the committed lockfiles. Cached browser revision matched.
Dedicated temporary PostgreSQL16.15/Redis7, bootstrap/migration and guarded
database `tiewtrade_e2e_pr66_ws`; no other service/container was running at setup.

Playwright measured24.732s, process26.005s, launcher bootstrap/test/cleanup32.096s.
Earlier inspection/dependency preparation time was not separately measured.
Private trace shows offline call ending23232.666ms and the first defined
closeCode evaluation ending23274.912ms with1005, approximately42.246ms later.
That is a sampled upper bound, not exact close-event latency. Reconnection/server
readiness and logout/revocation assertions also Passed; final observed code4401.
No trace contents containing credentials/cookies or raw network frames published.

Cleanup confirmed zero database sessions, normal database drop, dedicated
containers stopped/removed, and no listeners on8000/5173. Source/test/config and
lockfiles unchanged. No production/account/order actions, retry, CI rerun,
commit/push or merge. This diagnostic scope is complete and stops here.

The original Linux CI failure is **not reproduced or explained** by this single
isolated macOS run; preceding suite state/OS/timing differences remain possible,
not proven causes. PR66 required CI43156704084 remains Failed at WebSocket;
backend/Security Passed and later dedicated E2E cases Skipped remain unchanged.
F17 Full Validation/dependency gates remain pending.

Next recommendation, requiring owner authorization: one E2E-only rerun on the
same47d8042 head, retaining backend/Security evidence and unchanged tests/limits
(approximately7–12min). Passing would be current CI evidence, not proof of a
root-cause fix; if it fails, stop with the new evidence. Do not run that attempt
automatically under this completed local-diagnostic authorization.

### Same-SHA E2E-only rerun approved — 2026-11-12

Owner instructed “เริ่มทำ” after the explicit7–12min E2E-only rerun proposal.
PR66 head verified unchanged at47d804289855a010246567ff463085f2dab488a2.
Rerun only the failed E2E execution job and its dependent required verdict in
CI43156704084 once; retain backend/Security and other successful jobs. No code,
assertion/timeout or workflow change, full CI/Security rerun, commit/push or
merge. Follow to completion and stop/report on failure; no automatic retry.
The prior local passing trace does not establish a root-cause fix.

### E2E-only attempt2 completed — 2026-11-12

Same head47d804289855a010246567ff463085f2dab488a2. Approved job rerun targeted
the original failed E2E execution130978338855 and dependent required verdict.
[CI43156704084 attempt2](https://github.com/yukasung/tiewtrade/actions/runs/43156704084/attempts/2)
completed **Success**. Replacement E2E execution131086155107: main20Passed
(1.8min), catalog2Passed(35.3s), F16 sevenPassed(51.0s), F17 sevenPassed(1.0min),
wallet-risk/STOP sixPassed(1.0min), total42Passed. Replacement stable verdict
131089926310Passed. WebSocket original assertions Passed unchanged, no retries
inside Playwright. Other successful CI job results were reused, not rerun;
[Security43156703969](https://github.com/yukasung/tiewtrade/actions/runs/43156703969)
7/7Passed retained on the same head.

`gh pr checks66 --required` now all7Passed. PR66 Open, mergeStateStatus CLEAN,
mergeable MERGEABLE, basef7c94f5; not merged. Original attempt1 WS failure remains
historical; no claim of an established root-cause fix or non-flaky release.
Required-CI checkpoint complete. No source/workflow/threshold changes, new
commit/push or extra attempt. These result notes stay local for the next related
change, not a CI-only documentation commit. Next requires explicit owner merge
command; after an authorized merge follow post-merge CI. F17 Full Validation,
manual/opening and dependency gates remain pending; no Completed/release claim.

### PR66 merged and post-merge checkpoint closed — 2026-11-12

Owner explicitly commanded `merge PR #66`. Rechecked final head47d8042, all7
required checksPassed, CLEAN/MERGEABLE and basef7c94f5. Merged using a merge
commit with expected-head guard, preserving immutable evidence commit ancestry.
PR66 merged at2026-11-12T09:40:48Z, merge SHA
`afb2adb29e416f3e7e71aa0d497c842cb761ba6c`.

Followed both automatic main-push workflows to completion on that exact SHA:
[CI43193597428](https://github.com/yukasung/tiewtrade/actions/runs/43193597428)
**Success**, all11execution/verdict jobsPassed;
[Security43193597263](https://github.com/yukasung/tiewtrade/actions/runs/43193597263)
**Success**, all7jobsPassed. Backend main4,907Passed/31deselected/5warnings in
1,167.25s plus isolated54+1+1+27+16Passed, total5,006passed test executions.
Browser20+2+7+7+6Passed, total42, including WebSocket and sevenF17 cases. No
post-merge rerun or additional source/workflow changes were needed. Waiting for
automatic CI took approximately24minutes from merge to completion.

Merge/post-merge-CI task is complete. Historical failures and uncertain intermittent
WebSocket close timing remain documented; no claim of an identified root fix.
Local outcome/evidence notes are retained without a CI-only document commit or
extra PR. Branch/worktree retained to preserve those uncommitted notes. Remaining
F17 Full Validation/manual/opening/dependency gates keep their previous state;
F17 is not Completed or released. Next F17 work is its remaining approved
validation/dependency checkpoint, requiring the applicable owner instruction;
no further work remains in this merge task.
