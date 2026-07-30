from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from tiewtrade.application.session_persistence import (
    PersistenceState,
    PersistentSessionSnapshot,
    SessionPersistenceBlockedError,
)
from tiewtrade.market_data.candle import Candle


class _CompletedCandleProcessor[ProcessorSnapshotT](Protocol):
    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> ProcessorSnapshotT:
        pass


class SQLiteSessionPersistenceCoordinator[CoordinatorSnapshotT]:
    def __init__(
        self,
        session: _CompletedCandleProcessor[CoordinatorSnapshotT],
        record_snapshot: Callable[[CoordinatorSnapshotT], None],
    ) -> None:
        self._session = session
        self._record_snapshot = record_snapshot
        self._state = PersistenceState.READY

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentSessionSnapshot[CoordinatorSnapshotT]:
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

        return PersistentSessionSnapshot(
            session=snapshot,
            persistence_state=self._state,
        )
