# Public Binance Market Data Runtime Design

**Date:** 2026-07-26
**Status:** Approved, implemented, and verified in DEV-99
**Scope:** DEV-99, Phase 1 Paper Trading

## 1. Purpose

TiewTrade needs a reliable path from Binance public market data to the existing
completed-candle business flow. The Runtime must warm indicators with historical
data, receive newly completed candles, repair gaps, and stop new Entry decisions
whenever data continuity or freshness cannot be proven.

This feature does not authenticate with Binance, call a private endpoint, or send
an Order. It is safe to use while Paper Trading remains the only development and
test mode.

## 2. Product Decisions

- Binance public REST provides Historical Klines for indicator Warm-up and
  backfill.
- Binance public WebSocket provides live kline updates.
- The Runtime accepts `symbol` and `timeframe` from immutable Session
  configuration. `BTCUSDT 5m` is the Internal Alpha acceptance scenario, not a
  constant inside business logic.
- Application composition selects a Spot or USDⓈ-M Futures public market-data
  venue from the Session Market Type. Spot and Futures use the same Runtime
  contract but never share or substitute each other's Kline stream.
- Historical Warm-up prepares indicator state only. It must not create an Entry
  Intent, Fill, Basket, or any other trading side effect.
- The Strategy receives only newly completed candles after Warm-up succeeds.
- Warm-up and each REST backfill request must finish within 30 seconds. Failure
  leaves the Runtime fail closed.
- A candle is stale when no completed candle has arrived within 30 seconds after
  its expected close boundary.
- WebSocket reconnect uses three delayed attempts: 1, 2, and 4 seconds. Exhausting
  those attempts leaves the Runtime fail closed until the user starts it again.
- Phase 1 does not persist candles in SQLite and does not include Chart UI.
- All automated tests use fake transports or mocked HTTP/WebSocket sessions. They
  do not require network access or an API Key.

## 3. Architecture

```text
Binance Public REST ---- Historical Warm-up ---+
                                                |
                                                +--> MarketDataRuntime
                                                |
Binance Public WebSocket ---- Live Klines ------+
                                                          |
                                                          v
                                             CompletedCandlePipeline
                                  validation / deduplication / continuity / delivery
                                                          |
                           +------------------------------+------------------+
                           |                                                 |
                           v                                                 v
              MarketDataRuntimeStatus                         Application Candle Sink
          snapshot / watermark / state history                       |
                                                                  Paper Spot / Futures Session
```

The design uses an asynchronous Runtime and one network dependency:

```text
aiohttp>=3.11,<4
```

`aiohttp` owns both public REST requests and the WebSocket connection. This keeps
network work off the future Desktop UI thread and avoids two overlapping network
client dependencies.

### 3.1 Module Ownership

- `market_data/runtime.py` owns Runtime lifecycle, deadlines, source I/O,
  recovery, backfill orchestration, and shutdown.
- `market_data/candle_pipeline.py` owns candle validation, deduplication,
  continuity, and sink delivery. It records a delivery with
  `MarketDataRuntimeStatus.record_delivery(...)` only after the sink succeeds.
- `market_data/runtime_state.py` owns immutable status snapshots, the delivery
  watermark, and state history. `MarketDataRuntime` delegates its public
  `snapshot` and `visited_states` properties to this Status Tracker.
- `integrations/binance` owns Binance endpoint construction, response parsing,
  public REST transport, and public WebSocket transport. It exposes explicit Spot
  and USDⓈ-M Futures endpoint profiles selected by application composition.
- `application` composes the Runtime with the active Session and separates
  indicator-only Warm-up from live Strategy evaluation.
- `strategies` consumes validated candles and does not import Binance or network
  code.
- `execution` remains independent of market-data transport and is never called
  during Warm-up.

Small consumer-owned protocols define the historical source, live source, clock,
sleeper, and application candle sink used by the Runtime. Concrete Binance and
fake test adapters implement those contracts. The contracts expose only the
operations the Runtime needs and do not form a generic exchange SDK.

The public Binance adapter uses the Spot Kline REST/WebSocket APIs for a Spot
Session and the USDⓈ-M Futures Kline REST/WebSocket APIs for a Futures Session.
The Runtime remains venue-agnostic after composition; it receives only normalized
`Candle` values from the selected adapter.

## 4. Runtime State Model

```text
STARTING -> WARMING_UP -> LIVE
               |           |
               |           +-> STALE -> RECONNECTING
               |                           |
               |               success ----+-> BACKFILLING -> LIVE
               |               exhausted --+-> FAILED_CLOSED
               |
               +-> timeout/invalid data -> FAILED_CLOSED

Any active state -> STOPPED after explicit shutdown
```

The Runtime publishes an immutable snapshot after every meaningful transition.
The snapshot contains the state, UTC transition time, the legacy
`last_accepted_open_time` field, and a machine-readable reason. Despite its public
name, `last_accepted_open_time` is the successful-delivery watermark: the Status
Tracker updates it only after the application sink succeeds. Future UI and
Notifications consume this snapshot; they do not infer freshness from raw candles.

`FAILED_CLOSED` is terminal for one Runtime instance. Automatic retry does not
restart after the three attempts are exhausted. A user action creates or starts a
new Runtime instance.

## 5. Historical Warm-up

1. The application requests the number of historical candles required by the
   selected Strategy Preset. The Runtime does not hardcode RSI or ATR periods.
2. For the current RSI(14)/ATR(14) preset, the application requests at least 15
   completed candles.
3. Public REST loads candles ending at the most recent fully closed UTC boundary.
4. The Binance adapter maps decimal strings directly to `Decimal` and milliseconds
   directly to UTC `datetime` values.
5. `CompletedCandlePipeline` validates identity, UTC alignment, continuity, and
   duplicate ordering through its internal `CompletedCandleStream` before the
   batch reaches the application.
6. The application updates indicator state without evaluating Entry conditions or
   invoking execution.
7. Only after the complete Warm-up batch succeeds does the Runtime transition to
   `LIVE` and allow newly completed candles to reach normal Session processing.

The 30-second deadline covers the complete Warm-up operation. Timeout, malformed
data, insufficient completed candles, or a continuity gap transitions directly to
`FAILED_CLOSED`.

## 6. Live Candle Flow

The Binance WebSocket adapter receives kline messages but yields a `Candle` only
when Binance marks the kline as closed. Open updates are ignored at the integration
boundary.

For every yielded candle:

1. `CompletedCandlePipeline` validates symbol, timeframe, UTC alignment, OHLC,
   and volume.
2. The Pipeline passes the candle through its internal `CompletedCandleStream`.
3. Ignore a duplicate already seen by `CompletedCandleStream` without evaluating
   Strategy again.
4. Send the next contiguous candle to the application sink exactly once.
5. Advance the delivery watermark exposed as `last_accepted_open_time`, and its
   derived freshness deadline, only after the sink receives that candle
   successfully.

Messages for another stream identity and malformed Binance payloads do not reach
the Strategy. They produce an explicit Runtime failure reason rather than a
fabricated candle.

## 7. Gap Detection and Backfill

When `CompletedCandlePipeline` reports a missing candle from its internal
`CompletedCandleStream`, the Runtime must not deliver the later candle. It enters
`BACKFILLING` and requests the exact missing UTC range through public REST.

REST backfill paginates until it reaches the latest fully completed candle needed
to restore continuity. Every backfilled candle passes through the same
`CompletedCandlePipeline`, in ascending open-time order, before reaching the live
application sink. The originally observed later candle is naturally deduplicated
if REST already returned it.

Each REST backfill request has a 30-second Runtime deadline. The Pipeline records
the delivery watermark with `MarketDataRuntimeStatus` one candle at a time after
successful sink delivery. If a later delivery fails, the snapshot therefore
reports the last candle actually delivered rather than the end of the requested
batch.

The Runtime returns to `LIVE` only after the backfill range is contiguous and the
WebSocket stream is active. Empty, malformed, incomplete, or still-gapped backfill
data leaves the Runtime fail closed.

## 8. Stale Data and Reconnect

The Runtime calculates the next freshness deadline as 30 seconds after the next
expected completed-candle boundary. Crossing that deadline without successfully
delivering the expected candle immediately transitions to `STALE`; no new Entry
decision is allowed.

A WebSocket disconnect or stale deadline starts reconnect attempts after 1, 2,
and 4 seconds. Each successful connection enters `BACKFILLING` before returning to
`LIVE`, even when no missing candle is ultimately found. This proves continuity
between the last successfully delivered candle and the current public market
state.

If all three attempts fail, the Runtime transitions to `FAILED_CLOSED`. Existing
Basket state and Paper history remain unchanged. DEV-99 does not implement Stop
Session, Take Profit placement, or Recovery policy beyond preventing new candle
delivery to the Session.

## 9. Shutdown

Explicit shutdown stops accepting new WebSocket messages, cancels freshness and
retry timers, closes a public REST/WebSocket client session owned by the Binance
adapter, and transitions to `STOPPED`. A session injected by another owner is not
closed by the adapter. Shutdown is idempotent and awaits child-task completion so
network work does not survive the Runtime lifecycle.

Shutdown does not close an open Basket, fabricate a final candle, or change durable
trade history.

## 10. Failure Handling

- Public REST non-success responses, timeouts, malformed JSON, or invalid Binance
  values fail closed with a stable reason.
- Public WebSocket protocol errors or disconnects enter the bounded reconnect
  flow.
- Candle validation and continuity errors never get converted into permissive
  warnings.
- A callback or application sink failure stops further delivery and fails closed;
  the Runtime must not skip the failed candle and continue.
- Runtime state changes are monotonic according to the state model. A failed
  instance cannot silently return to `LIVE`.
- No error path falls back to cached, invented, or partially validated candles.

## 11. Verification

Unit and integration verification must cover:

- Binance REST and WebSocket payload mapping with exact `Decimal` and UTC values.
- Rejection of an open kline update.
- Strategy-selected Warm-up count and ascending completed-candle delivery.
- Indicator Warm-up without Entry Intent, Fill, or Basket side effects.
- Warm-up timeout after 30 seconds.
- Duplicate delivery without duplicate Strategy processing.
- Gap detection, paginated REST backfill, and ordered resume.
- Stale transition 30 seconds after the expected close boundary.
- Reconnect attempts after exactly 1, 2, and 4 seconds.
- Fail closed after the third unsuccessful reconnect.
- Reconnect success followed by mandatory backfill before `LIVE`.
- Backfill that remains discontinuous never returning to `LIVE`.
- Idempotent shutdown and cleanup of network/timer tasks.
- An end-to-end fake transport flow from Warm-up through a live completed candle
  into Paper Spot application processing.
- Confirmation that tests do not require credentials, private endpoints, or live
  Orders.

Repository verification must run the relevant tests plus the complete quality
gates defined in `PROJECT_PLAN.md`.

## 12. Out of Scope

- Binance private API authentication and account streams.
- Live Spot or Live Futures Order execution.
- Persistent candle storage.
- Candlestick Chart UI and historical market browsing.
- Multiple active Sessions, multiple Binance Accounts, or sub-accounts.
- Generic multi-exchange market-data abstractions.
- Unlimited reconnect loops.
