# TiewTrade - Codex Commands

## Purpose

Lightweight command launcher for TiewTrade workflows.

Detailed workflow rules live in the agent files:

- `docs/agents/plan.md`
- `docs/agents/implement.md`
- `docs/agents/review.md`
- `docs/agents/test.md`
- `docs/agents/security.md`
- `docs/agents/refactor.md`
- `docs/agents/explain-code.md`
- `docs/agents/task-complete.md`

## Project Rules

Always follow:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

Do not implement future tasks.

When documents conflict, `docs/product-decisions.md` is authoritative.

## Start Session

Command:

```text
Read docs/status.md
```

Purpose:

Summarize:

- Current Phase
- Current Task
- Completed Tasks
- Remaining Tasks
- Recommended Next Action

## Plan Task

Command:

```text
Read docs/agents/plan.md
```

Purpose:

Create implementation plan for current task.

## Implement

Command:

```text
Read docs/agents/implement.md
```

Purpose:

Implement current task.

## Review

Command:

```text
Read docs/agents/review.md
```

Purpose:

Review latest implementation.

## Test

Command:

```text
Read docs/agents/test.md
```

Purpose:

Execute testing workflow.

## Security

Command:

```text
Read docs/agents/security.md
```

Purpose:

Execute security review.

## Refactor

Command:

```text
Read docs/agents/refactor.md
```

Purpose:

Execute refactor workflow.

## Explain Code

Command:

```text
Read docs/agents/explain-code.md
```

Purpose:

Explain code added or modified in the latest task and generate explanation report.

## Complete Task

Command:

```text
Read docs/agents/task-complete.md
```

Purpose:

Verify task completion.

## Full Workflow

Command:

```text
Read docs/agents/plan.md
↓
Read docs/agents/implement.md
↓
Read docs/agents/review.md
↓
Read docs/agents/test.md
↓
Read docs/agents/security.md
↓
Read docs/agents/explain-code.md
↓
Read docs/agents/task-complete.md
```

## Project Status

Command:

```text
Read docs/status.md
```

Purpose:

Summarize:

- Current Phase
- Current Task
- Completed Tasks
- Remaining Tasks
- Open Issues
- Recommended Next Task

## Generate Next Task

Command:

```text
Read docs/task-breakdown.md
Read docs/status.md
```

Purpose:

Generate implementation prompt for the next task only.

## Architecture Audit

Command:

```text
Review:

- docs/architecture.md
- docs/database.md
- docs/product-decisions.md
```

Purpose:

Identify:

- Architecture violations
- Database violations
- Product decision violations
