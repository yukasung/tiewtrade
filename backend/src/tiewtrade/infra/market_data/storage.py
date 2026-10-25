import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import RowMapping

from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleWindow,
    Timeframe,
    align_floor,
    missing_windows,
    next_open,
    slot_count,
)
from tiewtrade.core.money import Quantity
from tiewtrade.core.timeframes import candle_storage_cutoff as retention_cutoff
from tiewtrade.infra.db import money_from_columns, quantity_from_columns, require_user_session
from tiewtrade.infra.db.session import MarketDataSession, UserSession, require_market_data_session
from tiewtrade.infra.market_data.catalog import SOURCE as SOURCE
from tiewtrade.infra.market_data.records import (
    CandleRead,
    RetentionError,
    StoredCandle,
    UnsupportedSeriesError,
    WindowTooLargeError,
)

Session = UserSession | MarketDataSession


def parameters(base: str, quote: str, timeframe: Timeframe) -> dict[str, object]:
    normalized_base = Quantity.of(0, base).asset
    normalized_quote = Quantity.of(0, quote).asset
    if (
        normalized_quote != "USDT"
        or normalized_base == normalized_quote
        or not isinstance(timeframe, Timeframe)
    ):
        raise UnsupportedSeriesError()
    return {
        "source": SOURCE,
        "base": normalized_base,
        "quote": normalized_quote,
        "timeframe": timeframe.value,
    }


def _session(session: Session) -> Session:
    if isinstance(session, UserSession):
        return require_user_session(session)
    return require_market_data_session(session)


async def require_active_pair(session: UserSession, base: str, quote: str) -> None:
    active = (
        await require_user_session(session).execute(
            """SELECT EXISTS(SELECT 1 FROM active_supported_symbols
            WHERE base=:base AND quote=:quote)""",
            {"base": base, "quote": quote},
        )
    ).scalar_one()
    if not active:
        raise UnsupportedSeriesError()


async def database_now(session: Session) -> datetime:
    result = await _session(session).execute("SELECT clock_timestamp()")
    value: datetime = result.scalar_one()
    return value


def validate_window(
    window: CandleWindow, as_of: datetime, timeframe: Timeframe, *, reading: bool = False
) -> None:
    duration_cutoff = retention_cutoff(window.end, timeframe)
    if timeframe in (Timeframe.W1, Timeframe.MN1):
        duration_cutoff = align_floor(duration_cutoff, timeframe)
    if window.start < retention_cutoff(as_of, timeframe) or window.end > next_open(
        align_floor(as_of, timeframe), timeframe
    ):
        raise RetentionError()
    if window.start < duration_cutoff:
        raise RetentionError()
    if reading and slot_count(window, timeframe) > 1000:
        raise WindowTooLargeError()


def _stored(row: RowMapping | Mapping[str, Any]) -> StoredCandle:
    candle = Candle(
        base=row["base"],
        quote=row["quote"],
        timeframe=Timeframe(row["timeframe"]),
        open_at=row["open_at"],
        end_at=row["end_at"],
        open=money_from_columns(row["open"], row["quote"]),
        high=money_from_columns(row["high"], row["quote"]),
        low=money_from_columns(row["low"], row["quote"]),
        close=money_from_columns(row["close"], row["quote"]),
        volume=quantity_from_columns(row["volume"], row["base"]),
        finality=CandleFinality(row["finality"]),
        observed_at=row["observed_at"],
    )
    return StoredCandle(candle, row["fetch_started_at"], row["last_checked_at"])


async def stored_rows(
    session: Session,
    base: str,
    quote: str,
    timeframe: Timeframe,
    window: CandleWindow,
    *,
    offload_conversion: bool = False,
) -> tuple[StoredCandle, ...]:
    params = parameters(base, quote, timeframe) | {"start": window.start, "end": window.end}
    result = await _session(session).execute(
        """SELECT * FROM market_candles
        WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe
          AND open_at>=:start AND open_at<:end ORDER BY open_at LIMIT 1000""",
        params,
    )
    rows = tuple(result.mappings())

    def convert() -> tuple[StoredCandle, ...]:
        return tuple(_stored(row) for row in rows)

    return await asyncio.to_thread(convert) if offload_conversion else convert()


async def read_candles(
    session: UserSession,
    base: str,
    quote: str,
    timeframe: Timeframe,
    window: CandleWindow,
    limit: int,
    *,
    offload_conversion: bool = False,
) -> CandleRead:
    session = require_user_session(session)
    now = await database_now(session)
    validate_window(window, now, timeframe, reading=True)
    rows = await stored_rows(
        session,
        base,
        quote,
        timeframe,
        window,
        offload_conversion=offload_conversion,
    )
    demand = (
        (
            await session.execute(
                """SELECT status,failure_code,
        refresh_requested_at,refresh_served_at FROM market_candle_demand
        WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe""",
                parameters(base, quote, timeframe),
            )
        )
        .mappings()
        .first()
    )
    status = str(demand["status"]) if demand else None
    failure = demand["failure_code"] if demand else None
    requested = demand["refresh_requested_at"] if demand else None
    served = demand["refresh_served_at"] if demand else None

    def finish() -> CandleRead:
        gaps = missing_windows(window, timeframe, (row.candle.open_at for row in rows))
        pending = (
            requested is not None
            and (served is None or requested > served)
            and any(refresh_due(row, requested) for row in rows)
        )
        coverage: Literal["PRESENT", "INCOMPLETE", "UNAVAILABLE"] = (
            "PRESENT"
            if not gaps
            else ("UNAVAILABLE" if status in {"UNAVAILABLE", "FAILED"} else "INCOMPLETE")
        )
        return CandleRead(
            rows[-limit:] if limit < len(rows) else rows,
            gaps,
            coverage,
            now,
            pending,
            status,
            failure,
        )

    return await asyncio.to_thread(finish) if offload_conversion else finish()


async def window_needs_work(
    session: Session,
    base: str,
    quote: str,
    timeframe: Timeframe,
    window: CandleWindow,
    as_of: datetime,
) -> tuple[bool, bool]:
    params = parameters(base, quote, timeframe) | {
        "start": window.start,
        "end": window.end,
        "as_of": as_of,
    }
    row = (
        (
            await _session(session).execute(
                """SELECT count(*) AS present,
        coalesce(bool_or(finality<>'CLOSED' AND fetch_started_at<end_at
            AND fetch_started_at<:as_of
            AND (:as_of>=end_at OR last_checked_at+interval '30 seconds'<=:as_of)),false)
            AS refresh
        FROM market_candles
        WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe
          AND open_at>=:start AND open_at<:end""",
                params,
            )
        )
        .mappings()
        .one()
    )
    return int(row["present"]) < slot_count(window, timeframe), bool(row["refresh"])


def refresh_due(row: StoredCandle, as_of: datetime) -> bool:
    return (
        row.candle.finality is not CandleFinality.CLOSED
        and row.fetch_started_at < row.candle.end_at
        and row.fetch_started_at < as_of
        and (as_of >= row.candle.end_at or row.last_checked_at + timedelta(seconds=30) <= as_of)
    )


async def enqueue(
    session: UserSession, base: str, quote: str, timeframe: Timeframe, window: CandleWindow
) -> bool:
    session = require_user_session(session)
    return await coalesce_demand(session, base, quote, timeframe, window)


async def coalesce_demand(
    session: Session, base: str, quote: str, timeframe: Timeframe, window: CandleWindow
) -> bool:
    """Shared row-locked demand; never resets worker claims, attempts or backoff."""
    if isinstance(session, UserSession):
        await require_active_pair(session, base, quote)
    session = _session(session)
    now = await database_now(session)
    validate_window(window, now, timeframe)
    missing, refresh = await window_needs_work(session, base, quote, timeframe, window, now)
    if not missing and not refresh:
        return False
    params = parameters(base, quote, timeframe) | {
        "start": window.start,
        "end": window.end,
        "now": now,
    }
    await session.execute(
        """INSERT INTO market_candle_demand
        (source,base,quote,timeframe,desired_start,desired_end,requested_at)
        VALUES (:source,:base,:quote,:timeframe,:start,:end,:now)
        ON CONFLICT DO NOTHING""",
        params,
    )
    row = (
        (
            await session.execute(
                """SELECT * FROM market_candle_demand
        WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe
        FOR UPDATE""",
                params,
            )
        )
        .mappings()
        .one()
    )
    missing, refresh = await window_needs_work(session, base, quote, timeframe, window, now)
    if not missing and not refresh:
        return False
    end = max(row["desired_end"], window.end)
    duration_cutoff = retention_cutoff(end, timeframe)
    if timeframe in (Timeframe.W1, Timeframe.MN1):
        duration_cutoff = align_floor(duration_cutoff, timeframe)
    start = max(
        min(row["desired_start"], window.start),
        retention_cutoff(now, timeframe),
        duration_cutoff,
    )
    params.update(start=start, end=end, refresh=now if refresh else None)
    await session.execute(
        """UPDATE market_candle_demand SET desired_start=:start,
        desired_end=:end, requested_at=greatest(requested_at,:now),
        refresh_requested_at=CASE WHEN CAST(:refresh AS timestamptz) IS NULL
          THEN refresh_requested_at ELSE greatest(refresh_requested_at,:refresh) END
        WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe""",
        params,
    )
    return True
