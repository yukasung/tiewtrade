from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class MarketDataRuntimeState(StrEnum):
    STARTING = "starting"
    WARMING_UP = "warming_up"
    LIVE = "live"
    BACKFILLING = "backfilling"
    STALE = "stale"
    RECONNECTING = "reconnecting"
    RATE_LIMITED = "rate_limited"
    FAILED_CLOSED = "failed_closed"
    STOPPED = "stopped"


class MarketDataRuntimeReason(StrEnum):
    START_REQUESTED = "start_requested"
    WARM_UP_COMPLETED = "warm_up_completed"
    WARM_UP_TIMEOUT = "warm_up_timeout"
    LIVE_CANDLE_ACCEPTED = "live_candle_accepted"
    GAP_DETECTED = "gap_detected"
    BACKFILL_COMPLETED = "backfill_completed"
    DATA_STALE = "data_stale"
    SOURCE_DISCONNECTED = "source_disconnected"
    RECONNECT_EXHAUSTED = "reconnect_exhausted"
    RATE_LIMITED = "rate_limited"
    RATE_LIMIT_EXHAUSTED = "rate_limit_exhausted"
    SOURCE_FATAL = "source_fatal"
    SOURCE_ERROR = "source_error"
    SINK_ERROR = "sink_error"
    STOP_REQUESTED = "stop_requested"


@dataclass(frozen=True, slots=True)
class MarketDataRuntimeSnapshot:
    state: MarketDataRuntimeState
    reason: MarketDataRuntimeReason
    transitioned_at: datetime
    last_accepted_open_time: datetime | None

    def __post_init__(self) -> None:
        _require_utc(self.transitioned_at, name="transitioned_at")
        if self.last_accepted_open_time is not None:
            _require_utc(
                self.last_accepted_open_time,
                name="last_accepted_open_time",
            )


class MarketDataRuntimeStatus:
    def __init__(
        self,
        now: Callable[[], datetime],
        *,
        on_transition: Callable[[MarketDataRuntimeSnapshot], None] | None = None,
    ) -> None:
        self._now = now
        self._on_transition = on_transition
        self._snapshot = MarketDataRuntimeSnapshot(
            state=MarketDataRuntimeState.STARTING,
            reason=MarketDataRuntimeReason.START_REQUESTED,
            transitioned_at=self._now(),
            last_accepted_open_time=None,
        )
        self._publish_transition()

    @property
    def snapshot(self) -> MarketDataRuntimeSnapshot:
        return self._snapshot

    def transition(
        self,
        state: MarketDataRuntimeState,
        reason: MarketDataRuntimeReason,
    ) -> None:
        self._snapshot = MarketDataRuntimeSnapshot(
            state=state,
            reason=reason,
            transitioned_at=self._now(),
            last_accepted_open_time=self._snapshot.last_accepted_open_time,
        )
        self._publish_transition()

    def record_delivery(self, open_time: datetime) -> None:
        self._snapshot = MarketDataRuntimeSnapshot(
            state=self._snapshot.state,
            reason=self._snapshot.reason,
            transitioned_at=self._snapshot.transitioned_at,
            last_accepted_open_time=open_time,
        )

    def _publish_transition(self) -> None:
        if self._on_transition is not None:
            self._on_transition(self._snapshot)


def _require_utc(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must use UTC")
