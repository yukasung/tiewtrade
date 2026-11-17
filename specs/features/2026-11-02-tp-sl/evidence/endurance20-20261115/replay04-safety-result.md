# REPLAY-04 — pre-optimization pagination safety gate

สถานะ: **Blocked — existing reader skips tied evidence** (2026-11-17)

## Observed result

Real PostgreSQL, isolated migrated template and three fresh fixture clones; two
synthetic users per fixture, production append preparation/decoder/reader and owner
RLS. One-record pages are permitted by the existing1..4096 contract and expose the
same boundary risk as a tie straddling a4096-record page.

- Unique input control: Passed.
- Same input/generation with INPUT and REBASE: Failed. Full read returns two distinct
  evidence identities; page1 returns one; next `input_id > 1` page returns none.
- Same input across generations: Failed with the same missing-evidence result.

These are valid persisted records under the schema, not corrupted rows or mocked SQL.
The production primary key includes generation and decision_kind, while the reader
and profile_restore.replay_owner_domain continuation use only input_id. This proves
an existing potential omission, NOT that historical W3 data suffered it. Financial
position/cash rebuild uses separate readers; do not infer an actual balance error.

Tests:1Passed/2Failed in6.942s. Raw log:
validation-artifacts/f17-replay04-safety-r3-20261117/pytest.log.
Two launcher setup failures (missing PORT, then BACKEND in extracted environment
helper) occurred before pytest/DB creation; retained first two artifact directories.
Final test-only cleanup/static edit names typed episode/pair arguments explicitly;
Ruff/format/mypy Passed. No production source modification in this task.
Independent database/connection/lock counts for internal fixture prefix:0/0/0.

## Impact / decision

A query-only rewrite cannot prove complete replay while preserving this incomplete
scalar cursor contract. Keep60s unchanged; do not run the144364-record speed campaign
or4h endurance now. Retain the failing regression as a blocker (not xfail/waived).
W3 remains Incomplete; F17 Pending Full Validation. No commit/push/CI/merge.

## Concrete next amendment — proposed, not implemented

Use a total continuation key covering `(input_id,generation,decision_kind)` for
full evidence enumeration, retaining owner/episode/pair scope and deterministic order.
Audit all callers before choosing compatibility behavior for existing scalar callers;
never substitute a tie's last input_id as a complete continuation token. Bound each
page to4096 and retain immutable evidence/decoder/digests, RLS and Money calculations.
Do not use WITH TIES/unbounded pages, omit REBASE or raise timeouts to hide this.

After this correctness change, move LIMIT onto narrow keys using the existing FK and
identical RLS guarantees, then fetch wide payloads. Prove no missing/duplicate evidence
across tied boundaries, foreign-owner isolation, wrong-scope cursors, generation and
REBASE transitions, partitions and snapshot/append behavior with real PostgreSQL.
Then compare plans/time at144364 records under the original short diagnostic bounds.
This changes the internal reader/caller contract beyond a query-only equivalence fix;
record/confirm the amendment before production edits. No public HTTP API/schema or
trading-rule change is proposed.
