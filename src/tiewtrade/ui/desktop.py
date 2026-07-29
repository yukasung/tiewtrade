import sys

from PySide6.QtWidgets import QApplication

from tiewtrade.ui.main_window import MainWindow
from tiewtrade.ui.session_workflow import CreateSession, LoadActiveSession
from tiewtrade.ui.theme import LIGHT_THEME


def run_desktop(
    *,
    create_session: CreateSession,
    load_active: LoadActiveSession,
) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow(create_session=create_session, load_active=load_active)
    window.setStyleSheet(LIGHT_THEME)
    window.show()
    return app.exec()
