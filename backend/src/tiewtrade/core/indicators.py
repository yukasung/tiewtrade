"""Pure eligibility controller and bounded financial transitions (F-11)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from tiewtrade.core.market_data import Candle, CandleFinality, CandleSeries, Timeframe, align_floor
from tiewtrade.core.moments import require_aware
from tiewtrade.core.money import Money, RoundingDirection, Scalar
from tiewtrade.core.money.indicator_batch import (
    FORMULA_VERSION as FORMULA_VERSION,
)
from tiewtrade.core.money.indicator_batch import (
    BatchAction,
    IndicatorBatchInput,
    IndicatorBatchState,
    advance_indicator_batch,
)

ROUNDING = RoundingDirection.TOWARD_NEGATIVE
NAMES = ("ema20", "ema50", "ema200", "rsi14", "macd_line", "macd_signal", "macd_histogram", "atr14")


class IndicatorStatus(StrEnum):
    READY = "READY"
    WARM_UP = "WARM_UP"
    GAP = "GAP"
    REFRESH_REQUIRED = "REFRESH_REQUIRED"


@dataclass(frozen=True, slots=True)
class IndicatorValue:
    value: Money | Scalar | None
    status: IndicatorStatus


@dataclass(frozen=True, slots=True)
class IndicatorPoint:
    open_at: datetime
    seed_open_at: datetime | None
    finality: CandleFinality | None
    values: dict[str, IndicatorValue]


@dataclass(frozen=True, slots=True)
class StreamBatch:
    points: tuple[IndicatorPoint, ...]
    refresh_dependencies: tuple[datetime | None, ...]


@dataclass(frozen=True, slots=True)
class IndicatorCheckpointState:
    numeric: IndicatorBatchState
    seed_open_at: datetime | None
    blocked: bool
    unconfirmed: bool
    refresh_dependency: datetime | None


class IndicatorStream:
    def __init__(self, base: str, quote: str, timeframe: Timeframe, as_of: datetime) -> None:
        require_aware("as_of", as_of)
        self.series = CandleSeries(base, quote, timeframe)
        self.base, self.quote, self.timeframe, self.as_of = (
            self.series.base,
            self.series.quote,
            timeframe,
            as_of,
        )
        self.state = IndicatorBatchState(self.base, self.quote, timeframe.value, timeframe.span)
        self.seed: datetime | None = None
        self.blocked = False
        self.unconfirmed = False
        self.refresh_dependency: datetime | None = None

    def export_state(self) -> IndicatorCheckpointState:
        return IndicatorCheckpointState(
            self.state, self.seed, self.blocked, self.unconfirmed, self.refresh_dependency
        )

    def restore_state(self, checkpoint: IndicatorCheckpointState) -> None:
        if type(checkpoint) is not IndicatorCheckpointState:
            raise ValueError("invalid indicator checkpoint")
        numeric = checkpoint.numeric
        if type(numeric) is not IndicatorBatchState or (
            numeric.base,
            numeric.quote,
            numeric.timeframe,
            numeric.span,
            numeric.formula_version,
        ) != (self.base, self.quote, self.timeframe.value, self.timeframe.span, FORMULA_VERSION):
            raise ValueError("different indicator checkpoint identity")
        if type(checkpoint.blocked) is not bool or type(checkpoint.unconfirmed) is not bool:
            raise ValueError("invalid indicator checkpoint flags")
        if numeric.last_open is not None and (
            numeric.last_open != align_floor(numeric.last_open, self.timeframe)
        ):
            raise ValueError("unaligned indicator checkpoint time")
        for moment in (checkpoint.seed_open_at, checkpoint.refresh_dependency):
            if moment is not None:
                require_aware("checkpoint time", moment)
                if numeric.last_open is None or moment > numeric.last_open:
                    raise ValueError("invalid indicator checkpoint time")
                if moment != align_floor(moment, self.timeframe):
                    raise ValueError("unaligned indicator checkpoint time")
                if moment + self.timeframe.span > self.as_of:
                    raise ValueError("ineligible indicator checkpoint time")
        if (
            (checkpoint.blocked != (checkpoint.refresh_dependency is not None))
            or (checkpoint.seed_open_at is None and checkpoint.unconfirmed)
            or (numeric.previous is None and checkpoint.seed_open_at is not None)
            or (numeric.previous is not None and checkpoint.seed_open_at is None)
            or (
                numeric.last_open is None
                and (
                    checkpoint.blocked
                    or checkpoint.unconfirmed
                    or checkpoint.seed_open_at is not None
                )
            )
        ):
            raise ValueError("inconsistent indicator checkpoint")
        if checkpoint.seed_open_at is not None:
            assert numeric.last_open is not None
            # Inputs after a refresh dependency are HOLD, including the dependency slot.
            end = min(numeric.last_open + self.timeframe.span, self.as_of)
            if checkpoint.refresh_dependency is not None:
                end = min(end, checkpoint.refresh_dependency)
            possible_count = (end - checkpoint.seed_open_at) // self.timeframe.span
            if numeric.accepted_count > possible_count:
                raise ValueError("accepted input count exceeds seed history")
        self.state = numeric
        self.seed = checkpoint.seed_open_at
        self.blocked = checkpoint.blocked
        self.unconfirmed = checkpoint.unconfirmed
        self.refresh_dependency = checkpoint.refresh_dependency

    def feed(
        self, open_at: datetime, candle: Candle | None, fetch_started_at: datetime | None
    ) -> IndicatorPoint:
        return self.feed_batch(((open_at, candle, fetch_started_at),), output_indices=(0,)).points[
            0
        ]

    def feed_batch(
        self,
        slots: tuple[tuple[datetime, Candle | None, datetime | None], ...],
        *,
        output_indices: tuple[int, ...],
    ) -> StreamBatch:
        if type(slots) is not tuple or not 1 <= len(slots) <= 16:
            raise ValueError("bounded slots required")
        if tuple(sorted(set(output_indices))) != output_indices or any(
            type(i) is not int or not 0 <= i < len(slots) for i in output_indices
        ):
            raise ValueError("invalid output indices")
        previous = self.state.last_open
        for moment, candle, fetched in slots:
            require_aware("open_at", moment)
            if previous is not None and moment != previous + self.timeframe.span:
                raise ValueError("input slots must be consecutive")
            previous = moment
            if candle is not None and (
                candle.open_at,
                candle.base,
                candle.quote,
                candle.timeframe,
            ) != (moment, self.base, self.quote, self.timeframe):
                raise ValueError("different candle series")
            if fetched is not None:
                require_aware("fetch_started_at", fetched)
        seed, blocked, unconfirmed, dependency = (
            self.seed,
            self.blocked,
            self.unconfirmed,
            self.refresh_dependency,
        )
        inputs: list[IndicatorBatchInput] = []
        metadata: list[tuple[IndicatorStatus, datetime | None, CandleFinality | None]] = []
        dependencies: list[datetime | None] = []
        for moment, candle, fetched in slots:
            status = IndicatorStatus.WARM_UP
            finality: CandleFinality | None = None
            action = BatchAction.HOLD
            if candle is None:
                action, status = BatchAction.RESET, IndicatorStatus.GAP
                seed = dependency = None
                blocked = unconfirmed = False
            elif candle.end_at <= self.as_of and candle.finality is not CandleFinality.OPEN:
                if candle.finality is CandleFinality.UNCONFIRMED and (
                    fetched is None or fetched < candle.end_at
                ):
                    blocked = True
                    if dependency is None:
                        dependency = moment
                if blocked:
                    status = IndicatorStatus.REFRESH_REQUIRED
                else:
                    action, status = BatchAction.ACCEPT, IndicatorStatus.READY
                    if seed is None:
                        seed = moment
                    unconfirmed |= candle.finality is CandleFinality.UNCONFIRMED
                    finality = CandleFinality.UNCONFIRMED if unconfirmed else CandleFinality.CLOSED
            accepted = candle if action is BatchAction.ACCEPT else None
            inputs.append(
                IndicatorBatchInput(
                    moment,
                    action,
                    self.base,
                    self.quote,
                    self.timeframe.value,
                    accepted.close if accepted else None,
                    accepted.high if accepted else None,
                    accepted.low if accepted else None,
                )
            )
            metadata.append((status, seed, finality))
            dependencies.append(dependency)
        result = advance_indicator_batch(
            self.state, tuple(inputs), output_indices=output_indices, rounding=ROUNDING
        )
        points = []
        for index, values in result.outputs:
            status, point_seed, finality = metadata[index]
            points.append(
                IndicatorPoint(
                    slots[index][0],
                    point_seed,
                    finality,
                    {
                        name: IndicatorValue(
                            value,
                            IndicatorStatus.WARM_UP
                            if status is IndicatorStatus.READY and value is None
                            else status,
                        )
                        for name, value in zip(NAMES, values, strict=True)
                    },
                )
            )
        self.state = result.state
        self.seed, self.blocked, self.unconfirmed, self.refresh_dependency = (
            seed,
            blocked,
            unconfirmed,
            dependency,
        )
        return StreamBatch(tuple(points), tuple(dependencies))
