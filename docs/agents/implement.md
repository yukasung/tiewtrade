# Implementation Agent Workflow

## Purpose

This document defines the standard implementation workflow for Codex when working on TiewTrade tasks.

The implementation agent must use this workflow before, during, and after every implementation task.

## Required Reading

Before implementing any task, Codex must read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Before Implementation

Codex must identify and confirm:

- Current phase.
- Current task.
- Current task status.
- Task scope.
- Task deliverables.
- Task dependencies.
- Whether dependencies are complete.
- Whether the requested work belongs to the current task.

Codex must not start implementation if:

- The task is not the current task.
- Required dependencies are incomplete.
- The work belongs to a future task.
- The work violates `docs/product-decisions.md`.
- The scope is unclear enough to risk implementing the wrong behavior.

## Implementation Rules

Codex must:

- Implement current task only.
- Do not implement future tasks.
- Follow `docs/architecture.md`.
- Follow `docs/database.md`.
- Follow `docs/product-decisions.md`.
- Avoid duplicate logic.
- Use reusable services when appropriate.
- Keep layers separated.
- Keep implementation aligned with the documented technology stack.
- Preserve existing user work.
- Avoid unrelated refactors.

Codex must not:

- Add future-scope features.
- Add multiple-bot behavior for Version 1.
- Add online license activation for Version 1.
- Add strategy builder behavior.
- Add manual trading behavior outside bot controls.
- Store raw API keys or secrets in SQLite.
- Store sensitive license data in logs.
- Call Binance directly from UI code.
- Put persistence logic directly inside UI code.

## Layering Rules

Implementation must respect the layered architecture:

- Presentation layer handles PySide6 screens, view models, and user interaction.
- Application layer coordinates use cases and workflows.
- Domain layer owns business rules, bot state, strategy decisions, risk rules, and trading concepts.
- Infrastructure layer owns Binance, secure storage, OS integration, and external adapters.
- Persistence layer owns SQLite repositories and local durable state.
- Cross-cutting services own logging, diagnostics, configuration, and shared policies.

Dependencies must not flow from lower-level domain logic into UI widgets.

## Task Scope Verification

Before writing code, Codex must compare the current task against `docs/task-breakdown.md`.

The implementation plan must answer:

- What task is being implemented?
- What deliverables are required?
- What files or modules are likely affected?
- What is explicitly out of scope?
- What future tasks must not be touched?
- What risks exist for this task?

## Quality Requirements

Every implementation must consider:

- Error handling.
- Logging.
- Configuration behavior.
- Recovery behavior where applicable.
- Security and sensitive data handling.
- Testability.
- User-facing simplicity.
- Non-technical user expectations.

## After Implementation

After implementation, Codex must create:

- `docs/task-report.md`

The task report must include:

- Completed work.
- Files changed.
- Technical decisions.
- Product decision compliance.
- Architecture compliance.
- Database compliance.
- Tests or checks performed.
- Open issues.
- Next task.

Codex must also update:

- `docs/status.md`

The status update must reflect:

- Completed task.
- New current task.
- Updated phase if applicable.
- Remaining tasks.
- Risks.
- Open issues.

## Review Checklist

Before considering a task complete, Codex must verify:

- Current task only was implemented.
- Future tasks were not implemented.
- `docs/product-decisions.md` was not violated.
- Architecture boundaries were respected.
- Database ownership and persistence rules were respected.
- No duplicate logic was introduced.
- Reusable services were used where appropriate.
- Errors are handled.
- Logs avoid sensitive data.
- Recovery behavior is considered where relevant.
- Tests or manual verification steps are documented.

## Review Handoff

Before considering a task complete, Codex must run the separate review workflow defined in:

- `docs/agents/review.md`

The implementation task is not complete until the review workflow has no blocking findings.

## Completion Rule

A task is not complete until:

- Implementation is finished.
- Review checklist is satisfied.
- `docs/agents/review.md` has been applied.
- `docs/task-report.md` is created.
- `docs/status.md` is updated.
- Any remaining open issues are documented.
