# Empty baseline / first trade implementation

วันที่: 2026-10-13 (Asia/Bangkok)
เจ้าของ approve preview-first-trade amendment; NC-43 closed.

## Change

Core compare recognizes only the approved empty baseline: zero trade count,
both IDs -1, exact Quantity zero, and no closed hint. The first positive-count
snapshot for the same candle establishes its OHLCV head even when open changes;
late empty snapshots cannot replace that head. All other cumulative comparisons
and conflict/finality/freshness rules remain unchanged. No timestamp tiebreak,
raw Decimal/float financial arithmetic, order submission or synthetic READY.

## Verification

- [first-trade-tests.xml](first-trade-tests.xml): **25 passed** across supervisor,
  preview persistence and venue stream mapping. Includes changed-open first trade,
  revision increment, duplicates/late empty, malformed sentinel/volume/closed hint,
  nonempty conflict with newer timestamp, and Hypothesis permutations.
- Affected Ruff/format and configured mypy (370 files) passed; initial import
  ordering fixed. Import-linter: 7 contracts kept, 0 broken. No full suite run.
- Built/recreated market-data only, exit 0. Deployed image manifest:
  `sha256:155b8c41f33e043d35f0905827d1ac49605174884daf1fca9eb62e480fe7ef83`.
- [Actual PG samples](first-trade-live-state.json): 14 read-only observations from
  2026-10-12T18:05:58Z to 18:07:05Z (2026-10-13 in Bangkok), spanning minute changes.
  No ORDER_UNCONFIRMED observed; preview rows stayed at 55, below the 60-row cap.
  One sample had disconnected/RECOVERING, followed by reconnection; this is not
  uninterrupted availability evidence. Final snapshot connected with active lease
  and latest preview receive age approximately 1.35 seconds.
- [Local browser/API smoke](first-trade-browser.json): authenticated chart mounted;
  BTC 1h and 1m live GETs both HTTP 200 with two rows, status RECOVERING, reason null,
  no JavaScript pageerrors. Two separate normal smoke accounts remain in dev DB;
  first launcher attempt used an API request context without baseURL and was corrected.
- Sanitized current-container log check found no progression-conflict or writer-
  unavailable entries in the queried five-minute window. Do not extrapolate to soak.

## Remaining

The confirmed empty→first-trade conflict is fixed and deployed. **READY has not
been demonstrated in the local browser smoke above**; history/backfill and REST
settlement still recover under the unchanged F-09 request budget. RECOVERING remains
visible rather than being promoted to READY. Other malformed/corrected nonempty
snapshots must still fail closed.

F-12 remains In Progress. Owner manual, complete coverage/review/CI and V-17
Pending Full Validation remain; bounded observations do not close those gates.

## Subsequent checkpoint

The RECOVERING result above was the state of this bounded observation. A later fix
for right-only history expansion closed the default BTC 1h REST settlement gap and
demonstrated live READY with changing OPEN rows in a real browser. See
[latest-history-ready.md](latest-history-ready.md). Remaining F-12 gates are unchanged.
