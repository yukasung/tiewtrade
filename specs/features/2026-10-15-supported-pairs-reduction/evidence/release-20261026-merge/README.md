# F-38 merged-candidate release checkpoint — 2026-10-27

Status: **Passed — merged candidate release validation complete.**
This supersedes current-candidate handoff instructions in the historical audit
notes. RC-01–RC-15 are closed for validated candidate `aabdfb9`.

## Candidate and evidence scope

- Measured source base: `12bf6328b1d927115c8ac095285a3aeedb53dcb3`; final
  harness/evidence candidate `aabdfb9dfa68d12bacac9ebacbdaebf4d2a262cb`, branch
  `validation/f38-release-checkpoint`. Owner-authorized commit/push completed;
  PR #38 merged as `bf7b847c0c860682bc808b5b1d0c71539ff74267` on 2026-10-27.
- Measured image: `sha256:6cacc3bc9d9df1ce8b0fb31374fd89e489f2ffa264466d7f6a9372b6ceeb1210`,
  tag `tiewtrade-f38-merge-12bf632`, schema 0042.
- Capacity stack `tiewtrade-f38-merge-r5-20261026`, PG 55484/Redis 56434;
  API CPU 6–7, builder 4–5, each 2 CPU/1 GiB. S5 uses a fresh separate stack;
  see [fairness provenance](fairness-aggregate-checkpoint.md).
- Runtime scope BTC+ETH 16 series; measured BTC workload eight series. No Live
  orders or private venue requests are part of these local fixture harnesses.
- Production source, migrations and lockfile have no uncommitted changes.
  Read/publication/catalog/schema changes since `bfb6ab0` were assessed in
  [candidate comparison](checkpoint-audit.md#candidate-comparison) and covered
  by current-image C1, steady, dirty, scheduler and S5 evidence.

## Current release crosswalk

| Criteria | Result and evidence |
|---|---|
| RC-01 isolation | Passed for measured fixtures; C1 environment and fresh S5 provenance identify separate stacks and limits. |
| RC-02 provenance | Passed; comparison/reuse decisions in checkpoint audit, phase before/after hashes and fairness provenance. |
| RC-03 readiness/R2-7 | Passed; [C1 result](capacity/c1-r5/result.json), 16/16 runtime series, exact cold/warm evidence. |
| RC-04 steady | Passed; [steady checkpoint](capacity/combined-steady-r7/README.md), 3,600.000492 s, 360/360 ready and 60/60 correct probes per BTC series. |
| RC-05 dirty/recovery | Passed; [dirty checkpoint](capacity/combined-dirty-r2/README.md), 3,600.001577 s, recovery 60.075708 s, post-recovery readiness complete. |
| RC-06 fairness | Passed; [scheduler JUnit](capacity/scheduler-r1/tests.xml), 31 tests; fresh [S5 result](capacity/s5-r1/result.json), eight series within original deadlines. |
| RC-07 rejected load | Passed in the same two measured phases; BUSY 1,200 and RATE 1,200 per phase, exact details and zero candle queries. |
| RC-08 aggregate | Passed; [raw aggregate](capacity/aggregate-r1/result.json), C4/C6 Passed, 57/57 checks true, failures empty. |
| RC-09 scope | Passed; raw evaluator verifies 2 runtime pairs /16 readiness series /1 profile pair /8 workload series. |
| RC-10–RC-13 restore | Reused Passed within approved pre-0030 scope; see restore provenance below. |
| RC-14 tests/review/CI | Passed; affected checks/review and final candidate push/PR CI, 12/12 jobs green; see CI record below. |
| RC-15 crosswalk/docs | Passed; current evidence mapped to V-12/V-13/V-15, roadmap closure corrected. Historical failures remain retained. |

V-12 maps to RC-03–RC-08, V-13 to RC-04–RC-09, and V-15 to RC-10–RC-13.
This does not change F-11, F-15, ETH workload, production PREPARED or Live status.
Historical failed/interrupted capacity and diagnostic attempts retain their
original result; passing replacements do not rewrite those records.

## Restore evidence reuse

[Original restore result](../release-20261024/restore/r8/result.json) remains
Passed: quiesced pre-0030 backup, restore into a fresh disposable database,
verification and upgrade 0030; RPO=0, RTO=2.247043 s. This proves the approved
F-38 migration-0030 drill, not a complete schema-0042 production restore.

Migrations through 0030, migration environment/config, restore harness and
`uv.lock` are unchanged against `bfb6ab0`. Later schema additions do not alter
that historical migration path. The bootstrap addition supplies an offline
platform-bootstrap role; it does not change the restored fixture's existing
data-role permissions. No new restore run is required solely for main integration.
Order/balance/position tables did not exist at the fixture's pre-0030 revision;
do not infer validation of restoring those later tables from this drill.

On 2026-10-27 the retained dump was recovered read-only from stopped container
`tiewtrade-f38-restore-r5-20261025-postgres` at
`/tmp/tiewtrade_f38_restore_source_r8.dump` to host
`/tmp/tiewtrade-f38-verified-restore-r8.dump`. No database was started or restored.
Size **843,063 bytes**, SHA-256
`0114a54efd385d6093e9256529c560733536efee04fb3523a6ba2a6366b0820c`
matches the original manifest. The binary is retained outside Git.

## Final local review and verification

Ready for Code Review was announced at the harness checkpoint. Final review
covered barrier task completion/cancellation and expected recovery 503 handling,
Redis fixed-window alignment, diagnostic acceptance isolation, resource-gate
inputs, raw evaluator provenance, and dependencies changed by main integration.
No unresolved Critical/High finding remains in that reviewed scope.

One CI portability finding was fixed: the Linux-only diagnostic clock import's
Mac type-ignore became unused under Linux strict Mypy. Runtime lookup now uses
the same Linux function without a platform-dependent ignore. Mypy for Linux and
macOS passes for that module; Ruff check/format passes across the 14 capacity
harness/test files. This diagnostic module is not imported by the normal
acceptance entrypoint, so this correction invalidates no measured phase.

Reuse prior affected checks: 78 harness/scope/gate tests, 44 API regression tests,
static checks and 31 scheduler tests passed. No full suite or timed workload was
repeated during final review. No production change followed the measured runs.
The experimental response offload remains reverted.

Final candidate `aabdfb9` passed both required CI runs on 2026-10-27:
[PR CI 40431978440](https://github.com/yukasung/tiewtrade/actions/runs/40431978440)
and [push CI 40431967222](https://github.com/yukasung/tiewtrade/actions/runs/40431967222),
each 6/6 jobs green. PR backend: **3,462 passed, 2 deselected**, 673.76 s;
lint/format/types/imports, frontend, API contracts, container and browser E2E passed.
These replace the old-head CI as current candidate proof.

[PR #38](https://github.com/yukasung/tiewtrade/pull/38) merged as `bf7b847`.
Backend/frontend/Compose trees match `aabdfb9` exactly. Post-merge CI is tracked at
[40434466982](https://github.com/yukasung/tiewtrade/actions/runs/40434466982);
its final result is available on that run and does not require another workload.

## Closure scope

F-38 validation is complete for the final source/harness candidate. This closing
edit changes documentation only; code, dependencies, migration/config and raw
evidence are unchanged, so existing validation remains applicable. Required CI
continues to run through the repository workflow. Failed/partial historical
attempts remain preserved; no threshold, duration or denominator was relaxed.
Production hosting/PREPARED, Live activation, F-11/F-15 and ETH workload remain
outside this closure. No deployment or Live order was performed.
