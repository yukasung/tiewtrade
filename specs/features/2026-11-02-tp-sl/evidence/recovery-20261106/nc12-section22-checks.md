NC12 §22 implemented/checked,2026-11-07. Retired generations retain raw native
counters as informational after declared intermediate dispose; live pools still
require native bounds/configuration and every generation's event-tracked active/
peak borrow bounds remain binding. Retired weakref loss with pending returns is
recorded as pending, never waived at quiescence. Final zero-return/inventory/error
criteria unchanged; unexpected live pool loss and capacity mutation still fail.

Real-DB regression holds2loans across dispose, observes nativecheckedout=-1 while
one event-tracked loan remains, then returns both and proves oldpool GC without
observer retention. Simulated missing-native-view cases keep real DB loans and
checkin callbacks; returned passes, deliberately unreturned fails. Live pool loss/
retired configuration mutation and prior API/worker/disconnect/cancellation tests
pass. Initial2failures were reused nonempty DB and double-cleanup of a closed loan;
fixed test cleanup and used a fresh isolated test DB, preserving initial logs.
Final88targeted cases passed14.17s; scoped Ruff/format/mypy passed2files. Production
source unchanged and prior applicable financial/safety proofs retained.

Next: one approved fresh-DB PAPER_INTERNAL20_V3 short W3, same30min/3000commands/
7faults and§19provenance (~35–45min total), then W4 only on passing. Reuse W1/W2/
overflow. Earlier incomplete W3 and all Failed results retained;4h Release remains
Pending Full Validation. No criteria/production/Git/deploy change or automatic retry.
