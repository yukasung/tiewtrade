from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal, localcontext

from PySide6.QtWidgets import QMessageBox, QPushButton
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.qt_interactions import click
from tiewtrade.application.bot_control import (
    BotControlAction,
    BotControlSnapshot,
    configured_bot_control,
    workspace_with_runtime_state,
)
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    DataFreshness,
)
from tiewtrade.ui.bot_control import BotControlWidget, _decimal_text


def test_configured_shows_immutable_overview_and_disabled_start_without_runtime(
    qtbot: QtBot,
) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    widget.show()
    session = configured_spot_session()

    widget.show_snapshot(
        configured_bot_control(
            session,
            observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        )
    )

    assert widget.overview.session_id_value.text() == str(session.config.session_id)
    assert widget.state_value.text() == "Configured"
    assert widget.start_button.text() == "Start Bot"
    assert widget.start_button.isVisible()
    assert not widget.start_button.isEnabled()
    assert widget.stop_button.isHidden()
    assert widget.recover_button.isHidden()
    assert widget.supporting_text.text() == "Runtime integration is not available yet"
    assert widget.findChildren(QPushButton, "manualBuyButton") == []
    assert widget.findChildren(QPushButton, "manualSellButton") == []


def test_initial_state_hides_recovery_requirement(qtbot: QtBot) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    widget.show()

    assert widget.recovery_required.isHidden()


def test_running_shows_runtime_and_basket_facts_without_manual_order_controls(
    qtbot: QtBot,
) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    widget.show()
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        actions=frozenset({BotControlAction.START}),
    )
    workspace = replace(
        workspace_with_runtime_state(
            configured.workspace,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        ),
        basket=BasketSnapshot(
            symbol="BTCUSDT",
            market_type="spot",
            entry_count=2,
            total_quantity=Decimal("1"),
            average_entry_price=Decimal("64000"),
            current_price=Decimal("65000"),
            take_profit_price=Decimal("66000"),
            unrealized_pnl=Decimal("1000"),
            liquidation_price=None,
            lifecycle="open",
            updated_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
        ),
    )
    running = BotControlSnapshot(
        state=BotRuntimeState.RUNNING,
        session=configured.session,
        workspace=workspace,
        available_actions=frozenset({BotControlAction.STOP}),
    )

    widget.show_snapshot(running)

    assert widget.state_value.text() == "Running"
    assert widget.data_freshness_value.text() == "Fresh"
    assert widget.overview.state_value.text() == "Immutable Configuration"
    assert widget.entry_count_value.text() == "2"
    assert widget.average_entry_value.text() == "64000 USDT"
    assert widget.current_price_value.text() == "65000 USDT"
    assert widget.take_profit_value.text() == "66000 USDT"
    assert widget.stop_button.isVisible()
    assert widget.stop_button.text() == "Stop Session"
    assert widget.findChildren(QPushButton, "manualBuyButton") == []
    assert widget.findChildren(QPushButton, "manualSellButton") == []


def test_configured_and_blocked_show_readable_data_freshness(qtbot: QtBot) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    widget.show_snapshot(configured)
    assert widget.data_freshness_value.text() == "Not Started"

    assert configured.workspace.header is not None
    blocked_workspace = workspace_with_runtime_state(
        configured.workspace, BotRuntimeState.BLOCKED
    )
    assert blocked_workspace.header is not None
    blocked_workspace = replace(
        blocked_workspace,
        header=replace(
            blocked_workspace.header,
            data_freshness=DataFreshness.UNAVAILABLE,
        ),
    )
    blocked = BotControlSnapshot(
        state=BotRuntimeState.BLOCKED,
        session=configured.session,
        workspace=blocked_workspace,
        available_actions=frozenset(),
        blocked_reason="Paper Bot recovery failed",
    )
    widget.show_snapshot(blocked)

    assert widget.data_freshness_value.text() == "Unavailable"


def test_progress_blocked_and_stopped_states_expose_only_their_allowed_actions(
    qtbot: QtBot,
) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    widget.show()
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    starting = BotControlSnapshot(
        state=BotRuntimeState.STARTING,
        session=configured.session,
        workspace=workspace_with_runtime_state(
            configured.workspace, BotRuntimeState.STARTING
        ),
        available_actions=frozenset(),
        progress_message="Starting Paper Bot",
    )
    widget.show_snapshot(starting)
    assert widget.supporting_text.text() == "Starting Paper Bot"
    assert not widget.start_button.isEnabled()

    stopping = BotControlSnapshot(
        state=BotRuntimeState.STOPPING,
        session=configured.session,
        workspace=workspace_with_runtime_state(
            configured.workspace, BotRuntimeState.STOPPING
        ),
        available_actions=frozenset(),
        progress_message="Stopping Paper Bot",
    )
    widget.show_snapshot(stopping)
    assert widget.supporting_text.text() == "Stopping Paper Bot"
    assert widget.stop_button.isVisible()
    assert not widget.stop_button.isEnabled()

    blocked = BotControlSnapshot(
        state=BotRuntimeState.BLOCKED,
        session=configured.session,
        workspace=workspace_with_runtime_state(
            configured.workspace, BotRuntimeState.BLOCKED
        ),
        available_actions=frozenset({BotControlAction.RECOVER}),
        blocked_reason="Paper Bot could not be started",
    )
    widget.show_snapshot(blocked)
    assert widget.state_value.text() == "Blocked"
    assert widget.supporting_text.text() == "Paper Bot could not be started"
    assert widget.recovery_required.isVisible()
    assert widget.recover_button.isVisible()
    assert widget.start_button.isHidden()
    assert widget.stop_button.isHidden()

    stopped = BotControlSnapshot(
        state=BotRuntimeState.STOPPED,
        session=configured.session,
        workspace=workspace_with_runtime_state(
            configured.workspace, BotRuntimeState.STOPPED
        ),
        available_actions=frozenset(),
    )
    widget.show_snapshot(stopped)
    assert widget.state_value.text() == "Stopped"
    assert widget.start_button.isHidden()
    assert widget.stop_button.isHidden()
    assert widget.recover_button.isHidden()


def test_enabled_action_emits_once_and_disables_repeated_submission(
    qtbot: QtBot,
) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget.show_snapshot(
        configured_bot_control(
            configured_spot_session(),
            observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
            actions=frozenset({BotControlAction.START}),
        )
    )
    assert widget.start_button.isEnabled()

    with qtbot.waitSignal(widget.start_requested):
        click(widget.start_button)
    click(widget.start_button)

    assert not widget.start_button.isEnabled()


def test_stop_cancel_does_not_emit_and_returns_focus(qtbot: QtBot) -> None:
    callbacks: list[tuple[Callable[[], None], Callable[[], None]]] = []

    def confirm_stop(confirm: Callable[[], None], cancel: Callable[[], None]) -> None:
        callbacks.append((confirm, cancel))

    widget = BotControlWidget(stop_confirmation=confirm_stop)
    qtbot.addWidget(widget)
    widget.show()
    widget.show_snapshot(_running_snapshot())
    emissions: list[None] = []
    widget.stop_requested.connect(lambda: emissions.append(None))

    click(widget.stop_button)

    assert len(callbacks) == 1
    assert emissions == []
    confirm, cancel = callbacks[0]
    cancel()

    assert emissions == []
    assert widget.stop_button.isEnabled()
    qtbot.waitUntil(widget.stop_button.hasFocus)


def test_stop_confirm_emits_once_and_guards_repeated_confirmation(qtbot: QtBot) -> None:
    callbacks: list[tuple[Callable[[], None], Callable[[], None]]] = []

    def confirm_stop(confirm: Callable[[], None], cancel: Callable[[], None]) -> None:
        callbacks.append((confirm, cancel))

    widget = BotControlWidget(stop_confirmation=confirm_stop)
    qtbot.addWidget(widget)
    widget.show()
    widget.show_snapshot(_running_snapshot())
    emissions: list[None] = []
    widget.stop_requested.connect(lambda: emissions.append(None))

    click(widget.stop_button)
    click(widget.stop_button)

    assert len(callbacks) == 1
    confirm, _cancel = callbacks[0]
    confirm()
    confirm()

    assert emissions == [None]
    assert not widget.stop_button.isEnabled()
    qtbot.waitUntil(widget.state_value.hasFocus)


def test_default_stop_confirmation_is_destructive_and_default_safe(
    qtbot: QtBot,
) -> None:
    widget = BotControlWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget.show_snapshot(_running_snapshot())
    emissions: list[None] = []
    widget.stop_requested.connect(lambda: emissions.append(None))

    click(widget.stop_button)

    dialog = next(
        child
        for child in widget.findChildren(QMessageBox)
        if child.text() == "Stop this Paper Bot session?"
    )
    assert dialog.isVisible()
    assert dialog.text() == "Stop this Paper Bot session?"
    assert "Existing Basket Take Profit stays active" in dialog.informativeText()
    cancel_button = next(
        button for button in dialog.buttons() if button.text() == "Cancel"
    )
    stop_button = next(
        button for button in dialog.buttons() if button.text() == "Stop Session"
    )
    assert dialog.defaultButton() is cancel_button
    assert dialog.buttonRole(stop_button) is QMessageBox.ButtonRole.DestructiveRole

    click(cancel_button)

    assert emissions == []
    qtbot.waitUntil(widget.stop_button.hasFocus)


def test_decimal_text_is_context_independent_and_exact() -> None:
    with localcontext() as context:
        context.prec = 4
        assert (
            _decimal_text(Decimal("12345678901234567890.123456789012345678900"))
            == "12345678901234567890.1234567890123456789"
        )

    assert _decimal_text(Decimal("0")) == "0"
    assert _decimal_text(Decimal("-0.0000")) == "0"


def _running_snapshot() -> BotControlSnapshot:
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    return BotControlSnapshot(
        state=BotRuntimeState.RUNNING,
        session=configured.session,
        workspace=workspace_with_runtime_state(
            configured.workspace,
            BotRuntimeState.RUNNING,
            data_freshness=DataFreshness.FRESH,
        ),
        available_actions=frozenset({BotControlAction.STOP}),
    )
