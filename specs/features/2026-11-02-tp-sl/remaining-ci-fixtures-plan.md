# Remaining CI fixture configuration — proposed checkpoint

สถานะ: **Proposed — Needs Owner Approval before the next fix/retry cycle**
วันที่: 2026-11-07
Candidate: `12e62040d00f2797a7c192b50bd1d81c8edb3d68`, PR59

## Actual results and stop rule

Required Security passed7/7 on
https://github.com/yukasung/tiewtrade/actions/runs/42367203731 . Complete secret
scan/mapping stages took126.10s with unchanged15-minute budget and exact approvals.

CI failed on both events, with the same2cases:
- PR https://github.com/yukasung/tiewtrade/actions/runs/42367203737 :4759passed,
  2failed,31deselected; main pytest997.24s. Other5jobs, including E2E, passed.
- Push https://github.com/yukasung/tiewtrade/actions/runs/42367198109 :4759passed,
  2failed,31deselected; main pytest796.31s. Other5jobs passed.

Later isolated backend steps did not run. Historical candidates957559a (Linux
type-check failure),0961f78 (5fixture failures) and12e6204 (2fixture failures) are
three non-passing published CI rounds for this recovery checkpoint. Stop before
another fix/retry cycle under AGENTS.md/testing §7; no fourth run is started here.
Current CI alone took about17min on the PR; earlier candidate timings are retained
in their receipts. This plan adds no retrospective total-time estimate.

## Findings

1. **Confirmed config omission:** backend CI supplies7 role URLs, but the real
   checkpoint preflight checks every DatabaseRole, including PLATFORM_BOOTSTRAP.
   That URL is absent; E2E already configures it and bootstrap already creates the
   role. Failure is DatabaseConfigurationError before the complete-role assertion.
2. **Controlled input gap:** the financial-oracle wrapper uses the shared ambient
   database while forcing a1-successful-claim budget. Its first scenario submits an
   order, runs one global selection round, then requires that owner's projection.
   The NoResultFound occurs at test_worker.py:537. Other fixtures can supply earlier
   due candidates. Selected owner/claim was not captured, so foreign-queue selection
   is a supported hypothesis, not a proven trace-level cause. Isolate the scenario
   inputs before interpreting it as a production financial calculation failure.

## Option A — recommended, keep all criteria

Apply only these two changes:
- `.github/workflows/ci.yml`: add backend job's
  `TIEWTRADE_DATABASE_URL_PLATFORM_BOOTSTRAP`, reusing the existing E2E role URL
  pattern with backend database `tiewtrade` and canonical disposable-test credentials
  from `backend/db/bootstrap/00-roles.sql`. No role creation, grants, new service or
  runtime credential is added by this change.
- `backend/tests/infra/execution_market/test_claim_coordination_financial.py`:
  mark its parametrized real-DB oracle with
  `@pytest.mark.usefixtures("internal_database")`, reusing the existing fresh DB
  factory. Preserve every scenario, fault, oracle assertion and claim-limit1.

Before full CI, check workflow syntax and actual-role fresh-DB preflight; run the
10financial wrapper cases and related real-DB claim/isolation regressions. Retain
exact decimal/cash/quantity/reservation/position/audit/duplicate-effect assertions.
Run scoped static checks and a complete secret scan if publication inputs change;
new secrets/identities still require their existing stop/approval rules.

Then publish one combined candidate and track full required CI, including later
isolated backend steps. Estimate targeted checks1–3min, CI20–25min if it passes;
runner/failure variation remains. No automatic full retry after failure: report
evidence and known/unknown causes before another round. No Paper workload campaign,
production change, skip/xfail, assertion reduction, new timeout, merge/deploy/Live.

Approval of A authorizes these exact fixture/config changes, checks and one full
publication/CI round as one checkpoint. It does not extend secret exceptions or
change trading/resource/latency acceptance criteria.

## Option B — stop at the current checkpoint

Keep the current candidate/draft PR and record the failure. A smaller targeted-only
checkpoint can support investigation, but it cannot replace required full CI or
permit merge/F17 completion. There is no user-requirement/evidence basis to waive
all-role or financial correctness assertions or call these failures capacity/SLA
failures. No reduced correctness criterion is proposed; defer publication instead.

No code/config patch for this plan has been applied or tested yet. The security
implementation/approved dataset already passed and need no further expansion.
