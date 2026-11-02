# NC-F19-21 clock-only comparison — 2026-11-02

Status: Observation complete / non-acceptance. Guest-relative clock movement observed;
original r3 publisher failure not reproduced or causally resolved. Owner authorized the
proposal with `เริ่มทำ`. No acceptance criteria changed.

## Scope and integrity

One passive 20-minute, 10Hz host/guest trace, no trading, PostgreSQL, Redis or application
workers. VM remained 8 CPUs / 3,043,373,056 bytes; observer limited to 0.1 CPU / 64MiB,
UID65534, read-only root, network none, all capabilities dropped, no-new-privileges,
no mounts/application environment. Existing runner image pinned by ID. No system clock,
Docker configuration, production code or unrelated container changed in this checkpoint.

Probe: `backend/tests/infra/risk_limits/profile_clock_probe.py`; regressions:
`test_clock_probe.py` in the same directory. Reuses existing runner/artifact conventions,
stdlib clocks and bounded JSONL transport; no financial/domain dependencies. Scoped cleanup
closes stdin and joins its own observer; timeout cleanup targets only its own container.
22 tests passed, zero skips (0.060s), including controlled offset movement, uncertainty,
gaps/caps/write errors, cancellation, protocol and sandbox inventory. Ruff, format and
mypy passed for both files. Frozen probe SHA256:
`ead57e24c8515e873e13c8c5bbca537ef314bfc16716ffbf552c3a794751109a`.

## Observations

Trace metadata 10:34:40–10:54:48 Asia/Bangkok, actual sampling duration 1200.001281250s.
12,000 contiguous exchanges, no cadence gaps, complete=true, acceptance_result=false.
Observer exited 0, no OOM, PID0, no healthcheck; executed source matches frozen tested
source. Trading validation services remain stopped; observer retained exited for evidence.

| Measurement | Result |
|---|---|
| Guest wall-minus-monotonic movement | 40 intervals: 24 decrease, 16 increase |
| Guest movement spacing | median29.999772s, range29.998825–30.099908s |
| Largest guest offset decrease | 2.991885–2.994309ms, sequence400 |
| Host offset movement | 504 increase intervals, zero decrease intervals |
| Literal adjacent wall timestamp reversals | zero in either domain at10Hz |
| Conditional guest/host UTC bounds | 11,930 available;70 Unknown, all retained |
| Nonoverlapping consecutive conditional relative bounds | 6 intervals, including2 decreases |
| Transport RTT | median2.781438ms, p99 10.711625ms, max136.136916ms |

At sequence400 (10:35:27.213931 host wall), guest offset decreased by
2.991885–2.994309ms; host offset change bound spans zero (-0.002792..+0.002334ms).
The independent transport-bounded guest-minus-host UTC change excludes zero:
-6.026936..-0.848592ms. This supports guest-specific relative timing movement in that
interval, conditional on no unobserved host wall step within the exchange. Absolute
monotonic origins are never subtracted across domains.

Host increases cluster 10:49:18.205695–10:50:13.721433, net midpoint offset change
+15.777334ms. Host timed logged NTP receipt10:49:17.146315 and successful adjtime
+16.616225ms at10:49:17.150961. This is consistent with gradual host adjustment;
504 detections are not evidence of504 discrete clock jumps. Of70 Unknown exchanges,
66 had host-bound change,2 wide RTT,2 both. No Unknown is silently discarded.

## Interpretation and limitations

Confirmed: guest-relative offset decreases exist without trading/DB load; movement
recurs around30s; some changes exceed both read and transport bounds. The captured
host did not show corresponding backward offset movements. Existing power logs show
caffeinate spanning the trace, with no matching sleep/wake event in the selected window.

Not established: exact clock setter/process, whether each interval is a discrete step
versus slew/rate/read-coherence effects, or the cause of original r3 guard rejection.
Original r3 offset change was about-35.589ms; this trace's maximum decrease is about3ms.
There are no BookState calls here. Ten-Hz sampling cannot rule out unobserved subinterval
movement. Python monotonic on the guest uses CLOCK_MONOTONIC (not an independent physical
reference); UTC comparisons retain the explicit transport/host-continuity assumption.
No global clock-stability proof or risk-SLA improvement follows from this diagnostic.

Docker's [2019 engineering description](https://www.docker.com/blog/addressing-time-drift-in-docker-desktop-for-mac/)
describes a historical HyperKit/LinuxKit guest time-sync mechanism that can step time.
That is a plausible mechanism to investigate, not proof of the current ARM64 Docker
implementation or identification of its setter. Current observations stand independently
of that historical explanation.

The existing pmset export initially failed UTF-8 decoding during postprocessing. Its
hash/error offset were retained, and replacement decoding marked uncertain lines;
all6 selected relevant lines contain no replacement characters. This did not affect
raw sampling. No probe rerun was performed.

## Evidence and checkpoint

Artifacts under `validation-artifacts/f19-set5-20261101/`:
- `nc21-checks/summary.json`, `final-tests.xml`: test/static results.
- `nc21-candidate/`: frozen probe and tests.
- `nc21-r1/`: samples.jsonl, inventory.json, result.json, source and guest stderr.
- `nc21-analysis/`: summary, all offset movements, correlation-details, existing host/VM/
  power logs, closure and SHA256 manifests. Raw results retained including all Unknowns.

NC21 diagnostic complete; V-20 remains **Failed / Pending Full Validation**. W2/W3/W4
not started; V-21..24 dependencies unchanged. NC17 latency failure remains unresolved
by this clock-only result. Do not relax freshness, safety, load, quota or SLA criteria.

Next: prepare an environment-remediation proposal with the environment owner using this
evidence, choosing either repair of guest timekeeping or a controlled Linux validation
host with equivalent approved resources. Availability and exact remedy are unverified;
configuration/provisioning and another W1 require separate approval. No additional
clock diagnostic or unchanged workload rerun is authorized. No commit/push performed.
