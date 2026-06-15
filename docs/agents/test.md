# Testing Agent Workflow

## Purpose

Perform testing and validation of completed implementation tasks.

Use this document by running:

Read `docs/agents/test.md`

## Required Context

Before testing, read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

Read latest implementation report if available:

- `docs/task-report.md`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Testing Scope

Test only the task that was just implemented.

Do not implement fixes.

Do not refactor code.

Do not start the next task.

Testing only.

## Testing Types

1. Functional Testing
2. Unit Testing
3. Integration Testing
4. Recovery Testing
5. Regression Testing

## Functional Testing

Verify:

- Acceptance criteria met.
- Expected user behavior.
- Expected business behavior.
- Expected application behavior.

Examples:

- License validation.
- Account connection.
- Bot start.
- Bot stop.
- Trade history.
- Position monitoring.

## Unit Testing

Required when implementation contains:

- Business logic.
- Service classes.
- Managers.
- Validators.
- Risk calculations.
- Strategy calculations.

Verify:

- Expected inputs.
- Expected outputs.
- Edge cases.
- Failure cases.

## Shared Abstraction Testing

Verify:

- Refactored logic behaves identically.
- Shared services produce expected results.
- Utility functions behave consistently.
- Shared functions produce deterministic outputs.
- Helpers preserve existing behavior.
- Base classes preserve subclass lifecycle and behavior.
- Edge cases from previous duplicated implementations are covered.

## Integration Testing

Required when implementation interacts with:

- Binance API.
- SQLite.
- Secure storage.
- License services.
- Application services.

Verify:

- Component interaction.
- Service registration.
- Dependency handling.
- Data flow correctness.

## Recovery Testing

Verify:

- Application restart.
- State restoration.
- Position synchronization.
- Order synchronization.
- Recovery workflows.

Examples:

- App crash.
- Network interruption.
- Binance reconnect.
- Bot restart.

## Regression Testing

Verify:

- Existing features still work.
- Previous tasks still work.
- No behavior changed unexpectedly.

## Trading Safety Testing

Verify:

- No duplicate orders.
- No duplicate bot instances.
- Stop Bot does not close positions.
- Risk validation before bot start.
- Invalid configuration blocks trading.

## Futures Testing

Verify:

- Long positions.
- Short positions.
- Margin validation.
- Position synchronization.
- Risk warnings.

## License Testing

Verify:

- Offline license validation.
- Invalid license handling.
- Missing license handling.
- Corrupted license handling.

## Test Report

Create:

- `docs/testing/test-{task-name}.md`

Include:

1. Summary
2. Functional Test Results
3. Unit Test Results
4. Integration Test Results
5. Recovery Test Results
6. Regression Test Results
7. Risks
8. Recommendations
9. Verdict

Verdict:

- PASS
- PASS WITH MINOR ISSUES
- FAIL

## Rules

Do not modify source code.

Do not implement fixes.

Testing only.

If issues are found:

- Describe issue.
- Describe impact.
- Recommend fix.

Do not apply fix.

## Completion Rule

Testing is complete only when:

- Functional testing completed.
- Unit testing completed.
- Integration testing completed.
- Recovery testing completed.
- Regression testing completed.
- Test report created.

End of workflow.

## Execution Instructions

After reading this document:

1. Read all required context.
2. Execute the testing workflow described in this document.
3. Perform all required testing actions.
4. Create all required reports.
5. Update all required files only when the testing workflow explicitly requires it.
6. Return the testing verdict.
7. Stop when testing is complete.

Testing-specific execution:

1. Identify the latest implemented task from `docs/status.md` and `docs/task-report.md`.
2. Determine the applicable functional, unit, integration, recovery, regression, trading safety, futures, and license checks for that task.
3. Run or document the applicable tests for the implemented task only.
4. Do not implement fixes.
5. Create `docs/testing/test-{task-name}.md`.
6. Return the testing verdict.
7. Stop after the testing report is created.

Do not summarize this document.
Do not explain the workflow.
Execute testing.
