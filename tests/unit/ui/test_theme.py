from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractItemView, QLabel, QWidget
from pytestqt.qtbot import QtBot

from tiewtrade.ui.theme import DARK_THEME
from tiewtrade.ui.trade_history_page import TradeHistoryPage
from tiewtrade.ui.trading_workspace import TradingWorkspace


def test_dark_theme_uses_approved_workspace_palette() -> None:
    for color in (
        "#0B0E11",
        "#141A22",
        "#1B2430",
        "#2B3441",
        "#F1F5F9",
        "#94A3B8",
        "#0ECB81",
        "#F6465D",
        "#F0B90B",
    ):
        assert color in DARK_THEME

    assert "background: #F4F7FB;" not in DARK_THEME
    assert "background: #FFFFFF;" not in DARK_THEME


def test_dark_theme_defines_focus_and_semantic_states() -> None:
    assert 'QWidget[state="positive"]' in DARK_THEME
    assert 'QWidget[state="negative"]' in DARK_THEME
    assert 'QWidget[state="warning"]' in DARK_THEME
    assert "QPushButton:focus" in DARK_THEME
    assert "QTableWidget:focus" in DARK_THEME
    assert "border: 2px solid #4C7DFF" in DARK_THEME


def test_dark_theme_styles_scoped_trading_tab_states() -> None:
    for selector in (
        "QLabel#openOrdersState",
        "QLabel#positionBasketState",
        "QLabel#basketState",
        "QLabel#fillState",
    ):
        assert selector in DARK_THEME


def test_dark_theme_covers_current_semantic_object_names_without_dead_navigation() -> (
    None
):
    for selector in (
        "QLabel#eyebrow",
        "QLabel#summaryValue",
        'QPushButton[retryButton="true"]',
    ):
        assert selector in DARK_THEME

    for dead_selector in (
        "QWidget#content",
        "QFrame#navigation",
        "QPushButton#navigationButton",
        "QPushButton#navigationButtonSelected",
        "QPushButton#unavailableRetryButton",
        "QLabel#environmentBadge",
    ):
        assert dead_selector not in DARK_THEME


def test_workspace_and_session_setup_labels_render_readably_on_dark_surfaces(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setStyleSheet(DARK_THEME)
    workspace.resize(1200, 700)
    workspace.show()

    form_label = next(
        label
        for label in workspace.setup.findChildren(QLabel)
        if label.text() == "Trade Mode"
    )

    assert _palette_color(
        workspace.header_symbol, QPalette.ColorRole.WindowText
    ) == QColor("#F1F5F9")
    assert _palette_color(form_label, QPalette.ColorRole.WindowText) == QColor(
        "#F1F5F9"
    )

    workspace.show_unavailable("Session storage is unavailable")

    assert _palette_color(
        workspace.unavailable_message, QPalette.ColorRole.WindowText
    ) == QColor("#FF9CAA")


def test_semantic_status_label_colors_override_generic_dark_label_color(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setStyleSheet(DARK_THEME)

    expected_colors = {
        "positive": QColor("#0ECB81"),
        "negative": QColor("#F6465D"),
        "warning": QColor("#F0B90B"),
    }
    for state, expected in expected_colors.items():
        label = QLabel(state, workspace)
        label.setProperty("state", state)
        label.ensurePolished()

        assert _palette_color(label, QPalette.ColorRole.WindowText) == expected


def test_combo_box_popup_view_renders_with_dark_readable_palette(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setStyleSheet(DARK_THEME)
    workspace.show()

    combo = workspace.setup.market_type
    combo.showPopup()
    view = combo.view()
    view.ensurePolished()

    assert _palette_color(view, QPalette.ColorRole.Base) == QColor("#1B2430")
    assert _palette_color(view, QPalette.ColorRole.Text) == QColor("#F1F5F9")

    combo.hidePopup()


def test_calendar_popup_renders_with_dark_readable_palette(qtbot: QtBot) -> None:
    page = TradeHistoryPage()
    qtbot.addWidget(page)
    page.setStyleSheet(DARK_THEME)
    page.show()
    calendar = page.from_date.calendarWidget()
    calendar.show()
    calendar_view = calendar.findChild(QAbstractItemView)

    assert calendar_view is not None
    assert _palette_color(calendar, QPalette.ColorRole.Window) == QColor("#141A22")
    assert _palette_color(calendar, QPalette.ColorRole.WindowText) == QColor("#F1F5F9")
    assert _palette_color(calendar_view, QPalette.ColorRole.Base) == QColor("#141A22")
    assert _palette_color(calendar_view, QPalette.ColorRole.Text) == QColor("#F1F5F9")


def test_bot_control_scroll_surfaces_and_scrollbar_render_dark(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setStyleSheet(DARK_THEME)
    workspace.setFixedSize(1024, 700)
    workspace.show()
    workspace.bot_control_button.click()
    scroll_bar = workspace.bot_control_scroll.verticalScrollBar()

    assert _palette_color(workspace._bot_pages, QPalette.ColorRole.Window) == QColor(
        "#141A22"
    )
    assert _palette_color(
        workspace.bot_control_scroll.viewport(), QPalette.ColorRole.Window
    ) == QColor("#141A22")
    assert _palette_color(scroll_bar, QPalette.ColorRole.Window) == QColor("#0B0E11")
    assert _palette_color(scroll_bar, QPalette.ColorRole.Base) == QColor("#0B0E11")
    assert (
        max(QColor(color).lightness() for color in _rendered_colors(scroll_bar)) < 128
    )


def test_compact_drawer_focus_renders_on_actionable_close_button(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setStyleSheet(DARK_THEME)
    workspace.resize(1024, 700)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)

    workspace.bot_control_button.click()

    assert workspace.bot_control_close_button.hasFocus()
    assert "#4c7dff" in _rendered_colors(workspace.bot_control_close_button)


def _palette_color(widget: QWidget, role: QPalette.ColorRole) -> QColor:
    return widget.palette().color(role)


def _rendered_colors(widget: QWidget) -> set[str]:
    image = widget.grab().toImage()
    return {
        image.pixelColor(x, y).name()
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 0
    }
