# PR63 scoped publication correction — 2026-11-08

Owner explicitly approved Option A for NC-F17-SEC-01: six exact checksum
false-positive exceptions, tests, normal commit/push and one replacement CI round.

- Initial candidate: f5b3449172b4ba1b216bf41ce9e099e9445cb31a.
- Initial [Security](https://github.com/yukasung/tiewtrade/actions/runs/42461082621):
  Failed, six public generated-source checksum occurrences; retained unchanged.
- Initial [CI](https://github.com/yukasung/tiewtrade/actions/runs/42461082591):
  E2E Failed at F16 obsolete table selector; backend still running at preparation.
  F17/later E2E steps were skipped, not Passed.
- Registry adds exactly the six approved identities. All prior entries unchanged;
  six manifest fingerprints match immutable candidate and worktree source bytes.
  Existing policy still blocks an unapproved High finding. Scanner/rules unchanged.
- Security unittest discovery under project Python: 47 tests, OK, 4 skipped by
  existing conditions. Initial system Python 3.9 invocation could not import
  tomllib; rerun with project Python passed, no code change for that environment.
- F16 browser regression: 1 passed (16.1s), real isolated PostgreSQL database
  tiewtrade_e2e_f17cifix20261108, production API/engine with existing test policy.
  MARKET BUY/SELL, LIMIT partial/cancel, exact server-state assertions and mobile
  overflow assertion unchanged. Only DOM selector follows unified activity table.
- Scoped ESLint and frontend typecheck passed. git diff --check passed.
- Screenshots alongside this checkpoint come from that isolated F16 test, not the
  owner account. Prior F16 historical screenshots preserved. Temporary venv link
  removed and isolated test database dropped after confirming zero connections;
  no shared environment installation or owner data mutation.

Replacement required CI remains pending until observed on the correction SHA.
No merge or F17 Completed claim; existing Release dependencies remain pending.
