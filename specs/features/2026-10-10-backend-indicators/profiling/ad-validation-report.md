# A–D implementation and validation — 2026-10-12

Status: **Implemented; ready for review.** NC-38 was approved by the owner before
the disconnect correction. No commit, push, merge or production activation.

## A — HTTP lifecycle, boundaries and failures

`indicator_routes._read_until_disconnect` observes ASGI disconnect alongside the
reader, cancels and joins both tasks, and keeps local admission until cleanup is
finished. Repeated cancellation does not cancel the reader's cleanup again.
An explicit stop flag handles Starlette receive wrappers that consume cancellation
while leaving their own task group: a fast reader cannot leave the watcher waiting
for another request message. Existing exception mappings and serialization limits
remain unchanged.

Evidence covers an actual disconnect message, repeated caller cancellation,
deadline cancellation of PostgreSQL `pg_sleep`, cleanup in under two seconds in
those cases, zero checked-out connections and subsequent pool/slot reuse. The
direct route tests substitute admission/reader entry points; PostgreSQL cleanup
tests use the real API role and `indicator_read_session`. Full middleware tests
cover successful responses and serialization at 29.999/30/30.001 seconds.

Prepared HTTP tests cover age 600s -1µs/equal/+1µs; token and generation expiry
independently at request entry and response completion. The test extends its own
session through the presented-session role and verifies the affected row, so 401
cannot substitute for the expected 409. Real refused DB/Redis connections return
the existing fixed 503 codes; restoring the dependency permits another GET and
does not renew the authenticated session.

The lifecycle starts with no generations/checkpoints/heads, checks cold GET 503,
then runs the real scheduler/coalescer/attempt/publication to obtain HTTP 200.
The attempt wrapper only observes the real result and stops the finite test loop.

## B — Source identity proof

Six actual-role PostgreSQL cases move pair, timeframe, or open time and either
commit or roll back. Commit invalidates both old and new identity scopes;
rollback preserves both; an unrelated pair remains valid. Existing source-lock,
trigger-integrity, publication, snapshot and journal tests remain in the full run.

## C — Exact fixture prerequisite

`profile_exact_fixture.py` performs one finite correctness run using a controlled
aligned DB clock and the real worker. It inserts **525,600 dense M1 rows**, obtains
READY and **527 checkpoints**, verifies exact 365-day bounds, and compares the
published digest with independently streamed canonical fixture bytes.

Evidence: `exact-fixture-tests.xml` (1 passed, 141.355s including fixture setup and
cleanup), `exact-fixture.json`. The isolated fixture is removed by teardown;
the harness reproduces it. No production resource limit was increased. This is
not cold1/warm5, RSS, event-loop-lag, sustained GC or capacity acceptance. Historical
525,599-slot results remain historical and are not relabelled as full-size passes.

## D — Consumer integration, crosswalk and gates

`baseline-coverage-crosswalk.md` maps RQ-1..15, V-1..18 and PV-1..10 explicitly.
The test-only `indicator_refresh_consumer.py` executes the approved HTTP protocol;
it is also used against the real API/DB/Redis/F-09 worker and indicator scheduler.
It is a reference integration harness, not a new production frontend feature.

The real flow proves GET creates no demand; concurrent POSTs coalesce; missing
CSRF is rejected; 202 and uncommitted/rolled-back candle changes do not produce
ready values; committed FakeVenue ingestion and a new generation produce READY
with UNCONFIRMED finality; the original cursor becomes 409. Additional actual
HTTP tests preserve active fetch token/generation/cursor/attempts/backoff across
duplicate requests, return 200 for already satisfied source, and reject an expired
target without clamping. Existing auth/CSRF and ingestion suites cover their
underlying contracts.

Deterministic consumer cases use scripted HTTP outcomes and fake time to
cover the maximum six-poll/60s budget, terminal failures/401, unknown POST outcome without blind
retry, COMPLETE with blocked indicators, 200 followed by an indicator reread,
one shared 409 restart, discarding old pages and no fan-out from more_required.
The same harness's successful path uses real endpoints in the integration case.

### Review corrections — 2026-10-12

The review identified unbounded rollback/invalidation fallback and a consumer
that counted sleeps without counting HTTP duration. Both were corrected at the
owner's request; the earlier green runs alone did not prove these failure cases.

Bounded transaction cleanup now reserves 0.1s of the existing 2s budget for abort
and bookkeeping cancellation. It detaches the physical connection from the pool
and synchronously terminates asyncpg before releasing admission. Invalidation
has a bounded wait too. This applies to successful-body exit as well as rollback;
the original body error/cancellation is preserved. Tests inject stalled rollback
and stalled invalidation, repeated cancellation and deadline/disconnect, and use
real PostgreSQL connections to verify closed transport, zero checkouts and a
replacement connection that can execute another query.

The consumer uses one monotonic 60s deadline including POST, polling and rereads.
Every request receives its remaining timeout; responses at/after the deadline
cannot authorize success or further requests. Six polls is an upper limit, not
a quota: with the first poll after 10s, no sixth request starts at exactly 60s.
New fake-clock cases cover slow POST/GET/reread, exact/over deadline and the
review's 11s-per-request reproduction. This does not add a production frontend.

### Current execution evidence

| Evidence | Result / scope |
|---|---|
| `ad-review-fixes-tests.xml` | **164 passed, 1 skipped** on Linux, 47.65s: corrected consumer/cleanup, all prepared API cases and DB regression. The skipped Compose check passed separately on the host (`ad-review-host-tests.xml`, **1 passed**). |
| `ad-review-writer-tests.xml` | **70 passed**, 32.39s: STAGING/publication regression for the shared bounded transaction helper. |
| `ad-linux-final-tests.xml` | **2,514 passed, 1 skipped**, zero failures/errors; 409.559s. Regular backend regression, not a load run. Includes final production disconnect code and source/boundary tests. |
| `ad-consumer-tests.xml` | **19 passed**, zero failures/skips. Subsequent test-only consumer/lifecycle additions plus the Compose image-pin test skipped inside Linux because Docker CLI is absent. Counts overlap; do not sum. |
| `exact-fixture-tests.xml` | **1 passed**, separate explicit finite dense-fixture check; profiling modules are not automatically collected by the regular suite. |
| `ad-frontend-tests.xml` | **158 passed** on Linux Node 22 / locked Vitest 4.1.11, including both symlink-dependent contract cases. |
| Local checks | Ruff check/format, mypy, seven import contracts; Linux frontend lint/types/build; generated types and exported OpenAPI unchanged. |

After the two review fixes, Ruff check/format, mypy (352 files), seven import
contracts and `git diff --check` passed again. The 2,514-test and frontend results
predate these fixes; the focused results above are the new evidence, not a claim
of another full-suite or load run. Initial Windows expansion lacked the explicit
test Redis variable and hit Alembic's locale decoding problem; the corrected
Linux execution above covers those tests. Starlette TestClient emits existing
deprecation warnings; its in-process timeout argument does not emulate network
timeouts, so deadline boundary evidence comes from the injected-clock scenarios.

Windows frontend initially had two symlink-permission failures and used stale
installed Vitest 3.2.4; the locked Linux environment above is the gate evidence.
Early Windows/Linux regression attempts exposed the fast-reader watcher race and
were interrupted, not counted as passing. The corrected code passed the complete
Linux run. `ad-prototype-*.xml` preserve early test-fixture mistakes (expiry model,
RLS setup and source setup); they are not current validation results.

Remaining work is review of these changes, owner-authorized Git actions and
remote CI, plus the approved phase-9 load/soak/capacity and release checks.
The historical capacity failures remain open. F-11 remains **In Progress** and
production PREPARED mode must not be inferred from these development tests.
