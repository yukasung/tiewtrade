# F17 evidence false-positive handling — proposal

สถานะ: **Proposed — Needs Owner Approval; no policy implementation authorized**
วันที่: 2026-11-07
Candidate: PR59, `0961f7893226ba1e1641e5138e46f78dbe50f6cf`

## Blocker and evidence

The unchanged secret scanner flags48118 new evidence occurrences locally:
47305 UUID values and813 SHA-256 values. They occur in synthetic request/idempotency
traces and candidate/query fingerprint records, not new production credentials.
Shape alone is not an authorization to suppress them. Keep the final remote result
as reported; this proposal does not turn a Failed/Incomplete scan into Passed.

Remote Security run42362300837 cancelled its secrets job at the15-minute limit;
the GitHub annotation confirms the timeout. No secrets manifest was produced and
the aggregate failed INVALID_POLICY_DATA. Thus the remote result is **Incomplete /
Failed gate**, not a completed scan proving48118 false positives. The shape counts
are from the separate local probe. Logs do not isolate scanner time from occurrence
resolution time; repeated per-occurrence Git/blame calls are a code-level lead,
not a measured root cause.

The current exact-occurrence registry is limited to256KiB. Expanding it with tens
of thousands of repeated per-occurrence entries would exceed that contract. No
folder/rule suppression, generic UUID/hex exemption or severity relaxation is allowed.

## Option A — recommended, requires security-spec amendment

Add an explicit owner-approved **immutable evidence manifest** for this fixed dataset
only. The local probe groups into39 immutable entries; the complete proposed list
is [proposed-evidence-bindings.json](evidence/recovery-20261106/proposed-evidence-bindings.json),
with all approvals explicitly PENDING. Each approved entry must bind the exact
commit, repository path, Git blob, scanner rule, observed count, explanation and
approval. Independently verify matches against the producing harness before use.
The UUID/checksum shape inventory is supporting evidence, never a general allow rule.

First add safe per-stage timings/counts and verify the source of the timeout on
bounded local inputs. Reuse/correct the existing occurrence mapping with batched or
cached immutable Git reads only after parity tests prove identical identities,
locators and failure behavior. Keep the15-minute job budget; do not extend it or
claim that the exception manifest alone resolves the timeout.

Keep Gitleaks scanning the complete candidate history and tracked tree. Resolve an
occurrence only when every approved binding matches. A changed blob, renamed path,
new finding or missing/invalid approval must remain blocked. Keep all existing
per-occurrence approvals, non-secret security gates and trading safety unchanged.
Preserve raw evidence and historical outcomes; do not rewrite published history.

Proposed contract: a versioned registry with entries containing `commit`, `path`,
`git_blob`, `rule`, `reported_matches`, `resolution=false_positive`, `reason`,
`approval` and `evidence`. Reject unknown/duplicate entries and malformed or
unapproved data. Bind this registry into the existing security configuration digest.
Deduplicate history/tree occurrences using existing occurrence identities before
checking the exact approved per-entry count; report resolved counts explicitly.
Neither path matching alone nor value shape alone can authorize resolution.

Option A is a proposed amendment to security requirements RQ-2/3/6/7 and §6.2,
the plan's exact secret exception registry contract, and validation V-05. Explicit
owner approval of A authorizes recording those amendments with the contract above,
then its implementation and checks as one checkpoint. Current F17 publication
approval alone does not cover this new contract. Any further scope/policy change
still requires its own approval.

Required checks: real credentials inserted into an approved evidence file must
change its blob and fail; renamed/copied files, changed counts/rules, missing or
tampered manifests must fail; new UUID-shaped credentials elsewhere must fail;
old exact approvals must still work. Verify scanner coverage and existing policy
failure-path tests, then rerun complete required CI on the new candidate. Stop and
report if actual secrets or further policy gaps are found. No merge/deploy/Live.

## Option B — retain the blocker

Keep current policy and the PR draft without adding exceptions. Code and workload
proofs remain available, but required Security cannot be called Passed and this
candidate cannot merge or close F17. Reconsider evidence publication separately.

No option is selected or implemented by writing this proposal. The draft is kept
local for owner review; no additional CI-triggering documentation commit is needed
merely to record this proposal or the current run result.
