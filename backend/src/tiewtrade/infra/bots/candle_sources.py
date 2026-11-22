"""Bounded public candle demand and durable recovery metadata for F-21."""

from dataclasses import dataclass
from datetime import datetime

from tiewtrade.core.market_data import CandleWindow, Timeframe, advance, align_floor
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.market_data.candle_closure import connection_ready, series_health
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.storage import closure_control, enqueue


@dataclass(frozen=True, slots=True)
class CandleSourceState:
    ready: bool
    recovery_at: datetime | None


async def price_recovery_at(session: UserSession) -> datetime | None:
    return (
        await session.execute(
            "SELECT bot_recovery_at FROM market_price_feed WHERE source=:source",
            {"source": SOURCE},
        )
    ).scalar_one_or_none()


async def ensure_candles(
    session: UserSession, pair: PositionPair, timeframe: Timeframe, observed_at: datetime
) -> None:
    end = align_floor(observed_at, timeframe)
    await enqueue(
        session, pair.base, pair.quote, timeframe, CandleWindow(advance(end, timeframe, -1), end)
    )


async def candle_source_state(
    session: UserSession, pair: PositionPair, timeframe: Timeframe, *, lock: bool = False
) -> CandleSourceState:
    row = (
        await session.execute(
            "SELECT status,phase,failure_code,lease_until,bot_recovery_at,clock_timestamp() AS now "
            "FROM market_candle_demand WHERE source=:source AND base=:base AND quote=:quote "
            "AND timeframe=:timeframe" + (" FOR SHARE" if lock else ""),
            {
                "source": SOURCE,
                "base": pair.base,
                "quote": pair.quote,
                "timeframe": timeframe.value,
            },
        )
    ).one_or_none()
    if row is None:
        return CandleSourceState(False, None)
    control = await closure_control(session)
    closure_ready = control is None or not control["enabled"] or await connection_ready(session)
    recovery = row.bot_recovery_at
    if control is not None and control["enabled"]:
        healthy, repaired_at = await series_health(
            session, pair.base, pair.quote, timeframe, row.now
        )
        closure_ready = closure_ready and healthy
        recovery = max(filter(None, (recovery, control["recovery_at"], repaired_at)))
    return CandleSourceState(
        closure_ready
        and row.status not in ("FAILED", "UNAVAILABLE")
        and row.phase != "REPAIR"
        and row.failure_code is None
        and not (
            row.status == "RUNNING" and (row.lease_until is None or row.lease_until <= row.now)
        ),
        recovery,
    )
