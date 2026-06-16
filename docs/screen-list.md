# Screen List

## Document Purpose

This document defines the Version 1 screens required for TiewTrade, a desktop trading bot application for non-technical Binance traders.

The goal is to define the user experience surface area before UI mockups, architecture, database design, or coding begins. Each screen focuses on purpose, core content, user actions, and navigation flow.

## UX Principles For Version 1

- Keep each screen focused on one primary decision or task.
- Use plain language for trading, account, and risk concepts.
- Make bot status visible and easy to understand.
- Make risky actions explicit, especially starting Futures trading or stopping while a position is open.
- Avoid strategy-building concepts entirely.
- Avoid exposing proprietary strategy logic beyond high-level labels.
- Guide users through setup instead of asking them to discover configuration on their own.

## Screen Inventory

Version 1 requires the following screens:

1. App Launch / Loading Screen
2. License File Validation Screen
3. First-Run Welcome Screen
4. Wizard Step 1: Connect Binance Account
5. Wizard Step 2: Select Spot or Futures
6. Wizard Step 3: Select Trading Pair
7. Wizard Step 4: Configure Capital
8. Wizard Step 5: Configure Risk Settings
9. Wizard Step 6: Review Configuration
10. Wizard Step 7: Start Bot
11. Main Dashboard
12. Position Monitoring Screen
13. Trade History Screen
14. Account Management Screen
15. Risk Settings Screen
16. Stop Bot Confirmation Screen
17. Error / Connection Issue Screen
18. License Management Screen

## Global Navigation Model

After setup is complete, the desktop application should use a simple primary navigation structure:

- Dashboard
- Positions
- Trade History
- Account
- Risk Settings
- License

The Start Bot and Stop Bot controls should remain easy to access from the Dashboard. Bot status should be visible in the main application frame or header across all primary screens.

## 1. App Launch / Loading Screen

### Screen Name

App Launch / Loading Screen

### Purpose

Confirm that the desktop application is opening, check basic local readiness, and route the user to the correct next screen.

### Main Components

- Product name.
- Simple loading state.
- Short status message such as checking license, loading configuration, or preparing app.
- Non-technical error message if the app cannot continue.

### User Actions

- Wait while the app loads.
- Retry if loading fails.
- Exit the application if the app cannot continue.

### Navigation Flow

- If no valid license file exists, navigate to License File Validation Screen.
- If a valid license exists but no setup configuration exists, navigate to First-Run Welcome Screen.
- If a valid license and setup configuration exist, navigate to Main Dashboard.
- If a blocking connection or local app issue occurs, navigate to Error / Connection Issue Screen.

## 2. License File Validation Screen

### Screen Name

License File Validation Screen

### Purpose

Allow users to select and locally validate their Offline License File before accessing the product.

### Main Components

- License file selection control.
- License status message.
- Validate License File button.
- Retry validation option.
- Plain-language explanation that a valid license is required.
- Support or help link placeholder.

### User Actions

- Select an Offline License File.
- Validate the license file locally.
- Retry validation.
- View help if validation fails.
- Exit the application.

### Navigation Flow

- If license file validation succeeds and setup is incomplete, navigate to First-Run Welcome Screen.
- If license file validation succeeds and setup is complete, navigate to Main Dashboard.
- If license file validation fails, remain on this screen and show a clear error.
- From the main application, users can return to license details through License Management Screen.

## 3. First-Run Welcome Screen

### Screen Name

First-Run Welcome Screen

### Purpose

Introduce the setup process and set expectations before the user connects Binance and starts live trading.

### Main Components

- Short welcome message.
- Setup step summary.
- Plain-language explanation that the bot uses one built-in strategy.
- Risk reminder that trading can lose money.
- Start Setup button.
- Exit or Set Up Later option.

### User Actions

- Start the setup wizard.
- Exit setup.
- Review basic setup expectations.

### Navigation Flow

- Start Setup navigates to Wizard Step 1: Connect Binance Account.
- Exit setup closes the wizard or returns to a non-trading inactive state.
- Users should not reach the Main Dashboard with bot controls enabled until required setup is complete.

## 4. Wizard Step 1: Connect Binance Account

### Screen Name

Connect Binance Account

### Purpose

Collect and validate Binance account connection details in a way that is understandable to users who may not be familiar with API setup.

### Main Components

- Step progress indicator.
- Account type selection: Main Account or Sub Account.
- Binance API key input.
- Binance API secret input.
- Permission guidance.
- Security reminder not to enable withdrawal permissions.
- Test Connection button.
- Connection status result.
- Back and Continue controls.

### User Actions

- Select Main Account or Sub Account.
- Enter Binance API credentials.
- Test the connection.
- Correct invalid credentials.
- Continue after successful validation.
- Go back to the welcome screen.

### Navigation Flow

- Back returns to First-Run Welcome Screen.
- Successful connection enables Continue.
- Continue navigates to Wizard Step 2: Select Spot or Futures.
- Invalid credentials or missing permissions keep the user on this screen with a clear message.
- Users may exit setup without saving an incomplete connection.

## 5. Wizard Step 2: Select Spot or Futures

### Screen Name

Select Spot or Futures

### Purpose

Let users choose the market mode the bot will trade in, while clearly explaining the risk difference between Spot and Futures.

### Main Components

- Step progress indicator.
- Spot option.
- Futures option.
- Plain-language comparison of Spot and Futures.
- Futures risk warning.
- Account permission status for selected mode.
- Back and Continue controls.

### User Actions

- Select Spot.
- Select Futures.
- Review the risk note.
- Continue after selecting a valid mode.
- Go back to account connection.

### Navigation Flow

- Back returns to Wizard Step 1: Connect Binance Account.
- Continue navigates to Wizard Step 3: Select Trading Pair.
- If the connected account lacks permissions for the selected mode, remain on this screen and explain what needs to be fixed.

## 6. Wizard Step 3: Select Trading Pair

### Screen Name

Select Trading Pair

### Purpose

Allow users to choose the Binance trading pair that the bot will trade.

### Main Components

- Step progress indicator.
- Search or select control for supported trading pairs.
- Current market mode label: Spot or Futures.
- Selected pair summary.
- Pair availability status.
- Back and Continue controls.

### User Actions

- Search for a trading pair.
- Select a trading pair.
- Change the selected pair.
- Continue after selecting a valid pair.
- Go back to market mode selection.

### Navigation Flow

- Back returns to Wizard Step 2: Select Spot or Futures.
- Continue navigates to Wizard Step 4: Configure Capital.
- Unsupported or unavailable pairs keep the user on this screen with a clear message.

## 7. Wizard Step 4: Configure Capital

### Screen Name

Configure Capital

### Purpose

Let users define how much capital the bot is allowed to use for the selected account, market mode, and trading pair.

### Main Components

- Step progress indicator.
- Available balance summary.
- Capital amount input.
- Allocation explanation.
- Warning that allocated capital is exposed to trading risk.
- Validation message for insufficient or invalid capital.
- Back and Continue controls.

### User Actions

- Enter capital amount.
- Review available balance.
- Adjust capital amount.
- Continue after valid capital is entered.
- Go back to trading pair selection.

### Navigation Flow

- Back returns to Wizard Step 3: Select Trading Pair.
- Continue navigates to Wizard Step 5: Configure Risk Settings.
- Invalid, zero, or unavailable capital keeps the user on this screen with a clear message.

## 8. Wizard Step 5: Configure Risk Settings

### Screen Name

Configure Risk Settings

### Purpose

Allow users to configure required risk controls without exposing strategy-building functionality.

### Main Components

- Step progress indicator.
- Required risk setting fields.
- Plain-language helper text for each setting.
- Futures-specific risk note when Futures mode is selected.
- Validation messages.
- Back and Continue controls.

### User Actions

- Enter or adjust risk settings.
- Review helper text.
- Correct invalid risk values.
- Continue after required settings are valid.
- Go back to capital configuration.

### Navigation Flow

- Back returns to Wizard Step 4: Configure Capital.
- Continue navigates to Wizard Step 6: Review Configuration.
- Missing or invalid risk settings keep the user on this screen with clear guidance.

## 9. Wizard Step 6: Review Configuration

### Screen Name

Review Configuration

### Purpose

Give users a final, understandable summary before they enable live automated trading.

### Main Components

- Step progress indicator.
- Connected account summary.
- Account type: Main Account or Sub Account.
- Market mode: Spot or Futures.
- Trading pair.
- Capital allocation.
- Risk settings summary.
- Built-in strategy summary.
- Risk disclosure.
- Edit links for each setup section.
- Back and Continue controls.

### User Actions

- Review all configuration details.
- Go back to change setup choices.
- Select a specific section to edit.
- Confirm readiness to proceed.

### Navigation Flow

- Back returns to Wizard Step 5: Configure Risk Settings.
- Edit Account returns to Wizard Step 1.
- Edit Market returns to Wizard Step 2.
- Edit Pair returns to Wizard Step 3.
- Edit Capital returns to Wizard Step 4.
- Edit Risk Settings returns to Wizard Step 5.
- Continue navigates to Wizard Step 7: Start Bot.

## 10. Wizard Step 7: Start Bot

### Screen Name

Start Bot

### Purpose

Let users make the final start decision after reviewing setup and risk information.

### Main Components

- Final start confirmation.
- Bot configuration summary.
- Risk confirmation checkbox or acknowledgment.
- Primary Start Bot button.
- Secondary Start Later option.
- Back control.
- Starting status message after bot startup begins.

### User Actions

- Acknowledge risk.
- Start the bot.
- Start later without starting the bot.
- Go back to review configuration.

### Navigation Flow

- Back returns to Wizard Step 6: Review Configuration.
- Start Bot navigates to Main Dashboard with bot status shown as starting or running.
- Start Later navigates to Main Dashboard with bot status shown as stopped.
- If startup fails, navigate to Error / Connection Issue Screen or show an inline error with a clear recovery path.

## 11. Main Dashboard

### Screen Name

Main Dashboard

### Purpose

Provide the primary operating view for the bot, showing status, configuration, current activity, and key controls.

### Main Components

- Bot status: running, stopped, starting, stopping, disconnected, or error.
- Start Bot or Stop Bot control.
- Connected account status.
- Account type summary.
- Market mode summary.
- Trading pair summary.
- Capital allocation summary.
- Current position summary.
- Recent trade activity.
- Risk setting summary.
- Navigation to Positions, Trade History, Account, Risk Settings, and License.

### User Actions

- Start the bot if stopped and configuration is valid.
- Stop the bot if running.
- View current position details.
- View recent trade details.
- Navigate to other main screens.
- Review connection and configuration status.

### Navigation Flow

- Start Bot changes bot status or routes to setup if required configuration is missing.
- Stop Bot opens Stop Bot Confirmation Screen.
- Position summary navigates to Position Monitoring Screen.
- Recent trade item navigates to Trade History Screen.
- Account status navigates to Account Management Screen.
- Risk summary navigates to Risk Settings Screen.
- License status navigates to License Management Screen.
- Connection or runtime failures route to Error / Connection Issue Screen or display a persistent recoverable error state.

## 12. Position Monitoring Screen

### Screen Name

Position Monitoring Screen

### Purpose

Help users understand the bot's active position state without requiring advanced trading knowledge.

### Main Components

- Active position status.
- Selected trading pair.
- Market mode.
- Entry summary.
- Multi-entry / DCA progress.
- Take profit progress.
- Exposure and risk values.
- Current bot status.
- Link back to Dashboard.

### User Actions

- Review active position state.
- Review DCA progress.
- Review take profit progress.
- Return to Dashboard.
- Stop the bot through the global bot control if available.

### Navigation Flow

- Dashboard position summary navigates to this screen.
- Back or Dashboard navigation returns to Main Dashboard.
- Stop Bot opens Stop Bot Confirmation Screen.
- If no active position exists, this screen shows an empty state and offers navigation back to Dashboard.

## 13. Trade History Screen

### Screen Name

Trade History Screen

### Purpose

Allow users to review completed and attempted bot trading activity.

### Main Components

- Trade history list.
- Trade status labels such as successful, failed, canceled, or rejected.
- Timestamp.
- Trading pair.
- Market mode.
- Order or execution summary.
- Basic filters such as date range, pair, or status if needed for usability.
- Empty state when no trades exist.
- Link back to Dashboard.

### User Actions

- Review past trades.
- Select a trade to view more detail.
- Filter or search trade history if supported.
- Return to Dashboard.

### Navigation Flow

- Dashboard recent activity navigates to this screen.
- Selecting a trade expands or opens trade details within the same screen.
- Dashboard navigation returns to Main Dashboard.
- This screen does not allow manual trading or strategy editing.

## 14. Account Management Screen

### Screen Name

Account Management Screen

### Purpose

Let users view, replace, remove, or validate their connected Binance account.

### Main Components

- Connected account status.
- Account type: Main Account or Sub Account.
- API credential status without exposing secret values.
- Spot permission status.
- Futures permission status.
- Test Connection button.
- Replace Account action.
- Remove Account action.
- Security reminder about withdrawal permissions.
- Bot-running warning if account changes require stopping the bot.

### User Actions

- View connected account state.
- Test connection.
- Replace account credentials.
- Remove connected account.
- Return to Dashboard.

### Navigation Flow

- Dashboard account status navigates to this screen.
- Replace Account may open the account connection flow or an account replacement form.
- Remove Account requires confirmation and should stop access to bot startup until a valid account is connected.
- If the bot is running, account-changing actions should require the bot to be stopped first.
- Dashboard navigation returns to Main Dashboard.

## 15. Risk Settings Screen

### Screen Name

Risk Settings Screen

### Purpose

Allow users to view and edit bot risk settings while maintaining clear guardrails around active trading.

### Main Components

- Current risk settings.
- Plain-language explanation for each setting.
- Market mode context.
- Futures-specific warning if applicable.
- Save Changes button.
- Cancel changes action.
- Validation messages.
- Notice that changes may require the bot to be stopped.

### User Actions

- Review current risk settings.
- Edit risk settings while the bot is stopped.
- Save valid changes.
- Cancel unsaved changes.
- Return to Dashboard.

### Navigation Flow

- Dashboard risk summary navigates to this screen.
- If the bot is running, risk settings are read-only or editing is blocked with a clear message.
- Save Changes returns to this screen with updated values and a success state.
- Dashboard navigation returns to Main Dashboard.

## 16. Stop Bot Confirmation Screen

### Screen Name

Stop Bot Confirmation Screen

### Purpose

Confirm the user's intent before stopping automated trading and clearly explain what will happen next.

### Main Components

- Stop confirmation message.
- Current bot status.
- Active position summary if a position exists.
- Explanation of what stopping the bot will do.
- Explanation of what stopping the bot will not do.
- Confirm Stop Bot button.
- Cancel button.

### User Actions

- Confirm stopping the bot.
- Cancel and return to the previous screen.
- Review active position context before stopping.

### Navigation Flow

- Opened from Dashboard or Position Monitoring Screen.
- Cancel returns to the previous screen.
- Confirm Stop Bot returns to Main Dashboard with bot status shown as stopping or stopped.
- If stopping fails, navigate to Error / Connection Issue Screen or show a clear recovery message.

## 17. Error / Connection Issue Screen

### Screen Name

Error / Connection Issue Screen

### Purpose

Give users a simple recovery path when the app, Binance connection, account permissions, or bot runtime enters a blocking error state.

### Main Components

- Plain-language error title.
- Short explanation of what happened.
- Suggested next step.
- Retry action.
- Go to Account action when the issue is account-related.
- Go to Dashboard action when safe.
- Support or help link placeholder.
- Bot status if relevant.

### User Actions

- Retry the failed action.
- Navigate to Account Management.
- Return to Dashboard.
- Exit the application if the issue is blocking.

### Navigation Flow

- Can be reached from launch, wizard, dashboard, account, or bot operation flows.
- Retry returns the user to the previous action if successful.
- Account-related issues navigate to Account Management Screen.
- Non-blocking issues allow return to Main Dashboard.

## 18. License Management Screen

### Screen Name

License Management Screen

### Purpose

Allow users to view their license status and handle Offline License File validation issues.

### Main Components

- Current license status.
- License type: lifetime license.
- Local validation status.
- Recheck License button.
- Change License File action if needed.
- Support or help link placeholder.
- Clear message if the license becomes invalid.

### User Actions

- View license state.
- Recheck license.
- Change or revalidate license file.
- Return to Dashboard.

### Navigation Flow

- Dashboard license status navigates to this screen.
- Recheck License remains on this screen and updates status.
- Change License File navigates to License File Validation Screen.
- Valid license state allows return to Main Dashboard.
- Invalid license state blocks bot operation and routes users to License File Validation Screen.

## Required Empty States

The following empty states should be planned as part of the relevant screens:

- No active position on Position Monitoring Screen.
- No trade history on Trade History Screen.
- No connected account on Account Management Screen.
- No valid license on License Management Screen.
- Bot stopped on Main Dashboard.
- Bot configuration incomplete on Main Dashboard.

## Required Confirmation States

The following actions should require explicit confirmation or acknowledgment:

- Starting the bot for the first time.
- Starting the bot in Futures mode.
- Stopping the bot while a position is active.
- Removing a Binance account.
- Replacing a Binance account while configuration exists.
- Saving risk setting changes that materially affect bot behavior.

## Assumptions And Open UX Decisions

- Offline License File validation is required before setup and is performed locally.
- The exact risk setting fields are not yet finalized.
- The exact supported desktop operating systems are not yet finalized.
- Stop Bot behavior is finalized: it stops automated trading activity but does not close existing positions or force liquidation.
- Account replacement may reuse the first wizard account connection screen or use a separate account form.
- Trade detail may be handled through inline expansion, a side panel, or a separate detail screen in later UX design.
- This document intentionally excludes UI mockups, visual layout, architecture, database design, and implementation details.
