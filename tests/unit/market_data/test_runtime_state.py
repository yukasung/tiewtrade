from datetime import UTC, datetime

from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeState,
    MarketDataRuntimeStatus,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
TRANSITION = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
DELIVERY = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def test_status_owns_transitions_and_history() -> None:
    status = MarketDataRuntimeStatus(SequenceClock(START, TRANSITION))
    status.transition(
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeReason.START_REQUESTED,
    )

    assert status.snapshot.transitioned_at == TRANSITION
    assert status.visited_states == (
        MarketDataRuntimeState.STARTING,
        MarketDataRuntimeState.WARMING_UP,
    )


def test_delivery_preserves_transition_metadata() -> None:
    status = MarketDataRuntimeStatus(SequenceClock(START, TRANSITION))
    status.transition(
        MarketDataRuntimeState.LIVE,
        MarketDataRuntimeReason.WARM_UP_COMPLETED,
    )
    status.record_delivery(DELIVERY)

    assert status.snapshot.state is MarketDataRuntimeState.LIVE
    assert status.snapshot.reason is MarketDataRuntimeReason.WARM_UP_COMPLETED
    assert status.snapshot.transitioned_at == TRANSITION
    assert status.snapshot.last_accepted_open_time == DELIVERY
