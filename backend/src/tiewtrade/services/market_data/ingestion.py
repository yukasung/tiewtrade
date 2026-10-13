"""Bounded, durable public-observation ingestion."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import (
    CandleWindow,
    Timeframe,
    align_ceil,
    align_floor,
    bounded_windows,
    expected_opens,
    initial_window,
    missing_windows,
    retention_cutoff,
)
from tiewtrade.infra.db.errors import DatabaseTimeoutError
from tiewtrade.infra.db.session import MarketDataSession, market_data_session
from tiewtrade.infra.indicators.source import begin_source_write, source_write_timeouts
from tiewtrade.infra.market_data.claims import (
    Claim,
    claim_next,
    cleanup,
    lock_claim,
    update_claim,
    write_candles,
)
from tiewtrade.infra.market_data.records import PartitionUnavailableError, StaleClaimError
from tiewtrade.infra.market_data.storage import PAIRS, database_now, refresh_due, stored_rows
from tiewtrade.venues.candles import CandlePage, CandleSource
from tiewtrade.venues.errors import (
    VenueError,
    VenueOutcomeUnknownError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueUnavailableError,
)
from tiewtrade.venues.symbols import Symbol

MARKET_TIMEOUT = timedelta(seconds=10)


@dataclass(frozen=True, slots=True)
class RoundSummary:
    attempts: int = 0
    stored: int = 0
    stale: int = 0


async def _seed_initial_demand(session: MarketDataSession) -> None:
    as_of = await database_now(session)
    for base, quote in sorted(PAIRS):
        for timeframe in Timeframe:
            window = initial_window(timeframe, as_of)
            await session.execute(
                """INSERT INTO market_candle_demand
                (source,base,quote,timeframe,desired_start,desired_end,requested_at)
                VALUES ('primary_spot',:base,:quote,:timeframe,:start,:end,:now)
                ON CONFLICT DO NOTHING""",
                {
                    "base": base,
                    "quote": quote,
                    "timeframe": timeframe.value,
                    "start": window.start,
                    "end": window.end,
                    "now": as_of,
                },
            )


async def _next_fetch_window(
    session: MarketDataSession,
    claim: Claim,
    cursor: datetime,
    end: datetime,
    refresh_at: datetime | None = None,
    max_request_span: timedelta | None = None,
) -> CandleWindow | None:
    if cursor >= end:
        return None
    for window in bounded_windows(CandleWindow(cursor, end), claim.timeframe):
        rows = await stored_rows(session, claim.base, claim.quote, claim.timeframe, window)
        if refresh_at is None:
            gaps = missing_windows(window, claim.timeframe, (r.candle.open_at for r in rows))
        else:
            eligible = {r.candle.open_at for r in rows if refresh_due(r, refresh_at)}
            gaps = missing_windows(
                window,
                claim.timeframe,
                (t for t in expected_opens(window, claim.timeframe) if t not in eligible),
            )
        if gaps:
            fetch_end = min(gaps[0].end, end)
            if max_request_span is not None:
                fetch_end = min(
                    fetch_end, align_floor(gaps[0].start + max_request_span, claim.timeframe)
                )
                if fetch_end <= gaps[0].start:
                    raise ValueError("source span limit is shorter than one candle")
            return CandleWindow(gaps[0].start, fetch_end)
    return None


async def _prepare(
    session: MarketDataSession, claim: Claim, max_request_span: timedelta | None = None
) -> CandleWindow | None:
    row = await lock_claim(session, claim)
    now = await database_now(session)
    start = max(row["leased_start"], align_ceil(retention_cutoff(now), claim.timeframe))
    end = min(row["leased_end"], align_floor(now, claim.timeframe) + claim.timeframe.span)
    if row["fetch_unit_id"] is not None:
        if row["attemptcount"] >= 3:
            await update_claim(
                session,
                claim,
                release=True,
                status="FAILED",
                failure_code="SOURCE_FAILURE",
                next_attempt_at=now + timedelta(seconds=120),
            )
            return None
        fetch_start = max(row["fetch_start"], start)
        fetch_end = min(row["fetch_end"], end)
        if max_request_span is not None:
            fetch_end = min(fetch_end, align_floor(fetch_start + max_request_span, claim.timeframe))
        if fetch_start < fetch_end:
            # Reclaimed pre-upgrade units may exceed the newly declared limit.
            # Keep their attempt budget/identity and leave the remaining tail for the cursor.
            await update_claim(session, claim, fetch_start=fetch_start, fetch_end=fetch_end)
            return CandleWindow(fetch_start, fetch_end)
    phase = row["phase"]
    cursor = max(row["cursor"] or start, start)
    refresh_at = row["refresh_as_of"] or row["refresh_requested_at"]
    window: CandleWindow | None = None
    if phase == "FORWARD" and cursor < end:
        window = await _next_fetch_window(
            session, claim, cursor, end, max_request_span=max_request_span
        )
    if window is None:
        gap = (
            await _next_fetch_window(session, claim, start, end, max_request_span=max_request_span)
            if start < end
            else None
        )
        if phase == "FORWARD" and gap is not None:
            await update_claim(
                session,
                claim,
                release=True,
                phase="REPAIR",
                repair_pass=1,
                repair_cursor=start,
                next_attempt_at=now + timedelta(seconds=30),
            )
            return None
        if phase == "REPAIR":
            window = await _next_fetch_window(
                session,
                claim,
                max(row["repair_cursor"] or start, start),
                end,
                max_request_span=max_request_span,
            )
            if window is None and gap is not None and row["repair_pass"] < 2:
                await update_claim(
                    session,
                    claim,
                    release=True,
                    repair_pass=2,
                    repair_cursor=start,
                    next_attempt_at=now + timedelta(seconds=60),
                )
                return None
        else:
            window = None
        if window is None:
            if refresh_at is not None:
                window = await _next_fetch_window(
                    session,
                    claim,
                    max(row["refresh_cursor"] or start, start),
                    end,
                    refresh_at,
                    max_request_span=max_request_span,
                )
                phase = "REFRESH"
            if window is None:
                requested = row["refresh_requested_at"]
                changes: dict[str, object] = {
                    "checked_at": now,
                    "fetch_unit_id": None,
                    "fetch_start": None,
                    "fetch_end": None,
                    "attemptcount": 0,
                }
                if refresh_at is not None:
                    changes["refresh_served_at"] = refresh_at
                if requested is not None and refresh_at is not None and requested > refresh_at:
                    changes.update(
                        status="PENDING",
                        phase="REFRESH",
                        refresh_as_of=requested,
                        refresh_cursor=start,
                        next_attempt_at=now + timedelta(seconds=30),
                    )
                elif gap is not None:
                    changes.update(
                        status="UNAVAILABLE",
                        failure_code="GAP_REPAIR_EXHAUSTED",
                        next_attempt_at=now + timedelta(seconds=120),
                    )
                elif (
                    row["desired_start"] < row["leased_start"]
                    or row["desired_end"] > row["leased_end"]
                ):
                    # A right-only extension has already proved every slot in the
                    # old lease. Continue at that boundary instead of restarting
                    # the full retention window. A left extension still has to
                    # begin at the newly requested start.
                    expansion_cursor = (
                        row["desired_start"]
                        if row["desired_start"] < row["leased_start"]
                        else row["leased_end"]
                    )
                    changes.update(
                        status="PENDING",
                        phase="FORWARD",
                        leased_start=row["desired_start"],
                        leased_end=row["desired_end"],
                        cursor=expansion_cursor,
                        refresh_cursor=None,
                        refresh_as_of=None,
                    )
                else:
                    changes.update(status="COMPLETE", failure_code=None)
                await update_claim(session, claim, release=True, **changes)
                return None
    assert window is not None
    await update_claim(
        session,
        claim,
        phase=phase,
        refresh_as_of=refresh_at,
        fetch_unit_id=uuid4(),
        fetch_start=window.start,
        fetch_end=window.end,
        attemptcount=0,
    )
    return window


def _validate(page: CandlePage, claim: Claim, window: CandleWindow) -> CandlePage:
    if (
        page.symbol != Symbol(claim.base, claim.quote)
        or page.timeframe != claim.timeframe
        or page.window != window
        or len(page.candles) > 1000
    ):
        raise VenueProtocolError()
    opens = [c.open_at for c in page.candles]
    if opens != sorted(opens):
        raise VenueProtocolError()
    candles = {c.open_at: c for c in page.candles}
    if any(candles[c.open_at] != c for c in page.candles):
        raise VenueProtocolError()
    return CandlePage(
        page.symbol, page.timeframe, page.window, tuple(candles.values()), page.received_at
    )


async def _failure(session: MarketDataSession, claim: Claim, error: Exception) -> bool:
    rate_limit_error = error if isinstance(error, VenueRateLimitedError) else None
    if rate_limit_error is not None:
        # Take the source lock before any series row; two 429 responses must not
        # hold opposing row locks while each tries to defer the entire source.
        await session.execute("SELECT pg_advisory_xact_lock(709, 1)")
    row = await lock_claim(session, claim)
    now = await database_now(session)
    count = row["attemptcount"]
    transient = isinstance(
        error,
        (
            TimeoutError,
            DatabaseTimeoutError,
            VenueUnavailableError,
            VenueOutcomeUnknownError,
            VenueRateLimitedError,
        ),
    )
    delay = timedelta(seconds={1: 30, 2: 60}.get(count, 120))
    if rate_limit_error is not None:
        delay = max(delay, rate_limit_error.retry_after or timedelta(seconds=120))
        await session.execute(
            """UPDATE market_candle_demand SET
            next_attempt_at=greatest(next_attempt_at,:until) WHERE source='primary_spot'""",
            {"until": now + delay},
        )
    await update_claim(
        session,
        claim,
        release=True,
        status="PENDING" if transient and count < 3 else "FAILED",
        checked_at=now,
        failure_code="PARTITION_UNAVAILABLE"
        if isinstance(error, PartitionUnavailableError)
        else "SOURCE_FAILURE",
        next_attempt_at=now + delay,
    )
    return rate_limit_error is not None


async def run_round(
    engine: AsyncEngine, source: CandleSource, worker: str, as_of: datetime
) -> RoundSummary:
    max_span = source.max_request_span
    if max_span is not None and max_span <= timedelta(0):
        raise ValueError("source span limit must be positive")
    async with market_data_session(engine) as session:
        await _seed_initial_demand(session)
    try:
        async with market_data_session(engine) as session:
            await cleanup(session)
    except DatabaseTimeoutError:
        # No fetch was claimed. The regular scheduler may try the next round;
        # do not spin or consume a source attempt for cleanup contention.
        logging.getLogger(__name__).warning("market-data cleanup: DATABASE_TIMEOUT")
        return RoundSummary()
    attempts = stored = stale = 0
    # Non-fetch state transitions are bounded independently of the HTTP budget.
    for _ in range(120):
        if attempts == 4:
            break
        async with market_data_session(engine) as session:
            claim = await claim_next(session, worker)
            if claim is None:
                break
            window = await _prepare(session, claim, max_span)
            if window is None:
                continue
            row = await lock_claim(session, claim)
            started = await database_now(session)
            await update_claim(
                session, claim, attemptcount=row["attemptcount"] + 1, fetch_started_at=started
            )
        attempts += 1
        try:
            async with asyncio.timeout(MARKET_TIMEOUT.total_seconds()):
                page = await source.fetch_candles(
                    Symbol(claim.base, claim.quote), claim.timeframe, window.start, window.end, 1000
                )
            page = _validate(page, claim, window)
            async with market_data_session(engine) as session:
                await begin_source_write(session)
                row = await lock_claim(session, claim)
                await write_candles(session, claim, page.candles, started)
                now = await database_now(session)
                refresh_unserved = False
                if row["phase"] == "REFRESH":
                    committed = await stored_rows(
                        session, claim.base, claim.quote, claim.timeframe, window
                    )
                    refresh_unserved = bool(
                        set(expected_opens(window, claim.timeframe))
                        - {candle.candle.open_at for candle in committed}
                    ) or any(refresh_due(candle, row["refresh_as_of"]) for candle in committed)
                if refresh_unserved:
                    await _failure(session, claim, VenueUnavailableError())
                else:
                    column = {
                        "FORWARD": "cursor",
                        "REPAIR": "repair_cursor",
                        "REFRESH": "refresh_cursor",
                    }[row["phase"]]
                    progress = window.end
                    if row["phase"] == "FORWARD" and len(page.candles) == 1000:
                        progress = page.candles[-1].end_at
                    await update_claim(
                        session,
                        claim,
                        release=True,
                        status="PENDING",
                        checked_at=now,
                        fetch_unit_id=None,
                        fetch_start=None,
                        fetch_end=None,
                        attemptcount=0,
                        failure_code=None,
                        **{column: progress},
                    )
                stored += len(page.candles)
        except StaleClaimError:
            stale += 1
        except (
            VenueError,
            TimeoutError,
            DatabaseTimeoutError,
            PartitionUnavailableError,
            ValueError,
        ) as error:
            try:
                async with market_data_session(engine) as session:
                    if isinstance(error, DatabaseTimeoutError):
                        await source_write_timeouts(session)
                    if await _failure(session, claim, error):
                        break
            except StaleClaimError:
                stale += 1
            except DatabaseTimeoutError:
                # The attempt reservation committed before HTTP. Preserve it
                # and its lease for normal reclaim rather than refunding it or
                # retrying an aborted write/claim update in a hot loop.
                logging.getLogger(__name__).warning("market-data failure record: DATABASE_TIMEOUT")
                break
    return RoundSummary(attempts, stored, stale)
