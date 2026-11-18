# Local worktree reconciliation — 2026-11-18

สถานะ: Approved documentation reconciliation — owner instructed completion through publication and cleanup.

## Scope and preserved work

The nine dirty worktrees were compared against main `c243d13`. No additional production
implementation remains in their diffs: Picomatch manifests, lock, vendor archives,
security adapter, policy and exception bytes already match main. This change publishes
owner-approved workflow/stateless-session instructions and missing historical closure
evidence. It does not change trading behavior, source-policy acceptance or release gates.

The [inventory](inventory.json) records hashes and disposition for every non-private
changed/untracked file. Original per-worktree staged/unstaged binary patches, untracked
tar archives, branch heads and the detailed private inventory are retained in the local
`TiewTrade-local-backup-20261118-225946` directory, outside Git. The 9,610 private
validation artifacts (approximately 4 GB) and prototype harness snapshots stay there.
Do not run archived campaigns or interpret old Draft/Blocked snapshots as current status.

## Reconciled records

- CI feedback-time PR #67: original failed candidates remain recorded. Main CI and Security
  passed on `f7c94f5`; explicitly authorized manual-full run 43146837886 also passed.
  Restored evidence closes this feature's existing validation criteria without another run.
- F-17 scheduler PR #66: isolated diagnostic and same-SHA rerun evidence are retained with
  the earlier WebSocket failure. Postmerge CI 43193597428 and Security 43193597263 passed
  on `afb2adb`. Passing later runs does not establish the intermittent failure's root cause.
- F-17 endurance PR #76: CI 44122272269 passed on `d3c9eae`; Security 44122272392 failed
  on the then-current advisory. Preserve that failure. Later LP04 remediation/approved
  artifact-bound exception was merged in PR #77; chart diagnostics merged in PR #78.
- Latest baseline `c243d13`: CI 44336322663 and Security 44336322562 passed. This supersedes
  the publication-pending status, without changing historical failed runs or claiming
  the intermittent chart problem permanently fixed.
- MF-13 visual preparation and Live-form geometry diagnostic records are historical.
  They do not replace owner acceptance or authorize new financial actions.

[Verified GitHub runs](verified-runs.json) contain exact SHAs, conclusions and links read
back during reconciliation. F-17 remains **Pending Full Validation**: original capacity,
bot/notification, Live-adapter/recovery and owner-acceptance obligations are unchanged.

## Review and validation

Changes are documentation and sanitized JSON evidence only. Review checks current-main
preservation, owner-approved workflow scope, historical versus current statuses, local
links, JSON syntax, whitespace and absence of common credential formats. Required CI
and Security still apply to the final PR candidate and postmerge SHA. No workload,
private trace upload, app/session mutation or automated Live order is part of this task.

After successful publication, private archived work is closed as retained history;
clean up local branch/worktree references only when merged/pushed/CI requirements hold.
Do not delete archives or ignore files merely because the associated branch is old.

Local review completed: copied historical files had committed bases identical to current
main. Fixed stale current CI-feedback and Picomatch roadmap summaries, while retaining
failed runs in their evidence. New local links resolve; JSON parses; whitespace and
common-credential-pattern checks passed. No source refactor applies to this doc change.
Final candidate required CI/postmerge results will be reported with SHA/run links; no
recursive evidence-only PR is needed to report this documentation PR's own CI.
