# Database Design Final

## Document Purpose

This document defines the final conceptual database design and domain model for the Version 1 TiewTrade desktop trading bot application.

The purpose is to prepare the project for later physical database design without creating SQL scripts, migration files, source code, or implementation-level storage definitions.

This document incorporates the review findings from `/docs/database-review.md` and clarifies entity ownership, relationships, recovery data, security boundaries, and integrity rules.

## Source Documents

- `/docs/project-overview.md`
- `/docs/screen-list.md`
- `/docs/user-flow.md`
- `/docs/architecture.md`
- `/docs/database.md`
- `/docs/database-review.md`

## Technology Context

- Database: SQLite.
- Runtime: Python 3.13.
- Application type: Local desktop application.
- User interface: PySide6 desktop application.
- Exchange integration: Binance API.
- Supported exchange modes: Binance Spot and Binance Futures.
- Supported account contexts: Binance Main Account and Binance Sub Account.

## Non-Goals

This document does not define:

- SQL scripts.
- Migration files.
- Physical table definitions.
- Column types.
- ORM classes.
- Source code.
- Encryption implementation details.
- Binance API payload structures.

## Final Database Design Decisions

The following decisions are confirmed for Version 1 conceptual design.

| Area | Final Decision |
|---|---|
| Account modeling | `Account` is the canonical account context for both Main Account and Sub Account usage. |
| Sub Account modeling | `Sub Account` is modeled as a specialized account context/profile related to a parent Main Account when known. Bot records reference one canonical Account Context only. |
| Bot account relationship | A Bot Instance references exactly one Account Context. It must not separately reference unrelated Main and Sub Account records. |
| Bot instance boundary | Bot Instance is modeled as the ownership boundary for the single Version 1 bot experience. The model may remain future-ready, but Version 1 must not expose multiple bot creation, switching, archiving, or concurrent bot execution. |
| Strategy model | Version 1 supports one built-in proprietary strategy only. Users configure parameters but do not create or modify strategy logic. |
| Configuration history | Orders, trades, and recovery records reference immutable Configuration Snapshots instead of relying only on mutable active settings. |
| Order execution modeling | Order Execution / Fill is a first-class child entity of Order. Trade remains the user-facing history summary. |
| Recovery detail | Recovery Session owns Recovery Detail records for each reconciled order, position, stop request, account validation, or capability check. |
| Error modeling | Error Record tracks active user-facing errors separately from diagnostic logs. |
| Log storage | SQLite stores structured, redacted Log Entry records. Rotating local diagnostic files may exist later, but trading-critical facts must be stored in domain entities, not only logs. |
| Credential storage | Raw API keys and secrets are never stored in SQLite. SQLite stores only opaque credential references and redacted display hints. |
| License storage | SQLite stores minimum local license state and redacted license references. Sensitive entitlement tokens belong in secure storage when required. |

## 1. Database Design Principles

### Local Durable State

SQLite is the durable local store for non-secret product state, including:

- Application setup state.
- Account metadata.
- Credential references.
- Bot configuration and lifecycle state.
- Risk configuration.
- Strategy configuration references.
- Capital reservations.
- Position state.
- Order state.
- Order executions and fills.
- Trade history.
- Recovery state.
- License state.
- Error records.
- Redacted diagnostic logs.

The application must be able to restart, recover from a crash, and restore user-visible state without relying on a remote application server.

### Domain-Driven Persistence

Persistence follows product and domain concepts, not screen layout. Screens consume data through application services and read models. They should not dictate the storage model.

Primary domain concepts are:

- Account.
- Sub Account.
- Credential Reference.
- Account Permission Snapshot.
- Bot Instance.
- Bot State History.
- Strategy Configuration.
- Risk Configuration.
- Configuration Snapshot.
- Capital Reservation.
- Position.
- Order.
- Order Execution / Fill.
- Trade.
- Stop Request.
- Recovery Session.
- Recovery Detail.
- Application Settings.
- License.
- License Validation History.
- Error Record.
- Log Entry.
- Diagnostic Export.
- Exchange Capability.

### Aggregate-Oriented Consistency

Writes must preserve aggregate boundaries and trading safety. Operations that change the consistency of one aggregate should be atomic within that aggregate. Workflows that span multiple aggregates must be coordinated by application services.

Important consistency operations include:

- Completing setup.
- Replacing account credentials.
- Removing an account.
- Activating a license.
- Starting a bot.
- Stopping a bot.
- Saving a validated configuration.
- Creating an immutable configuration snapshot.
- Creating an order intent before Binance submission.
- Correlating an order with Binance identifiers.
- Recording order executions.
- Updating position state from executions.
- Creating trade history summaries.
- Creating recovery details.
- Resolving active errors.

### No Raw Secrets In SQLite

Raw Binance API keys, API secrets, and sensitive entitlement tokens must not be stored in SQLite.

SQLite may store:

- Opaque credential references.
- Redacted display hints.
- Credential lifecycle state.
- Non-secret account labels.
- Sensitive non-secret account identity references when required.

Sensitive non-secret values must be redacted in logs, exports, and support references.

### Idempotent Trading State

The database must prevent duplicate trading actions after retries, timeouts, reconnects, restarts, and crashes.

Every bot-generated order must begin as a durable local order intent before Binance submission. The intent must include a bot action reference so unknown order states block only the relevant action scope unless the risk policy requires the whole bot to pause.

### Explicit Recovery State

Recovery must be represented directly in the domain model, not inferred only from logs.

The database must preserve:

- App-level clean-shutdown marker.
- Per-bot last known runtime state.
- Per-bot unresolved work markers.
- Stop request state.
- Unknown order state.
- Last known position or exposure.
- Exchange synchronization results.
- Recovery detail records.
- User review requirements.

### Immutable Historical Context

Orders, executions, trades, and recovery corrections must preserve the configuration context that produced them.

Users may edit risk settings later, but historical trading records must still show the effective strategy version, risk settings, capital allocation, market mode, trading pair, account context, and exchange capability context used at the time.

### Append-Friendly Trading History

Trade history is product data and should be retained locally. Corrections discovered during recovery must be represented as corrections or reconciled updates, not silently hidden.

This is not event sourcing. The application does not reconstruct the entire world from historical events, but it does keep enough operational history for user trust, support, and recovery.

### SQLite-Friendly Access

SQLite writes should be coordinated through a persistence layer so UI activity and background bot workers do not create uncontrolled write contention.

Expected persistence behavior:

- Serialized writes.
- Short write transactions.
- Explicit consistency boundaries.
- Read models optimized for Dashboard, Position Monitoring, Trade History, Account Management, Risk Settings, License Management, and Error screens.

## 2. Domain Model

## Domain Contexts

### Account Context

Owns Binance account metadata, Main Account and Sub Account identity, permission status, connectivity status, secure credential references, credential lifecycle state, and account permission snapshots.

### Bot Context

Owns Bot Instance lifecycle, runtime state, bot status, start and stop state, capital allocation, bot state history, and duplicate runtime prevention.

### Strategy And Risk Context

Owns the built-in strategy configuration, risk configuration, user-configurable parameters, risk validation state, and immutable configuration snapshots.

### Trading Context

Owns Positions, Orders, Order Executions / Fills, Trades, exchange correlation, idempotency, partial fills, rejections, cancellations, unknown states, and trade history.

### Recovery Context

Owns restart recovery, crash recovery, exchange reconnection, open position synchronization, order synchronization, stop request reconciliation, recovery details, and state restoration.

### Licensing Context

Owns Offline License File metadata, local validation state, redacted license references, and license validation history.

### Diagnostics Context

Owns Error Records, structured Log Entries, diagnostic export records, redaction state, and support-safe references.

### Application Context

Owns Application Settings, setup progress, clean-shutdown marker, local preferences, application configuration version, and global startup routing state.

## Account Context Rule

The final model uses a single canonical account context reference.

- A Main Account is represented by an Account entity with account type `Main Account`.
- A Sub Account is represented by an Account entity with account type `Sub Account`.
- A Sub Account may have a parent Main Account relationship when known.
- The Sub Account entity/profile stores Sub Account-specific metadata and lineage.
- A Bot Instance references exactly one Account Context ID.
- A Bot Instance must never reference both a Main Account and a separate Sub Account as independent trading targets.

This rule prevents invalid bot-account combinations and simplifies future physical database design.

## Trading Object Rule

Orders, positions, executions, and trades have separate meanings.

- Order represents local intent plus Binance order lifecycle.
- Order Execution / Fill represents exchange execution facts for an order.
- Position represents current or historical exposure.
- Trade represents user-facing trading activity shown in Trade History.

An initial entry Order may exist before a Position exists. A Position is created when exposure is established locally or discovered during recovery. Recovered Positions may exist without complete local Order history and must be marked as recovery-created or recovery-corrected.

## 3. Entity Definitions

## Account

### Purpose

Represents one Binance trading account context known to the desktop application.

An Account can represent either:

- Binance Main Account.
- Binance Sub Account.

### Responsibilities

- Identify the Binance account context used for trading.
- Distinguish Main Account and Sub Account usage.
- Store non-secret account metadata.
- Store secure credential reference state.
- Track Spot permission status.
- Track Futures permission status.
- Track connectivity and validation state.
- Provide the canonical account reference for Bot Instances.
- Support safe removal and credential deletion recovery.

### Important Attributes

- Account ID.
- Exchange name.
- Account type: Main Account or Sub Account.
- Parent Main Account ID when this account is a Sub Account and lineage is known.
- User-facing account label.
- Binance account identity reference.
- Redacted account display hint.
- Credential Reference ID.
- Credential lifecycle state.
- Spot permission status.
- Futures permission status.
- Withdrawal permission warning state.
- Connectivity status.
- Last validation timestamp.
- Last permission snapshot reference.
- Removal status.
- Created timestamp.
- Updated timestamp.
- Removed timestamp when applicable.

### Relationships

- Account may have many Sub Account profiles.
- Account may have many Bot Instances.
- Account has one active Credential Reference.
- Account may have many Account Permission Snapshots.
- Account may have many Capital Reservations through Bot Instances.
- Account may have many Orders, Positions, Trades, and Log Entries through Bot Instances.
- Account may have Error Records.
- Account may participate in Recovery Sessions and Recovery Details.

## Sub Account

### Purpose

Represents Sub Account-specific metadata, lineage, and display context for an Account whose account type is Sub Account.

### Responsibilities

- Preserve Sub Account product language for the UI and flows.
- Link a Sub Account context to a parent Main Account when known.
- Store non-secret Sub Account metadata.
- Prevent ambiguity between Main Account and Sub Account trading contexts.
- Support permission validation and troubleshooting for Sub Account connections.

### Important Attributes

- Sub Account profile ID.
- Account Context ID.
- Parent Main Account ID when available.
- Sub Account label.
- Binance Sub Account identity reference.
- Redacted Sub Account display hint.
- Permission status summary.
- Connectivity status summary.
- Created timestamp.
- Updated timestamp.
- Removed or inactive flag.

### Relationships

- Sub Account profile belongs to one Account Context with account type Sub Account.
- Sub Account profile may reference one parent Main Account.
- Bot Instances reference the Account Context, not the Sub Account profile directly.
- Sub Account profile may have related Log Entries and Error Records through its Account Context.

## Credential Reference

### Purpose

Represents the SQLite-safe reference to credentials stored outside SQLite.

### Responsibilities

- Store only opaque secure-storage references.
- Track credential lifecycle state.
- Support credential rotation.
- Support recoverable credential deletion during account removal.
- Provide redacted display hints without exposing secret material.

### Important Attributes

- Credential Reference ID.
- Account ID.
- Secure storage provider name.
- Opaque secure storage reference.
- Redacted display hint.
- Credential status.
- Lifecycle state: Active, Rotation Pending, Removal Pending, Removed, Delete Failed.
- Last verified timestamp.
- Deletion requested timestamp when applicable.
- Deletion completed timestamp when applicable.
- Failure reason when deletion fails.

### Relationships

- Credential Reference belongs to one Account.
- Credential Reference is used by Account Service and Secure Storage Provider.
- Credential Reference may have related Error Records and Log Entries.
- Credential Reference must never store raw API keys or API secrets.

## Account Permission Snapshot

### Purpose

Preserves the account permission and exchange access state observed at validation time or bot start time.

### Responsibilities

- Store the permission context used when a bot starts.
- Support troubleshooting after Binance permissions change.
- Preserve Spot and Futures capability status.
- Record withdrawal permission warning state without storing secrets.
- Support recovery validation after restart or reconnect.

### Important Attributes

- Account Permission Snapshot ID.
- Account ID.
- Validation trigger.
- Spot permission status.
- Futures permission status.
- Withdrawal permission warning state.
- Account identity verification status.
- API trading permission status.
- Read permission status.
- Market access result.
- Validation timestamp.
- Validation result.
- Failure reason when applicable.

### Relationships

- Account Permission Snapshot belongs to one Account.
- Bot Instance may reference the snapshot used at start.
- Configuration Snapshot may reference the effective permission snapshot.
- Recovery Detail may reference permission snapshots used during reconciliation.

## Bot Instance

### Purpose

Represents one configured automated trading bot runtime.

### Responsibilities

- Own bot lifecycle state.
- Own the selected Account Context.
- Own selected market mode and trading pair.
- Own capital allocation.
- Own active Strategy Configuration.
- Own active Risk Configuration.
- Own active Configuration Snapshot.
- Own runtime state required for start, stop, and recovery.
- Own order, position, trade, and recovery relationships.
- Act as a future-ready ownership boundary while Version 1 supports one configured bot experience and prevents duplicate active runtimes.

### Important Attributes

- Bot Instance ID.
- Bot name or label.
- Account Context ID.
- Market mode: Spot or Futures.
- Trading pair.
- Runtime status.
- Lifecycle status.
- Setup completion status.
- Capital allocation reference.
- Active Capital Reservation ID.
- Active Strategy Configuration ID.
- Active Risk Configuration ID.
- Active Configuration Snapshot ID.
- Last known account permission snapshot reference.
- Last start timestamp.
- Last stop timestamp.
- Last heartbeat timestamp.
- Stop requested flag.
- Recovery required flag.
- Unresolved work flag.
- Last clean worker shutdown marker.
- Created timestamp.
- Updated timestamp.
- Archived or inactive flag.

### Relationships

- Bot Instance belongs to exactly one Account Context.
- Bot Instance has one active Strategy Configuration.
- Bot Instance has one active Risk Configuration.
- Bot Instance has one active Configuration Snapshot when ready to run.
- Bot Instance has one active Capital Reservation when configured or running.
- Bot Instance may have many Positions over time.
- Bot Instance may have many Orders.
- Bot Instance may have many Trades.
- Bot Instance may have many Bot State History records.
- Bot Instance may have many Stop Requests.
- Bot Instance may have many Recovery Sessions.
- Bot Instance may have many Error Records.
- Bot Instance may have many Log Entries.

## Bot State History

### Purpose

Stores operational lifecycle transitions for a Bot Instance.

This is not event sourcing. It is a compact operational history for diagnostics, support, and recovery investigation.

### Responsibilities

- Record bot state changes.
- Preserve start, stop, disconnected, error, recovery, and sync-required transitions.
- Link state changes to errors or recovery sessions when relevant.
- Support Dashboard and support diagnostics.

### Important Attributes

- Bot State History ID.
- Bot Instance ID.
- Previous state.
- New state.
- Transition reason.
- User action reference when applicable.
- Related Stop Request ID when applicable.
- Related Recovery Session ID when applicable.
- Related Error Record ID when applicable.
- Created timestamp.

### Relationships

- Bot State History belongs to one Bot Instance.
- Bot State History may reference Stop Request.
- Bot State History may reference Recovery Session.
- Bot State History may reference Error Record.
- Bot State History may have related Log Entries.

## Strategy Configuration

### Purpose

Stores the configurable parameters for the single built-in proprietary strategy.

### Responsibilities

- Identify the built-in strategy assigned to a Bot Instance.
- Preserve the strategy version.
- Preserve user-configurable strategy parameters.
- Prevent user-created or user-edited strategy logic.
- Provide input to Configuration Snapshots.

### Important Attributes

- Strategy Configuration ID.
- Bot Instance ID.
- Strategy name.
- Strategy version.
- RSI entry parameter reference.
- ATR take-profit parameter reference.
- DCA position-management parameter reference.
- Active flag.
- Validation status.
- Created timestamp.
- Updated timestamp.
- Superseded timestamp when applicable.

### Relationships

- Strategy Configuration belongs to one Bot Instance.
- Strategy Configuration is referenced by Configuration Snapshot.
- Strategy Configuration is used by the Strategy Engine.
- Orders and Trades reference Configuration Snapshot rather than relying only on the current Strategy Configuration.

## Risk Configuration

### Purpose

Stores risk settings used to validate bot startup and trading actions.

### Responsibilities

- Define user-configured risk controls.
- Support Spot and Futures risk validation.
- Support account-level exposure checks for the active Bot Instance and selected Account Context.
- Prevent bot start when risk settings are invalid.
- Provide input to Configuration Snapshots.
- Preserve risk versioning for historical orders and trades.

### Important Attributes

- Risk Configuration ID.
- Bot Instance ID.
- Capital allocation reference.
- Maximum active exposure reference.
- Maximum order size reference.
- DCA limit settings.
- Maximum DCA depth.
- Stop conditions.
- Futures leverage guardrail.
- Futures margin mode requirement.
- Futures liquidation-risk threshold.
- Reduce-only requirement for Futures exits.
- Risk profile status.
- Active flag.
- Last validation timestamp.
- Created timestamp.
- Updated timestamp.
- Superseded timestamp when applicable.

### Relationships

- Risk Configuration belongs to one Bot Instance.
- Risk Configuration is referenced by Configuration Snapshot.
- Risk Configuration is used by Risk Engine.
- Risk Configuration validates Capital Reservation.
- Orders and Trades reference Configuration Snapshot rather than relying only on the current Risk Configuration.

## Configuration Snapshot

### Purpose

Represents an immutable record of the effective bot configuration used for startup, order creation, trade history, and recovery.

### Responsibilities

- Preserve historical configuration context.
- Prevent later edits from changing the meaning of historical trades.
- Link orders and trades to the effective strategy version, risk settings, account context, market mode, trading pair, and capital allocation.
- Support auditability without exposing proprietary strategy internals.

### Important Attributes

- Configuration Snapshot ID.
- Bot Instance ID.
- Account Context ID.
- Account Permission Snapshot ID.
- Strategy Configuration ID.
- Risk Configuration ID.
- Exchange Capability reference.
- Snapshot reason: setup completed, bot start, settings edit, recovery correction.
- Strategy version.
- Risk configuration version reference.
- Market mode.
- Trading pair.
- Capital allocation reference.
- Futures margin mode requirement when applicable.
- Futures leverage reference when applicable.
- Snapshot status.
- Created timestamp.

### Relationships

- Configuration Snapshot belongs to one Bot Instance.
- Configuration Snapshot references one Account Context.
- Configuration Snapshot references one Strategy Configuration.
- Configuration Snapshot references one Risk Configuration.
- Configuration Snapshot may reference one Account Permission Snapshot.
- Configuration Snapshot may reference one Exchange Capability record.
- Order references the Configuration Snapshot effective at intent creation.
- Trade references the Configuration Snapshot effective for the user-visible trading activity.
- Recovery Detail may reference the Configuration Snapshot used during reconciliation.

## Capital Reservation

### Purpose

Represents capital allocated or reserved for the active Bot Instance to prevent the configured bot allocation from exceeding account resources.

### Responsibilities

- Track bot-level capital allocation.
- Support one active bot allocation for the selected Account Context in Version 1.
- Prevent configured allocations from exceeding account resources.
- Support startup validation.
- Support runtime risk checks.
- Release or invalidate capital safely when bot state changes.

### Important Attributes

- Capital Reservation ID.
- Bot Instance ID.
- Account Context ID.
- Market mode.
- Trading pair.
- Reserved capital reference.
- Reservation status: Draft, Active, Suspended, Release Pending, Released, Invalid.
- Validation timestamp.
- Last balance check timestamp.
- Created timestamp.
- Updated timestamp.
- Released timestamp when applicable.
- Release reason when applicable.

### Relationships

- Capital Reservation belongs to one Bot Instance.
- Capital Reservation belongs to one Account Context.
- Capital Reservation is validated by Risk Configuration.
- Capital Reservation is included in Configuration Snapshot.
- Capital Reservation may have Error Records when invalid or stale.

## Position

### Purpose

Represents current or historical market exposure for a Bot Instance.

For Spot, this represents inventory exposure or holdings controlled by the bot. For Futures, this represents a Futures position.

### Responsibilities

- Track active exposure for Position Monitoring.
- Track DCA progress.
- Track ATR take-profit progress.
- Support open position synchronization.
- Preserve recovery-relevant position state.
- Distinguish Spot exposure from Futures position state.
- Preserve recovery-created or recovery-corrected state.

### Important Attributes

- Position ID.
- Bot Instance ID.
- Account Context ID.
- Configuration Snapshot ID when available.
- Market mode.
- Trading pair.
- Exposure type.
- Position status.
- Direction.
- Quantity or exposure amount reference.
- Average entry reference.
- DCA progress state.
- Take-profit progress state.
- Spot holding reference when applicable.
- Futures margin mode when applicable.
- Futures leverage reference when applicable.
- Futures liquidation-risk reference when applicable.
- Source of truth marker: Local, Binance, Reconciled.
- Recovery-created flag.
- Recovery correction flag.
- Last synchronized timestamp.
- Created timestamp.
- Updated timestamp.
- Closed timestamp when applicable.

### Relationships

- Position belongs to one Bot Instance.
- Position belongs to one Account Context through Bot Instance.
- Position may be created by one or more filled entry Orders.
- Position may have many DCA Orders.
- Position may have many take-profit or exit Orders.
- Position may have many Order Executions through Orders.
- Position may have many Trades.
- Position may be reconciled by many Recovery Details.
- Position may have related Error Records and Log Entries.

## Order

### Purpose

Represents a bot-generated order intent and its lifecycle with Binance.

### Responsibilities

- Persist local order intent before exchange submission.
- Prevent duplicate submissions.
- Link the order to the bot action or strategy decision that produced it.
- Correlate local intent with Binance order identifiers.
- Track order lifecycle status.
- Support partial fills, cancellations, rejections, failures, and unknown states.
- Support order synchronization during recovery.

### Important Attributes

- Order ID.
- Bot Instance ID.
- Account Context ID.
- Configuration Snapshot ID.
- Bot action reference.
- Position ID when applicable.
- Market mode.
- Trading pair.
- Order purpose: Entry, DCA, Take Profit, Exit, Cancel, Recovery.
- Order side.
- Order type reference.
- Futures reduce-only flag when applicable.
- Order intent status.
- Exchange submission status.
- Client-side order reference.
- Binance order identifier.
- Quantity reference.
- Price reference.
- Filled quantity reference.
- Average fill price reference.
- Rejection reason.
- Failure reason.
- Unknown-status flag.
- User review required flag.
- Created timestamp.
- Submitted timestamp.
- Last synchronized timestamp.
- Finalized timestamp when applicable.

### Relationships

- Order belongs to one Bot Instance.
- Order belongs to one Account Context through Bot Instance.
- Order references one Configuration Snapshot.
- Order may reference one Position.
- Order may have many Order Executions / Fills.
- Order may produce one or many Trade summaries.
- Order may be reconciled by many Recovery Details.
- Order may have related Error Records and Log Entries.

## Order Execution / Fill

### Purpose

Represents one exchange execution or fill associated with an Order.

### Responsibilities

- Store partial fill facts.
- Store exchange execution timestamps.
- Preserve executed quantity, price, and fee references.
- Support recovery-discovered fills.
- Separate precise exchange execution data from user-facing Trade History.

### Important Attributes

- Order Execution ID.
- Order ID.
- Bot Instance ID.
- Account Context ID.
- Position ID when known.
- Trade ID when summarized.
- Binance execution identifier when available.
- Execution status.
- Executed quantity reference.
- Executed price reference.
- Fee reference.
- Fee asset reference.
- Liquidity role reference when available.
- Exchange event timestamp.
- Discovered during recovery flag.
- Created timestamp.

### Relationships

- Order Execution belongs to one Order.
- Order Execution belongs to one Bot Instance through Order.
- Order Execution may relate to one Position.
- One or many Order Executions may be summarized by one Trade.
- Order Execution may be created or corrected by Recovery Detail.

## Trade

### Purpose

Represents user-reviewable trading activity generated by the bot.

Trade is the product-facing history record. It is not the raw execution ledger.

### Responsibilities

- Support the Trade History screen.
- Summarize completed and attempted bot activity.
- Distinguish successful, failed, canceled, rejected, partially filled, unknown, blocked, and recovery-corrected activity.
- Link user-visible activity to Orders, Executions, Positions, and Configuration Snapshots.
- Preserve enough information for support without exposing proprietary strategy internals.

### Important Attributes

- Trade ID.
- Bot Instance ID.
- Account Context ID.
- Configuration Snapshot ID.
- Order ID when applicable.
- Position ID when applicable.
- Recovery Session ID when applicable.
- Market mode.
- Trading pair.
- Trade status.
- Trade event category.
- Entry or exit classification.
- Quantity reference.
- Price reference.
- Fee summary reference when available.
- Realized result reference when available.
- Recovery correction flag.
- User-visible summary.
- Created timestamp.
- Exchange event timestamp when available.

### Relationships

- Trade belongs to one Bot Instance.
- Trade belongs to one Account Context through Bot Instance.
- Trade references one Configuration Snapshot when available.
- Trade is usually produced by one Order.
- Trade may summarize one or many Order Executions.
- Trade may relate to one Position.
- Trade may be associated with one Recovery Session or Recovery Detail.
- Trade may have related Log Entries.

## Stop Request

### Purpose

Represents a durable request to stop a Bot Instance.

### Responsibilities

- Persist Stop Bot intent.
- Block new strategy actions after stop is requested.
- Track cancellation of app-owned unfilled entry and DCA orders.
- Track protective or reduce-only orders that remain active.
- Support stop recovery after disconnect, restart, or crash.

### Important Attributes

- Stop Request ID.
- Bot Instance ID.
- Account Context ID.
- Request status.
- Requested timestamp.
- Requested by user flag.
- New strategy actions blocked flag.
- Orders requiring cancellation summary.
- Cancellation result summary.
- Protective orders remaining summary.
- Related Recovery Session ID when applicable.
- Completed timestamp when applicable.
- Failure reason when applicable.

### Relationships

- Stop Request belongs to one Bot Instance.
- Stop Request may reference many Orders through Recovery Details.
- Stop Request may be reconciled by one or more Recovery Sessions.
- Stop Request may create Bot State History records.
- Stop Request may have related Error Records and Log Entries.

## Recovery Session

### Purpose

Represents a recovery or synchronization run after restart, crash, reconnect, unknown order status, stop-request interruption, or position mismatch.

### Responsibilities

- Track recovery lifecycle.
- Coordinate open position synchronization.
- Coordinate order synchronization.
- Coordinate stop request reconciliation.
- Refresh and validate exchange capability before resume.
- Record recovery outcomes.
- Support user-facing recovery status and state restoration.

### Important Attributes

- Recovery Session ID.
- Recovery trigger.
- Recovery status.
- Bot Instance ID when applicable.
- Account Context ID when applicable.
- Market mode when applicable.
- Trading pair when applicable.
- Started timestamp.
- Completed timestamp.
- Position sync result.
- Order sync result.
- Stop request sync result.
- Risk revalidation result.
- Exchange capability validation result.
- User review required flag.
- Failure reason.

### Relationships

- Recovery Session may belong to one Bot Instance.
- Recovery Session may reference one Account Context.
- Recovery Session has many Recovery Details.
- Recovery Session may reference many Orders through Recovery Details.
- Recovery Session may reference Positions through Recovery Details.
- Recovery Session may update Trades as recovery corrections.
- Recovery Session may resolve or create Error Records.
- Recovery Session may have many Log Entries.

## Recovery Detail

### Purpose

Represents one item reconciled during a Recovery Session.

### Responsibilities

- Track detailed synchronization outcomes.
- Store before-and-after reconciliation summaries.
- Identify mismatches between local state and Binance state.
- Preserve user review requirements.
- Avoid overloading Recovery Session with item-level detail.

### Important Attributes

- Recovery Detail ID.
- Recovery Session ID.
- Item type: Order, Position, Stop Request, Account Permission, Exchange Capability, Trade, Capital Reservation.
- Related entity reference.
- Previous local state summary.
- Binance observed state summary.
- Resulting local correction summary.
- Source of truth marker.
- Reconciliation result.
- User review required flag.
- Correction reason.
- Created timestamp.

### Relationships

- Recovery Detail belongs to one Recovery Session.
- Recovery Detail may reference Order.
- Recovery Detail may reference Position.
- Recovery Detail may reference Stop Request.
- Recovery Detail may reference Trade.
- Recovery Detail may reference Account Permission Snapshot.
- Recovery Detail may reference Exchange Capability.
- Recovery Detail may create or update Error Records.
- Recovery Detail may have related Log Entries.

## Exchange Capability

### Purpose

Represents cached Binance market and symbol rules needed to validate pair selection and order intent.

### Responsibilities

- Support trading pair validation.
- Support Spot and Futures capability differences.
- Support precision and minimum-order validation.
- Identify unsupported or suspended trading pairs.
- Support recovery when exchange rules change.

### Important Attributes

- Exchange Capability ID.
- Exchange name.
- Market mode.
- Trading pair.
- Trading status.
- Symbol availability.
- Quantity precision reference.
- Price precision reference.
- Minimum order reference.
- Minimum notional reference.
- Supported order-type reference.
- Futures-specific capability reference when applicable.
- Last refreshed timestamp.
- Validation status.

### Relationships

- Exchange Capability may be referenced by Configuration Snapshot.
- Exchange Capability is used by Risk Configuration validation.
- Exchange Capability is used by Order validation.
- Exchange Capability may be referenced by Recovery Detail.
- Exchange Capability may have related Error Records and Log Entries.

## Application Settings

### Purpose

Stores local application preferences and global application state that are not specific to a single bot.

### Responsibilities

- Store setup completion state.
- Store application preferences.
- Store application configuration version.
- Store app-level clean-shutdown marker.
- Store current startup route hints.
- Store diagnostic preferences.
- Reference active license state where needed for startup routing.

### Important Attributes

- Application Settings ID.
- Application configuration version.
- Setup completion status.
- Setup draft status.
- Last opened timestamp.
- App-level clean-shutdown marker.
- Last startup route.
- Active license reference when applicable.
- Default Bot Instance ID when applicable.
- Diagnostic export preference.
- UI preference reference.
- Created timestamp.
- Updated timestamp.

### Relationships

- Application Settings may reference the active License.
- Application Settings may reference the default Bot Instance.
- Application Settings is used by Startup Coordinator and Recovery Coordinator.
- Application Settings may have related Log Entries.

## License

### Purpose

Represents local Offline License File validation state for the one-time purchase lifetime license model.

### Responsibilities

- Track offline license file validation status.
- Track redacted license file reference state.
- Support startup routing.
- Support License Management screen.
- Block bot startup when invalid.
- Preserve local validation history without requiring network access.
- Avoid storing full license file content, full license keys, or sensitive license material.

### Important Attributes

- License ID.
- License status.
- Redacted license reference.
- Device binding reference.
- Secure entitlement reference when required.
- Activation timestamp.
- Last validation timestamp.
- Next validation requirement.
- Grace status.
- Grace expiry reference when applicable.
- Failure reason.
- Active flag.
- Created timestamp.
- Updated timestamp.

### Relationships

- Exactly one License should be active for the application at a time.
- License may have many License Validation History records.
- License may be referenced by Application Settings for startup routing.
- License may have Error Records.
- License may have related Log Entries.
- License does not own Accounts or Bot Instances, but invalid license state blocks new bot starts and may stop new strategy actions after safe synchronization.

## License Validation History

### Purpose

Stores compact history of license validation attempts for support and startup diagnostics.

### Responsibilities

- Track validation attempts without storing full license keys.
- Preserve validation outcome and reason.
- Support grace-state troubleshooting.
- Support License Management screen diagnostics.

### Important Attributes

- License Validation History ID.
- License ID.
- Validation trigger.
- Validation status.
- Grace status after validation.
- Redacted validation reference.
- Failure reason when applicable.
- Created timestamp.

### Relationships

- License Validation History belongs to one License.
- License Validation History may create Error Records.
- License Validation History may have related Log Entries.

## Error Record

### Purpose

Represents an active or historical user-facing error state.

Error Record is separate from Log Entry. Logs are diagnostic; Error Records drive screens, retry actions, recovery routing, and bot state impact.

### Responsibilities

- Track unresolved errors.
- Map errors to user-facing messages.
- Track retry policy.
- Track whether recovery is required.
- Track whether bot operation is blocked.
- Support Error / Connection Issue screen.

### Important Attributes

- Error Record ID.
- Error category.
- Error severity.
- User-facing summary.
- Technical support reference.
- Account Context ID when applicable.
- Bot Instance ID when applicable.
- Order ID when applicable.
- Position ID when applicable.
- Recovery Session ID when applicable.
- License ID when applicable.
- Retry policy.
- Blocking flag.
- Recovery required flag.
- Resolution status.
- Created timestamp.
- Resolved timestamp when applicable.

### Relationships

- Error Record may reference Account.
- Error Record may reference Bot Instance.
- Error Record may reference Order.
- Error Record may reference Position.
- Error Record may reference Recovery Session.
- Error Record may reference License.
- Error Record may create Bot State History records.
- Error Record may have related Log Entries.

## Log Entry

### Purpose

Represents redacted diagnostic and operational log records stored in SQLite.

### Responsibilities

- Support troubleshooting.
- Record lifecycle transitions.
- Record account validation outcomes.
- Record bot start and stop events.
- Record order and recovery issues.
- Preserve support-safe references.
- Avoid storing trading-critical facts only in logs.

### Important Attributes

- Log Entry ID.
- Severity.
- Category.
- Message summary.
- Support reference.
- Account Context ID when applicable.
- Bot Instance ID when applicable.
- Order ID when applicable.
- Trade ID when applicable.
- Recovery Session ID when applicable.
- Error Record ID when applicable.
- Diagnostic Export ID when included in export.
- Redaction status.
- Created timestamp.

### Relationships

- Log Entry may reference Account.
- Log Entry may reference Bot Instance.
- Log Entry may reference Order.
- Log Entry may reference Trade.
- Log Entry may reference Recovery Session.
- Log Entry may reference Error Record.
- Log Entry may be included in Diagnostic Export.
- Log Entry must not contain raw API keys, raw API secrets, full license keys, or sensitive account identifiers without redaction.

## Diagnostic Export

### Purpose

Represents a user-initiated diagnostic export for support.

### Responsibilities

- Track diagnostic export creation.
- Record export date range.
- Record redaction status.
- Record user consent.
- Avoid ambiguity around privacy and support workflows.

### Important Attributes

- Diagnostic Export ID.
- Export status.
- Export requested timestamp.
- Export completed timestamp.
- Included date range.
- Included categories.
- Redaction policy applied.
- User consent flag.
- Support reference.
- Failure reason when applicable.

### Relationships

- Diagnostic Export may include many Log Entries.
- Diagnostic Export may include redacted summaries of Error Records.
- Diagnostic Export must not include raw credentials, full license keys, or sensitive account identifiers without redaction.

## 4. Entity Relationships

## Relationship Summary

| Relationship | Cardinality | Final Rule |
|---|---:|---|
| Account to Sub Account profile | One to zero or many | A Main Account may be related to Sub Account profiles for lineage and display. |
| Account Context to Bot Instance | One to many | Each Bot Instance references exactly one Account Context. |
| Account to Credential Reference | One to one active, many over time | One active credential reference is used for trading; old references may remain for lifecycle audit until removed. |
| Account to Account Permission Snapshot | One to many | Snapshots preserve validation history and start-time permission state. |
| Bot Instance to Strategy Configuration | One to one active, many over time | Only one active strategy configuration per bot. |
| Bot Instance to Risk Configuration | One to one active, many over time | Only one active risk configuration per bot. |
| Bot Instance to Configuration Snapshot | One to many | Snapshots are immutable historical configuration contexts. |
| Bot Instance to Capital Reservation | One to one active, many over time | Only one active reservation per bot. |
| Bot Instance to Bot State History | One to many | Captures operational state transitions. |
| Bot Instance to Stop Request | One to many | Usually zero or one active unresolved stop request. |
| Bot Instance to Position | One to many over time | Usually one active exposure per bot and pair, with historical positions retained. |
| Bot Instance to Order | One to many | Orders are bot-owned for idempotency and recovery. |
| Order to Order Execution / Fill | One to many | One order can fill in multiple parts. |
| Order to Trade | One to many | One order may produce multiple user-visible trade summaries when needed. |
| Position to Order | One to many | Entry, DCA, and take-profit orders may attach to a position once known. |
| Position to Trade | One to many | Trades affect or summarize position state. |
| Recovery Session to Recovery Detail | One to many | Each reconciled item is stored as a detail record. |
| Recovery Detail to Order / Position / Stop Request | Many to one optional | Details identify the item reconciled. |
| License to License Validation History | One to many | Validation attempts are stored compactly and redacted. |
| Error Record to domain entities | Many to one optional | Error Records drive user-facing error and retry state. |
| Domain entities to Log Entry | One to many optional | Logs use support-safe references and redacted content. |
| Diagnostic Export to Log Entry | One to many | Export includes redacted log records by user consent. |

## Critical Relationship Clarifications

### Account, Sub Account, And Bot Instance

- Bot Instance must reference `Account Context ID`.
- Account Context can be Main Account or Sub Account.
- Sub Account profile is not an independent bot target.
- Parent Main Account reference is informational and validation-related.
- Credential ownership belongs to the Account Context used for trading.

### Position, Order, Execution, And Trade

- Order can exist before Position.
- Position can be created after a filled entry order.
- Position can also be created during recovery if Binance shows exposure that local state did not know about.
- Order Execution / Fill belongs to Order.
- Trade summarizes user-visible activity and may reference one Order and one Position.
- Trade should not be used as the only source of exact partial-fill facts.

### Configuration Snapshot And Historical Records

- Active Strategy Configuration and Risk Configuration may change over time.
- Configuration Snapshot is immutable.
- Order references the Configuration Snapshot active when the order intent was created.
- Trade references the Configuration Snapshot relevant to the user-visible activity.
- Recovery Detail may reference the snapshot used to validate restored state.

### License And Application Settings

- The application should have exactly one active License record.
- Application Settings may reference the active License for startup routing.
- License validation history belongs to License.
- Sensitive license entitlement material should not be stored directly in SQLite.

### Logs And Error Records

- Error Record is product state.
- Log Entry is diagnostic state.
- Trading-critical facts belong in Orders, Executions, Positions, Trades, Recovery Details, or Error Records.
- Logs may reference domain records but must not be the only place where critical trading facts exist.

## 5. Aggregate Boundaries

## Account Aggregate

### Aggregate Root

Account.

### Includes

- Account metadata.
- Sub Account profile metadata.
- Credential Reference.
- Account permission state.
- Account Permission Snapshot.

### Consistency Rules

- Raw credentials are outside SQLite.
- Account identity must distinguish Main Account and Sub Account contexts.
- Exactly one active Credential Reference should exist for an active Account Context.
- Account replacement requires revalidation.
- Account removal is recoverable and must coordinate Credential Reference lifecycle state.
- Account removal invalidates or archives affected Bot Instances before the account becomes fully removed.
- Account identity references are sensitive non-secret data and must be redacted in logs and exports.

## Bot Instance Aggregate

### Aggregate Root

Bot Instance.

### Includes

- Bot lifecycle state.
- Bot State History.
- Stop Request.
- Active Strategy Configuration reference.
- Active Risk Configuration reference.
- Active Configuration Snapshot reference.
- Capital Reservation.
- Runtime recovery flags.

### Consistency Rules

- Bot startup requires valid license, account, credentials, permissions, configuration, risk settings, exchange capability, and capital reservation.
- Risk settings cannot be changed while a bot is running.
- A duplicate active or running bot for the same Account Context, market mode, and trading pair is not allowed.
- One active Strategy Configuration is allowed per Bot Instance.
- One active Risk Configuration is allowed per Bot Instance.
- One active Capital Reservation is allowed per Bot Instance.
- Stop requested state must block new strategy actions until resolved.
- Per-bot unresolved work markers must survive restart.

## Configuration Aggregate

### Aggregate Root

Configuration Snapshot.

### Includes

- Strategy Configuration reference.
- Risk Configuration reference.
- Account Permission Snapshot reference.
- Exchange Capability reference.
- Market mode.
- Trading pair.
- Capital allocation reference.

### Consistency Rules

- Configuration Snapshot is immutable once created.
- Orders and Trades must reference the effective Configuration Snapshot.
- Failed configuration edits must not destroy the last known valid snapshot.
- Draft setup configuration must never enable bot startup.

## Order Aggregate

### Aggregate Root

Order.

### Includes

- Local order intent.
- Bot action reference.
- Exchange correlation.
- Submission state.
- Unknown-state marker.
- Order Execution / Fill records.
- Rejection, failure, cancellation, and finalization state.

### Consistency Rules

- Order intent must be persisted before exchange submission.
- Unknown order state blocks duplicate submission for the same bot action.
- Retry after timeout must synchronize first rather than blindly submit a new order.
- Order result and related executions should be persisted together.
- Trade summaries should be updated consistently with order result and execution facts.

## Position Aggregate

### Aggregate Root

Position.

### Includes

- Spot exposure or Futures position state.
- DCA progress.
- Take-profit progress.
- Source-of-truth marker.
- Synchronization state.
- Recovery correction flags.

### Consistency Rules

- Spot exposure and Futures position state must remain distinct.
- Futures position state must preserve margin mode, leverage reference, and liquidation-risk reference.
- Position state must be reconciled after restart, crash, reconnect, or unknown order resolution.
- Binance state is treated as operational reality during reconciliation, with before-and-after correction detail persisted.

## Trade History Aggregate

### Aggregate Root

Trade.

### Includes

- User-visible trading activity.
- Order result summary.
- Execution summary.
- Recovery correction flag.
- Historical status.
- User-facing summary.

### Consistency Rules

- Trade History must distinguish filled, partially filled, canceled, rejected, failed, unknown, blocked, and recovery-corrected outcomes.
- Recovery corrections should not silently erase previous trade history.
- Trade History should be readable without exposing strategy internals.
- Exact execution facts belong to Order Execution / Fill.

## Recovery Aggregate

### Aggregate Root

Recovery Session.

### Includes

- Recovery trigger.
- Recovery status.
- Recovery Detail records.
- Position synchronization result.
- Order synchronization result.
- Stop request reconciliation result.
- Risk revalidation result.
- Exchange capability validation result.
- User review requirement.

### Consistency Rules

- Recovery must block bot resume until required checks pass.
- Unknown order status remains visible until resolved.
- Each reconciled order, position, stop request, permission check, and capability check should have a Recovery Detail when material.
- Recovery outcomes must be persisted before the app reports restored state.
- User review requirement must be durable and visible after restart.

## License Aggregate

### Aggregate Root

License.

### Includes

- Activation state.
- Local entitlement state.
- Grace state.
- Validation state.
- License Validation History.

### Consistency Rules

- Exactly one active License should exist.
- Invalid license blocks new bot starts.
- License invalidation should stop new strategy actions after safe synchronization.
- Full license keys and sensitive entitlement tokens must not be stored in SQLite.
- Validation failures must be redacted in logs and exports.

## Application Settings Aggregate

### Aggregate Root

Application Settings.

### Includes

- Setup completion state.
- Setup draft status.
- Application configuration version.
- App-level clean-shutdown marker.
- Startup route hints.
- Local preferences.
- Diagnostic preferences.

### Consistency Rules

- App-level clean-shutdown marker must not replace per-bot unresolved work markers.
- Draft setup state must not enable bot startup.
- Application configuration version must support future upgrades.
- Application Settings should reference, not own, active License and default Bot Instance.

## Diagnostics Aggregate

### Aggregate Roots

- Error Record.
- Log Entry.
- Diagnostic Export.

### Includes

- User-facing error state.
- Redacted diagnostic log records.
- Export metadata.
- Redaction status.
- User consent state.

### Consistency Rules

- Error Records drive user-facing error state and retry actions.
- Logs are bounded diagnostic records.
- Diagnostic exports require redaction and user consent.
- Logs and exports must not include raw credentials, full license keys, or sensitive account identity values without redaction.

## Exchange Capability Aggregate

### Aggregate Root

Exchange Capability.

### Includes

- Market mode.
- Trading pair.
- Trading status.
- Precision references.
- Minimum-order references.
- Supported order-type references.
- Last refresh and validation state.

### Consistency Rules

- Pair validation must use fresh-enough capability data before bot start.
- Recovery must refresh capability data before resume when stale or when Binance rejects an order due to symbol rules.
- Unsupported or suspended pairs must block Start Bot and new order submission.

## 6. Data Ownership

| Data Area | Owning Domain | Write Authority | Read Consumers |
|---|---|---|---|
| Account metadata | Account Context | Account Service | Dashboard, Account Management, Setup Wizard, Recovery |
| Sub Account profile | Account Context | Account Service | Account Management, Setup Wizard, Dashboard |
| Credential reference | Account Context | Account Service and Secure Storage Provider | Account Service only |
| Account permission snapshot | Account Context | Account Validation Service | Bot Startup, Recovery, Diagnostics |
| Bot lifecycle state | Bot Context | Bot Control Service and Bot Instance Manager | Dashboard, Recovery, Logging |
| Bot state history | Bot Context | Bot Control Service and Recovery Coordinator | Dashboard, Diagnostics |
| Stop request | Bot Context | Bot Control Service and Recovery Coordinator | Dashboard, Recovery, Error Screen |
| Strategy configuration | Strategy Context | Setup Wizard and Configuration Service | Bot Runtime, Review Configuration |
| Risk configuration | Risk Context | Risk Settings Service | Bot Runtime, Dashboard, Review Configuration |
| Configuration snapshot | Strategy and Risk Context | Configuration Service | Order Manager, Trade History, Recovery |
| Capital reservation | Bot and Risk Context | Bot Resource Coordinator | Bot Startup, Risk Engine, Dashboard |
| Position state | Trading Context | Position Manager and Recovery Coordinator | Dashboard, Position Monitoring, Recovery |
| Order state | Trading Context | Order Manager and Recovery Coordinator | Trade History, Recovery, Logging |
| Order execution / fill | Trading Context | Order Manager and Recovery Coordinator | Trade History, Position Monitoring, Recovery |
| Trade history | Trading Context | Trade History Service | Trade History Screen, Dashboard, Diagnostics |
| Recovery session | Recovery Context | Recovery Coordinator | Startup, Dashboard, Error Screen, Logging |
| Recovery detail | Recovery Context | Recovery Coordinator | Recovery, Trade History, Diagnostics |
| License state | Licensing Context | License Service | Startup, Dashboard, License Management, Bot Startup |
| License validation history | Licensing Context | License Service | License Management, Diagnostics |
| Application settings | Application Context | Settings Service and Startup Coordinator | Startup, Navigation, UI Shell |
| Error records | Diagnostics Context | Domain Services and Error Handler | Error Screen, Dashboard, Recovery |
| Log entries | Diagnostics Context | Logging Provider | Diagnostics, Support Export |
| Diagnostic exports | Diagnostics Context | Diagnostics Service | Support Export |
| Exchange capability cache | Trading Infrastructure Context | Exchange Capability Adapter | Setup, Risk Engine, Order Manager, Recovery |

## 7. Persistence Strategy

### SQLite Role

SQLite is the durable local database for non-secret product state. It supports:

- Startup routing.
- Setup persistence.
- Bot lifecycle restoration.
- Multiple account metadata.
- Main Account and Sub Account contexts.
- One active Bot Instance boundary for Version 1, with future-ready identity and state history.
- Configuration snapshots.
- Capital reservations.
- Trade history.
- Position monitoring.
- Order tracking.
- Order execution tracking.
- Recovery synchronization.
- License state.
- Error records.
- Structured diagnostic logs.

### Repository Boundaries

Repository boundaries should align with aggregates:

- Account Repository.
- Credential Reference Repository.
- Account Permission Snapshot Repository.
- Bot Instance Repository.
- Bot State History Repository.
- Configuration Repository.
- Capital Reservation Repository.
- Order Repository.
- Order Execution Repository.
- Position Repository.
- Trade History Repository.
- Stop Request Repository.
- Recovery Repository.
- License Repository.
- Application Settings Repository.
- Error Repository.
- Log Repository.
- Diagnostic Export Repository.
- Exchange Capability Repository.

These are conceptual boundaries only.

### Write Coordination

All writes should pass through a persistence coordination layer.

Reasons:

- Bot workers run outside the UI thread.
- Bot workers, recovery, synchronization, and UI-triggered saves may contend for writes even when Version 1 has one active bot.
- SQLite allows many readers but limited concurrent writes.
- Trading state must remain consistent for recovery.
- Order intent, order result, execution facts, position changes, and trade history must not drift apart.

### Transaction Boundaries

Database design should preserve atomic boundaries for:

- Completed setup save.
- Account creation.
- Account credential replacement.
- Account removal state transition.
- Credential Reference lifecycle update.
- Account permission snapshot creation.
- Bot start transition.
- Bot stop request creation.
- Bot stop completion.
- Configuration snapshot creation.
- Capital reservation activation.
- Capital reservation release.
- Order intent creation.
- Order submission correlation.
- Order execution recording.
- Order result plus trade summary.
- Position update plus trade history.
- Recovery session creation.
- Recovery detail creation.
- Recovery completion.
- Error record creation and resolution.
- Offline license file validation update.
- License validation history creation.
- Application settings update.

### Data Integrity Rules

The later physical database design must support these conceptual rules:

- One active or running Bot Instance per Account Context, market mode, and trading pair.
- One active Strategy Configuration per Bot Instance.
- One active Risk Configuration per Bot Instance.
- One active Capital Reservation per Bot Instance.
- One active Configuration Snapshot used by a runnable Bot Instance.
- One active Credential Reference per Account Context.
- One active License for the application.
- One unresolved order intent per bot action reference.
- Unknown order state blocks duplicate submission for the same bot action reference.
- Account removal cannot complete while active Bot Instances depend on it.
- Credential deletion failure must leave a retryable state.
- Trade History must not depend on bounded diagnostic logs.

### Data Classification

| Data Class | Storage Rule |
|---|---|
| Raw Binance API key | Secure storage only, not SQLite |
| Raw Binance API secret | Secure storage only, not SQLite |
| Secure credential reference | SQLite allowed only as opaque non-secret reference |
| Redacted credential display hint | SQLite allowed |
| Binance account identity reference | SQLite allowed as sensitive non-secret data; redact in logs and exports |
| Full license key | Do not store in SQLite |
| Redacted license reference | SQLite allowed |
| Sensitive entitlement token | Secure storage preferred; SQLite only if explicitly approved and protected |
| Bot configuration | SQLite |
| Configuration snapshot | SQLite |
| Risk configuration | SQLite |
| Order, execution, trade history | SQLite |
| Position and exposure state | SQLite |
| Recovery state | SQLite |
| Error records | SQLite |
| Logs | SQLite structured logs with redaction and retention |
| Diagnostic export metadata | SQLite |

### Account Removal Strategy

Account removal must be recoverable because SQLite cannot guarantee that platform secure storage deletion succeeds.

Required lifecycle:

- Mark Account as removal requested.
- Stop or archive dependent Bot Instances.
- Mark Credential Reference as Removal Pending.
- Attempt secure credential deletion.
- If deletion succeeds, mark Credential Reference as Removed and Account as Removed.
- If deletion fails, mark Credential Reference as Delete Failed and keep the Account inactive until resolved.
- Surface unresolved deletion through Error Record.

### Capital Reservation Strategy

Capital Reservation must prevent allocation drift.

Rules:

- Reservation is validated before bot start.
- Reservation becomes active only after risk and account checks pass.
- Reservation is suspended when bot is disconnected or requires recovery.
- Reservation is released when bot is archived, removed, or the configuration no longer needs it.
- Reservation release should be durable before user-visible status changes.
- A stale or invalid reservation must create an Error Record or Recovery Detail.

## 8. Configuration Storage Strategy

### Configuration Categories

Configuration persistence must support:

- Application settings.
- Setup wizard draft state.
- Completed setup state.
- Account metadata and credential references.
- Account permission snapshots.
- Bot Instance configuration.
- Strategy Configuration.
- Risk Configuration.
- Configuration Snapshot.
- Capital Reservation.
- Market mode.
- Trading pair.
- Exchange Capability.
- License state.

### Draft Vs Completed Configuration

Draft configuration may be persisted during the first-run wizard.

Draft configuration must:

- Be clearly marked incomplete.
- Never enable Start Bot.
- Be recoverable after application restart.
- Be replaceable by a completed setup.
- Avoid creating active trading resources until validation succeeds.

Completed configuration must:

- Pass account validation.
- Pass credential validation.
- Pass permission validation.
- Pass license validation.
- Pass market mode validation.
- Pass trading pair validation.
- Pass exchange capability validation.
- Pass capital validation.
- Pass risk validation.
- Create or reference a Bot Instance.
- Create a Configuration Snapshot.

### Last Known Valid Configuration

The application must preserve the last known valid completed configuration when users edit account, capital, pair, or risk settings.

Failed validation must not destroy the prior working configuration. If a configuration edit fails, the active Configuration Snapshot remains unchanged and the failed validation is represented through Error Record and, where relevant, Log Entry.

### Configuration Snapshot Creation

A Configuration Snapshot should be created when:

- First setup completes.
- A bot starts after successful validation.
- Risk settings are successfully changed while the bot is not running.
- Market mode, pair, account, or capital settings are changed.
- Recovery requires a correction to the known valid configuration context.

Snapshots are immutable. New settings create a new snapshot rather than mutating the historical context used by previous orders and trades.

### Configuration Ownership

- Account settings belong to the Account Aggregate.
- Bot setup belongs to the Bot Instance Aggregate.
- Strategy settings belong to Strategy Configuration.
- Risk settings belong to Risk Configuration.
- Immutable effective configuration belongs to Configuration Snapshot.
- Global preferences belong to Application Settings.
- License state belongs to License.

## 9. Trade History Storage Strategy

### Trade History Goals

Trade history must support:

- Dashboard recent activity.
- Trade History screen.
- Recovery transparency.
- Order rejection visibility.
- Partial-fill visibility.
- Support diagnostics.
- User trust.

### Trade Records Should Capture

Trade records should capture product meaning:

- Bot Instance ownership.
- Account Context.
- Configuration Snapshot.
- Market mode.
- Trading pair.
- Related Order.
- Related Position when applicable.
- Related Recovery Session when corrected.
- Trade status.
- Trade category.
- Entry or exit classification.
- Quantity and price references.
- Fee summary reference when available.
- Realized result reference when available.
- Recovery correction flag.
- User-visible summary.
- Timestamps.

### Order Executions Should Capture

Order Execution / Fill records should capture exchange execution facts:

- Related Order.
- Related Position when known.
- Binance execution identifier when available.
- Executed quantity reference.
- Executed price reference.
- Fee reference.
- Fee asset reference.
- Exchange event timestamp.
- Recovery-discovered flag.

### Supported Trade Outcomes

Trade history must distinguish:

- Successful.
- Filled.
- Partially filled.
- Canceled.
- Rejected.
- Failed.
- Unknown.
- Blocked by risk.
- Blocked by license.
- Blocked by invalid configuration.
- Recovery corrected.

### Trade History And Recovery

Recovery may update or add trade history when:

- An unknown order is resolved.
- A partial fill is discovered.
- A rejected order was missed during outage.
- A local position differs from Binance reality.
- A recovered Binance position has no full local order history.
- A stop request is completed after reconnection.

Recovery corrections should be visible enough for support and user trust, but summarized in user-friendly language for the Trade History screen.

### Retention

Trade history should be retained locally unless the user removes application data or a future product requirement defines retention controls.

Diagnostic logs may be time or size bounded. Trade history, order history, execution history, and recovery detail are product records and should not follow short diagnostic log retention by default.

## 10. Recovery Data Strategy

### Recovery Goals

Recovery persistence must allow the application to answer:

- Was the last application shutdown clean?
- Was a specific bot worker cleanly stopped?
- Was a bot running before restart or crash?
- Was Stop Bot requested?
- Were new strategy actions blocked?
- Were there open or unknown orders?
- Were there partial fills?
- Was there open Spot exposure or a Futures position?
- Did exchange capability change?
- Did recovery complete?
- Is user review required?
- Can the bot safely resume?

### Recovery Data To Persist

Recovery strategy requires durable state for:

- App-level clean-shutdown marker.
- Per-bot clean worker shutdown marker.
- Last known bot status.
- Last known heartbeat.
- Unresolved work flag.
- Last known account validation state.
- Last known account permission snapshot.
- Last known exchange capability validation state.
- Last known open order state.
- Unknown order state.
- Order Execution / Fill records.
- Last known position or exposure state.
- Stop-request state.
- Recovery Session status.
- Recovery Detail records.
- User review required flag.
- Error Records.

### Startup Restoration Flow

On application startup:

1. Load Application Settings.
2. Check app-level clean-shutdown marker.
3. Load active License state.
4. Load Account metadata and Credential References.
5. Load Bot Instances.
6. Load per-bot runtime markers.
7. Load unresolved Stop Requests.
8. Load unresolved Orders and unknown order states.
9. Load active Positions or exposure state.
10. Determine whether recovery is required.
11. Refresh Exchange Capability when required.
12. Run order and position synchronization when required.
13. Create Recovery Session and Recovery Details for material reconciliation work.
14. Persist recovery outcome.
15. Show Dashboard, Setup, License, Error, or Sync Required state.

### Order Recovery Rules

- Unknown orders must block duplicate order submission for the same bot action.
- Order synchronization must attempt to correlate local order intent with Binance order records.
- Partial fills must update Order, Order Execution / Fill, Position, and Trade History as applicable.
- Rejections must be visible in Trade History or Error Record depending on user impact.
- Missing exchange order after local intent must be recorded in Recovery Detail.
- Blind retry after timeout or unknown status is not allowed.

### Position Recovery Rules

- Spot exposure must be restored as Spot inventory exposure.
- Futures positions must be restored with Futures-specific state.
- Position mismatch must create Recovery Detail with before-and-after summaries.
- Binance state is treated as operational reality during reconciliation.
- Bot resume is allowed only after risk revalidation.
- Recovered positions without local orders must be marked as recovery-created or recovery-corrected.
- User review is required when reconciliation changes material exposure, order status, or risk state.

### Stop Request Recovery

If Stop Bot was requested while disconnected, during shutdown, or during a crash:

- The Stop Request must be restored on startup.
- The bot must remain blocked from new strategy actions.
- App-owned unfilled entry and DCA orders should be canceled where supported after reconnection.
- Protective take-profit or reduce-only orders should be identified.
- Cancellation outcomes should be recorded in Recovery Details.
- Remaining Spot exposure or Futures positions must be shown to the user.
- The bot should transition to Stopped only after reconciliation is persisted.

### Exchange Reconnection Rules

After network or Binance API failure:

- Account connectivity state should be updated.
- Error Record should track user-facing connection state.
- Bot State History should record disconnected and reconnected transitions.
- Exchange Capability should be refreshed when stale or when errors indicate rule changes.
- Open Orders and active Positions should be synchronized before normal trading resumes.

### Crash Recovery Rules

After an unclean shutdown:

- App-level clean-shutdown marker is not enough by itself.
- Each Bot Instance must be evaluated using its last status, heartbeat, unresolved work flag, unknown orders, active Stop Requests, and active Positions.
- Recovery Session must be created for material reconciliation.
- Recovery Detail must capture each order, position, capability, or stop-request correction.
- User review is required when exposure, order state, or stop state cannot be confidently reconciled.

## Security And Privacy Persistence Rules

### API Key Security

- Raw API keys and secrets must never be stored in SQLite.
- Credential Reference must be opaque and non-sensitive.
- Redacted display hints must not reveal enough information to reconstruct a key.
- Credential deletion failures must be recoverable and visible.
- Logs and diagnostic exports must redact credential-related values.

### License Security

- Full license keys must not be stored in SQLite.
- Redacted license references may be stored for user display.
- Sensitive entitlement tokens should be stored in secure storage when required.
- License Validation History must not expose full license material.

### Account Identity Privacy

Binance account identity references are sensitive non-secret metadata.

Rules:

- Store only values required for account distinction, recovery, and support.
- Redact account identity references in logs.
- Redact or omit account identity references in diagnostic exports.
- Prefer user-facing local labels in UI where possible.

### Diagnostic Export Privacy

Diagnostic Export requires:

- User initiation or explicit user consent.
- Redaction policy applied before export.
- Export metadata retained.
- Raw credentials omitted.
- Full license keys omitted.
- Sensitive account identifiers redacted.
- Trading amounts and order references redacted or summarized when support does not require exact values.

## Questions Before Physical Database Design

The conceptual design is ready for physical database design after the team confirms:

- Exact Version 1 risk parameters exposed to users.
- Exact Version 1 capital allocation fields and validation thresholds.
- Future multiple-bot expansion rules are deferred and must not affect Version 1 physical design beyond preserving Bot Instance identity.
- Exact supported Binance order types for Spot and Futures.
- Final Futures policy for margin mode, leverage, one-way mode, and long/short risk limits.
- Exact Trade History filters required in Version 1.
- Diagnostic export scope for Version 1.
- Supported operating systems and secure storage providers.
- Offline license file format, validation rules, and redacted storage details.

## Final Readiness Statement

This final database design supports:

- Binance Main Account.
- Binance Sub Account.
- Binance Spot trading.
- Binance Futures trading.
- One configured Bot Instance experience for Version 1, with future-ready Bot Instance ownership boundaries.
- Bot start and stop flows.
- Position recovery.
- Order tracking.
- Partial fill tracking.
- Trade history.
- Risk configuration.
- Strategy configuration.
- Immutable configuration history.
- Application settings.
- License storage.
- License validation history.
- Error records.
- Crash recovery.
- State restoration.
- API key security.
- Redacted logging.
- Diagnostic export control.

The design remains conceptual and is suitable for the next Architecture, physical database design, and implementation planning phases.
