# F-17 remediation refactor and local-readiness checkpoint

Date:2026-11-08 Asia/Bangkok. Owner explicitly requested `refactor the code`.

Refactor is limited to `KillSwitchControls.tsx` and its tests. Extracted the existing
receipt/status recovery into recoverActiveStop; centralized the repeated mounted
scope assertion; reused client/render setup in the affected test file. Request
ordering, branch outcomes, UUID lifecycle, unknown-result behavior and account
scope guards are unchanged. No financial/backend/runtime business logic changed.

Affected STOP suite16passed in1.33s; frontend typecheck and scoped ESLint passed.
Existing scoped core/DB/API/protection/browser evidence remains applicable to the
unchanged contracts; no full suite or timed workload was repeated for confidence.

After refactor, continued approved validation without another permission gate.
Verified owner local target and current-main compatibility of the existing UI
worktree; stopped only the verified services on owner ports5173/8000 and their
three chart-worktree Paper workers. The previous market-data process was absent.
Started API/market-data/frontend/wallet/risk/order from this reviewed candidate,
retaining the same database/Redis15/signup/dev keys. No migration or extra infra.
Worker launcher receives only engine/scan roles; API launcher clears ambient
TIEWTRADE configuration before applying its explicit API values and stop authority.

Health/API proxy200, frontend served recoverActiveStop, process CWDs matched this
worktree, price/execution feeds had live leases, and risk reached READY without
latch/replay pending. Publication watermark advanced2806→2946. Financial facts
and protection records(excluding mutable scheduling time) matched the private
pre-restart digests across8selected tables/data sets. Owner account data was not reset.

## Manual-profile blocker

Actual account use is MANUAL. Existing F19 source/spec permit resume only for BOT,
while F17 MF-13's approved manual wording asks the owner to STOP then resume.
No user action phase was started by the agent. Do not change business rules or
reinterpret the approved criterion as Passed. See the concrete
[clarification proposal](../../manual-profile-clarification.md).

Closed publication again; financial/admission/protection remained off throughout.
All four gates are off. Candidate and fresh market-data service remain local;
compatible API stop authority is on, but no STOP/BUY/SELL was submitted by the agent.
Private operator receipt retains exact process/session identities and digest proof;
no credentials or account-row payloads were copied to repo evidence.

Refactor/checks complete. MF-13 is Pending Clarification / Not Run on the replacement
owner round; original Failed remains. Required remote CI/Git publication and full
Release dependencies remain pending. Next needs owner A/B decision from the linked
proposal; this is not another implementation/refactor approval request.


## Owner decision — 2026-11-08

Owner approved option A. MF-13 mapping updated to MANUAL STOP/completion and
expected unavailable resume, with existing isolated BOT evidence retained in its
original scope. No runtime/source change or automated owner action. Health200 and
all four Paper flags false were checked after approval. Replacement remains
Not Run until the owner performs the UI round. No additional tests are required
for this documentation-only mapping; previous passing evidence remains valid.
