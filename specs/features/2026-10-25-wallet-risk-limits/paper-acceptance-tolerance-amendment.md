# F18-R34 — bounded Paper acceptance tolerances

สถานะ: Approved — เจ้าของตอบ “ตกลงตามนี้” ต่อข้อเสนอรวม

## Exact approved criteria
For F18 Paper W1/W2/W3 only, each source channel may be short by at most
one unique committed observation per complete nominal measurement window:
count + 1 >= active_seconds * 5. This is one observation per run/channel,
not per second, owner, fault interval or gap. Preserve nominal counts and actual
counts, identities, [start,end) boundaries, original price-only fault exemptions
and all gap statistics. No drain/setup padding, duplicate counting or stale-price
permission. Diagnostic/CHECK defaults retain strict counts.

For W1/W2/W3, each owner's ready risk inputs must meet 99.5% within3s.
Run-wide99.9% within3s and every input<=5s remain mandatory, with complete
acknowledgements and no clock errors. This accepts up to0.5% per-owner responses
in3–5s; it does not change risk computation, freshness or production behavior.
Unspecified/CHECK profiles retain their existing per-owner quota.

Keep100owners×20orders,5Hz,explicitchildR33,processingp95<=500ms/p99<=1s,
resources,financial/fence/auth/idempotency rules,RESET,deadlines,overflow,recovery,
fault schedule and600/300/1800s windows unchanged. No Live execution.

## Implementation and evidence reuse
Reuse cadence_summary and sla_summary in backend/tests/infra/risk_limits;
add explicit bounded count allowance metadata and change only acceptance verdicts.
Correct required_book_inputs report to SOURCE_HZ, preserving nominal versus minimum.
Tests cover zero/one/two missing observations, duplicate/drain exclusion, approved
phase quotas, aggregate quota,hard bound and missing acknowledgement rejection.
Run affected lint/types; no runtime/publisher/schema changes.

R33 W1 raw FAILED result remains immutable. Re-evaluate its complete receipts and
risk evidence under R34 into a separate attributed assessment, checking all other
gates and proving the source delta is evaluation-only. Use W1 evidence only if
complete and every R34 gate passes. Do not relabel historical results in place.
Then continue W2→W3→W4 and regression/final review on unchanged runtime, recording
source hashes and the evaluator-only difference. One workload at a time; stop on
failure, no automatic retry or further threshold reduction. Estimated remaining
65–95min if gates pass first time, excluding fixes/CI/manual. Preparation10–15min.
Paper validation remains distinct from Completed; V22/V23 and missingCI/manual
stay pending. No commit/push/merge authorization.
