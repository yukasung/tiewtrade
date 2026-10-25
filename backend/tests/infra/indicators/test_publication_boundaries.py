"""Fresh-ID publication completeness under the unchanged 500ms SQL budget."""

from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.util import load_python_file
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.db.errors import IndicatorBuildConfigurationError
from tiewtrade.infra.indicators.claims import AttemptOutcome, PublicationResult, publish
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import capture_snapshot, initialize


async def test_publication_migration_roundtrip(migrator_engine: AsyncEngine) -> None:
    migration = load_python_file(
        Path(__file__).resolve().parents[3] / "migrations/versions",
        "0039_indicator_publication_boundaries.py",
    )
    query = text("""SELECT pg_get_functiondef(oid),proowner,proacl::text,proconfig
      FROM pg_proc WHERE oid=
      'public.publish_indicator_generation(uuid,bigint,uuid,uuid,uuid,uuid,boolean)'::regprocedure""")
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            before = (await connection.execute(query)).one()

            def roundtrip(sync: Connection) -> None:
                with Operations.context(MigrationContext.configure(sync)):
                    migration.downgrade()
                    old = sync.execute(query).one()
                    assert old[0] == before[0].replace(migration._NEW, migration._OLD)
                    assert old[1:] == before[1:]
                    migration.upgrade()

            await connection.run_sync(roundtrip)
            assert (await connection.execute(query)).one() == before
        finally:
            await transaction.rollback()


@pytest.mark.parametrize("plan_mode", ["force_custom_plan", "force_generic_plan"])
@pytest.mark.parametrize(
    ("timeframe", "damage"),
    [(tf.value, None) for tf in Timeframe]
    + [("1m", fault) for fault in ("first", "interior", "end", "boundary", "count")],
)
async def test_fresh_checkpoint_boundaries(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    plan_mode: str,
    timeframe: str,
    damage: str | None,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("""UPDATE indicator_build_jobs SET status='FAILED_OPERATIONAL'
                  WHERE NOT(base='BTC' AND timeframe=:tf)"""),
                {"tf": timeframe},
            )
            # No statistics for the candidate about to be created; never ANALYZE it.
            await connection.execute(text("ANALYZE indicator_checkpoints"))
        claim = await writer.claim(uuid4())
        assert claim is not None
        async with indicator_source_session(builder_engine) as source:
            snapshot = await capture_snapshot(source, claim)
            await initialize(writer, claim, snapshot)
        # Privileged fixture supplies keys only: codec/parity is covered by scan tests.
        # The publication itself runs through the real builder identity and timeout.
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("""UPDATE indicator_generations SET
              dataset_revision=repeat('a',64),checkpoint_count=ceil(
                public.market_timeframe_slots(timeframe,calculation_start,calculation_end)
                /1000.0)::integer+1 WHERE id=:id"""),
                {"id": claim.generation_id},
            )
            await connection.execute(
                text("""INSERT INTO indicator_checkpoints
              SELECT g.id,least(public.market_timeframe_advance(g.timeframe,
                g.calculation_start,1000*n),g.calculation_end),'{}'::jsonb
              FROM indicator_generations g CROSS JOIN LATERAL
                generate_series(0,g.checkpoint_count-1) n WHERE g.id=:id"""),
                {"id": claim.generation_id},
            )
            if damage in ("first", "interior", "end", "boundary"):
                offset = {"first": 0, "interior": 1000, "end": 526000, "boundary": 1000}[damage]
                target = """least(public.market_timeframe_advance(g.timeframe,
                    g.calculation_start,:offset),g.calculation_end)"""
                statement = (
                    "UPDATE indicator_checkpoints cp SET next_open_at="
                    "cp.next_open_at+interval '1 minute' FROM indicator_generations g"
                    if damage == "boundary"
                    else "DELETE FROM indicator_checkpoints cp USING indicator_generations g"
                )
                await connection.execute(
                    text(
                        statement
                        + " WHERE g.id=:id AND cp.generation_id=g.id AND cp.next_open_at="
                        + target
                    ),
                    {"id": claim.generation_id, "offset": offset},
                )
            elif damage == "count":
                await connection.execute(
                    text(
                        "UPDATE indicator_generations SET checkpoint_count=checkpoint_count-1 "
                        "WHERE id=:id"
                    ),
                    {"id": claim.generation_id},
                )
        if timeframe == "1m":
            async with migrator_engine.connect() as connection:
                count: int = (
                    await connection.execute(
                        text("SELECT checkpoint_count FROM indicator_generations WHERE id=:id"),
                        {"id": claim.generation_id},
                    )
                ).scalar_one()
                assert count == (526 if damage == "count" else 527)
        try:
            with pytest.raises(IndicatorBuildConfigurationError) if damage else nullcontext():
                async with writer.transaction() as session:
                    await session.execute(
                        "SELECT set_config('plan_cache_mode',:mode,true)", {"mode": plan_mode}
                    )
                    assert await publish(session, claim, numeric=False) == PublicationResult.READY
        finally:
            if damage is not None:
                await writer.finish(AttemptOutcome.OPERATIONAL)
