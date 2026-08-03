from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.qt_interactions import click
from tiewtrade.application.bot_control import BotLifecycleResult
from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    OpenOrderSnapshot,
    configured_workspace_snapshot,
    failed_workspace_snapshot,
    loading_open_orders_tab,
    ready_open_orders_tab,
    ready_position_basket_tab,
    stale_workspace_snapshot,
)
from tiewtrade.ui.candlestick_chart import CandlestickChartWidget
from tiewtrade.ui.notification_center import NotificationStore
from tiewtrade.ui.trading_workspace import TradingWorkspace


def test_workspace_places_existing_features_in_one_screen(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    assert workspace.header_symbol.text() == "No Session"
    assert isinstance(workspace.chart, CandlestickChartWidget)
    assert workspace.tabs.tabText(0) == "Open Orders"
    assert workspace.tabs.tabText(1) == "Position / Basket"
    assert workspace.tabs.tabText(2) == "Trade History"
    assert workspace.open_orders.state_label.text() == "No open orders"
    assert workspace.position_basket.state_label.text() == (
        "No open Position or Basket"
    )
    assert workspace.setup.isVisible()


def test_workspace_places_candlestick_chart_above_tables_with_docked_bot_control(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    qtbot.waitUntil(lambda: workspace.chart.isVisible())

    assert workspace.chart.geometry().bottom() < workspace.tabs.geometry().top()
    assert workspace.bot_control.isVisible()


def test_chart_snapshot_changes_only_the_chart(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    snapshot = ChartSnapshot(
        session=configured_spot_session(),
        chart_range=ChartRange(
            datetime(2026, 8, 2, 0, tzinfo=UTC),
            datetime(2026, 8, 2, 0, 20, tzinfo=UTC),
        ),
        observed_at_utc=datetime(2026, 8, 2, 0, 20, tzinfo=UTC),
        candles=(),
        fills=(),
        state=ChartReadState.UNAVAILABLE,
        message="Chart is unavailable",
    )

    workspace.chart.show_snapshot(snapshot)

    assert workspace.chart._snapshot is snapshot
    assert workspace.setup.isVisible()
    assert workspace.bot_control.isVisible()
    assert workspace.open_orders.state_label.text() == "No open orders"


def test_workspace_tabs_render_independent_scoped_states(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    observed_at = datetime(2026, 8, 2, 1, 2, 4, tzinfo=UTC)
    ready_orders = ready_open_orders_tab(
        (
            OpenOrderSnapshot(
                order_id="order-1",
                created_at_utc=observed_at,
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                price=Decimal("66321.1200"),
                quantity=Decimal("0.00300000"),
                filled_quantity=Decimal("0.00100000"),
                status="partially_filled",
            ),
        ),
        observed_at_utc=observed_at,
    )
    basket = BasketSnapshot(
        symbol="BTCUSDT",
        market_type="spot",
        entry_count=1,
        total_quantity=Decimal("0.00300000"),
        average_entry_price=Decimal("66000.0000"),
        current_price=Decimal("66321.1200"),
        take_profit_price=Decimal("67000.0000"),
        unrealized_pnl=Decimal("0.96336000"),
        liquidation_price=None,
        lifecycle="active_pair",
        updated_at_utc=observed_at,
    )
    snapshot = replace(
        configured_workspace_snapshot(
            configured_spot_session(), observed_at_utc=observed_at
        ),
        open_orders=loading_open_orders_tab(ready_orders),
        position_basket=ready_position_basket_tab(basket, observed_at_utc=observed_at),
    )

    workspace.show_workspace_snapshot(snapshot)

    assert workspace.open_orders.state_label.text() == "Loading Open Orders…"
    assert workspace.open_orders.table.rowCount() == 1
    assert workspace.position_basket.state_label.text() == ""
    assert workspace.position_basket.table.rowCount() == 1


def test_snapshot_updates_all_persistent_header_facts(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    snapshot = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    workspace.show_workspace_snapshot(snapshot)

    assert workspace.header_symbol.text() == "BTCUSDT"
    assert workspace.header_timeframe.text() == "5m"
    assert workspace.header_mode.text() == "Paper"
    assert workspace.header_market_type.text() == "Spot"
    assert workspace.header_preset.text() == "RSI Step Grid v1"
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.header_freshness.text() == "Market data not started"
    assert workspace.header_read_state.text() == "Ready"


def test_notification_header_and_drawer_render_and_acknowledge_in_memory_only(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1024, 700)
    workspace.show()
    snapshot = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 2, 9, 30, tzinfo=UTC),
    )
    assert snapshot.header is not None
    blocked_workspace = replace(
        snapshot,
        header=replace(snapshot.header, runtime_state=BotRuntimeState.BLOCKED),
    )
    store = NotificationStore()
    store.publish(
        BotLifecycleResult(
            workspace=blocked_workspace,
            blocked_reason="Paper Bot recovery required",
        ),
        occurred_at_utc=datetime(2026, 8, 2, 9, 30, tzinfo=UTC),
    )

    workspace.show_workspace_snapshot(blocked_workspace)
    workspace.show_notifications(store)

    assert workspace.notification_button.text() == "Notifications · 1"
    assert workspace.notification_button.accessibleName() == (
        "Notifications: 1 unread; highest severity Critical"
    )
    click(workspace.notification_button)
    qtbot.waitUntil(workspace.notification_drawer.isVisible)
    assert workspace.notification_rows[0].text() == (
        "2026-08-02 09:30:00 UTC · Critical · Safety · Paper Bot recovery required"
    )

    click(workspace.notification_acknowledge_buttons[0])

    assert store.unread_count == 0
    assert workspace.notification_button.text() == "Notifications · 0"
    assert workspace.notification_button.accessibleName() == "Notifications: 0 unread"
    assert workspace.notification_acknowledge_buttons[0].accessibleName() == (
        "Acknowledged notification: Paper Bot recovery required"
    )
    assert workspace.header_runtime.text() == "Blocked"


def test_error_and_stale_snapshots_keep_header_facts_visible(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    ready = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    expected_facts = ("BTCUSDT", "5m", "Paper", "Spot", "RSI Step Grid v1")

    for snapshot, read_state in (
        (failed_workspace_snapshot(ready, "Workspace data is unavailable"), "Error"),
        (stale_workspace_snapshot(ready), "Stale"),
    ):
        workspace.show_workspace_snapshot(snapshot)
        assert (
            workspace.header_symbol.text(),
            workspace.header_timeframe.text(),
            workspace.header_mode.text(),
            workspace.header_market_type.text(),
            workspace.header_preset.text(),
        ) == expected_facts
        assert workspace.header_read_state.text() == read_state


def test_ui_modules_do_not_import_prohibited_adapters() -> None:
    ui_paths = Path("src/tiewtrade/ui").glob("*.py")
    ui_source = "\n".join(path.read_text() for path in ui_paths)
    for prohibited in (
        "tiewtrade.integrations.sqlite",
        "tiewtrade.strategies",
        "binance",
        "tiewtrade.execution",
    ):
        assert prohibited not in ui_source


def test_bot_control_is_docked_at_wide_width(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    qtbot.waitUntil(lambda: not workspace.compact_mode)

    assert workspace.bot_control.isVisible()
    assert not workspace.bot_control_button.isVisible()
    assert not workspace.bot_control_close_button.isVisible()


def test_bot_control_uses_drawer_below_breakpoint(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1199, 700)
    workspace.show()
    workspace.activateWindow()

    qtbot.waitUntil(workspace.isActiveWindow)

    qtbot.waitUntil(lambda: workspace.compact_mode)
    assert not workspace.bot_control.isVisible()
    assert workspace.bot_control_button.isVisible()

    click(workspace.bot_control_button)

    assert workspace.bot_control.isVisible()
    assert workspace.bot_control.geometry().right() == workspace.rect().right()
    assert workspace.bot_control_close_button.isVisible()
    assert workspace.bot_control_close_button.hasFocus()

    click(workspace.bot_control_close_button)

    assert not workspace.bot_control.isVisible()
    assert workspace.bot_control_button.hasFocus()


def test_escape_closes_compact_bot_control_and_restores_trigger_focus(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1024, 700)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)
    qtbot.waitUntil(lambda: workspace.compact_mode)

    click(workspace.bot_control_button)
    QTest.keyClick(workspace.bot_control_close_button, Qt.Key.Key_Escape)

    qtbot.waitUntil(lambda: not workspace.bot_control.isVisible())
    assert workspace.bot_control_button.hasFocus()


def test_escape_shortcut_is_active_only_while_compact_drawer_is_open(
    qtbot: QtBot,
) -> None:
    class CountingWorkspace(TradingWorkspace):
        def __init__(self) -> None:
            self.close_calls = 0
            super().__init__()

        def close_bot_control(self) -> None:
            self.close_calls += 1
            super().close_bot_control()

    workspace = CountingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1024, 700)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)
    qtbot.waitUntil(lambda: workspace.compact_mode)

    assert not workspace._drawer_close_shortcut.isEnabled()
    QTest.keyClick(workspace.bot_control_button, Qt.Key.Key_Escape)
    assert workspace.close_calls == 0

    click(workspace.bot_control_button)
    assert workspace._drawer_close_shortcut.isEnabled()
    workspace.resize(1200, 700)
    qtbot.waitUntil(lambda: not workspace.compact_mode)

    assert not workspace._drawer_close_shortcut.isEnabled()
    QTest.keyClick(workspace.tabs, Qt.Key.Key_Escape)
    assert workspace.close_calls == 0

    workspace.resize(1024, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)
    QTest.keyClick(workspace.bot_control_close_button, Qt.Key.Key_Escape)

    assert workspace.close_calls == 1
    assert not workspace._drawer_close_shortcut.isEnabled()
    QTest.keyClick(workspace.bot_control_button, Qt.Key.Key_Escape)
    assert workspace.close_calls == 1


def test_resize_transitions_do_not_duplicate_drawer_close_connection(
    qtbot: QtBot,
) -> None:
    class CountingWorkspace(TradingWorkspace):
        def __init__(self) -> None:
            self.close_calls = 0
            super().__init__()

        def close_bot_control(self) -> None:
            self.close_calls += 1
            super().close_bot_control()

    workspace = CountingWorkspace()
    qtbot.addWidget(workspace)
    workspace.show()

    for width in (1200, 1024, 1200, 1024):
        workspace.resize(width, 700)
        expected_compact = width < 1200
        qtbot.waitUntil(partial(_has_compact_mode, workspace, expected_compact))

    click(workspace.bot_control_button)
    click(workspace.bot_control_close_button)

    assert workspace.close_calls == 1


def test_resizing_keeps_the_same_bot_control_and_workspace_state(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    session = configured_spot_session()
    bot_instances = (
        workspace.bot_control,
        workspace._bot_pages,
        workspace.setup,
        workspace.overview,
        workspace.unavailable_panel,
    )

    workspace.show_workspace_snapshot(
        configured_workspace_snapshot(
            session,
            observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        )
    )
    workspace.show_configured_session(session)
    workspace.tabs.setCurrentWidget(workspace.trade_history)
    workspace.resize(1199, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)
    workspace.resize(1200, 700)
    qtbot.waitUntil(lambda: not workspace.compact_mode)

    assert (
        workspace.bot_control,
        workspace._bot_pages,
        workspace.setup,
        workspace.overview,
        workspace.unavailable_panel,
    ) == bot_instances
    assert workspace.overview.isVisible()
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.tabs.currentWidget() is workspace.trade_history
    assert workspace.bot_control.isVisible()


def test_configured_session_updates_header_and_bot_control(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    session = configured_spot_session()

    workspace.show_workspace_snapshot(
        configured_workspace_snapshot(
            session,
            observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        )
    )
    workspace.show_configured_session(session)

    assert workspace.header_symbol.text() == session.market_data.symbol
    assert workspace.header_timeframe.text() == session.market_data.timeframe
    assert workspace.header_mode.text() == "Paper"
    assert workspace.header_market_type.text() == "Spot"
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.header_freshness.text() == "Market data not started"
    assert workspace.overview.isVisible()


def test_compact_bot_control_trigger_exposes_current_state(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)

    assert workspace.bot_control_button.text() == "Bot Control · No Session"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: No Session"

    session = configured_spot_session()
    workspace.show_workspace_snapshot(
        configured_workspace_snapshot(
            session,
            observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        )
    )
    workspace.show_configured_session(session)

    assert workspace.bot_control_button.text() == "Bot Control · Configured"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: Configured"

    workspace.show_unavailable("Session storage is unavailable")

    assert workspace.bot_control_button.text() == "Bot Control · Unavailable"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: Unavailable"

    workspace.show_setup()

    assert workspace.bot_control_button.text() == "Bot Control · No Session"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: No Session"


@pytest.mark.parametrize("transition", ["setup", "configured", "unavailable"])
def test_bot_control_state_transition_resets_scrolled_setup_to_top(
    qtbot: QtBot,
    transition: str,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setFixedSize(1024, 700)
    workspace.show()
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)
    click(workspace.setup.advanced_toggle)
    vertical = workspace.bot_control_scroll.verticalScrollBar()
    horizontal = workspace.bot_control_scroll.horizontalScrollBar()
    qtbot.waitUntil(lambda: vertical.maximum() > 0)
    vertical.setValue(vertical.maximum())

    target: QWidget = workspace.setup.trade_mode_label
    if transition == "configured":
        session = configured_spot_session()
        workspace.show_workspace_snapshot(
            configured_workspace_snapshot(
                session,
                observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
            )
        )
        workspace.show_configured_session(session)
        target = workspace.overview.state_value
    elif transition == "unavailable":
        workspace.show_unavailable("Session storage is unavailable")
        target = workspace.unavailable_retry_button
    else:
        workspace.show_setup()

    assert vertical.value() == 0
    assert horizontal.value() == 0
    assert (
        workspace.bot_control_scroll.viewport()
        .rect()
        .intersects(
            _widget_rect_in_viewport(target, workspace.bot_control_scroll.viewport())
        )
    )


@pytest.mark.parametrize("content", ["spot", "futures", "advanced"])
def test_bot_control_content_is_scrollable_at_minimum_window_size(
    qtbot: QtBot,
    content: str,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setFixedSize(1024, 700)
    workspace.show()
    assert (workspace.width(), workspace.height()) == (1024, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)

    target: QWidget = workspace.setup.spot_ratio
    if content == "futures":
        workspace.setup.market_type.setCurrentIndex(
            workspace.setup.market_type.findData("futures")
        )
        target = workspace.setup.leverage
    elif content == "advanced":
        workspace.setup.market_type.setCurrentIndex(
            workspace.setup.market_type.findData("futures")
        )
        click(workspace.setup.advanced_toggle)
        target = workspace.setup.fee_percent

    scroll_bar = workspace.bot_control_scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: scroll_bar.maximum() > 0)

    workspace.bot_control_scroll.ensureWidgetVisible(target)
    qtbot.waitUntil(
        lambda: (
            workspace.bot_control_scroll.viewport()
            .rect()
            .contains(
                _widget_rect_in_viewport(
                    target, workspace.bot_control_scroll.viewport()
                )
            )
        )
    )

    assert scroll_bar.maximum() > 0
    assert workspace.bot_control_scroll.widget() is workspace._bot_pages


def test_trade_history_signal_is_emitted_when_tab_is_opened(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)

    with qtbot.waitSignal(workspace.trade_history_activated):
        workspace.tabs.setCurrentWidget(workspace.trade_history)


def test_unavailable_state_and_busy_control_are_scoped_to_bot_control(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    workspace.show_unavailable("Paper Session unavailable")
    workspace.set_bot_busy(True)

    assert workspace.unavailable_message.text() == "Paper Session unavailable"
    assert workspace.unavailable_panel.isVisible()
    assert workspace.header_runtime.text() == "No Session"
    assert not workspace.unavailable_retry_button.isEnabled()
    assert not workspace.setup.create_button.isEnabled()


def _widget_rect_in_viewport(widget: QWidget, viewport: QWidget) -> QRect:
    return QRect(widget.mapTo(viewport, QPoint(0, 0)), widget.size())


def _has_compact_mode(workspace: TradingWorkspace, expected: bool) -> bool:
    return workspace.compact_mode is expected
