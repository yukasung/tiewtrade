# TiewTrade - Codex Commands

## Purpose

This file provides simple shortcut commands for working with Codex.

Detailed workflows are defined in:

- `docs/agents/implement.md`
- `docs/agents/review.md`
- `docs/agents/test.md`
- `docs/agents/security.md`
- `docs/agents/refactor.md`
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

Follow current task scope only.

When documents conflict, `docs/product-decisions.md` is authoritative.

## Start Session

```text
Read docs/status.md

Summarize:

- Current Phase
- Current Task
- Completed Tasks
- Remaining Tasks
- Recommended Next Action
```

## Implement

```text
Read docs/agents/implement.md
```

## Review

```text
Read docs/agents/review.md
```

## Test

```text
Read docs/agents/test.md
```

## Security

```text
Read docs/agents/security.md
```

## Refactor

```text
Read docs/agents/refactor.md
```

## Complete Task

```text
Read docs/agents/task-complete.md
```

## Full Workflow

```text
Read docs/agents/implement.md

After implementation:

Read docs/agents/review.md

After review:

Read docs/agents/test.md

After testing:

Read docs/agents/security.md

After security review:

Read docs/agents/task-complete.md
```

## Project Status

```text
Read docs/status.md

Summarize:

- Current Phase
- Current Task
- Completed Tasks
- Remaining Tasks
- Open Issues
- Recommended Next Task
```

## Generate Next Task

```text
Read docs/task-breakdown.md
Read docs/status.md

Generate implementation prompt for the next task only.
```

## Emergency Architecture Review

```text
Review:

- docs/architecture.md
- docs/database.md
- docs/product-decisions.md

Identify:

- Architecture violations
- Database violations
- Product decision violations
```
