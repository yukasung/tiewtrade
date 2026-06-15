# Task Completion Agent Workflow

## Purpose

Verify that a task is truly complete before moving to the next task.

Use this document by running:

Read `docs/agents/task-complete.md`

## Required Context

Before marking a task complete, read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

Read latest reports:

- `docs/task-report.md`
- `docs/reviews/*`
- `docs/testing/*`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Completion Scope

Review only the current task.

Do not start the next task.

Do not implement new features.

Completion verification only.

## Required Completion Checklist

A task cannot be marked COMPLETE until all checks pass.

## 1. Implementation Verification

Verify:

- Task scope fully implemented.
- Deliverables completed.
- No incomplete placeholders.
- No TODO items that block functionality.

Check:

- Files created.
- Files modified.
- Expected outputs.

## 2. Architecture Verification

Verify:

- Implementation follows `docs/architecture.md`.
- Layer boundaries respected.
- No architecture violations.
- No shortcut implementations.

Check:

- Presentation Layer.
- Application Layer.
- Domain Layer.
- Infrastructure Layer.
- Persistence Layer.

## 3. Database Verification

Verify:

- Database design follows `docs/database.md`.
- Entity ownership respected.
- Relationships respected.
- No schema shortcuts.

## 4. Product Decision Verification

Verify implementation follows:

- `docs/product-decisions.md`

Examples:

- One Account = One Bot.
- Stop Bot does not close positions.
- Offline License File.
- Spot and Futures support.

No decision violations are allowed.

## 5. Code Review Verification

Verify review completed.

Required file:

```text
docs/reviews/review-{task-name}.md
```

Review verdict must be:

- PASS
- PASS WITH MINOR FIXES

FAIL is not allowed.

## 6. Testing Verification

Verify testing completed.

Required file:

```text
docs/testing/test-{task-name}.md
```

Testing verdict must be:

- PASS
- PASS WITH MINOR ISSUES

FAIL is not allowed.

## 7. Security Verification

Verify security review completed.

Required file:

```text
docs/reviews/security-{task-name}.md
```

Security verdict must be:

- PASS
- PASS WITH MINOR FIXES

FAIL is not allowed.

## 8. Documentation Verification

Verify:

- `docs/task-report.md` created.
- `docs/status.md` updated.
- Documentation remains accurate.

Check:

- Current task status.
- Completed task list.
- Next task.

## 9. Trading Safety Verification

Verify, if applicable:

- Trading behavior preserved.
- No duplicate orders possible.
- No duplicate bot instances possible.
- Recovery behavior preserved.
- Risk validation preserved.

## 10. Open Issues Verification

Verify:

- Open issues documented.
- Known limitations documented.
- Risks documented.

## Completion Decision

If all checks pass, mark task:

```text
COMPLETE
```

Update:

```text
docs/status.md
```

Move task from:

```text
In Progress
```

to:

```text
Completed Tasks
```

Update:

```text
Next Task
```

## Completion Report

Create:

```text
docs/completion/task-complete-{task-name}.md
```

Include:

1. Summary
2. Scope Delivered
3. Files Created
4. Files Modified
5. Review Result
6. Testing Result
7. Security Result
8. Open Issues
9. Risks
10. Recommended Next Task
11. Final Verdict

Verdict:

- COMPLETE
- NOT COMPLETE

## Rules

Do not implement fixes.

Do not refactor code.

Do not start the next task.

Completion verification only.

## Completion Rule

A task is complete only when:

- Implementation completed.
- Review passed.
- Testing passed.
- Security passed.
- Documentation updated.
- Status updated.

End of workflow.
