# Shared Abstraction Rules Review

## 1. Summary

This document records the project-wide code reuse and shared abstraction standards added to the TiewTrade agent workflows.

The standards are intended to eliminate duplicate logic, reduce copy-paste implementations, improve maintainability, and enforce reusable architecture across implementation, review, refactoring, testing, security, task completion, and command workflows.

No product scope, architecture decisions, database design decisions, or feature scope were changed.

## 2. Rules Added

The following engineering standards were added:

- Search the existing codebase before implementing new logic.
- Search shared abstractions before creating new functions, helpers, services, or base classes.
- Reuse existing implementations when available.
- Extract repeated logic into the appropriate shared abstraction.
- Do not duplicate business logic.
- Do not copy-paste implementations.
- Major duplicate business logic blocks task approval and task completion.

## 3. Files Updated

- `docs/agents/implement.md`
- `docs/agents/review.md`
- `docs/agents/refactor.md`
- `docs/agents/test.md`
- `docs/agents/security.md`
- `docs/agents/task-complete.md`
- `docs/commands.md`

## 4. Recommended Folder Structure

```text
src/shared/functions/
src/shared/utils/
src/shared/helpers/
src/shared/services/
src/shared/base/
```

Recommended use:

- `src/shared/functions/`: pure reusable calculations with no state and no dependencies.
- `src/shared/utils/`: formatting, conversion, parsing, and transformation functions.
- `src/shared/helpers/`: small stateless helper logic used by multiple modules.
- `src/shared/services/`: reusable business, domain, application, or integration logic.
- `src/shared/base/`: shared lifecycle, behavior, or runtime responsibilities.

## 5. Examples

Shared Function examples:

- `calculate_pnl()`
- `calculate_average_price()`
- `calculate_position_size()`

Utility Function examples:

- `format_price()`
- `format_percentage()`
- `convert_timestamp()`

Helper examples:

- `BinancePairHelper`
- `LicenseFileHelper`
- `ValidationHelper`

Shared Service examples:

- `RiskValidationService`
- `LicenseValidationService`
- `BinanceAccountService`
- `RecoveryService`
- `SynchronizationService`

Base Class examples:

- `BaseBotWorker`
- `BaseExchangeAdapter`
- `BaseRepository`

## 6. Benefits

- Reduces duplicated business rules.
- Improves maintainability.
- Keeps trading safety logic consistent.
- Keeps license validation behavior consistent.
- Keeps credential and logging security behavior centralized.
- Makes testing easier by concentrating repeated behavior in reusable units.
- Reduces risk of inconsistent Binance API handling.
- Reduces risk of inconsistent recovery and synchronization behavior.

## 7. Compliance Checklist

Before implementation:

- Existing codebase searched.
- Existing shared functions searched.
- Existing utilities searched.
- Existing helpers searched.
- Existing services searched.
- Existing base classes searched.

During implementation:

- Reusable logic extracted when repeated.
- Business logic placed in shared services when reused.
- Pure calculations placed in shared functions when reused.
- Formatting, parsing, conversion, and transformation placed in utilities when reused.
- Stateless support logic placed in helpers when reused.
- Shared lifecycle behavior placed in base classes when reused.

During review:

- No duplicate business logic exists.
- No repeated validation logic exists.
- No repeated Binance API handling exists.
- No repeated configuration logic exists.
- No repeated logging logic exists.
- No repeated recovery logic exists.

Before completion:

- Code reuse rules followed.
- Shared abstractions used correctly.
- Major duplication is not present.
- Task report documents relevant technical decisions.
