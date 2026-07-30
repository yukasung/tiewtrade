from datetime import UTC, datetime

from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeSnapshot,
    MarketDataRuntimeState,
    MarketDataRuntimeStatus,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
TRANSITION = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
DELIVERY = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)


def test_runtime_state_exposes_rate_limit_diagnostics() -> None:
    assert MarketDataRuntimeState.RATE_LIMITED == "rate_limited"
    assert MarketDataRuntimeReason.RATE_LIMITED == "rate_limited"
    assert MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED == "rate_limit_exhausted"
    assert MarketDataRuntimeReason.SOURCE_FATAL == "source_fatal"


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def test_status_publishes_transitions_without_retaining_history() -> None:
    observed: list[MarketDataRuntimeSnapshot] = []
    status = MarketDataRuntimeStatus(
        SequenceClock(START, TRANSITION),
        on_transition=observed.append,
    )
    status.transition(
        MarketDataRuntimeState.WARMING_UP,
        MarketDataRuntimeReason.START_REQUESTED,
    )

    assert [snapshot.state for snapshot in observed] == [
        MarketDataRuntimeState.STARTING,
        MarketDataRuntimeState.WARMING_UP,
    ]
    assert status.snapshot.transitioned_at == TRANSITION
    assert not hasattr(status, "visited_states")


def test_delivery_preserves_transition_metadata() -> None:
    observed: list[MarketDataRuntimeSnapshot] = []
    status = MarketDataRuntimeStatus(
        SequenceClock(START, TRANSITION),
        on_transition=observed.append,
    )
    status.transition(
        MarketDataRuntimeState.LIVE,
        MarketDataRuntimeReason.WARM_UP_COMPLETED,
    )
    status.record_delivery(DELIVERY)

    assert status.snapshot.state is MarketDataRuntimeState.LIVE
    assert status.snapshot.reason is MarketDataRuntimeReason.WARM_UP_COMPLETED
    assert status.snapshot.transitioned_at == TRANSITION
    assert status.snapshot.last_accepted_open_time == DELIVERY
    assert len(observed) == 2
