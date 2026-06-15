# Product Decisions

## Document Purpose

This document records the finalized Version 1 product decisions for TiewTrade.

This is the authoritative product decision source for implementation. When this document conflicts with earlier planning, user-flow, architecture, or database documents, this document takes precedence until those documents are updated.

## Source Documents Reviewed

- `/docs/project-overview.md`
- `/docs/screen-list.md`
- `/docs/user-flow.md`
- `/docs/architecture.md`
- `/docs/database.md`
- `/docs/project-review.md`

## Product Decisions

### Bot Model

- One Account = One Bot.
- Multiple Bots are not supported in Version 1.
- Version 1 supports one configured bot experience at a time.
- The connected account may be a Binance Main Account or Binance Sub Account.
- Users cannot create, duplicate, switch between, archive, or run multiple bots in Version 1.
- Architecture and database elements that support multiple bot instances are considered future-ready foundations, not Version 1 user-facing scope.

### Stop Bot Behavior

- Stop Bot stops automated trading activity.
- Stop Bot does not close existing positions.
- Stop Bot does not force liquidation.
- Existing positions remain under user control.
- Stop Bot prevents the bot from opening new automated entries.
- Stop Bot prevents the bot from adding new automated DCA entries.
- Stop Bot does not guarantee that Binance-side exposure becomes zero.
- The app must clearly show users whether a position remains open after stopping the bot.
- The app must use plain-language confirmation copy before stopping a bot, especially when an active position exists.

### Futures Support

- Binance Futures is supported in Version 1.
- Long positions are supported.
- Short positions are supported.
- Same strategy logic applies to Spot and Futures.
- Futures mode must show additional risk warnings before start.
- Futures trading must clearly communicate leverage, liquidation, and margin risk in user-facing language.
- Futures execution may require exchange-specific handling, but product behavior should remain understandable to non-technical users.

### License Model

- Version 1 uses an Offline License File.
- No online activation is required.
- License validation is performed locally.
- The app must allow the user to provide or select a license file.
- The app must validate the license file before allowing product access.
- If the license file is missing, invalid, expired, corrupted, or unsupported, the app must block product access and show a clear recovery path.
- License validation must not require an internet connection.
- The product should avoid using language such as "online activation" in Version 1 UI.

## Version 1 Constraints

### Product Scope Constraints

- Desktop application only.
- Binance only.
- Binance Spot supported.
- Binance Futures supported.
- Binance Main Account supported.
- Binance Sub Account supported.
- One built-in proprietary strategy only.
- Users configure trading parameters only.
- Users cannot create strategies.
- Users cannot edit strategy logic.
- Users cannot write code.
- Users cannot import custom strategy logic.
- One Account = One Bot.
- Multiple Bots are not supported.
- Multi-account bot management is not supported.
- Manual trading outside bot controls is not supported.

### Bot Operation Constraints

- Bot startup requires a valid local license file.
- Bot startup requires a valid Binance account connection.
- Bot startup requires selected Spot or Futures mode.
- Bot startup requires a supported trading pair.
- Bot startup requires valid capital configuration.
- Bot startup requires valid risk settings.
- Bot startup requires user review before activation.
- Stop Bot does not close positions.
- Stop Bot does not force liquidation.
- The app must not imply guaranteed profit or risk-free trading.

### Futures Constraints

- Futures mode must support both long and short positions.
- Futures mode must use the same core strategy logic as Spot.
- Futures risk must be surfaced more prominently than Spot risk.
- The app must validate that the connected Binance account can use Futures.
- The app must communicate that Futures losses may exceed user expectations due to leverage and liquidation risk.

### License Constraints

- No online license activation in Version 1.
- No recurring subscription in Version 1.
- No remote license account portal in Version 1.
- License validation is local.
- License file handling must avoid exposing sensitive license data in logs, screenshots, or error messages.

### UX Constraints

- The app must remain simple enough for non-technical traders.
- The first-run wizard remains the primary setup path.
- Users must always understand whether the bot is running, stopped, disconnected, or blocked by an error.
- Risk messages must be clear and non-technical.
- Stop Bot messaging must clearly state that positions remain under user control.
- Futures warnings must be explicit before bot start.

### Exclusions

The following are excluded from Version 1:

- Multiple bots.
- Strategy builder.
- AI strategy builder.
- Multiple strategies.
- User-defined strategy logic.
- Custom technical indicators.
- Backtesting.
- Copy trading.
- Social trading.
- Mobile app.
- Web app.
- Telegram notifications.
- Portfolio management.
- Marketplace.
- Multi-exchange support beyond Binance.
- Manual order placement outside bot controls.
- Tax reporting.
- Accounting reports.
- Institutional account management.
- Online license activation.
- Cloud license account management.
- Cloud synchronization.

## Future Version Considerations

The following items are intentionally deferred and should not be implemented as Version 1 user-facing features unless the product scope is formally changed:

- Multiple Bot support.
- Multiple account management.
- Bot creation, bot switching, bot archiving, and bot comparison.
- More than one built-in strategy.
- Strategy marketplace.
- Strategy builder.
- AI-assisted strategy builder.
- Backtesting.
- Advanced trade history filtering and export.
- Diagnostic export workflow.
- Online license activation.
- License account portal.
- Device management for licenses.
- Mobile companion app.
- Web dashboard.
- Telegram, email, or push notifications.
- Portfolio analytics.
- Multi-exchange support.
- Copy trading.
- Manual trading module.
- Advanced Futures controls beyond Version 1 risk settings.

## Implementation Alignment Notes

- `project-overview.md`, `screen-list.md`, and `user-flow.md` should be updated to remove open-decision language for Stop Bot behavior, license activation, and Futures long/short support.
- `architecture.md` should be updated to treat multiple bot runtime support as future-ready only for Version 1 and to remove the previous long-only Futures restriction.
- `database.md` may keep future-ready concepts, but implementation should not expose multiple bot workflows in Version 1.
- License screens and flows should be renamed or adjusted from online activation language to offline license file validation language.

## Final Decision Summary

Version 1 is a single-bot desktop trading application for Binance Spot and Binance Futures. A user connects one Binance account context, configures one built-in strategy through simple parameters, validates an offline license file locally, starts the bot, monitors positions and trades, and can stop automated activity without automatically closing or liquidating existing positions.
