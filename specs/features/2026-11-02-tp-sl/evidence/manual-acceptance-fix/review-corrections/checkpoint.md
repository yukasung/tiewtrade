# Post-review R1/R2 correction checkpoint

Date:2026-11-08 Asia/Bangkok. Owner instructed “แก้ไข” after read-only review.
Scope: fixes to High STOP stale-receipt finding and Medium missing exit quantity.
No backend/API/database contract or trading-rule change.

## R1 High — stale received STOP consumes a fresh click

Review reproduced persisted APPLIED hint with active USER cause: first normal
click performed1GET/0POST with no error; second click posted. This is unsafe for
MANUAL intents admitted after the old cutoff without resume.

Now resolve a persisted hint independently with an owner/mode-scoped read-only
query on mount. While resolving it, UI says Checking previous request and cannot
label its action a fresh STOP. Valid received receipts retire the recovered hint
without POST; receipt REQUEST_PENDING is durable acceptance, not STOPPED proof.
As with prior successful receipt handling, the next explicit normal STOP is a new
intent and uses a fresh UUID, even while USER remains active/no resume. Current
completion/progress remains from the normal server status query, never inferred
from receipt acknowledgement. No automatic POST from mount or query effects.
Unknown lookup errors preserve key/recovery action; exact404 keeps the same key
for explicit retry, allowing a delayed commit without a duplicate identity.
An invalid-key422 retires the malformed hint. Unreadable storage without a hint
still permits STOP. Old recovery updates cannot retire a newer unknown attempt;
existing owner/mode and mounted-scope guards retained.

## R2 Medium — actual queued exit quantity absent

Details now displays exit_quantity as Queued exit quantity independently of
allocation, current executable/covered quantity and exit_filled_quantity. Values
remain exact server strings through MarketValue, no client sizing/arithmetic.
Null/missing quantity is unavailable, never substituted from current allocation.
Partial fills and later metadata updates do not change the displayed queue fact.

## Targeted checks

64affected tests passed: KillSwitchControls19 + PaperTradingActivity15 +
PaperTradePage30. KillSwitch19 passed again after the test's async flush/lint fix.
Final typecheck and scoped ESLint passed; diff whitespace check passed.
Unchanged backend financial/RLS/concurrency proofs and the prior review's core66
remain in their original scope; no backend/real-DB financial campaign repeated.

New regressions cover active MANUAL/no-resume stale APPLIED receipt with normal
and failing storage; read-only recovery0POST, then one explicit normal click1POST
with fresh key. Unknown retry retains exact original identity and payload; old
recovery cache cannot clear a newer unknown key. Scope switching remains safe.
Existing persisted pending/APPLIED/missing tests now distinguish autonomous GET
resolution from explicit retry/new intent; no automatic new identity accepted.
Storage warning assertions scoped to Paper because both modes now read their own
hint on mount. Initial8failures reflected old on-click recovery selectors/setup;
they were retained as intermediate failures and adapted to the intended recovery
phase, keeping POST/key and owner-scope assertions. No safety criteria lowered.

Browser6scenarios passed on actual components with intercepted synthetic API:
STOP Thai/English × normal/blocked storage(4), each0automaticPOST then1fresh-key
POST for one normal click; EXITING Thai/English mobile375(2), queued0.99BTC remains
while allocation/executable metadata changes and filled0.5→0.8BTC. No owner session
or actual STOP/order submitted. Screenshots inspected; queue/filled labels readable.
First English harness run imported an unversioned duplicate i18n module during
Vite HMR and rendered Thai; runner fixed to import the component's exact module
URL. Scope and assertions unchanged. Initial lint require-await in a test fixed
with explicit microtask flush. Final checks passed.

## Runtime and pending gates

Local proxy health200, all four gates remain false. Read-only inspection observed
one USER/PAPER STOP APPLIED at07:40:19Z during the surrounding work interval; this
is not attributed to the agent or accepted as a new owner validation round.
Agent browser requests were intercepted in fresh contexts; no owner auth/session
was used. No protection requests in the inspected interval, no automatic repair,
trade, wallet reset or gate opening. Existing manual Failed remains historical.

R1/R2 corrections and affected validation complete locally. Per AGENTS.md64–65,
next requires owner instruction for refactor. Do not automatically refactor or
publish/commit/push/merge. Final required CI on the eventual published candidate,
F17 Batch/Release/dependencies remain pending; not Completed or merge-ready.


## Owner-authorized refactor completed

Owner requested refactor. [Final refactor/validation evidence](refactor-checkpoint.md)
supersedes the refactor-wait boundary above:64targeted tests and6affected browser
cases, lint/types passed. Prior manifests/results retained; current identities
updated. Next authorized Git publication/required CI; no Git action performed.
