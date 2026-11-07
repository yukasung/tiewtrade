NC12 §22 W4 — Incomplete overall / integrated recovery Failed,2026-11-07.
Total206.839s; preflight passed. Real pg_dump/restore canonical data/RLS/grants checks
passed; domain replay21episodes,59evidence records,20checkpoints,18positions; one
expired legacy claim recovered without economic effects. Backup1816699bytes.
F16/F17 integrated recovery then timed out at60s, leaving its result Failed. Outer
campaign records Incomplete/TimeoutError; preserve both scopes and all raw evidence.
Source and target cleanup0connections/0advisory locks; candidate/runner unchanged.

Root cause identified from code and read-only DB evidence: recover() passes target
engines to publisher/parent readers, but f15.run_worker_process() constructs its own
ENGINE/ENGINE_SCAN using ambient source-role URLs. Thus parent waited for target
while worker serviced source. On source, the staged pending receipt and retry became
REJECTED/ORDER_SAFETY_UNAVAILABLE and retry attempt advanced to4; on target both
results remained absent and retry attempt2. These are isolated synthetic fixture
DBs, not user/live data. Never treat target non-progress as a need for larger timeout.
Evidence:source-versus-restored-worker-effects.json/restored-state-snapshot.json,
traceback atprofile_internal_restore.py recover andprofile_workload.py worker setup.

No final integrated pending/exit/retry/idempotency acceptance claimed. No source fix
or new run after this failed gate. W1§16/W2§20/overflow§20/shortW3§22 remain Passed;
4h Release and fullF17 dependencies/required CI remain pending. Next proposed§23
routes only W4 worker engines explicitly to target with unchanged factory defaults,
checks source unchanged, targeted real-DB/default-path regressions and one W4 rerun.
No repeated long workload is proposed.
