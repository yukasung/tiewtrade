# F-20 — Implementation checkpoint

2026-11-19 · feature/f-20-bot-lifecycle · HEAD 31c9146 + working tree · Python 3.12.15

M1 in progress. Added pure lifecycle transitions, shared strategy input and decision
contracts, scoped intent validation, and an exact versioned document codec.

Local checks from `backend/`:

- `pytest -q tests/core/test_bot_contract.py tests/core/test_trading_stops.py` — 14 passed.
- Ruff and mypy on both new modules and their contract tests — passed.
- `python -m tests.purity` and `lint-imports --no-cache` — passed, seven import contracts kept.

V-01..04 remain Partial. The local tests cover deterministic evaluation, exact
Money/Quantity roundtrip, mismatched document versions, missing indicator input,
wrong-mode intents, and the separation between stop, readiness, and resume.
Strategy registry pinning, execution feedback, integrated source readiness, and
the complete lifecycle matrix still need evidence. M3–M5 and all Batch/Release
criteria remain Not Run.

## M2

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- Migration 0067 upgraded from scratch, downgraded empty to 0066 and upgraded again.
- After a control request committed, downgrade refused as designed. The revision
  stayed at 0067, the request was preserved, and forced RLS remained enabled.
- Targeted pytest passed 16 cases across the bot inbox, core contracts and stop
  rules. Two database sessions submitted the same key and recovered one request.
  A changed payload conflicted. Foreign owner and wrong-mode lookups returned
  no receipt. The role test confirmed API cannot update runs and the engine
  cannot update pinned strategy versions or decision facts.
- Ruff and targeted mypy passed. Import-linter kept seven contracts.

V-06 and V-17 remain Partial. The receipt test recovers stored requests through
a new database transaction. HTTP response loss, applied/rejected worker results,
active-slot contention, Paper command linkage, and rolling compatibility still
require evidence. Execution and UI integration remain in progress.

## M2 claims and decision journal

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- Targeted pytest passed 17 tests for the inbox, scope, core contracts and stop
  rules. A worker with an expired lease could not finalize after takeover.
- The decision journal test and three inbox tests passed together. Injecting a
  failure after the first real Paper command insert rolled back the command,
  decision and checkpoint. A successful retry created two commands and links.
  Replaying the same input in another transaction did not create a command.
- Ruff and targeted mypy passed. Import-linter kept seven contracts.
- The first journal integration run hit PostgreSQL SQLSTATE 42P08 because one
  bind was inferred as both UUID and text. The event now uses a UUID cast and
  the affected test passed on rerun.

V-07/08 are Partial. The test uses the real Paper command writer through a
fixture adapter. It does not validate production bot admission, process-kill
recovery, ordering of market inputs, or execution feedback. No production
composition calls this journal yet. M1 lifecycle coverage and the remaining
M2 tests, including active-slot races, still need evidence. M3–M5 remain open.

## Paper slot and authority

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- Six targeted tests passed across bot decision writes, request claims, owner
  isolation and the existing platform stop regression. The tightened slot test
  passed separately for STARTING contention and PAUSED, RECOVERING and STOPPED
  retention. A Paper slot and a simulated Live database slot were independent.
- The real Paper worker rejected a decision-linked command whose run stopped
  after queueing. No order or reservation was created. Ruff and targeted mypy
  passed and import-linter kept seven contracts.
- V-05 and V-09 remain Partial. Replacement, flatness and restart races still
  need evidence. The worker currently checks linked queued commands at
  admission. Legacy unlinked BOT fixtures still enter the pre-F-20 path.
  Before V-09 can pass, migrate the affected fixtures and require the link
  for all BOT intents. F-20 remains inactive. Matching, risk and protection
  integration after admission and the UI are still open.

## Paper BOT lineage

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- Paper worker now rejects a queued BOT command without a decision link,
  or whose linked run, account use or episode is ineligible. The integration
  test verified that an unlinked request creates zero orders and reservations.
- The F-18/F-19 fixture now creates lineage through the real decision journal.
  Platform stop still cancels the accepted BOT order and preserves the
  accepted manual order. The same fixture is used by BOT-only submissions in
  the shared workload helper. Profiles, assertions and thresholds are unchanged.
- The first targeted run passed six cases and detected a fixture SQL binding
  error in the stop regression. The fixture now binds its JSON through CAST
  and the affected Stop regression passed on rerun. Ruff and targeted mypy passed.

V-09 remains Partial. Full approval still requires production bot admission,
risk and execution feedback evidence. The changed workload fixtures have static
coverage. No scheduled acceptance or timed campaign was run in this checkpoint.

## Paper risk and protection

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- Six targeted cases passed for existing TP/SL execution, the BOT protective
  exit after a loss stop, and rejection of an unlinked BOT command. The exit
  uses a matching F-17 immutable command link and still passes the existing
  protection allocation and risk checks.
- Four bot decision cases passed, including rejection before enqueue when the
  owner has no loss limit. A separate configured-risk integration passed:
  the actual Paper writer filled one linked decision, wrote one position
  event, debited 100 USDT, and left zero active reservations. Earlier
  test attempts used the admission receipt as fill evidence and counted
  zero-balance reservation rows as active. The corrected test reads the
  matching projection and asserts that reservation amounts are zero.
- Ruff, targeted mypy and import-linter passed.

V-09 and V-13 remain Partial. The test evaluates control and execution with
injected strategy outcomes. Production strategy orchestration, BOT bracket
intake and the F-17 CLOSE_AND_STOP branch are still open. The existing F-17
worker handles ordinary linked protection exits but does not yet execute
CLOSE_AND_STOP when BOT setup fails. No Ready for Code Review checkpoint has
been reached.

## BOT bracket

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- Strategy decisions now carry optional, typed protection prices attached to
  a specific BUY. Required protection with no matching bracket is rejected.
- Migration 0068 adds one immutable source link for protection, preserving
  the existing manual request source. Empty upgrade/downgrade/re-upgrade
  passed. Populated downgrade refused and left 0068, three linked groups and
  forced RLS intact.
- 13 targeted tests passed for bot decisions, F-17 execution and core
  contracts. The full and partial variants passed together afterward:
  Paper protected 0.999 BTC on a 1 BTC gross fill and 0.3996 BTC on a 0.4 BTC
  gross fill. Both started with zero protected quantity before execution.
- Core contract checks, Ruff, targeted mypy, purity and seven import contracts
  passed.

V-13 remains Partial. BOT setup failure CLOSE_AND_STOP and worker feedback into
the durable run remain open. The Paper scheduler and API/UI are still pending.

## Stop and API

2026-11-19 · HEAD 31c9146 + working tree · PostgreSQL 16 / isolated Redis

- Final TP/SL setup failure recorded a SYSTEM stop and durable close quantity.
  After fresh evidence returned, the real Paper worker sent one reducing
  command and closed the protection allocation. The test starts from the final
  approved setup attempt and injects the temporary failure at validation.
- Owner F-19 stop projected STOPPED and its cause onto a durable Paper run.
  Strategy decisions check pending and applied trading stops before saving
  a new decision.
- API exposes status, stop reason and receipt recovery by key or ID. HTTP
  tests passed authenticated status, CSRF, mode and owner isolation, and
  closed admission without a published strategy. Paper and Live UI use
  scope-separated status queries and the existing Kill Switch controls.
- 32 backend targeted cases passed across HTTP, route classification, Paper
  decisions, and F-17 regression. A separate claimed-start test passed after
  normalizing database UUIDs at the RiskScope boundary. It verified the
  pinned configuration and durable STARTING receipt.
- 38 frontend component tests passed. Frontend typecheck, targeted ESLint,
  backend Ruff and mypy, OpenAPI/type generation and import boundaries passed.

Remaining before Ready for Code Review: the production registry and worker
composition, evaluation/recovery loop, replacement and resume proof handling,
catalog withdrawal consumer, and the complete integrated Feature checks.
The POST route currently fails closed. The database start operation is
covered through test configuration only. V-09/10/13/14/16 remain Partial.

## Worker control and quote input

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16

- The bounded worker control round applies an allowlisted Paper configuration
  after the existing wallet, catalog and risk checks. A removed configuration
  gets a durable refusal. Registry resolution requires the exact pinned
  implementation/configuration/state versions.
- A test strategy explicitly registered for quote inputs went from STARTING
  to RUNNING and committed one decision. A repeated trade input resolved to
  the original decision. Disabling the admission gate persisted PAUSED;
  restored readiness resumed the run without another decision. Running under
  a registry without the pinned implementation persisted an F-19 SYSTEM stop.
- Nine targeted bot decision tests passed before the pause addition. The
  affected integrated control/quote test passed again with pause and recovery.
  Ruff, targeted mypy and the import contracts passed.

V-01..04/08/10/11 remain Partial. The quote input path is explicit and
supports strategies without indicator dependencies. An automated input
scheduler, indicator and fill feedback adapters, restart reconciliation,
replacement/resume proofs, and the durable F-37 consumer remain open.

## Catalog consumer, scheduler and recovery

2026-11-19 · HEAD 31c9146 + working tree · separate PostgreSQL 16 databases

- F-37 withdrawal discovers only run hints across users and modes, then records
  an owner-scoped, immutable acknowledgement and stops each matching run.
  Isolated catalog test (1 passed) used the real removal operation and verified
  two affected runs, unaffected-pair isolation, idempotent replay, and a Partial
  F-37 effect with two stopped bots. No Live order was sent.
- The bounded Paper sweep rotates by run ID. PostgreSQL leases serialize worker
  takeover. The replacement worker rechecks wallet and order reconciliation,
  deduplicates a previously consumed quote and prevents the old worker from
  evaluating. An owner-confirmed F-19 resume moves the same run to RECOVERING.
- Nine targeted bot tests passed on a separate migrated database. The first
  attempt to share the catalog database with these tests counted a pre-existing
  run from the other tests. The fresh-global test passed on its isolated database.
- Migration 0069 empty downgrade/re-upgrade, Ruff, targeted mypy, import contracts,
  generated OpenAPI/types, frontend typecheck and targeted ESLint passed.

V-08/10/12/17 remain Partial. The catalog sweep and Paper quote scheduler are
implemented as bounded rounds. Remaining gates include atomic replacement,
system-stop resume proofs, execution feedback and indicator inputs, rolling
worker composition, and the full integrated Feature validation. F-20 has not
reached Ready for Code Review.

## Replacement, strategy recovery proof and receipt intake

2026-11-19 · HEAD 31c9146 + working tree · isolated PostgreSQL 16 and Redis

- Replacement can apply the accepted F-19 acknowledgement, retire the old
  run and create a STARTING run in one transaction. The worker never projects
  the old run into RECOVERING. Stale summary proof preserves the stop and
  original slot. Both targeted database cases passed on migration 0070.
- A strategy SYSTEM stop only becomes eligible for owner resume after the
  worker successfully probes the pinned strategy against current inputs.
  Version, stop identity, financial and catalog revisions, market watermark
  and quote expiry bound the evidence. The integrated probe test passed and
  produced zero orders. No proof is accepted for protection failure or other
  unsupported SYSTEM causes.
- Paper feedback reads immutable, linked order events in per-order sequence.
  Full and partial fill tests read the ACCEPTED event before the execution fact
  and verified the gross quantities using the real Paper writer. Three
  targeted cases passed. The scheduler consumes feedback only for strategies
  that explicitly declare it.
- With a test deployment allowlist, the HTTP start route persists a request,
  recovers it by key and refuses a conflicting payload. The default remains
  closed. Twenty API and routing tests passed.
- Fourteen targeted bot/core cases passed on 0071 before the feedback change;
  affected full/partial/protection cases passed afterward. Empty migration
  downgrade/re-upgrade checks passed. Ruff, targeted mypy and architecture
  gates passed for the affected files.

F-20 has not reached Ready for Code Review. Indicator-based scheduling does
not yet consume prepared F-11 data. The start and replacement UI controls,
complete feedback state coverage, rolling-worker verification and final
integrated Feature checks remain incomplete.

## Implementation fixes and deep code review — 2026-11-19

Candidate: `feature/f-20-bot-lifecycle`, HEAD `31c9146` plus the current uncommitted
tracked/untracked working tree. No commit, push, merge, deployment or Live order.
This review covers the current candidate; it does not certify F-20 complete.

### Scope and changes verified

Reviewed the approved requirements/plan/validation, tracked diff, new F-20 source,
migrations 0067–0071, generated contracts, tests, and affected matcher, protection,
risk/stop/catalog, owner-session and UI callers. Checked single writer, PostgreSQL
persistence, RLS/grants, transaction boundaries, immutable facts, idempotent identities,
Paper/Live isolation and default-closed activation.

Closed implementation findings in this checkpoint:

- A stopped run previously blocked a linked reducing SELL as well as BUY. Preserve
  exact BOT lineage for SELL and the immutable F-17 exit exception, while denying
  new BUY when run authority is blocked.
- Accepted BUYs in a shared pair checkpoint could be driven by another command
  after the run paused. The writer now supplies blocked order IDs to the existing
  pure matcher. Real-DB regression verifies two accepted orders, unchanged wallet,
  retained reservations and zero positions while paused, then exactly two fills
  and 180 USDT spent after readiness returns.
- Pure evaluation held financial locks. Snapshot preparation now commits before
  evaluation; a second owner transaction reassembles and compares run revision,
  lease generation, immutable state/config and full input before committing either
  a decision or a strategy-error stop/proof. A real-DB stop committed between these
  phases invalidates the result and leaves decision/order counts unchanged.
- StrategyInput lacked caller-supplied scope/run/input identity for deterministic
  order IDs. Added strict immutable context and Paper/Live parity tests, including
  a different run producing a different key without clocks/randomness.
- Normalize asyncpg's UUID subclass at the DB-to-core boundary; strict core UUID
  validation remains intact. Scheduled evaluation/recovery now passes.
- Account-source unavailability pauses a run, rather than escaping as a strategy
  failure. Per-run admission/conflict failures defer without abandoning other owners.
- The bot panel now reuses the F-19 stop journal/control/summary, shows verified
  holdings and actual protection allocation/state, distinguishes unavailable
  exposure, and provides a safe status-error retry. Start remains disabled and
  Live remains unavailable. No raw exception is displayed.
- Paper isolation gate now scans F-20 source and its transitive dependencies, with
  explicit internal imports and all existing network/secret prohibitions retained.

### Latest checks and retained failures

Environment: disposable PostgreSQL 16 (`tiewtrade-f20-review`, then fresh
`tiewtrade-f20-final`), separate Redis 7, Python 3.12 virtualenv, local frontend
Node/npm. Migration upgrade to 0071 succeeded. No existing development database
was reset. Tool elapsed times are recorded where available; total editing/review
wall time was not measured and is not represented as a benchmark.

- Initial affected backend group: 136 passed before the final snapshot/context/UI
  changes. Its unchanged financial/protection assertions remain useful evidence.
- Final selected group has 153 cases: core strategy 41, matcher 48, risk matcher 6,
  bot inbox 3, bot integration 12, protections 13, risk stops 9, bot API 4 and route
  classification 17. The fresh group passed 152 with one scheduler lifecycle case
  failing. After the targeted UUID correction and test-call fix, that exact lifecycle
  case passed, including recovery and the new stop-between-transactions assertion.
  This is combined targeted evidence, not a claim of one all-green final full suite.
- Earlier retained-DB runs incorrectly assumed global scheduler counters described
  only the current test owner. Corrected the harness to sweep bounded pages and
  retain exact owner-scoped assertions. Subsequent diagnosis found the strict UUID
  mismatch; an added stop test also initially omitted required `reason_code`.
  Preserve these Failed runs as history; their affected tests now pass.
- Paper isolation initially failed on the new imports; the expanded gate passed
  both isolation cases after the correction. The other 29 gate cases passed in
  the preceding run. Import-linter: seven contracts kept, zero broken.
- Final backend `ruff format --check src tests`, `ruff check src tests` and
  `mypy src tests` passed: 754 files formatted, 753 files type checked.
- Frontend `typecheck`, `lint`, targeted PaperBotPanel/KillSwitchControls tests
  (24 passed), and production build passed. Build retains the >500 kB bundle warning.
- OpenAPI exported and TypeScript regenerated from it. `git diff --check` passed.
- Earlier catalog integration and empty migration checks remain recorded above;
  neither was rerun as part of the final 153-case group. No workload, endurance,
  full regression, final-SHA required CI or owner acceptance is claimed.

Reproduction commands (use isolated role-specific DB/Redis environment):

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/pytest -q tests/core/test_bot_contract.py tests/core/test_paper_matching.py tests/core/test_risk_matching.py tests/infra/bots/test_requests.py tests/infra/execution_market/test_bot_decisions.py tests/infra/protections/test_lifecycle.py tests/infra/risk_limits/test_stops.py tests/api/test_bot_routes.py tests/api/test_route_classification.py
.venv/bin/pytest -q tests/gates/test_gates.py tests/gates/test_paper_isolation.py
.venv/bin/ruff format --check src tests
.venv/bin/ruff check src tests
.venv/bin/mypy src tests
.venv/bin/lint-imports
cd ../frontend
npm run typecheck
npm run lint
npm run test -- tests/PaperBotPanel.test.tsx tests/KillSwitchControls.test.tsx
npm run build
```

### Open review findings

Critical: 0 identified. High: 2. Medium: 2. Low: 0 identified.
These are open findings, not accepted exceptions or permission to merge.

| ID / severity | File/location | Problem and impact | Recommended fix |
|---|---|---|---|
| CR-F20-01 / High | `backend/src/tiewtrade/infra/bots/evaluation.py:199–204`; plan §2/§5; RQ-03/11 | Every descriptor requiring indicators or a timeframe returns without consuming F-11 data. The pure contract accepts these dependencies and start can create its run, but the engine cannot evaluate it even when data is ready. A run can stay STARTING, or retain a prior status, without a dependency-specific explanation. This is unfinished F-20 input assembly, separate from the intentionally deferred F-21 trading formula. | Connect a bounded backend dependency reader with provenance/revision/warm-up checks; expose explicit readiness reasons, and test unready→ready and source-revision invalidation without inventing a strategy trigger/catch-up policy. |
| CR-F20-02 / High | `specs/features/2026-11-19-bot-lifecycle/validation.md:19–27`; `backend/tests/infra/execution_market/test_bot_decisions.py` | The committed tests/evidence do not cover the approved process-kill/DB-disconnect matrix or all replacement-vs-fill/stop, loss/reset, reordered feedback and stale-worker races. Atomic rollback, active-slot concurrency, lease takeover and the stop-between-transactions case cover parts of these criteria, not the full financial safety contract. No claim that all Feature gates pass is justified. | Add the missing real-PostgreSQL fault/barrier cases and exact order/ledger/reservation/position oracles; close each gap with evidence before merge. Preserve existing assertions and do not substitute mocks or move these safety checks to Batch. |
| CR-F20-03 / Medium | `backend/migrations/versions/0071_bot_resume_proofs.py:46–57`; `backend/src/tiewtrade/services/engine/bot.py:266–283` | Recovery discovery always selects the oldest 20 eligible stops. If those strategies remain broken and never produce a proof, each round selects them again; later owners can be permanently starved of recovery probes. The active-run cursor does not rotate this query. | Add bounded fair scheduling/cursor or durable retry progress for recovery probes, retaining owner isolation and proof freshness. Test more than one page with permanent failures before a recoverable owner. |
| CR-F20-04 / Medium | `backend/src/tiewtrade/services/api/bot_routes.py:121–138`; `frontend/src/BotRunStatus.tsx:16–21` | Status materializes every positive-quantity protection group and the browser polls every two seconds. Historical FAILED groups can retain quantity, so response/query/decode work grows without a bound or pagination. This can degrade status availability as an account accumulates history. | Reuse bounded F-17 pagination or a bounded status summary with an explicit truncation/details indicator; test large histories and retain visible failed/exposed allocations. |

### Requirements coverage

| Requirements | Coverage at this checkpoint |
|---|---|
| RQ-01/02/04/05/06 | Pure/versioned context, exact codecs, deterministic identities, parity, execution linkage and pinned recovery implemented; complete execution-outcome/error matrix remains partial. |
| RQ-03/08/11 | Quote/account/risk readiness and pause/recovery path implemented; indicator/timeframe input assembly missing (CR-F20-01). |
| RQ-07/09/10/12/13/14 | Per-mode slot, requested vs running, F-19 stop/resume and atomic flat replacement implemented; UI now shows exposure/protection. Fair recovery and full race/acceptance evidence remain open. |
| RQ-15/16/17/18/19 | PostgreSQL authority, RLS, owner locks, durable keys, atomic decision/intents, execution fences and replay implemented; fault/concurrency coverage incomplete (CR-F20-02). |
| RQ-20/21/22 | SYSTEM proof path, catalog receipts, exact fill-linked brackets and F-17 failure exit implemented and partly integrated; remaining error/replay/race matrix is not certified. |
| RQ-23/24/25 | Owner/mode API, CSRF, privileges, immutable facts, shared controls and localization implemented; browser/owner acceptance, full journal scope scenarios and bounded status remain open. |
| RQ-26/27 | Targeted real-DB safety/parity/isolation evidence available; full Feature validation, required CI and later dependencies remain pending. |

### Validation coverage and remaining risks

V-01 now has passing core purity/import and deterministic/parity evidence. V-02..14,
V-16/17 remain Partial. V-15 is now Partial (component/control checks passed;
isolated-browser and owner acceptance not run). V-18 is Partial (local checks and
parity passed; required CI on a final SHA not run). V-19/20 Batch and V-21 Release
remain Not Run / Pending Full Validation or their named dependencies.

Tests have not sent Live orders or loaded Live credentials. Default production
strategy registry/admission remains closed. Financial behavior beyond the tested
paths, fairness with larger populations, fault recovery, indicator readiness,
UI browser acceptance, rolling deployment and final CI remain material risks.
F-21 actual strategy/parameters, F-22/F-23 Live execution/reconciliation and F-24
activation remain separate dependencies.

Next authorized work is to close CR-F20-01..04 and the missing Feature evidence,
then recheck only those changes/regressions. Requirements/plan approval does not
need to be requested again for these scoped engineering fixes. Owner UI acceptance
and required CI remain gates before merge. Do not label this candidate Ready for
Code Review, Completed or ready to merge while implementation findings remain.

Code review result: **CHANGES REQUIRED**.

## Review corrections verified — 2026-11-20

This section supersedes the open-finding status above; prior Failed/Partial results
remain historical evidence. Candidate is the working tree on
`feature/f-20-bot-lifecycle`, base HEAD `31c9146`, including untracked F-20 files.
No commit, push, PR, merge, production activation or Live order was performed.

### Findings and corrections

| Finding | Correction and targeted evidence | Status |
|---|---|---|
| High — recovered corrupt state bypasses validation on a duplicate input | `infra/bots/evaluation.py` decodes pinned config/state before duplicate readiness. `test_bot_review_safety.py` tests wrong schema and financial float in stored state with an accepted BUY: SYSTEM stop, no subsequent fill or cash/position change. | Fixed; 2 cases passed |
| CR-F20-01 / High — missing indicator/timeframe assembly | New `infra/bots/inputs.py` reuses F-11 prepared reader/checkpoints, bounded suffix, closed point, warm-up and source proof. Unsigned claims moved to `infra/indicators/read_contract.py`, signing imports remain compatible. Engine reads outside financial locks and rechecks proof under a source SHARE fence before committing; missing/stale dependencies pause with a visible reason. `test_bot_indicator_inputs.py`: unready data, ready data/provenance, correction between prepare/commit. | Fixed; 3 cases passed in the owner-approved extra attempt |
| High — catalog withdrawal makes SYSTEM failure proof permanently undiscoverable | Recovery uses immutable failure linkage and unresolved latest SYSTEM generation rather than latest run event. Current catalog eligibility remains mandatory; old run stays stopped/retired. Real withdrawal/add-back/probe/owner-confirmed replacement test checks receipts, no old-run restart, unchanged cash and zero orders/positions. | Fixed; 1 case passed |
| CR-F20-02 / High — missing financial fault/race evidence | Real subprocess SIGKILL before commit, connection termination before commit and lost acknowledgement after commit check atomic decision/state/command/link/audit and financial sources. Owner-lock barriers test both stop/replacement orders, rejection of an old decision after stop acknowledgement, and replacement waiting for a real reducing fill then rejecting stale reconciliation. Actual risk RESET after BREACH cannot clear the F-19 cause or commit pre-breach output. Full/partial execution tests now consume fill then actual disposition, replay older receipts and assert state never regresses. | Identified fault/race gaps addressed; broader Feature acceptance remains partial as detailed below |
| CR-F20-03 / Medium — oldest failed probes starve later owners | Migration 0072 adds owner-RLS durable last-attempt scheduling. A real 21-owner case verifies the next scan reaches owner 21 after the first 20 permanent failures. Scheduling hints cannot authorize resume. | Fixed; 1 case passed |
| CR-F20-04 / Medium — unbounded protection status | API returns at most 20 decoded groups, reads one extra row, prioritizes failed/conflicted groups and exposes `protections_more`. UI shows the notice; F-17 cursor history discovers all allocations. Real API test verifies 21 positive groups and paginated discovery including the canceled original. | Fixed; API and component checks passed |

The feedback work also found that F-15 projection `last_event_id` points to a
matcher checkpoint, not an immutable FILL. The corrected reader joins the latest
immutable fill by exact order/owner/episode with the authoritative current
projection. Raw fill and disposition have distinct durable identities and ordered
revision phases. It adds no financial writer, inferred fill or quantity calculation.

### Checks, commands and retained failures

Environment: isolated PostgreSQL 16 `tiewtrade-f20-review`, isolated Redis 7,
existing Python 3.12 virtualenv and frontend toolchain. Role-specific URLs and
`TIEWTRADE_TEST_REDIS_URL` point only to disposable services. New safety tests use
the existing real-database template/clone fixture. No existing development database
was reset; no mock replaced transaction/locking/financial assertions.

- `test_bot_review_safety.py`: 7 passed across targeted runs (corrupt state 2,
  process/connection/ack faults 3, fairness 1, catalog recovery 1).
- `test_bot_indicator_inputs.py`: 3 passed after the explicitly approved CAST fix;
  the process was capped at 120 seconds. No further indicator run was performed.
  Preserve three earlier fixture failures (advance argument, checkpoint boundary,
  timestamptz inference); assertions for warm-up/source revision were retained.
- `test_bot_review_races.py`: both stop/replacement barrier orders, real loss
  reset and reducing-fill/replacement barrier passed (4 cases across targeted runs).
  The reducing-fill case verifies 0.999 BTC bought after base fee, sold at 99:
  98.901 gross less 0.098901 fee = 98.802099 USDT. Final cash is initial cash less
  1.197901 USDT, position zero, two position events, two commands, no reservations.
- `test_bot_review_migration.py`: empty 0072→0071→head roundtrip, unchanged schema
  snapshot/default-disabled activation, narrow grants and populated downgrade
  refusal passed (2 cases across targeted runs). Refusal preserves head, RLS and
  provenance. No claim of a populated rolling-deployment campaign.
- Updated `test_authorized_bot_decision_reaches_real_paper_financial_writer`:
  full, partial and protection-setup-failure all passed (3), including terminal
  feedback, older receipt replay and existing financial/protection oracles.
- Affected bot-decision/protection/risk-stop/isolation regression: 33 passed
  (`test_bot_decisions.py -k 'not authorized_bot_decision'`,
  `test_lifecycle.py`, `test_stops.py`, `test_paper_isolation.py`).
- Prepared-indicator API regression after data-contract relocation: 38 passed.
  Prior setup errors were caused by the temporary harness omitting the isolated
  Redis test URL; fixing that environment restored the existing tests. Cursor and
  indicator route tests from the preceding run remain valid.
- Bot API/status history test passed; preceding affected bot/API group 16 passed.
  Frontend typecheck/lint and PaperBotPanel/KillSwitchControls: 24 passed after API
  types regeneration. Existing production build result remains applicable: no
  frontend runtime source changed after those checks; bundle-size warning retained.
- Final Ruff format/check passed (760 files); mypy passed (759 source files).
  Import-linter kept all seven contracts; `git diff --check` passed.
- Retained harness failures: migration helper result was initially treated as a
  string; terminal feedback initially assumed checkpoint ID was a fill ID; loss
  reset fixture used a pre-breach revision; the fill barrier initially read an
  intent from `OrderCommand` instead of retaining the submitted intent. Each
  affected test passed after correction. A file-only mypy invocation omitted the
  source roots; the canonical `mypy src tests` passed. No safety assertion was
  removed and none of these runs is represented as an all-green full suite.

### Review scope, coverage and remaining gates

Reviewed the correction diff, new migration, engine/evaluation callers, F-11
reader/proof contracts, feedback journal, API/UI status and affected tests.
No additional Critical/High/Medium/Low code finding was identified in that scope.
Persistent scheduling, run state and idempotency remain PostgreSQL-backed; the
immutable registry is deployment configuration, not persistent session/business
authority. RLS, source/owner locks, Paper/Live boundaries, signing, exact money,
default-closed admission and F-17 reducing exits were retained.

RQ-03/06/08/11 now include verified indicator inputs and corrupt recovery guards;
RQ-13/20/21 include catalog/SYSTEM proof recovery; RQ-16/17/19/24/26 have additional
process/connection/race/replay evidence; RQ-23/25 have bounded status. Existing
coverage for the remaining RQs is retained. These tests do not certify every row
of the approved Feature validation matrix or authorize production trading.

V-03/05/07/08/10/11/13/17 received the evidence above; keep their aggregate Partial
status until every scenario in each row has a mapped result. V-15/16 browser,
responsive/scope checks and owner UI acceptance remain pending. V-18 final-SHA
required CI is Not Run; no local result substitutes for it. V-19/20 Batch and
V-21 Release remain Pending Full Validation/Dependencies, including real F-21
strategy, F-22/F-23 reconciliation and F-24 activation.

Next step: finish the unmapped Feature acceptance scenarios and owner UI
acceptance, then required CI on a final candidate SHA before merge. Scope/plan
approval need not be requested again for engineering validation. This checkpoint
closes the listed implementation corrections; it does not claim Completed,
all Feature gates passed, or ready to merge.

Teardown: after all test processes exited, removed only
`tiewtrade-f20-review` and `tiewtrade-f20-review-redis`. Existing development
PostgreSQL and F-18 Redis containers were left intact.

## Recovery and readiness fixes — 2026-11-20

Owner instructed “แก้ไข” after the next review identified two High and one Medium
finding. The approved engineering amendment was recorded in `plan.md` before code
changes. Scope is the working tree on `feature/f-20-bot-lifecycle`, base `31c9146`;
no commit/push/merge or production/Live activation is claimed.

| Finding | Fix and evidence | Result |
|---|---|---|
| High — duplicate-input shortcut can issue proof without evaluating the strategy | `services/engine/bot.py` permits the no-op shortcut only for normal delivery. Every dry probe now executes the pure strategy and validates output; exception and wrong-state-version output produce no proof. The healthy probe test emits a real valid BUY intent yet proves that neither a decision nor command/order is created. | Fixed |
| High — PAUSED on the same lease skips reconciliation | `infra/bots/evaluation.py` checks full account/order proof and unresolved commands before every PAUSED readiness path, including an already consumed quote. Four real-DB cases cover pending commands/conflicted order source × duplicate/new quote; revision/state/financial sources remain unchanged until the real command outcome or valid source is available. Existing exposure is allowed; flatness was not added to resume. | Fixed |
| Medium — STARTING cannot pause or explain lost readiness | The existing STARTING→PAUSED transition is used with fixed account/market/risk reasons. STARTING also rechecks full reconciliation because readiness can change after the control transaction. Actual control-created runs test protocol outage, disconnected market feed and conflicted order source, then healthy recovery. | Fixed |

Pure evaluation failures now retain input identity in the immutable failure event.
For status feedback, the event also retains its canonical order/revision/status,
validated again against `ExecutionFeedback` and owner/run/order lineage on replay.
This is needed when PARTIALLY_FILLED becomes CANCELED during F-19 cleanup; reading
the current projection cannot reproduce the failed disposition. Raw FILL still
uses the original F-15 immutable fact/codec. Missing or malformed context never
falls back to a guessed quote. Legacy evaluation-failure events without any input
identity field remain stopped; scheduling attempts still rotate to prevent
starvation. Missing-version events can still prove that the pinned code loads and
evaluates successfully. No new schema, financial formula or activation permission.

### Targeted results

Disposable PostgreSQL 16: `tiewtrade-f20-recovery-review`, role-specific localhost
URLs, existing `internal_database` template/clone fixtures and unchanged F-18/F-19
runtime/financial writers. Docker was started because the daemon was unavailable;
no existing application database was reset and no Redis was required by this group.

- New `test_bot_readiness_recovery.py`: **12 distinct cases passed across targeted
  runs**: legacy missing context 1; duplicate quote with exception/invalid output 2;
  accepted and partial→canceled feedback 2; same-lease PAUSED guards 4; actual
  control-created STARTING outages 3. This is combined targeted evidence, not a
  claim of one complete final-suite run.
- Partial execution oracle: 40 USDT spent, 0.3996 BTC held after base fee, one
  position event; stop cancels the remainder and releases reservations. Failed and
  healthy dry probes keep these amounts and the two order commands unchanged.
  Unknown-order, invalid-revision and extra-field status snapshots are rejected.
- Existing affected regressions: safety faults/catalog/fairness/corrupt recovery
  **7 passed**, stop/replacement/fill/loss-reset barriers **4 passed**. These ran
  before the final additive status-snapshot/legacy-context checks; their unchanged
  financial assertions remain valid, with current recovery paths covered above.
- Existing scheduled start/pinning/takeover/SYSTEM proof/owner resume case passed
  again after the final readiness changes. Full/partial/protection-setup-failure
  financial writer cases **3 passed** and Paper isolation **2 passed** after the
  status-snapshot change. No Live order was sent.
- Final Ruff format/check passed (761 files); mypy passed (760 source files);
  import-linter kept all seven contracts; `git diff --check` passed.
- Frontend, OpenAPI and migration source were unchanged in this correction; their
  prior affected checks remain evidence. No indicator campaign, full regression,
  workload/endurance run, owner acceptance or required CI was rerun/claimed.

Retained failed runs: the first new group had five passes and three failures:
feedback cleanup had not yet driven its CANCEL, and two order-source fixtures
violated the database UNKNOWN-state constraint. The fixtures now use the actual
cancel worker/cleanup and valid CONFLICTED source state; all three passed on the
targeted retry. The market outage test initially expected the broad reason instead
of the more precise MARKET_NOT_READY and passed after correcting that expectation.
Four existing regression setups initially found no `users` table because the new
base database had not been migrated (clone-based tests were unaffected); after
upgrading that disposable base to 0072, those four cases passed. Preserve these
failures; no assertion, trading threshold or safety gate was removed.

### Correction review and remaining gates

Reviewed the changed engine/evaluator, failure-event writer, feedback codec/reader
and callers, plus new tests and affected F-19/Paper paths. The three findings above
are closed; no additional code finding remains in this correction scope. PostgreSQL
authority, owner locks, durable identities, pinned run state, exact Money/Quantity,
Paper/Live isolation and default-closed activation are retained. No useful runtime
refactor was needed beyond reusing the existing feedback/transition contracts.

RQ-09/11/12/20 and V-03/08/11 receive the new evidence. Aggregate Feature matrix
statuses remain Partial where their other scenarios are unmapped or unaccepted;
V-15/16 browser/owner acceptance and V-18 final-SHA required CI remain pending.
V-19..21 Batch/Release remain Pending Full Validation/Dependencies. Legacy failures
without retained input context deliberately cannot receive an automatic proof.

Next step: finish remaining Feature acceptance evidence and owner UI acceptance,
then required CI on the final candidate before merge under the existing workflow.
This fixes the requested review findings; it does not mark all of F-20 Completed
or ready to merge.

Teardown: after test processes exited, removed only the disposable
`tiewtrade-f20-recovery-review` container. No other container/database was removed.

## Scoped recovery/readiness refactor — 2026-11-20

Reviewed only the latest recovery/readiness additions, not the earlier F-20 feature
diff. Recorded the scoped amendment in `plan.md` before changing code.

- `services/engine/bot.py`: expanded replay-vs-evaluation selection into explicit
  branches, preserving the same exception boundary and dry-probe behavior.
- `infra/bots/evaluation.py`: made saved-status vs immutable-fact feedback selection
  explicit and removed the unused default pause reason. Every caller still supplies
  its original reason; no readiness, stop, reconciliation or proof rule changed.
- `infra/bots/system_stop.py`: corrected the module description to include strategy
  failures; no writer or payload behavior changed.
- `test_bot_readiness_recovery.py`: consolidated repeated admission-toggle and
  order-source SQL into two file-local helpers with bound parameters, reusing the
  existing engine/session pattern. Kept transaction boundaries, scope, operations
  and all financial/state assertions intact; moved the local `submit_order` import
  to the existing import group. No suitable existing helper was found in the test
  modules; no shared fixture or new runtime abstraction was introduced.

Validation on a new disposable PostgreSQL 16 container of the same isolated name:
upgraded its base to 0072, then ran the 12 recovery/readiness cases, existing
scheduled start/recovery caller and two Paper-isolation cases in one selected
group: **15 passed**. Ruff format/check passed (761 files), mypy passed (760 source
files), import-linter kept all seven contracts, and `git diff --check` passed.
Review of this refactor identified no additional finding. No frontend, OpenAPI,
migration, financial formula, activation gate or unrelated implementation changed;
no indicator campaign, full regression or Live order was run.

This refactor has no remaining work in its requested scope. Feature acceptance,
owner UI acceptance, required CI and Batch/Release dependencies remain pending
as recorded above; this result is not feature completion or merge approval.

After all checks exited, removed only this refactor's disposable PostgreSQL
container; no other container or database was removed.

## Feature validation closure and owner UI checkpoint — 2026-11-20

Candidate: `feature/f-20-bot-lifecycle`, base `31c9146ad73b45b9d323063e24140911d1ca1948`
plus the working diff/untracked F-20 files. Amendments were recorded in plan before
the engineering changes. This section supersedes the earlier unmapped aggregate
Partial entries; it preserves their original failures and limitations above.

### Implementation and scoped review

- Added migration 0073's owner/mode/request-time index. Status reads the latest
  unresolved start request separately from the current run, under owner RLS and
  one repeatable-read snapshot. A pending receipt is never RUNNING.
- Added `pending_request_id` and `snapshot_at` to the API/generated types. UI uses
  the existing Badge/MarketTime and F-19 controls; summary reconciliation time
  uses the same formatter. Normal Start remains disabled, production registry
  empty, Live unavailable. No quantity, risk, fee or matching formula changed.
- Added a test-only composition by reusing the guarded risk/Paper app, production
  API and actual wallet/risk/order/protection workers. Controllers are never
  imported/mounted by production. Persistent business data stays in PostgreSQL.
- Connected `npm run test:e2e:bots` to the existing Chromium CI job; no new service
  or production scheduler was added. The dedicated config isolates ports and
  database guard, as the existing protection/risk configurations do.
- Reviewed the new diff, migration, generated contracts, status query/UI callers,
  test composition and changed assertions. React checklist: consistent hooks,
  owner/mode query keys, abort signal, shared UI, stable keys, keyboard/focus and
  no client financial authority. No additional Critical/High/Medium/Low code
  finding was identified in this closure diff. Prior full review/fixes remain
  applicable; no unrelated refactor or additional abstraction was introduced.
- Investigated possible catalog add-back/shared-checkpoint bypass: existing
  `_cancel_removed_openings` checks every BUY's persisted admission revision
  before advancing shared state, not only the claim anchor. No duplicate fence
  was added.

### New checks and retained failure history

Environment: disposable PostgreSQL 16 `tiewtrade-f20-feature-pg` and Redis 7
`tiewtrade-f20-feature-redis`, Python 3.12 virtualenv, existing frontend toolchain.
Role URLs target only these services; internal tests use generated database clones.
No Live order, external exchange call, full regression, timed workload or further
indicator campaign was run. Approved indicator results above remain in use.

- Core document/lifecycle tests, migration pair and replacement variants: **58
  passed** in the selected group (53 core, 2 migration, 3 replacement). Negative
  documents include unknown schema/fields, noncanonical/duplicate keys and float;
  all lifecycle edges and authorization guards are covered. Replacement fault
  after retire/resume but before commit preserves original stop/run/slot and
  financial facts, then retries once without an extra run.
- `test_bot_feature_gates.py`: **14 distinct cases passed across targeted runs**:
  nine invalidations of a fresh resume proof, three nonflat/unproven replacement
  refusals, a two-engine barrier takeover and linked unknown→rejected feedback.
  Old output cannot commit after takeover; only one 25 USDT order fills, yielding
  0.24975 BTC after the existing base-fee rule, with one position event.
- `test_bot_api_restart.py`, distinct-pair slot, old withdrawal replay and bot API
  routes: **8 passed** together. Real uvicorn process loses an acknowledgement
  after commit, is killed, and a new process/client recovers applied and rejected
  outcomes by original keys/cookies after the disposable Redis database is lost.
  Counts remain requests/results 2, runs/events 1, orders/reservations/positions 0;
  cash unchanged. Different payload conflicts and identical retry returns the
  original result. Slot contention uses BTC and ETH metadata, plus one simulated
  Live slot without a Live executor. Old withdrawal cannot stop the replacement.
- Canceled feedback (accepted and partial-then-canceled) and linked rejection:
  **3 passed**. Unknown has no invented feedback/position; actual rejection has
  one consumable identity, duplicate consumption no effect. Canceled event uses
  its immutable identity/order lineage, never an inferred fill.
- Protected full-fill abnormal-stop extension: **1 passed**. The real missing-
  implementation path plus F-19 leaves the exact protection document, 0.999 BTC
  holding and cash unchanged, with no extra command. Existing partial/filled and
  F-17 setup-failure reducing-exit oracles remain applicable.
- Browser suite: **2 cases passed** (lifecycle/real exposure/protection/lost stop
  acknowledgement/reload/resume, and late response/mode/logout/other-owner scope).
  Responsive matrix covers 375/768/1280/1440px × Thai/English × light/dark, plus
  keyboard focus and disabled normal Start. Screenshots wait for actual UI
  holdings, protection and 9,900 USDT trade snapshot after the 100 USDT fill.
  Lifecycle and scope cases were subsequently rerun individually only for the
  corrected screenshot framing/additional Live evidence; both passed.
- Component group: 24 passed plus the corrected timestamp assertion passed in
  its targeted retry (25 affected component cases total). Frontend typecheck,
  ESLint and production build passed; the existing bundle-size warning remains.
- Backend Ruff check/format passed (841 files), mypy passed (763 source files),
  purity passed, seven import contracts kept. Runtime OpenAPI equals exported
  JSON; generated frontend types were regenerated from that contract. Workflow
  YAML parses and references the existing npm/config path. `git diff --check`
  passed. Required remote CI remains **Not Run**, not replaced by local checks.

Retain these failures, all resolved without relaxing assertions:

1. Head 0073→0071 downgrade was initially assumed atomic across revisions. Alembic
   commits reversible 0073 before 0072 refuses. The refusal test now explicitly
   starts at the populated 0072 boundary, checks unchanged version/facts/RLS, then
   upgrades head; head empty roundtrip still checks 0073→0071→head.
2. Proof wallet-revision mutation was blocked by TT015. Replaced raw UPDATE with
   existing owner lock, financial-writer marker and increment helper; retry passed.
3. Browser logout initially targeted a control absent on Live page. Navigate to
   the real account page; scope test passed. Adding a Live capture later omitted
   Playwright's `info` parameter once; added it, targeted scope case passed.
4. Summary component originally expected raw ISO text. It now checks semantic
   `time[datetime]`, the existing GMT+7 formatter and translated label; passed.
5. Protected financial-writer fixture originally had no pinned start event, so the
   lifecycle evaluator correctly found no run. Added its original entry metadata
   before invoking the lifecycle reader; STOPPED and unchanged protection passed.
6. Mobile locator screenshots were occluded by the existing sticky toolbar.
   Capture the actual full page from scroll origin. Also wait for the independent
   trade-snapshot polling before capture; no product layout/policy was changed.

### Scenario mapping and requirements coverage

Existing evidence is reused unless its contract, schema or caller changed. Test
module names below are under `backend/tests/infra/execution_market/` unless noted.
Passed means the scoped Feature criteria, not activation or full-system validation.

| Gate | Evidence covering the approved scenarios | Current result |
|---|---|---|
| V-01 / RQ-01/05 | `core/test_bot_contract.py`: repeated pure evaluation and Paper/Live parity; purity/import checks | Passed |
| V-02 / RQ-02/06 | Exact codec/negative documents, claimed-start pinning, missing-version/corrupt-state/recovery cases; registry deployment configuration only | Passed |
| V-03 / RQ-03/08/11 | Approved indicator 3-case evidence; source correction fence; readiness/reconciliation/loss checks in `test_bot_readiness_recovery.py` and loss-reset race | Passed |
| V-04 / RQ-04/09/12 | Complete pure transition matrix + guards, STARTING/pending separation, terminal/unknown/rejected/canceled feedback and original stop-cause checks | Passed |
| V-05 / RQ-07/08/14/17 | BTC/ETH concurrent slot + simulated separate Live slot; replacement rollback/stale summary; stop/decision and real fill barriers; position/pending/unknown refusal; F-19 resume with retained exposure | Passed |
| V-06 / RQ-15/16/23 | Real API process/key-only lost-ack recovery, stable applied/rejected outcomes; concurrent inbox and owner/mode lookup tests | Passed |
| V-07 / RQ-16/19/24 | Existing SIGKILL/DB disconnect/commit-before-ack and mid-transaction faults; new API+Redis-loss recovery; exact financial and audit counts | Passed |
| V-08 / RQ-16/17/19 | Duplicate/reordered feedback/state; source/run/claim fences; two-engine barrier with one actual fill; existing owner RLS/isolation and fair scheduling tests | Passed |
| V-09 / RQ-08/18 | Real shared Paper dispatch/matching/protection and unchanged funds/filter/risk/catalog gates; unlinked BOT refusal and accepted-BUY shared-checkpoint fence; reducing/manual regressions | Passed |
| V-10 / RQ-10..12/17 | Existing stop/platform/account-use/loss-hit/reset and replacement races; stale/cross-mode/new-cause summary refusal; browser F-19 stop/resume and existing three-state cleanup checks | Passed |
| V-11 / RQ-06/13/20 | Broken output/throw/missing/corrupt state; exact failed feedback probe; 9 proof invalidations; real protected fill survives abnormal stop; valid proof + explicit owner F-19 summary path | Passed |
| V-12 / RQ-17/21 | Existing real catalog multi-owner/mode/unaffected-pair/Partial effects/replay case; historical admission fence; real withdrawal/add-back/replacement and explicit old-event replay against new run | Passed |
| V-13 / RQ-04/19/22 | Unknown/rejected/canceled identities, real partial/full execution and ordered replay, exact cash/fees/positions/reservations; F-17 protection quantity/setup-failure exit checks | Passed |
| V-14 / RQ-15/23/24 | Bot API/routing tests + shared auth/CSRF/session enforcement; RLS/grant tests; sanitized errors, mode/owner isolation, Live default closed | Passed |
| V-15 / RQ-09/13/25 | Components and isolated actual-API browser flows passed; owner review of images/flow still required | Partial — owner UI acceptance pending |
| V-16 / RQ-16/23/25 | Real lost stop ack→reload→by-key recovery, late mode response, logout/new owner, episode/pair reset component tests; responsive/locale/theme/focus matrix; shared template components | Passed |
| V-17 / RQ-15/17/23/24 | Empty migration roundtrips and populated refusal across earlier checkpoints/0073; RLS/grants/integrity; process restart, legacy failure context and fenced takeover compatibility; additive schema/default-closed rollout review | Passed within closed F-20 rollout; see limitation below |
| V-18 / RQ-05/26/27 | Local parity/isolation, affected regression/static/build/OpenAPI/review passed; F-20 browser wired into existing CI | Partial — final-SHA required CI Not Run |
| V-19..21 / RQ-27 and integrated dependencies | No new Batch/Release campaign; real F-21, F-22/F-23/F-24 and notification dependencies unchanged | Pending Full Validation/Dependencies |

Rolling limitation: F-20 adds no production worker/strategy/activation. Compatibility
proven here is additive schema + older-shaped facts + restart/takeover under the
closed rollout. This is not an enabled mixed-release production campaign. Before
F-21/F-24 activation, every executing worker must support BOT fencing; default-
closed API/empty registry is not permission to enable bots beside legacy executors.
No claim is made about Live reconciliation, leverage/liquidation or new PnL rules:
F-20 reuses existing exact Paper execution contracts and has no Live executor.

### Owner review artifacts and next gate

The image matrix in [ui/](ui/) contains no real account credentials or Live orders.
Representative artifacts:

- [Paper pending](ui/f20-pending.png), [paused](ui/f20-paused.png)
- [Mobile Thai/light](ui/f20-running-375-th-light.png)
- [Desktop English/dark](ui/f20-running-1440-en-dark.png)
- [F-19 reconciliation and retained holding before resume](ui/f20-resume-summary.png)
- [Live unavailable](ui/f20-live-unavailable.png)

**Ready for Code Review** was announced; scoped review then completed without a
new code finding. Implementation/local validation checkpoint reached. Remaining
mandatory pre-publication gate: explicit owner UI acceptance under validation §4/§5
and AGENTS.md Git rules. Then commit/push/PR and required CI on the final candidate
may proceed under existing authorization; no repeated workflow permission needed.
No commit/push/merge has been performed at this checkpoint. Feature is not marked
Completed or ready to merge; remote CI and later Batch/Release remain separate.

Final artifact QA: checked complete mobile page (including the actual 9,900 USDT
balance), desktop dark layout, reconciliation modal and Live-unavailable page.
All 20 PNG artifacts and local document links exist; the 21-row validation table
retains its structure. Final Ruff check/format, mypy, frontend typecheck/ESLint
and diff whitespace checks passed after the last source/test edits. The final
lifecycle capture case passed in 21.9 seconds overall; the scope/Live capture
case passed in 12.3 seconds overall. These are targeted reruns for the changed
capture assertions, not an additional regression campaign.

Requested owner acceptance of the concrete image/flow evidence; response pending.
After all test/browser processes exited, removed only the two disposable
`tiewtrade-f20-feature-pg` and `tiewtrade-f20-feature-redis` containers. No other
container, development database or production service was removed.

## Owner UI acceptance and publication - 2026-11-20

Owner explicitly accepted the presented image/flow set in this conversation
(response: "รับรอง UI ชุดนี้"). This satisfies validation section 4 and V-15's
owner gate for the concrete artifacts above. No runtime code or UI changed after
that acceptance. V-15 is Passed; final-SHA required CI (V-18) remains Not Run
until publication completes. Batch/Release remain pending; no activation granted.

Proceed with scoped commit/push/PR, required CI and conditional expected-head merge
under AGENTS.md's standing Git authorization. Retain all earlier failed/partial
history; report CI with candidate SHA/run links rather than recursive docs commits.

## Required CI secret triage - 2026-11-20

PR #83: https://github.com/yukasung/tiewtrade/pull/83
Candidate: 8ad901f47a69663b9db9de9cd4440860355bed84.
CI run: https://github.com/yukasung/tiewtrade/actions/runs/44664792212
Security run: https://github.com/yukasung/tiewtrade/actions/runs/44664792238

Security/secrets failed on exactly one new generic-api-key occurrence at
backend/tests/infra/execution_market/test_bot_catalog.py:130. It is the fixed
synthetic request idempotency marker passed to F-37 request_remove in the isolated
fixture, not authentication material. Identity:
38f59f54c402881bfb2d0d027dd95c57ac30530308ecbc92bc42237c01262836.

Source/callers confirm no credential/external API path. History scanning retains
the occurrence even after a later textual change. Prepared the exact registry
row in proposed-secret-exception.json; the active registry remains unchanged
pending mandatory owner review under the approved Security CI plan. Scanner
rules, historical scan, security thresholds and merge gates remain unchanged.

At triage, API-contract/frontend/Docker and all three CodeQL languages/dependency/
policy checks passed; backend and E2E still running. This is not an all-green
required CI result. PR remains blocked and will not be merged without all gates.

Owner explicitly approved the single proposed false-positive occurrence on
2026-11-20. Added only identity
38f59f54c402881bfb2d0d027dd95c57ac30530308ecbc92bc42237c01262836
to the existing exact-occurrence registry. Retained its original commit/path/line
binding and triage evidence; scanner configuration, history coverage and gates
unchanged. The proposal file now records the actual owner approval. Corrected the
full base-SHA transcription in this document (short base 31c9146 unchanged).

First CI browser result: general/F-37/F-16/F-17 suites passed, F-20 scope case
passed, F-20 lifecycle failed because stop returned 503 (expected 202). The F-20
config inherited the flag from the local launcher but did not declare it itself;
CI correctly retained production's default-closed F-19 authority. Added only the
existing risk-E2E test-environment flag to playwright.bots.config.ts. Stop/lost-ack
assertions and production activation rules unchanged. Owner-accepted runtime UI
is unchanged. Backend first run still in progress at this correction.

Security policy tests: initial invocation accidentally used macOS Python 3.9,
which lacks tomllib (import errors). Canonical backend Python 3.12 invocation
passed: 79 tests, 4 skipped. No policy assertions changed.

Superseded first CI backend pytest was canceled after remaining active beyond
30 minutes, rather than representing it as a pass. Previous base pytest took
14m42s. Added bounded verbose diagnostics to the new candidate's required backend
step (25m interrupt + 30s grace, 40m job budget); timeout remains a failure. No
tests/assertions were removed. Failure details will determine any subsequent
scoped fix; no blind rerun beyond the documented retry policy.

The canceled backend log completed 2,232 tests before a stalled next page and
contained three earlier failures. Matching its progress to the identical 5,768
collected tests identified the secret-canary bot-404 oracle, explicit renewing
route oracle and schema0066 preflight fixture. The next-page parent-poll fixture
was missing MANUAL origin after the workload helper began selecting BOT lineage;
its child raised before signaling submitted, leaving the parent Event unbounded.
Corrected these test-only contracts, preserved all secret/financial/pool/latency
assertions and bounded only the in-memory handshake/task wait. Kept the approved
checkpoint experiment pinned to 0066 by downgrading its empty clone, not by
changing the experiment's preflight or running a new campaign.

Targeted PostgreSQL group passed 7 tests: both canary variants, the route-policy
module, real pinned preflight and parent-poll projection/gate test. Ruff format/
check, mypy (763 sources), corrected config ESLint/typecheck and YAML parsing
passed. Reviewed this correction diff and callers: no additional finding.

The broad CI timeout edits were prepared but removed before publication once
the exact fixture stall was identified. The published correction will retain
verbose pytest names/durations and the per-test bounded handshake only; existing
whole-suite timing/acceptance criteria remain unchanged.

Corrected browser config verified with the launcher authority variable explicitly
unset: `env -u TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED npm run test:e2e:bots`
passed both cases in 32.5s. The guarded config now supplies its own F-19 test flag.
Production/UI code and owner-accepted appearance remain unchanged.
