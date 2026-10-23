# Closure checkpoint — 2026-10-24

Owner changed repository visibility to Public, authorized the hosted CI rerun and
required checks, then requested closure documentation and exclusion of unused proof code.
This retires the self-hosted approach; it does not complete SC-01..14 or prove isolation.

## Verified remote state

- Repository: `yukasung/tiewtrade`, Public.
- [CI 39972554569 attempt 3](https://github.com/yukasung/tiewtrade/actions/runs/39972554569/attempts/3):
  completed/success on `51f0e2700e5c478e5b13b52f2cedcff2f6961d8d`, all six jobs passed.
- Attempts 1/2 remain historical billing failures; the original billing cause is
  undetermined. Attempt 3 demonstrates that this run is no longer blocked.
- `main` protection read back: six required GitHub Actions checks (app ID 15368),
  strict/up-to-date and enforce admins enabled; force push and deletion disabled.
  No additional reviewer requirement was enabled.
- No workflow, trigger, storage, budget or payment settings were changed.
  CI-05 trigger reduction and F-35 storage amendment were never implemented.

## Cleanup and PR scope

- See [cleanup-checkpoint.md](cleanup-checkpoint.md): VM/cache/runtime removed,
  Lima uninstalled; disabled `tiewtrade_ci` account/residual home remain because
  macOS denied archival. Do not claim complete host cleanup.
- Untracked `.ci/self-hosted/` and `backend/tests/gates/test_pf_probe.py` were moved
  recoverably outside the repository to
  `/Users/chainarongjaykeaw/Projects/TiewTrade/self-hosted-ci-archive.JtZ5BW/`.
  They are historical proof code, not active tools; paths in old evidence refer
  to the original experiment. No runtime private keys are included in this archive.
- Proposed PR scope is documentation and historical evidence only: mission NC-52,
  roadmap follow-up and this feature folder. No application/workflow/test code.
- Approval records and Failed/Partial/Not Run validation remain historical evidence.
  Requirements/plan are retired, not silently rewritten into a hosted implementation.
- No commit or push was performed. This is not a release or Live Trading approval.

## Verification scope

Documentation-only closure: check diff whitespace, local Markdown references and
parse retained JSON evidence. Application tests are not repeated: no runtime code
changed, and the hosted CI result above covers the unchanged main revision.
Remote state was re-read during closure; elapsed documentation work was not measured.
