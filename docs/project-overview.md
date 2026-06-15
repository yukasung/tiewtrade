# Project Overview

## 1. Executive Summary

TiewTrade is a desktop trading bot application designed to help Binance users start automated trading with minimal setup. The product provides a single built-in proprietary trading strategy using RSI-based entry logic, ATR-based take profit logic, and multi-entry / DCA position management. Users do not create, edit, or code trading strategies; they only configure supported trading parameters such as exchange account, market type, trading pair, capital allocation, and risk settings.

Version 1 focuses on a simple, guided desktop experience for Binance Spot and Binance Futures trading. The application supports both Binance Main Accounts and Binance Sub Accounts, with the same strategy logic applied across Spot and Futures. The business model is a one-time purchase with a lifetime license.

The primary product objective is to reduce the complexity of automated trading for non-technical users while maintaining clear risk controls, transparent bot state, and accessible trade monitoring.

## 2. Product Vision

The product vision is to make automated Binance trading approachable for general users who want a ready-to-use trading bot without learning programming, building strategies, or managing technical infrastructure.

TiewTrade should feel like a reliable desktop trading assistant: easy to set up, simple to understand, and focused on controlled execution of one predefined trading methodology.

The product should prioritize:

- Minimal setup effort.
- Clear configuration decisions.
- Transparent bot status.
- Understandable trading activity.
- Strong risk visibility.
- Stable desktop operation.

## 3. Business Goals

- Launch a paid desktop trading bot product using a one-time lifetime license model.
- Serve Binance traders who want automation without strategy design or coding.
- Reduce onboarding friction through a first-run setup wizard.
- Differentiate through simplicity, single-strategy focus, and support for both Spot and Futures.
- Build user trust through clear risk settings, account visibility, and transparent trade history.
- Establish a foundation for future paid upgrades, companion features, or advanced editions without expanding Version 1 scope prematurely.

## 4. Target Users

The target users are:

- Binance Spot traders.
- Binance Futures traders.
- Users with Binance Main Accounts.
- Users with Binance Sub Accounts.
- General users who understand basic trading concepts but do not have programming knowledge.
- Traders who want automation but do not want to design, test, or maintain trading strategies.

The product is not primarily intended for professional quant traders, institutions, strategy developers, or users who require custom strategy logic.

## 5. User Personas

### Persona 1: The Casual Binance Trader

**Profile:** A retail trader who manually trades on Binance and wants to automate part of their trading activity.

**Needs:**

- Simple setup.
- Clear capital allocation controls.
- Ability to start and stop the bot easily.
- Basic visibility into trades and open positions.

**Pain Points:**

- Does not know how to code.
- Finds trading bot platforms too complex.
- Does not want to manage servers or technical infrastructure.

### Persona 2: The Risk-Conscious Futures User

**Profile:** A Binance Futures user who wants automated execution but is aware that leverage and liquidation risk must be controlled.

**Needs:**

- Explicit Futures mode selection.
- Clear risk settings before starting.
- Position monitoring.
- Ability to stop the bot quickly.

**Pain Points:**

- Worried about overexposure.
- Needs visibility into active positions.
- Does not want hidden or confusing bot behavior.

### Persona 3: The Non-Technical Automation Seeker

**Profile:** A general user who has heard about trading bots and wants an easy way to begin automated trading on Binance.

**Needs:**

- Wizard-based onboarding.
- No coding or strategy-building requirement.
- Plain-language configuration.
- Review step before activation.

**Pain Points:**

- Does not understand APIs deeply.
- May not understand all trading risks.
- Needs guardrails and confirmation before enabling live trading.

### Persona 4: The Sub Account Operator

**Profile:** A trader who separates trading activity using Binance Sub Accounts.

**Needs:**

- Connect a Binance Main Account or Sub Account.
- Run the bot against the selected account context.
- View activity for the connected account.

**Pain Points:**

- Wants account separation.
- Needs confidence that the bot is operating on the intended account.
- Does not want cross-account confusion.

## 6. User Problems

- Automated trading tools are often too technical for general users.
- Many bots require users to create, configure, or optimize trading strategies.
- Strategy-builder products create decision fatigue for users who only want a ready-made approach.
- Users may not know how to safely configure exchange API access.
- Users need clear risk controls before allowing a bot to trade live funds.
- Futures trading introduces additional risk that must be surfaced clearly.
- Users need simple monitoring of bot status, open positions, and trade history.
- Users need confidence that they can stop the bot when needed.

## 7. Product Scope

TiewTrade is a desktop application that connects to Binance and executes one built-in proprietary trading strategy based on user-defined configuration.

The product scope includes:

- Desktop application experience.
- First-run setup wizard.
- Binance account connection.
- Support for Binance Spot.
- Support for Binance Futures.
- Support for Binance Main Accounts.
- Support for Binance Sub Accounts.
- Trading pair selection.
- Capital configuration.
- Risk settings configuration.
- Starting and stopping the bot.
- Dashboard for bot and account status.
- Account management.
- Trade history.
- Position monitoring.

The product scope does not include user-created strategies, multiple strategies, social trading, mobile access, web access, or marketplace functionality.

## 8. Version 1 Scope

Version 1 should deliver the smallest complete product that allows a user to safely configure and run the built-in trading bot on Binance Spot or Binance Futures.

Version 1 includes:

- First-run wizard setup:
  - Connect Binance Account.
  - Select Spot or Futures.
  - Select Trading Pair.
  - Configure Capital.
  - Configure Risk Settings.
  - Review Configuration.
  - Start Bot.
- Dashboard:
  - Bot status.
  - Selected exchange mode.
  - Selected trading pair.
  - Capital allocation summary.
  - Current position summary.
  - Recent trade activity.
- Account Management:
  - Add Binance account credentials.
  - Identify whether the connection is for a Main Account or Sub Account.
  - View connection status.
  - Remove or replace account connection.
- Trade History:
  - View completed bot trades.
  - View relevant order details.
  - View timestamps and execution results.
- Position Monitoring:
  - View active position state.
  - View DCA / multi-entry progress.
  - View take profit status.
  - View exposure and risk-related values.
- Bot Controls:
  - Start Bot.
  - Stop Bot.
  - Show running, stopped, error, and disconnected states.
- Risk Settings:
  - Configure user-facing risk parameters.
  - Review risk settings before activation.
  - Prevent bot start when required risk settings are incomplete.

## 9. Out Of Scope

The following items are explicitly out of scope for Version 1:

- Multiple strategies.
- Strategy builder.
- AI strategy builder.
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
- Managed investment services.

## 10. Core Features

### First-Run Wizard

The wizard guides users from account connection to bot activation. It is the primary onboarding path and should reduce ambiguity for non-technical users.

### Binance Account Connection

Users can connect a Binance account for Spot or Futures trading. The product must support both Main Account and Sub Account usage.

### Market Mode Selection

Users choose whether the bot operates on Binance Spot or Binance Futures. The selected mode affects available account permissions, position behavior, and displayed risk information.

### Trading Pair Selection

Users choose a supported trading pair. The product should prevent unsupported or invalid pair selections.

### Capital Configuration

Users define how much capital the bot is allowed to use. The product should communicate that allocated capital may be exposed to market risk.

### Risk Settings

Users configure trading risk parameters. These settings must be visible before bot activation and editable while the bot is stopped.

### Built-In Strategy Execution

The application runs a single proprietary strategy using:

- RSI Entry.
- ATR Take Profit.
- Multi-entry / DCA Position Management.
- The same core strategy logic for Spot and Futures.

Users cannot modify the strategy logic itself.

### Dashboard

The dashboard provides the main operating view after setup, showing bot status, account connection, market mode, selected pair, open position status, and recent activity.

### Trade History

Users can review completed bot trading activity and relevant execution details.

### Position Monitoring

Users can monitor active position state, including entries, DCA progress, and take profit progress.

### Start Bot

Users can start automated trading after required configuration is complete and reviewed.

### Stop Bot

Users can stop automated trading. The product must clearly communicate what stopping the bot does and does not do, including any assumptions about open positions.

## 11. User Experience Goals

- The application should be understandable to users without programming knowledge.
- The first-run experience should guide users step by step.
- Users should always know whether the bot is running, stopped, disconnected, or in an error state.
- Users should be able to review configuration before live trading begins.
- Risk-related information should be visible and written in plain language.
- The product should avoid advanced trading jargon where simpler wording is possible.
- The interface should make dangerous actions explicit, especially starting Futures trading or changing risk settings.
- The product should provide confidence that the selected account, market mode, and trading pair are correct.
- The user should not need to understand the proprietary strategy internals to operate the product.
- The product should avoid overwhelming users with unnecessary configuration options.

## 12. Functional Requirements

### Account Connection

- The system shall allow users to connect a Binance account.
- The system shall support Binance Main Account usage.
- The system shall support Binance Sub Account usage.
- The system shall indicate whether the account connection is active, invalid, disconnected, or missing required permissions.
- The system shall allow users to remove or replace a connected account.
- The system shall prevent bot startup if no valid Binance account is connected.

### Wizard Setup

- The system shall display the first-run wizard when no valid bot configuration exists.
- The wizard shall include steps for account connection, market mode selection, trading pair selection, capital configuration, risk settings, review, and bot start.
- The system shall validate each wizard step before allowing users to proceed.
- The system shall display a final review before bot activation.
- The system shall allow users to exit setup without starting the bot.

### Market Selection

- The system shall allow users to choose Binance Spot or Binance Futures.
- The system shall use the selected market mode for bot operation.
- The system shall show Futures-specific risk messaging when Futures mode is selected.
- The system shall prevent bot startup if the selected account does not support the selected market mode.

### Trading Pair Configuration

- The system shall allow users to select a trading pair supported by the selected market mode.
- The system shall prevent invalid or unsupported trading pair configuration.
- The system shall show the currently selected trading pair on the dashboard.

### Capital Configuration

- The system shall allow users to configure capital allocated to the bot.
- The system shall validate that configured capital is greater than zero.
- The system shall prevent bot startup if configured capital is missing or invalid.
- The system shall show configured capital before bot activation.

### Risk Settings

- The system shall allow users to configure required risk settings.
- The system shall validate risk settings before bot startup.
- The system shall prevent bot startup when required risk settings are incomplete or invalid.
- The system shall show risk settings in the review step.
- The system shall allow risk settings to be edited while the bot is stopped.
- The system shall clearly communicate when risk setting changes require the bot to be stopped.

### Bot Operation

- The system shall allow users to start the bot after configuration is complete.
- The system shall allow users to stop the bot.
- The system shall display bot status at all times in the main application experience.
- The system shall execute only the built-in proprietary strategy.
- The system shall not allow users to create, edit, import, or code strategies.
- The system shall apply the same strategy logic to Spot and Futures, subject to exchange-specific execution behavior.
- The system shall record bot-generated trading activity for trade history.

### Dashboard

- The system shall provide a dashboard after setup.
- The dashboard shall display bot status.
- The dashboard shall display connected account status.
- The dashboard shall display selected market mode.
- The dashboard shall display selected trading pair.
- The dashboard shall display capital configuration summary.
- The dashboard shall display open position status when applicable.
- The dashboard shall display recent trade activity.

### Trade History

- The system shall display historical bot trades.
- The system shall show relevant execution information for each trade.
- The system shall distinguish successful, failed, canceled, or rejected trade events where applicable.
- The system shall allow users to inspect past bot activity without modifying strategy logic.

### Position Monitoring

- The system shall display active position state.
- The system shall display multi-entry / DCA progress where applicable.
- The system shall display take profit progress where applicable.
- The system shall display relevant risk and exposure values in a user-readable format.

### Error Handling

- The system shall communicate account connection errors.
- The system shall communicate exchange permission errors.
- The system shall communicate invalid configuration errors.
- The system shall communicate bot runtime errors.
- The system shall avoid hiding failed trading actions from the user.

### Licensing

- The system shall support a one-time purchase lifetime license model.
- The system shall restrict product access when no valid license is present.
- The system shall provide a clear license activation or validation experience.

## 13. Non-Functional Requirements

### Usability

- The product should be usable by people without programming knowledge.
- The first-run setup should be completed with minimal required steps.
- Primary bot controls should be easy to find and understand.
- Risk warnings should be clear, direct, and non-technical.

### Reliability

- The application should maintain accurate bot state.
- The application should handle temporary Binance connectivity issues gracefully.
- The application should avoid duplicate bot actions caused by repeated clicks, restarts, or unstable connections.
- The application should preserve user configuration across restarts.

### Security

- Binance credentials and sensitive account connection data must be protected.
- The product should request only the permissions required for Version 1 operation.
- The product should not expose sensitive credentials in logs, exports, screenshots, or error messages.
- The product should clearly advise users not to enable withdrawal permissions for trading bot access.

### Performance

- The desktop application should remain responsive during bot operation.
- Dashboard and monitoring information should update in a timely manner.
- Long-running bot activity should not freeze primary user controls.

### Transparency

- Users should be able to understand what the bot is configured to trade.
- Users should be able to understand whether the bot is currently active.
- Users should be able to view historical bot actions.
- The product should clearly distinguish configuration, monitoring, and active trading states.

### Maintainability

- Product behavior should be documented well enough for future implementation teams to make consistent decisions.
- Strategy configuration boundaries should remain clear: users configure parameters but do not alter strategy logic.
- Version 1 scope should avoid unnecessary feature expansion.

### Compliance and Responsible Use

- The product should communicate that trading involves risk.
- The product should not promise profits or guaranteed outcomes.
- The product should avoid presenting automated trading as financial advice.
- Futures trading risk should be especially visible due to leverage and liquidation exposure.

## 14. Assumptions

- The working product name is TiewTrade unless replaced by a final brand name.
- The application is intended for desktop use only in Version 1.
- Binance is the only supported exchange in Version 1.
- Users will provide their own Binance account and API access.
- Users are responsible for ensuring their Binance account is eligible for Spot and/or Futures trading.
- The built-in proprietary strategy already exists conceptually but its internal logic is not part of this document.
- Users can configure trading parameters but cannot modify strategy rules, indicators, or signal logic.
- Spot and Futures use the same core strategy logic, with exchange-specific behavior handled by the application.
- A valid license is required to use the product.
- The one-time purchase license grants lifetime access to the purchased product version or license terms defined by the business.
- The product will need clear legal disclaimers before release.
- The exact list of configurable risk parameters is not yet finalized.
- The exact supported operating systems are not yet defined.
- The exact license activation process is not yet defined.
- The exact behavior of Stop Bot with open positions needs final product decision.

## 15. Constraints

- Version 1 must remain focused on a single built-in strategy.
- Users must not be able to create or modify strategy logic.
- The product must support Binance Spot and Binance Futures only.
- The product must support Binance Main Account and Sub Account usage.
- The first-run experience must use a wizard setup flow.
- The product must be suitable for non-programmers.
- The business model is one-time purchase with lifetime license.
- No mobile app or web app is included in Version 1.
- No copy trading, marketplace, or portfolio management is included in Version 1.
- Product design must avoid suggesting guaranteed profit or risk-free automation.
- Any future expansion should not compromise the simplicity of Version 1.

## 16. Risks

### Market and Trading Risk

Automated trading can lose money. Futures trading may involve leverage, liquidation, and rapid capital loss. The product must make risk visible without overwhelming users.

### User Misconfiguration Risk

Users may enter incorrect API credentials, choose the wrong account, select the wrong market mode, allocate too much capital, or misunderstand risk settings.

### Exchange Dependency Risk

The product depends on Binance availability, API behavior, account permissions, and exchange rule changes.

### Security Risk

Improper handling of API credentials could expose users to account risk. Credential handling must be treated as a critical product concern.

### Legal and Compliance Risk

The product may be interpreted as providing financial advice if messaging is not careful. Claims about profitability, safety, or performance must be avoided unless legally reviewed and substantiated.

### Strategy Performance Risk

The built-in proprietary strategy may perform differently across market conditions. Users may attribute losses to product failure even when the bot executes as configured.

### Support Risk

Non-technical users may require support for Binance setup, API permissions, Futures concepts, and risk settings.

### Scope Expansion Risk

Requests for multiple strategies, custom logic, notifications, portfolio tools, or mobile access could distract from the simplicity required for Version 1.

### Licensing Risk

Lifetime license expectations must be defined clearly to avoid ambiguity around updates, support, device limits, and major version upgrades.

## 17. Success Criteria

Version 1 should be considered successful when:

- A new user can complete the wizard and start the bot without programming knowledge.
- Users can connect a Binance Main Account or Sub Account.
- Users can choose Spot or Futures mode.
- Users can select a trading pair and configure capital.
- Users can configure required risk settings and review them before activation.
- Users can start and stop the bot from the desktop application.
- Users can see bot status clearly at all times.
- Users can monitor active positions and review trade history.
- Users understand that the product runs one built-in strategy only.
- Users cannot accidentally create or modify strategy logic.
- The product communicates trading risk clearly and avoids profit guarantees.
- The Version 1 scope remains free of out-of-scope features.

Measurable business and product indicators may include:

- Wizard completion rate.
- Successful account connection rate.
- Bot startup success rate after completed configuration.
- Frequency of bot stop actions due to user confusion or errors.
- Support request volume related to setup and risk settings.
- License purchase conversion rate.
- Refund or cancellation rate.
- User satisfaction with setup simplicity.

## 18. Future Roadmap

Future roadmap items are candidates only and should not be treated as Version 1 commitments.

### Near-Term Enhancements

- Improved onboarding education for Binance API setup.
- More detailed risk explanations.
- Enhanced trade filtering and export.
- More detailed bot activity logs.
- Better license management experience.
- Additional desktop operating system support if not included in Version 1.

### Mid-Term Enhancements

- Optional notifications through channels selected after Version 1 validation.
- Additional reporting for bot performance.
- More advanced account-level safety limits.
- More guided presets for conservative, balanced, and aggressive parameter configurations.
- Better support tooling for troubleshooting user setup issues.

### Long-Term Possibilities

- Additional exchanges.
- Additional built-in strategies.
- Advanced edition for experienced users.
- Web companion dashboard.
- Mobile companion app.
- Marketplace or partner ecosystem.
- Portfolio-level analytics.

These roadmap items require separate product discovery, technical feasibility review, legal review, and commercial validation before being added to an official release plan.
