# Commands Update Review

## Commands Added

- `Plan Task`
- `Explain Code`
- `Architecture Audit`

## Commands Removed

- Removed the previous longer full workflow text that described intermediate steps between agents.
- Removed duplicated workflow details that now belong only in the agent files.
- Renamed the emergency architecture review shortcut to `Architecture Audit`.

## Workflow Changes

- `docs/commands.md` now acts as a lightweight command launcher.
- Workflow execution details remain inside the relevant agent files.
- Planning is now part of the standard full workflow before implementation.
- Code explanation is now part of the standard full workflow before task completion.
- Command sections now use a consistent structure: command plus purpose.

## Recommended Usage

Use `docs/commands.md` to choose the workflow shortcut.

Use agent files for actual execution:

```text
Read docs/agents/plan.md
Read docs/agents/implement.md
Read docs/agents/review.md
Read docs/agents/test.md
Read docs/agents/security.md
Read docs/agents/explain-code.md
Read docs/agents/task-complete.md
```

Use individual commands when only one workflow is needed.

Use the full workflow for normal task delivery.

## Final Workflow Diagram

```text
Plan Task
↓
Implement
↓
Review
↓
Test
↓
Security
↓
Explain Code
↓
Complete Task
```
