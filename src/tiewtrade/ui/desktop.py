import sys
from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from tiewtrade.ui.bot_lifecycle_workflow import LifecycleAction, RuntimeSnapshotRelay
from tiewtrade.ui.chart_workflow import LoadChart
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
    start_bot: LifecycleAction | None = None,
    stop_bot: LifecycleAction | None = None,
    recover_bot: LifecycleAction | None = None,
    initialize_bot: LifecycleAction | None = None,
    runtime_snapshots: RuntimeSnapshotRelay | None = None,
    shutdown_runtime: Callable[[], None] | None = None,
    load_chart: LoadChart | None = None,
) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow(
        create_session=create_session,
        load_active=load_active,
        list_baskets=list_baskets,
        list_fills=list_fills,
        start_bot=start_bot,
        stop_bot=stop_bot,
        recover_bot=recover_bot,
        initialize_bot=initialize_bot,
        runtime_snapshots=runtime_snapshots,
        shutdown_runtime=shutdown_runtime,
        load_chart=load_chart,
    )
    window.setStyleSheet(DARK_THEME)
    window.show()
    return app.exec()
