# Combined candidate checkpoint

วันที่: 2026-11-08 (Asia/Bangkok)
Branch: feature/remove-prices-page
Base: 1237bf6f1e2146fff6c68d01094e4fbb96ebd8c3 (merged deadline fix PR #61)
Candidate: base + uncommitted prices-removal changes.
Frontend source/test diff SHA256: a781b0c3a68f50a7bf20d24af0d78d6cfd98fc64d6486d961256f2a6941a2e48

Owner authorized combining the merged fix and validating V-03 with “เริ่มทำ”.
Fast-forwarded the feature branch to main. Preserved every pre-existing tracked edit,
verified against the saved binary diff, except the intentionally combined roadmap additions.
Untracked feature specs/evidence were retained. No stash/reset, new commit, push or PR.
No additional backend diff exists relative to main.

## Result

[Targeted chart E2E](combined-chart-20261108.log): **4 passed in 22.6s**:
- module navigation/history/deep links and cancellation of inactive chart work;
- retired bookmark fallback, TH/EN desktop/mobile menus, keyboard and no price subscription;
- live snapshots READY → RECOVERING/STALE → READY without indicator reads;
- password login, pair/timeframe switching and real latest-price producer/API.

Used the unchanged playwright.chart.config.ts and default Uvicorn auto loop, not the
previous temporary --loop asyncio workaround. PostgreSQL 16/Redis 7 were disposable,
database tiewtrade_e2e_prices_20261108, ports 18012/18174. Task containers removed afterwards.
Existing dev servers and unrelated worktrees were not changed. No Live orders were sent.

First setup attempt ran migration while the new PostgreSQL container was still starting;
migration failed with connection_lost and all four tests failed in seed setup because the
schema function begin_indicator_source_write was absent. No feature assertions ran.
After pg_isready confirmed readiness, migration succeeded and all four tests passed.
No source, fixture, timeout or assertion changes were made to obtain the passing run.

Screenshots from this passing run are retained under combined-20261108/; historical images
and failed recovery evidence remain intact. Existing unit/static/build and price-service
results remain applicable because their code/dependencies/contracts are unchanged.
The imported backend fix was independently reviewed and passed post-merge CI:
https://github.com/yukasung/tiewtrade/actions/runs/42391404254
https://github.com/yukasung/tiewtrade/actions/runs/42391404243
Those runs do not substitute for required CI on this uncommitted combined candidate.

## Findings and next gate

Medium recovery validation blocker is closed by the combined default-loop result.
Low stale risk-E2E route list was fixed previously and remains fixed.
V-01..07 local evidence is satisfied; V-08 awaits the prices-feature refactor decision,
and V-09 required CI remains Not Run. No new findings from integration checks.
Next: ask owner whether to refactor this prices-removal feature, per AGENTS.md.
The prior refactor authorization concerned the separate deadline feature, not this feature.
Commit/push/PR and merge of prices removal still require their own commands.
Do not mark this feature Completed or ready to merge yet.
