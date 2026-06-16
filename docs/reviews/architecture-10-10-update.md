# Architecture 10/10 Update Review

## Summary

Updated `docs/architecture.md` to define TiewTrade as a Modular Layered Architecture with MVVM for the Presentation Layer and Ports & Adapters at external and persistence boundaries.

The update aligns the architecture with `docs/product-decisions.md`, especially:

- One Account = One Bot for Version 1.
- Multiple Bot Instances are not supported in Version 1.
- Futures supports both long and short positions.
- Stop Bot does not close existing positions.
- Binance, SQLite, license validation, secure storage, logging, and time are accessed through ports.

## Before / After Style

| Area | Before | After |
|---|---|---|
| Architecture style | Layered modular architecture | Modular Layered Architecture with MVVM and Ports & Adapters |
| Presentation pattern | PySide6 screens and view models mentioned generally | MVVM explicitly limited to Presentation Layer |
| External boundaries | Infrastructure and persistence boundaries were present but less strict | Required ports and adapters are explicitly named |
| Bot model | Architecture implied Version 1 multi-bot runtime support | Version 1 is One Account = One Bot with duplicate runtime prevention |
| Futures support | Futures was described as long-side only | Futures supports long and short behavior with Futures-specific risk validation |
| Layer rules | Layer separation described broadly | Concrete dependency rules and anti-patterns added |
| Testability | General modularity guidance | Explicit fake-port and framework-independent testing rules |

## New Rules Added

- Views and ViewModels must not call Binance directly.
- ViewModels must not read or write SQLite directly.
- ViewModels must call Application Services only.
- Domain must not import PySide6, Binance SDKs, SQLite adapters, or OS secure storage libraries.
- Infrastructure and Persistence implement ports and must not call UI components.
- Every exchange order must start as a local order intent.
- Unknown order status must trigger synchronization before retry.
- Stop Bot must not close Spot holdings or Futures positions automatically.
- Recovery synchronization must complete before trading resumes.
- Shared abstractions must be used for repeated logic instead of copy-paste implementations.

## New Diagrams Added Or Updated

- Updated High-Level Architecture diagram.
- Updated Runtime Model diagram.
- Added MVVM Presentation Flow diagram.
- Added Ports & Adapters Boundary diagram.
- Updated Module Dependency diagram with port contracts.
- Added Order Execution Sequence diagram.
- Preserved and aligned Bot Start, Stop Bot, Trading Execution, and Recovery sequence diagrams.

## Risks Reduced

- Reduced risk of UI code containing trading logic.
- Reduced risk of Domain depending on PySide6, Binance SDKs, or SQLite implementation details.
- Reduced risk of duplicate bot runtime creation.
- Reduced risk of duplicate order submission after timeouts or unknown exchange responses.
- Reduced risk of implementation accidentally enabling unsupported Version 1 multi-bot behavior.
- Reduced risk of Futures short support being omitted despite product decisions.
- Reduced risk of credential or license handling bypassing security boundaries.

## Limitations

- This update does not define source code, interfaces, database schemas, or migration files.
- Exact package names may still be adjusted during implementation if they preserve the same boundaries.
- The architecture keeps future multi-bot expansion possible, but Version 1 must not expose or implement multi-bot management.
- Futures hedge mode remains out of scope for Version 1.
- Concrete test cases remain defined by implementation, review, and testing agents.

## Final Recommendation

Use the updated `docs/architecture.md` as the authoritative architecture source before continuing implementation beyond TASK-001.

Before coding each task, verify:

- Current task scope from `docs/status.md`.
- Product decisions from `docs/product-decisions.md`.
- Architecture boundaries from `docs/architecture.md`.
- Database ownership rules from `docs/database.md`.
- Shared abstraction and no-duplication rules from the workflow agent files.
