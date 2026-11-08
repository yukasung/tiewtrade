# F19 publication browser recovery correction — 2026-11-08

Owner explicitly approved Option A in publication-stop-recovery-e2e-proposal.md.
Production code unchanged; only the affected browser scenario was adjusted.

Previous candidate19434bc: Security Passed; browser main20/catalog2/F16seven/
F17seven Passed; risk suite five Passed/one Failed at obsolete post-reload
same-key expectation. Backend still running at preparation.

Targeted evidence:
- STOP component19 Passed; scoped ESLint/typecheck and diff check Passed.
- Real-DB browser case Passed (11.9s), including UNKNOWN same-key POST retry200,
  same request/generation, second dropped ACK, read-only by-key GET after reload,
  no automatic POST, journal retirement, explicit new STOP distinct key/request
  and generation+1; existing post-cutoff fill/completion, Paper/Live isolation,
  unavailable Live execution, summary, keyboard, locale/mobile/error assertions.
- First local run Failed because the added assertion accidentally compared the
  mutable receipt state too: REQUEST_PENDING had advanced to APPLIED. Corrected
  to the immutable request/generation identity; no production behavior change.
- Isolated database tiewtrade_e2e_f19recover20261108, per-test fresh owner, no
  owner-account mutation or live exchange order. Screenshots alongside are test
  data; previous screenshots preserved. Temporary venv link removed.

Normal commit/push and one further CI round approved. No full CI pass is claimed
until all required jobs finish on the new SHA. No merge or F17 Completed claim;
remaining Batch/Release dependencies retained.
