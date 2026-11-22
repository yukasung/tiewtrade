"""Restricted metadata-only coalescing; no source scan or ownership takeover."""

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.indicators.session import (
    IndicatorWriterSession,
    indicator_writer_session,
    require_indicator_writer_session,
)

POLL_SECONDS = 10.0


async def coalesce_session(session: IndicatorWriterSession) -> int:
    session = require_indicator_writer_session(session)
    await session.execute("""SELECT set_config('lock_timeout','200ms',true),
        set_config('statement_timeout','500ms',true)""")
    # Only one coalescer needs to update the shared catalog per transaction.
    # Keep this gate through commit/rollback, independent of the attempt lock (711,1).
    # A busy caller leaves durable work to the holder and the next regular poll.
    if not (await session.execute("SELECT pg_try_advisory_xact_lock(711,2)")).scalar_one():
        return 0
    return int(
        (await session.execute("SELECT public.coalesce_indicator_build_jobs()")).scalar_one()
    )


async def coalesce_jobs(engine: AsyncEngine) -> int:
    async with indicator_writer_session(engine) as session:
        return await coalesce_session(session)
