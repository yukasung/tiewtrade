# F-10 — Final local validation

วันที่: 2026-10-07
ผล: Local functional validation ผ่าน V-1..V-32

## Verification

- Backend full suite: **1780 passed**,2 live venue_contract tests deselected.
- Backend Ruff/format, mypy261 files and7 import contracts passed.
- Frontend lint/typecheck/build, **132 Vitest tests passed**.
- Full Playwright browser suite: **10 passed** after isolating repeated F09 fixtures.
- Generated OpenAPI/frontend types regenerate identically; git diff --check passed.
- Final isolated Compose build/startup passed with internal Redis process ACLs.
- Two final read-only reviewers found no remaining concrete spec/security blockers.

## Criteria coverage

| Criterion | Evidence | Result |
|---|---|---|
| V-1 | Venue isolation/import/network/safety gates; no private market credentials. | PASS |
| V-2 | Feed five-pair validation, forged symbols and push-only API frame rejection. | PASS |
| V-3 | Money parser/DB/API roundtrips, exact string models and browser display. | PASS |
| V-4 | Core exact10s/10s+1µs and duplicate/receipt-independent age tests. | PASS |
| V-5 | Core/adapter missing, malformed and future timestamps; E2E silent stream stale. | PASS |
| V-6 | Actual PG disconnect-before-cleanup regression and E2E upstream outage. | PASS |
| V-7 | ACK gate, controlled delayed per-pair recovery and E2E awaiting snapshot. | PASS |
| V-8 | Partial-order properties, scoped duplicates, persisted latch, pre-detection attempt token and old epochs. | PASS |
| V-9 | Deterministic capped/stable60s backoff and HTTP/WSS429/418 Retry-After minimum tests. | PASS |
| V-10 | Controlled ACK deadlines/races/control frames/rotation plus localhost WSS server. | PASS |
| V-11 | Actual DB-role grants, RLS and0014 upgrade/downgrade/replay. | PASS |
| V-12 | Concurrent writer lease takeover, stale owner/generation rejection and recovery-task fencing. | PASS |
| V-13 | Actual SIGKILL producer, lease expiry, new durable generation before readiness: recovery-validation.md. | PASS |
| V-14 | Actual PG rollback/no publication and Docker Redis outage/restart with failed publication retaining PG updates. | PASS |
| V-15 | Subscribed ACK before PG read, missed-publication recovery and Redis6900 notification burst. | PASS |
| V-16 | Central ASGI guard inventory/default denial, HTTP/WS shared presented owner helper. | PASS |
| V-17 | NC-28 start-anchored authorization window, blocked query/send, actual expiry/revocation and no renewal. | PASS |
| V-18 | Origin missing/wildcard/foreign, query token denial and auth failure closed tests. | PASS |
| V-19 | Pydantic/generated TS contract and runtime decoder; protocol/app limits and exact strings. | PASS |
| V-20 | Latest slot queue, slow client cleanup, resource probe task recovery507→5. | PASS |
| V-21 | Deferred GET/WS, BigInt/microsecond ordering, identity/epoch cleanup tests. | PASS |
| V-22 | Browser offline/close/watchdog/resume and E2E reconnect waiting for fresh full view. | PASS |
| V-23 | Approved server-observed status and timestamps, no browser current-ready proof; delayed/clock tests. | PASS |
| V-24 | Actual cold migration59.999/60s, restart interval, server market warning and immediate known delivery warning. | PASS |
| V-25 | Thai/English panel/ARIA transitions, exact values, six inspected screenshots360/1440. | PASS |
| V-26 | Actual fake producer→PG→Redis→API→browser full-flow E2E; no API quote mock. | PASS |
| V-27 | Full1780 backend/132 frontend/10 E2E regression; F09 queue fixture isolated on repeated E2E. | PASS |
| V-28 | Readonly public price route/grant/scope review; no orders, account stream, PnL, bots or Live execution. | PASS |
| V-29 | Actual100/101 TCP, actual16/17 guards pre-lookup, three sessions across two API processes. | PASS |
| V-30 | Actual Redis31/IP/201/global no lookup, token bucket/CAS tests and forged forwarding header ignored. | PASS |
| V-31 | Cancel/accept failure/close/session expiry, actual cross-process slot replacement and stale owner CAS. | PASS |
| V-32 | Realtime pool3/overflow0, bounded tasks, DB lock/Redis1s delay failclosed while interactive HTTP200. | PASS |

## Detailed artifacts

- [Resource validation](resource-validation.md) and [measurements](resource-measurements.json)
- [Actual recovery validation](recovery-validation.md) and [measurements](recovery-measurements.json)
- Screenshots: ready-th/en360/1440, market-warning-th360, delivery-warning-th360.
- Regression fixes verified: recovery-failure supervision, failure reasons, cold-start
  interval, ACK/rotation boundaries, reconnect Retry-After, old callbacks and immediate
  disconnect persistence before cleanup.

## Limits and integration

Measurements describe this development machine, not a production performance SLA.
Live venue_contract remains a separate daily job; normal verification uses recorded
fixtures and fake public quotes. No orders/Live/account stream were introduced.
External GitHub CI has not run because no commit/push was authorized. Before merge,
all required remote CI jobs must be green under testing.md; no merge was performed.
Work remains uncommitted on feature/f-10-realtime-prices as instructed.


## Follow-up verification — 2026-10-08

The2026-10-07 verification/reviewer statements above are historical. Subsequent
deep review findings1–7 now have fixes; a new deep review has not yet been run.
Owner approved NC-29 before adding the scoped inbound-decoder gate exception.

- Backend full:1851passed,2live venue tests deselected,no skips (114.36s).
- Frontend158Vitesttests plus lint/typecheck/build passed.
- Playwright10passed (52.0s), including authenticated257byte message closing1008.
- Wire/logging23tests passed; oversized UTF-8/binary/fragments/compressed messages
  are rejected without delivery to ASGI; native ping/pong and other failure codes preserved.
- Boundary/purity/isolation/asyncio/wire/logging253tests passed, including22new
  scoped decoder fixtures. Full Ruff/format, mypy266files,7import contracts passed.
- Docker Linux frozen build/protocol loader and lock freshness passed.
- Writer expiry during SQL waits:7actual PostgreSQL lock races reject and roll back;
  BIGINT maximum trade ID reads back exactly; oversized REST/WS IDs fail before DB.

Detailed fixes and authorization are recorded in feature validation.md/plan.md.
Existing resource/recovery measurements remain their original dated evidence.
No new externalCI result, final review approval, commit, push or merge is claimed.


### 2026-10-08 — Full local validation after latest review fixes

- Full backend: **1870 passed, 2 live venue-contract tests deselected, no skips**,
  123.07s; 3 existing Starlette deprecation warnings.
- Frontend: **158 passed**; ESLint, TypeScript and Vite production build passed.
- Playwright: **10 passed (1.1m)** against isolated `tiewtrade_e2e_f10`,
  real API/Vite/PostgreSQL/Redis and controlled fixture producers; no live orders.
- Backend Ruff/format (268 files), mypy (267 files), 7 import contracts,
  offline lock freshness (55 packages), and in-memory OpenAPI/schema comparison passed.
- PostgreSQL16/Redis7 used disposable containers, separate from application data.
  Original API/frontend were temporarily stopped for ports8000/5173 and restored;
  API health and frontend HTTP200 verified. Test containers/volumes removed.

Local validation after the three latest fixes is complete. Deep code review was
APPROVED before this run; no implementation changes were required by these tests.
Remote CI and merge remain pending; no commit/push/merge performed. Docker image
rebuild and live venue-contract probes were not rerun as part of this test task.
