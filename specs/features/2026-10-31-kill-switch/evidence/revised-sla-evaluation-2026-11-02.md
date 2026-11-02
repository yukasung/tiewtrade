# F-19 revised SLA evaluator and NC17 offline evaluation — 2026-11-02

## Scope and result

Owner approved the amended plan and validation on 2026-11-02. The explicit `F19_SET5`
evaluator now requires, both per owner and run-wide, at least 99.5% within 3 seconds and
99.9% within 5 seconds, plus an absolute 6-second ceiling. Complete acknowledgements and
zero clock/stream-order errors remain mandatory. `F18_R34` retains its previous limits,
verdict and result schema. No production/API/schema/trading code changed and no W1 ran.

The affected non-DB regression passed 40 tests. Ruff format/check and mypy passed for the
two evaluator files. Exact 3.000/3.001, 5.000/5.001 and 6.000/6.001 boundaries, per-owner
versus run-wide disagreement, the independent absolute ceiling, earliest multi-input
acknowledgement, missing/pending/clock/order failures and unchanged F18 output are covered.

NC23/24 clock-setter observer source/tests were removed from the release candidate after
their reports/artifacts were retained. NC25 and further clock tracing remain stopped.

## Immutable NC17 derivation

The evaluator ran against a temporary copy of the NC17 receipts. Hashes of the original
inputs, result and every risk stream were checked before and after and did not change.
The original `acceptance_result=false` remains untouched.

- Original commit: `2322d86541a5ef68ef41e86f7f3ec9e6778e0fba`
- Original source tree SHA-256: `dfd4cce5d4702afcb6dfee1e80347b6783bf035be0e1480201ede9ac1ec17a13`
- Final evaluator SHA-256: `b820a0767d65667e2c7b640386866168f7a376b0061a47550b9ec713d2d0b53b`
- Final regression SHA-256: `803a989427da61baf2cd2713cc59beb7ffbdb7fa002e86ad7921f24b4d7557e1`
- 918,703/918,703 samples acknowledged; clock errors 0; stream-order errors 0
- Within 3 seconds: run 0.998582784643; worst owner 0.995754871013
- Within 5 seconds: run 0.999996734527; worst owner 0.999673451616
- Maximum: 5.034698 seconds; no 6-second absolute miss
- All 30 non-SLA acceptance terms are crosswalked: 26 Passed and 4 W1-only
  Not Applicable. This includes dedicated LOSS_LIMIT proof, exact command/cycle/fill/
  cancel/replay counters, owner/financial observations, source, resource/cleanup,
  scenarios, duration and worker outcome isolation.

The original result did not serialize individual child return codes. That acceptance term
is supported by the retained post-run `failed_gate=risk_sla` isolation artifact, which
identifies no non-SLA acceptance failure; this limitation is explicit in the derived JSON.

The derived Feature result passes the revised SLA. It is not a Batch/System Ready result:
NC17 predates the NC19 scheduler and final integrated Paper+Live candidate. Paper and Live
production activation remain off until the one final integrated workload and every release
dependency gate pass together.

Full derived output and per-owner values:
`validation-artifacts/f19-set5-20261101/revised-sla-20261102/derived-result.json`.
