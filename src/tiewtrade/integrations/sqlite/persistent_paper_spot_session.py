from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionSnapshot,
)
from tiewtrade.application.session_persistence import SessionPersistenceCoordinator
from tiewtrade.integrations.sqlite.paper_spot_history import PaperSpotSQLiteHistory
from tiewtrade.integrations.sqlite.session_persistence import (
    SQLiteSessionPersistenceCoordinator,
)


class _PaperSpotSnapshotRecorder:
    def __init__(self, history: PaperSpotSQLiteHistory) -> None:
        self._history = history

    def record(self, snapshot: PaperSpotSessionSnapshot) -> None:
        if snapshot.entry_fill is not None:
            if snapshot.basket_id is None:
                raise ValueError("entry Fill requires a Basket ID")
            self._history.record_entry(
                basket_id=snapshot.basket_id,
                entry_number=snapshot.basket_entry_count,
                fill=snapshot.entry_fill,
            )
        if snapshot.take_profit_fill is None and snapshot.closed_basket is None:
            return
        if snapshot.take_profit_fill is None or snapshot.closed_basket is None:
            raise ValueError(
                "Take Profit Fill and closed Basket must be present together"
            )
        if snapshot.basket_id != snapshot.closed_basket.basket_id:
            raise ValueError("closed Basket requires a matching Basket ID")
        self._history.record_close(
            basket_id=snapshot.closed_basket.basket_id,
            fill=snapshot.take_profit_fill,
            closed=snapshot.closed_basket,
        )


def create_persistent_paper_spot_session(
    session: PaperSpotSession,
    history: PaperSpotSQLiteHistory,
) -> SessionPersistenceCoordinator[PaperSpotSessionSnapshot]:
    if session.identity != history.session_identity:
        raise ValueError("Paper Spot Session and Trade History identity differ")
    recorder = _PaperSpotSnapshotRecorder(history)
    return SQLiteSessionPersistenceCoordinator(session, recorder.record)
