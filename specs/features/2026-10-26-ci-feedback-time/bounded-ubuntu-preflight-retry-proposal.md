# Ubuntu sudo HTTPS preflight — bounded resilience proposal

สถานะ: **Approved — owner “approve” 2026-11-19, before implementation**
วันที่: 2026-11-19
Current PR81 headb288645, CI44475468423; main remains unmerged by this task.

## Evidence and existing contract

Repeated hosted runners fail canonical Ubuntu HTTPS in sudo despite successful DNS;
recent attempts return200 as user and timeout in sudo. The original chart correction
passed real-DB/native browser locally but its newly approved CI round did not reach
browser execution. Initial history head4578c20 also had two such preflight failures;
a third reached E2E. This is repeated operational variability, not proof that chart
criteria are wrong or that an endpoint/TLS/privilege gate should be removed.

The approved network-diagnostics-amendment.md explicitly says no retry (DNS5s,
curl6s, privileged coreutils7s/outer8s, global monotonic100s, workflow step2minutes).
Changing that approved no-retry clause needs owner approval. The last chart continuation
authorized one new CI round only; it failed, so no additional round has been launched.

## Recommended exact amendment

- Preserve canonical https://archive.ubuntu.com/ubuntu/ as the required sudo-context
  endpoint. Continue only after an actual successful verified HTTPS response there and
  a complete diagnostic within the existing100s global deadline. Never substitute user
  success, a local probe or an earlier run for sudo success on the current runner.
- Retry only sudo/canonical-Ubuntu HTTPS outcome `timeout`, at most two additional probes
  (three total), with bounded0.2s delay. Keep each curl6s, connect3s, privileged kill7s,
  outer8s and the global100s/step2min unchanged. Check remaining budget before every
  delay/spawn, and fail closed if insufficient/exhausted; no automatic workflow reruns.
- Keep all unsuccessful attempt statuses/counts in sanitized evidence; a final success
  must not rewrite earlier attempts as success. Never retain raw response/header/body,
  proxy credentials or curl error text. Preserve current DNS and other-context evidence.
- No retry/ignore for TLS/certificate/HTTP failure, malformed responses, missing tool,
  privileged execution failure or unknown status. No insecure TLS flag, HTTP fallback,
  endpoint replacement, DNS/resolver/apt/proxy mutation or CI-selection change.
- Reuse existing probe/bounded_command/status parser and existing tests. Add focused
  deterministic cases for timeout→success, all-timeout rejection, no retry for other
  failures, exhausted budget/no orphan privileged child, exact sanitization and unchanged
  gate. No application/financial/READY/30s/assertion or security severity/coverage change.

## Bounded execution after approval

One correction checkpoint: record amendment before code, targeted helper tests/static
checks, review/fix, then one new required CI/Security round on final candidate. Stop/report
on failure before another hosted attempt. If candidate passes, existing expected-head
merge, postmerge checks and merged/pushed/green cleanup of the four refs remain mandatory.
No extra Live/workload campaign. Expected local helper work10–20minutes; hosted required
CI and postmerge about20–30minutes each, depending on queue/network.

## Alternative

Keep current source/no-retry diagnostic and authorize exactly one same-SHA E2E-only retry
once the current workflow finishes. This is smaller scope but leaves the recurring
single-probe availability issue unchanged and may fail again. Keeping PR open and waiting
for network recovery is also valid; it does not authorize bypassing the gate or merging.

Owner approved the recommended exact amendment and its bounded execution with “approve”.
The original no-retry contract is superseded only for the timeout/context/endpoint above.
Current application/main and original four branch refs stay
untouched; chart fix and exact approved checksum exception remain in the reviewed PR.


## Feature checkpoint — implementation and review

- Implemented `https_probe` using the existing sanitized `probe`/`bounded_command`/
  status parser. Curl still has `--retry 0`; Python orchestration alone retries the exact
  approved timeout up to three total outcomes, retaining attempt evidence. All other
  contexts/endpoints/statuses remain single probe. No workflow or gate/assertion change.
- Reserve a full8s before any probe or privileged metadata subprocess; do not shorten
  the outer timeout below the existing inner7s. Recheck budget after retry delay before
  spawn. Exhaustion remains fail closed, with original timeout attempts retained.
- Local macOS policy suite:65 tests OK, one Linux-only test skipped. After test typing/
  formatting fixes, network suite24 OK with that one platform skip, Ruff check/format and
  strict mypy on both changed Python files passed. Initial static failures were test-only
  line length/type inference/module export issues, corrected without assertion changes.
- Actual Linux container using existing cached application image, network disabled,
  read-only source/root and disposable tmpfs: all24 network tests Passed, zero skips.
  Includes actual GNU timeout killing a descendant before its delayed marker write.
- Reviewed full helper/test diff, existing CI worker caller/order/2-minute cap and schema,
  requirements RQ04/05/06/09/10, gate completeness, sanitized evidence and budget edges.
  No open findings. Existing stateless/session/trading runtime is unaffected. No useful
  further refactor beyond the shared HTTPS wrapper; do not broaden source changes.
- Hosted Feature evidence remains Pending on the new final candidate. Previous network
  failures and chart CI failure remain Failed; local tests do not replace required CI.
  Next: publish once and follow one approved required CI/Security round; stop/report if
  it fails. If passed, existing expected-head merge/postmerge/cleanup remains authorized.
