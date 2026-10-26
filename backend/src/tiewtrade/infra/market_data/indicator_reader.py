"""Bounded, consistent candle scan for F-11."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic
from typing import cast

from sqlalchemy import RowMapping

from tiewtrade.core.indicators import FORMULA_VERSION, IndicatorPoint, IndicatorStream
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleSeries,
    CandleWindow,
    Timeframe,
    advance,
    bounded_windows,
    expected_opens,
    slot_count,
)
from tiewtrade.core.moments import require_aware
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.crypto.indicator_cursor import DatasetChangedError
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.session import IndicatorSourceSession
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.records import StoredCandle
from tiewtrade.infra.market_data.storage import parameters


def timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


@dataclass(frozen=True, slots=True)
class IndicatorRead:
    points: tuple[IndicatorPoint, ...]
    revision: str
    refresh_first: datetime | None
    refresh_more: bool
    queue_status: str | None
    failure_code: str | None


async def query_budget(session: UserSession | IndicatorSourceSession, deadline: float) -> None:
    remaining = int((deadline - monotonic()) * 1000)
    if remaining <= 0:
        raise TimeoutError()
    await session.execute(
        "SELECT set_config('statement_timeout', :value, true)", {"value": str(min(500, remaining))}
    )
    await session.execute(
        "SELECT set_config('lock_timeout', :value, true)", {"value": str(min(200, remaining))}
    )


async def fetch_rows(
    session: UserSession | IndicatorSourceSession,
    base: str,
    quote: str,
    timeframe: Timeframe,
    window: CandleWindow,
    *,
    numeric_text: bool = False,
) -> tuple[RowMapping, ...]:
    numeric_columns = (
        "open::text AS open,high::text AS high,low::text AS low,"
        "close::text AS close,volume::text AS volume"
        if numeric_text
        else "open,high,low,close,volume"
    )
    result = await session.execute(
        "SELECT source,base,quote,timeframe,open_at,end_at," + numeric_columns + ","
        "finality,observed_at,fetch_started_at,last_checked_at FROM market_candles "
        "WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe "
        "AND open_at>=:start AND open_at<:end ORDER BY open_at LIMIT 1000",
        parameters(base, quote, timeframe) | {"start": window.start, "end": window.end},
    )
    return tuple(result.mappings())


def decode_row(row: RowMapping, series: CandleSeries) -> StoredCandle:
    if (row["source"], row["base"], row["quote"], row["timeframe"]) != (
        SOURCE,
        series.base,
        series.quote,
        series.timeframe.value,
    ):
        raise ValueError("different stored series")
    # asyncpg already returns validated PostgreSQL numeric columns as Decimal.
    # Construct the domain values directly so their mandatory __post_init__
    # invariants run once instead of paying the public text-normalisation path
    # and a second guarded Decimal context for every OHLCV field.  Text remains
    # supported for the API's lower-materialisation query path.
    open_value = cast(Decimal | str, row["open"])
    high_value = cast(Decimal | str, row["high"])
    low_value = cast(Decimal | str, row["low"])
    close_value = cast(Decimal | str, row["close"])
    volume_value = cast(Decimal | str, row["volume"])
    candle = Candle(
        series.base,
        series.quote,
        series.timeframe,
        cast(datetime, row["open_at"]),
        cast(datetime, row["end_at"]),
        Money(open_value, series.quote)
        if isinstance(open_value, Decimal)
        else Money.of(open_value, series.quote),
        Money(high_value, series.quote)
        if isinstance(high_value, Decimal)
        else Money.of(high_value, series.quote),
        Money(low_value, series.quote)
        if isinstance(low_value, Decimal)
        else Money.of(low_value, series.quote),
        Money(close_value, series.quote)
        if isinstance(close_value, Decimal)
        else Money.of(close_value, series.quote),
        Quantity(volume_value, series.base)
        if isinstance(volume_value, Decimal)
        else Quantity.of(volume_value, series.base),
        CandleFinality(row["finality"]),
        cast(datetime, row["observed_at"]),
        series,
    )
    fetched, checked = (
        cast(datetime, row["fetch_started_at"]),
        cast(datetime, row["last_checked_at"]),
    )
    if fetched is not None:
        require_aware("fetch_started_at", fetched)
    require_aware("last_checked_at", checked)
    if fetched is not None and fetched > checked:
        raise ValueError("invalid fetch observation")
    return StoredCandle(candle, fetched, checked)


class IndicatorDigest:
    """Canonical full dataset hash shared by API reference and prepared builder."""

    def __init__(
        self, base: str, quote: str, timeframe: Timeframe, calculation: CandleWindow
    ) -> None:
        self._digest = hashlib.sha256()
        self._record(
            [
                1,
                SOURCE,
                base,
                quote,
                timeframe.value,
                FORMULA_VERSION,
                timestamp(calculation.start),
                timestamp(calculation.end),
            ]
        )

    def _record(self, value: list[object]) -> None:
        self._digest.update(
            json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
        )

    def feed(self, moment: datetime, row: StoredCandle | None) -> None:
        if row is None:
            self._record([timestamp(moment), "MISSING"])
        else:
            candle = row.candle
            self._record(
                [
                    timestamp(moment),
                    timestamp(candle.end_at),
                    candle.open.as_parts()["amount"],
                    candle.high.as_parts()["amount"],
                    candle.low.as_parts()["amount"],
                    candle.close.as_parts()["amount"],
                    candle.volume.as_parts()["quantity"],
                    candle.finality.value,
                    timestamp(candle.observed_at),
                    timestamp(row.fetch_started_at) if row.fetch_started_at else None,
                ]
            )

    def feed_batch(self, slots: tuple[tuple[datetime, StoredCandle | None], ...]) -> None:
        if type(slots) is not tuple or not 1 <= len(slots) <= 1000:
            raise ValueError("bounded digest slots required")
        missing = bytearray()
        for moment, row in slots:
            if row is None:
                missing.extend(b'["')
                missing.extend(timestamp(moment).encode("ascii"))
                missing.extend(b'","MISSING"]\n')
                continue
            if missing:
                self._digest.update(missing)
                missing.clear()
            self.feed(moment, row)
        if missing:
            self._digest.update(missing)

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


async def read_indicators(
    session: UserSession,
    base: str,
    quote: str,
    timeframe: Timeframe,
    calculation: CandleWindow,
    output: CandleWindow,
    as_of: datetime,
    deadline: float,
    revision: str | None = None,
    *,
    restored: IndicatorStream | None = None,
    prepared_revision: str | None = None,
) -> IndicatorRead:
    parameters(base, quote, timeframe)
    if (restored is None) != (prepared_revision is None):
        raise ValueError("prepared stream and revision required together")
    digest = IndicatorDigest(base, quote, timeframe, calculation) if restored is None else None
    stream = restored or IndicatorStream(base, quote, timeframe, as_of)
    points: list[IndicatorPoint] = []
    refresh_first: datetime | None = None
    refresh_more = False
    # Keep cold asyncpg result materialization below the 100 ms event-loop budget
    # while preserving the accepted maximum of eight candle queries. Sparse long
    # timeframes need smaller batches than dense minute/hour calculations.
    total_slots = slot_count(calculation, timeframe)
    api_batch_size = min(250, max(1, (total_slots + 7) // 8))
    for batch in bounded_windows(calculation, timeframe, api_batch_size):
        await query_budget(session, deadline)
        rows = {
            cast(datetime, row["open_at"]): row
            for row in await fetch_rows(session, base, quote, timeframe, batch, numeric_text=True)
        }
        opens = iter(expected_opens(batch, timeframe))
        while True:
            moments = tuple(next(opens, None) for _ in range(16))
            slots: list[tuple[datetime, Candle | None, datetime | None]] = []
            digest_slots: list[tuple[datetime, StoredCandle | None]] = []
            for moment in moments:
                if moment is None:
                    break
                raw = rows.get(moment)
                row = decode_row(raw, stream.series) if raw is not None else None
                if digest is not None:
                    digest_slots.append((moment, row))
                slots.append(
                    (moment, row.candle if row else None, row.fetch_started_at if row else None)
                )
            if not slots:
                break
            if digest is not None:
                digest.feed_batch(tuple(digest_slots))
            selected = tuple(
                i for i, (moment, _, _) in enumerate(slots) if output.start <= moment < output.end
            )
            result = stream.feed_batch(tuple(slots), output_indices=selected)
            points.extend(result.points)
            for index in selected:
                dependency = result.refresh_dependencies[index]
                if dependency is not None:
                    if refresh_first is None:
                        refresh_first = dependency
                    elif dependency >= advance(refresh_first, timeframe, 1000):
                        refresh_more = True
            if monotonic() >= deadline:
                raise TimeoutError()
            await asyncio.sleep(0)
    result_revision = digest.hexdigest() if digest is not None else cast(str, prepared_revision)
    if revision is not None and result_revision != revision:
        raise DatasetChangedError()
    await query_budget(session, deadline)
    demand = (
        (
            await session.execute(
                "SELECT status,failure_code FROM market_candle_demand "
                "WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe",
                parameters(base, quote, timeframe),
            )
        )
        .mappings()
        .first()
    )
    return IndicatorRead(
        tuple(points),
        result_revision,
        refresh_first,
        refresh_more,
        str(demand["status"]) if demand else None,
        str(demand["failure_code"]) if demand and demand["failure_code"] else None,
    )
