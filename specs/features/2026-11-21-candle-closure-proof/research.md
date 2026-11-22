# Closure proof research

สถานะ: **Research — ไม่ใช่ approval หรือ runtime activation**
วันที่: 2026-11-21 (Asia/Bangkok)

## Primary source

[Binance TH official API documentation, Kline/Candlestick Streams](https://www.binance.th/api-docs/en/#klinecandlestick-streams),
accessed2026-11-21, identifies `k.x` as "Is this kline closed?". The combined public
stream endpoint is `wss://nbstream.binance.th/w3w/wsa/stream`. Native start/end times,
OHLCV and interval/symbol identity accompany that flag. This is evidence for a proposed
closure-proof input, not evidence that reconnect/reordering/REST corrections are harmless.

No Binance Global semantics substituted for TH. Existing TH REST parser exposes no
independent closure flag and remains unsuitable to infer CLOSED from REST alone.

## Existing implementation and standards

- `venues/binance_th/candles.py` constructs UNCONFIRMED REST history.
- `venues/binance_th/candle_stream_mapping.py` preserves x=true as closed_hint and
  UNCONFIRMED. Its test explicitly locks that behavior.
- F12 plan around line500 explicitly scoped the stream to preview, no CLOSED history
  promotion and no stream-to-indicator overwrite. This was deliberate behavior.
- `infra/market_data/storage.py::refresh_due` and F11 RQ9/NC31 distinguish requests
  started before/after end_at while retaining original finality.
- `infra/bots/inputs.py::read_bot_indicators`, RSI/test pure strategies require CLOSED.
  Live preview diagnosis on the Paper Test Entry branch demonstrated green post-end
  candles, ATR READY and zero strategy BUY due to this cross-contract gap.

The proposal therefore amends the shared source contract; it cannot be implemented as
an undocumented parser one-line change or by weakening strategy admission.

## Bounded public observation

One attempt, one public WebSocket subscription for BTCUSDT/ETHUSDT1m, at most75seconds
listening and at most one REST GET per captured closed symbol after the event. No auth,
private account access, database writes, source simulation, Start or orders. Announced
scope and approximate1-2minute duration before running. Capture is a standalone /tmp
research probe, not application implementation or an approved validation campaign.

Raw public observations and REST comparison are in `evidence/public-closure-probe.json`,
with SHA256 beside it. Money/Quantity used for price/volume equality; floating elapsed
seconds are wall-clock timing only. Outcome will be recorded after the single probe.

This observation cannot prove all9 project timeframes, week/month boundaries, outage
recovery, rare corrections, latency guarantees or production load. Such gaps must remain
explicit in the plan/validation; no repeat campaign or Live orders authorized by this probe.

## Result of the single probe

Capture2026-11-21 06:55:00.847949 to06:56:00.728428UTC (13:55-13:56Asia/Bangkok),
59.847seconds elapsed, two native closed events received, no stream error. Candle native
range t1795244100000 / T1795244159999; both event flags boolean true. Observed outcome:

| Symbol | Native identity | OHLC equality | Volume equality | Proposed CP04 result |
|---|---|---|---|---|
| BTCUSDT | Match | Match | WS53.22099000 / REST53.22099000 | Example eligible for full verifier checks; not runtime CLOSED approval |
| ETHUSDT | Match | Match | WS611.04950000 / REST610.94450000 | Conflict; do not promote CLOSED |

Money/Quantity normalized equality used. One sample does not establish why ETH volume
mismatched (lag, correction, upstream aggregation or another cause); no causal explanation
inferred and no delayed re-fetch/repeated campaign performed. It proves that even a real
x=true plus matching OHLC is insufficient for the proposed all-field agreement requirement.
Do not drop volume comparison or introduce a numeric tolerance merely to make this sample
pass. Preserve it as a negative fixture for conflict/repair/retry validation.

BTC is positive evidence that a native closure event and matching post-end REST can be
observed; it is not statistical reliability, proof of every timeframe or an implementation
validation pass. CP05 must keep ETH/source conflicts unavailable for trading until resolved
with accepted evidence. Raw payload timestamps and request-start/response times are in the
JSON artifact, so all temporal claims can be checked independently. SHA256 verified locally.
