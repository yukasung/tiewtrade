# Offline delivery and explicit socket teardown

สถานะ: **Approved — owner continuous-completion instruction / AGENTS engineering delegation,2026-11-14**

Post-mergea116114: main browser35 Passed/1Failed at realtime-prices.spec.ts:137,
closeCode undefined after offline + explicit WebSocket.close within existing5s.
Keep historical failure. Graceful close requires transport cooperation; this
probe teardown is separate from product offline detection (F07 V22/V24).

Before code: keep offline while asserting API remains READY, restore connectivity,
explicitly close old probe and await real close event, then replace stream and
assert READY. Keep90s test, existing poll budgets, exact frame1008/revocation4401,
HTTP401 and schema/money/status assertions. No synthetic events, mock close,
production or timeout/acceptance changes. Independently validate existing offline,
close/heartbeat and reconnect behaviors instead of imposing an offline handshake.

Exact case on fresh isolated DB/Redis with real producer/API/WS; lint/types/diff
review, then PR/requiredCI/merge/postmerge when gates pass. Maintain3-round stop
rule and analyze any failure before subsequent attempts. No unrelated refactor.


## Local validation

Exact real producer/PG/Redis/API/WS case1 Passed22.1s, including1008 frame-close,
offline API READY, explicit old close event, reconnect READY, logout4401/HTTP401.
Scoped frontend ESLint/TypeScript and diff check Passed. Fixture database dropped
with0 connections; dedicated Redis removed. Private log:/tmp/ws-offline-browser.log.
Reviewed3-line ordering diff: no assertion deletion or timeout change, no production
change; no additional abstraction/refactor needed. Initial prep command used backend
cwd for repo-relative docs and failed before edits; corrected to root before source
changes. Publish/follow requiredCI and main CI under standing owner authorization.
