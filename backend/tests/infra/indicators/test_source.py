"""Real PostgreSQL source proof, supported lock order, and actual role boundaries."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.services.market_data.test_ingestion import FullSource
from tiewtrade.core.market_data import Timeframe, align_floor
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import DatabaseTimeoutError, NotPermittedError, SourceWriteScopeError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.source import (
    PROOF_SQL,
    SourceFence,
    begin_source_write,
    proof_parameters,
)
from tiewtrade.services.market_data.ingestion import run_round
from tiewtrade.venues.candles import CandlePage
from tiewtrade.venues.symbols import Symbol

INSERT = """INSERT INTO market_candles
 (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
 observed_at,fetch_started_at,last_checked_at,ingestion_generation)
 VALUES('primary_spot','BTC','USDT','1m',:opened,:end,1,2,1,1,0,'UNCONFIRMED',:now,:now,:now,1)
 ON CONFLICT(source,base,quote,timeframe,open_at) DO UPDATE SET close=excluded.close"""


@pytest_asyncio.fixture
async def md() -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def builder() -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(DatabaseRole.INDICATOR_BUILDER, pool_size=2, max_overflow=0)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def active(migrator_engine: AsyncEngine) -> AsyncIterator[None]:
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT activate_indicator_source_proof()"))
        await c.execute(text("DELETE FROM market_candles"))
        await c.execute(text("DELETE FROM market_candle_demand"))
    try:
        yield
    finally:
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text("DELETE FROM market_candles"))
            await c.execute(
                text("""UPDATE indicator_rollout_control SET
                source_proof_state='PENDING',mode='LEGACY' WHERE id=1""")
            )
            await c.execute(
                text("""DO $$ DECLARE p record; BEGIN
              FOR p IN SELECT relid FROM pg_partition_tree('market_candles'::regclass) LOOP
                EXECUTE format('DROP TRIGGER IF EXISTS indicator_source_statement ON %s',p.relid);
              END LOOP; END $$""")
            )
            await c.execute(text("DROP TRIGGER indicator_source_rows ON market_candles"))
            await c.execute(text("DELETE FROM indicator_source_changes"))
            await c.execute(text("DELETE FROM market_candle_demand"))


def values(offset: int = 0) -> dict[str, datetime]:
    now = datetime.now(UTC)
    opened = align_floor(now, Timeframe.M1) - timedelta(minutes=2 - offset)
    return {"opened": opened, "end": opened + timedelta(minutes=1), "now": now}


async def fence(builder: AsyncEngine) -> SourceFence:
    async with indicator_source_session(builder) as s:
        row = (
            (await s.execute("SELECT epoch,revision FROM indicator_source_guard")).mappings().one()
        )
        return SourceFence(row["epoch"], row["revision"])


async def valid(builder: AsyncEngine, version: SourceFence, bounds: dict[str, datetime]) -> bool:
    async with indicator_source_session(builder) as s:
        params = proof_parameters(
            version,
            source="primary_spot",
            base="BTC",
            quote="USDT",
            timeframe="1m",
            start=bounds["opened"],
            end=bounds["end"],
        )
        return bool((await s.execute(PROOF_SQL, params)).scalar_one())


@pytest.mark.usefixtures("active")
async def test_missing_or_spoofed_scope_and_transaction_reuse(md: AsyncEngine) -> None:
    for spoof in (False, True):
        with pytest.raises(SourceWriteScopeError):
            async with market_data_session(md) as s:
                if spoof:
                    await s.execute("SELECT set_config('tiewtrade.source_scope','WRITE',true)")
                await s.execute(INSERT, values())
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute(INSERT, values())
    with pytest.raises(SourceWriteScopeError):
        async with market_data_session(md) as s:
            await s.execute(INSERT, values())


@pytest.mark.usefixtures("active")
async def test_guarded_proof_does_not_lock_candles_while_maintenance_waits(
    migrator_engine: AsyncEngine,
    builder: AsyncEngine,
) -> None:
    bounds = values()
    original = await fence(builder)
    relations_locked = asyncio.Event()
    maintenance_pid: list[int] = []

    async def maintain() -> None:
        async with migrator_engine.begin() as c:
            maintenance_pid.append((await c.execute(text("SELECT pg_backend_pid()"))).scalar_one())
            await c.execute(text("LOCK TABLE market_candles IN ACCESS EXCLUSIVE MODE"))
            relations_locked.set()
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))

    task: asyncio.Task[None] | None = None
    try:
        async with asyncio.timeout(5):
            async with migrator_engine.begin() as publisher:
                pid: int = (await publisher.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                await publisher.execute(text("SELECT id FROM indicator_source_guard FOR UPDATE"))
                task = asyncio.create_task(maintain())
                await relations_locked.wait()
                # Observe the real guard wait, not a timing assumption.
                while not bool(
                    (
                        await publisher.execute(
                            text("SELECT :holder=ANY(pg_blocking_pids(:waiter))"),
                            {"holder": pid, "waiter": maintenance_pid[0]},
                        )
                    ).scalar_one()
                ):
                    await asyncio.sleep(0.01)
                params = proof_parameters(
                    original,
                    source="primary_spot",
                    base="BTC",
                    quote="USDT",
                    timeframe="1m",
                    start=bounds["opened"],
                    end=bounds["end"],
                )
                await publisher.execute(text("SET LOCAL lock_timeout='200ms'"))
                assert bool((await publisher.execute(text(PROOF_SQL), params)).scalar_one())
                assert not bool(
                    (
                        await publisher.execute(
                            text("""SELECT EXISTS(
                    SELECT 1 FROM pg_locks l JOIN pg_class c ON c.oid=l.relation
                    WHERE l.pid=pg_backend_pid() AND c.relname LIKE 'market_candles%')""")
                        )
                    ).scalar_one()
                )
                # Negative control: the old traversal blocks in this exact state.
                with pytest.raises(DBAPIError, match="lock timeout"):
                    async with publisher.begin_nested():
                        await publisher.execute(
                            text(
                                "SELECT count(*) FROM pg_partition_tree('market_candles'::regclass)"
                            )
                        )
            await task
        assert not await valid(builder, original, bounds)
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.usefixtures("active")
async def test_committed_changes_rollback_metadata_and_aba(
    md: AsyncEngine, builder: AsyncEngine
) -> None:
    bounds = values()
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute(INSERT, bounds)
    original = await fence(builder)
    assert await valid(builder, original, bounds)
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute("UPDATE market_candles SET last_checked_at=clock_timestamp()")
    assert await valid(builder, original, bounds)
    with pytest.raises(RuntimeError):
        async with market_data_session(md) as s:
            await begin_source_write(s)
            await s.execute("UPDATE market_candles SET close=2")
            raise RuntimeError("rollback")
    assert await valid(builder, original, bounds)
    for price in (2, 1):
        async with market_data_session(md) as s:
            await begin_source_write(s)
            await s.execute("UPDATE market_candles SET close=:price", {"price": price})
    assert not await valid(builder, original, bounds)


@pytest.mark.usefixtures("active")
async def test_append_outside_window_and_missing_journal(
    md: AsyncEngine, builder: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    bounds = values()
    original = await fence(builder)
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute(INSERT, values(1))
    assert await valid(builder, original, bounds)
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_source_guard SET journal_floor=revision"))
    assert not await valid(builder, original, bounds)


@pytest.mark.usefixtures("active")
async def test_read_snapshot_with_delayed_writer_and_scope_lock_order(
    md: AsyncEngine, builder: AsyncEngine
) -> None:
    bounds = values()
    async with indicator_source_session(builder) as reader:
        row = (
            (await reader.execute("SELECT epoch,revision FROM indicator_source_guard"))
            .mappings()
            .one()
        )
        original = SourceFence(row["epoch"], row["revision"])
        async with market_data_session(md) as writer:
            await begin_source_write(writer)
            await writer.execute(INSERT, bounds)
            params = proof_parameters(
                original,
                source="primary_spot",
                base="BTC",
                quote="USDT",
                timeframe="1m",
                start=bounds["opened"],
                end=bounds["end"],
            )
            assert (await reader.execute(PROOF_SQL, params)).scalar_one()
        assert (await reader.execute(PROOF_SQL, params)).scalar_one()
    assert not await valid(builder, original, bounds)
    started = asyncio.Event()

    async def contender() -> None:
        started.set()
        async with market_data_session(md) as s:
            await begin_source_write(s)
            await s.execute(INSERT, bounds)

    async with market_data_session(md) as holder:
        await begin_source_write(holder)
        await holder.execute("SELECT open_at FROM market_candles FOR UPDATE")
        task = asyncio.create_task(contender())
        await started.wait()
        await asyncio.sleep(0.05)
        assert not task.done()
    await asyncio.wait_for(task, 2)


@pytest.mark.usefixtures("active")
async def test_partitions_ddl_scope_leaf_dml_and_rollback(
    md: AsyncEngine, migrator_engine: AsyncEngine, builder: AsyncEngine
) -> None:
    bounds = values()
    name = f"market_candles_{bounds['opened']:%Y%m}"
    with pytest.raises(Exception, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
        async with migrator_engine.begin() as c:
            await c.execute(text(f"ALTER TABLE market_candles DETACH PARTITION {name}"))
    with pytest.raises(Exception, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
        async with migrator_engine.begin() as c:
            await c.execute(text(f"DROP TABLE {name}"))
    with pytest.raises(SourceWriteScopeError):
        async with market_data_session(md) as s:
            await s.execute(INSERT.replace("market_candles", name), bounds)
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute(INSERT.replace("market_candles", name), bounds)
    original = await fence(builder)
    with pytest.raises(RuntimeError):
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text(f"ALTER TABLE market_candles DETACH PARTITION {name}"))
            raise RuntimeError("rollback")
    assert await valid(builder, original, bounds)
    with pytest.raises(NotPermittedError):
        async with market_data_session(md) as s:
            await begin_source_write(s)
            await s.execute("TRUNCATE market_candles")


@pytest.mark.usefixtures("active")
async def test_maintenance_upgrade_rejected_before_relation_lock(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as c:
        with pytest.raises(Exception, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
            await c.execute(text("SELECT begin_indicator_source_write()"))
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))


async def test_builder_and_api_actual_privileges(
    builder: AsyncEngine, api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    async with indicator_source_session(builder) as s:
        assert (await s.execute("SHOW transaction_read_only")).scalar_one() == "on"
        assert (await s.execute("SHOW transaction_isolation")).scalar_one() == "repeatable read"
        assert (await s.execute("SELECT count(*) FROM market_candles")).scalar_one() >= 0
    for engine in (api_engine, builder):
        for table in ("indicator_generations", "indicator_checkpoints", "indicator_build_jobs"):
            async with engine.connect() as c:
                with pytest.raises(DBAPIError, match="permission denied"):
                    await c.execute(
                        text(
                            f"UPDATE {table} SET id=id"
                            if table != "indicator_checkpoints"
                            else f"DELETE FROM {table}"
                        )
                    )
        async with engine.connect() as c:
            with pytest.raises(DBAPIError, match="permission denied"):
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
    for table in ("users", "sessions", "user_api_keys", "market_candle_demand"):
        async with builder.connect() as c:
            with pytest.raises(DBAPIError, match="permission denied"):
                await c.execute(text(f"SELECT * FROM {table}"))
    async with migrator_engine.connect() as c:
        assert not bool(
            (
                await c.execute(
                    text("""SELECT rolsuper OR rolbypassrls FROM pg_roles
            WHERE rolname='tiewtrade_indicator_builder'""")
                )
            ).scalar_one()
        )
    async with api_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_ready_generations"))
        ).scalar_one() == 0


@pytest.mark.usefixtures("active")
async def test_future_partition_and_truncate_require_maintenance(
    migrator_engine: AsyncEngine, md: AsyncEngine, builder: AsyncEngine
) -> None:
    name = "test_indicator_source_2035"
    original = await fence(builder)
    with pytest.raises(DBAPIError, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
        async with migrator_engine.begin() as c:
            await c.execute(
                text(f"""CREATE TABLE {name} PARTITION OF market_candles
                FOR VALUES FROM ('2035-01-01') TO ('2035-02-01')""")
            )
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        await c.execute(
            text(f"""CREATE TABLE {name} PARTITION OF market_candles
            FOR VALUES FROM ('2035-01-01') TO ('2035-02-01')""")
        )
        await c.execute(
            text(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {name} TO tiewtrade_market_data")
        )
    try:
        assert (await fence(builder)).epoch != original.epoch
        async with migrator_engine.begin() as c:
            assert (
                await c.execute(
                    text("""SELECT count(*) FROM pg_trigger WHERE
                tgrelid=CAST(:name AS regclass)
                AND tgname IN ('indicator_source_statement','indicator_source_rows')"""),
                    {"name": name},
                )
            ).scalar_one() == 2
        future = datetime(2035, 1, 1, tzinfo=UTC)
        payload = {"opened": future, "end": future + timedelta(minutes=1), "now": future}
        with pytest.raises(SourceWriteScopeError):
            async with market_data_session(md) as s:
                await s.execute(INSERT.replace("market_candles", name), payload)
        async with market_data_session(md) as s:
            await begin_source_write(s)
            await s.execute(INSERT.replace("market_candles", name), payload)
        with pytest.raises(DBAPIError, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
            async with migrator_engine.begin() as c:
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(text("TRUNCATE market_candles"))
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text("TRUNCATE market_candles"))
    finally:
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text(f"DROP TABLE {name}"))


@pytest.mark.usefixtures("active")
async def test_real_ingestion_acquires_scope_before_claim_and_candle_locks(md: AsyncEngine) -> None:
    trace: list[str] = []

    def begin(conn: Any) -> None:
        trace.append("BEGIN")

    def commit(conn: Any) -> None:
        trace.append("COMMIT")

    class ObservedSource(FullSource):
        async def fetch_candles(
            self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
        ) -> CandlePage:
            assert trace.count("BEGIN") == trace.count("COMMIT")
            trace.append("VENUE")
            return await super().fetch_candles(symbol, timeframe, start, end, limit)

    def before_execute(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        trace.append(statement)

    event.listen(md.sync_engine, "before_cursor_execute", before_execute)
    event.listen(md.sync_engine, "begin", begin)
    event.listen(md.sync_engine, "commit", commit)
    try:
        result = await run_round(md, ObservedSource(), "source-proof-test", datetime.now(UTC))
    finally:
        event.remove(md.sync_engine, "before_cursor_execute", before_execute)
        event.remove(md.sync_engine, "begin", begin)
        event.remove(md.sync_engine, "commit", commit)
    assert result.stored > 0
    write = trace[trace.index("VENUE") + 1 :]
    scope = next(i for i, sql in enumerate(write) if "begin_indicator_source_write" in sql)
    claim = next(i for i, sql in enumerate(write) if "FOR UPDATE" in sql)
    upsert = next(i for i, sql in enumerate(write) if "INSERT INTO market_candles" in sql)
    assert scope < claim < upsert
    seeded = next(i for i, sql in enumerate(trace) if "INSERT INTO market_candle_demand" in sql)
    cleanup_scope = next(i for i, sql in enumerate(trace) if "begin_indicator_source_write" in sql)
    assert "COMMIT" in trace[seeded:cleanup_scope]
    assert "BEGIN" in trace[trace.index("COMMIT", seeded) + 1 : cleanup_scope]
    deletion = next(i for i, sql in enumerate(trace) if "DELETE FROM market_candles" in sql)
    assert cleanup_scope < deletion < trace.index("VENUE")
    # Each write transaction, not only the first round's first upsert.
    for index, sql in enumerate(trace):
        if "INSERT INTO market_candles" in sql:
            start = max(i for i in range(index) if trace[i] == "BEGIN")
            transaction = trace[start:index]
            scope = next(
                i for i, item in enumerate(transaction) if "begin_indicator_source_write" in item
            )
            row_lock = next(i for i, item in enumerate(transaction) if "FOR UPDATE" in item)
            assert scope < row_lock


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize(
    ("leaf", "trigger", "operation"),
    [
        (leaf, trigger, operation)
        for leaf in (False, True)
        for trigger in ("indicator_source_rows", "indicator_source_statement")
        for operation in ("drop", "disable", "replace")
        if not (leaf and trigger == "indicator_source_rows" and operation != "disable")
    ],
)
async def test_trigger_damage_requires_maintenance_and_reactivation(
    migrator_engine: AsyncEngine,
    builder: AsyncEngine,
    md: AsyncEngine,
    leaf: bool,
    trigger: str,
    operation: str,
) -> None:
    bounds = values()
    relation = f"market_candles_{bounds['opened']:%Y%m}" if leaf else "market_candles"
    # PostgreSQL itself forbids dropping/replacing a cloned row trigger directly.
    if operation == "replace":
        level = "ROW" if trigger == "indicator_source_rows" else "STATEMENT"
        statement = (
            f"CREATE OR REPLACE TRIGGER {trigger} AFTER INSERT ON {relation} "
            f"FOR EACH {level} EXECUTE FUNCTION indicator_source_statement_guard()"
        )
    else:
        statement = (
            f"DROP TRIGGER {trigger} ON {relation}"
            if operation == "drop"
            else f"ALTER TABLE {relation} DISABLE TRIGGER {trigger}"
        )
    original = await fence(builder)
    with pytest.raises(DBAPIError, match="SOURCE_MAINTENANCE_SCOPE_REQUIRED"):
        async with migrator_engine.begin() as c:
            await c.execute(text(statement))
    assert await valid(builder, original, bounds)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        await c.execute(text(statement))
        assert (
            await c.execute(text("SELECT source_proof_state FROM indicator_rollout_control"))
        ).scalar_one() == "PENDING"
    assert not await valid(builder, original, bounds)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT activate_indicator_source_proof()"))
    repaired = await fence(builder)
    assert repaired.epoch != original.epoch
    assert not await valid(builder, original, bounds)
    assert await valid(builder, repaired, bounds)
    # Healthy replay preserves the epoch, and real runtime writes are journaled.
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT activate_indicator_source_proof()"))
    assert await fence(builder) == repaired
    async with market_data_session(md) as s:
        await begin_source_write(s)
        await s.execute(INSERT, bounds)
    assert not await valid(builder, repaired, bounds)


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("blocker", ["guard", "relation"])
async def test_source_scope_timeout_releases_locks_and_reuses_connection(
    migrator_engine: AsyncEngine,
    blocker: str,
) -> None:
    writer = create_engine_for(DatabaseRole.MARKET_DATA, pool_size=1, max_overflow=0)
    try:
        async with market_data_session(writer) as s:
            pid = (await s.execute("SELECT pg_backend_pid()")).scalar_one()
            previous_lock = (await s.execute("SHOW lock_timeout")).scalar_one()
            previous_query = (await s.execute("SHOW statement_timeout")).scalar_one()
        async with migrator_engine.begin() as holder:
            await holder.execute(
                text(
                    "SELECT id FROM indicator_source_guard FOR UPDATE"
                    if blocker == "guard"
                    else "LOCK TABLE market_candles IN ACCESS EXCLUSIVE MODE"
                )
            )
            async with asyncio.timeout(2):
                with pytest.raises(DatabaseTimeoutError, match="55P03"):
                    async with market_data_session(writer) as s:
                        await begin_source_write(s)
            # Rollback has returned even while the blocker is still held.
            assert not bool(
                (
                    await holder.execute(
                        text("""SELECT EXISTS(SELECT 1 FROM pg_locks
                WHERE pid=:pid AND relation IN ('market_candles'::regclass,
                'indicator_source_guard'::regclass))"""),
                        {"pid": pid},
                    )
                ).scalar_one()
            )
        async with market_data_session(writer) as s:
            assert (await s.execute("SELECT pg_backend_pid()")).scalar_one() == pid
            assert (await s.execute("SHOW lock_timeout")).scalar_one() == previous_lock
            assert (await s.execute("SHOW statement_timeout")).scalar_one() == previous_query
            with pytest.raises(SourceWriteScopeError):
                await s.execute(INSERT, values())
        async with market_data_session(writer) as s:
            await begin_source_write(s)
            await s.execute(INSERT, values())
    finally:
        await writer.dispose()


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("cancel", [False, True])
async def test_source_timeout_or_cancel_rolls_back_candles_journal_and_metadata(
    md: AsyncEngine,
    builder: AsyncEngine,
    cancel: bool,
) -> None:
    bounds = values()
    original = await fence(builder)
    written = asyncio.Event()
    writer_pids: list[int] = []

    async def write() -> None:
        async with market_data_session(md) as s:
            writer_pids.append((await s.execute("SELECT pg_backend_pid()")).scalar_one())
            await begin_source_write(s)
            await s.execute(INSERT, bounds)
            await s.execute(
                """INSERT INTO market_candle_demand
                (source,base,quote,timeframe,desired_start,desired_end,requested_at)
                VALUES('primary_spot','BTC','USDT','1m',:opened,:end,:now)""",
                bounds,
            )
            written.set()
            if cancel:
                await asyncio.Event().wait()
            else:
                await s.execute("SELECT pg_sleep(5)")

    task = asyncio.create_task(write())
    async with asyncio.timeout(2):
        await written.wait()
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(DatabaseTimeoutError, match="57014"):
                await task
    assert await fence(builder) == original
    assert await valid(builder, original, bounds)
    with pytest.raises(SourceWriteScopeError):
        async with market_data_session(md) as s:
            assert (await s.execute("SELECT pg_backend_pid()")).scalar_one() == writer_pids[0]
            await s.execute(INSERT, bounds)
    async with market_data_session(md) as s:
        await begin_source_write(s)
        assert (await s.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
        assert (await s.execute("SELECT count(*) FROM market_candle_demand")).scalar_one() == 0


@pytest.mark.usefixtures("active")
async def test_cleanup_timeout_finishes_round_without_fetch(
    md: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    class NoFetch(FullSource):
        async def fetch_candles(
            self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
        ) -> CandlePage:
            raise AssertionError("cleanup contention must not consume source attempts")

    async with migrator_engine.begin() as holder:
        await holder.execute(text("SELECT id FROM indicator_source_guard FOR UPDATE"))
        async with asyncio.timeout(3):
            result = await run_round(md, NoFetch(), "blocked-cleanup", datetime.now(UTC))
        assert result.attempts == result.stored == 0
    # The next scheduled round can make progress without resetting anything.
    result = await run_round(md, FullSource(), "recovered-cleanup", datetime.now(UTC))
    assert result.stored > 0


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("block_failure_record", [False, True])
async def test_post_fetch_guard_timeout_preserves_attempt_and_backoff(
    md: AsyncEngine,
    migrator_engine: AsyncEngine,
    block_failure_record: bool,
) -> None:
    async with migrator_engine.begin() as holder:

        class BlockAfterFetch(FullSource):
            async def fetch_candles(
                self,
                symbol: Symbol,
                timeframe: Timeframe,
                start: datetime,
                end: datetime,
                limit: int,
            ) -> CandlePage:
                page = await super().fetch_candles(symbol, timeframe, start, end, limit)
                await holder.execute(text("SELECT id FROM indicator_source_guard FOR UPDATE"))
                if block_failure_record:
                    await holder.execute(
                        text("""SELECT base FROM market_candle_demand
                        WHERE base=:base AND timeframe=:timeframe FOR UPDATE"""),
                        {"base": symbol.base, "timeframe": timeframe.value},
                    )
                return page

        async with asyncio.timeout(5):
            result = await run_round(md, BlockAfterFetch(), "blocked-write", datetime.now(UTC))
        assert result.attempts == (1 if block_failure_record else 4)
        assert result.stored == 0
    async with market_data_session(md) as s:
        assert (await s.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
        rows = (
            (
                await s.execute("""SELECT status,attemptcount,fetch_unit_id,
            token IS NOT NULL AND lease_until>clock_timestamp() AS leased,
            next_attempt_at>clock_timestamp()+interval '20 seconds' AS deferred
            FROM market_candle_demand WHERE attemptcount>0""")
            )
            .mappings()
            .all()
        )
        assert len(rows) == result.attempts
        assert all(
            row["status"] == ("RUNNING" if block_failure_record else "PENDING")
            and row["attemptcount"] == 1
            and row["fetch_unit_id"] is not None
            and (row["leased"] if block_failure_record else row["deferred"])
            for row in rows
        )


@pytest.mark.usefixtures("active")
@pytest.mark.parametrize("damage", ["missing", "wrong_handler", "wrong_events", "disabled"])
async def test_stale_ready_flag_cannot_validate_damaged_catalog(
    migrator_engine: AsyncEngine,
    builder: AsyncEngine,
    damage: str,
) -> None:
    bounds = values()
    original = await fence(builder)
    async with migrator_engine.begin() as c:
        # Model an already damaged installation from the previous migration.
        await c.execute(text("UPDATE indicator_rollout_control SET source_proof_state='PENDING'"))
        await c.execute(text("DROP TRIGGER indicator_source_rows ON market_candles"))
        if damage != "missing":
            handler = (
                "indicator_source_statement_guard"
                if damage == "wrong_handler"
                else "indicator_source_row_journal"
            )
            events = "INSERT" if damage == "wrong_events" else "INSERT OR UPDATE OR DELETE"
            await c.execute(
                text(
                    f"CREATE TRIGGER indicator_source_rows AFTER {events} "
                    f"ON market_candles FOR EACH ROW EXECUTE FUNCTION {handler}()"
                )
            )
            if damage == "disabled":
                await c.execute(
                    text("ALTER TABLE market_candles DISABLE TRIGGER indicator_source_rows")
                )
        await c.execute(text("UPDATE indicator_rollout_control SET source_proof_state='READY'"))
    assert not await valid(builder, original, bounds)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT activate_indicator_source_proof()"))
    repaired = await fence(builder)
    assert repaired.epoch != original.epoch
    assert not await valid(builder, original, bounds)
    assert await valid(builder, repaired, bounds)
