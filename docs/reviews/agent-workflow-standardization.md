# Agent Workflow Standardization Review

## 1. Files Updated

- `docs/agents/implement.md`
- `docs/agents/review.md`
- `docs/agents/test.md`
- `docs/agents/security.md`
- `docs/agents/refactor.md`
- `docs/agents/task-complete.md`

## 2. Execution Sections Added

Each workflow agent now includes a final `## Execution Instructions` section.

The execution sections instruct Codex to:

- Read required context.
- Execute the workflow instead of summarizing it.
- Perform required actions.
- Create required reports.
- Update required files when the workflow allows it.
- Return the correct verdict or result.
- Stop when the workflow is complete.

## 3. Improvements Made

- Converted workflow files from passive documentation into executable workflow prompts.
- Standardized the final instruction pattern across all agents.
- Added task-specific execution steps for implementation, review, testing, security review, refactoring, and completion verification.
- Clarified that agent runs must not summarize or explain the workflow.
- Clarified that agents must stop after their assigned workflow is complete.
- Updated the review workflow to require a saved report at `docs/reviews/review-{task-name}.md`.
- Aligned review verdicts with task completion requirements.

## 4. Standardization Rules

- Every agent file must end with `## Execution Instructions`.
- Execution instructions must tell Codex to execute the workflow, not summarize it.
- Each agent must read its required context before acting.
- Each agent must operate only within its declared scope.
- Each agent must create its required report before returning a verdict.
- Agents must not start future tasks.
- Agents must not modify product scope, architecture decisions, database design, or task definitions unless their workflow explicitly allows it.
- Reports must use the expected folder and filename pattern defined by each agent.

## 5. Recommended Usage

Use the command files as shortcuts, then let the agent document execute itself:

```text
Read docs/agents/implement.md
```

```text
Read docs/agents/review.md
```

```text
Read docs/agents/test.md
```

```text
Read docs/agents/security.md
```

```text
Read docs/agents/refactor.md
```

```text
Read docs/agents/task-complete.md
```

Expected behavior:

- Codex reads the agent file.
- Codex reads required project context.
- Codex executes the workflow.
- Codex creates the required report.
- Codex returns the workflow result or verdict.
