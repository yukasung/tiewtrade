from dataclasses import dataclass
from datetime import datetime

from tiewtrade.application.paper_futures_session import (
    PaperFuturesSession,
    PaperFuturesSessionSnapshot,
)
from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceBlockedError,
)
from tiewtrade.integrations.sqlite.paper_futures_history import (
    PaperFuturesSQLiteHistory,
)
from tiewtrade.market_data.candle import Candle


@dataclass(frozen=True, slots=True)
class PersistentPaperFuturesSnapshot:
    session: PaperFuturesSessionSnapshot
    persistence_state: PersistenceState


class PersistentPaperFuturesSQLiteSession:
    def __init__(
        self,
        session: PaperFuturesSession,
        history: PaperFuturesSQLiteHistory,
    ) -> None:
        if session.identity != history.session_identity:
            raise ValueError("Paper Futures Session and Trade History identity differ")
        self._session = session
        self._history = history
        self._state = PersistenceState.READY

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentPaperFuturesSnapshot:
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

        return PersistentPaperFuturesSnapshot(
            session=snapshot,
            persistence_state=self._state,
        )

    def _record_snapshot(self, snapshot: PaperFuturesSessionSnapshot) -> None:
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
