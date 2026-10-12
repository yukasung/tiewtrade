"""Typed builder-only recovery and bounded metadata collection."""

import asyncio
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.indicators.session import indicator_writer_session


class RetryResult(StrEnum):
    QUEUED = "QUEUED"
    REJECTED = "REJECTED"


async def retry_job(engine: AsyncEngine, job: UUID, request: UUID) -> RetryResult:
    if not isinstance(job, UUID) or not isinstance(request, UUID):
        raise ValueError("UUID_REQUIRED")
    async with asyncio.timeout(2):
        async with indicator_writer_session(engine) as session:
            await session.execute("""SELECT set_config('lock_timeout','200ms',true),
                set_config('statement_timeout','500ms',true)""")
            result = RetryResult(
                (
                    await session.execute(
                        "SELECT public.retry_indicator_build_job(:job,:request)",
                        {"job": job, "request": request},
                    )
                ).scalar_one()
            )
        return result


async def collect(engine: AsyncEngine) -> dict[str, int]:
    async with asyncio.timeout(2):
        async with indicator_writer_session(engine) as session:
            await session.execute("""SELECT set_config('lock_timeout','200ms',true),
                set_config('statement_timeout','500ms',true)""")
            result: dict[str, int] = (
                await session.execute("SELECT public.gc_indicator_data()")
            ).scalar_one()
        return result
