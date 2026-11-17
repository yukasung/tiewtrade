# OBS-05 M1 refactor — 2026-11-17

Owner authorized refactor. Extracted private `_save_cleanup_failure` to separate evidence
publication from task/resource cleanup. Existing save callback, exception priority,
cancellation semantics, error order and Failed/Incomplete behavior remain unchanged.
No production changes or new dependencies.

40 affected prefix regressions passed. Ruff/format/mypy passed for the changed module.
Prior 170-test real-PG M1 evidence remains valid: this extraction changes no transaction,
locking or database lifecycle. Proceed to approved one preflight and OBS-05 diagnostic.
Campaign result pending; no commit/push/CI/merge.
