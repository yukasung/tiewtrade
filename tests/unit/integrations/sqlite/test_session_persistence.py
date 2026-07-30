from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceBlockedError,
)
from tiewtrade.integrations.sqlite.session_persistence import (
    SQLiteSessionPersistenceCoordinator,
)
from tiewtrade.market_data.candle import Candle


@dataclass(frozen=True, slots=True)
class FakeSnapshot:
    sequence: int


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> FakeSnapshot:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return FakeSnapshot(self.calls)


def candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
    )


def test_snapshot_is_recorded_before_ready_result_returns() -> None:
    session = FakeSession()
    recorded: list[FakeSnapshot] = []
    coordinator = SQLiteSessionPersistenceCoordinator(session, recorded.append)
    completed = candle()

    result = coordinator.process_completed_candle(
        completed,
        received_at=completed.close_time,
    )

    assert recorded == [result.session]
    assert result == result.__class__(
        session=FakeSnapshot(1),
        persistence_state=PersistenceState.READY,
    )


def test_recorder_failure_blocks_every_later_candle() -> None:
    session = FakeSession()

    def fail_recording(snapshot: FakeSnapshot) -> None:
        raise OSError("forced persistence failure")

    coordinator = SQLiteSessionPersistenceCoordinator(session, fail_recording)
    completed = candle()

    with pytest.raises(OSError, match="forced persistence failure"):
        coordinator.process_completed_candle(
            completed,
            received_at=completed.close_time,
        )
    with pytest.raises(
        SessionPersistenceBlockedError,
        match="Session is blocked because Trade History persistence failed",
    ):
        coordinator.process_completed_candle(
            completed,
            received_at=completed.close_time,
        )

    assert session.calls == 1


def test_session_failure_does_not_become_persistence_failure() -> None:
    session = FakeSession()
    session.error = RuntimeError("session failed")
    recorded: list[FakeSnapshot] = []
    coordinator = SQLiteSessionPersistenceCoordinator(session, recorded.append)
    completed = candle()

    with pytest.raises(RuntimeError, match="session failed"):
        coordinator.process_completed_candle(
            completed,
            received_at=completed.close_time,
        )

    session.error = None
    result = coordinator.process_completed_candle(
        completed,
        received_at=completed.close_time,
    )
    assert result.persistence_state is PersistenceState.READY
    assert session.calls == 2
    assert recorded == [FakeSnapshot(2)]
