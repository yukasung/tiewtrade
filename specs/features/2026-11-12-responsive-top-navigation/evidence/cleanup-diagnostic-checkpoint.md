# Cleanup diagnostic checkpoint

วันที่: 2026-11-14 Asia/Bangkok
สถานะ: **Local diagnostic Passed; original CI failure unresolved**
ฐาน: bfa9cd5. Changes remain uncommitted.

## Change

Only test_profile_resources.py: capture the held connection PID via read-only SELECT; append phase, observer PIDs, held PID and existing cleanup result to assertions on failure. No query text/credentials/account data in evidence. Existing negative leak assertions,5s cleanup budget and production code unchanged. The additional diagnostic query can affect timing; local success is not proof that the original failure was harmless or fixed.

## Results

- Fresh isolated database exact test:1 Passed in11.08s.
- Same resource file including neighboring pool inventory/return tests:10 Passed in10.74s. No failure evidence emitted.
- Ruff check/format: Passed. Targeted mypy with MYPYPATH=src: Passed after adding held_pid:int. Initial file-only mypy had source-resolution errors; corrected invocation identified one missing annotation which was fixed.
- Only type annotation changed after test success; no runtime retest needed.
- Private logs: frontend/test-results/navigation-publication/cleanup-exact.log and cleanup-neighbors.log.
- Isolated DB had0 connections before cleanup. Owner database/services untouched.

## Conclusion and next step

The failure did not reproduce in exact or neighboring tests. Cannot distinguish connection leak, shared-suite interference or timing from current evidence. PR70 CI remains Failed; no rerun, commit/push, merge or retarget was done. Next proposal: publish this diagnostic and run one candidate in the same full CI context, retaining5s and all leak checks; requires owner approval because this diagnostic plan stops at local report.


## Approved publication outcome

Owner authorized one diagnostic CI candidate. Committed/pushed as fec9260; CI43527203085 and Security43527203035 Passed. Backend5006 stages total Passed. Prior uncommitted/no-rerun statements describe the local checkpoint only. No failure-only output emitted; this does not establish the original root cause. Stop/report checkpoint reached, no additional investigation or acceptance change performed. Next: owner-requested navigation code review and visual acceptance before merge.
