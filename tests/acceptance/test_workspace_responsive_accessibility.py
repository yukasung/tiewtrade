from dataclasses import replace
from datetime import UTC, datetime

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.qt_interactions import click
from tiewtrade.application.bot_control import BotLifecycleResult
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    configured_workspace_snapshot,
)
from tiewtrade.ui.notification_center import NotificationStore
from tiewtrade.ui.trading_workspace import TradingWorkspace


def test_breakpoint_reuses_bot_control_and_restores_keyboard_focus(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.show_configured_session(configured_spot_session())
    original_control = workspace.bot_control_widget

    workspace.resize(1200, 700)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)
    qtbot.waitUntil(lambda: not workspace.compact_mode)
    assert workspace.bot_control.isVisible()
    assert not workspace.bot_control_button.isVisible()

    workspace.resize(1199, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    assert workspace.bot_control_widget is original_control
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.bot_control_button.isVisible()

    click(workspace.bot_control_button)
    qtbot.waitUntil(workspace.bot_control.isVisible)
    assert workspace.bot_control_close_button.hasFocus()
    QTest.keyClick(workspace.bot_control_close_button, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not workspace.bot_control.isVisible())
    assert workspace.bot_control_button.hasFocus()


def test_notification_drawer_exposes_text_severity_and_keyboard_focus(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1199, 700)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)
    snapshot = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 3, 9, tzinfo=UTC),
    )
    assert snapshot.header is not None
    blocked = replace(
        snapshot,
        header=replace(snapshot.header, runtime_state=BotRuntimeState.BLOCKED),
    )
    store = NotificationStore()
    store.publish(
        BotLifecycleResult(
            workspace=blocked,
            blocked_reason="Paper Bot recovery required",
        ),
        occurred_at_utc=datetime(2026, 8, 3, 9, tzinfo=UTC),
    )
    workspace.show_workspace_snapshot(blocked)
    workspace.show_notifications(store)

    click(workspace.notification_button)
    qtbot.waitUntil(workspace.notification_drawer.isVisible)
    assert workspace.notification_close_button.hasFocus()
    assert "Critical" in workspace.notification_rows[0].text()
    assert workspace.header_runtime.text() == "Blocked"
    click(workspace.notification_close_button)
    assert workspace.notification_button.hasFocus()


def test_trading_tables_are_named_and_scroll_horizontally(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(760, 700)
    workspace.show()

    tables = (
        workspace.open_orders.table,
        workspace.position_basket.table,
        workspace.trade_history.basket_table,
        workspace.trade_history.fill_table,
    )
    for table in tables:
        assert table.accessibleName()
        assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        for column in range(table.columnCount()):
            table.setColumnWidth(column, 180)
        table.resize(360, 180)
        table.show()
        qtbot.waitUntil(lambda table=table: table.horizontalScrollBar().maximum() > 0)
