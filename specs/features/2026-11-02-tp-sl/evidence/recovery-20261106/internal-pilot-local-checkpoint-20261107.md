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
| IP-V3 | Production-composition code/CI integration audit Passed on f15596d; see step2 below. Target-environment activation/readiness is not verified or enabled and remains an opening prerequisite. |
| IP-V4 | Prior lifecycle/browser and controlled20 evidence retained in its unchanged scope; final candidate coverage audit remains |
| IP-V5 | D20 passed in retained scope |
| IP-V6 | Amended internal W1/W2/overflow/shortW3 passed; original100-account and4h Release obligations remain Pending Full Validation |
| IP-V7 |20-account snapshot/rebuild and integrated W4 passed |
| IP-V8 | Recovery review/finding fixes/refactor and final candidate CI passed; merged as f15596d. Evidence-to-candidate reconciliation below is complete; this does not close IP-V3/IP-V9. |
| IP-V9 | Not Run:invite/access/Paper-only/warning/opening authorization gates; no deployment performed |

All historical Failed/Partial/Incomplete results remain unchanged. The4historical
active cancellations remain unattributed; later passing runs are not a causal fix
claim. The retired-pool false alarms and W4 source-routing bug have specific fixes
and regressions. No result is relabelled as4h endurance or full F17 Completed.

Historical next checkpoint at the time of the local campaign: final candidate review,
Git publication/CI and production-admission/opening gates. Git/CI/merge have since
completed as recorded below. Production-admission and internal opening remain open.
No workload rerun is needed merely for confidence; repeat only affected evidence.

Recovery review found Medium test isolation/CI configuration gaps. Owner-authorized
fixture fix is locally verified; see[exact results](review-fixture-fix.md).
This supersedes the unresolved empty-DB execution limitation above, not the old
run outcomes. Required remote CI and all other remaining gates still apply.


## Merged-candidate evidence reconciliation — 2026-11-07

Owner requested step1 only: reconcile retained evidence and update validation/roadmap.
No source/configuration, acceptance criterion or historical result changed in this
step. No workload/test rerun, deployment, access enablement or Live order occurred.

### Candidate and remote gates

- Published candidate: `abfde03727fc1ca20d2054464f3361f690db1d18`.
- Owner-authorized [PR59](https://github.com/yukasung/tiewtrade/pull/59) merged as
  `f15596df0b1ced53107964a8ed9bb657fda9d336`, preserving candidate ancestry.
  Its parents are main `2f1d047ea5a4187eb09d50edff258d982eed9b77` and the published
  candidate. The candidate-to-merge tree diff is empty.
- Candidate [PR CI](https://github.com/yukasung/tiewtrade/actions/runs/42372638772),
  [push CI](https://github.com/yukasung/tiewtrade/actions/runs/42372633594) and
  [Security](https://github.com/yukasung/tiewtrade/actions/runs/42372638757) passed.
- Merge-SHA [CI](https://github.com/yukasung/tiewtrade/actions/runs/42374499165)
  passed6/6; [Security](https://github.com/yukasung/tiewtrade/actions/runs/42374499141)
  passed7/7. Backend main:4761passed/31deselected in1091.23s; subsequent isolated
  protection/migration/global-state/rollback steps:50+1+1+27+16passed. Post-merge
  E2E includes F16/F17/F18. Prior failures remain historical failures.

### Reuse boundary

Compared every entry of the retained W4 `nc12-section23-w4/candidate-sha256.json`
against bytes in the merge commit:994entries,968identical,26changed. This manifest
is a snapshot of selected paths, not a complete inventory of the later candidate.
All listed migrations and the recovery production execution/protection/worker/query
paths match. The26changed entries comprise4backend source files,12test/harness
files and10frontend source files. Main also added frontend helpers `apiRequest.ts`
and `isRecord.ts`, which are outside the older manifest.

The4backend differences are in core/risk_limits.py, infra/risk_limits/storage.py,
infra/auth/sessions.py and infra/api_keys/records.py: removal of unused exception,
reader, session record and property. Frontend changes consolidate request/error
and journal helpers. These integrated main changes have current-SHA regression,
static and browser CI proof; the older workload does not itself prove their final
bytes. Fixture/config/harness changes have scoped regression receipts in
[review-fixture-fix.md](review-fixture-fix.md) and
[remaining-ci-fixtures-local.md](remaining-ci-fixtures-local.md), followed by the
passing complete remote gates above. This is evidence reuse within the retained
profiles, not a claim that the old workload ran on f15596d.

D20/W1/amended W2/overflow/short W3 and W4 retain their Passed results and original
candidate/config/schema/runner hashes, counts, duration and limitations. No result
is relabelled as the original100-account or4h Release workload. Financial,
transaction/idempotency/RLS, snapshots/rebuild and restore proofs remain usable for
the unchanged execution contracts. Current API/UI regression proof is supplied by
merge-SHA CI; production admission/activation still requires its own audit.

### Remaining gates and next step

Step1 is complete. IP-V8's published-candidate CI blocker is closed. IP-V2/IP-V4
candidate evidence has been reconciled as above; no production-opening acceptance
is inferred. IP-V3 final F16/F18 production Paper admission/activation audit and
IP-V9 invited access/Paper-only/warning/deployment authorization remain open.
Original100-account/4h Release and bot/notification/Live dependencies remain Pending
Full Validation/Dependency; F17 stays Development Complete, not Completed.

Next is step2: audit actual Paper admission and risk integration against existing
approved criteria, then identify only missing evidence or concrete blockers. Step2
has not been started or authorized by the owner's step1 instruction. Do not rerun
load merely for confidence, enable access or deploy from this documentation task.


## Step2 — Paper admission/risk integration audit — 2026-11-07

Owner authorized step2 after step1 reconciliation. Audit candidate:
`f15596df0b1ced53107964a8ed9bb657fda9d336`; current source matches that merge
commit (working edits are documentation only). This is a source/CI evidence audit,
not an inspection or activation of a selected deployment database.

**Result: production-composition integration Passed; deployment opening Pending.**
No new implementation blocker was identified within this admission/risk audit.
This does not certify the complete application or remove deployment/access gates.

| Boundary | Inspected implementation | Current evidence / conclusion |
|---|---|---|
| Actual API policy | services/api/manual_order_routes.py:manual_admission_policy/new_order; infra/paper_orders/manual_policy.py | Resolves TransactionalRiskPolicy inside owner transaction, validates account use and authoritative holdings; no UI-ready flag authorizes intake. API actual-policy cases in tests/api/test_risk_admission.py passed in merge-SHA backend CI. |
| Worker and matching recheck | services/engine/paper_order_main.py; infra/paper_orders/request_worker.py and worker.py | Production loops pass TransactionalRiskPolicy. Transfer rechecks active episode, stop generations, catalog and policy; matching resolves fresh evidence under owner/publication fences and rechecks global rollout controls between inputs. test_api_price_tail.py, test_matching_fence.py, test_execution.py and test_concurrency.py passed in backend CI. |
| Unknown/outage/loss | infra/risk_limits/policy.py and views.py; core/risk_limits.py | Missing/inconsistent evidence fails closed; configured-owner breach stays latched. Bounded SELL is derived from held minus reserved; oversized SELL gets no reduction exemption. Optional unset limit is the approved Paper MANUAL policy, not fabricated READY evidence or a test allow policy. Core risk tests and actual DB execution tests passed. |
| End-to-end production composition | tests/e2e_risk_app.py; frontend/playwright.risk-limits.config.ts; frontend/e2e/risk-limits.spec.ts | Imports real app/lifespan and real order/risk serve loops; no AllowPolicy override. Recorded sources, fault controls and protocol activation exist only in the guarded isolated test wrapper. All6 risk-composition browser cases passed in59.1s in post-merge E2E job128409272903. F16 test-policy browser suite alone is not used to satisfy this boundary. |
| Economic and retry effects | same browser suite plus infra/risk_limits/test_execution.py and infra/protections tests | BUY/fill, queued refusal after breach, resting cancellation, bounded SELL, reset retaining stop, price outage/cache failure, same-key recovery and correction replay have assertions. Browser checks exact cash9899.8901, BTC0.9989 and loss0.119910010010010011. Backend has rollback/fence/concurrency/duplicate-effect assertions, including isolated F17 tests. Financial calculations retain Money/Quantity; no formulas were changed. |
| Authentication/isolation/statelessness | services/api/authentication.py, request_identity.py; infra/auth/sessions.py; owner UserSession/RLS and migration0041 | Session identity is looked up in PostgreSQL, CSRF is checked and missing identity fails closed. Per-request request.state is not persistent business/session storage. Durable inbox/claims/risk settings/stops remain in DB; test-only wrapper globals are not production state. Route-policy/session/owner-isolation tests passed in merge-SHA backend CI. |
| Activation and mode separation | migration0045 risk_protocol_control; policy.paper_opening_protocol_enabled; production app router composition | Protocol flags defaultfalse in shared DB. Test wrapper enables only its guarded local DB and turns flags off on shutdown; its control routes are not mounted in production. Paper paths/owner scopes remain explicit; browser Live mutation is unavailable. Passing isolated activation does not prove flags/readiness in a future deployment. |

Remote evidence: [post-merge backend/E2E CI](https://github.com/yukasung/tiewtrade/actions/runs/42374499165)
6/6Passed and [Security](https://github.com/yukasung/tiewtrade/actions/runs/42374499141)
7/7Passed. The backend command includes the cited API/core/risk/auth/stop tests;
F17 integration and migration guards run in explicit isolated steps. The E2E log
identifies test:e2e:risk-limits and6passed, not just generic browser success.
No source/config/harness change since that merge affects these proofs; no additional
test, load campaign or static-check rerun was necessary for this documentation audit.

F16 V-18's old missing-F18-policy implementation dependency is superseded by this
actual-policy integration proof and existing F18 R34/R35/R36 evidence. F16 V-18 is
recorded as integration Passed / target-environment activation Pending, not blanket
production readiness. IP-V3's code/CI audit is complete; operational admission
readiness must be established in the chosen environment before internal opening.

Next is step3: prepare the existing access controls for at most10invited people,
Paper-only access, no public signup/access and a development warning. The opening
checkpoint must also identify the target deployment, verify its migration/worker/
feed/owner-risk readiness and controlled activation procedure, then obtain explicit
deploy/opening authorization. No target process/DB/flag was changed here. Step3 has
not started; owner instruction is required. No new capacity cap, infrastructure,
security exception, Live path, requirement change or F17 Completed claim is added.
