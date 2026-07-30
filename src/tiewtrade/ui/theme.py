DARK_THEME = """
QMainWindow, QWidget#workspace, QWidget#workspaceContent {
    background: #0B0E11;
    color: #F1F5F9;
    font-family: "Inter", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 14px;
}
QFrame#workspaceHeader, QFrame#botControl, QFrame#card,
QFrame#statusCard, QFrame#filterCard, QFrame#emptyPanel {
    background: #141A22;
    border: 1px solid #2B3441;
    border-radius: 8px;
}
QFrame#chartPlaceholder {
    background: #10151C;
    border: 1px solid #2B3441;
    border-radius: 8px;
}
QLabel {
    color: #F1F5F9;
}
QLabel#brand, QLabel#pageTitle, QLabel#sectionTitle,
QLabel#detailValue, QLabel#readOnlyValue, QLabel#stateValue {
    color: #F1F5F9;
}
QLabel#brand {
    color: #4C7DFF;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#pageTitle {
    font-size: 24px;
    font-weight: 700;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 650;
}
QLabel#supportingText, QLabel#detailLabel, QLabel#filterLabel,
QLabel#summaryLabel, QLabel#pageLabel, QLabel[stateMessage="true"] {
    color: #94A3B8;
}
QLabel#eyebrow {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 700;
}
QLabel#summaryValue {
    color: #F1F5F9;
    font-weight: 700;
}
QLabel#environmentBadge, QWidget[state="warning"] {
    background: #2A2412;
    color: #F0B90B;
    border-radius: 6px;
}
QWidget[state="positive"] { color: #0ECB81; }
QWidget[state="negative"] { color: #F6465D; }
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background: #1B2430;
    border: 1px solid #3A4656;
    border-radius: 6px;
    color: #F1F5F9;
    min-height: 36px;
    padding: 0 10px;
    selection-background-color: #315CF4;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
QPushButton:focus, QTabBar::tab:focus {
    border: 2px solid #4C7DFF;
}
QLineEdit:read-only, QComboBox:disabled, QDateEdit:disabled {
    background: #151C25;
    color: #94A3B8;
}
QComboBox QAbstractItemView {
    alternate-background-color: #141A22;
    background: #1B2430;
    border: 1px solid #3A4656;
    color: #F1F5F9;
    outline: 0;
    selection-background-color: #315CF4;
    selection-color: #F8FAFC;
}
QCalendarWidget {
    background: #141A22;
    color: #F1F5F9;
}
QCalendarWidget QWidget {
    background: #141A22;
    color: #F1F5F9;
}
QCalendarWidget QAbstractItemView {
    alternate-background-color: #141A22;
    background: #141A22;
    color: #F1F5F9;
    selection-background-color: #315CF4;
    selection-color: #F8FAFC;
}
QCalendarWidget QToolButton, QCalendarWidget QMenu {
    background: #1B2430;
    color: #F1F5F9;
}
QPushButton#primaryButton {
    background: #315CF4;
    border: 0;
    border-radius: 6px;
    color: #F8FAFC;
    font-weight: 650;
    min-height: 38px;
    padding: 0 18px;
}
QPushButton#primaryButton:hover { background: #416DFF; }
QPushButton#primaryButton:disabled {
    background: #26334D;
    color: #6F7D93;
}
QPushButton#secondaryButton, QPushButton[retryButton="true"] {
    background: #1B2430;
    border: 1px solid #3A4656;
    border-radius: 6px;
    color: #F1F5F9;
    min-height: 36px;
    padding: 0 14px;
}
QPushButton#secondaryButton:hover, QPushButton[retryButton="true"]:hover {
    background: #243044;
    border-color: #4C7DFF;
}
QPushButton#destructiveButton {
    background: #F6465D;
    border: 0;
    border-radius: 6px;
    color: #FFFFFF;
    min-height: 38px;
    padding: 0 18px;
}
QPushButton#advancedButton {
    background: transparent;
    border: 0;
    color: #6E97FF;
    font-weight: 600;
    text-align: left;
}
QTabWidget::pane {
    background: #141A22;
    border: 1px solid #2B3441;
}
QTabBar::tab {
    background: #0B0E11;
    color: #94A3B8;
    min-height: 36px;
    padding: 0 16px;
}
QTabBar::tab:selected {
    color: #F1F5F9;
    border-bottom: 2px solid #4C7DFF;
}
QScrollArea#botControlScroll {
    background: transparent;
    border: 0;
}
QTableWidget {
    alternate-background-color: #111821;
    background: #141A22;
    border: 0;
    color: #F1F5F9;
    gridline-color: #2B3441;
    selection-background-color: #22355F;
    selection-color: #F8FAFC;
}
QTableWidget::item { padding: 7px 8px; }
QHeaderView::section {
    background: #1B2430;
    border: 0;
    border-bottom: 1px solid #2B3441;
    color: #CBD5E1;
    font-weight: 650;
    padding: 8px;
}
QCheckBox { color: #CBD5E1; spacing: 7px; }
QCheckBox::indicator:checked {
    background: #315CF4;
    border: 1px solid #4C7DFF;
}
QLabel#fieldError, QLabel#filterError { color: #F6465D; }
QLabel#unavailableMessage {
    background: #2A1B20;
    border: 1px solid #71313D;
    border-radius: 6px;
    color: #FF9CAA;
    padding: 10px 12px;
}
"""
