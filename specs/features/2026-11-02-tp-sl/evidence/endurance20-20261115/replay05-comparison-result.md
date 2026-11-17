# REPLAY-05 — one short query comparison (2026-11-17)

สถานะ: **Diagnostic Complete — not full replay/endurance acceptance**

Owner instructed เริ่มทำ after readiness. Pinned runner hash and candidate inventory
matched; original120s preflight passed7samples with PostgreSQL healthy/RedisPONG.
No source changes during execution. One fresh owned database; two synthetic owners,
144364records belonging to owner1; old reader then new reader once,4096page limit and
original60s bound per enumeration. Total285.274s (4m45.274s),seed56.711s;900s total
budget retained. No Redis instance created, no owner/Live order sent.

## Results

| Measure | Baseline | Candidate |
|---|---:|---:|
| Decoded records |144364|144364|
| Pages including terminal empty |37|37|
| Enumeration seconds |55.199640|43.662336|
| SQL + driver seconds |20.391658|7.170433|
| Decoder seconds |33.835320|35.577908|
| First-page EXPLAIN execution ms |857.611|121.059|
| First-page wide sort disk KiB |208128|5936|
| Late-page EXPLAIN execution ms |12.530|16.664|

Identity/timestamp/digest stream matches exactly; every record was decoded/checked by
the production decoder. Candidate elapsed was20.9% lower in this one fixed-order run,
not a statistically established improvement: baseline-first/cache/host effects remain.
Candidate first page scans narrow144364keys then limits4096 before indexed evidence
fetch; only4096wide rows sorted, not144364. It still scans keys and spills a small wide
sort, so do not claim elimination of all work. EXPLAIN samples taken after enumeration;
SQL+driver/decoder wall time is not pure PostgreSQL server time. Late-page sample uses
scalar strict-input cutoff on this unique-ID fixture; it does not prove every composite
cursor query plan. Tie correctness comes from the separate real-DB safety tests.

Foreign owner cannot read the nonempty first page. Financial-state fingerprint unchanged;
source/runner/helper/baseline bindings unchanged. Cleanup receipt and independent check:
owned database absent,zero connections,zero locks. All previous Failed/Incomplete retained.
Raw artifacts: validation-artifacts/f17-replay05-comparison-20261117/.

## Decision / next checkpoint

Keep60s unchanged. Reader now leaves about16.34s under this bound, but this fixture does
NOT run complete financial position/cash/checkpoint replay or20ownerfinalization. The
new reader addresses the measured wide-sort inefficiency; it does not establish that
historical CUT01 timeout or every W3 failure is resolved.

Recommend next: full financial replay across20synthetic owners at representative144364
input history, retaining all original money/order/position checks and60s per-owner
budget, before spending another4h campaign. Bind updated reader/cursor to that fixture
and document the representative size; use valid prior safety proof where unaffected.
This is a recommendation, not an executed/approved extra run. Current one comparison
is consumed; stop/report. No4h/commit/push/CI/merge. F17 Pending Full Validation and
historical W3Incomplete remain unchanged.
