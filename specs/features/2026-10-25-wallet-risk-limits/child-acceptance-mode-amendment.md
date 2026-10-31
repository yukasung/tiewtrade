# F18-R33 — use the validated child publisher for Paper acceptance

สถานะ: Approved — owner replied “approve” on 2026-10-29
วันที่: 2026-10-29

## Evidence and exact change

R32child5Hz diagnostic on source
b03b85789d9448a84b1c225affbc288af65a924b158b48ae0d0b7c21fbae5764 completed60s with
300unique committed BOOK observations and300freshprices for eachBTC/ETH channel.
Max gaps:BOOK0.292794s,PRICE0.499703s.3212orderedunique price-frame receipts match
the database; noINCOMPLETE/source/control failure,13pools finalized0checked-out,
postrun DBconnections0. See the canonical M5 checkpoint for raw evidence.
This passes the short source gate only, not risk/financial/RESET/W1–W4 acceptance.

Replace only the approved acceptance plan's inline mode with an explicitly selected
child publisher for W1/W2/W3 and W4 source-fixture build. Use the existing R31 code,
5Hz R32target and all original resource/pool limits; no new scheduling method,
financial logic, SQL/fence, worker count, resource allocation or criteria change.

Remove the CLI guard that currently rejects child mode outside source diagnostic.
Keep inline default for compatibility and debugging, but official acceptance runners
must explicitly select `--publisher-mode child`; no fallback on error. Record mode
in every relevant manifest. Add the same explicit selection to W4build (default
inline for existing callers); verify uses the captured build manifest and existing
restore procedure. Do not turn on diagnostic tracing for acceptance or modify
production market feed/runtime defaults.

## Checks and authorized progression after approval

Reuse R31/R32tests and current short-gate evidence where unaffected. Check CLI mode
selection without trace, W4build mode propagation, shutdown/tail receipt and process
inventory contracts; run affected lint/types. No repeat60s diagnostic merely because
a CLI gate changed. Freeze the final source/runner/config hashes after checks and
review the affected diff/dependencies.

Then proceed W1→W2→W3→W4→regression/final review under the already approved5Hz
acceptance plan. W1=600s,W2=300s,W3=1800s; same100×20 andR25–R32oracles. Use fresh
isolated databases and one workload at a time. Stop on a failing gate, preserve
unfinished inputs/failure evidence and do not retry or change settings automatically.
R33approval authorizes this mode change and conditional progression, not new
threshold changes or Live orders. No per-stage reapproval when prior gates pass.

Estimate first W1 checkpoint17–22min including mode checks/setup/10min measurement/
analysis; remaining complete sequence approximately85–120min if each gate passes,
excluding bug fixes and remoteCI/manual waiting. Update estimates if needed.

W1–W3 need evidence on final child5Hzcandidate; earlier inline/10Hzfailure records
remain unchanged. W4/regression reuse only with proven unaffected dependencies.
No commit/push/merge without owner instruction. Paper validation and F18Completed
remain distinct; V22/V23 and missing requiredCI/manual evidence stay pending.

## Why approval is needed

R32 explicitly kept child diagnostic-only, and the owner's acceptance plan chose
inline. R33 changes that acceptance-mode decision; the short diagnostic approval
alone did not authorize promotion. AGENTS.md requires approval before changing an
approved method. This is not a request to approve R31/R32 or unchanged tests again.
