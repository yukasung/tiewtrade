# Shared Candle Closure Proof — implementation review checkpoints

2026-11-21. Implementation and scoped review/fixes are ready for owner checkpoint;
**not Completed, not ready to merge, not activated in owner preview**.
Requirements, plan and validation remain Approved. No Live or owner-account order was sent.

Initial historical candidate: `evidence/reviewed-candidate-manifest.json`; unpublished dependency base
`46841d394f4fe23f94626114619ef0c4c66438d1`. Original F21/Paper WIP and preview were preserved.

## Initial review findings and disposition (historical)

| Severity | Location | Problem and impact | Fix / disposition |
|---|---|---|---|
| High | `infra/market_data/claims.py::write_candles`, `candle_closure.py::series_health`, `infra/bots/candle_sources.py` | A corrected CLOSED candle could otherwise be skipped, or become eligible UNCONFIRMED warm-up for a later signal while its contradiction remained unresolved. New entries could use unverified historical inputs. | Inspect contradictions before the legacy CLOSED skip; atomically invalidate/demote/journal. Block the affected pair/timeframe until matching repair; preserve conflict across candidate replacement and advance durable recovery cutoff. Real PG regression passed. |
| High | `infra/bots/inputs.py`, `authority.py::_queued_signal_current` | A proof read during evaluation must not authorize a queued BUY after correction, lease/catalog/protocol change or proof replacement. | Server-derived proof ID/policy/fingerprint are pinned in provenance and rebound under existing source/wallet/risk locks at commit/admission. Active correction tests reject orders before commit or matching. Existing authority matrix passed. |
| Medium | `infra/bots/indicator_tail.py`, `infra/indicators/prepared.py` | Closure promotion within a prepared head invalidates the old checkpoint. A suffix-only-after-head fallback cannot restore it safely. | Restore before the earliest journal change, prove unchanged prefix at the original fence, replay fewer than1000 candles under a new fence and recheck both on admission. Codec, freshness, numeric-failure, rollout and head-authority gates retained. |
| Medium | `infra/bots/inputs.py::read_bot_indicators` | F11 aggregate UNCONFIRMED provenance includes eligible warm-up history, so it cannot alone identify signal-candle finality. It prevented legitimate entries with a verified CLOSED signal. | Preserve aggregate metadata; require the actual canonical signal CLOSED plus current proof before permitting inherited UNCONFIRMED warm-up provenance. OFF and other strategies retain prior guards. Actual strategy/Paper matcher fixture passed. |
| Medium | `infra/market_data/storage.py::coalesce_demand` | Periodic enqueue could revive an exhausted closure-only refresh using a new request timestamp for the same evidence. | Bind closure-only demand to immutable candidate creation time; preserve existing retry/backoff/deadline budget. Real PG exhausted-demand replay test passed. |
| Low | `services/market_data/candle_realtime.py` | Deeply nested capture logic obscured native versus sticky preview hints. | Extract `_persist_closure`; persist actual native x=true before replacing the latest slot. Metadata-only duplicate and progression regression passed. |

No unresolved Critical/High source-code finding was identified in the reviewed scope after
these fixes. This is an automated scoped review, not owner acceptance or independent review.

## Coverage and checks

- Requirements CP01–07: strict native candidate, exact typed OHLCV comparison, post-end
  request bounds, append-only native/results chain, guarded atomic CLOSED publication.
- CP08–10: durable multi-instance source/lease/catalog fences; correction invalidation,
  conflict recovery, deterministic duplicate keys, current proof revalidation and recovery cutoff.
- CP11–13: existing A-to-B freshness/entry/STOP/risk guards preserved; actual Paper matcher
  composition verifies orders and rejects stale authority. Post-fill correction preserves
  stored first-fill anchors, position projection and wallet ledger; no execution rewrite.
- CP14–16: existing coalescing/rate/backoff and typed adapters reused; default OFF, strict
  migrator activation attestations, trigger inventory, narrow runtime privileges and durable
  diagnostic states. No hidden UI text was restored and no frontend contract changed.
- Architecture/stateless/security: all authoritative state is PostgreSQL, transient buffers
  only schedule/display; new-pool/concurrent-worker tests passed. No Redis/infrastructure,
  persistent in-process authority, private exchange API, money formula or Live permission added.
  Seven import contracts passed. Money/Quantity are used for exact financial values.

Evidence (counts overlap; do not sum as unique cases):

| Check | Result | Evidence |
|---|---|---|
| Final source/indicator/claim/permissions/Paper/authority regression | 149 passed | `evidence/targeted-regression.txt` |
| Venue/core/both pure strategies | 289 passed; additional exact-field coverage26 passed | `venue-core-strategy.txt`, `exact-fields.txt` |
| Closure PG suite, including post-fill and conflict repair | 17 passed; extra before/after-promotion rollback2 passed | `closure-conflict-review.txt`, `rollback-after-promotion.txt` |
| Existing F21/Paper migration tests | 4 passed | `existing-migrations.txt` |
| Realtime subscription/progression units after test import fix | 15 passed | `service-units.txt` |
| Changed-file Ruff + format | Passed | `lint-and-format.txt` |
| Source mypy | 287 files passed | `source-types.txt` |
| All changed source/test files, scoped mypy | 20 files passed | `changed-file-types.txt` |
| Import boundaries | 7 kept,0 broken | `import-contracts.txt` |
| Full repository mypy | **Failed:90 errors in10 unchanged dependency test files** | `full-typecheck-failed.txt` |

Full mypy is not being waived. It remains a pre-merge blocker; source-only/scoped success
is not a substitute. No unrelated dependency test annotations were changed in this branch.

Failure history retained: first P1 role checks exposed missing narrow metadata grants;
fixed and subsequent PG runs passed. An old bootstrap scheduling mock did not implement
new DB calls; its interrupted run was replaced with an explicit scoped mock plus real PG
coverage. Early OFF-mode admission/query-budget regressions were corrected. A proposed
migration-test expectation change was wrong: Alembic commits revisions separately. It
failed2/4 tests, was restored exactly, and all4 original tests passed. No requirement or
safety assertion was relaxed.

## Public campaign and remaining gates

The single authorized public attempt is **Partial**, not Passed:
`evidence/public-paper-campaign.json` (historical candidate manifest retained separately).
Boot ran08:09:06–08:10:49 UTC. Actual BTC/ETH1m REST history was fetched; F11 returned
READY then SUPERSEDED/SOURCE_CHANGED. The execution source additionally reported book
readiness unavailable. Closure activation and API bot setup were not reached. There were
**zero orders, fills, positions or accepted closure proofs**. Owned services were cancelled;
no owner preview/account was changed and no additional public attempt was made.

The later CP06 runtime correction has deterministic PG evidence but no real public campaign
on that final runtime. V17 remains incomplete and requires a newly authorized bounded run;
its failure cannot be described as NO_SIGNAL because strategies were not reached.

Remaining risks/gates:

- Real source/bootstrap/F11 and order-book readiness must be established before claiming
  an end-to-end real-source Paper entry. Exact WS/REST conflicts intentionally block entry;
  no volume tolerance or synthetic CLOSED/ARM/fill was introduced.
- Conflict can keep a series unavailable until fresh matching evidence is obtainable.
  This preserves CP06; any relaxation is a separate owner decision.
- Full repository type check, full stable-candidate backend regression/required CI, owner
  acceptance and independent review where required are still outstanding.
- Batch/Release remain Pending Full Validation. No commit/push/PR/merge or owner-preview
  protocol activation was performed by this implementation checkpoint.

Next: resolve the existing combined-candidate CI blockers in their owning scope and obtain
approval for another bounded public campaign after source readiness preparation. Owner
acceptance must precede preview activation; it may allow an already-started Paper run to
buy when valid signals arrive. Required CI must pass on the final combined candidate.


## Owner continuation review — historical checkpoint (corrections below)

Final candidate: `evidence/continuation-reviewed-candidate-manifest.json`.
This follow-up reviewed only dependency annotations, the failed test inventories/fixtures,
and campaign harness changes against their affected callers; previous runtime review and
unaffected correctness evidence remain applicable. No production trading behavior changed
in this continuation. PostgreSQL remains authoritative; no login/business state was moved
to memory, no infrastructure dependency or Live capability was added.

Findings resolved:

| Severity | Location | Problem / impact | Fix and evidence |
|---|---|---|---|
| Medium | ten F21 dependency test files listed in plan | Full strict mypy had90 errors, blocking CI. | Explicit annotations/narrowing/direct imports/SQL mappings; no assertions removed. Full804-file mypy Passed. |
| Medium | `tests/api/test_api_key_routes.py`, `test_route_policy.py` | Approved configuration routes missing from the explicit secret/policy inventory. | Exact identity placeholder/404 and renewing route added. Canary2passed; final affected16passed. |
| Medium | `tests/api/test_strategy_status.py` | Shared state and missing F11 authority prevented intended real accounting scenarios. | Reuse isolated PG/client and existing seed_prepared, preserving flat/read-only protection assertions. Final affected16passed. |
| Medium | `tests/gates/test_paper_isolation.py`, `tests/infra/bots/test_candle_finality_reason.py` | Inventories/mocks predated approved F21/closure dependencies. | Explicit internal SQL/domain paths with recursive network/secret prohibition retained; complete indicator metadata and exact missing-proof rejection. Final affected16passed. |
| Low | `tests/infra/execution_market/profile_candle_closure.py::prepare_heads` | Exactly two build calls treated safe SUPERSEDED as failed readiness. | Existing DB scheduler/fresh-head authority, unchanged600s cooldown, total300s preparation limit. No synthetic readiness; campaign2 reached both READY. |
| Medium | same profile, `main` exception report | RuntimeError-only reporting lost the API setup failure location/status; original campaign cause cannot be reconstructed. | Typed API rejection and safe frame metadata; excludes bodies/locals/raw errors. Six harness tests Passed, including secret exclusion and exclusive-attempt preservation. Original Partial remains unresolved acceptance evidence. |

Environment findings: shared Redis Pub/Sub caused the full-run idle test to receive an
uncontrolled event; dedicated temporary Redis passed unchanged tests. Two protection SLA
cases failed during concurrent full load; unchanged cases passed after it quiesced. No
production code, timeout, correctness/security/trading threshold was relaxed.

Final checks: full mypy804 Passed, Ruff Passed, format885 Passed; API contract unchanged,
import contracts7 kept. Full backend raw result6012passed/7failed/32deselected, followed by
16passed affected regressions covering all failures plus both protection timing cases.
Other isolated CI phases exited0. Counts overlap and cannot be summed as unique tests.
See validation and `evidence/continuation-checks.json` for logs and historical failures.

Remaining risks and gates: campaign2 ended Partial at OWNED_API_SETUP with zero users,
wallets, orders and positions; neither real entry nor real-source TP/SL was proved.
An offline fresh-DB API signup succeeded and does not identify the campaign's original
failure. Do not claim a code cause or NO_SIGNAL. Another actual-source attempt requires
owner authorization under the bounded-attempt rule. Remaining Feature matrices, owner/
independent acceptance and required CI remain open; Batch/Release Pending Full Validation.
No publication, merge, owner-preview activation or Live trade. No new unresolved Critical/
High source finding was identified in this follow-up; validation is still incomplete.

Next: owner decides whether to authorize another bounded public campaign with the improved
safe diagnostics; do not repeat automatically. Complete remaining gates before publication.


## Completion continuation review — historical code-review checkpoint

Candidate: `evidence/completion-candidate-manifest.json`. Ready for Code Review was
announced after the latest fixes/checks. This review covers only new harness/test changes
and their API/evidence callers; previous production review and regression remain valid.

| Severity | Location | Problem / impact | Recommended fix / disposition |
|---|---|---|---|
| Medium | `tests/infra/execution_market/profile_candle_closure.py::campaign` | RSI payload included strategy_name, forbidden by its API input model; actual attempt3 stopped with422 before creating runs. | Fixed: reuse existing StrategyConfigurationInput/PaperTestConfigurationInput via configuration_payload. Both pass real HTTP/PG and replay assertions. |
| Medium | same profile, inventory and capture_evidence | Migrator FORCE RLS hid users/financial rows, producing misleading zero-activity evidence and ineffective empty-DB inventory. | Fixed: strictly local owned-DB guard + existing test-admin read-only audit engine, parameter hiding, actual PG read/write-refusal proof. Append corrected read-only historical evidence; do not rewrite original reports. |

Actual corrected facts for both attempts2/3: each2users/2wallets/2EXTERNAL_CAPITAL ledger
rows;0runs/0orders/0positions. Previous zero-user/wallet statements are superseded and
must not be used as acceptance evidence. Attempt3 exact failure is configuration HTTP422;
attempt2 lacked status diagnostics and its exact original status remains unproved.

Validation: latest14passed affected API/PG/harness tests;9passed final guard/harness tests
(overlap). Full mypy804 Passed; Ruff/format Passed. One intermediate type error from using
a non-exported os import in the new guard test was corrected directly. No runtime trading,
financial math, money types, RLS policy, session storage, production infrastructure, API
contract or Live permission changed. Audit superuser is test-only/read-only and guarded;
no credential/cookie/body/raw-error text is included in evidence. Inspecting new diff and
callers found no further code defect. Existing full/failed/affected results are retained.

Still **CHANGES REQUIRED for acceptance**, despite review-ready code: real source entry
has not been demonstrated, remaining Feature matrices/owner and independent acceptance/
required CI are pending. Three bounded attempts were Partial; a fourth must be explicitly
chosen under AGENTS. Do not relabel this as NO_SIGNAL or Completed; no fake signal/fill,
threshold relaxation or campaign retry was used. Batch/Release Pending Full Validation.

Next: review current code now; owner decision is pending for a fourth bounded attempt.
No publication/merge or owner-preview activation before the outstanding gates.



## Authorized attempt4 evidence review — current checkpoint

Owner explicitly approved one further actual-source Paper attempt after the three-attempt
stop. Candidate remains `evidence/completion-candidate-manifest.json`, fingerprint
51f6519346fe9bf92bf5a4d53568678375b8198024fc99936762b955d3867566.
No implementation changed this turn; previous static, review and affected tests remain
applicable. Only plan authorization, evidence and checkpoint documentation changed.

Attempt4 boot12:51:38UTC; actual campaign12:53:15–12:59:16UTC,360s capture plus normal
cleanup. Result **Partial**, not Passed and not NO_SIGNAL. Two real API starts succeeded,
8MATCHED closure results and7decisions were persisted. Offline re-verification reconstructed
all8 actual native/REST pairs with existing Money/Quantity/Candle/ClosureCandidate and
verify_closure; identities, fingerprints, exact OHLCV and post-end request bounds Passed.

Actual green BTC12:54 candle produced one100USDT MARKET BUY command in the next candle,
requested12:55:41.081358UTC. Its decision references a verified proof and ATR; there is one
linked command, no duplicate. It was **REJECTED / ORDER_SAFETY_UNAVAILABLE**, recorded
12:56:24.323755UTC. No matched order projection/fill/execution/position/reservation exists.
The first-fill anchor remains unresolved (no execution/price/TP/SL); TP/SL and PnL therefore
remain unexercised by this public attempt. Both wallet ledgers retain only their original
10000USDT capital entries; no fee/trade/balance mutation was observed.

Commit-timestamp evidence: BUY decision committed12:55:41.701637, resulting runrevision8;
INDICATOR_NOT_READY pause revision9 committed12:56:00.684285; rejection committed
12:56:24.448782; resume revision10 committed12:56:28.294247. Thus the durable run was
PAUSED with a newer revision at rejection. Existing paper_bot_authority requires RUNNING
and queued proof checks pin the decision revision, so this state blocks that command.
This is evidence-backed code/timeline analysis; the generic rejection did not record an
individual sub-guard. No stop requests exist. The cause of roughly43seconds queue/
processing latency remains unproved; indicator/source readiness gaps, book warnings and
risk-monitor DATABASE_TIMEOUT deferrals occurred. Do not infer a root latency cause or
change freshness/admission/STOP/risk rules from these observations.

Evidence: `public-paper-campaign-4.json`, `public-paper-campaign-4-diagnostics.json`,
`public-paper-campaign-4-authority-timeline.json`, `public-paper-campaign-4-verification.json`
and raw log. FEED_DISCONNECTED in final execution state follows producer cleanup and
alone is not evidence of source state at admission. Original reports are preserved.

Owned workers stopped; temporary Redis cleaned up; owner preview/accounts/Live untouched.
No fifth public attempt, extension, synthetic signal/fill, business-rule relaxation or
commit/push/PR/merge. V17 remains Partial: real signal-to-command is now proved, but actual
fill/first-fill protection is not. Remaining owner/independent/required-CI and other Feature
matrices remain open; Batch/Release Pending Full Validation. Code-review readiness remains,
not Completed or merge-ready.

Next: review current code/evidence and diagnose command-dispatch/source readiness latency
before proposing any further bounded public attempt. Another attempt needs explicit owner
authorization; no automatic retry is part of this checkpoint.

CHANGES REQUIRED

## Review correction checkpoint —2026-11-22 (current)

Supersedes prior code-review disposition for the three High findings on parent51f65193.
Current source/test candidate51ab7d36 (full fingerprint in review-fix-candidate-manifest.json).

| Finding | Correction and evidence |
|---|---|
| High: queued BUY outlives B | authority.py checks native A→B interval using database time before and after proof reads and rechecks lease. Real-PG deterministic clock boundary/cross-boundary regression passed. |
| High: accepted BUY fills after proof invalidation | blocked_paper_openings reuses _closure_signal_current under risk_financial_fence/hold_bot_indicator_source through fill commit; includes SELL-driven shared matching, without queued run-revision equality. Actual matcher/ledger regressions passed with bot RUNNING and zero extra BUY executions. Pre-closure schemas retain the expand guard. |
| High: contradictory close published before progression check | supervisor classifies OPEN→close conflict/OLDER before persistence; record_candidate stores native candidate and INVALIDATED outcome atomically without reconcile. Saved metadata reconstructs the prior native observation. Concurrent PG reader test passed, no CLOSED/proof visible. |
| Related exit races uncovered by affected tests | Retain original rejection assertions: compare pinned guard_revision at queued/accepted authority and share signal_exit_guarded for signal A/current entry B at context and registration. Existing decision-first/exit-first, same-candle and rollback/lost-ack tests passed. No new cooldown. |
| Medium: incomplete Feature acceptance | Still open: public fill/protection, full compatibility/recovery matrices, owner/independent acceptance and required CI. No waiver or new campaign. |

Review covered changed callers and SQL lock ordering, RLS/roles, default-off compatibility,
error paths, Money/Quantity reuse, immutable execution/anchor preservation, reducing SELL,
stateless/multi-instance authority and duplicate/retry behavior. Reused closure-reference and
exit-guard helpers; no extra infrastructure, UI/contract or unrelated runtime change.

Validation: final PG67passed, failed basket/recovery4passed, units116passed, gates6passed;
counts overlap. Scoped mypy/Ruff/format8files and7import contracts passed. Earlier failures
(51/12,14/1,83/4), setup-only permission error and wrong test path are not green-run claims;
raw available reports remain. The original full6012/7 and public attempt4Partial remain
historical evidence, not final-candidate CI/venue acceptance. See validation.md current
checkpoint and review-fix-checks.json. No unresolved High correction finding after review;
overall feature is not Completed or merge-ready. No publication or public rerun performed.

Next: owner/independent review and outstanding Feature/CI gates. Another bounded actual
source campaign requires explicit owner authorization; no automatic fifth attempt.

CHANGES REQUIRED


## Scoped refactor checkpoint —2026-11-22

Owner requested refactor of the latest review correction only. Changed two production
files: authority.py names signal_end/entry_end and reuses the native calendar boundary;
candle_realtime.py uses an early generation/lease return and one prior observation to
remove repeated tuple access. Existing shared closure/exit helpers remain reused.
No new abstraction, financial formula, SQL, lock/transaction order, branch priority,
exception behavior, strategy or activation rule changed. The scoped before/after diff is
evidence/refactor-scoped.diff; this is separate from the larger uncommitted feature diff.

Candidate 9d77fa16b8932916fee62483208db15b49e966b4697ff9d3c830403cfdab1860 (39 Python files) is bound by
evidence/refactor-candidate-manifest.json; all previous manifests/reports are preserved.
Real PostgreSQL closure and commit-fence tests: **53 passed**. Realtime unit tests:
**15 passed**. Scoped Ruff/format and mypy (2 files), import contracts
(7 kept) and git diff --check passed. Raw test logs and static check summary are in
evidence/refactor-*. No public-source experiment was run. Dedicated disposable local
test services were used; owner preview/accounts and Live were untouched.

Review of the scoped refactor found no new issue. Persistent authority remains in
PostgreSQL; no session cache, process-local business authority or infrastructure was
added to the application. No test assertions or safety conditions were removed.
Previous Feature Partial gates, public-fill evidence, independent/owner acceptance and
required CI remain open; Batch/Release Pending Full Validation. Not Completed or
merge-ready. No commit/push/PR/merge. Next: remaining owner/independent acceptance and
required CI under the approved gates; another public campaign needs explicit approval.


## Local Feature-gate continuation —2026-11-22

Two additional real-PG V08 tests passed alongside four existing regressions (6 total).
Reviewed only the new tests and fixture/lease/claim interactions: real writes/claims,
separate pools, old-writer rejection and exact one-result assertions; no mocks substitute
for durable behavior. Production hashes remain unchanged after the refactor. Static checks
passed with src included for mypy resolution. See validation.md current local checkpoint,
local-recovery-candidate-manifest.json and local-recovery-tests.txt.

Offline historical dispatch analysis preserves ambiguity: terminal attempts is reset and
per-claim timing was not captured. Do not assert a latency root cause or change guards.
Owner publication exception is awaiting an answer; no draft PR/CI run/public campaign
was started. Full process/deployment recovery, public-fill and owner/independent/required-CI
gates remain open. No new finding in the added recovery tests.


## Draft publication candidate —2026-11-22

Owner publication exception is authorized; earlier pending-publication notes remain
historical. Integrated origin/main005ec483 F17 refactor without conflicts, preserving
EntryAtrProtection. Affected protection/paper-test/basket-target units118passed and actual
PostgreSQL first-fill/protection tests10passed. Scoped Ruff/format/mypy2files passed;
git diff --check passed. Logs: publication-protection-units.txt, publication-first-fill-pg.txt.
No new runtime correction or trading-rule change was needed for integration.

Final reviewed commit will bind the combined F21/Paper dependencies plus closure source,
fixes/refactor/tests and all existing evidence. publication-candidate-manifest.json binds
changed runtime/test/config file content against main005ec483; previous manifests remain
historical. Draft PR only, no merge. Required CI has not yet passed and will be reported
with final SHA/run links after publication, without a documentation-only commit loop.

Owner/independent acceptance, remaining Partial matrices and public actual fill remain
open. No campaign5, owner-preview/account operation, Live activation or merge is authorized.
Batch/Release remain Pending Full Validation; not Completed or merge-ready.


## Browser fixture correction checkpoint —2026-11-22

Corrected only two E2E files: chart Timeframe lookup uses exact:true like the existing
locators; strategy selector is required to be enabled/focusable when no run is pinned,
with Shift+Tab/Tab assertions through it. All Start-disabled,16UI combinations, budget
persistence, no-form/no-tabs and zero-mutating-request checks remain. Actual isolated
local browser regression2passed in23.7s; scoped ESLint and frontend typecheck passed.
See evidence/publication-e2e-corrections.txt. No runtime, strategy, trading safety,
timeout or environment guard was loosened. Original CI44986019642 E2E34/2 result is
preserved. Push this in-scope test correction and evaluate required CI on the final head;
no merge/public campaign5/owner-preview activation. Other acceptance gates remain open.


## F16 stable draft-control checkpoint —2026-11-22

The one failing reset/recovery browser case passed locally in10.5s on disposable services.
Scoped ESLint and frontend typecheck passed. The existing test already used the bot-card
draft field; use one #paper-bot-budget locator instead of the pre-F21 label at all three
assertions. Reset/409/UNKNOWN/original-body-and-key/404/empty-journal checks are unchanged.
No runtime/safety/timeout change. See evidence/publication-manual-draft-correction.txt.
Search found no remaining E2E references to that obsolete label or the corrected loose
Timeframe/strategy-disabled expectations. Push the test-only fix and follow final-SHA CI;
keep previous failures, owner/independent/public-fill gates and no-merge scope unchanged.


## Post-CI process-crash test review —2026-11-22

Published runtime e193fd32passed required CI44990595087 and Security44990595105,
including66browser cases. New local diff is only four parametrized real-process crash
cases plus reuse of the existing subprocess marker/closure fixtures. Checked transaction
boundary visibility, source scope, rollback revision, durable pending recovery, proof-ID
and observation/result dedup, child cleanup and runtime role separation. The CHILD
fixture stores no persistent business authority; PostgreSQL remains authoritative.
Initial TT011 harness failures were corrected by acquiring the existing source scope;
all four new cases then passed; five related existing regressions had already passed.
Scoped lint/format/types passed after fixing mypy src resolution. No runtime, financial,
strategy, session, privilege or Live change. No new review finding in this diff.

See validation.md and process-crash-recovery-checks.txt. This self-review does not replace
independent/owner acceptance. V08/full Feature matrices and public fill remain Partial.
New tests are uncommitted/unpublished; no new CI or campaign was authorized this turn.


## Local deployment compatibility test review —2026-11-22

Added21tests (25with related regressions, all passed) for typed inventory, candidate
identity, source proof readiness, separate runtime writer processes and deactivation.
Reused ready/INVENTORY/marker; factored one rejection helper to compare unchanged
activation state rather than repeating SQL across three tests. Checked runtime roles,
source fencing, rollback visibility, child cleanup and PostgreSQL shared authority.
No production/financial/session/Live change and no remaining finding in this diff.
Ruff/format and strict mypy passed2files; evidence/deployment-compatibility-checks.txt.

Positive compatibility claim is limited to current proof v1. Legacy-style SQL rejection
is not proof of compatibility with an historical binary or actual deployed inventory.
V14 remains Partial for owner deployment evidence; new tests have no final-head CI.
No public campaign/preview activation/publication or merge occurred this turn.


## Proof-wait correction deep review —2026-11-22

Reviewed the narrow runtime correction, both modified PostgreSQL test modules, campaign5
artifacts, approved requirements/plan/validation and affected input/recovery/decision/
queued/matching dependencies. No unresolved Critical/High/Medium/Low finding in this
correction. UNCONFIRMED remains non-tradable until native/REST proof is current; normal
preparation waiting no longer resets the durable cutoff. Actual recovery, source/price/
indicator epoch changes and freshness/proof/owner/revision locks retain their authority.
No changes to financial formulas, session authority, role access or Live capability.

45selected PostgreSQL correctness/safety cases and Ruff/format/mypy3files plus7import
contracts passed. Reproduction before correction failed both new wait cases. Afterward,
normal wait→one command/Paper fill and reconnect→no stale BUY passed; RSI ARM/tail and
queued/matching/source/risk/STOP regressions passed. Evidence fingerprints match current
files. The review does not certify market availability: corrected-candidate public fill/
first-fill protection, final-SHA required CI and owner/independent acceptance remain open.
Owner now permits one publication/CI round for this reviewed patch, with no merge or new
public campaign. Keep this automated review distinct from independent human acceptance.
