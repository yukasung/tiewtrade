import sys

from PySide6.QtWidgets import QApplication

from tiewtrade.ui.main_window import CreateSession, MainWindow
from tiewtrade.ui.theme import LIGHT_THEME


def run_desktop(*, create_session: CreateSession) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow(create_session=create_session)
    window.setStyleSheet(LIGHT_THEME)
    window.show()
    return app.exec()
