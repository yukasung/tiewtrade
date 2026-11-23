"""Native close evidence matched against an independently fetched canonical candle."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import Candle, CandleFinality, advance, align_floor
from tiewtrade.core.moments import require_aware

POLICY_VERSION = 1


class ClosureResult(StrEnum):
    MATCHED = "MATCHED"
    WRONG_SERIES = "WRONG_SERIES"
    NOT_SETTLED = "NOT_SETTLED"
    CONFLICT = "CONFLICT"


def candle_identity(candle: Candle) -> tuple[str, ...]:
    return (
        candle.base,
        candle.quote,
        candle.timeframe.value,
        candle.open_at.isoformat(),
        candle.end_at.isoformat(),
    )


def candle_values(candle: Candle) -> tuple[str, ...]:
    return (
        candle.open.as_parts()["amount"],
        candle.high.as_parts()["amount"],
        candle.low.as_parts()["amount"],
        candle.close.as_parts()["amount"],
        candle.volume.as_parts()["quantity"],
    )


def candle_fingerprint(candle: Candle) -> str:
    """Canonical values; finality and transport timestamps cannot change OHLCV identity."""
    content: tuple[str, ...] = (*candle_identity(candle), *candle_values(candle))
    return hashlib.sha256(json.dumps(content, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ClosureCandidate:
    observation: CandleObservation

    def __post_init__(self) -> None:
        value = self.observation
        if type(value) is not CandleObservation or not value.closed_hint:
            raise ValueError("native closure event required")
        c = value.candle
        if (
            align_floor(c.open_at, c.timeframe) != c.open_at
            or advance(c.open_at, c.timeframe, 1) != c.end_at
            or value.received_at < c.end_at
        ):
            raise ValueError("invalid native close interval")

    @property
    def fingerprint(self) -> str:
        value = self.observation
        return hashlib.sha256(
            json.dumps(
                (
                    POLICY_VERSION,
                    candle_fingerprint(value.candle),
                    value.trade_count,
                    value.first_trade_id,
                    value.last_trade_id,
                ),
                separators=(",", ":"),
            ).encode()
        ).hexdigest()


def verify_closure(
    candidate: ClosureCandidate,
    canonical: Candle,
    *,
    fetch_started_at: datetime,
    as_of: datetime,
) -> ClosureResult:
    require_aware("fetch_started_at", fetch_started_at)
    require_aware("as_of", as_of)
    native = candidate.observation.candle
    if candle_identity(native) != candle_identity(canonical):
        return ClosureResult.WRONG_SERIES
    if (
        canonical.finality is CandleFinality.OPEN
        or canonical.end_at > as_of
        or fetch_started_at < canonical.end_at
        or canonical.observed_at < fetch_started_at
        or canonical.observed_at > as_of
    ):
        return ClosureResult.NOT_SETTLED
    if candle_fingerprint(native) != candle_fingerprint(canonical):
        return ClosureResult.CONFLICT
    return ClosureResult.MATCHED
