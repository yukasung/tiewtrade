"""Isolated real-DB checks for the shared native three-minute schedule."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.util import load_python_file
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _snapshot
from tests.infra.execution_market.conftest import (
    _internal_database_template as _internal_database_template,
)
from tests.infra.execution_market.conftest import internal_database as internal_database
from tests.infra.execution_market.conftest import (
    internal_database_factory as internal_database_factory,
)
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_rollout import synthetic_heads
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_source import fence, valid, values
from tests.infra.market_data.test_chart_preview import market_data_engine as market_data_engine
from tiewtrade.core.timeframes import Timeframe, advance, align_floor, slot_count
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.source import begin_source_write

pytestmark = pytest.mark.usefixtures("internal_database", "prepared")


def migration() -> Any:
    return load_python_file(
        Path(__file__).resolve().parents[3] / "migrations/versions",
        "0066_three_minute_timeframe.py",
    )


def run_migration(connection: Connection, direction: str) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration(), direction)()


async def insert_candle(engine: AsyncEngine, timeframe: str, seconds: int = 180) -> None:
    async with market_data_session(engine) as session:
        await begin_source_write(session)
        await session.execute(
            """INSERT INTO market_candles(source,base,quote,timeframe,open_at,end_at,
              open,high,low,close,volume,finality,observed_at,fetch_started_at,
              last_checked_at,ingestion_generation)
            VALUES('primary_spot','BTC','USDT',:tf,:opened,:ended,
              100,101,99,100.000000000000000001,0.000000000000000001,'OPEN',
              clock_timestamp(),clock_timestamp(),clock_timestamp(),1)""",
            {
                "tf": timeframe,
                "opened": datetime(2026, 11, 7, tzinfo=UTC),
                "ended": datetime(2026, 11, 7, tzinfo=UTC) + timedelta(seconds=seconds),
            },
        )


async def test_all_python_and_sql_schedules_agree_under_actual_builder_role(
    builder_engine: AsyncEngine,
) -> None:
    moment = datetime(2024, 2, 29, 23, 59, 59, tzinfo=UTC)
    async with builder_engine.connect() as connection:
        for tf in Timeframe:
            opened = align_floor(moment, tf)
            ended = advance(opened, tf, 3)
            row = (
                await connection.execute(
                    text("""SELECT
              market_timeframe_floor(:tf,:moment),market_timeframe_advance(:tf,:opened,3),
              market_timeframe_slots(:tf,:opened,:ended)"""),
                    {"tf": tf.value, "moment": moment, "opened": opened, "ended": ended},
                )
            ).one()
            assert row == (opened, ended, slot_count(opened, ended, tf))
        assert len(Timeframe) == 9 and Timeframe.M3.value == "3m"


@pytest.mark.parametrize("timeframe,seconds", [("3m", 180), ("3m", 60), ("2m", 120)])
async def test_actual_market_writer_enforces_native_three_minute_constraints(
    market_data_engine: AsyncEngine,
    timeframe: str,
    seconds: int,
) -> None:
    if (timeframe, seconds) == ("3m", 180):
        await insert_candle(market_data_engine, timeframe, seconds)
        async with market_data_session(market_data_engine) as session:
            row = (
                await session.execute("SELECT close::text,volume::text FROM market_candles")
            ).one()
            assert row == ("100.000000000000000001", "0.000000000000000001")
    else:
        from tiewtrade.infra.db.errors import InfraError

        with pytest.raises(InfraError):
            await insert_candle(market_data_engine, timeframe, seconds)


async def test_populated_empty_three_minute_downgrade_roundtrip_preserves_schema_and_facts(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    # Populate the actual prior schema, not a source already invalidated by downgrade.
    async with migrator_engine.begin() as connection:
        await connection.run_sync(lambda sync: run_migration(sync, "downgrade"))
    await insert_candle(market_data_engine, "1m", 60)
    await synthetic_heads(
        migrator_engine, timeframes=tuple(tf for tf in Timeframe if tf is not Timeframe.M3)
    )
    before = await _snapshot(migrator_engine)
    async with migrator_engine.begin() as connection:
        state_tables = (
            "indicator_source_changes",
            "indicator_build_jobs",
            "indicator_checkpoints",
        )
        state = {
            table: (
                await connection.execute(
                    text(
                        f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text"
                    )
                )
            ).all()
            for table in state_tables
        }
        guard: UUID = (
            await connection.execute(text("SELECT epoch FROM indicator_source_guard WHERE id=1"))
        ).scalar_one()
        generations = (
            await connection.execute(
                text("SELECT to_jsonb(g)-'status' FROM indicator_generations g ORDER BY id")
            )
        ).all()
        facts = (
            await connection.execute(text("SELECT row_to_json(c)::text FROM market_candles c"))
        ).all()
        functions = (
            await connection.execute(
                text("""SELECT oid::regprocedure::text,
          proowner,proacl,prosecdef,proconfig,prosrc FROM pg_proc
          WHERE pronamespace='public'::regnamespace ORDER BY oid""")
            )
        ).all()
        await connection.run_sync(lambda sync: run_migration(sync, "upgrade"))
        assert (
            await connection.execute(
                text("SELECT market_timeframe_advance('3m','2026-11-07 UTC'::timestamptz,1)")
            )
        ).scalar_one() == datetime(2026, 11, 7, 0, 3, tzinfo=UTC)
        await connection.run_sync(lambda sync: run_migration(sync, "downgrade"))
        assert (
            await connection.execute(text("SELECT count(*) FROM indicator_heads"))
        ).scalar_one() == 0
        assert (
            await connection.execute(
                text("SELECT count(*) FROM indicator_generations WHERE status<>'EXPIRED'")
            )
        ).scalar_one() == 0
        assert (
            await connection.execute(
                text("SELECT to_jsonb(g)-'status' FROM indicator_generations g ORDER BY id")
            )
        ).all() == generations
        changed = (
            await connection.execute(
                text(
                    "SELECT epoch,revision,journal_floor,scope_kind "
                    "FROM indicator_source_guard WHERE id=1"
                )
            )
        ).one()
        assert changed[0] != guard
        assert changed[1:] == (0, 0, "MAINTENANCE")
        for table in state_tables:
            assert (
                await connection.execute(
                    text(
                        f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text"
                    )
                )
            ).all() == state[table]
        assert (
            await connection.execute(text("SELECT row_to_json(c)::text FROM market_candles c"))
        ).all() == facts
        assert (
            await connection.execute(
                text("""SELECT oid::regprocedure::text,
          proowner,proacl,prosecdef,proconfig,prosrc FROM pg_proc
          WHERE pronamespace='public'::regnamespace ORDER BY oid""")
            )
        ).all() == functions
    assert await _snapshot(migrator_engine) == before


@pytest.mark.parametrize("state", ["candle", "demand", "metadata", "readiness", "jobs"])
async def test_downgrade_refuses_three_minute_state_atomically(
    migrator_engine: AsyncEngine,
    market_data_engine: AsyncEngine,
    state: str,
) -> None:
    if state == "candle":
        await insert_candle(market_data_engine, "3m")
    else:
        async with migrator_engine.begin() as connection:
            if state == "demand":
                await connection.execute(
                    text("""INSERT INTO market_candle_demand
                  (source,base,quote,timeframe,desired_start,desired_end,requested_at)
                  VALUES('primary_spot','BTC','USDT','3m','2026-11-07 UTC',
                    '2026-11-07 00:03 UTC',clock_timestamp())""")
                )
            elif state == "metadata":
                await connection.execute(
                    text("""UPDATE market_candle_feed_state
                  SET metadata='{"BTC/USDT/3m":"2026-11-07T00:00:00+00:00"}'::jsonb""")
                )
            elif state == "readiness":
                await connection.execute(
                    text("""INSERT INTO supported_symbol_timeframe_readiness
                  (base,quote,catalog_revision,timeframe) VALUES('BTC','USDT',1,'3m')""")
                )
            else:
                await connection.execute(
                    text("UPDATE indicator_rollout_control SET mode='PREPARING'")
                )
                await connection.execute(text("SELECT seed_indicator_build_jobs()"))
    before = await _snapshot(migrator_engine)
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            with pytest.raises(RuntimeError, match="THREE_MINUTE_DOWNGRADE_NOT_DRAINED"):
                await connection.run_sync(lambda sync: run_migration(sync, "downgrade"))
        finally:
            await transaction.rollback()
    assert await _snapshot(migrator_engine) == before


async def test_seed_and_fairness_cover_all_eighteen_series_without_duplicate_claims(
    migrator_engine: AsyncEngine,
    builder_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as connection:
        await connection.execute(text("UPDATE indicator_rollout_control SET mode='PREPARING'"))
        assert (
            await connection.execute(text("SELECT seed_indicator_build_jobs()"))
        ).scalar_one() == 18
        assert (
            await connection.execute(text("SELECT seed_indicator_build_jobs()"))
        ).scalar_one() == 0
    selected: set[tuple[str, Timeframe]] = set()
    for _ in range(18):
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            claim = await writer.claim(uuid4())
            assert claim is not None
            key = (claim.base, claim.timeframe)
            assert key not in selected
            selected.add(key)
            await writer.finish(AttemptOutcome.OPERATIONAL)
    assert selected == {(base, tf) for base in ("BTC", "ETH") for tf in Timeframe}


async def test_downgrade_lock_waits_for_concurrent_three_minute_insert_then_refuses(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as writer:
        tx = await writer.begin()
        await writer.execute(
            text("""INSERT INTO market_candle_demand
          (source,base,quote,timeframe,desired_start,desired_end,requested_at)
          VALUES('primary_spot','BTC','USDT','3m','2026-11-07 UTC',
            '2026-11-07 00:03 UTC',clock_timestamp())""")
        )
        started = asyncio.Event()

        async def downgrade() -> None:
            async with migrator_engine.begin() as connection:
                started.set()
                await connection.run_sync(lambda sync: run_migration(sync, "downgrade"))

        task = asyncio.create_task(downgrade())
        try:
            await started.wait()
            await asyncio.sleep(0.05)
            assert not task.done()
            await tx.commit()
            with pytest.raises(RuntimeError, match="THREE_MINUTE_DOWNGRADE_NOT_DRAINED"):
                await asyncio.wait_for(task, 3)
        finally:
            if tx.is_active:
                await tx.rollback()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_maintenance_ddl_failure_rolls_back_facts_heads_and_source_fence(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await insert_candle(market_data_engine, "1m", 60)
    await synthetic_heads(migrator_engine, timeframes=(Timeframe.M1,))
    tables = (
        "market_candles",
        "indicator_source_guard",
        "indicator_source_changes",
        "indicator_heads",
        "indicator_generations",
        "indicator_build_jobs",
        "indicator_checkpoints",
    )

    async def snapshot() -> dict[str, Any]:
        async with migrator_engine.connect() as connection:
            return {
                table: (
                    await connection.execute(
                        text(f"SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text")
                    )
                ).all()
                for table in tables
            }

    before = await snapshot()
    schema = await _snapshot(migrator_engine)
    module = migration()
    original = module._checks

    def fail_after_checks(adding: bool) -> None:
        original(adding)
        raise RuntimeError("INJECTED_DDL_FAILURE")

    monkeypatch.setattr(module, "_checks", fail_after_checks)
    with pytest.raises(RuntimeError, match="INJECTED_DDL_FAILURE"):
        async with migrator_engine.begin() as connection:

            def apply(sync: Connection) -> None:
                with Operations.context(MigrationContext.configure(sync)):
                    module.downgrade()

            await connection.run_sync(apply)
    assert await snapshot() == before
    assert await _snapshot(migrator_engine) == schema


async def test_migration_rejects_claimed_writer_then_invalidates_old_source_fence(
    migrator_engine: AsyncEngine,
    builder_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as connection:
        await connection.run_sync(lambda sync: run_migration(sync, "downgrade"))
        await connection.execute(text("SELECT seed_indicator_build_jobs()"))
    original = await fence(builder_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        assert await writer.claim(uuid4()) is not None
        # A live pinned writer owns table locks until it exits. Fail closed on a
        # bounded lock timeout rather than modifying any of its durable state.
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError):
            async with migrator_engine.begin() as connection:
                await connection.execute(text("SET LOCAL lock_timeout='100ms'"))
                await connection.run_sync(lambda sync: run_migration(sync, "upgrade"))
        await writer.finish(AttemptOutcome.OPERATIONAL)
    async with migrator_engine.begin() as connection:
        await connection.run_sync(lambda sync: run_migration(sync, "upgrade"))
    assert (await fence(builder_engine)).epoch != original.epoch
    assert not await valid(builder_engine, original, values())


@pytest.mark.parametrize("served_before_upgrade", [15, 16])
async def test_upgrade_preserves_old_cursor_and_completes_fair_round_before_wrapping(
    migrator_engine: AsyncEngine,
    builder_engine: AsyncEngine,
    served_before_upgrade: int,
) -> None:
    async with migrator_engine.begin() as connection:
        await connection.run_sync(lambda sync: run_migration(sync, "downgrade"))
        assert (
            await connection.execute(text("SELECT seed_indicator_build_jobs()"))
        ).scalar_one() == 16
    served: set[tuple[str, Timeframe]] = set()
    for _ in range(served_before_upgrade):
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            claim = await writer.claim(uuid4())
            assert claim is not None
            served.add((claim.base, claim.timeframe))
            await writer.finish(AttemptOutcome.SOURCE_CHANGED)
    before = await slot(migrator_engine)
    assert before["dispatch_cursor"] == served_before_upgrade - 1
    job_rows = text("SELECT to_jsonb(j) FROM indicator_build_jobs j ORDER BY id")
    async with migrator_engine.begin() as connection:
        jobs = (await connection.execute(job_rows)).all()
        await connection.run_sync(lambda sync: run_migration(sync, "upgrade"))
        assert (await connection.execute(job_rows)).all() == jobs
    assert await slot(migrator_engine) == before
    async with migrator_engine.begin() as connection:
        assert (
            await connection.execute(text("SELECT seed_indicator_build_jobs()"))
        ).scalar_one() == 2
        # Equal deadlines exercise the ring tie-breaker, not priority ordering.
        await connection.execute(
            text(
                "UPDATE indicator_build_jobs "
                "SET retry_not_before=clock_timestamp()-interval '1 second',"
                "availability_deadline=statement_timestamp()+interval '600 seconds'"
            )
        )
    all_series = [(base, tf) for base in ("BTC", "ETH") for tf in Timeframe]
    series_indices = {series: index for index, series in enumerate(all_series)}
    assert len(series_indices) == 18
    remaining = set(all_series) - served
    current_cursor = before["dispatch_cursor"]
    for expected_round, candidates in (
        (before["dispatch_round"], remaining),
        (before["dispatch_round"] + 1, set(all_series)),
    ):
        expected = sorted(
            candidates, key=lambda key: (series_indices[key] - current_cursor - 1) % len(all_series)
        )
        selected = []
        for key in expected:
            async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
                assert writer is not None
                claim = await writer.claim(uuid4())
                assert claim is not None
                actual = (claim.base, claim.timeframe)
                assert actual == key
                assert claim.dispatch_round == expected_round
                assert actual not in selected
                selected.append(actual)
                await writer.finish(AttemptOutcome.SOURCE_CHANGED)
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE indicator_build_jobs "
                        "SET retry_not_before=clock_timestamp()-interval '1 second'"
                    )
                )
        assert set(selected) == candidates
        current_cursor = series_indices[selected[-1]]
    assert (await slot(migrator_engine))["dispatch_round"] == before["dispatch_round"] + 1
