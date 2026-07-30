import sys

from PySide6.QtWidgets import QApplication

from tiewtrade.ui.main_window import MainWindow
from tiewtrade.ui.session_workflow import CreateSession, LoadActiveSession
from tiewtrade.ui.theme import DARK_THEME
from tiewtrade.ui.trade_history_workflow import ListBaskets, ListFills


def run_desktop(
    *,
    create_session: CreateSession,
    load_active: LoadActiveSession,
    list_baskets: ListBaskets,
    list_fills: ListFills,
) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow(
        create_session=create_session,
        load_active=load_active,
        list_baskets=list_baskets,
        list_fills=list_fills,
    )
    window.setStyleSheet(DARK_THEME)
    window.show()
    return app.exec()
