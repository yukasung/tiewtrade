"""Observe actual row-lock prefixes while typed entrypoints wait at barriers."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_source_lock_matrix import blocked_by
from tests.services.indicator_builder.test_attempt import seed
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.scan import scan_staging

TABLES = (
    "indicator_source_guard",
    "indicator_rollout_control",
    "indicator_build_slot",
    "indicator_build_jobs",
)
ORDERS = {
    "claim": (1, 2),  # Jobs use SKIP LOCKED, tested separately by claim regressions.
    "heartbeat": (2, 3),
    "publish": (0, 1, 2, 3),
    "retry": (3,),
    "gc": (0, 3),
}


async def assert_row_locked(c: AsyncConnection, table: str, expected: bool) -> None:
    try:
        async with c.begin_nested():
            await c.execute(text(f"SELECT 1 FROM {table} FOR UPDATE NOWAIT"))
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) == "55P03"
        assert expected, table
    else:
        assert not expected, table
        # Successful probes must not retain locks and interfere with the waiter.
        await c.rollback()


@pytest.mark.parametrize(
    "operation,barrier", [(op, stage) for op, stages in ORDERS.items() for stage in stages]
)
async def test_typed_entrypoint_row_lock_prefix_and_cancel_cleanup(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    operation: str,
    barrier: int,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = None if operation == "claim" else await writer.claim(uuid4())
        if operation == "publish":
            assert claim is not None
            await scan_staging(builder_engine, writer, claim)

        async def invoke() -> None:
            if operation == "claim":
                await writer.claim(uuid4())
            elif operation == "heartbeat":
                await writer.heartbeat()
            elif operation == "publish":
                assert claim is not None
                await writer.publish_ready(claim)
            else:
                async with writer.transaction() as session:
                    if operation == "gc":
                        await session.execute("SELECT gc_indicator_data()")
                    else:
                        assert claim is not None
                        await session.execute(
                            "SELECT retry_indicator_build_job(:job,:request)",
                            {"job": claim.job_id, "request": uuid4()},
                        )

        async with migrator_engine.connect() as holder, migrator_engine.connect() as observer:
            pid: int = (await holder.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            await holder.execute(text(f"SELECT 1 FROM {TABLES[barrier]} FOR UPDATE"))
            task = asyncio.create_task(invoke())
            try:
                await blocked_by(observer, writer.backend_pid, pid)
                prefix = ORDERS[operation][: ORDERS[operation].index(barrier)]
                for index, table in enumerate(TABLES):
                    if index != barrier:
                        await assert_row_locked(observer, table, index in prefix)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                assert task.cancelled()
                await holder.rollback()
            for table in TABLES:
                await assert_row_locked(observer, table, False)


@pytest.mark.parametrize("barrier", [0, 1, 2, 3])
async def test_reap_row_lock_prefix_and_cancel_returns_advisory_lock(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    barrier: int,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        assert claim is not None
    # Owner has exited and its physical session was discarded; only the orphan remains.
    async with (
        migrator_engine.connect() as holder,
        migrator_engine.connect() as observer,
        migrator_engine.connect() as reaper,
    ):
        holder_pid: int = (await holder.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        reaper_pid: int = (await reaper.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        await reaper.commit()
        await holder.execute(text(f"SELECT 1 FROM {TABLES[barrier]} FOR UPDATE"))

        async def invoke() -> None:
            async with reaper.begin():
                await reaper.execute(
                    text("SELECT reap_indicator_build_slot(:owner,:epoch,:fence)"),
                    claim.parameters(),
                )

        task = asyncio.create_task(invoke())
        try:
            await blocked_by(observer, reaper_pid, holder_pid)
            for index, table in enumerate(TABLES):
                if index != barrier:
                    await assert_row_locked(observer, table, index < barrier)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            assert task.cancelled()
            await holder.rollback()
        for table in TABLES:
            await assert_row_locked(observer, table, False)
        locks: int = (
            await observer.execute(
                text("SELECT count(*) FROM pg_locks WHERE pid=:pid AND locktype='advisory'"),
                {"pid": reaper_pid},
            )
        ).scalar_one()
        assert locks == 0
