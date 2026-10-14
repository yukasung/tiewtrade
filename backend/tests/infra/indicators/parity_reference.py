"""Test-only source fixture and independent rounded-Fraction indicator reference."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from fractions import Fraction

from tests.core.test_indicators import _oracle, _text
from tiewtrade.core.indicators import (
    IndicatorPoint,
    IndicatorStatus,
    IndicatorStream,
    IndicatorValue,
)
from tiewtrade.core.market_data import Candle, CandleFinality, CandleWindow, Timeframe
from tiewtrade.core.money import Money, Quantity, Scalar

Slot = tuple[datetime, Candle | None, datetime | None]
SPAN = timedelta(minutes=1)


def scan(
    stream: IndicatorStream,
    slots: tuple[Slot, ...],
    batch_size: int,
    fetch_size: int,
) -> tuple[IndicatorPoint, ...]:
    points: list[IndicatorPoint] = []
    for fetch in range(0, len(slots), fetch_size):
        rows = slots[fetch : fetch + fetch_size]
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            points.extend(stream.feed_batch(batch, output_indices=tuple(range(len(batch)))).points)
    return tuple(points)


def parity_slots(
    start: datetime,
    warm_count: int,
    offsets: list[int],
    *,
    refresh_index: int = 1020,
    gap_index: int = 1040,
    open_index: int = 1010,
) -> tuple[Slot, ...]:
    slots: list[Slot] = []
    first = 1000 - warm_count
    for index in range(1220):
        moment = start + index * SPAN
        if index < first or index == gap_index:
            slots.append((moment, None, None))
            continue
        ticks = 100 * 10**18 + offsets[index - first]
        close = Money.of(_text(ticks), "USDT")
        finality = (
            CandleFinality.OPEN
            if index == open_index
            else CandleFinality.UNCONFIRMED
            if index % 3 == 0 or index == refresh_index
            else CandleFinality.CLOSED
        )
        bar = Candle(
            "BTC",
            "USDT",
            Timeframe.M1,
            moment,
            moment + SPAN,
            close,
            close + Money.of(1, "USDT"),
            close - Money.of(1, "USDT"),
            close,
            Quantity.of("1.123456789012345678", "BTC"),
            finality,
            moment,
        )
        slots.append((moment, bar, moment if index == refresh_index else bar.end_at))
    return tuple(slots)


def reference_points(slots: tuple[Slot, ...]) -> tuple[IndicatorPoint, ...]:
    # Eligibility/finality follows the fixture's observations; all bars end before as_of.
    segments: list[list[int]] = [[]]
    metadata: list[tuple[datetime | None, CandleFinality | None, IndicatorStatus, int, int]] = []
    seed: datetime | None = None
    blocked = unconfirmed = False
    for moment, bar, fetched in slots:
        status, position = IndicatorStatus.WARM_UP, -1
        finality: CandleFinality | None = None
        if bar is None:
            segments.append([])
            seed, blocked, unconfirmed = None, False, False
            status = IndicatorStatus.GAP
        elif bar.finality is not CandleFinality.OPEN:
            if bar.finality is CandleFinality.UNCONFIRMED and (
                fetched is None or fetched < bar.end_at
            ):
                blocked = True
            if blocked:
                status = IndicatorStatus.REFRESH_REQUIRED
            else:
                seed = seed if seed is not None else moment
                unconfirmed |= bar.finality is CandleFinality.UNCONFIRMED
                finality = CandleFinality.UNCONFIRMED if unconfirmed else CandleFinality.CLOSED
                status = IndicatorStatus.READY
                # Parse fixture text as an exact Fraction instead of decimal arithmetic.
                fraction_ticks = Fraction(bar.close.as_parts()["amount"]) * 10**18
                assert fraction_ticks.denominator == 1
                segments[-1].append(fraction_ticks.numerator)
                position = len(segments[-1]) - 1
        metadata.append((seed, finality, status, len(segments) - 1, position))
    answers = [_oracle(prices) for prices in segments]
    points = []
    names = (
        "ema20",
        "ema50",
        "ema200",
        "rsi14",
        "atr14",
    )
    for (moment, _, _), (point_seed, finality, status, segment, position) in zip(
        slots, metadata, strict=True
    ):
        values: dict[str, IndicatorValue] = {}
        for name in names:
            ticks = answers[segment][position][name] if position >= 0 else None
            value = (
                None
                if ticks is None
                else Scalar.of(_text(ticks))
                if name == "rsi14"
                else Money.of(_text(ticks), "USDT")
            )
            values[name] = IndicatorValue(
                value,
                IndicatorStatus.WARM_UP
                if status is IndicatorStatus.READY and value is None
                else status,
            )
        points.append(IndicatorPoint(moment, point_seed, finality, values))
    return tuple(points)


def canonical_digest(
    slots: tuple[Slot, ...], calculation: CandleWindow, timeframe: Timeframe = Timeframe.M1
) -> str:
    def stamp(moment: datetime) -> str:
        return moment.astimezone(UTC).isoformat(timespec="microseconds")

    records: list[list[object]] = [
        [
            1,
            "primary_spot",
            "BTC",
            "USDT",
            timeframe.value,
            "indicators-v2",
            stamp(calculation.start),
            stamp(calculation.end),
        ]
    ]
    for moment, bar, fetched in slots:
        records.append(
            [stamp(moment), "MISSING"]
            if bar is None
            else [
                stamp(moment),
                stamp(bar.end_at),
                bar.open.as_parts()["amount"],
                bar.high.as_parts()["amount"],
                bar.low.as_parts()["amount"],
                bar.close.as_parts()["amount"],
                bar.volume.as_parts()["quantity"],
                bar.finality.value,
                stamp(bar.observed_at),
                stamp(fetched) if fetched else None,
            ]
        )
    return hashlib.sha256(
        b"".join(
            json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
            for record in records
        )
    ).hexdigest()
