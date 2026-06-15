# Review Agent Workflow

## Purpose

This document defines the standard review workflow for Codex when reviewing TiewTrade task implementations.

The review agent must verify that the implementation satisfies the current task only, follows the documented architecture, respects product decisions, and does not introduce future-scope behavior.

## Required Reading

Before reviewing any task, Codex must read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`
- `docs/task-report.md` when available

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Review Scope

Codex must identify:

- Current phase.
- Current task.
- Implemented scope.
- Expected deliverables from `docs/task-breakdown.md`.
- Files changed.
- Tests or checks performed.
- Any open issues from `docs/task-report.md`.

Codex must review the current task only.

Do not review or approve future-scope implementation as part of the current task.

## General Review Checklist

Verify:

- Current task only was implemented.
- Future tasks were not implemented.
- `docs/product-decisions.md` was not violated.
- Task scope matches `docs/task-breakdown.md`.
- Architecture boundaries were respected.
- Database ownership and persistence rules were respected.
- No duplicate logic was introduced.
- Reusable services were used where appropriate.
- Layers remain separated.
- Errors are handled.
- Logs avoid sensitive data.
- Recovery behavior is considered where relevant.
- Tests or manual verification steps are documented.
- `docs/task-report.md` was created or updated.
- `docs/status.md` was updated when the task was completed.

## Shared Abstraction Review

Verify:

- No duplicate logic.
- No repeated calculations.
- No repeated validation.
- No repeated Binance API handling.
- No repeated configuration handling.
- No repeated logging logic.
- No repeated recovery logic.

Verify proper use of:

- Shared Function in `src/shared/functions/`.
- Utility Function in `src/shared/utils/`.
- Helper in `src/shared/helpers/`.
- Service in `src/shared/services/`.
- Base Class in `src/shared/base/`.

If duplicate business logic exists:

- Verdict must not be PASS.
- Findings must explain where duplication exists.
- Findings must recommend the correct shared abstraction.

## TiewTrade Specific Review Checks

### Trading Architecture

Verify:

- Bot lifecycle follows `docs/architecture.md`.
- One Account = One Bot.
- Stop Bot does not close positions.
- Spot and Futures behaviors follow `docs/product-decisions.md`.
- Recovery flow follows `docs/user-flow.md`.

### Trading Safety

Verify:

- No duplicate order creation.
- Idempotent order handling.
- Position state consistency.
- Recovery state consistency.
- Risk validation exists before bot start.

### Binance Integration

Verify:

- Spot adapter is isolated from Futures adapter.
- Exchange errors are handled correctly.
- API failures do not crash the application.
- Account validation is performed before trading.

### License Compliance

Verify:

- Offline license model is respected.
- No online activation dependency is introduced.
- Invalid license blocks bot startup.

### Documentation Compliance

Verify:

- `docs/status.md` is updated.
- `docs/task-report.md` is created.
- Task scope matches `docs/task-breakdown.md`.
- No future tasks are implemented.

## Review Output

Create:

- `docs/reviews/review-{task-name}.md`

The review report and response must include:

- Verdict.
- Summary of what was reviewed.
- Files reviewed.
- Findings ordered by severity.
- Architecture compliance notes.
- Database compliance notes.
- Product decision compliance notes.
- Shared abstraction compliance notes.
- Testing or verification gaps.
- Required fixes before task completion.

Verdict:

- PASS
- PASS WITH MINOR FIXES
- FAIL

If no issues are found, state that clearly and mention any remaining residual risk.

## Approval Rule

Codex must not approve a task if:

- The implementation violates `docs/product-decisions.md`.
- The implementation includes future-scope work.
- The current task deliverables are incomplete.
- Major duplicate business logic exists.
- Sensitive data can be logged or persisted unsafely.
- Trading behavior can create duplicate orders.
- Bot startup can bypass license, account, configuration, or risk validation.
- Stop Bot can close or liquidate positions unexpectedly.
- Required documentation updates are missing.

## Execution Instructions

After reading this document:

1. Read all required context.
2. Execute the review workflow described in this document.
3. Perform all required review actions.
4. Create all required reports.
5. Update all required files only when the review workflow explicitly requires it.
6. Return the review verdict.
7. Stop when review is complete.

Review-specific execution:

1. Identify the latest implementation from `docs/status.md` and `docs/task-report.md`.
2. Identify changed files for the latest implementation.
3. Review changed files only.
4. Verify task scope, architecture, database, product decision, security, trading safety, and shared abstraction compliance.
5. Create `docs/reviews/review-{task-name}.md`.
6. Return the review verdict.
7. Stop after the review report is created.

Do not summarize this document.
Do not explain the workflow.
Execute the review.
