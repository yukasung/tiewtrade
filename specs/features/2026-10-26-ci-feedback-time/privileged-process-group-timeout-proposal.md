# Privileged process-group timeout correction

สถานะ: **Approved — owner “approve” 2026-11-19 before implementation**
วันที่: 2026-11-19
PR81 candidate d2aefa198fc6ad45d9acaaeb78ba54a641008024; main remains unchanged.

## Finding and evidence

CI44479026954, policy job135406467410, fails the retained actual descendant assertion:
`test_inner_timeout_kills_descendant_before_outer_timeout`, line275, marker exists after
`timeout --signal=KILL 1s` returned124. No E2E/network worker ran. The previous failure
on93e504b stopped at the earlier code assertion; accepting supported124 exposed the
actual process-lifetime failure. Do not call this a harmless test-portability issue.
Local cached Linux GNU timeout passed the same descendant test; that proves only its
local binary behavior, not the hosted binary. Do not delete or skip the descendant test.

Upstream uutils reports the matching KILL-only-direct-child defect in
https://github.com/uutils/coreutils/issues/15768 (opened2026-10-25). This supports a likely
cause, but hosted binary version/path has not been captured, so do not claim exact runtime
identity proved. The GitHub image is Ubuntu26.04; version/image alone is not a binary proof.
https://docs.python.org/3/library/subprocess.html documents `Popen`, `start_new_session`
and timeout cleanup behavior. Keep the CI failure as the decisive observed evidence.

## Recommended bounded correction

- Replace dependency on host `timeout --signal=KILL` with a small standard-library Python
  supervisor in the same repository-owned helper. Reuse the existing fixed probe command
  construction, parsing, context/sanitized metadata and gate. No new dependency/image,
  package install, network configuration or runner selection change.
- Run the supervisor inside the required sudo context for privileged children. Start the
  fixed getent/curl/metadata command in its own session/process group; supervisor stays
  outside it and uses `os.killpg(..., SIGKILL)` on expiry, then reaps its direct child.
  Account for cleanup inside the current outer8s budget; retain DNS5s, curl6s/inner7s,
  metadata limits, global100s and step2min. No user-context cleanup pretending to kill root.
- Restrict internal operation/target/duration to existing probe/metadata cases. Preserve
  raw-output capture only across the internal subprocess boundary; validate/sanitize
  before JSON/logging as today. Never print command stderr, headers, proxy values/errors.
  Fail closed on launch/cleanup/privilege/schema/budget failures, not success or a retryable
  network timeout. Retry only genuine approved canonical sudo HTTPS timeout, at most3.
- Keep TLS verification/endpoint/sudo-success gate, all existing correctness/trading/
  READY/30s assertions and previous Failed/Partial states. Preserve default application,
  sessions, money, DB/schema and workflow selection unchanged.

## Feature validation and bounded execution

One local correction checkpoint: record approved amendment before source edit, then
implement, targeted tests/static checks, review/fix as authorized by AGENTS2026-11-14/18.
Validate actual descendant termination (including TERM-ignoring child), child reaping,
normal success/nonzero, missing tool, cleanup error, malformed/unknown internal operation,
secret suppression, exact root/user command wiring, deadline and retry/gate preservation.
Use disposable local Linux root container and actual user/sudo hosted evidence; no Live
orders or workload campaign. Keep the current descendant assertion active on hosted Linux.
If local evidence cannot prove cleanup within existing budgets, stop rather than relax it.
Expected local20–30minutes, then exactly one new required CI/Security round20–30minutes;
stop/report on failure before another hosted attempt. On success follow existing approved
expected-head merge, required postmerge checks20–30minutes and verified merged-ref cleanup.
Owner approved this correction checkpoint and exactly one new required CI/Security round.
Stop/report on failure before any further hosted round.

## Alternatives

Keep PR81 open and the four refs unchanged pending a proven runner/coreutils fix. Do not
rerun the same failing candidate as a correction or switch images/skip the test silently.
An explicit GNU binary could be smaller but its availability on hosted sudo PATH has not
been proved; installing/replacing coreutils would broaden scope and require network access.


## Implementation detail recorded before source edit

Use one internal `--supervise OP TARGET` mode restricted to dns/https/metadata and the
existing fixed targets. Fixed commands and durations are constructed inside that mode;
never accept arbitrary executable/timeout flags. The root supervisor uses Popen with a
new session, kills its process group and reaps within0.5s cleanup reservation inside the
outer8s. Classify outer supervisor/privilege/envelope/cleanup errors as operational failure,
not a retryable network timeout. Return a strictly validated internal CommandResult JSON;
only existing parsed/sanitized outcomes enter the final report. Preserve earlier timeout
parser behavior for actual fixed-command results. Use existing metadata-only mode inside
the supervised metadata command and existing run_command for the outer boundary.


## Feature local implementation/review checkpoint

- Supervisor uses fixed operation/target allowlists and fixed5/7s limits; same helper
  runs inside sudo for privileged work. New session, explicit process-group SIGKILL,
  bounded0.5s direct-child reap, pipe close. Cleanup/supervisor/privilege/envelope failures
  become operational_error and cannot trigger a network retry. Existing network result
  parser, TLS/current-sudo-success gate, budgets, selection and assertions retained.
- Actual offline Linux root container using the existing cached image:30 network tests
  Passed, zero skips. Descendant registers SIGTERM-ignore, writes a started marker, then
  cannot write its delayed orphan marker after group timeout. Actual internal CLI test
  executes fixed DNS fixture, verifies own session and same effective UID, and exercises
  envelope/probe parsing. No GNU/uutils timeout binary is used or needed.
- Whole local policy suite71 OK with one Linux-only skip; Ruff check/format and strict
  mypy on both changed Python files Passed. Reused unaffected chart real-DB/browser and
  historical checksum proofs; no application test rerun solely for this diagnostic change.
- Initial container CLI fixture failed because default Docker tmpfs is noexec; resolution
  checked fixture executable discovery, then allowed exec only on this disposable tmpfs.
  All30 passed with network disabled/read-only root/source. One added test string exceeded
  line length and was split; final Ruff passed. These were local harness/static failures,
  not evidence of hosted success or a reason to weaken assertions.
- Reviewed source/test diff, fixed target/duration and sudo boundary, lifecycle/cleanup,
  protocol schema/redaction, retry distinction, global/per-probe budget and existing worker
  caller/order/2min cap. No remaining findings. Existing application stateless/session,
  persistence, money/order/risk behavior untouched. Shared fixed-command construction is
  the necessary refactor; no unrelated refactor is justified.
- Required hosted CI/Security on final candidate remains Pending. Exactly one new round
  authorized by latest owner approve, stop/report on failure. Previous93e504b/d2aefa1
  policy failures and all earlier failures remain Failed. On success continue existing
  expected-head merge, mandatory postmerge gates and exact merged-ref cleanup.
