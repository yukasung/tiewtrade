# Scoped harness review findings — fixes and affected validation

Date:2026-11-09 Asia/Bangkok. Owner instructed “แก้ไข” after the read-only review.
Status: **Four reviewed findings fixed; affected validation Passed; await owner refactor instruction**.
Production base de3bdcb unchanged. No production/domain/API/migration/dependency edits.

## Fixes

1. D20 and W4 record workload_status independently. A proven Failed (nonzero phase
   outcome or assertion failure) remains Failed if cleanup/identity/budget evidence
   is also incomplete. Cleanup observations/errors remain separate. An otherwise
   passed phase with bad cleanup is still Incomplete, never Passed. Primary
   assertion exceptions are preserved, not replaced by secondary cleanup errors.
2. Failed cleanup identity validation preserves only allowlisted count/time and
   backend PID/role/state/type/transaction fields with error_type. Null/missing or
   inconsistent identity remains rejected; raw extra fields/query/private values
   are not copied. No retry, waiting or resource exemption introduced.
3. Diagnostic parent cleanup attempts intake shutdown and every engine disposal,
   even if quiescence/snapshot/disposal fails. Secondary cleanup failures are kept
   as exception-type notes; an original body error/cancellation remains primary.
   No observer failure can skip the remaining four engines as in the reproduced case.
4. Diagnostic source change now records Incomplete/CandidateChanged and returns1;
   unchanged observation returns0/ObservationComplete. Observation completion is
   separate from workload/resource acceptance.

## Validation

New regression file15cases covers Failed+bad-cleanup for both runners, passed+
bad-cleanup, assertion exception identity, rejected snapshot retaining PID without
private fields, quiescence/intake/snapshot/dispose/body/cancellation failures and
changed/unchanged diagnostic source. No timed workload or actual trading requests.

Affected combined selection: **42passed in6.36s**:

- `test_remaining_paper_review_regressions.py`15
- `test_remaining_paper_cleanup_diagnostic.py`5 (including real-DB interruption cases)
- `test_remaining_paper_cleanup_identity.py`17 (including actual held-backend rejection)
- `test_remaining_paper_campaign.py`5

Ruff/check, format/check and MYPYPATH=src scoped mypy Passed4files (three harness
modules plus new regression file). Initial strict-type/import/format issues were
corrected before final checks; no check suppressed. Generated test source/template/
clones removed by existing isolated fixtures; launcher confirmed source removal.
Source hashes are in [review-fix-source-manifest.json](review-fix-source-manifest.json).
No commit/push/PR/merge or Live/operator gate action.

## Prior evidence and next checkpoint

The [D20/W4 passing receipt](identity-replacement-checkpoint.md), original first
D20 Incomplete and non-reproducing diagnostic remain historical results on their
recorded source. These fixes affect error handling/evidence/diagnostic teardown;
production financial/runtime and workload parameters/measurement/thresholds are
unchanged. No D20/W4 rerun was necessary or authorized to verify these simulated
failure paths. This checkpoint does not label past campaigns as executed on the
new harness bytes or claim new current-harness required CI.

Findings fixed and affected validation complete. Per AGENTS.md, ask owner whether
to `refactor the code` and wait before starting that step. Do not automatically
refactor, create a new review loop, publish or run more campaigns. F17 remains
Pending Full Validation: B/manual/opening/original100-account/4h/bot/notification/
Live obligations unchanged. No whole-feature Ready for Code Review/Completed claim.
