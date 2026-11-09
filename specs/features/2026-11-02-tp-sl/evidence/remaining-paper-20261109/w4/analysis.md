# Current W4 integrated restore — 2026-11-09

Status: **Passed** on production de3bdcb plus pinned current harness.

Revision2 preflight Passed. Fresh source/target; real backup/restore canonical
data and RLS/grants match. Domain replay21episodes,59evidence records,20checkpoints,
18positions; one expired claim recovered in one round without economic changes.
F16/F17 internal recovery Passed: pending receipt identity, exact retry and exit
assertions passed. Source unchanged. Backup1,828,938bytes.
Campaign 145.858s including preflight; runner/support/source unchanged.
Cleanup0connections/0advisory locks in both source and target; after source process
exit no target source backends. No owner account/gate change, Live or Git action.

This closes the current20-owner integrated restore checkpoint only, not100-account/
4h or bot/notification/Live/full F17 validation. Retain historical results.
