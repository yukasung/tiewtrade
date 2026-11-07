NC12 §18 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V2 changes
W2 only to10commands/s/1200s with120cycles-per-owner/12000commands unchanged.
Completion allowance1260s; required book inputs12000 at10Hz. V1/defaults, money,
worker/pool/coordinator/retry and other phase definitions unchanged. Actual V2 name
is forwarded to worker subprocesses and recorded in manifests/timing revision.
Tests233 passed8.77s;5 profile rechecks passed0.31s after test typing correction.
Scoped Ruff/format passed5repo files and private runner; mypy passed5files. Private
runner retains its pre-existing broad cleanup exception with BLE001 excluded only
for that file. Production source hashes unchanged; prior safety evidence remains
valid. W1§16 passing evidence reused only for unchanged assertions. All earlier
Failed/Incomplete runs retained. No§17 diagnostic added or executed.

Next: one approved fresh-DB V2 W2 withpreflight (~25–30min including20min measured),
then overflow/W3/W4 conditional on passing each gate. No repeated W1/D20. A failed/
incomplete gate stops without retry. Internal pilot and F17 remain open pending gates.
