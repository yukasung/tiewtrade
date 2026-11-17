# TAIL-02 review findings R1/R2 — corrections

สถานะ: **Corrected; targeted validation Passed; awaiting owner refactor instruction**
Owner instructed “แก้ไข” after the two Medium findings. No new timed run/Git action.

## Corrections

R1: Exact historical SQL packaged in fixtures/tail_cursor_baseline.json with
revision/path/normalization/original digest. baseline_sql verifies these and the
content digest against the preserved TAIL-01 summary. No Git/process/network or
ancestor object lookup; obsolete historical source extractor removed. Missing,
malformed, hash/SQL/provenance/type corruption fails closed with sanitized ValueError.
No workflow checkout change or fallback control.

R2: Binding guard matches the helper's actual awaited session.execute expression,
SQL constant and episode parameters, plus awaited result assignments at both
callers. Rejects SQL concatenation, unused references, wrong episode, missing await,
discarded results, extra helper statements, duplicate references and empty source.
Formatting-only AST differences remain accepted. No general AST framework or
runtime session/query/pool/deadline modification.

## Verification

141targeted tests Passed in23.55s, no skips: prior123plus18new control/binding cases.
No-Git test uses a root with no repository and forbids process capture. Original
review counterexamples now fail closed; control corruption and formatting covered.
Retained real-PG equivalence/RLS/snapshot, final-tail/error/timeout and parent-poll
regressions Passed. Scoped Ruff check/format check/mypy Passed on3Python files;
JSON provenance/content digest and whitespace verified. Test parent DB removed
normally. Private log: validation-artifacts/f17-clock-recovery-tests-20261115/
attempt-1794734249434144000.log.

[Source bridge](tail02-review-fixes-source-bridge.json) proves profile_workload.py
unchanged and measured old/new SQL digests identical to TAIL-02. Its86observations
remain valid for that isolated fixture, not current-candidate4h acceptance. No old
receipt overwritten. Backend production/migrations/frontend unchanged; no trading,
financial calculation, session persistence or multi-instance behavior changed.
Ephemeral observation is diagnostic control, never authoritative business state.

No required CI, timed campaign, commit/push/merge or opening. Both4hIncomplete
results and finalfinancial/rebuild/Release/dependencies remain pending; F17 not
Completed. Next: separate owner refactor instruction per AGENTS, then affected
validation. New4h/Git execution still requires its applicable authorization.
