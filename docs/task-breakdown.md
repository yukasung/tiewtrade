# Task Breakdown

## Purpose

This document defines the implementation phases and development tasks for Version 1 of TiewTrade.

The goal is to break the project into small, reviewable, and independently deliverable tasks suitable for Codex-assisted development.

This document is implementation planning only. It does not generate source code, database schemas, UI mockups, or architecture diagrams.

## Source Of Truth

Implementation must follow:

- `/docs/product-decisions.md`
- `/docs/project-overview.md`
- `/docs/screen-list.md`
- `/docs/user-flow.md`
- `/docs/architecture.md`
- `/docs/database.md`

When task scope conflicts with product decisions, `/docs/product-decisions.md` takes precedence.

## Version 1 Implementation Rules

- One Account = One Bot.
- Multiple Bots are not supported in Version 1.
- Binance Spot is supported.
- Binance Futures is supported.
- Futures long positions are supported.
- Futures short positions are supported.
- Stop Bot stops automated trading activity.
- Stop Bot does not close existing positions.
- Stop Bot does not force liquidation.
- Existing positions remain under user control.
- License validation uses an Offline License File.
- No online license activation is required.
- License validation is performed locally.
- Users cannot create, edit, import, or code strategies.
- Users only configure supported trading parameters.

## Phase 1 - Foundation

## TASK-001 Project Foundation

### Goal

Create the base desktop application structure.

### Scope

- Python project setup.
- Dependency management.
- Folder structure.
- Environment configuration.
- Application bootstrap.
- Logging framework foundation.
- Configuration framework foundation.
- Desktop application entry point.

### Deliverables

- Project structure.
- Dependency configuration.
- Application entry point.
- Initial configuration loading.
- Initial logging setup.

### Dependencies

- None.

## TASK-002 License Module

### Goal

Implement offline license file validation.

### Scope

- License file selection or loading.
- Local license file validation.
- License status management.
- License error handling.
- Missing, invalid, expired, corrupted, or unsupported license file states.
- Redacted license logging.

### Deliverables

- License service.
- Local license validation flow.
- License status model.
- License error states.

### Dependencies

- TASK-001 Project Foundation.

## TASK-003 Database Foundation

### Goal

Create local persistence infrastructure.

### Scope

- SQLite initialization.
- Repository pattern foundation.
- Database bootstrap.
- Migration foundation.
- Connection management.
- Transaction boundary foundation.
- Persistence error handling.

### Deliverables

- Database layer.
- Repository interfaces.
- Database bootstrap flow.
- Migration/versioning foundation.

### Dependencies

- TASK-001 Project Foundation.

## Phase 2 - Account Management

## TASK-004 Secure Credential Storage

### Goal

Store Binance credentials securely outside SQLite.

### Scope

- macOS Keychain support.
- Windows Credential Manager support.
- Linux Secret Service support.
- Credential lifecycle management.
- Credential creation, replacement, retrieval, and deletion.
- Credential error handling.
- No raw API secrets in SQLite logs or local database records.

### Deliverables

- Secure storage service.
- Credential reference model.
- Credential lifecycle flow.

### Dependencies

- TASK-001 Project Foundation.
- TASK-003 Database Foundation.

## TASK-005 Binance Account Module

### Goal

Connect and validate one Binance account context for the Version 1 bot.

### Scope

- Main Account support.
- Sub Account support.
- API key validation.
- Secret key validation.
- Spot permission validation.
- Futures permission validation.
- Withdrawal permission warning.
- Account status management.
- One Account = One Bot enforcement at product level.

### Deliverables

- Account service.
- Account validation flow.
- Account permission validation.
- Account connection status states.

### Dependencies

- TASK-002 License Module.
- TASK-003 Database Foundation.
- TASK-004 Secure Credential Storage.

## Phase 3 - Trading Infrastructure

## TASK-006 Binance Spot Integration

### Goal

Integrate Binance Spot API operations required by Version 1.

### Scope

- Spot market data.
- Spot account information.
- Spot balance access.
- Spot order placement.
- Spot order cancellation.
- Spot order status lookup.
- Spot exchange capability validation.
- Error mapping for user-facing and recovery flows.

### Deliverables

- Spot adapter.
- Spot market data access.
- Spot account data access.
- Spot order operations.

### Dependencies

- TASK-005 Binance Account Module.

## TASK-007 Binance Futures Integration

### Goal

Integrate Binance Futures API operations required by Version 1.

### Scope

- Futures market data.
- Futures account information.
- Futures balance and margin information.
- Long position support.
- Short position support.
- Position information.
- Futures order placement.
- Futures order cancellation.
- Futures order status lookup.
- Futures exchange capability validation.
- Futures risk and liquidation-related data access where available.
- Error mapping for user-facing and recovery flows.

### Deliverables

- Futures adapter.
- Futures market data access.
- Futures account data access.
- Futures position access.
- Futures order operations.

### Dependencies

- TASK-005 Binance Account Module.

## TASK-008 Exchange Synchronization

### Goal

Implement exchange synchronization services for safe startup, recovery, and reconnection.

### Scope

- Position synchronization.
- Order synchronization.
- Account synchronization.
- Exchange capability synchronization.
- Recovery synchronization.
- Unknown order reconciliation.
- Local state versus Binance state comparison.
- User review required state when synchronization cannot be safely resolved.

### Deliverables

- Synchronization engine.
- Position synchronization service.
- Order synchronization service.
- Account synchronization service.
- Recovery synchronization service.

### Dependencies

- TASK-006 Binance Spot Integration.
- TASK-007 Binance Futures Integration.
- TASK-003 Database Foundation.

## Phase 4 - Trading Engine

## TASK-009 Bot Lifecycle

### Goal

Implement single-bot runtime management.

### Scope

- Start bot.
- Stop bot.
- Runtime state.
- Lifecycle state machine.
- Single active bot enforcement.
- Startup validation.
- Stop Bot behavior that stops automation without closing positions.
- Disconnected, error, stopped, starting, running, stopping, and sync-required states.

### Deliverables

- Bot manager.
- Lifecycle manager.
- Bot state model.
- Start and stop orchestration.

### Dependencies

- TASK-002 License Module.
- TASK-003 Database Foundation.
- TASK-005 Binance Account Module.
- TASK-008 Exchange Synchronization.

## TASK-010 Strategy Engine

### Goal

Implement the built-in proprietary strategy engine.

### Scope

- RSI entry signal handling.
- ATR take profit signal handling.
- Signal generation.
- Same core strategy logic for Spot and Futures.
- Long signal support.
- Short signal support for Futures.
- Strategy configuration consumption.
- Strategy internals hidden from user-editable behavior.

### Deliverables

- Strategy engine.
- Signal generation service.
- Strategy configuration integration.

### Dependencies

- TASK-009 Bot Lifecycle.

## TASK-011 DCA Engine

### Goal

Implement multi-entry / DCA position management logic.

### Scope

- Entry management.
- DCA management.
- Average price calculation.
- DCA progress tracking.
- DCA limit enforcement.
- Spot DCA behavior.
- Futures long and short DCA behavior.

### Deliverables

- DCA engine.
- DCA state model.
- DCA progress integration.

### Dependencies

- TASK-010 Strategy Engine.
- TASK-012 Risk Engine.

## TASK-012 Risk Engine

### Goal

Implement risk controls for Spot and Futures trading.

### Scope

- Capital allocation.
- Risk validation.
- Exposure checks.
- Balance checks.
- DCA limit checks.
- Order size checks.
- Futures safety checks.
- Long and short Futures risk checks.
- Validation before bot start.
- Validation before order submission.
- Risk setting change validation while bot is stopped.

### Deliverables

- Risk engine.
- Risk validation service.
- Capital validation service.
- Futures risk validation service.

### Dependencies

- TASK-005 Binance Account Module.
- TASK-006 Binance Spot Integration.
- TASK-007 Binance Futures Integration.

## TASK-013 Order Management

### Goal

Manage order lifecycle safely and idempotently.

### Scope

- Order intent.
- Order tracking.
- Order submission correlation.
- Client-side order references where supported.
- Partial fills.
- Filled, rejected, canceled, failed, and unknown states.
- Retry handling.
- Idempotency.
- No blind retry after unknown order status.
- Order synchronization integration.

### Deliverables

- Order manager.
- Order lifecycle service.
- Order idempotency policy.
- Order status tracking.

### Dependencies

- TASK-006 Binance Spot Integration.
- TASK-007 Binance Futures Integration.
- TASK-008 Exchange Synchronization.
- TASK-012 Risk Engine.

## TASK-014 Position Management

### Goal

Manage position lifecycle and exposure visibility.

### Scope

- Position creation.
- Position updates.
- Spot exposure tracking.
- Futures long position tracking.
- Futures short position tracking.
- Position close detection.
- Position state reconciliation.
- Recovery state.
- DCA progress integration.
- ATR take profit progress integration.
- Stop Bot visibility for positions that remain open.

### Deliverables

- Position manager.
- Position state model.
- Position synchronization integration.
- Position monitoring data service.

### Dependencies

- TASK-008 Exchange Synchronization.
- TASK-011 DCA Engine.
- TASK-013 Order Management.

## Phase 5 - Recovery & Reliability

## TASK-015 Recovery Engine

### Goal

Recover safely after restart, crash, reconnect, or uncertain exchange state.

### Scope

- Crash recovery.
- Restart recovery.
- State restoration.
- Open position recovery.
- Unknown order recovery.
- Stop request recovery.
- Exchange reconnection recovery.
- Recovery detail recording.
- User review required state.

### Deliverables

- Recovery engine.
- Recovery coordinator.
- State restoration flow.
- Recovery status model.

### Dependencies

- TASK-008 Exchange Synchronization.
- TASK-009 Bot Lifecycle.
- TASK-013 Order Management.
- TASK-014 Position Management.

## TASK-016 Logging & Diagnostics

### Goal

Provide operational visibility without exposing sensitive data.

### Scope

- Structured logging.
- Error tracking.
- Redaction rules.
- Bot lifecycle logs.
- License logs.
- Account validation logs.
- Order and recovery logs.
- Local diagnostics.
- Support-safe error references.

### Deliverables

- Logging service.
- Error tracking service.
- Redaction policy implementation.
- Diagnostic data model.

### Dependencies

- TASK-001 Project Foundation.
- TASK-002 License Module.
- TASK-003 Database Foundation.
- TASK-015 Recovery Engine.

## Phase 6 - User Interface

## TASK-017 Application Shell

### Goal

Create the main desktop shell.

### Scope

- PySide6 application shell.
- Main window.
- Navigation.
- Window management.
- Global bot status.
- Global account status.
- Global license status.
- Error and recovery routing.

### Deliverables

- Main application shell.
- Navigation structure.
- Global status display.

### Dependencies

- TASK-001 Project Foundation.
- TASK-002 License Module.
- TASK-009 Bot Lifecycle.

## TASK-018 License Screens

### Goal

Implement offline license file UX.

### Scope

- License file selection.
- License file validation state.
- Missing license state.
- Invalid license state.
- Expired or unsupported license state.
- Valid license state.
- Local validation only.
- No online activation wording.

### Deliverables

- License file validation screen.
- License status screen.
- License error states.

### Dependencies

- TASK-002 License Module.
- TASK-017 Application Shell.

## TASK-019 Setup Wizard

### Goal

Implement the onboarding flow for non-technical traders.

### Scope

- Connect account.
- Select Spot or Futures.
- Select trading pair.
- Configure capital.
- Configure risk.
- Review configuration.
- Start Bot or Start Later.
- Futures risk acknowledgment.
- One Account = One Bot setup flow.

### Deliverables

- Complete wizard flow.
- Wizard validation.
- Review configuration step.
- Start Bot step.

### Dependencies

- TASK-005 Binance Account Module.
- TASK-008 Exchange Synchronization.
- TASK-009 Bot Lifecycle.
- TASK-012 Risk Engine.
- TASK-017 Application Shell.

## TASK-020 Dashboard

### Goal

Implement the main operating dashboard.

### Scope

- Bot status.
- Account status.
- Market mode.
- Trading pair.
- Capital summary.
- Balance summary.
- Position summary.
- PnL or result summary where available.
- Recent trade activity.
- Start Bot action.
- Stop Bot action.
- Recovery and error status.

### Deliverables

- Dashboard screen.
- Dashboard read model.
- Dashboard actions.

### Dependencies

- TASK-009 Bot Lifecycle.
- TASK-014 Position Management.
- TASK-017 Application Shell.

## TASK-021 Position Monitoring

### Goal

Display active positions and exposure in user-readable language.

### Scope

- Active position state.
- Spot exposure state.
- Futures long position state.
- Futures short position state.
- DCA progress.
- Take profit progress.
- Exposure and risk values.
- Stop Bot context when a position remains open.
- Empty state when no active position exists.

### Deliverables

- Position monitoring screen.
- Position detail view model.
- Position empty state.

### Dependencies

- TASK-014 Position Management.
- TASK-017 Application Shell.

## TASK-022 Trade History

### Goal

Display historical bot trading activity.

### Scope

- Historical trade list.
- Order result summary.
- Filled, partially filled, rejected, canceled, failed, and unknown outcomes.
- Recovery-corrected activity.
- Basic trade detail view.
- No manual trading actions.
- No strategy editing.

### Deliverables

- Trade history screen.
- Trade detail display.
- Trade history empty state.

### Dependencies

- TASK-013 Order Management.
- TASK-014 Position Management.
- TASK-017 Application Shell.

## TASK-023 Account Management UI

### Goal

Manage the connected Binance account context.

### Scope

- View connected account.
- Main Account display.
- Sub Account display.
- API credential status.
- Spot permission status.
- Futures permission status.
- Test connection.
- Replace account.
- Remove account.
- Bot-running guardrails for account changes.

### Deliverables

- Account management screen.
- Account replacement flow.
- Account removal confirmation.
- Account validation display.

### Dependencies

- TASK-004 Secure Credential Storage.
- TASK-005 Binance Account Module.
- TASK-017 Application Shell.

## TASK-024 Risk Settings UI

### Goal

Manage risk settings while preserving safe bot operation.

### Scope

- View current risk settings.
- Edit risk settings while bot is stopped.
- Read-only or blocked editing while bot is running.
- Capital allocation setting.
- DCA limit setting.
- Exposure and order size settings.
- Futures risk settings.
- Futures long and short risk messaging.
- Validation messages.

### Deliverables

- Risk settings screen.
- Risk validation display.
- Risk save flow.

### Dependencies

- TASK-012 Risk Engine.
- TASK-017 Application Shell.

## Phase 7 - Testing & Release

## TASK-025 Integration Testing

### Goal

Verify integrated behavior across product modules.

### Scope

- Spot workflows.
- Futures long workflows.
- Futures short workflows.
- Account validation workflows.
- Offline license file workflows.
- Start Bot workflow.
- Stop Bot workflow.
- Order workflow.
- Position workflow.
- Recovery workflows.
- Error handling workflows.

### Deliverables

- Integration test coverage.
- Integration test report.
- Known issue list.

### Dependencies

- TASK-001 through TASK-024.

## TASK-026 End-to-End Testing

### Goal

Verify complete user journeys.

### Scope

- First launch.
- Offline license file validation.
- Wizard flow.
- Account connection flow.
- Spot trading flow.
- Futures long trading flow.
- Futures short trading flow.
- Stop Bot with no position.
- Stop Bot with open position.
- Trade history review.
- Position monitoring.
- Recovery after restart.

### Deliverables

- End-to-end test coverage.
- E2E test report.
- Release-blocking issue list.

### Dependencies

- TASK-025 Integration Testing.

## TASK-027 Release Preparation

### Goal

Prepare Version 1 for distribution.

### Scope

- Build packaging.
- Installer.
- Versioning.
- Offline license file packaging assumptions.
- Release checklist.
- Basic user-facing setup notes.
- Known limitations.

### Deliverables

- Packaged desktop application.
- Installer or distribution artifact.
- Release checklist.
- Version 1 known limitations.

### Dependencies

- TASK-026 End-to-End Testing.

## Phase Dependency Summary

| Phase | Depends On | Primary Outcome |
|---|---|---|
| Phase 1 - Foundation | None | App, license, and database foundations |
| Phase 2 - Account Management | Phase 1 | Secure Binance account connection |
| Phase 3 - Trading Infrastructure | Phase 2 | Spot, Futures, and synchronization adapters |
| Phase 4 - Trading Engine | Phase 3 | Bot lifecycle, strategy, risk, orders, and positions |
| Phase 5 - Recovery & Reliability | Phase 4 | Safe restart, recovery, logging, and diagnostics |
| Phase 6 - User Interface | Phases 1-5 | Complete desktop user experience |
| Phase 7 - Testing & Release | Phases 1-6 | Verified and packaged Version 1 release |

## Implementation Review Rules

Each task should be implemented and reviewed independently where possible.

Before a task is considered complete:

- Scope items must be implemented or explicitly deferred.
- Deliverables must be present.
- Product decisions must be respected.
- No unsupported Version 1 features should be added.
- Sensitive data must not be logged.
- Trading-related behavior must be recoverable where applicable.
- User-facing behavior must remain understandable for non-technical traders.

## Deferred From Version 1

The following items must not be introduced as hidden scope during implementation:

- Multiple bot management.
- Multiple account management.
- Strategy builder.
- AI strategy builder.
- User-defined strategy logic.
- Backtesting.
- Copy trading.
- Mobile app.
- Web app.
- Telegram notifications.
- Marketplace.
- Multi-exchange support.
- Online license activation.
- Cloud synchronization.
