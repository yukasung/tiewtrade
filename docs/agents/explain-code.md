# Code Explanation Agent Workflow

## Purpose

Explain code that was added or modified in the latest task.

Use this document by running:

```text
Read docs/agents/explain-code.md
```

## Required Context

Before explaining code, read:

- `docs/status.md`
- `docs/task-breakdown.md`
- `docs/task-report.md`

If needed, also read:

- `docs/architecture.md`
- `docs/database.md`
- `docs/product-decisions.md`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Explanation Scope

Explain only code added or modified in the latest task.

Do not implement new code.

Do not refactor code.

Do not start the next task.

Explanation only.

## What To Explain

Explain:

1. Files created
2. Files modified
3. Purpose of each file
4. Important classes
5. Important functions
6. Data flow
7. How the code fits the architecture
8. What was intentionally not implemented
9. Risks or limitations
10. How to run or verify the result

## Explanation Style

Use simple language.

Avoid unnecessary technical jargon.

Explain for a project owner or developer who wants to understand what changed.

When explaining functions or classes:

- Describe what it does.
- Describe why it exists.
- Describe where it is used.
- Describe important inputs and outputs.

## Output

Create:

```text
docs/explanations/explain-{task-name}.md
```

Include:

1. Summary
2. Task Context
3. Files Created
4. Files Modified
5. Code Walkthrough
6. Important Classes
7. Important Functions
8. Architecture Alignment
9. Data Flow
10. How To Run
11. How To Verify
12. Limitations
13. Next Recommended Step

## Rules

Do not modify source code.

Do not implement fixes.

Do not refactor.

Do not start the next task.

Explanation only.

## Execution Instructions

After reading this document:

1. Read required context files.
2. Identify the latest completed or in-progress task.
3. Identify files created or modified in that task.
4. Explain the code changes.
5. Create the explanation report in `docs/explanations/`.
6. Return a short summary and the report path.

Do not summarize this document.

Execute the explanation workflow.

End of workflow.
