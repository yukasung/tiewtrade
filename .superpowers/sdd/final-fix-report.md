# DEV-121 Final Fix Report

## TDD evidence

- RED: `env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/unit/test_ci_workflow.py -q` returned `1 failed, 3 passed in 0.01s`; `test_verify_workflow_targets_main_without_duplicate_branch_pushes` failed because the complete trigger block lacked `types: [opened, synchronize, reopened, edited]`.
- GREEN: the same command returned `4 passed in 0.01s` after the minimal workflow change.

## Files changed

- `.github/workflows/verify.yml`
- `tests/unit/test_ci_workflow.py`
- `docs/superpowers/specs/2026-07-27-ci-verification-workflow-design.md`
- `docs/superpowers/plans/2026-07-27-ci-verification-workflow.md`

## Static checks

- Focused Ruff lint: passed.
- Focused Ruff format check: passed after formatting `tests/unit/test_ci_workflow.py`.
- `git diff --check`: passed.
- `git diff --check main HEAD`: passed against the final commit.

## Commit

- `fix: cover retargeted pull requests in CI`

## Self-review

- The workflow now runs after a Pull Request is retargeted to `main` through the `edited` event.
- Contract tests assert complete trigger, permission/job-environment, setup/installation, verification-sequence, and exact `BASE_SHA` YAML blocks without adding dependencies.
- No production module, docs-site, dependency, secret, or Binance-related file changed.

## Remaining external gate

GitHub Actions has not run because this branch has not been pushed. User permission is required before push; keep DEV-121 `In Progress` until the remote run passes.
