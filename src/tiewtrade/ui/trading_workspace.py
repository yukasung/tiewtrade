from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.ui.preset_display import preset_display_name
from tiewtrade.ui.session_overview import SessionOverviewWidget
from tiewtrade.ui.session_setup import SessionSetupWidget
from tiewtrade.ui.trade_history_page import TradeHistoryPage


class TradingWorkspace(QWidget):
    trade_history_activated = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workspace")

        self.setup = SessionSetupWidget()
        self.overview = SessionOverviewWidget()
        self.trade_history = TradeHistoryPage()

        self.unavailable_panel = QFrame()
        self.unavailable_message = QLabel()
        self.unavailable_message.setObjectName("unavailableMessage")
        self.unavailable_message.setWordWrap(True)
        self.unavailable_retry_button = QPushButton("Try Again")
        self.unavailable_retry_button.setProperty("retryButton", True)

        self.header_symbol = QLabel("No Session")
        self.header_timeframe = QLabel("—")
        self.header_mode = QLabel("Paper")
        self.header_preset = QLabel("RSI Step Grid v1")
        self.header_runtime = QLabel("No Session")
        self.header_freshness = QLabel("Market data not started")

        self.chart_state = QLabel("Chart is not available yet")
        self.orders_state = QLabel("No open orders")
        self.position_state = QLabel("No open Position or Basket")

        self._bot_pages = QStackedWidget()
        self._bot_pages.addWidget(self.setup)
        self._bot_pages.addWidget(self.overview)
        self._bot_pages.addWidget(self.unavailable_panel)

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

    @Slot()
    def show_setup(self) -> None:
        self._bot_pages.setCurrentWidget(self.setup)
        self.header_runtime.setText("No Session")

    def show_configured_session(self, session: ConfiguredPaperSession) -> None:
        self.overview.show_session(session)
        self._bot_pages.setCurrentWidget(self.overview)
        self.header_symbol.setText(session.market_data.symbol)
        self.header_timeframe.setText(session.market_data.timeframe)
        market = session.config.market_type.value.title()
        self.header_mode.setText(f"Paper · {market}")
        self.header_preset.setText(preset_display_name(session.config.preset_version))
        self.header_runtime.setText("Configured")
        self.header_freshness.setText("Market data not started")

    def show_unavailable(self, message: str) -> None:
        self.unavailable_message.setText(message)
        self._bot_pages.setCurrentWidget(self.unavailable_panel)
        self.header_runtime.setText("Unavailable")

    def set_bot_busy(self, busy: bool) -> None:
        self.setup.set_loading(busy)
        self.unavailable_retry_button.setDisabled(busy)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.workspace_header = QFrame()
        self.workspace_header.setObjectName("workspaceHeader")
        header_layout = QHBoxLayout(self.workspace_header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("TIEWTRADE")
        brand.setObjectName("brand")
        header_layout.addWidget(brand)
        for label in (
            self.header_symbol,
            self.header_timeframe,
            self.header_mode,
            self.header_preset,
            self.header_runtime,
            self.header_freshness,
        ):
            header_layout.addWidget(label)
        header_layout.addStretch()
        root.addWidget(self.workspace_header)

        body = QWidget()
        body.setObjectName("workspaceContent")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

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
        self.bot_control.setFixedWidth(360)
        bot_layout = QVBoxLayout(self.bot_control)
        bot_title = QLabel("Bot Control")
        bot_title.setObjectName("sectionTitle")
        bot_layout.addWidget(bot_title)
        bot_layout.addWidget(self._bot_pages, 1)

        body_layout.addWidget(primary, 1)
        body_layout.addWidget(self.bot_control)
        root.addWidget(body, 1)

    @Slot(int)
    def _tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.trade_history:
            self.trade_history_activated.emit()

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
