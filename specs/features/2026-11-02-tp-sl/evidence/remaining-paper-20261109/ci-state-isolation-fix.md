# PR66 first CI — isolated mock state integration repair

Date:2026-11-09 Asia/Bangkok. PR66 publication task; no new product/profile decision.
Initial head5216d3b: [CI42648028344](https://github.com/yukasung/tiewtrade/actions/runs/42648028344)
Failed in backend main pytest:6failed/4,886passed/31deselected,5warnings.
All6 failures are the parameterized mocked parent-lifecycle shutdown regression.
Isolated protection/migration/fresh-global steps were Skipped after main failure;
not counted Passed. Frontend/API/container/config and browser42Passed. Security
[42648028318](https://github.com/yukasung/tiewtrade/actions/runs/42648028318)7/7Passed.
The duplicate push CI was intentionally Cancelled, separate from the PR result.

## Root cause and scoped correction

Starlette State.__setattr__ assigns self._state[key]=value. The test's
monkeypatch.setattr(app.state,"_state",{}) inserted a key into the existing state;
it did not replace its backing dictionary. In the full CI order, earlier real
lifespans left disposed engine references pointing at now-deleted fixture DBs.
The parent diagnostic loop consequently encountered real engines and tried to
reconnect, rather than using only the intended doubles. The isolated local65test
selection ran those mocked cases before real lifespans, concealing the dependency.
Traceback locates the attempt in parent_lifecycle's app.state engine loop.

Correct only the unit test: scoped monkeypatch of app.state to a fresh State(),
assert distinct state identity and preserve original state's entries. Original
state is restored by pytest monkeypatch teardown. All six original outcome/error/
disposal assertions remain. No production/diagnostic/runtime behavior, database
schema, money, workload, threshold, timeout or security registry changes.

## Evidence and continuation

Reordered local targeted selection so actual real-DB diagnostic cases run before
the mocked regressions, as in CI. Combined65Passed6.84s; scoped Ruff/format/mypy
Passed; generated fixture databases cleaned normally. Native State assignment
behavior independently reproduced in memory. No D20/W4 or full local suite rerun.
This is a related CI test-isolation correction within the authorized PR task;
it does not introduce a business/architecture/spec amendment or trading action.

Retain the first remote Failed and skipped stages as above; local success does
not replace required CI. Update the same PR and monitor the new final head. Old
immutable evidence blobs/exact exception bindings remain unchanged. No new PR,
exception, criterion waiver, automatic merge or release/completion claim.
