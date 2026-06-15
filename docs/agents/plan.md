# Task Planning Agent Workflow

## Purpose

Create an implementation plan before coding a task.

Use this document by running:

```text
Read docs/agents/plan.md
```

## Required Context

Before planning, read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Planning Scope

Plan only the current task from `docs/status.md`.

Do not implement code.

Do not modify source files.

Do not start the next task.

Planning only.

## When To Use

Use this agent before implementation when the current task is:

- Medium complexity.
- High risk.
- Related to trading logic.
- Related to Binance integration.
- Related to database persistence.
- Related to recovery.
- Related to security.
- Related to bot lifecycle.

## Planning Checklist

## 1. Current Task Identification

Verify:

- Current Phase.
- Current Task.
- Task Scope.
- Task Deliverables.
- Task Dependencies.

## 2. Requirement Alignment

Verify alignment with:

- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`

## 3. Implementation Approach

Define:

- What will be created.
- What will be modified.
- What will not be touched.
- Which layer owns the logic.

Layers:

- Presentation Layer.
- Application Layer.
- Domain Layer.
- Infrastructure Layer.
- Persistence Layer.
- Shared Layer.

## 4. File Plan

List expected files:

- Files to create.
- Files to modify.
- Files to avoid.

## 5. Shared Abstraction Plan

Before implementation, identify whether reusable logic is needed.

Use:

- Shared Function.
- Utility Function.
- Helper.
- Shared Service.
- Base Class.

Avoid duplicate logic.

Avoid copy-paste implementations.

## 6. Risk Review

Identify risks:

- Architecture risk.
- Trading safety risk.
- Security risk.
- Database risk.
- Recovery risk.
- Testing risk.

## 7. Testing Plan

Define what must be tested:

- Functional tests.
- Unit tests.
- Integration tests.
- Recovery tests.
- Regression tests.

## 8. Implementation Boundaries

Confirm:

- Do not implement future tasks.
- Do not change product scope.
- Do not bypass architecture.
- Do not introduce unrelated features.

## Output

Create:

```text
docs/plans/plan-{task-name}.md
```

Include:

1. Summary
2. Current Task
3. Scope
4. Dependencies
5. Implementation Approach
6. File Plan
7. Shared Abstraction Plan
8. Risk Review
9. Testing Plan
10. Out Of Scope
11. Ready For Implementation Verdict

Verdict:

- READY
- READY WITH RISKS
- NOT READY

## Rules

Do not write source code.

Do not edit implementation files.

Do not start implementation.

Planning only.

## Execution Instructions

After reading this document:

1. Read all required context files.
2. Read `docs/status.md`.
3. Identify the current task.
4. Create an implementation plan for the current task only.
5. Save the plan in `docs/plans/`.
6. Return the readiness verdict.

Do not summarize this document.

Do not explain the workflow.

Execute the planning workflow.

End of workflow.
