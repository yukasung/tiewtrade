# F-12 / F-11 — Indicator latency investigation

สถานะ: **Investigation Approved / Implementation Needs Approval** — เจ้าของอนุมัติ
targeted profiling เมื่อ 2026-10-13; แผนแก้ที่ได้จากผลวัดอยู่ใน
[`../2026-10-10-backend-indicators/performance-plan-v3.md`](../2026-10-10-backend-indicators/performance-plan-v3.md).

## Evidence

After staged candle loading, one browser session observed:

| Request | Observed behavior |
|---|---|
| BTC/USDT 1h | 5 initial INDICATOR_BUSY refusals; eventual 200 took 429ms |
| BTC/USDT 1m | 200 took 7671ms, 1000 output rows |

Responses had generation_id=null, indicating LEGACY. Durations cover individual
forwarded HTTP requests measured with performance.now, not total page latency or
capacity measurements. Busy refusals demonstrate contention, not which client caused it.

Confirmed code paths:

- indicator_read_controller.py: LEGACY calls read_indicators over calculation bounds.
- indicator_reader.py: scans bounded 1000-slot windows, hashes every dependency
  including missing slots, and feeds IndicatorStream in batches of at most 16.
- chart_routes.py: LEGACY verification calls the same reader.
- indicator_admission.py: one physical history/verify job per API process; other
  requests receive INDICATOR_BUSY instead of waiting in a server queue.

The proportional cost of DB queries, hashing, decoding and numeric state advancement
has not been measured separately. Do not claim a specific hotspot without profiling.

## Proposed scope

1. Profile a single bounded LEGACY read using existing profiling tools and a fixed
   isolated fixture; separate DB, dependency digest, decoding and indicator advancement.
   Reuse existing F-11 performance work/evidence rather than starting a new feature.
2. Optimize only the measured hotspot while preserving exact indicator output,
   canonical dataset revision, full dependency coverage, seed, gap/reset/finality
   behavior, deadline checks, cancellation and scheduling fairness.
3. Select equivalence and safety tests by the affected layer and include corrections
   before seed, missing data, refresh-required segments and revision invalidation.
4. Measure the same fixture before/after, plus browser 1h→1m and initial load;
   report API compute time separately from admission waits.

Constraints: retain approved 16-slot numerical batch and admission limits unless a
separate F-11 amendment is approved. No shortened seed history, frontend indicator
calculation, unverified cache reuse or automatic PREPARED activation.
PREPARED remains subject to its rollout/capacity gates; existing capacity failures
are not closed by this targeted investigation.

Before code changes, record the selected optimization and validation in the F-11
approved-plan amendment following the investigation. This proposal authorizes
investigation scope only when approved; it does not pre-approve a speculative fix.

## Investigation result — 2026-10-13

The approved read-only profile used one separate API process and one repeatable-read
snapshot of the same development database used by the slow browser request. It did
not prepare, delete or update candles and did not call an exchange or order path.

| Measurement | Result |
|---|---:|
| Calculation slots | 525,599 |
| Stored rows decoded | 5,845 |
| Missing slots | 519,754 |
| Output rows | 1,000 |
| Instrumented elapsed | 7.870049s |
| Core / `IndicatorStream.feed_batch` | 4.361351s |
| Canonical digest | 1.678560s |
| DB execution | 0.613779s |
| Decode | 0.173266s |
| Maximum observed event-loop lag | 9.340ms |

This single diagnostic run is a hotspot measurement, not a latency or capacity SLA.
It matches the earlier browser observation closely enough to explain that the sparse
365-day LEGACY scan, rather than output rendering, dominates the 1m response.

A second cProfile run adds profiler overhead and therefore is not compared as latency.
It recorded 525,599 digest calls, 33,113 `feed_batch` calls and nearly 5 million
`_Average` constructions. `advance_indicator_batch` repeatedly rebuilds empty numeric
state for RESET events across the 519,754 missing slots. The selected bounded fix and
its exact-parity validation are specified in the F-11 v3 amendment linked above.
