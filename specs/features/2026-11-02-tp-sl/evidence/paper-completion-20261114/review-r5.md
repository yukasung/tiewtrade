# Consolidated review and bounded corrections — 2026-11-15

สถานะ: Review findings corrected; owner refactor instruction and final publication gates pending.

Reviewed task diff, callers and approved remaining-Paper acceptance/amendments,
including financial owner-lock/snapshot checks, accounting defaults, RLS/session
boundaries, API read-only composition, cancellation evidence and campaign cleanup.
No Critical/High finding identified in this review. No trading rules or production
code changed during these corrections. PostgreSQL remains authoritative; diagnostic
in-memory buffers are bounded, temporary evidence rather than business/session state.

## Findings resolved

| Severity | Location | Problem / impact | Correction |
|---|---|---|---|
| Medium | `profile_commit_observation.py`, `observe_commits.begin` | Invalidated connection metadata access could mask primary failure/cancellation, misleading diagnostic classification. | Preserve primary exception and type-only note; metadata-only failure still raises, no false commit confirmation; hooks restored. |
| Medium | `profile_diagnostics.py`, `observe_workload` | Observer teardown could replace original cancellation. | Preserve original cancellation like other primary failures, with sanitized secondary error type. |
| Medium | `remaining_paper_campaign.py`, manifest authorization | Revised100/burst5 labels inherited stale numeric approval prose. | Bind known profile to its approved document; effective criteria stay in structured fields. |
| Low | `remaining_paper_campaign.py`, CLI validation | W2-only burst5 accepted unsupported phases until after preflight, or incorrectly labeled CONTROLLED20. | Reject unsupported pairs before output/preflight; valid legacy configurations unchanged. |

## Verification and evidence reuse

139 targeted tests Passed in7.18s, including real PostgreSQL commit/rollback evidence,
metadata-only failure, primary exception/cancellation, teardown failure, hook restoration,
profile authorization and CLI rejection. No skipped cases. Ruff check, format check and
mypy Passed for all6 affected files; `git diff --check` Passed. Temporary test DB cleaned
normally by launcher. No owner/Live operations or timed workload rerun.

[Source bridge](review-r5-source-bridge.json) compares all1017 recorded paths against
R4 burst evidence: only the6 named harness/test files changed; every backend/src path
is unchanged. Completed workload evidence remains valid for its stated profile and
scope; historical inventories/manifests/results remain immutable.

Correction notice: earlier revised100 and burst5 manifests contain inaccurate human
`authorization` prose (old250ms or10/s). Use their explicit selected profile, structured
configuration/results and approved timing amendment to interpret them. This notice
does not replace Failed results or expand their scope. Future manifests use corrected
profile-bound document references. Read [final local checkpoint](final-checkpoint.md)
with this source bridge; its1017/1017 equality refers to the pre-review R4 checkpoint.

## Remaining gates and risks

Local internal20 acceptance passed under the explicitly approved profile; old20W2 and
100-account failures remain Failed. Full100/4h Release, bot/notification/Live dependencies,
opening/owner acceptance and final candidate required CI remain pending. W3 short fault
observations do not establish all-owner per-fault recovery or four-hour endurance.
F17 is not Completed. No commit/push/PR/merge performed.

Next: await explicit `refactor the code` instruction per AGENTS.md; after authorized
refactor validate affected evidence, then follow owner-directed Git/required CI gates.
