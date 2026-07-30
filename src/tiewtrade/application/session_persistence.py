from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from tiewtrade.market_data.candle import Candle


class PersistenceState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class SessionPersistenceBlockedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PersistentSessionSnapshot[SessionSnapshotT]:
    session: SessionSnapshotT
    persistence_state: PersistenceState


class SessionPersistenceCoordinator[SessionSnapshotT](Protocol):
    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentSessionSnapshot[SessionSnapshotT]:
        pass
