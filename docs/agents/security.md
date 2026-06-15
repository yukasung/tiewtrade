# Security Audit Agent Workflow

## Purpose

Perform a security-focused review of newly implemented features.

Use this document by running:

Read `docs/agents/security.md`

## Required Context

Before starting a security review, read:

- `docs/project-overview.md`
- `docs/product-decisions.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/task-breakdown.md`
- `docs/status.md`

Read latest implementation report if available:

- `docs/task-report.md`

If any document conflicts with `docs/product-decisions.md`, follow `docs/product-decisions.md`.

## Security Review Scope

Review only the files modified in the latest implementation.

Do not implement fixes.

Do not refactor code.

Do not start the next task.

Security review only.

## Security Review Areas

1. Credential Security
2. License Security
3. Trading Safety
4. Binance Integration Security
5. Database Security
6. Logging Security
7. Recovery Security
8. Application Security

## Credential Security

Verify:

- API Keys are never stored in SQLite.
- API Secrets are never stored in SQLite.
- Secure credential storage is used.
- Credentials are masked in UI.
- Credentials are masked in logs.
- Credentials are deleted correctly when an account is removed.

Expected secure storage providers:

- macOS Keychain.
- Windows Credential Manager.
- Linux Secret Service.

Check:

- Credential creation.
- Credential update.
- Credential rotation.
- Credential deletion.

## License Security

Verify:

- Offline license validation only.
- No online activation dependency.
- Invalid license blocks application access.
- Invalid license blocks bot startup.
- Corrupted license handled safely.
- License information is not exposed in logs.

Check:

- Missing license file.
- Invalid license file.
- Expired license file.
- Corrupted license file.
- Unsupported license file.

## Shared Security Logic

Verify:

- Security validation is centralized.
- Credential validation is not duplicated.
- License validation is not duplicated.
- Security-sensitive logic is reused consistently.
- Redaction logic is shared rather than copied across modules.
- Authentication, authorization, and permission checks use shared services or helpers when repeated.

## Trading Safety

Verify:

- Duplicate orders cannot occur.
- Duplicate bot instances cannot occur.
- Risk validation exists before bot start.
- Invalid configuration blocks trading.
- Stop Bot does not unexpectedly close positions.
- Position state remains consistent.
- Order state remains consistent.

Check:

- Spot mode.
- Futures mode.
- Long positions.
- Short positions.
- DCA workflow.
- Recovery workflow.

## Binance Integration Security

Verify:

- Binance API failures handled safely.
- Rate limits handled correctly.
- Unknown order states handled safely.
- Timeout handling exists.
- Order synchronization exists.
- Position synchronization exists.

Check:

- Spot adapter.
- Futures adapter.
- Account validation.
- Exchange capability validation.

## Database Security

Verify:

- SQLite contains no raw API secrets.
- SQLite contains no raw license secrets.
- Sensitive values are redacted.
- Data integrity rules enforced.
- Recovery state stored safely.

Review:

- Account records.
- Bot records.
- Position records.
- Order records.
- Trade records.
- Recovery records.
- License records.

## Logging Security

Verify:

- API Keys never appear in logs.
- API Secrets never appear in logs.
- License secrets never appear in logs.
- Sensitive account identifiers are redacted.

Check:

- Application logs.
- Error logs.
- Recovery logs.
- Diagnostic logs.

## Recovery Security

Verify:

- Application restart recovery is safe.
- Crash recovery is safe.
- Synchronization required before trading resumes.
- Recovery cannot create duplicate orders.
- Recovery cannot create duplicate positions.

Review:

- Restart workflow.
- Crash workflow.
- Exchange reconnection workflow.
- Synchronization workflow.

## Application Security

Verify:

- Configuration validation exists.
- Error handling exists.
- Unsafe application states are blocked.
- Invalid startup conditions are blocked.

Check:

- Missing configuration.
- Invalid account.
- Invalid trading pair.
- Invalid risk settings.
- Missing license.

## Risk Classification

Classify findings:

### Critical

Immediate risk of financial loss, credential exposure, or unsafe trading behavior.

### High

High probability security issue or trading risk.

### Medium

Moderate risk requiring correction.

### Low

Minor improvement recommended.

### Informational

No action required.

## Output

Create:

- `docs/reviews/security-{task-name}.md`

Include:

1. Summary
2. Files Reviewed
3. Security Checks Performed
4. Issues Found
5. Risk Classification
6. Required Fixes
7. Recommendations
8. Verdict

Verdict:

- PASS
- PASS WITH MINOR FIXES
- FAIL

## Rules

Do not modify source code.

Do not implement fixes.

Do not refactor code.

Do not start the next task.

Security review only.

## Completion Rule

Security review is complete only when:

- Credential security reviewed.
- License security reviewed.
- Trading safety reviewed.
- Binance integration reviewed.
- Database security reviewed.
- Logging security reviewed.
- Recovery security reviewed.
- Security report created.

End of workflow.

## Execution Instructions

After reading this document:

1. Read all required context.
2. Execute the security review workflow described in this document.
3. Perform all required security review actions.
4. Create all required reports.
5. Update all required files only when the security workflow explicitly requires it.
6. Return the security verdict.
7. Stop when security review is complete.

Security-specific execution:

1. Identify the latest implementation from `docs/status.md` and `docs/task-report.md`.
2. Review only files modified in the latest implementation.
3. Perform credential, license, trading safety, Binance integration, database, logging, recovery, application, and shared security checks.
4. Do not implement fixes.
5. Create `docs/reviews/security-{task-name}.md`.
6. Return the security verdict.
7. Stop after the security report is created.

Do not summarize this document.
Do not explain the workflow.
Execute security review.
