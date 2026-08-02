# Dark Candlestick Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a dark, Session-bound completed-candle chart with durable Buy/Sell Fill markers in the unified Trading Workspace.

**Architecture:** Immutable chart facts and range validation live in `application`; bounded public candles and durable fills are composed there; a focused PySide6 widget renders supplied facts. The UI workflow loads data off the Qt thread and discards stale request generations.

**Tech Stack:** Python 3.12, PySide6/QPainter, aiohttp, SQLite, pytest, pytest-qt, mypy, Ruff.

## Global Constraints

- Use only completed UTC candles from the immutable Session symbol and timeframe.
- Load visible historical ranges from public Binance data; never store chart candles in SQLite.
- Derive markers only from durable `TradeFill` records scoped to the Session and UTC range.
- UI must not import SQLite, Binance, strategy, execution, or credentials.
- Network and SQLite work must run through `BackgroundTask`, not the Qt event thread.
- A chart failure is a sanitized chart-only unavailable state and cannot block tables or Bot Control.
- Do not add manual Buy/Sell behavior, private endpoints, or change business policy.
- Preserve the dark Workspace and 1,200 px Bot Control breakpoint.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `application/chart_data.py` | Immutable range, marker, snapshot, completed-candle rules. |
| `application/chart_history.py` | Session-bound public candle and durable Fill composition. |
| `integrations/sqlite/trade_history.py` | Deterministic Session/range Fill query. |
| `ui/candlestick_chart.py` | QPainter chart surface and range controls. |
| `ui/chart_workflow.py` | Background requests, generation, completed updates. |
| `ui/trading_workspace.py` | Replaces the chart placeholder. |
| `ui/main_window.py`, `ui/desktop.py`, `desktop_main.py` | Workflow ownership and injected use cases. |

### Task 1: Immutable chart read model

**Files:**

- Create: `src/tiewtrade/application/chart_data.py`
- Create: `tests/unit/application/test_chart_data.py`

**Interfaces:** Produces `ChartRange`, `ChartMarker`, `ChartReadState`,
`ChartSnapshot`, and `append_completed_candle(snapshot, candle) -> ChartSnapshot`.

- [ ] **Step 1: Write the failing tests**

```python
def test_ready_snapshot_rejects_candle_from_another_session_timeframe() -> None:
    with pytest.raises(ValueError, match="candle timeframe must match Session"):
        ready_chart_snapshot(session, chart_range, candles=(candle("15m"),), fills=())

def test_append_completed_candle_replaces_same_open_time_and_keeps_order() -> None:
    result = append_completed_candle(ready_snapshot(), candle("5m", minute=10))
    assert tuple(item.open_time for item in result.candles) == tuple(
        sorted(item.open_time for item in result.candles)
    )
```

- [ ] **Step 2: Verify RED**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/application/test_chart_data.py -q`

Expected: FAIL because `chart_data` does not exist.

- [ ] **Step 3: Implement the minimal model**

Create the four immutable value types, validate UTC `[start, end)` ranges,
Session-bound candles/markers, and same-open-time replacement. No I/O occurs in
this module.

- [ ] **Step 4: Verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/application/test_chart_data.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/tiewtrade/application/chart_data.py tests/unit/application/test_chart_data.py && git commit -m "feat: add chart read model"`

### Task 2: Bounded public candles and durable Fill markers

**Files:**

- Create: `src/tiewtrade/application/chart_history.py`
- Modify: `src/tiewtrade/integrations/sqlite/trade_history.py`
- Create: `tests/unit/application/test_chart_history.py`
- Modify: `tests/unit/integrations/sqlite/test_trade_history.py`

**Interfaces:** Produces `ChartHistory.load(session, chart_range) -> ChartSnapshot`
and `SQLiteTradeHistory.list_session_fills(session_id, start_utc, end_utc) -> tuple[TradeFill, ...]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_chart_history_loads_only_requested_public_range_and_session_fills() -> None:
    snapshot = history.load(session, chart_range)
    assert source.requests == [(session.market_data, chart_range.start_utc, chart_range.end_utc)]
    assert [marker.fill_id for marker in snapshot.markers] == ["buy-1", "sell-1"]

def test_list_session_fills_orders_by_utc_then_fill_id_and_excludes_other_session() -> None:
    assert history.list_session_fills(SESSION_ID, START, END) == (first, second)
```

- [ ] **Step 2: Verify RED**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/application/test_chart_history.py tests/unit/integrations/sqlite/test_trade_history.py -q`

Expected: FAIL because the new use case and query do not exist.

- [ ] **Step 3: Implement bounded composition**

Use existing `HistoricalCandleSource.load_range()` with Session market data and
always close the source in `finally`. Query SQLite by `session_id` and
`filled_at_utc >= start AND filled_at_utc < end`, ordered by
`filled_at_utc, fill_id`. Compose only validated candles and fills into the
Task 1 snapshot.

- [ ] **Step 4: Verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/application/test_chart_history.py tests/unit/integrations/sqlite/test_trade_history.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/tiewtrade/application/chart_history.py src/tiewtrade/integrations/sqlite/trade_history.py tests/unit/application/test_chart_history.py tests/unit/integrations/sqlite/test_trade_history.py && git commit -m "feat: load chart history by visible range"`

### Task 3: Render chart facts and load asynchronously

**Files:**

- Create: `src/tiewtrade/ui/candlestick_chart.py`
- Create: `src/tiewtrade/ui/chart_workflow.py`
- Create: `tests/unit/ui/test_candlestick_chart.py`
- Create: `tests/unit/ui/test_chart_workflow.py`

**Interfaces:** Produces `CandlestickChartWidget`,
`ChartWorkflow.configure(session)`, `ChartWorkflow.load_range(chart_range)`, and
`ChartWorkflow.completed_candle(candle)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_chart_renders_durable_buy_and_sell_markers_without_action_buttons(qtbot: QtBot) -> None:
    chart.show_snapshot(ready_snapshot(markers=(buy_marker, sell_marker)))
    assert chart.accessibleName() == "Candlestick chart for BTCUSDT 5m"
    assert chart.findChildren(QPushButton, "manualOrderButton") == []

def test_latest_chart_request_wins_and_unavailable_is_chart_scoped(qtbot: QtBot) -> None:
    workflow.load_range(first_range)
    workflow.load_range(latest_range)
    assert snapshots[-1].visible_range == latest_range
```

- [ ] **Step 2: Verify RED**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ui/test_candlestick_chart.py tests/unit/ui/test_chart_workflow.py -q`

Expected: FAIL because the widget and workflow do not exist.

- [ ] **Step 3: Implement widget and workflow**

`CandlestickChartWidget` renders snapshot grid, completed candles, and only
durable Buy/Sell marker labels via `QPainter`. Its Previous and Next range
controls are keyboard accessible. `ChartWorkflow` uses `BackgroundTask`, gives
each request a generation, publishes only the latest generation, and maps an
exception to `Chart is unavailable` without emitting an Workspace failure.

- [ ] **Step 4: Verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ui/test_candlestick_chart.py tests/unit/ui/test_chart_workflow.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/tiewtrade/ui/candlestick_chart.py src/tiewtrade/ui/chart_workflow.py tests/unit/ui/test_candlestick_chart.py tests/unit/ui/test_chart_workflow.py && git commit -m "feat: render dark candlestick chart"`

### Task 4: Compose chart into Desktop Workspace

**Files:**

- Modify: `src/tiewtrade/ui/trading_workspace.py`
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `src/tiewtrade/ui/desktop.py`
- Modify: `src/tiewtrade/desktop_main.py`
- Modify: `src/tiewtrade/ui/theme.py`
- Modify: `tests/unit/ui/test_trading_workspace.py`
- Modify: `tests/unit/ui/test_main_window.py`
- Modify: `tests/unit/test_desktop_main.py`
- Create: `tests/acceptance/test_desktop_chart.py`

**Interfaces:** Consumes `ChartWorkflow` and `CandlestickChartWidget`; configures
the chart after Session readiness and preserves it through runtime Workspace
snapshots.

- [ ] **Step 1: Write the failing composition tests**

```python
def test_workspace_replaces_placeholder_with_chart_and_keeps_wide_bot_control_docked(qtbot: QtBot) -> None:
    workspace.resize(1200, 700)
    workspace.show()
    assert workspace.chart.isVisible()
    assert workspace.bot_control.isVisible()

def test_chart_unavailable_keeps_bot_control_and_history_usable(qtbot: QtBot) -> None:
    chart_workflow.fail_current_request()
    assert window.workspace.bot_control.isEnabled()
    assert window.workspace.trade_history.isEnabled()
```

- [ ] **Step 2: Verify RED**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/unit/test_desktop_main.py tests/acceptance/test_desktop_chart.py -q`

Expected: FAIL because composition does not yet supply the chart component.

- [ ] **Step 3: Implement focused composition**

Create `ChartWorkflow` in `MainWindow`, configure it from the existing
Session-ready signal, forward snapshots to the Workspace chart, and close it
with other workflows. Replace `chartPlaceholder`, add only chart-specific dark
theme rules, and inject the application chart use case in `desktop_main`.

- [ ] **Step 4: Verify GREEN and full branch**

Run:

`QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/unit/test_desktop_main.py tests/acceptance/test_desktop_chart.py -q`

`QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest -q`

`.venv/bin/python -m ruff check src tests`

`.venv/bin/python -m ruff format --check src tests`

`.venv/bin/python -m mypy`

`git diff --check`

Expected: every command exits 0.

- [ ] **Step 5: Commit**

Run: `git add src/tiewtrade/ui/trading_workspace.py src/tiewtrade/ui/main_window.py src/tiewtrade/ui/desktop.py src/tiewtrade/desktop_main.py src/tiewtrade/ui/theme.py tests/unit/ui/test_trading_workspace.py tests/unit/ui/test_main_window.py tests/unit/test_desktop_main.py tests/acceptance/test_desktop_chart.py && git commit -m "feat: compose workspace candlestick chart"`

## Plan Self-Review

- Spec coverage: Tasks 1–2 cover validated Session/range facts, public historical data, durable UTC Fill markers, and no candle cache. Task 3 covers rendering, completed updates, generation safety, and isolated failures. Task 4 covers responsive Workspace composition and full verification.
- Placeholder scan: no deferred behavior, vague validation, or unbound interface remains.
- Type consistency: `ChartRange`, `ChartSnapshot`, and `ChartWorkflow` are introduced before consumers; widgets receive only injected use cases and immutable snapshots.
