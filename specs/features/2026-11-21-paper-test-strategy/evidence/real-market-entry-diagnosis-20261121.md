# Real-market entry diagnosis - 2026-11-21

Scope: owner requested a detailed investigation of no BUY after visible candle close.
Read-only runtime/source/spec review; no implementation change, trading instruction,
source mutation, new run or finality bypass.

## Confirmed root cause - High functional/integration blocker

The installed Binance TH REST adapter always constructs UNCONFIRMED candles
(`backend/src/tiewtrade/venues/binance_th/candles.py:153`). The stream mapper also keeps
UNCONFIRMED when x=true/closed_hint or the interval ends (`candle_stream_mapping.py:57`);
`tests/venues/binance_th/test_candle_stream_mapping.py:154` explicitly asserts that behavior.
No CLOSED producer/closure-acceptance step is established in this active source pipeline.

Shared strategy indicator input rejects UNCONFIRMED before strategy evaluation
(`infra/bots/inputs.py:227`). Both Paper Test Entry (`strategies/paper_test/strategy.py:67`)
and RSI Step Grid (`strategies/rsi_step_grid/strategy.py:83`) independently require CLOSED.
Using the same RSI rule preserves this incompatibility; it does not make real-source
candles eligible. Waiting another bar, choosing another timeframe/strategy, retrying Start
or hiding readiness messages does not repair the current contract mismatch.

This is a system integration limitation, not evidence that a market candle's time interval
has not ended. The user-visible completed green candle can genuinely exist while the
application's stricter CLOSED capability remains unavailable. We have NOT established that
the external venue can never provide usable closure evidence; the installed application
currently does not accept such evidence as CLOSED.

## Runtime evidence

Captured owned preview at2026-11-21 06:47:12UTC (13:47:12 Asia/Bangkok):

- Active strategy paper-green-atr-test, BTC/USDT,1m,100USDT, PAUSED revision19.
- State pending_id=null, pending_filled=false, entry_sequence0, last_candle=null.
- Source events alternate INDICATOR_NOT_READY during refresh then BOT_CANDLE_UNCONFIRMED.
- Signal candle06:46-06:47UTC: open57299.99, close57358.39 (green), finalityUNCONFIRMED.
  OHLC fetch started06:47:11.196098UTC, after its06:47:00 end; thus the interval ended
  and a post-end fetch occurred. That satisfies F11's display/calculation eligibility,
  not F09 closure proof or the approved strategy admission requirement.
- Latest eight sampled BTC1m candles all UNCONFIRMED, including multiple green candles.
- bot_decisions0, bot_order_links0, nonzero position projections0 in this owned preview.
  There is no strategy BUY reaching sizing/matching/exchange rejection in this trace.
  This does not certify that every downstream balance/risk/book gate would pass after
  a future finality fix; those stages were not reached by this signal.
- Direct owned indicator read: one point, ATR READY, finalityUNCONFIRMED.
- Authenticated status GET: PAUSED, BOT_CANDLE_UNCONFIRMED, positions0.

The diagnostic helper initially matched multiple historical test runs; narrowed it to
active run statuses before the reported indicator read. No DB rows were changed.

## Specification boundary

F09 RQ6 and its approved REST limitation preserve UNCONFIRMED without closure proof.
F11 RQ9/NC31 permits calculation from post-end-fetched UNCONFIRMED but explicitly does
not turn it into CLOSED or authorize trading. F21 and Paper Test Entry use CLOSED-only;
owner reaffirmed and approved the same-RSI rule. Each module follows its local contract,
but the assembled real-source entry flow has no usable CLOSED producer.

Do not change UNCONFIRMED to CLOSED merely because time passed, REST returned, ATR is
READY or a WebSocket hint arrived. Any accepted closure-proof mechanism must have a
reviewed source contract, durable provenance and owner-approved requirements/plan/validation
before changing this boundary. The superseded UNCONFIRMED trading proposal stays inactive.

## Validation gap - Medium

Existing financial/browser acceptance tests use controlled CLOSED fixtures. Those tests
remain useful and passed within that declared scope, but they do not prove that the
production-shaped market adapter can provide a tradable signal. An actual source-adapter
through strategy admission test with accepted closure evidence is required before claiming
real-market entry readiness. Real-source entry is Blocked, not Passed/Completed.

## Checks

`pytest tests/venues/binance_th/test_candles.py
 tests/venues/binance_th/test_candle_stream_mapping.py
 tests/strategies/test_rsi_step_grid.py tests/strategies/test_paper_test_strategy.py
 tests/infra/bots/test_candle_finality_reason.py`: **263 passed in1.29s**.
These fixture/pure tests reproduce both sides of the incompatibility, not its resolution.
Evidence logs: deep-source-tests.log, deep-source-diagnostic.log. Diff whitespace check passed.
No new tests asserting a different trading policy and no live venue orders were introduced.

## Recommendation / next step

Prepare a shared source-finality contract/design that can legitimately produce a tradable
CLOSED capability, validate actual venue evidence and uncertainty, and obtain the required
source/trading approval before implementation. Preserve Money/Quantity, first-fill TP/SL,
one-position, freshness/recovery/STOP and retry/idempotency rules. Validate actual adapter
payload -> durable evidence -> indicator -> strategy -> guarded Paper BUY, including
corrections and reopen/replay races. Do not label a compatibility fix complete on fixture
passes alone. Current owner visual/required CI/Batch/Release gates remain pending.
