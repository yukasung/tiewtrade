# TiewTrade - Commands

## Rule

Always follow:

- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

Do not implement future tasks.

When documents conflict, `docs/product-decisions.md` is authoritative.

## Architecture Rule

When logic is reused:

- Extract to Shared Function.
- Extract to Utility Function.
- Extract to Helper.
- Extract to Shared Service.
- Extract to Base Class.

Use standard shared locations:

- `src/shared/functions/`
- `src/shared/utils/`
- `src/shared/helpers/`
- `src/shared/services/`
- `src/shared/base/`

Avoid copy-paste implementations.

Always search for reusable abstractions before creating new code.

Duplicate business logic is not allowed.

## Start

```text
Read docs/commands.md
Read docs/status.md
Tell me the current task and recommended next action.
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

## Full Task Workflow

```text
Read docs/agents/implement.md
Then read docs/agents/review.md
Then read docs/agents/test.md
Then read docs/agents/security.md
Then read docs/agents/task-complete.md
```

## Project Status

```text
Read docs/status.md
Summarize current phase, current task, completed tasks, remaining tasks, and next recommended task.
```

## Next Task Prompt

```text
Read docs/task-breakdown.md
Read docs/status.md
Generate the Codex prompt for the next task only.
```
