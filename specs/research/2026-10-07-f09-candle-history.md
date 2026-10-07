# F-09 — Candle history evidence for NC-09 / T-04

สถานะ: **Research — ไม่ใช่ข้อกำหนด implementation ที่อนุมัติ**

NC-09/T-04 ปิดจากคำยืนยันเจ้าของภายหลังการวิจัยนี้; ดู [decision](2026-10-07-f09-decisions.md). ข้อเท็จจริงและช่องว่างหลักฐานด้านล่างไม่เปลี่ยนจากการอนุมัติ.

Verified date: **2026-10-07**. Initial findings were documentation research;
the public-contract appendix below records later bounded live public reads.
No credentials, implementation changes or trading operations. Scope is **Binance TH**;
Binance.com behavior has not been substituted for Binance TH evidence.

## Documented facts

| Topic | Verified statement | Primary source |
|---|---|---|
| REST | Public `GET /api/v1/klines`; required symbol/interval; optional startTime/endTime/limit. Weight(IP)=1; default/max limit=500/1000. Oldest-first; identified by open time. Defaults: start=10 days ago, end=now. | [Kline/Candlestick Data](https://www.binance.th/api-docs/en/#kline-candlestick-data) |
| Intervals | `1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M`; proposed `1m,5m,15m,1h,4h,1d` all supported. | [Kline/Candlestick Data](https://www.binance.th/api-docs/en/#kline-candlestick-data) |
| Payload | REST arrays contain open/close times, OHLC, volumes, trades; no closure flag shown. Time fields are milliseconds. | [REST payload](https://www.binance.th/api-docs/en/#kline-candlestick-data), [General API Information](https://www.binance.th/api-docs/en/#general-api-information) |
| Streaming | `<symbol>@kline_<interval>`; same intervals; `k.x` indicates closed. Prose says every second; update-speed says 2000ms. | [Kline/Candlestick Streams](https://www.binance.th/api-docs/en/#kline-candlestick-streams) |
| Lifecycle | `wss://nbstream.binance.th/w3w/wsa/stream?streams=...`; lowercase symbols; 24h connection; ping 3min/pong deadline 10min; 1024 streams; 5 incoming control/frame messages/sec. | [General WSS information](https://www.binance.th/api-docs/en/#general-wss-information), [Websocket Limits](https://www.binance.th/api-docs/en/#websocket-limits) |
| Quota | Shared per IP, not key; weight headers; 429/418 require backoff with Retry-After. | [LIMITS](https://www.binance.th/api-docs/en/#limits) |

## Evidence gaps — not promises

The reviewed sections do not establish historical retention, maximum query span,
boundary inclusivity, candle timezone alignment, replay guarantees, empty-period
behavior or delivery SLA. No `timeZone` parameter is listed for klines. The
ten-day default is not a historical-retention limit. [Official reference](https://www.binance.th/api-docs/en/)

In particular, documentation support for requesting a time range does **not**
prove that one year of candles exists for every selected symbol. A new symbol
cannot have a pre-listing exchange history; missing history must remain explicit
rather than being synthesized as real exchange observations.

## Repository evidence

- [mission.md](../mission.md) §9 records the NC-09 choice for chart/strategy timeframes
  and indicators; [tech-stack.md](../tech-stack.md) records the approved T-04 PostgreSQL/365-day choice.
- [F-33 requirements](../features/2026-09-28-venue-layer/requirements.md)
  explicitly excludes candle contracts. Existing
  [PriceSource](../../backend/src/tiewtrade/venues/prices.py) returns the latest
  price with venue/receipt timestamps, not a historical OHLCV series.
- [Endpoint](../../backend/src/tiewtrade/venues/binance_th/endpoints.py) currently
  lists TRADES, EXCHANGE_INFO and ACCOUNT; it does not expose klines. This is
  intentional prior scope, not an implementation defect to bypass.
- [market_data/main.py](../../backend/src/tiewtrade/services/market_data/main.py)
  is still a placeholder. There is no existing ingestion worker to count as done.
- [Database standard](../standards/database.md) §2/§5/§7 specifies UTC storage,
  market-data writes restricted to price/candle tables, time partitioning and
  defined retention. Its current document status is **Proposed**; this note does
  not change that status or independently approve an architecture.

## T-04 comparison — engineering inference, not a decision

Both approaches are technically plausible candidates. The difference is who
owns the history after retrieval, and what must happen when that history is
missing or temporarily unavailable.

The retention targets currently under discussion are **one year** or **90 days**
for PostgreSQL. The owner subsequently chose the 365-day PostgreSQL target in the linked decision. Retention means
how long local observations are kept; availability means which observations
can actually be obtained. Neither local target guarantees upstream history or
requires an immediate full backfill of every symbol and interval.

| Candidate | Benefit to evaluate | Work / limitation to specify |
|---|---|---|
| Fetch upstream for each chart request | Fewer persistent components and no local history-retention job | Each request depends on upstream availability and quota; concurrent users requesting the same series repeat work unless requests are coalesced/cached. Must bound chart ranges, retries and failure behavior. |
| PostgreSQL cache/history with bounded initial load and on-demand backfill | Can reuse already retrieved series across chart reads; can retain the observations the app actually received | Requires ingestion ownership, partition/retention jobs, uniqueness/upserts, source provenance, gap detection/repair and explicit coverage reporting. Cache presence alone does not prove freshness/completeness. |

No measurements were performed. Neither approach has a demonstrated latency,
operating cost, storage size or uptime advantage in this repository. A cache
hit can avoid an upstream history fetch by design; the magnitude of any benefit
depends on observed requests, symbols, intervals and cache coverage.

The candidate rule “initially fetch at most 1000 candles per pair/interval,
then backfill on demand” needs an **explicit time cutoff** as well as a row cap
if the owner chooses either retention target. Independent fixed-interval arithmetic:

| Interval | Span of 1000 consecutive full candles |
|---|---:|
| 1m | 16h 40m |
| 5m | 3d 11h 20m |
| 15m | 10d 10h |
| 1h | 41d 16h |
| 4h | 166d 16h |
| 1d | 1000d |

Thus a row cap is neither a promise of one-year coverage nor a retention cutoff.
The approved local target defines “one year” as a fixed 365-day window.
For capacity estimates after scope approval, a 365-day window has 525600 one-minute
slots per continuously covered pair; this is row arithmetic, not an estimate of
actual stored bytes or actual exchange coverage.

## Validation candidates for the later approved plan

These are proposed checks, not approved contracts:

1. Record public klines responses for selected SITE/GLOBAL symbols and intervals;
   verify array/envelope shape, decimal strings, timestamps and error shapes.
   The published sample has questionable comma formatting; do not treat prose
   examples as a validated parser contract.
2. Check explicit bounded historical queries, boundary behavior and earliest
   available data before promising one-year backfill. Pagination can be designed
   around returned open times with overlap/deduplication, but its exact cursor
   rule should follow verified boundary behavior rather than guessed inclusivity.
3. Verify candle boundary alignment, current REST candle behavior, and REST/WS
   reconciliation. A close-time field alone is insufficient evidence that the
   latest returned candle is final. Keep open and final observations distinct.
4. Validate reconnect/gap repair without claiming streams replay missed data;
   test duplicate/out-of-order events and replacement of partial observations.
5. Agree indicator formulas/seeds/warmup, insufficient-history behavior and
   whether strategies consume only closed candles. Choosing indicator names
   does not define these trading semantics or authorize inventing them.

This note supports the owner's NC-09/T-04 discussion only. F-09 still needs its
own requirements, approved plan/validation and resolved relevant clarifications
before implementation.

## Public REST contract probes — 2026-10-07

Official [Binance TH reference](https://www.binance.th/api-docs/en/#kline-candlestick-data)
was reread before probing. **11 sequential, credential-free GET requests** were
sent to `https://api.binance.th/api/v1/` between **10:17:29 and 10:18:11 UTC**.
No websocket, account endpoint, trading request, full-history query or 365-day
coverage query was made. One earlier sandbox DNS failure returned no HTTP
response; network escalation then enabled the public reads. No 429/418 occurred.

The [fixture directory](2026-10-07-f09-public-contract/) contains the exact URL,
query parameters, local UTC request/receipt times, HTTP status, public response
body and only Date/Content-Type/X-MBX/Retry-After response headers where present.
No credentials, cookies, account identifiers or request environment were recorded.
`02-exchange-info.json` retains six relevant public symbols; other top-level
fields are unchanged, with original-response length/SHA-256 and projection
description recorded. Other response bodies are retained verbatim as strings.

### Requests and observed results

All candle requests supplied explicit start/end times. The timestamp reference
was `/time` response `serverTime=1791368250194`.

| Fixture | Exact request parameters (endpoint is klines unless stated) | Observed result |
|---|---|---|
| [01](2026-10-07-f09-public-contract/01-time.json) | `/time`, no parameters | HTTP200; object with integer serverTime |
| [02](2026-10-07-f09-public-contract/02-exchange-info.json) | `/exchangeInfo`, no parameters | HTTP200; timezone UTC; all five seed symbols GLOBAL/TRADING; BTCTHB SITE/TRADING |
| [03](2026-10-07-f09-public-contract/03-btc-usdt-1m.json) | symbol=BTCUSDT, interval=1m, startTime=1791367920000, endTime=1791368250194, limit=10 | HTTP200; six rows |
| [04](2026-10-07-f09-public-contract/04-btc-usdt-1d.json) | symbol=BTCUSDT, interval=1d, startTime=1791158400000, endTime=1791368250194, limit=10 | HTTP200; three rows, including current UTC day |
| [05](2026-10-07-f09-public-contract/05-btc-thb-site-1m.json) | symbol=BTCTHB, interval=1m, startTime=1791367920000, endTime=1791368250194, limit=10 | HTTP200; six rows |
| [06](2026-10-07-f09-public-contract/06-boundary-exact.json) | symbol=BTCUSDT, interval=1m, startTime=1791368040000, endTime=1791368040000, limit=10 | HTTP200; exactly the row opening at 1791368040000 |
| [07](2026-10-07-f09-public-contract/07-boundary-start-plus-one.json) | symbol=BTCUSDT, interval=1m, startTime=1791368040001, endTime=1791368100000, limit=10 | HTTP200; only row opening at 1791368100000 |
| [08](2026-10-07-f09-public-contract/08-boundary-end-minus-one.json) | symbol=BTCUSDT, interval=1m, startTime=1791367980000, endTime=1791368039999, limit=10 | HTTP200; only row opening at 1791367980000 |
| [09](2026-10-07-f09-public-contract/09-max-limit-1000.json) | symbol=BTCUSDT, interval=1m, startTime=1791308280000, endTime=1791368250194, limit=1000 | HTTP200; exactly 1000 rows |
| [10](2026-10-07-f09-public-contract/10-over-limit-1001.json) | symbol=BTCUSDT, interval=1m, startTime=1791368040000, endTime=1791368100000, limit=1001 | HTTP400; code=-1130, limit parameter invalid |
| [11](2026-10-07-f09-public-contract/11-unknown-symbol.json) | symbol=NOTAREALSYMBOL, interval=1m, startTime=1791368040000, endTime=1791368100000, limit=1 | HTTP400; code=-1121, Invalid symbol |

These are observations at the recorded times, **not general guarantees**:

- Successful candle bodies were bare JSON arrays, without a success envelope.
  Every observed row had 12 fields: integer open time, four OHLC strings, base
  volume string, integer close time, quote volume string, integer trade count,
  two taker-volume strings and trailing string `0`. Open times were strictly
  increasing. Decimal precision differed between SITE/THB and GLOBAL/USDT;
  the adapter must not assume every decimal string has the same scale.
- GLOBAL BTCUSDT and SITE BTCTHB both accepted normal symbol names, without an
  additional type parameter. ExchangeInfo established the five seed pairs'
  metadata, but klines were not requested for the other four seed pairs.
- For these BTCUSDT 1m samples, the range was inclusive on **open time** at both
  ends. Moving startTime one millisecond past a known open excluded that row;
  moving endTime one millisecond before it excluded it. A prospective pagination
  rule using `last_open_time + 1ms` is supported by these samples; it remains a
  plan proposal requiring bounds, monotonic progress and duplicate checks.
- The observed daily open times align to 00:00 UTC and minute open times to UTC
  minute boundaries. This establishes the tested samples only, not every
  interval/symbol's boundary convention or future venue behavior.
- Current-day and then-current-minute rows were returned with scheduled close
  timestamps beyond the `/time` reference. REST supplies no closure flag.
  **Finality remains UNKNOWN** as a proposed conservative domain representation;
  this research does not promote a REST row to CLOSED merely because closeTime
  has passed, a later row exists or repeated reads match. The observed same-minute
  volume changed between fixtures03/09, illustrating mutable observations, not
  proving when they become immutable.

### Weight discrepancy requiring explicit treatment before implementation

Published klines weight remains **1**, but recorded `X-MBX-USED-WEIGHT-1M`
values in the same minute were `1 → 2 → 3 → 8 → 18 → 19` for fixtures06–11.
Thus the observed increases for the 1000-row call and invalid-limit call were
**5** and **10**, respectively; the other calls in that sequence increased by1.
The header is shared per IP, so this bounded run cannot prove exclusive causal
cost or a complete weight schedule. It does show that blindly planning fixed
weight1 for every klines request lacks adequate evidence.

| Fixture | HTTP Date (UTC, 2026-10-07) | Used weight 1m | Difference from preceding response |
|---|---|---:|---:|
| 01 time | 10:17:30 | 1 | No baseline |
| 02 exchangeInfo | 10:17:30 | 11 | +10 |
| 03 limit10 | 10:17:51 | 12 | +1 |
| 04 limit10 | 10:17:51 | 13 | +1 |
| 05 limit10 | 10:17:52 | 14 | +1 |
| 06 limit10 | 10:18:08 | 1 | Minute changed; not comparable |
| 07 limit10 | 10:18:08 | 2 | +1 |
| 08 limit10 | 10:18:09 | 3 | +1 |
| 09 limit1000 | 10:18:09 | 8 | +5 |
| 10 invalid limit1001 | 10:18:10 | 18 | +10 |
| 11 unknown symbol/limit1 | 10:18:11 | 19 | +1 |

No klines limit-based cost tiers were found in the current official reference.
The published limit tiers in [Order Book](https://www.binance.th/api-docs/en/#order-book)
belong to `/depth`; they cannot be assigned to `/klines`. Do not reinterpret the
observed +5/+10 as verified reservation costs. A twelfth request was not made:
another shared-IP header delta would not establish exclusive accounting.

No additional requests were made to resolve the discrepancy or provoke rate
limits. The plan must explicitly address an authoritative cost contract versus
observed shared usage, reusing the venue limiter rather than silently changing
its approved accounting behavior. Any unresolved venue-cost rule should remain
a named clarification; this research does not select a financial or architecture
policy to work around it.

### Still unknown after these probes

Historical retention, earliest available candle for each pair, listing-time
identification, true missing-period semantics, long-window limits, correction
policy/finality, delivery SLA and other interval boundaries remain unverified.
No observation above establishes 365-day availability or distinguishes a
before-listing absence from a genuine ingestion gap. Current requirements and
owner decisions are maintained by the root agent; this appendix grants no code
or plan approval.

## Follow-up public probes — six additional authorized GETs

After the initial probe budget, the root agent authorized a separate six-request
read-only budget to verify remaining intervals and a candidate page size500.
Fixtures12–17 contain six sequential credential-free `/klines` GET responses
between **10:22:19 and 10:22:21 UTC, 2026-10-07**. The only request header supplied
was `Accept: application/json`; no new server-time request was made. The common
endTime `1791368538921` came from the local UTC clock and is recorded as a probe
bound, not a new trusted exchange-clock contract. No 429/418 occurred.

All requests below used symbol=BTCUSDT and endTime=1791368538921:

| Fixture | interval / startTime / limit | Result | HTTP Date UTC | Used weight1m / preceding delta |
|---|---|---|---|---|
| [12](2026-10-07-f09-public-contract/12-btc-usdt-5m.json) | 5m / 1791368400000 / 1 | HTTP200, one row | 10:22:19 | 1 / no same-minute baseline |
| [13](2026-10-07-f09-public-contract/13-btc-usdt-15m.json) | 15m / 1791368100000 / 1 | HTTP200, one row | 10:22:19 | 2 / +1 |
| [14](2026-10-07-f09-public-contract/14-btc-usdt-1h.json) | 1h / 1791367200000 / 1 | HTTP200, one row | 10:22:20 | 3 / +1 |
| [15](2026-10-07-f09-public-contract/15-btc-usdt-4h.json) | 4h / 1791360000000 / 1 | HTTP200, one row | 10:22:20 | 4 / +1 |
| [16](2026-10-07-f09-public-contract/16-limit-500.json) | 1m / 1791338580000 / 500 | HTTP200, 500 rows | 10:22:21 | 9 / +5 |
| [17](2026-10-07-f09-public-contract/17-limit-500.json) | 1m / 1791338580000 / 500 | HTTP200, 500 rows | 10:22:21 | 14 / +5 |

Observed rows for5m/15m/1h/4h had the same12-field type sequence as the initial
samples. Their open timestamps were divisible by their fixed interval durations
in milliseconds, and `close_time - open_time + 1` equaled300000,900000,3600000
and14400000, respectively. These samples support UTC epoch alignment and inclusive
scheduled close boundaries for the tested rows; they do not prove general
immutability or finality. Together with fixtures03/04, all six approved intervals
now have a live BTCUSDT shape observation.

Both500-row pages had strictly increasing consecutive minute opens from
1791338580000 through1791368520000 and the same12-field types. Latest-row volume
changed between reads; neither stable historical rows nor a changed latest row
defines a finality rule. **Proposed REST finality remains UNKNOWN** underRQ-6.

The two additional observed weight deltas were both+5. Consequently, page500
is supported as a bounded working request size, but **weight1 for page500 is
not supported by these observations**, and reducing page1000to500 is not a
demonstrated quota remedy. Shared-IP accounting still prevents converting any
single or repeated delta into a guaranteed isolated endpoint cost. The research
does not approve reserving5/10, invent a tier schedule or change venue limits;
the documented-versus-observed cost question still requires explicit resolution
or an approved uncertainty guard in the later plan.
