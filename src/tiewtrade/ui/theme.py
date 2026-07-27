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
QLineEdit, QComboBox, QSpinBox {
    background: #FFFFFF;
    border: 1px solid #B8C4D8;
    border-radius: 7px;
    color: #172033;
    min-height: 36px;
    padding: 0 10px;
    selection-background-color: #DCE6FF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #3D63F2;
}
QLineEdit:read-only, QComboBox:disabled {
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
