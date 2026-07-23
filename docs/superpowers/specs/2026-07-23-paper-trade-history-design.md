# Paper Trade History Design

**Date:** 2026-07-23
**Status:** Approved design
**Scope:** Phase 1 Paper Trading

## 1. Purpose

Phase 1 must let the user review every trade created by the Bot and answer:

- When did each BUY or SELL fill?
- At what price and quantity did it fill?
- Which Basket and Entry did it belong to?
- How much gross and net realized profit or loss did the completed Basket produce?

The first version uses numeric tables only. It does not display a candlestick chart
or provide general historical market browsing.

## 2. Product Decisions

- The installation uses one Binance Account only.
- The application allows one Active Bot Session globally.
- A Session runs one Strategy Preset and pins its Symbol, Timeframe, Market Type,
  Trade Mode, and capital settings.
- Phase 1 records Paper Spot and Paper Futures history.
- Paper and Live use the same normalized Basket and Trade Fill records.
- Phase 1 does not connect to Binance Private APIs and never sends a Live order.
- Paper Futures records `funding_fee = 0.00` in Phase 1. Funding simulation is
  outside this feature.
- Trade history contains only orders and fills owned by the Bot Session. It does
  not include manual trades or trades created by another system.
- Trade Fill and Basket Result records are durable. Candle retention is a
  separate market-data decision and does not affect trade-history retention.

## 3. Source-of-Truth Alignment

Before implementation begins, the project documentation must be updated to apply
the approved product decisions:

- Remove Account Profile, sub-account, and multi-account behavior from
  `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, and `PROJECT_PLAN.md`.
- Replace per-account Active Session ownership with one Active Bot Session for
  the installation.
- State that Paper Futures Funding Fee is zero in the first Paper Trading phase.
- Remove Account Profile fields and filters from the planned UI and persistence
  model.
- Preserve the rule that Paper and Live share trading and risk policies while
  using different execution adapters.

These changes supersede the conflicting Account Profile and Paper funding clauses
in the current project documents.

## 4. Architecture

```text
Strategy
   |
   v
Order Intent
   |
   v
Paper Executor ---------------- Future Live Binance Adapter
   |                                      |
   +------------ actual Fill Event -------+
                         |
                         v
                Trade History Service
                  |               |
                  v               v
             Trade Fill      Basket Result
                  \               /
                   \             /
                    v           v
                        SQLite
                          |
                          v
                 Trade History Query
                    |           |
                    v           v
             Basket History   Trade Fills
                 table          table
```

The UI reads persisted history through an application query service. It does not
call an executor or Binance directly.

The Trade History Service owns normalization and persistence of execution
results. Trading-domain code remains independent of SQLite and UI details.

## 5. Persistent Records

### 5.1 Basket Result

Each Basket Result stores:

- `basket_id`
- `session_id`
- `trade_mode`: `PAPER` or `LIVE`
- `market_type`: `SPOT` or `FUTURES`
- `symbol`
- `timeframe`
- `strategy_preset_version`
- `opened_at_utc`
- `closed_at_utc`, nullable while open
- `entry_count`
- `invested_notional`
- `gross_realized_pnl`
- `trading_fees`
- `funding_fee`
- `net_realized_pnl`
- `status`: `OPEN` or `CLOSED`

Open Baskets are visible, but their changing value is not counted as closed
realized profit.

### 5.2 Trade Fill

Each Trade Fill stores:

- `fill_id`
- `basket_id`
- `session_id`
- `order_id`
- `exchange_trade_id`, nullable for Paper
- `side`: `BUY` or `SELL`
- `entry_number`, nullable when the Fill is not an Entry
- `filled_at_utc`
- `price`
- `quantity`
- `notional`
- `commission`
- `commission_asset`
- `realized_pnl`
- `source`: `PAPER_EXECUTOR` or `BINANCE`

The persistence schema supports multiple Trade Fills for one Order so a future
Live adapter can record Binance partial fills without changing the history model.

### 5.3 Identity and Deduplication

- Paper Fill IDs are deterministic execution identifiers produced by the Paper
  Executor.
- Future Live records use the Binance Trade ID together with Bot-owned Order
  identity as their external deduplication key.
- Duplicate Fill delivery is idempotent and must not change Basket totals.
- All records are scoped directly by `session_id`; there is no Account Profile
  identifier.

## 6. Profit Calculation

The history displays `Net Realized PnL` after execution costs.

For Paper Spot:

```text
gross_realized_pnl =
    total_sell_proceeds - allocated_cost_of_sold_assets

net_realized_pnl =
    gross_realized_pnl - buy_fees - sell_fees
```

For Paper Futures, the existing shared Futures PnL policy provides gross realized
PnL. The history calculation is:

```text
net_realized_pnl =
    gross_realized_pnl - trading_fees - funding_fee
```

In Phase 1, Paper Futures always persists `funding_fee = 0.00`.

All monetary calculations use the project's decimal policy. Binary floating-point
values must not be used for persisted trading amounts.

Future Live history must use actual Binance execution price, quantity, commission,
realized PnL, and income data. It must not present expected order values as actual
results.

## 7. Recording Flow

1. The Strategy creates an Order Intent.
2. The Paper Executor simulates execution and emits actual Paper Fill events.
3. The Trade History Service validates and normalizes each Fill.
4. SQLite stores the Trade Fill and updates the related Basket Result in one
   database transaction.
5. When the Basket remains open, its status remains `OPEN`.
6. When the Basket closes, the service persists final gross PnL, fees, funding,
   and Net Realized PnL and changes its status to `CLOSED`.
7. The UI refreshes its query model from SQLite.

If persistence fails, the operation is rolled back and the application fails
closed by preventing new Entries. There is no in-memory fallback for durable
trade history.

## 8. Future Live Recording

Live recording is not implemented in this feature, but the shared records must
support it without migration of Paper history.

The future Live flow will:

1. Add a Bot-owned client order identity containing the Session scope.
2. Receive actual execution events from Binance.
3. Ignore manual and externally created orders.
4. Persist normalized Binance Trade Fills idempotently.
5. Reconcile missing fills and income records after reconnect.
6. Block new Entries until reconciliation confirms durable history is current.

Live credentials remain in OS Keyring and are never stored in SQLite.

## 9. Trade History UI

The Trade History screen contains two connected tables.

### 9.1 Basket History

The top table displays:

- Closed At
- Mode
- Market
- Symbol
- Timeframe
- Entries
- Invested or Notional
- Gross PnL
- Trading Fees
- Funding Fee
- Net PnL
- Status

It sorts newest records first and supports filters for Symbol, Timeframe, Market
Type, Trade Mode, Status, and UTC date range. The summary displays total closed
Net PnL for the filtered result.

Pagination prevents the UI from loading the complete history into memory.

### 9.2 Trade Fills

Selecting a Basket loads its fills in execution order. The detail table displays:

- Filled At
- Side
- Entry Number
- Price
- Quantity
- Notional
- Commission
- Realized PnL
- Source

Positive results use a positive-state color, negative results use a
negative-state color, and zero uses a neutral color. Color is supplementary;
signed numeric values remain visible.

## 10. Failure Handling

- A duplicate Fill is acknowledged without creating another record or changing
  totals.
- An unknown Basket or invalid Session relationship rejects the Fill.
- A Basket cannot transition from `CLOSED` back to `OPEN`.
- A closed Basket cannot accept another Fill.
- Fill persistence and Basket aggregation commit or roll back together.
- SQLite unavailability blocks Session start or new Entries.
- UI query failures show an explicit unavailable state and do not fabricate zero
  balances or PnL.
- Future Live reconnect enters reconciliation before new Entries are allowed.

## 11. Verification

Automated verification must cover:

- Multi-entry Paper Spot BUY fills followed by SELL and correct gross PnL, fees,
  and Net PnL.
- Paper Futures realized PnL and trading fees with zero Funding Fee.
- Multiple partial fills for one Order.
- Idempotent duplicate Fill delivery.
- Atomic Trade Fill and Basket Result persistence.
- Open Basket exclusion from closed Net PnL totals.
- Persistence across application restart.
- Query filters, ordering, pagination, Basket selection, and filtered Net PnL
  totals.
- Rejection of records that are not owned by the Bot Session.
- Fail-closed behavior when SQLite is unavailable.
- Absence of Binance Private API calls and Live orders in Phase 1 tests.
- Unit, integration, persistence, and UI view-model tests.
- Ruff lint, format check, mypy, and `git diff --check`.

## 12. Non-Goals

Phase 1 does not include:

- Candlestick charts or BUY/SELL markers on a chart
- General historical market-data browsing
- CSV export
- Manual editing of history
- Importing manual or pre-existing Binance trades
- Live execution or Private API integration
- Paper Futures funding simulation
- Multi-account or Binance sub-account support
