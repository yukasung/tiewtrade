# Internal Paper local campaign — 2026-11-07

**Approved local workload/restore campaign: Passed.** Full F17 status remains in
[roadmap](../../../../roadmap.md). Internal opening is not yet accepted or activated.

| Gate | Pinned profile / evidence | Result |
|---|---|---|
| Controlled protection | prior controlled20:20owners,400baseline,all starts≤1s | Passed in retained scope |
| D20 | §14v2:600commands,300s,financial/resource/final-tail | Passed in retained scope |
| W1 | §16 V1:20owners/400baseline,3600commands,1800.965s | Passed; p95/p99=144.262/211.241ms |
| W2 | §20 V2:12000commands,10/s,1205.681s≤1260s | Passed; p95/p99=364.028/516.442ms; original250ms target warning retained |
| Overflow | §20 V2:4097inputs,20.155s recovery | Passed; economic effects unchanged |
| Short W3 | §22 V3:3000commands,1800.001s,7faults | Passed; p95/p99=132.721/201.237ms |
| Snapshots/replay | Short W3:620/620samples,20final replays | Passed; snapshot p95/p99=48.893/109.821ms,rebuildmax7.145s |
| W3 resources |1800s window,RSSgrowth−5.019%,81process pool reports | Passed; all generations returned,no observer resource errors |
| W4 | §23:real pg_dump/restore and F16/F17 recovery | Passed; canonical/RLS/grants,receipt identity,exact retry,source unchanged,duplicateexit/fill0 |

Evidence directories: [W1](nc12-section16-w1/analysis.md),
[W2](nc12-section20-w2/analysis.md), [overflow](nc12-section20-overflow/analysis.md),
[short W3](nc12-section22-w3/analysis.md), [W4](nc12-section23-w4/analysis.md).
Each campaign retains candidate/config/runner/schema proof and cleanup0connections/
0advisory locks. W4 also pins its support script. Credentials/env files stay outside
repository evidence. No automated Live orders or production activation occurred.

## Candidate and test scope

Latest W4 source hashes are in[nc12-section23-w4/candidate-sha256.json](nc12-section23-w4/candidate-sha256.json).
Production files unchanged from the passing workload candidate. §23 adds only an
optional test-worker engine factory(default path unchanged), explicit restored DB
routing and source-unchanged verification. Prior workload proofs are reused for
those unaffected contracts, supported by default-worker/CLI/lifecycle regressions.

§23 targeted coverage:125unique cases;124passed in initial mixed suite, the empty-DB
case passed separately on a fresh DB;6routing/digest rechecks also passed. Initial
fixture/type failures retained in logs. Ruff/format/mypy passed3files. §22 resource
fix has88passing targeted cases plus scoped checks; prior production50safety cases
remain applicable. Partitioned local checks do not replace full regression/required
remote CI on a final published SHA. Empty-DB tests need isolated execution.

## Acceptance coverage and remaining gates

| Criterion | Current evidence / remaining work |
|---|---|
| IP-V1 | Local profile/default/worker-forwarding/fault/count contract tests passed |
| IP-V2 | Retained correctness/safety proofs plus financial/idempotency/RLS/restore assertions passed in these local profiles; final candidate audit remains |
| IP-V3 | Actual TransactionalRiskPolicy/authenticated HTTP exercised in isolated workload; F18 R34 Paper evidence exists in roadmap. Final production-admission integration/activation audit remains; no production readiness enabled |
| IP-V4 | Prior lifecycle/browser and controlled20 evidence retained in its unchanged scope; final candidate coverage audit remains |
| IP-V5 | D20 passed in retained scope |
| IP-V6 | Amended internal W1/W2/overflow/shortW3 passed; original100-account and4h Release obligations remain Pending Full Validation |
| IP-V7 |20-account snapshot/rebuild and integrated W4 passed |
| IP-V8 | Pending final review/required CI on latest recovery candidate; previous98ff2f8 CI is not current-change CI |
| IP-V9 | Not Run:invite/access/Paper-only/warning/opening authorization gates; no deployment performed |

All historical Failed/Partial/Incomplete results remain unchanged. The4historical
active cancellations remain unattributed; later passing runs are not a causal fix
claim. The retired-pool false alarms and W4 source-routing bug have specific fixes
and regressions. No result is relabelled as4h endurance or full F17 Completed.

Next checkpoint: final candidate/production-admission coverage review, then owner-
authorized Git publication/required CI and internal opening gates. Git/deploy/Live
remain governed by existing approvals. No further workload rerun is needed merely
for confidence; repeat only evidence affected by a subsequent change.

Recovery review found Medium test isolation/CI configuration gaps. Owner-authorized
fixture fix is locally verified; see[exact results](review-fixture-fix.md).
This supersedes the unresolved empty-DB execution limitation above, not the old
run outcomes. Required remote CI and all other remaining gates still apply.
