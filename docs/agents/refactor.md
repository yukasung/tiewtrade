# Refactor Agent Workflow

## Purpose

Perform a controlled refactoring review and improvement process.

Use this document by running:

Read `docs/agents/refactor.md`

## Required Context

Before refactoring, read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

Review latest reports if available:

- `docs/task-report.md`
- `docs/reviews/*`
- `docs/testing/*`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Refactoring Scope

Refactor only existing code.

Do not introduce new features.

Do not expand project scope.

Do not start the next task.

Preserve behavior.

Preserve trading logic.

Preserve public interfaces.

## Refactoring Goals

Improve:

- Maintainability.
- Readability.
- Modularity.
- Testability.
- Reliability.

Without changing business behavior.

## Architecture Compliance

Verify:

- Architecture boundaries are respected.
- Layer separation remains clear.
- UI does not depend on infrastructure.
- Domain does not depend on PySide6.
- Trading logic remains isolated.
- Persistence remains isolated.

Check:

- Presentation Layer.
- Application Layer.
- Domain Layer.
- Infrastructure Layer.
- Persistence Layer.

## Code Quality

Review:

- Duplicate code.
- Dead code.
- Unused classes.
- Unused methods.
- Large classes.
- Large methods.
- Deep nesting.
- Excessive complexity.

## Trading Safety Review

Verify:

- No duplicate order creation.
- No duplicate bot runtime creation.
- Stop Bot behavior preserved.
- Position state handling preserved.
- Recovery behavior preserved.
- Risk validation preserved.

Refactoring must never weaken:

- Trading safety.
- Recovery workflows.
- Synchronization workflows.

## OOP Design

Verify:

- Single Responsibility Principle.
- Separation of Concerns.
- Clear module responsibilities.
- Consistent naming.
- Consistent package structure.

## Service Extraction Rules

Repeated logic should be moved into shared services.

Preferred locations:

```text
src/application/services/
src/domain/services/
src/infrastructure/services/
src/shared/
```

Examples:

- Binance validation.
- License validation.
- Risk validation.
- Configuration validation.
- Recovery helpers.
- Synchronization helpers.

Rules:

1. Avoid duplicate logic.
2. Prefer services for business logic.
3. Prefer helpers for stateless utilities.
4. Do not over-engineer.
5. Preserve existing behavior.

## Performance Review

Review:

- Excessive polling.
- Unnecessary Binance API calls.
- Repeated calculations.
- Database write frequency.
- Memory usage.
- Long-running operations.

Verify:

- UI thread remains responsive.
- Trading workers remain isolated.

## Security Preservation

Verify refactoring does not weaken:

- Secure credential storage.
- License validation.
- Data redaction.
- Logging protection.
- Recovery validation.

## Recovery Preservation

Verify:

- Restart recovery still works.
- Crash recovery still works.
- Synchronization still works.
- State restoration still works.

## Refactor Recommendations

Classify:

### Critical Refactor

Must be fixed.

### Recommended Refactor

Should be fixed.

### Optional Refactor

Can be improved later.

## Output

Create:

- `docs/reviews/refactor-{task-name}.md`

Include:

1. Summary
2. Files Reviewed
3. Refactor Opportunities
4. Risks
5. Recommendations
6. Refactor Plan
7. Verdict

Verdict:

- NO REFACTOR NEEDED
- RECOMMENDED REFACTOR
- CRITICAL REFACTOR REQUIRED

## Rules

Do not implement new features.

Do not change trading behavior.

Do not change business rules.

Do not start the next task.

Refactoring only.

## Completion Rule

Refactoring is complete only when:

- Architecture remains compliant.
- Tests still pass.
- Security remains intact.
- Trading behavior remains unchanged.
- Recovery behavior remains unchanged.
- Documentation remains accurate.

End of workflow.
