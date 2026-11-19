# Paper publication and opening gate audit — 2026-11-19

สถานะ: **Audit complete; activation not performed. F-17 Pending Full Validation.**
Audited main: `81334aa7e50828382822a2bc0339fe3565ee6991`.
Authority: owner “เริ่มทำ” after proposed status reconciliation and Paper admission audit.
This is a repository/evidence audit, not inspection of an active deployment or owner DB.

## Publication and source bridge

[PR76](https://github.com/yukasung/tiewtrade/pull/76) published the accumulated
reader/financial-evidence and harness corrections at
`d3c9eae91f8fd0c0de091862106a77873d72b6b5`. The
[publication checkpoint](publication-checkpoint.md) records 640 targeted tests and
41-file static checks, complete-cursor/exact-fill/RLS/concurrent-fill coverage, and
W4-only readiness adaptation. Earlier CI failures and postmerge picomatch blocker
remain in the [original record](publication-postmerge-blocker.md); subsequent LP04
remediation and PR79/80 caller/source validation close the current security publication
blocker without changing Paper execution logic.

Read-only `git diff --name-only d3c9eae main -- backend/src backend/migrations
frontend/src compose.yaml` returns no paths. The same comparison of
`backend/tests/infra/execution_market`, `backend/tests/infra/protections` and
`backend/tests/infra/paper_orders` returns no paths. This bridges the published financial,
protection and workload implementation to audited main; it does not claim all repository
files or dependency bytes are unchanged. PR80 changed frontend tooling, with its own
frozen-install/caller/E2E evidence; PR81 changed chart/preflight test composition, with
its own actual DB/browser/Linux/CI proof. Those changes do not alter W3/W4 execution.

Current main passed [CI 44484162505](https://github.com/yukasung/tiewtrade/actions/runs/44484162505)
and [Security 44484162445](https://github.com/yukasung/tiewtrade/actions/runs/44484162445).
The previous [Nov17 audit](paper-gate-audit-20261117.md) final-publication and W4 pending
statements describe their earlier checkpoint; current scoped results are below.

| Gate | Current finding | Disposition |
|---|---|---|
| W3 observed original 4h / internal20 | [AWAKE01](w3-awake01-result.md): 28,200 commands, seven recovered faults, all 20 financial/replay oracles and resource/cleanup checks Passed | Reuse on unchanged workload/production paths; no repeat campaign justified |
| Representative replay20 | [REBUILD20-05](rebuild20-05-result.md): 144,364 inputs per owner, all 20 full financial replays within original 60s | Reuse scoped proof; not original100-account acceptance |
| W4 current reader/fill recovery | [READY02](w4-ready02-result.md): actual dump/restore, 21 episodes/58 evidence, expired claim recovery, RLS/exact retry/no duplicate exit Passed | Nov17 current-W4 gap closed; CURRENT01 Incomplete retained |
| Publication inventory/review/required CI | PR76 inventory/targeted checks, subsequent remediations and current main CI/Security Passed | Publication gap closed; no owner opening authority inferred |
| Owner visual acceptance | [Latest MF-13 record](../../manual-acceptance-fix-validation.md#latest-mf-13-read-only-visual-preparation--2026-11-12) explicitly leaves owner visual confirmation Pending | Retain pending; earlier functional STOP/REPLACE/CANCEL proof remains valid only in its scope |
| Original100-account integrated/Release acceptance | Earlier Failed/Partial/Incomplete retained in validation; internal20 is a separately approved profile | Pending Full Validation; not replaced by W3 internal20 or CI |
| Bot/notifications and Live | V-19 depends on F-20/F-21/notification work; V-20 depends on Live integration | Pending Dependency / Full Validation; no activation |

## Actual admission contracts

- Signup: `backend/src/tiewtrade/services/api/settings.py::signup_open` defaults closed
  unless `TIEWTRADE_SIGNUP_OPEN=1`. Development `compose.yaml` explicitly sets 1 and
  contains development-only credentials/port bindings. It is not evidence that public
  registration is closed on an intended deployment. No environment/credential values
  from a running process were read by this audit.
- Opening risk: `infra/risk_limits/policy.py::paper_opening_protocol_enabled` reads all
  three PostgreSQL `risk_protocol_control` switches in the owner transaction. Migration
  0045 defaults publication/financial/admission false; API intake and engine paths use
  the shared policy, owner locks and database proof. Current deployed switch values
  were not queried and must not be inferred from migration defaults or old cleanup.
- Protection: migration 0063 defaults `paper_protection_protocol.enabled` false;
  `infra/paper_orders/requests.py` and `infra/protections/storage.py`/`worker.py` enforce
  it. The approved plan requires compatible allocation-aware writers before activation
  and excludes mixed old financial writers. `services/engine/paper_order_main.py`
  runs protection work before intake/matching, but a source/PID check alone does not
  prove the actual target workers, feed freshness or readiness.
- STOP authority: `services/api/kill_switch_routes.py::_require_authority_enabled`
  requires explicit `TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED=1`. It is absent from
  base Compose. MF-09/13 require effective API config and durable STOP completion
  before admission; a risk READY display or worker PID is insufficient. Existing
  `backend/tests/api/test_kill_switch_routes.py` retains the default-closed regression.
- Isolation/stateless: `infra/auth/sessions.py` keeps hashed login sessions in PostgreSQL;
  risk/protection switches, order receipts, claims and owner locks are shared DB state.
  Engine pool objects and disposable scheduling hints are not persistent truth. The
  reviewed paths introduce no process-local session authority or new infrastructure.
- Paper mutation routers remain `/paper`; source/CI evidence does not grant Live or
  owner-account mutation authority. Twenty synthetic accounts and 5 commands/s are
  validation profiles, not application-enforced signup/account/throughput limits.

## Next bounded checkpoint

Prepare read-only visual acceptance on the intended current-candidate local environment,
then obtain the owner's outstanding MF-13 visual confirmation. Reuse the already accepted
functional owner observations; do not submit additional orders merely to repeat them.
If starting a preview requires owner-service changes, use its existing approved startup
procedure and verify its ownership/configuration first. No preview was started here.

Before any later Paper opening, record the intended internal audience/target and explicit
owner opening authority; verify effective signup exposure, migrated schema, compatible
writers, live source/worker readiness, effective STOP authority/durable completion and
actual database protocol state against the approved gates. This audit does not add a
user cap or authorize changing flags. A missing target/acceptance is an activation blocker,
not grounds to rerun the four-hour campaign. New scope/financial actions and original
Release/dependency work retain their existing approval/validation requirements.

Audit verification: current and historical PR/CI states, source equality and original-head
ancestry were checked read-only; Markdown links/status consistency and whitespace checked
for this documentation delta. No application tests, workload, DB query, orders, account
change, deployment or activation were performed. Documentation publication follows standing
AGENTS Git authorization and unchanged required checks; its own CI is reported with SHA/run
links rather than another report-only commit. No further work remains in this audit scope.
