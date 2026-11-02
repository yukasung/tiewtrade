# F-19 NC22 — Measurement reliability audit (same machine)

สถานะ: **Audit complete / non-acceptance — 2026-11-02**
Owner explicitly approved the same-machine audit plan. The earlier Linux-target proposal
is superseded: no other machine, provisioning, configuration changes or new workload.
All original Failed/Pending results and F19_SET5 criteria remain unchanged.

## Decision

**There is no evidence-backed reason to relax the SLA or regrade a failed run.**
NC17's timestamp-based results reconstruct exactly. NC18 independently establishes real
monotonic scheduler queue waits exceeding3s, and source-server timestamps corroborate
late decisions under their clock-continuity assumption. Client observation delay does
change some borderline results, but it cannot be estimated away for other transactions.
Physical elapsed-time uncertainty is not fully bounded in the historical acceptance data.

A reproducible **Medium measurement-guard defect** was found: the evaluator accepts a
stream whose acknowledgement timestamps regress without flagging that broken ordering
precondition. This does not explain the supplied failures: all44 acknowledgement files
(11each in NC17/NC18/NC19-r3/NC20) have zero timestamp regressions. No harness patch was
applied. Stop at this checkpoint and approve a narrow guard fix separately.

## Evidence integrity and source provenance

Artifacts: `validation-artifacts/f19-set5-20261101/nc22-measurement-audit/`.
`audit.py` reads original files and writes only separate audit outputs.261 original raw
file/hash entries match their retained manifests across NC17, NC18, NC19-r3, NC20, NC21.
This checks consistency with retained hashes, not independent cryptographic authenticity.
No source DB was started/restored/queried; no old artifact or acceptance result overwritten.

`source-provenance.json` records9 hash-matched source files copied to audit snapshots.
The original publisher source matches for NC17/18; NC19/20 workload, publisher and risk
observer sources are available. AST comparisons show identical `sla_summary`, `telemetry`,
financial-marker and source-receipt functions between matched NC19/20 sources.

**Source gap:** original NC17/18 `profile_workload.py` and NC18 `profile_risk_timing.py`
contents were not recoverable from the currently available local snapshots or stopped
runner `/work` copies. Their expected hashes/tree identities and prior reports remain.
Do not substitute the newer source as proof of their exact historical implementation.
Historical producer claims below therefore distinguish prior reviewed evidence from a
new inspection of byte-identical source. This limits a full source-level recertification;
it does not invalidate the retained raw identities or independent timestamp reconstruction.

## Clock and identity map

| Evidence | Clock / identity | Precision and missing information |
|---|---|---|
| PRICE `inputs.jsonl.ready_at` | Original PostgreSQL `pg_xact_commit_timestamp(xmin)` on price-frame row; cursor identifies frame | ISO timestamp with microsecond representation; producer fails when commit timestamp missing. No per-read wall/monotonic bracket in old runs |
| Financial input `ready_at` | Original PostgreSQL commit timestamp of financial-boundary row; owner+sequence identity | Same representation; original NC17/18 producer bytes unavailable, prior review retained; NC19/20 matched source inspected |
| `*.risk.jsonl` acknowledgements | Python `datetime.now(UTC)` after successful transaction-context exit; owner/cursor/boundary/pending | Microsecond representation, not a measured accuracy bound. Old normal telemetry lacks XID/PID and same-instant monotonic bracket |
| NC18 `commit-times.jsonl` | Source-database commit timestamp linked by proof/file identity, writer xmin/current XID and backend PID |23,648 VERIFIED,1,272 UNKNOWN. Every VERIFIED XID matches low32bits; none has negative observed-minus-server delay. UNKNOWN remains UNKNOWN; no guessed parent/subtransaction mapping |
| `source-commits.jsonl` | Parent's received source-event time: sequential wall read then monotonic; source identity/server commit time carried separately | Not a clock-read bracket and not child execution/guard time. Cross-process IPC/receipt delay and reading skew unbounded |
| NC18 stage durations | Monotonic queue/stage durations; wall anchors link owner/attempt/round | Queue waits are physical monotonic durations; wall anchors alone cannot bound clock adjustment between DB readiness and completion |
| NC20 guard observer | Scoped child BookState observer; only failure arguments produce records |1,203 calls/zero failures, so missing r3 guard arguments are not recovered.60s diagnostic cannot certify600s stability |
| NC21 trace | Separate bracketed wall/monotonic reads in host and guest; sequence/PID/read-resolution pads and transport bounds | Host reported time resolution~1µs/mono~41.7ns; guest clocks1ns. Resolution is not accuracy.70 uncertain exchanges retained. No DB/trading/acknowledgement identity |

All PostgreSQL/worker containers shared the Docker guest environment in these runs;
host Mac and guest absolute monotonic origins are never subtracted. Clock changes can
still affect guest wall-based commit and observation timestamps at different instants.
NC21 properties/offset bounds cannot be projected backwards onto NC17/18/r3/NC20.

## Evaluator, transaction and denominator checks

- Matched NC19/20 telemetry emits only after the transaction context successfully exits.
  Exceptions skip emission. Final owner state is reread before exit, so a risk savepoint's
  rolled-back INSERT is not by itself evidence of the final cursor. Pending replay is
  excluded by the evaluator. Prior real-DB rollback/savepoint evidence is reused; those
  DB tests were not rerun in this service-free audit.
- Independent reconstruction sorts all supplied nonpending worker acknowledgements and
  finds the first frontier reaching each PRICE cursor or owner financial boundary.
  No measured-input duplicates and no per-stream timestamp regression occur in the four
  supplied datasets. On ordered streams, controlled cross-worker cases choose the first
  eligible acknowledgement correctly. Acknowledgements before readiness fail closed.
- NC17 reconstructs **918,703/918,703 samples;1,302 >3s;3 >5s;213 late acknowledgement
  groups;56/100 owners below99.9%**. No missing or negative observed latency. These are
  the same timestamp conclusions as the retained result, not a physical-time regrade.
- The existing measured flag includes source-drain receipts. Retained NC17 phase analysis
  has902,475 nominal-load samples (1,293 >3s/3 >5s),16,228 drain samples (9 >3s),zero setup
  samples. No sample is removed and no new exemption is introduced. Removing drain would
  not eliminate the load-period misses. Scheduled W3 fault exclusions remain separate;
  this audit does not invent W1 exclusions or certify unexecuted W3 behavior.
- NC18 is a300s deliberate cutoff; r3 ends on publisher failure; NC20 is60s non-acceptance.
  Their supplied measured flags include partial/drain/cancellation scopes. The independent
  raw counts in `stream-and-clock-audit.json` are **not nominal-window denominators or
  acceptance verdicts**. NC18's previous451,280 nominal-window samples and552 outstanding
  inputs differ from all-flagged counts because scope differs; no original result is replaced.
- NC21 is clock-only, acceptance_result=false; it has no SLA denominator. No diagnostic,
  incomplete600s window or partial financial snapshot passes V-20.

## What the evidence establishes

| Conclusion | Classification | Evidence / limits |
|---|---|---|
| NC17 reported timestamp misses are reproducible; stream-order/omitted-worker errors explain them | **พิสูจน์ได้** for reproduction; proposed explanation excluded for supplied files | All11streams used, duplicates0/regressions0, exact independent counts |
| Client observation is the same instant as DB commit | **พบข้อจำกัดของวิธีวัด** | NC18 source-time proof delay p50~4.984ms/p99~42.491ms/max149.723ms; cannot subtract these estimates from NC17 or r3 |
| Every NC18 late group is only client-observation delay | **ตัดออกได้สำหรับหลักฐานที่ผูกได้** |152 VERIFIED late groups:148 still>3s by source-server timestamps;4groups/12samples cross3s only at observation;3othergroups remain UNKNOWN |
| Real queue latency exists independently of wall-time readings | **พิสูจน์ได้** | NC18 semaphore waits include3.161157751s measured by monotonic. Does not certify all end-to-end elapsed times or the amended scheduler's W1 |
| r3 parent observed wall-time reversal | **พิสูจน์ได้** | Receipt lines3606→3607:wall−16.857ms/mono+18.732250ms; offset difference−35.589250ms. Sequential unbracketed reads cannot attribute setter or child guard |
| NC21 guest-relative movements cause original r3 rejection or all NC17 misses | **หลักฐานไม่พอ** | Different run/no BookState/DB; maximum guest offset decrease~3ms is not a correction budget for older runs |
| No observed reversal proves a stable clock throughout historical runs | **หลักฐานไม่พอ** | Sparse unbracketed receipts/ordered acknowledgement times do not exclude smaller forward/backward steps or continuous slew |
| Old normal telemetry can be converted to true commit/monotonic SLA retrospectively | **หลักฐานไม่พอ** | Missing transaction and paired-clock evidence; restored xmin/commit times must not stand in for source times |

## Finding and proposed patch — not implemented

**Medium — `backend/tests/infra/risk_limits/profile_workload.py::sla_summary`, stream merge
around lines1558–1569.** `heapq.merge` requires each input stream to be sorted, but there
is no per-file ordering validation. `clock_errors` only increments when an acknowledgement
precedes an input's ready timestamp; that is insufficient to detect stream regression.

Controlled reproduction (one input ready00:00:00, same owner/cursor in each acknowledgement):
- Ordered separate streams at03.100s and01.000s select01.000s as expected.
- One file at03.100s then01.000s reports a miss but clock_errors=0 despite broken ordering.
- One file at00.500s then00.400s returns **passed=true, clock_errors=0** despite regression.

Impact: a future trace can receive a confident pass/fail under an invalid merge
precondition. This counterexample does not establish historical physical latency or
justify sorting a damaged stream and treating it as valid.

Recommended narrow amendment: validate nondecreasing timestamps in **every consumed
worker stream before pending/owner filtering**, retain file/line/time identities, and
fail the measurement-evidence gate on regression. Equal timestamps remain valid. Keep
all input/acknowledgement rows and existing denominators/thresholds; do not repair by
sorting, dropping, clamping or shifting times. Regression metadata should be additive to
the test report and distinct from the existing negative-latency clock_errors count.
A guard can identify invalid ordering, not certify clock continuity on an ordered trace.

Before applying: owner approval under the approved plan's stop-at-defect rule. Proposed
regression covers backwards timestamps with a would-be pass and would-be miss, equality,
interleaved ordered workers, pending/foreign-owner rows, plus existing boundary/quota/
missing-ack cases. No production/schema change, new timed run or settings change needed.

## Checks, preservation and next step

18 selected existing non-DB regressions passed, zero skips; five separate controlled
cases completed and persisted. Actual DB rollback/savepoint tests intentionally not run.
Command from `backend/`:

```sh
./.venv/bin/python -m pytest tests/infra/risk_limits/test_workload_sla.py \
  -k 'not savepoint and not refused_workload and not joined_observation' \
  --junitxml=../validation-artifacts/f19-set5-20261101/nc22-measurement-audit/regression.xml -q
```

Audit reproduction from repository root (writes only its own derived artifacts):

```sh
backend/.venv/bin/python validation-artifacts/f19-set5-20261101/nc22-measurement-audit/audit.py
```

No production/harness code, system settings, resources, pools, source cadence, public API,
schema, financial logic or acceptance criteria changed. No services/workload/new probe,
Git commit/push or external machine. Broad lint/types unnecessary for documentation and
standalone offline audit; existing runtime files unchanged.

**Next:** review/approve the narrow stream-order guard amendment above before patching.
Do not rerun W1 or start another diagnostic. Even after the guard, the original latency
failure and clock-continuity limitations remain; fixing the guard alone does not close
V-20 **Failed/Pending Full Validation**, W2/W3/W4 or V-21..24 dependencies.


## Follow-up — owner-approved guard fixed (2026-11-02)

The finding and prepatch reproduction above remain historical. Owner approved the narrow
patch: stream timestamp regressions now produce a separate error count/bounded diagnostic
list and force passed=false, before pending/owner filtering. No rows are removed/reordered.
27 non-DB tests and changed-file Ruff/format/mypy passed. No timed run/settings/production
change or old failure regrade. The historical audit.py imports its evaluator from the working
tree: its prepatch expected-pass assertions require the retained matched NC20 snapshot,
not today's patched evaluator. Original audit outputs/hashes are preserved. See the NC22
guard checkpoint in plan/validation for commands, scope and remaining limitations.
