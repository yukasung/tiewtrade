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

The review response must include:

- Approved or Changes Required.
- Summary of what was reviewed.
- Findings ordered by severity.
- Architecture compliance notes.
- Database compliance notes.
- Product decision compliance notes.
- Testing or verification gaps.
- Required fixes before task completion.

If no issues are found, state that clearly and mention any remaining residual risk.

## Approval Rule

Codex must not approve a task if:

- The implementation violates `docs/product-decisions.md`.
- The implementation includes future-scope work.
- The current task deliverables are incomplete.
- Sensitive data can be logged or persisted unsafely.
- Trading behavior can create duplicate orders.
- Bot startup can bypass license, account, configuration, or risk validation.
- Stop Bot can close or liquidate positions unexpectedly.
- Required documentation updates are missing.
