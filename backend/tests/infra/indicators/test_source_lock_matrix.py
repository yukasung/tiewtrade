"""R2-L: real PostgreSQL lock graphs, rollback and actual-role entrypoints."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import INSERT, values
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_source import md as md
from tests.infra.market_data.test_batch_write import candle_at, claim_window
from tests.services.indicator_builder.test_attempt import seed
from tiewtrade.core.market_data import CandleWindow
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import DatabaseUnavailableError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.claims import PublicationResult, publish
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.scan import scan_staging
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.market_data.claims import cleanup, write_candles
from tiewtrade.infra.market_data.records import StaleClaimError
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


class RollbackMaintenanceError(Exception):
    """Exit after real DDL while preserving the fixture's partition topology."""


@pytest.mark.parametrize("operation", ["drop", "detach", "truncate"])
async def test_query_timeout_after_ddl_rolls_back_epoch_heads_and_topology(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    operation: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    built = await run_attempt(builder_engine, uuid4())
    assert built.status is AttemptStatus.READY
    async with migrator_engine.connect() as c:
        before = await source_state(c)
        relations = (
            await c.execute(
                text("SELECT relid FROM pg_partition_tree('market_candles') ORDER BY relid")
            )
        ).all()
    with pytest.raises(DBAPIError, match="statement timeout"):
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            assert (await c.execute(text("SELECT count(*) FROM indicator_heads"))).scalar_one() == 0
            await c.execute(text(ddl(operation)))
            await c.execute(text("SET LOCAL statement_timeout='50ms'"))
            await c.execute(text("SELECT pg_sleep(5)"))
    async with migrator_engine.connect() as c:
        assert await source_state(c) == before
        assert (
            await c.execute(text("SELECT generation_id FROM indicator_heads"))
        ).scalar_one() == built.generation_id
        assert (
            await c.execute(
                text("SELECT relid FROM pg_partition_tree('market_candles') ORDER BY relid")
            )
        ).all() == relations


@pytest.mark.usefixtures("active")
async def test_write_upgrade_rejected_without_access_exclusive_lock(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        with pytest.raises(DBAPIError, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
            async with c.begin_nested():
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        assert (
            await c.execute(
                text("""SELECT count(*) FROM pg_locks WHERE
          pid=pg_backend_pid() AND mode='AccessExclusiveLock'""")
            )
        ).scalar_one() == 0


def ddl(operation: str) -> str:
    name = f"market_candles_{datetime.now(UTC):%Y%m}"
    return {
        "drop": f"DROP TABLE {name}",
        "detach": f"ALTER TABLE market_candles DETACH PARTITION {name}",
        "truncate": "TRUNCATE market_candles",
    }[operation]


async def source_state(connection: AsyncConnection) -> dict[str, Any]:
    return dict(
        (
            await connection.execute(
                text("SELECT epoch,revision,journal_floor FROM indicator_source_guard")
            )
        )
        .mappings()
        .one()
    )


async def blocked_by(observer: AsyncConnection, waiter: int, holder: int) -> None:
    async with asyncio.timeout(2):
        while True:
            blocked: bool = (
                await observer.execute(
                    text("SELECT :holder=ANY(pg_blocking_pids(:waiter))"),
                    {"holder": holder, "waiter": waiter},
                )
            ).scalar_one()
            if blocked:
                return
            await asyncio.sleep(0.005)


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("leaf", [False, True])
@pytest.mark.parametrize("across_partitions", [False, True])
@pytest.mark.parametrize("operation", ["upsert", "cleanup"])
async def test_scoped_f09_contender_waits_before_row_locks(
    md: AsyncEngine,
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    leaf: bool,
    across_partitions: bool,
    operation: str,
) -> None:
    now = datetime.now(UTC)
    boundary = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = (
        boundary - timedelta(minutes=2) if across_partitions else boundary + timedelta(minutes=2)
    )
    bars = tuple(candle_at(start + timedelta(minutes=i), now) for i in range(4))
    claim = await claim_window(api_engine, md, CandleWindow(start, bars[-1].end_at))
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await write_candles(s, claim, bars, now)
    pids: list[int] = []
    started = asyncio.Event()

    async def contender() -> None:
        async with market_data_session(md) as s:
            pids.append((await s.execute("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            if operation == "cleanup":
                await cleanup(s)
            else:
                await begin_source_write(s)
                await write_candles(s, claim, bars, now)

    task: asyncio.Task[None] | None = None
    try:
        async with migrator_engine.connect() as observer:
            async with market_data_session(md) as holder:
                await begin_source_write(holder)
                holder_pid = (await holder.execute("SELECT pg_backend_pid()")).scalar_one()
                tables = (
                    sorted({f"market_candles_{bar.open_at:%Y%m}" for bar in bars})
                    if leaf
                    else ["market_candles"]
                )
                for table in tables:
                    await holder.execute(f"SELECT open_at FROM {table} ORDER BY open_at FOR UPDATE")
                    await holder.execute(f"UPDATE {table} SET last_checked_at=last_checked_at")
                task = asyncio.create_task(contender())
                await started.wait()
                await blocked_by(observer, pids[0], holder_pid)
                # Scope takes every candle relation before waiting on the guard.
                locks: int = (
                    await observer.execute(
                        text("""SELECT count(*) FROM pg_locks
                  WHERE pid=:pid AND mode='RowExclusiveLock' AND granted
                  AND relation IN (SELECT relid FROM pg_partition_tree('market_candles'))"""),
                        {"pid": pids[0]},
                    )
                ).scalar_one()
                partitions: int = (
                    await observer.execute(
                        text("SELECT count(*) FROM pg_partition_tree('market_candles')")
                    )
                ).scalar_one()
                assert locks == partitions
            await asyncio.wait_for(task, 2)
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("leaf", [False, True])
async def test_old_preselect_before_guard_has_real_deadlock_cycle(
    md: AsyncEngine,
    migrator_engine: AsyncEngine,
    leaf: bool,
) -> None:
    bounds = values()
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute(INSERT, bounds)
    table = f"market_candles_{bounds['opened']:%Y%m}" if leaf else "market_candles"
    task: asyncio.Task[Any] | None = None
    try:
        async with md.connect() as old, md.connect() as new, migrator_engine.connect() as observer:
            for connection in (old, new):
                await connection.execute(text("SET LOCAL lock_timeout='3s'"))
                await connection.execute(text("SET LOCAL statement_timeout='4s'"))
            old_pid: int = (await old.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            new_pid: int = (await new.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            await old.execute(text(f"SELECT open_at FROM {table} FOR UPDATE"))
            await new.execute(text("SELECT begin_indicator_source_write()"))
            task = asyncio.create_task(new.execute(text(f"UPDATE {table} SET close=close")))
            await blocked_by(observer, new_pid, old_pid)
            # Keep real triggers enabled; the legacy preselect is what inverts the order.
            results = await asyncio.wait_for(
                asyncio.gather(
                    old.execute(text("SELECT begin_indicator_source_write()")),
                    task,
                    return_exceptions=True,
                ),
                5,
            )
            assert any(
                isinstance(r, DBAPIError) and getattr(r.orig, "sqlstate", None) == "40P01"
                for r in results
            )
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize(
    "role", [DatabaseRole.API, DatabaseRole.MARKET_DATA, DatabaseRole.INDICATOR_BUILDER]
)
async def test_scope_helper_privilege_matrix(role: DatabaseRole) -> None:
    engine = create_engine_for(role)
    try:
        async with engine.connect() as c:
            assert (await c.execute(text("SELECT count(*) FROM market_candles"))).scalar_one() == 0
        for helper in ("begin_indicator_source_write", "begin_indicator_source_maintenance"):
            async with engine.connect() as c:
                if role == DatabaseRole.MARKET_DATA and helper == "begin_indicator_source_write":
                    await c.execute(text(f"SELECT {helper}()"))
                else:
                    with pytest.raises(DBAPIError, match="permission denied"):
                        await c.execute(text(f"SELECT {helper}()"))
        async with engine.connect() as c:
            with pytest.raises(DBAPIError, match="permission denied"):
                await c.execute(
                    text(
                        "UPDATE indicator_source_guard SET "
                        "scope_owner_xid=pg_current_xact_id(),scope_kind='WRITE'"
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("operation", ["drop", "detach", "truncate"])
@pytest.mark.parametrize("holder_kind", ["reader", "writer"])
@pytest.mark.parametrize("timeout", [False, True])
async def test_maintenance_ddl_waits_for_relations_then_progresses_or_rolls_back(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
    md: AsyncEngine,
    operation: str,
    holder_kind: str,
    timeout: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    built = await run_attempt(builder_engine, uuid4())
    assert built.status is AttemptStatus.READY
    started = asyncio.Event()
    pids: list[int] = []

    async def maintain() -> None:
        with (
            pytest.raises(DBAPIError, match="lock timeout")
            if timeout
            else pytest.raises(RollbackMaintenanceError)
        ):
            async with migrator_engine.begin() as c:
                await c.execute(
                    text(
                        "SET LOCAL lock_timeout='200ms'"
                        if timeout
                        else "SET LOCAL lock_timeout='2s'"
                    )
                )
                pids.append((await c.execute(text("SELECT pg_backend_pid()"))).scalar_one())
                started.set()
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
                assert (
                    await c.execute(text("SELECT count(*) FROM indicator_heads"))
                ).scalar_one() == 0
                await c.execute(text(ddl(operation)))
                raise RollbackMaintenanceError()

    task: asyncio.Task[None] | None = None
    try:
        async with migrator_engine.connect() as observer:
            original = await source_state(observer)
            async with (md if holder_kind == "writer" else api_engine).begin() as holder:
                pid: int = (await holder.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                if holder_kind == "writer":
                    await holder.execute(text("SELECT begin_indicator_source_write()"))
                await holder.execute(text("SELECT count(*) FROM market_candles"))
                task = asyncio.create_task(maintain())
                await started.wait()
                await blocked_by(observer, pids[0], pid)
                assert (
                    await observer.execute(
                        text("""SELECT count(*) FROM pg_locks
                  WHERE pid=:pid AND relation='indicator_source_guard'::regclass
                    AND mode IN ('RowShareLock','RowExclusiveLock','ExclusiveLock')"""),
                        {"pid": pids[0]},
                    )
                ).scalar_one() == 0
                if timeout:
                    await task
            if not timeout:
                await asyncio.wait_for(task, 3)
            assert await source_state(observer) == original
            assert (
                await observer.execute(text("SELECT generation_id FROM indicator_heads"))
            ).scalar_one() == built.generation_id
            assert (
                await observer.execute(
                    text("SELECT count(*) FROM pg_partition_tree('market_candles')")
                )
            ).scalar_one() > 1
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("operation", ["drop", "detach", "truncate"])
@pytest.mark.parametrize("holder_kind", ["publisher", "gc"])
async def test_publisher_and_gc_never_query_candles_under_guard(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    operation: str,
    holder_kind: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    pids: list[int] = []
    relations_locked = asyncio.Event()

    async def maintain() -> None:
        with pytest.raises(RollbackMaintenanceError):
            async with migrator_engine.begin() as c:
                await c.execute(text("SET LOCAL lock_timeout='2s'"))
                pids.append((await c.execute(text("SELECT pg_backend_pid()"))).scalar_one())
                await c.execute(text("LOCK TABLE market_candles IN ACCESS EXCLUSIVE MODE"))
                relations_locked.set()
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
                await c.execute(text(ddl(operation)))
                raise RollbackMaintenanceError()

    task: asyncio.Task[None] | None = None
    try:
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            claim = await writer.claim(uuid4())
            assert claim is not None
            await scan_staging(builder_engine, writer, claim)
            if holder_kind == "gc":
                assert await writer.publish_ready(claim) == PublicationResult.READY
            async with migrator_engine.connect() as observer:
                original = await source_state(observer)
                # Same physical writer for publish; a normal builder session for GC.
                context = (
                    writer.transaction()
                    if holder_kind == "publisher"
                    else indicator_writer_session(builder_engine)
                )
                async with context as session:
                    await session.execute("SET LOCAL lock_timeout='200ms'")
                    pid = (await session.execute("SELECT pg_backend_pid()")).scalar_one()
                    # Acquire the guard through the real permitted typed entrypoint;
                    # builder deliberately has no direct FOR UPDATE privilege on it.
                    await session.execute("SELECT gc_indicator_data()")
                    task = asyncio.create_task(maintain())
                    await asyncio.wait_for(relations_locked.wait(), 2)
                    await blocked_by(observer, pids[0], pid)
                    if holder_kind == "publisher":
                        assert (
                            await publish(session, claim, numeric=False) == PublicationResult.READY
                        )
                    else:
                        await session.execute("SELECT gc_indicator_data()")
                    assert (
                        await observer.execute(
                            text("""SELECT count(*) FROM pg_locks l
                      JOIN pg_class c ON c.oid=l.relation WHERE l.pid=:pid
                      AND c.relname LIKE 'market_candles%'"""),
                            {"pid": pid},
                        )
                    ).scalar_one() == 0
                await asyncio.wait_for(task, 3)
                assert await source_state(observer) == original
                assert (
                    await observer.execute(text("SELECT generation_id FROM indicator_heads"))
                ).scalar_one() == claim.generation_id
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.usefixtures("active")
async def test_scope_helpers_have_no_public_execute(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(
                text("""SELECT count(*) FROM pg_proc p,
          LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
          WHERE p.oid IN ('begin_indicator_source_write()'::regprocedure,
            'begin_indicator_source_maintenance()'::regprocedure)
          AND a.grantee=0 AND a.privilege_type='EXECUTE'""")
            )
        ).scalar_one() == 0


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("failure", ["stale_claim", "expired_lease", "disconnect"])
async def test_failed_claim_or_disconnect_rolls_back_scope_and_reuses_pool(
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    md: AsyncEngine,
    failure: str,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA, pool_size=1, max_overflow=0)
    bounds = values()
    try:
        claim = await claim_window(
            api_engine, engine, CandleWindow(bounds["opened"], bounds["end"])
        )
        async with migrator_engine.connect() as c:
            original = (
                await c.execute(text("SELECT epoch,revision FROM indicator_source_guard"))
            ).one()
            journal: int = (
                await c.execute(text("SELECT count(*) FROM indicator_source_changes"))
            ).scalar_one()
        if failure == "expired_lease":
            async with migrator_engine.begin() as c:
                await c.execute(
                    text(
                        "UPDATE market_candle_demand SET "
                        "lease_until=clock_timestamp()-interval '1 second'"
                    )
                )
        expected = DatabaseUnavailableError if failure == "disconnect" else StaleClaimError
        with pytest.raises(expected):
            async with market_data_session(engine) as s:
                pid = (await s.execute("SELECT pg_backend_pid()")).scalar_one()
                await begin_source_write(s)
                await s.execute(INSERT, bounds)
                await s.execute("UPDATE market_candle_demand SET attemptcount=attemptcount+1")
                if failure != "disconnect":
                    from dataclasses import replace

                    invalid = replace(claim, token=uuid4()) if failure == "stale_claim" else claim
                    await write_candles(s, invalid, (), bounds["now"])
                else:
                    async with md.connect() as c:
                        terminated: bool = (
                            await c.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
                        ).scalar_one()
                        assert terminated
                    await s.execute("SELECT 1")
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(text("SELECT epoch,revision FROM indicator_source_guard"))
            ).one() == original
            remaining_journal: int = (
                await c.execute(text("SELECT count(*) FROM indicator_source_changes"))
            ).scalar_one()
            assert remaining_journal == journal
            assert (await c.execute(text("SELECT count(*) FROM market_candles"))).scalar_one() == 0
            assert (
                await c.execute(text("SELECT max(attemptcount) FROM market_candle_demand"))
            ).scalar_one() == 0
            assert (
                await c.execute(
                    text(
                        "SELECT count(*) FROM pg_locks WHERE pid=:pid "
                        "AND locktype IN ('relation','tuple','transactionid')"
                    ),
                    {"pid": pid},
                )
            ).scalar_one() == 0
        async with market_data_session(engine) as s:
            reused = (await s.execute("SELECT pg_backend_pid()")).scalar_one()
            assert (reused == pid) == (failure != "disconnect")
            await begin_source_write(s)
            await s.execute(INSERT, bounds)
    finally:
        await engine.dispose()
