from dataclasses import dataclass
from datetime import datetime

from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionSnapshot,
)
from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceBlockedError,
)
from tiewtrade.integrations.sqlite.paper_spot_history import PaperSpotSQLiteHistory
from tiewtrade.market_data.candle import Candle


@dataclass(frozen=True, slots=True)
class PersistentPaperSpotSnapshot:
    session: PaperSpotSessionSnapshot
    persistence_state: PersistenceState


class PersistentPaperSpotSQLiteSession:
    def __init__(
        self,
        session: PaperSpotSession,
        history: PaperSpotSQLiteHistory,
    ) -> None:
        if session.identity != history.session_identity:
            raise ValueError("Paper Spot Session and Trade History identity differ")
        self._session = session
        self._history = history
        self._state = PersistenceState.READY

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentPaperSpotSnapshot:
        if self._state is PersistenceState.BLOCKED:
            raise SessionPersistenceBlockedError(
                "Session is blocked because Trade History persistence failed"
            )

        snapshot = self._session.process_completed_candle(
            candle,
            received_at=received_at,
        )
        try:
            self._record_snapshot(snapshot)
        except Exception:
            self._state = PersistenceState.BLOCKED
            raise

        return PersistentPaperSpotSnapshot(
            session=snapshot,
            persistence_state=self._state,
        )

    def _record_snapshot(self, snapshot: PaperSpotSessionSnapshot) -> None:
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
