from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.bot_control import BotControlAction, BotControlSnapshot
from tiewtrade.application.trading_workspace import BotRuntimeState
from tiewtrade.ui.session_overview import SessionOverviewWidget


class BotControlWidget(QWidget):
    start_requested = Signal()
    stop_requested = Signal()
    recover_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("botControlWidget")
        self.overview = SessionOverviewWidget()
        self.state_value = QLabel("—")
        self.state_value.setObjectName("botControlState")
        self.supporting_text = QLabel()
        self.supporting_text.setObjectName("supportingText")
        self.supporting_text.setWordWrap(True)
        self.recovery_required = QLabel("Recovery Required")
        self.recovery_required.setObjectName("recoveryRequired")
        self.entry_count_value = QLabel("—")
        self.average_entry_value = QLabel("—")
        self.current_price_value = QLabel("—")
        self.take_profit_value = QLabel("—")
        self.start_button = QPushButton("Start Bot")
        self.start_button.setObjectName("startBotButton")
        self.stop_button = QPushButton("Stop Session")
        self.stop_button.setObjectName("stopSessionButton")
        self.stop_button.setProperty("destructive", True)
        self.recover_button = QPushButton("Recover")
        self.recover_button.setObjectName("recoverBotButton")
        self.start_button.clicked.connect(self._start_clicked)
        self.stop_button.clicked.connect(self._stop_clicked)
        self.recover_button.clicked.connect(self._recover_clicked)
        self._build_layout()
        self._hide_actions()
        self.recovery_required.hide()

    @Slot(object)
    def show_snapshot(self, value: object) -> None:
        if not isinstance(value, BotControlSnapshot):
            return
        self.overview.show_session(
            value.session,
            configuration_summary=value.state is not BotRuntimeState.CONFIGURED,
        )
        self.state_value.setText(_STATE_TEXT[value.state])
        self.recovery_required.setVisible(value.state is BotRuntimeState.BLOCKED)
        self._show_basket_facts(value)
        self._show_state_content(value)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_layout = QVBoxLayout(status_card)
        state_label = QLabel("BOT STATE")
        state_label.setObjectName("eyebrow")
        status_layout.addWidget(state_label)
        status_layout.addWidget(self.state_value)
        status_layout.addWidget(self.supporting_text)
        status_layout.addWidget(self.recovery_required)
        root.addWidget(status_card)

        facts = QFrame()
        facts.setObjectName("card")
        fact_grid = QGridLayout(facts)
        for row, (label, value) in enumerate(
            (
                ("Entries", self.entry_count_value),
                ("Average Entry", self.average_entry_value),
                ("Current Price", self.current_price_value),
                ("Take Profit", self.take_profit_value),
            )
        ):
            fact_grid.addWidget(QLabel(label), row, 0)
            fact_grid.addWidget(value, row, 1)
        root.addWidget(facts)
        root.addWidget(self.overview)

        actions = QHBoxLayout()
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.recover_button)
        root.addLayout(actions)

    def _show_basket_facts(self, snapshot: BotControlSnapshot) -> None:
        basket = snapshot.workspace.basket
        if basket is None:
            self.entry_count_value.setText("—")
            self.average_entry_value.setText("—")
            self.current_price_value.setText("—")
            self.take_profit_value.setText("—")
            return
        self.entry_count_value.setText(str(basket.entry_count))
        self.average_entry_value.setText(
            f"{_decimal_text(basket.average_entry_price)} USDT"
        )
        self.current_price_value.setText(f"{_decimal_text(basket.current_price)} USDT")
        self.take_profit_value.setText(
            f"{_decimal_text(basket.take_profit_price)} USDT"
        )

    def _show_state_content(self, snapshot: BotControlSnapshot) -> None:
        self._hide_actions()
        state = snapshot.state
        if state is BotRuntimeState.CONFIGURED:
            self.supporting_text.setText(
                ""
                if BotControlAction.START in snapshot.available_actions
                else "Runtime integration is not available yet"
            )
            self._show_action(
                self.start_button, BotControlAction.START in snapshot.available_actions
            )
            return
        if state is BotRuntimeState.STARTING:
            self.supporting_text.setText(snapshot.progress_message or "")
            self._show_action(self.start_button, False)
            return
        if state is BotRuntimeState.RUNNING:
            self.supporting_text.setText("Paper Bot is running")
            self._show_action(
                self.stop_button, BotControlAction.STOP in snapshot.available_actions
            )
            return
        if state is BotRuntimeState.STOPPING:
            self.supporting_text.setText(snapshot.progress_message or "")
            self._show_action(self.stop_button, False)
            return
        if state is BotRuntimeState.STOPPED:
            self.supporting_text.setText("Paper Bot has stopped")
            return
        self.supporting_text.setText(snapshot.blocked_reason or "")
        if BotControlAction.RECOVER in snapshot.available_actions:
            self._show_action(self.recover_button, True)

    def _hide_actions(self) -> None:
        for button in (self.start_button, self.stop_button, self.recover_button):
            button.hide()
            button.setDisabled(True)

    @staticmethod
    def _show_action(button: QPushButton, enabled: bool) -> None:
        button.setEnabled(enabled)
        button.show()

    @Slot()
    def _start_clicked(self) -> None:
        self._emit_once(self.start_button, self.start_requested.emit)

    @Slot()
    def _stop_clicked(self) -> None:
        self._emit_once(self.stop_button, self.stop_requested.emit)

    @Slot()
    def _recover_clicked(self) -> None:
        self._emit_once(self.recover_button, self.recover_requested.emit)

    def _emit_once(
        self,
        button: QPushButton,
        emit: Callable[[], object],
    ) -> None:
        if not button.isEnabled():
            return
        button.setDisabled(True)
        emit()


_STATE_TEXT = {
    BotRuntimeState.CONFIGURED: "Configured",
    BotRuntimeState.STARTING: "Starting",
    BotRuntimeState.RUNNING: "Running",
    BotRuntimeState.STOPPING: "Stopping",
    BotRuntimeState.STOPPED: "Stopped",
    BotRuntimeState.BLOCKED: "Blocked",
}


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
