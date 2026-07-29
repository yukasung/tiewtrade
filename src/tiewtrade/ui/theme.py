LIGHT_THEME = """
QMainWindow, QWidget#content {
    background: #F4F7FB;
    color: #172033;
    font-family: "Inter", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 14px;
}
QFrame#navigation {
    background: #FFFFFF;
    border-right: 1px solid #E3E9F2;
}
QLabel#brand {
    color: #2457E6;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
}
QPushButton#navigationButtonSelected {
    background: #EAF0FF;
    border: 0;
    border-radius: 8px;
    color: #1F4ED8;
    font-weight: 600;
    padding: 11px 14px;
    text-align: left;
}
QPushButton#navigationButtonSelected:disabled {
    color: #1F4ED8;
}
QLabel#environmentBadge {
    background: #EEF8F2;
    border-radius: 8px;
    color: #16794A;
    font-size: 12px;
    font-weight: 600;
    padding: 10px 12px;
}
QLabel#pageTitle {
    color: #172033;
    font-size: 25px;
    font-weight: 700;
}
QLabel#supportingText, QLabel#detailLabel {
    color: #62708A;
}
QLabel#sectionTitle {
    color: #172033;
    font-size: 16px;
    font-weight: 650;
}
QFrame#card, QFrame#statusCard {
    background: #FFFFFF;
    border: 1px solid #E3E9F2;
    border-radius: 12px;
}
QFrame#statusCard {
    background: #EEF4FF;
    border-color: #D8E4FF;
}
QLabel#eyebrow {
    color: #4A65A0;
    font-size: 11px;
    font-weight: 700;
}
QLabel#stateValue {
    color: #173F9B;
    font-size: 17px;
    font-weight: 650;
}
QLabel#detailValue, QLabel#readOnlyValue {
    color: #172033;
    font-weight: 600;
}
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background: #FFFFFF;
    border: 1px solid #B8C4D8;
    border-radius: 7px;
    color: #172033;
    min-height: 36px;
    padding: 0 10px;
    selection-background-color: #DCE6FF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 2px solid #3D63F2;
}
QLineEdit:read-only, QComboBox:disabled, QDateEdit:disabled {
    background: #F1F4F8;
    color: #4C5B73;
}
QPushButton#primaryButton {
    background: #315CF4;
    border: 0;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 650;
    min-height: 38px;
    padding: 0 20px;
}
QPushButton#primaryButton:hover {
    background: #244CDD;
}
QPushButton#primaryButton:focus, QPushButton#secondaryButton:focus,
QPushButton[retryButton="true"]:focus {
    border: 2px solid #173F9B;
}
QPushButton#advancedButton {
    background: transparent;
    border: 0;
    color: #315CF4;
    font-weight: 600;
    padding: 4px 0;
    text-align: left;
}
QPushButton#advancedButton:hover {
    color: #244CDD;
}
QPushButton#primaryButton:disabled {
    background: #A9B8E9;
}
QPushButton#secondaryButton, QPushButton[retryButton="true"] {
    background: #FFFFFF;
    border: 1px solid #9EACC2;
    border-radius: 8px;
    color: #25334D;
    font-weight: 600;
    min-height: 36px;
    padding: 0 14px;
}
QPushButton#secondaryButton:hover, QPushButton[retryButton="true"]:hover {
    background: #EEF4FF;
    border-color: #6F86B5;
}
QPushButton#secondaryButton:disabled {
    background: #F1F4F8;
    border-color: #D5DCE8;
    color: #78869D;
}
QFrame#filterCard {
    background: #FFFFFF;
    border: 1px solid #D8E1EF;
    border-radius: 10px;
}
QLabel#filterLabel, QLabel#summaryLabel {
    color: #4C5B73;
    font-size: 12px;
    font-weight: 600;
}
QLabel#summaryValue {
    color: #173F9B;
    font-weight: 700;
}
QLabel#pageLabel {
    color: #4C5B73;
    min-width: 92px;
}
QLabel[stateMessage="true"] {
    color: #4C5B73;
    padding: 6px 2px;
}
QLabel#basketState, QLabel#fillState {
    min-height: 20px;
}
QLabel#filterError {
    color: #B42318;
    font-size: 12px;
}
QCheckBox {
    color: #25334D;
    spacing: 7px;
}
QCheckBox::indicator {
    height: 16px;
    width: 16px;
}
QCheckBox::indicator:checked {
    background: #315CF4;
    border: 1px solid #244CDD;
}
QTableWidget {
    alternate-background-color: #F7F9FC;
    background: #FFFFFF;
    border: 1px solid #D8E1EF;
    border-radius: 8px;
    color: #172033;
    gridline-color: #E5EAF2;
    selection-background-color: #DCE6FF;
    selection-color: #172033;
}
QTableWidget::item {
    padding: 7px 8px;
}
QTableWidget::item:selected {
    background: #DCE6FF;
    color: #172033;
}
QHeaderView::section {
    background: #EEF2F7;
    border: 0;
    border-bottom: 1px solid #CBD5E3;
    border-right: 1px solid #DCE3ED;
    color: #344158;
    font-weight: 650;
    padding: 8px;
}
QLabel#fieldError {
    color: #B42318;
    font-size: 12px;
}
QLabel#unavailableMessage {
    background: #FFF4E5;
    border: 1px solid #FFD8A8;
    border-radius: 8px;
    color: #8A4B08;
    padding: 10px 12px;
}
"""
