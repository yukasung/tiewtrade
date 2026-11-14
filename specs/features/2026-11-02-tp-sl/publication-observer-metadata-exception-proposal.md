# PR75 observer metadata false-positive proposal

สถานะ: Approved A — owner explicitly approved the one exact false-positive identity on 2026-11-15 and instructed continuation through merge.

Security run43643041111 on candidate9f7c376bfd504b93bb297566a5a46e85938f7f74
blocked exactly one open finding; all other Security jobs passed.

- Kind: secret; scanner rule: generic-api-key.
- Identity: `c42e41222935f5834421eb5dac76023447c6a18ccb698c928a824a7281734252`.
- Location: backend/tests/infra/execution_market/profile_commit_observation.py:18
  in commit9f7c376bfd504b93bb297566a5a46e85938f7f74.
- Classified value: constant name of an ephemeral connection.info metadata slot;
  read/written exclusively by opt-in test observer, no credential/authentication use.
  Original process/session state and transaction rules unchanged.

Proposed registry diff: append exactly one secret/false_positive entry to
.github/security/exceptions.json with the identity above, this proof as evidence,
reason identifying the non-credential metadata slot, and approval recording the
owner's exact response. No wildcard/rule/path allowlist, scanner suppression,
threshold change, source change or existing exception modification.

After approval: validate registry/model negative tests and existing Security policy
tests, commit/push this bounded correction, follow final candidate CI, merge only
after all required gates pass, then follow post-merge CI. Preserve initial failure.
No workload rerun, owner financial operation or Live action required.

Why owner review is required: Security requirements RQ-7 and tools/security/README.md
state that the owner must review each registry diff before merge. General Git
authorization does not provide an exact identity classification decision.

Preparation evidence: Security policy tests on project Python3.12 ran53tests,
OK with4tool-dependent skips (no registry modification). The same policy CI job
passed on the published candidate. Initial system-Python3.9 invocation could not
import tomllib; this was an environment mismatch, not a source failure.

Candidate CI links:
- https://github.com/yukasung/tiewtrade/actions/runs/43643041139
- https://github.com/yukasung/tiewtrade/actions/runs/43643041111

No registry entry has been applied. Source and current candidate remain9f7c376.

Final initial-candidate results: CI43643041139 SUCCESS. Backend main5065Passed,
with isolated groups54/1/1/27/16Passed (reported separately to avoid overlapping
coverage claims). Browser groups36/2/8/7/6Passed, total59. Frontend/API contract/
Docker checks passed. Security43643041111 FAILURE only open secret identity above;
CodeQL all3languages, dependencies and policy jobs passed. Gate correctly blocked.
Owner exception question is pending; no approval inferred from elapsed time, general
merge instruction, successful local tests or other jobs. No merge performed.

## Owner decision and bounded implementation — 2026-11-15

Owner response: “A — อนุมัติ 1 exact false-positive exception และทำต่อจน merge”.
This decision supersedes the pending state in historical paragraphs above. Appended
exactly the proposed identity, secret/false_positive, with reason, exact approval and
commit/path/line evidence. All prior registry entries retained unchanged. Scanner,
severity, required gates and application source remain unchanged. Initial failed
Security run retained. Required final-candidate and post-merge CI will be followed.

Validation before publication: project Python3.12 policy suite ran53tests, OK with
4tool-dependent skips. Direct model/registry checks passed: exactly one append;
all previous entries byte-equivalent as JSON values; selected identity excepted;
unrelated high secret remains blocked and unknown severity remains Needs Triage.
Whitespace Passed. Configuration/evidence only, no application-source refactor gate.
