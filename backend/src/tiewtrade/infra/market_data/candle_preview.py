"""Public preview persistence with singleton writer fencing and bounded rows."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import (
    CandleSeries,
    CandleWindow,
    Timeframe,
    advance,
    align_ceil,
    align_floor,
    previous_open,
    retention_cutoff,
)
from tiewtrade.infra.db.session import MarketDataSession, UserSession, require_market_data_session
from tiewtrade.infra.market_data.catalog import PAIRS, SOURCE
from tiewtrade.infra.market_data.storage import coalesce_demand, database_now, parameters


@dataclass(frozen=True, slots=True)
class PreviewLease:
    owner: UUID
    epoch: int


class PreviewLeaseLostError(ValueError):
    pass


async def acquire(session: MarketDataSession, owner: UUID) -> PreviewLease | None:
    session = require_market_data_session(session)
    row = (
        (
            await session.execute(
                """UPDATE market_candle_feed_state SET owner=:owner,
      epoch=epoch+1,lease_until=clock_timestamp()+interval '20 seconds',connected=false,
      bootstrapped=false,failure_code='RECOVERING'
      WHERE source=:source AND lease_until<=clock_timestamp() RETURNING epoch""",
                {"owner": owner, "source": SOURCE},
            )
        )
        .mappings()
        .first()
    )
    return PreviewLease(owner, row["epoch"]) if row else None


async def fence(session: MarketDataSession, lease: PreviewLease) -> RowMapping:
    session = require_market_data_session(session)
    row = (
        (
            await session.execute(
                """UPDATE market_candle_feed_state
      SET lease_until=clock_timestamp()+interval '20 seconds'
      WHERE source=:source AND owner=:owner AND epoch=:epoch
        AND lease_until>clock_timestamp() RETURNING *""",
                {"source": SOURCE, "owner": lease.owner, "epoch": lease.epoch},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise PreviewLeaseLostError()
    return row


async def connection(
    session: MarketDataSession, lease: PreviewLease, connected: bool, failure: str | None = None
) -> PreviewLease:
    await fence(session, lease)
    row = (
        (
            await session.execute(
                """UPDATE market_candle_feed_state SET epoch=epoch+1,
      connected=:connected,bootstrapped=false,failure_code=:failure
      WHERE source=:source RETURNING epoch""",
                {"source": SOURCE, "connected": connected, "failure": failure},
            )
        )
        .mappings()
        .one()
    )
    return PreviewLease(lease.owner, row["epoch"])


async def bootstrap_series(
    session: MarketDataSession, lease: PreviewLease, series: CandleSeries
) -> None:
    await fence(session, lease)
    now = await database_now(session)
    upper = align_floor(now, series.timeframe)
    lower = align_ceil(retention_cutoff(now, series.timeframe), series.timeframe)
    last = (
        await session.execute(
            """SELECT max(open_at) FROM market_candles
      WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe
        AND fetch_started_at>=end_at""",
            parameters(series.base, series.quote, series.timeframe),
        )
    ).scalar_one()
    start = max(
        lower,
        last if last is not None else advance(upper, series.timeframe, -1000),
    )
    if start < upper:
        await coalesce_demand(
            session,
            series.base,
            series.quote,
            series.timeframe,
            CandleWindow(start, upper),
        )


async def complete_bootstrap(session: MarketDataSession, lease: PreviewLease) -> None:
    await fence(session, lease)
    await session.execute(
        """UPDATE market_candle_feed_state SET bootstrapped=true
      WHERE source=:source""",
        {"source": SOURCE},
    )


async def enqueue_ended(
    session: MarketDataSession,
    lease: PreviewLease,
    demands: dict[tuple[str, str, Timeframe], CandleWindow],
) -> None:
    state = await fence(session, lease)
    metadata = dict(state["metadata"])
    now = await database_now(session)
    for (base, quote, tf), window in demands.items():
        parameters(base, quote, tf)
        if window.end > align_floor(now, tf):
            continue  # A closure hint does not authorize a pre-end REST observation.
        key = f"{base}/{quote}/{tf.value}"
        previous = datetime.fromisoformat(metadata[key]) if key in metadata else None
        if previous is not None and previous >= window.end:
            continue
        start = max(window.start, align_ceil(retention_cutoff(now, tf), tf))
        if previous is not None:
            start = max(start, previous)
        if start < window.end:
            await coalesce_demand(session, base, quote, tf, CandleWindow(start, window.end))
        metadata[key] = window.end.isoformat()
    if len(metadata) > len(PAIRS) * len(Timeframe):
        raise ValueError("unbounded preview metadata")
    await session.execute(
        """UPDATE market_candle_feed_state SET metadata=CAST(:metadata AS jsonb)
      WHERE source=:source""",
        {"source": SOURCE, "metadata": json.dumps(metadata)},
    )


async def flush(
    session: MarketDataSession, lease: PreviewLease, rows: tuple[tuple[CandleObservation, int], ...]
) -> None:
    await fence(session, lease)
    if len(rows) > len(PAIRS) * len(Timeframe) or len(
        {(r.candle.base, r.candle.quote, r.candle.timeframe) for r, _ in rows}
    ) != len(rows):
        raise ValueError("unbounded preview batch")
    for observation, revision in rows:
        candle = observation.candle
        params = parameters(candle.base, candle.quote, candle.timeframe) | {
            "open_at": candle.open_at,
            "end_at": candle.end_at,
            "open": candle.open.as_parts()["amount"],
            "high": candle.high.as_parts()["amount"],
            "low": candle.low.as_parts()["amount"],
            "close": candle.close.as_parts()["amount"],
            "volume": candle.volume.as_parts()["quantity"],
            "finality": candle.finality.value,
            "event": observation.event_at,
            "received": observation.received_at,
            "epoch": lease.epoch,
            "revision": revision,
        }
        await session.execute(
            """INSERT INTO market_candle_preview
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
           event_at,received_at,epoch,revision)
          VALUES(:source,:base,:quote,:timeframe,:open_at,:end_at,:open,:high,:low,:close,
            :volume,:finality,:event,:received,:epoch,:revision)
          ON CONFLICT(source,base,quote,timeframe,open_at) DO UPDATE SET
            open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
            volume=excluded.volume,finality=excluded.finality,event_at=excluded.event_at,
            received_at=excluded.received_at,epoch=excluded.epoch,revision=excluded.revision
          WHERE excluded.event_at>=market_candle_preview.event_at
            AND (excluded.epoch>market_candle_preview.epoch OR
              (excluded.epoch=market_candle_preview.epoch AND
               excluded.revision>market_candle_preview.revision))""",
            params,
        )
        await session.execute(
            """DELETE FROM market_candle_preview WHERE
          source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe AND
          open_at NOT IN(SELECT open_at FROM market_candle_preview WHERE source=:source
            AND base=:base AND quote=:quote AND timeframe=:timeframe
            ORDER BY open_at DESC LIMIT 120)""",
            params,
        )


async def read_live(
    session: UserSession, series: CandleSeries
) -> tuple[RowMapping, tuple[Mapping[str, Any], ...], datetime, bool]:
    params = parameters(series.base, series.quote, series.timeframe)
    now = await database_now(session)
    snapshot = tuple(
        (
            await session.execute(
                """WITH snapshot AS MATERIALIZED (SELECT CAST(:now AS timestamptz) AS now),
      preview AS MATERIALIZED (
        SELECT p.open_at,p.end_at,p.open,p.high,p.low,p.close,p.volume,p.finality,
          p.event_at,p.received_at,p.epoch,p.revision,
          EXISTS(SELECT 1 FROM market_candles h,snapshot
            WHERE h.source=p.source AND h.base=p.base AND h.quote=p.quote
              AND h.timeframe=p.timeframe AND h.open_at=p.open_at
              AND h.end_at<=snapshot.now AND h.finality<>'OPEN'
              AND (h.finality='CLOSED' OR h.fetch_started_at>=h.end_at)) AS settled
        FROM market_candle_preview p WHERE p.source=:source AND p.base=:base
          AND p.quote=:quote AND p.timeframe=:timeframe
        ORDER BY p.open_at DESC LIMIT 2)
      SELECT state.*,snapshot.now AS server_time,
        preview.open_at AS preview_open_at,preview.end_at AS preview_end_at,
        preview.open AS preview_open,preview.high AS preview_high,
        preview.low AS preview_low,preview.close AS preview_close,
        preview.volume AS preview_volume,preview.finality AS preview_finality,
        preview.event_at AS preview_event_at,preview.received_at AS preview_received_at,
        preview.epoch AS preview_epoch,preview.revision AS preview_revision,
        preview.settled AS preview_settled
      FROM market_candle_feed_state state CROSS JOIN snapshot
      LEFT JOIN preview ON true WHERE state.source=:source
      ORDER BY preview.open_at DESC NULLS LAST""",
                params | {"now": now},
            )
        ).mappings()
    )
    state = snapshot[0]
    now = state["server_time"]
    rows = tuple(
        {
            "open_at": row["preview_open_at"],
            "end_at": row["preview_end_at"],
            "open": row["preview_open"],
            "high": row["preview_high"],
            "low": row["preview_low"],
            "close": row["preview_close"],
            "volume": row["preview_volume"],
            "finality": row["preview_finality"],
            "event_at": row["preview_event_at"],
            "received_at": row["preview_received_at"],
            "epoch": row["preview_epoch"],
            "revision": row["preview_revision"],
            "settled": row["preview_settled"],
        }
        for row in snapshot
        if row["preview_open_at"] is not None
    )
    recovered = False
    if rows:
        previous = previous_open(rows[0]["open_at"], series.timeframe)
        recovered = bool(
            (
                await session.execute(
                    """SELECT EXISTS(SELECT 1 FROM market_candles WHERE
          source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe
          AND open_at=:previous AND finality<>'OPEN'
          AND (finality='CLOSED' OR fetch_started_at>=end_at))""",
                    params | {"previous": previous},
                )
            ).scalar_one()
        )
    return state, tuple(reversed(rows)), now, recovered
