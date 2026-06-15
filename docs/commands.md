# TiewTrade - Codex Commands

## Important Rule

Always read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`

before implementing any task.

Do not violate `product-decisions.md`.

Do not implement future tasks.

When documents conflict, `docs/product-decisions.md` is authoritative.

## Start Session

```text
Read:

- docs/project-overview.md
- docs/product-decisions.md
- docs/task-breakdown.md

Identify current task.

Summarize:

- Current phase
- Current task
- Remaining tasks
- Risks
```

## Implement Current Task

```text
Read:

- docs/project-overview.md
- docs/product-decisions.md
- docs/architecture.md
- docs/database.md
- docs/task-breakdown.md

Implement current task only.

Requirements:

- Follow architecture.md
- Follow database.md
- Follow product-decisions.md
- Avoid duplicate logic
- Create reusable services when appropriate

Do not implement future tasks.
```

## Review Current Task

```text
Review implementation.

Verify:

- Architecture compliance
- Database compliance
- No duplicate logic
- Proper separation of layers
- Error handling
- Recovery handling
- Logging
```

## Test Current Task

```text
Create test checklist.

Verify:

- Happy path
- Error path
- Recovery path
- Edge cases
```

## Security Review

```text
Review:

- API Key handling
- License handling
- Secure storage usage
- Sensitive data exposure
- Logging redaction
```

## Complete Current Task

```text
Create:

docs/task-report.md

Include:

- Completed work
- Files changed
- Technical decisions
- Open issues
- Next task
```

## Review Project Status

```text
Read:

- docs/task-breakdown.md

Summarize:

- Current phase
- Completed tasks
- Remaining tasks
- Recommended next task
```

## Generate Next Task Prompt

```text
Read:

- docs/task-breakdown.md

Generate implementation prompt for the next task.

Include:

- Scope
- Requirements
- Deliverables
- Exclusions
```
