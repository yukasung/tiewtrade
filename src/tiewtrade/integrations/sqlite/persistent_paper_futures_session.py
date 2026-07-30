from tiewtrade.application.paper_futures_session import (
    PaperFuturesSession,
    PaperFuturesSessionSnapshot,
)
from tiewtrade.application.session_persistence import SessionPersistenceCoordinator
from tiewtrade.integrations.sqlite.paper_futures_history import (
    PaperFuturesSQLiteHistory,
)
from tiewtrade.integrations.sqlite.session_persistence import (
    SQLiteSessionPersistenceCoordinator,
)


class _PaperFuturesSnapshotRecorder:
    def __init__(self, history: PaperFuturesSQLiteHistory) -> None:
        self._history = history

    def record(self, snapshot: PaperFuturesSessionSnapshot) -> None:
        if snapshot.entry_fill is not None:
            if snapshot.basket_id is None:
                raise ValueError("entry Fill requires a Basket ID")
            entry_number = snapshot.basket_entry_count
            if snapshot.closed_basket is not None:
                entry_number = snapshot.closed_basket.entry_count
            self._history.record_entry(
                basket_id=snapshot.basket_id,
                entry_number=entry_number,
                fill=snapshot.entry_fill,
            )

        if snapshot.exit_fill is None and snapshot.closed_basket is None:
            return
        if snapshot.exit_fill is None or snapshot.closed_basket is None:
            raise ValueError("exit Fill and closed Basket must be present together")
        if snapshot.basket_id != snapshot.closed_basket.basket_id:
            raise ValueError("closed Basket requires a matching Basket ID")
        self._history.record_close(
            basket_id=snapshot.closed_basket.basket_id,
            fill=snapshot.exit_fill,
            closed=snapshot.closed_basket,
        )


def create_persistent_paper_futures_session(
    session: PaperFuturesSession,
    history: PaperFuturesSQLiteHistory,
) -> SessionPersistenceCoordinator[PaperFuturesSessionSnapshot]:
    if session.identity != history.session_identity:
        raise ValueError("Paper Futures Session and Trade History identity differ")
    recorder = _PaperFuturesSnapshotRecorder(history)
    return SQLiteSessionPersistenceCoordinator(session, recorder.record)
