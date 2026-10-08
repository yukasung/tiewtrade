# F-10 — actual crash and Redis recovery validation

วันที่: 2026-10-07
สถานะ: V-13/V-14 evidence passed; does not certify the other F-10 gates or external CI.

The validation used a separate disposable PostgreSQL database
`tiewtrade_e2e_f10_recovery` on localhost:55432, existing development DB roles,
its own Redis container `tiewtrade-f10-recovery-redis` on localhost:56382,
and a real Uvicorn API on localhost:58521. It did not interrupt the main
validation Redis on56379 or its producer/database/API. The upstream was the
existing test-only `backend/tests/e2e_realtime_runner.py` fake public feed;
no live venue, account, orders or production fault-injection endpoint was involved.

## V-13 — producer SIGKILL and durable restart

- Authenticated HTTP initially returned READY for all five approved pairs.
- SIGKILL terminated the isolated fake producer process without a CloseEvent.
- At5.314s after the kill, authenticated HTTP returned all five RECOVERING;
  delivery itself remained CONNECTED. The expired producer lease therefore
  invalidated READY without depending on a clean disconnect notification.
- The restarted real QuoteSupervisor advanced durable generation3→5.
  An HTTP snapshot already on generation5 still showed all five RECOVERING,
  followed by all five READY after genuine fake-feed reconciliation.
- No production lease settings or clocks were changed.

## V-14 — actual Redis restart, failed publication and recovery ordering

First, `docker restart tiewtrade-f10-recovery-redis` ran while the API and
producer were alive. Authenticated HTTP sampling at approximately50ms intervals
observed18 RECOVERING snapshots followed by all five READY. The potential
Redis-py silent retry issue did not reproduce in this actual restart run;
no speculative transport configuration change was made.

A stronger stop/start run kept the API and producer alive while Redis was stopped.
The producer continued committing quotes to PostgreSQL, while an actual
RedisNotifications.publish attempt returnedFalse:

| Pair | PG revision before stop | PG revision while Redis unavailable | First recovered HTTP revision |
|---|---:|---:|---:|
| BTC |208|223|224|
| DOGE |209|224|225|
| ETH |209|224|225|
| SOL |207|222|223|
| XRP |209|224|225|

HTTP during the known outage reported delivery RECOVERING and all five rows
RECOVERING. First recovered HTTP returned READY for all five, with revisions
at least as new as every PostgreSQL row observed during the failed-publication
interval. Missed invalidations did not discard the latest durable prices.

A test-only process wrapper observed the real notification subscriber and
broadcaster without editing production modules. On Redis start it recorded:

1. Subscribe server acknowledgement at monotonic35223.426713.
2. PostgreSQL snapshot completion at35223.431294.
3. CONNECTED broadcast at35223.431487, containing exactly the snapshot revisions.

The raw trace proves acknowledgement→PG snapshot→CONNECTED ordering for this
actual recovery; the first recovered HTTP arrived0.194s after the start command
began. Timing is local measurement, not a new latency guarantee.

## Regression checks and artifacts

Ran against the same disposable database and its Redis:

```sh
uv run pytest tests/services/market_data/test_realtime.py::test_failed_commit_rolls_back_quote_and_does_not_publish tests/infra/realtime/test_notifications.py
```

Result: **4 passed in3.32s**. The rollback test exercises a real PostgreSQL
transaction and proves unchanged stored rows and no publication; notification
tests cover acknowledgement, idle heartbeat timeout and actual Redis pong/pubsub.

[recovery-measurements.json](recovery-measurements.json) contains HTTP rows,
server times, revisions, crash/restart timestamps, publish result and the
bounded recovery trace. It contains no cookies, tokens, API secrets or passwords.
Temporary probe scripts were confined to `/private/tmp`; production code was
unchanged. The temporary probe child producer exited when its owning probe
session ended, so the stronger outage run used a dedicated persistent producer
session before collecting its final evidence.

The isolated API/producer processes were stopped, and only the recovery Redis
container/database were removed after validation. The shared development
PostgreSQL service and unrelated validation services remained running.
