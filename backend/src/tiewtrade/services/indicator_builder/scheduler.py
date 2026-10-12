"""Poll durable eligibility and dispatch sequential attempts on the two-connection pool."""

import asyncio
from contextlib import suppress
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.indicators.maintenance import collect
from tiewtrade.infra.indicators.scheduling import POLL_SECONDS, coalesce_jobs
from tiewtrade.services.indicator_builder.attempt import AttemptResult, AttemptStatus, run_attempt


async def run_scheduler(
    engine: AsyncEngine, owner: UUID, stop: asyncio.Event
) -> AttemptResult | None:
    """Stop on ambiguous ownership; supervisor/recovery belongs to the launcher.

    A stop signal drains the current attempt. Task cancellation instead invokes
    run_attempt's bounded cancellation protocol and propagates to the caller.
    Database/configuration failures propagate with their existing fixed types.
    """
    if type(owner) is not UUID:
        raise ValueError("builder owner UUID required")
    while not stop.is_set():
        await collect(engine)
        await coalesce_jobs(engine)
        if stop.is_set():
            break
        result = await run_attempt(engine, owner, scheduled=True)
        if result.status is AttemptStatus.ORPHANED:
            return result
        # Keep dispatching eligible series without sleeping while work is queued.
        # Backoff eligibility and fair rounds are enforced by the DB claim function.
        if result.status not in (AttemptStatus.NO_JOB, AttemptStatus.LOCK_BUSY):
            continue
        # Timeout simply starts the next DB-clock poll.
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), POLL_SECONDS)
    return None
