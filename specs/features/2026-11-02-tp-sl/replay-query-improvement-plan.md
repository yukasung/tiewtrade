# NC-F17-REPLAY-04 — bounded replay query safety gate

สถานะ: In progress under owner instruction “เริ่มทำ” and delegated engineering authority (2026-11-14).

## Evidence and scope (before implementation)

REPLAY03-R2 enumerated 144364 records in55.346s; first page joined all rows and sorted
208128KiB to disk before LIMIT4096. Keep60s and all financial/security criteria.
Compare limiting narrow keys before fetching payloads, using existing UserSession,
RLS, decoder and indexes. No migration, trading change, four-hour run or Git publication.

Reuse profile_tail_reads.seed_history, test_tail_reads.market, internal_database
fixtures and existing replay reader/decoder. Key FK in0034 binds evidence identity,
owner,episode,pair; both tables have the same forced owner RLS and immutable rows.

## Mandatory safety gate

Schema key includes generation,input_id,decision_kind; current reader orders and
advances only input_id. Before rewriting SQL, reproduce pagination at a tied input ID
(INPUT/REBASE and different generations) against real PostgreSQL, using valid records
and no production writes. Compare complete expected evidence with paged enumeration.
Do not declare old/new equivalence from unique-input synthetic data alone. If original
reader skips rows, stop query rewrite/benchmark and report this existing correctness
blocker with a concrete cursor-contract amendment; optimization alone cannot satisfy
no-missing-record validation. Preserve existing Failed/Incomplete history.

## Conditional implementation and validation

Only if safety gate passes: bounded-key read then evidence join with final ordering;
real-DB equivalence (empty/page boundaries,foreign owner,missing episode/pair,
generation/REBASE,partitions,append snapshot), unchanged digest rejection and no writes;
scoped Ruff/format/mypy. One original120s preflight then fresh144364-record short
comparison with per-enumeration60s and900s total including cleanup. Pin candidate,
config/schema/runner, use reviewed cleanup/finalization helpers. Diagnostic only;
stop/report, no automatic4h campaign. Query must preserve complete evidence enumeration.

## Safety checkpoint — 2026-11-17

[Result](evidence/endurance20-20261115/replay04-safety-result.md): unique controlPassed,
INPUT/REBASE and generation paginationFailed under realPG. Existing scalar cursor
skips valid evidence at ties. Query rewrite and speed comparison NotRun; no production
change. Correctness cursor-contract amendment proposed in result before optimization.
Ruff/format/mypyPassed; fixtures removed/0connections/0locks. Historical results retained.

## REPLAY-05 — owner-authorized correction/review/refactor (before source)

สถานะ: Approved by owner instruction to finish preparation, including review and
refactor without repeated questions (2026-11-17). Supersedes REPLAY04 stop for this fix.

Add optional `after: SavedExecutionInput` to the internal reader, reusing its immutable
scoped record rather than adding a new cursor type. Total order is input_id,generation,
decision_kind (INPUT before REBASE). Reject mixed scalar/record cursor and wrong episode
or pair. Preserve legacy after_input_id as a strict input-id range filter, explicitly
not a complete pagination token. Change full replay caller to pass the last saved record.
Bound narrow keys in a materialized CTE before loading payload; retain forced owner RLS,
FK, original decoder,4096 maximum and60s. No API/schema/financial rule changes.

Caller audit also found executions.py uses range+LIMIT1 to authenticate a specific fill
source. Tied IDs could select the wrong evidence and reject a valid fill. Replace that
lookup with a scoped exact evidence ID+recorded_at reader using the same decoder; keep
all original identity/digest/financial checks and no fallback/retry. This necessary
caller fix is included under delegated engineering authority and owner's continuous scope.

Tests: realPG tie pagination with1/2/4096 boundary, total order/equality to complete
ordered baseline, scope/foreign owner, scalar compatibility, invalid/mixed cursor,
REBASE/generation,partition and concurrent append snapshot,exact identity/digest.
Run affected replay/evidence/execution safety tests and scoped static. Review then
refactor within this diff; resolve findings and rerun affected proof. Preserve all prior
failures. Prepare a pinned short comparison runner; stop ready for timed testing (owner
asked until ready), no4h/CI/Git. No performance pass claimed from correctness tests.

### Scoped review and refactor checkpoint (before final edits)

Owner authorized review/refactor in the same instruction. Reviewed caller diff, scalar
compatibility, FK/RLS materialization, replay cursor, exact fill identity, decoder and
transaction/session lifetimes. No new financial calculation or state cache. Review
finding: exact lookup must keep the key registry membership proof (not evidence table
alone); changed to key/evidence join before second safety run. Add orphan-negative
proof. Second run73Passed/1Failed only because expected digest-error wording differs
from existing normalized OrderConflictError; fix assertion, not production behavior.

Refactor within scope: use explicit None check for exact lookup, name full-replay cursor
last_evidence, keep test imports together and assert pagination advances. Retain existing
query/record types rather than add cursor abstraction. Run affected tests and scoped
static; retain earlier unchanged decoder/evidence proofs. Prepare but do not execute
short comparison; record historical failures and no4h/CI/Git.

Final review follow-up: exact fill lookup must not scan an owner's entire registry as
history grows. Join its complete existing primary-key identity (episode,pair,generation,
input_id,decision_kind) from the already selected evidence row, as well as evidence ID/
timestamp. This keeps registry proof and supports existing PK lookup without migration;
rejects inconsistent registry provenance. Recheck exact lookup/fill regressions only.

### REPLAY-05 ready checkpoint

[Implementation/review/refactor and validation](evidence/endurance20-20261115/replay05-ready.md)
complete:75unique cases covered using latest23/retained14+38,staticPassed,cleanupPassed.
Prepared pinned short comparison,not executed. Owner's “until ready to test” checkpoint
reached; no4h/Git. All historical failures/60s/F17pending preserved.

### REPLAY-05 comparison execution authorized — 2026-11-17

Owner instructed เริ่มทำ after readiness and workload guidance. Execute the pinned
comparison once with original120s preflight/60s enumeration/900s total and cleanup.
Retain all prior results; stop/report after this run, no automatic4h or Git.

### REPLAY-05 short comparison completed — 2026-11-17

[Result](evidence/endurance20-20261115/replay05-comparison-result.md): one diagnostic
complete;144364records/37pages both readers,matching evidence digest. Baseline55.200s,
candidate43.662s;first-page disk sort208128→5936KiB. Preflight/source/RLS/no-write/cleanup
Passed,total285.274s. Fixed-order/cache limitations retained; not fullfinancial replay
or4h acceptance. Keep60s;recommend representative20ownerfinancial replay next. One run
consumed;stop/report,no automatic extra run/Git. HistoricalW3Incomplete/F17Pending unchanged.
