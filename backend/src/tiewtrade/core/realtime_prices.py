"""Pure latest-price ordering and readiness (F-10 plan sections 1 and 3)."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Final

from tiewtrade.core.moments import require_aware
from tiewtrade.core.money import Money

MAX_PRICE_AGE = timedelta(seconds=10)
# Public trade metadata must fit the signed BIGINT in the approved durable schema.
MAX_TRADE_ID: Final[int] = 2**63 - 1


class ObservationKind(Enum):
    STREAM = "STREAM"
    SNAPSHOT = "SNAPSHOT"


@dataclass(frozen=True, slots=True)
class QuoteObservation:
    source: str
    base: str
    quote: str
    amount: Money
    trade_id: int
    trade_time: datetime
    received_at: datetime
    observation_kind: ObservationKind

    def __post_init__(self) -> None:
        if type(self.trade_id) is not int or not 0 <= self.trade_id <= MAX_TRADE_ID:
            raise ValueError("invalid trade identifier")
        if not self.source or not self.base or not self.quote:
            raise ValueError("missing quote identity")
        if not isinstance(self.observation_kind, ObservationKind):
            raise ValueError("invalid observation kind")
        base, quote = self.base.upper(), self.quote.upper()
        if self.amount.unit != quote or not Money.of("0", quote) < self.amount:
            raise ValueError("invalid positive quote amount/unit")
        require_aware("trade_time", self.trade_time)
        require_aware("received_at", self.received_at)
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "quote", quote)
        object.__setattr__(self, "trade_time", self.trade_time.astimezone(UTC))
        object.__setattr__(self, "received_at", self.received_at.astimezone(UTC))


class Readiness(Enum):
    MISSING = "MISSING"
    RECOVERING = "RECOVERING"
    STALE = "STALE"
    READY = "READY"


def readiness(
    *,
    quote: QuoteObservation | None,
    connected: bool,
    reconciled: bool,
    producer_alive: bool,
    now: datetime,
) -> Readiness:
    require_aware("reference_time", now)
    if quote is None:
        return Readiness.MISSING
    if not connected or not reconciled or not producer_alive or quote.trade_time > now:
        return Readiness.RECOVERING
    if now - quote.trade_time > MAX_PRICE_AGE:
        return Readiness.STALE
    return Readiness.READY


@dataclass(frozen=True, slots=True)
class QuoteState:
    confirmed: QuoteObservation | None = None
    candidate: QuoteObservation | None = None
    order_ambiguous_at: datetime | None = None
    protocol_error: bool = False


def _same_pair(a: QuoteObservation, b: QuoteObservation) -> None:
    if (a.source, a.base, a.quote) != (b.source, b.base, b.quote):
        raise ValueError("cannot compare different quote identities")


def observe(state: QuoteState, incoming: QuoteObservation) -> QuoteState:
    current = state.candidate or state.confirmed
    if current is None:
        return replace(state, confirmed=incoming, candidate=incoming)
    _same_pair(current, incoming)
    if (
        current.observation_kind is ObservationKind.STREAM
        and incoming.observation_kind is ObservationKind.STREAM
        and current.trade_id == incoming.trade_id
        and (current.trade_time != incoming.trade_time or current.amount != incoming.amount)
    ):
        at = max(current.trade_time, incoming.trade_time)
        return replace(
            state, protocol_error=True, order_ambiguous_at=max(at, state.order_ambiguous_at or at)
        )
    if incoming.trade_time < current.trade_time:
        return state
    if incoming.trade_time == current.trade_time:
        if (
            current.observation_kind is ObservationKind.STREAM
            and incoming.observation_kind is ObservationKind.STREAM
            and current.trade_id != incoming.trade_id
        ):
            return replace(
                state,
                candidate=incoming,
                confirmed=(
                    incoming
                    if state.order_ambiguous_at is None and not state.protocol_error
                    else state.confirmed
                ),
            )
        if incoming.amount != current.amount:
            at = incoming.trade_time
            return replace(state, order_ambiguous_at=max(at, state.order_ambiguous_at or at))
        return state
    return replace(
        state,
        candidate=incoming,
        confirmed=(
            incoming
            if state.order_ambiguous_at is None and not state.protocol_error
            else state.confirmed
        ),
    )


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    state: QuoteState
    succeeded: bool


def reconcile(
    state: QuoteState,
    snapshot: QuoteObservation,
    *,
    started_at: datetime,
    now: datetime,
) -> ReconciliationResult:
    require_aware("recovery_started_at", started_at)
    require_aware("reference_time", now)
    latch = state.order_ambiguous_at
    if latch is not None and (started_at <= latch or snapshot.trade_time <= latch):
        return ReconciliationResult(state, succeeded=False)
    current = state.candidate
    if current is not None:
        _same_pair(current, snapshot)
        if current.trade_time == snapshot.trade_time and current.amount != snapshot.amount:
            at = snapshot.trade_time
            return ReconciliationResult(
                replace(state, order_ambiguous_at=max(at, latch or at)), succeeded=False
            )
    winner = snapshot if current is None or snapshot.trade_time > current.trade_time else current
    if winner.trade_time > now or now - winner.trade_time > MAX_PRICE_AGE:
        return ReconciliationResult(state, succeeded=False)
    return ReconciliationResult(QuoteState(confirmed=winner, candidate=winner), succeeded=True)
