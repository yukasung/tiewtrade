from datetime import UTC, datetime

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.bot_control import BotControlSnapshot, configured_bot_control
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    DataFreshness,
    TradingWorkspaceSnapshot,
    WorkspaceReadState,
)
from tiewtrade.ui.bot_control import BotControlWidget
from tiewtrade.ui.preset_display import preset_display_name
from tiewtrade.ui.session_setup import SessionSetupWidget
from tiewtrade.ui.trade_history_page import TradeHistoryPage

BOT_CONTROL_BREAKPOINT = 1200
BOT_CONTROL_WIDTH = 360

_RUNTIME_STATE_TEXT = {
    BotRuntimeState.NO_SESSION: "No Session",
    BotRuntimeState.CONFIGURED: "Configured",
    BotRuntimeState.STARTING: "Starting",
    BotRuntimeState.RUNNING: "Running",
    BotRuntimeState.STOPPING: "Stopping",
    BotRuntimeState.STOPPED: "Stopped",
    BotRuntimeState.BLOCKED: "Blocked",
}
_DATA_FRESHNESS_TEXT = {
    DataFreshness.NOT_STARTED: "Market data not started",
    DataFreshness.FRESH: "Market data is fresh",
    DataFreshness.STALE: "Market data is stale",
    DataFreshness.UNAVAILABLE: "Market data is unavailable",
}
_READ_STATE_TEXT = {
    WorkspaceReadState.LOADING: "Loading",
    WorkspaceReadState.EMPTY: "Empty",
    WorkspaceReadState.READY: "Ready",
    WorkspaceReadState.ERROR: "Error",
    WorkspaceReadState.STALE: "Stale",
}


class TradingWorkspace(QWidget):
    trade_history_activated = Signal()
    start_bot_requested = Signal()
    stop_bot_requested = Signal()
    recover_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workspace")

        self.setup = SessionSetupWidget()
        self.bot_control_widget = BotControlWidget()
        self.overview = self.bot_control_widget.overview
        self.trade_history = TradeHistoryPage()

        self.unavailable_panel = QFrame()
        self.unavailable_message = QLabel()
        self.unavailable_message.setObjectName("unavailableMessage")
        self.unavailable_message.setWordWrap(True)
        self.unavailable_retry_button = QPushButton("Try Again")
        self.unavailable_retry_button.setProperty("retryButton", True)

        self.header_symbol = QLabel("No Session")
        self.header_timeframe = QLabel("—")
        self.header_mode = QLabel("—")
        self.header_market_type = QLabel("—")
        self.header_preset = QLabel("—")
        self.header_runtime = QLabel("No Session")
        self.header_freshness = QLabel("No Session")
        self.header_read_state = QLabel("Empty")

        self.chart_state = QLabel("Chart is not available yet")
        self.orders_state = QLabel("No open orders")
        self.position_state = QLabel("No open Position or Basket")

        self._bot_pages = QStackedWidget()
        self._bot_pages.setObjectName("botControlPages")
        self._bot_pages.addWidget(self.setup)
        self._bot_pages.addWidget(self.bot_control_widget)
        self._bot_pages.addWidget(self.unavailable_panel)
        self.bot_control_widget.start_requested.connect(self.start_bot_requested)
        self.bot_control_widget.stop_requested.connect(self.stop_bot_requested)
        self.bot_control_widget.recover_requested.connect(self.recover_requested)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._empty_panel(self.orders_state), "Open Orders")
        self.tabs.addTab(self._empty_panel(self.position_state), "Position / Basket")
        self.tabs.addTab(self.trade_history, "Trade History")
        self.tabs.currentChanged.connect(self._tab_changed)

        unavailable_layout = QVBoxLayout(self.unavailable_panel)
        unavailable_layout.addWidget(self.unavailable_message)
        unavailable_layout.addWidget(self.unavailable_retry_button)
        unavailable_layout.addStretch()

        self._build_layout()
        self.compact_mode = self.width() < BOT_CONTROL_BREAKPOINT
        self._drawer_open = False
        self.bot_control_button = QPushButton()
        self.bot_control_button.setObjectName("secondaryButton")
        self.bot_control_button.clicked.connect(self.open_bot_control)
        self._header_layout.addWidget(self.bot_control_button)
        self._set_bot_control_state("No Session")
        self._drawer_close_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._drawer_close_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._drawer_close_shortcut.activated.connect(self.close_bot_control)
        self._drawer_close_shortcut.setEnabled(False)
        self._apply_layout_mode()

    @Slot()
    def show_setup(self) -> None:
        self._activate_setup()

    @Slot(object)
    def show_workspace_snapshot(self, value: object) -> None:
        if not isinstance(value, TradingWorkspaceSnapshot):
            return
        self._show_header(value)
        self._show_placeholder_states(value)

    @Slot(str)
    def show_setup_for_validation(self, field: str) -> None:
        self._activate_setup()
        if self.compact_mode and not self._drawer_open:
            self.open_bot_control()
        validation_widgets = self.setup.reveal_validation_field(field)
        if validation_widgets is None:
            return
        control, error_label = validation_widgets
        self.setup.adjustSize()
        self._bot_pages.adjustSize()
        control.setFocus(Qt.FocusReason.OtherFocusReason)
        self.bot_control_scroll.ensureWidgetVisible(error_label)

    def _activate_setup(self) -> None:
        self._show_bot_page(self.setup)
        self._set_bot_control_state("No Session")

    def show_configured_session(self, session: ConfiguredPaperSession) -> None:
        self.show_bot_control_snapshot(
            configured_bot_control(
                session,
                observed_at_utc=datetime.now(UTC),
            )
        )

    @Slot(object)
    def show_bot_control_snapshot(self, value: object) -> None:
        if not isinstance(value, BotControlSnapshot):
            return
        self.bot_control_widget.show_snapshot(value)
        self.show_workspace_snapshot(value.workspace)
        self._show_bot_page(self.bot_control_widget)
        self._set_bot_control_state(_RUNTIME_STATE_TEXT[value.state])

    def show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self._show_bot_page(self.unavailable_panel)
        self._set_bot_control_state("Unavailable")

    def set_bot_busy(self, busy: bool) -> None:
        self.setup.set_loading(busy)
        self.unavailable_retry_button.setDisabled(busy)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        compact = event.size().width() < BOT_CONTROL_BREAKPOINT
        if compact != self.compact_mode:
            self.compact_mode = compact
            self._apply_layout_mode()
        if self.compact_mode and self._drawer_open:
            self._position_drawer()

    @Slot()
    def open_bot_control(self) -> None:
        if not self.compact_mode:
            return
        self._drawer_open = True
        self._drawer_close_shortcut.setEnabled(True)
        self._position_drawer()
        self.bot_control.show()
        self.bot_control.raise_()
        self.bot_control_close_button.setFocus(Qt.FocusReason.OtherFocusReason)

    @Slot()
    def close_bot_control(self) -> None:
        if not self.compact_mode or not self._drawer_open:
            return
        self._drawer_open = False
        self._drawer_close_shortcut.setEnabled(False)
        self.bot_control.hide()
        self.bot_control_button.setFocus()

    def _position_drawer(self) -> None:
        width = min(BOT_CONTROL_WIDTH, self.width())
        top = self.workspace_header.geometry().bottom() + 13
        self.bot_control.setGeometry(
            self.width() - width,
            top,
            width,
            self.height() - top,
        )

    def _apply_layout_mode(self) -> None:
        self._body_layout.removeWidget(self.bot_control)
        self._drawer_close_shortcut.setEnabled(False)
        if self.compact_mode:
            self._drawer_open = False
            self.bot_control.setMinimumWidth(0)
            self.bot_control.setMaximumWidth(BOT_CONTROL_WIDTH)
            self.bot_control.setParent(self)
            self.bot_control.hide()
            self.bot_control_close_button.show()
            self.bot_control_button.show()
            return

        self._drawer_open = False
        self.bot_control_button.hide()
        self.bot_control_close_button.hide()
        self.bot_control.setParent(self._body)
        self.bot_control.setFixedWidth(BOT_CONTROL_WIDTH)
        self._body_layout.addWidget(self.bot_control)
        self.bot_control.show()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.workspace_header = QFrame()
        self.workspace_header.setObjectName("workspaceHeader")
        self._header_layout = QHBoxLayout(self.workspace_header)
        self._header_layout.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("TIEWTRADE")
        brand.setObjectName("brand")
        self._header_layout.addWidget(brand)
        for label in (
            self.header_symbol,
            self.header_timeframe,
            self.header_mode,
            self.header_market_type,
            self.header_preset,
            self.header_runtime,
            self.header_freshness,
            self.header_read_state,
        ):
            self._header_layout.addWidget(label)
        self._header_layout.addStretch()
        root.addWidget(self.workspace_header)

        self._body = QWidget()
        self._body.setObjectName("workspaceContent")
        self._body_layout = QHBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(12)

        primary = QWidget()
        primary_layout = QVBoxLayout(primary)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(12)
        chart = QFrame()
        chart.setObjectName("chartPlaceholder")
        chart_layout = QVBoxLayout(chart)
        self.chart_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_state.setProperty("stateMessage", True)
        chart_layout.addWidget(self.chart_state)
        primary_layout.addWidget(chart, 3)
        primary_layout.addWidget(self.tabs, 2)

        self.bot_control = QFrame()
        self.bot_control.setObjectName("botControl")
        self.bot_control.setFixedWidth(BOT_CONTROL_WIDTH)
        bot_layout = QVBoxLayout(self.bot_control)
        bot_header = QHBoxLayout()
        bot_title = QLabel("Bot Control")
        bot_title.setObjectName("sectionTitle")
        bot_header.addWidget(bot_title)
        bot_header.addStretch()
        self.bot_control_close_button = QPushButton("Close")
        self.bot_control_close_button.setObjectName("secondaryButton")
        self.bot_control_close_button.setAccessibleName("Close Bot Control")
        self.bot_control_close_button.clicked.connect(self.close_bot_control)
        bot_header.addWidget(self.bot_control_close_button)
        bot_layout.addLayout(bot_header)
        self.bot_control_scroll = QScrollArea()
        self.bot_control_scroll.setObjectName("botControlScroll")
        self.bot_control_scroll.viewport().setObjectName("botControlViewport")
        self.bot_control_scroll.setWidgetResizable(True)
        self.bot_control_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.bot_control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._bot_pages.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Minimum,
        )
        self.bot_control_scroll.setWidget(self._bot_pages)
        bot_layout.addWidget(self.bot_control_scroll, 1)

        self._body_layout.addWidget(primary, 1)
        self._body_layout.addWidget(self.bot_control)
        root.addWidget(self._body, 1)

    @Slot(int)
    def _tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.trade_history:
            self.trade_history_activated.emit()

    def _set_bot_control_state(self, state: str) -> None:
        self.bot_control_button.setText(f"Bot Control · {state}")
        self.bot_control_button.setAccessibleName(f"Bot Control: {state}")

    def _show_bot_page(self, page: QWidget) -> None:
        self._bot_pages.setCurrentWidget(page)
        self.bot_control_scroll.horizontalScrollBar().setValue(0)
        self.bot_control_scroll.verticalScrollBar().setValue(0)

    def _show_header(self, snapshot: TradingWorkspaceSnapshot) -> None:
        header = snapshot.header
        if header is None:
            self.header_symbol.setText("No Session")
            self.header_timeframe.setText("—")
            self.header_mode.setText("—")
            self.header_market_type.setText("—")
            self.header_preset.setText("—")
            self.header_runtime.setText("No Session")
            self.header_freshness.setText("No Session")
        else:
            self.header_symbol.setText(header.symbol)
            self.header_timeframe.setText(header.timeframe)
            self.header_mode.setText(header.trade_mode.value.title())
            self.header_market_type.setText(header.market_type.value.title())
            self.header_preset.setText(preset_display_name(header.preset_version))
            self.header_runtime.setText(_RUNTIME_STATE_TEXT[header.runtime_state])
            self.header_freshness.setText(_DATA_FRESHNESS_TEXT[header.data_freshness])
        self.header_read_state.setText(_READ_STATE_TEXT[snapshot.read_state])

    def _show_placeholder_states(self, snapshot: TradingWorkspaceSnapshot) -> None:
        if (
            snapshot.read_state is WorkspaceReadState.LOADING
            and snapshot.header is None
        ):
            self.orders_state.setText("Loading workspace data")
            self.position_state.setText("Loading workspace data")
            return
        if snapshot.read_state is WorkspaceReadState.ERROR and snapshot.header is None:
            message = snapshot.message or "Workspace data is unavailable"
            self.orders_state.setText(message)
            self.position_state.setText(message)
            return
        self.orders_state.setText("No open orders")
        self.position_state.setText("No open Position or Basket")

    @staticmethod
    def _empty_panel(message: QLabel) -> QFrame:
        panel = QFrame()
        panel.setObjectName("emptyPanel")
        layout = QVBoxLayout(panel)
        layout.addStretch()
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setProperty("stateMessage", True)
        layout.addWidget(message)
        layout.addStretch()
        return panel
