from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QWidget


def click(
    widget: QWidget,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
) -> None:
    QTest.mouseClick(widget, button)


def table_item(table: QTableWidget, row: int, column: int) -> QTableWidgetItem:
    item = table.item(row, column)
    assert item is not None
    return item


def qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)
