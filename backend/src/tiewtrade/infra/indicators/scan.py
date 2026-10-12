"""Bounded source scan; returns sealed STAGING only, never publishes READY."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import cast

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.market_data import Candle, bounded_windows, expected_opens
from tiewtrade.core.money import MoneyError
from tiewtrade.infra.db.errors import IndicatorBuildOwnershipError
from tiewtrade.infra.indicators.claims import BuildClaim
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter
from tiewtrade.infra.indicators.scheduling import POLL_SECONDS
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import (
    StagingSnapshot,
    append_checkpoint,
    capture_snapshot,
    initialize,
    seal,
)
from tiewtrade.infra.market_data.indicator_reader import (
    IndicatorDigest,
    decode_row,
    fetch_rows,
    query_budget,
)

HEARTBEAT_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class StagingScan:
    snapshot: StagingSnapshot
    digest: str
    checkpoint_count: int


async def scan_staging(
    engine: AsyncEngine,
    writer: PinnedIndicatorWriter,
    claim: BuildClaim,
    *,
    scheduled: bool = False,
) -> StagingScan:
    """Caller owns pinned scope; errors return only after source/heartbeat are closed.

    Terminal release/publication belongs to the caller after this function returns.
    No result points or whole dataset are retained, and an aborted scan is never resumed.
    """
    writer.require_claim(claim)
    await writer.heartbeat()
    failure: list[BaseException] = []
    stop = asyncio.Event()

    async def heartbeats() -> None:
        next_heartbeat = monotonic() + HEARTBEAT_SECONDS if scheduled else 0.0
        try:
            while not stop.is_set():
                try:
                    await asyncio.wait_for(
                        stop.wait(), POLL_SECONDS if scheduled else HEARTBEAT_SECONDS
                    )
                    break
                except TimeoutError:
                    pass
                if stop.is_set():
                    break
                if not scheduled or monotonic() >= next_heartbeat:
                    await writer.heartbeat()
                    next_heartbeat = monotonic() + HEARTBEAT_SECONDS
                if scheduled:
                    await writer.coalesce()
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            failure.append(error)

    task = asyncio.create_task(heartbeats())
    captured: StagingSnapshot | None = None
    initialized = False
    try:
        async with indicator_source_session(engine) as session:
            snapshot = await capture_snapshot(session, claim)
            captured = snapshot
            deadline = monotonic() + (claim.attempt_deadline - snapshot.as_of).total_seconds()

            def check() -> None:
                if failure:
                    raise failure[0]
                writer.require_claim(claim)
                if monotonic() >= deadline:
                    raise IndicatorBuildOwnershipError("indicator build deadline exceeded")

            check()
            await initialize(writer, claim, snapshot)
            initialized = True
            stream = IndicatorStream(claim.base, claim.quote, claim.timeframe, snapshot.as_of)
            digest = IndicatorDigest(claim.base, claim.quote, claim.timeframe, snapshot.calculation)
            await append_checkpoint(writer, claim, snapshot, stream, snapshot.calculation.start)
            count = 1
            for window in bounded_windows(snapshot.calculation, claim.timeframe):
                check()
                await query_budget(session, deadline)
                rows = {
                    cast(datetime, row["open_at"]): row
                    for row in await fetch_rows(
                        session, claim.base, claim.quote, claim.timeframe, window
                    )
                }
                opens = iter(expected_opens(window, claim.timeframe))
                while True:
                    check()
                    slots: list[tuple[datetime, Candle | None, datetime | None]] = []
                    for _ in range(16):
                        moment = next(opens, None)
                        if moment is None:
                            break
                        raw = rows.get(moment)
                        row = decode_row(raw, stream.series) if raw is not None else None
                        digest.feed(moment, row)
                        slots.append(
                            (
                                moment,
                                row.candle if row else None,
                                row.fetch_started_at if row else None,
                            )
                        )
                    if not slots:
                        break
                    stream.feed_batch(tuple(slots), output_indices=())
                    check()
                    await asyncio.sleep(0)
                await append_checkpoint(writer, claim, snapshot, stream, window.end)
                count += 1
                # Do not retain the previous input batch while fetching its successor.
                rows.clear()
                raw = None
                row = None
                slots.clear()
            check()
            revision = digest.hexdigest()
        # Close the source before recording completed scan metadata / future publication.
        if failure:
            raise failure[0]
        await seal(writer, claim, revision)
        stop.set()
        await asyncio.wait_for(asyncio.shield(task), 2)
        check()
        return StagingScan(snapshot, revision, count)
    except MoneyError:
        # A numeric failure still needs the healthy pinned session to publish its manifest.
        # Close source (via the context above), then let any started heartbeat commit.
        stop.set()
        await asyncio.wait_for(asyncio.shield(task), 2)
        if failure:
            raise failure[0] from None
        writer.require_claim(claim)
        if not initialized and captured is not None:
            # Persist only the already captured identity for numeric publication.
            # No new source snapshot, calculation, checkpoint or retry cycle.
            # Ambiguous DB commits are not MoneyError and never enter this path.
            await initialize(writer, claim, captured)
        raise
    finally:
        stop.set()
        if not task.done():
            task.cancel()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
