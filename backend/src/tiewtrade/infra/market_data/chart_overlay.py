"""Bounded chart-only stream overlay. Canonical/indicator reads remain unchanged."""

import asyncio
from dataclasses import replace

from sqlalchemy import RowMapping

from tiewtrade.core.market_data import CandleWindow, Timeframe, missing_windows
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.market_data.records import CandleRead
from tiewtrade.infra.market_data.storage import _stored, parameters


def _merge_preview(
    history: CandleRead,
    preview_rows: tuple[RowMapping, ...],
    window: CandleWindow,
    timeframe: Timeframe,
) -> CandleRead:
    merged = {stored.candle.open_at: stored for stored in history.candles}
    for row in preview_rows:
        stored = merged.get(row["open_at"])
        if stored is not None:
            candle = stored.candle
            settled = candle.finality.value == "CLOSED" or (
                candle.end_at <= history.observed_at and stored.fetch_started_at >= candle.end_at
            )
            if settled or candle.observed_at >= row["received_at"]:
                continue
        merged[row["open_at"]] = _stored(dict(row) | {"finality": row["display_finality"]})
    candles = tuple(merged[key] for key in sorted(merged))
    gaps = missing_windows(window, timeframe, merged)
    return replace(
        history,
        candles=candles,
        gaps=gaps,
        coverage="PRESENT" if not gaps else "INCOMPLETE" if candles else "UNAVAILABLE",
    )


async def overlay_preview(
    session: UserSession,
    base: str,
    quote: str,
    timeframe: Timeframe,
    window: CandleWindow,
    history: CandleRead,
) -> CandleRead:
    result = await session.execute(
        """SELECT p.*,
        p.received_at AS observed_at,p.received_at AS fetch_started_at,
        p.received_at AS last_checked_at,
        CASE WHEN p.end_at<=:now OR p.epoch<>s.epoch THEN 'UNCONFIRMED'
             ELSE p.finality END AS display_finality
        FROM market_candle_preview p JOIN market_candle_feed_state s USING(source)
        WHERE p.source=:source AND p.base=:base AND p.quote=:quote AND p.timeframe=:timeframe
          AND p.open_at>=:start AND p.open_at<:end AND p.open_at<=:now
        ORDER BY p.open_at DESC LIMIT 120""",
        parameters(base, quote, timeframe)
        | {"start": window.start, "end": window.end, "now": history.observed_at},
    )
    rows = tuple(result.mappings())
    return await asyncio.to_thread(_merge_preview, history, rows, window, timeframe)
