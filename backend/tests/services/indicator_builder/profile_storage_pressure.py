"""Explicit >3 GiB isolated-PostgreSQL regression; no application DB allowed."""

from collections.abc import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tiewtrade.infra.indicators.maintenance import collect
from tiewtrade.infra.indicators.scheduling import coalesce_jobs
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


async def test_full_storage_pressure_then_actual_ready_survives_allocated_bloat(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    record_property: Callable[[str, object], None],
) -> None:
    await seed(builder_engine, migrator_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    job = (await metadata(migrator_engine))["id"]
    try:
        async with migrator_engine.begin() as c:
            # Keep freed disk pages during the recovery probe. No mocked size,
            # budget, publisher, query or Money calculation is used.
            await c.execute(
                text("ALTER TABLE indicator_checkpoints ALTER COLUMN payload SET STORAGE EXTERNAL")
            )
            await c.execute(
                text("ALTER TABLE indicator_checkpoints SET (autovacuum_enabled=false)")
            )
            await c.execute(
                text("""INSERT INTO indicator_generations
                SELECT (jsonb_populate_record(NULL::indicator_generations,
                    to_jsonb(g)||jsonb_build_object('id',gen_random_uuid(),
                      'candidate_sequence',n+1,'status','READY','checkpoint_count',500))).*
                FROM indicator_generations g CROSS JOIN generate_series(1,450)n
                WHERE g.job_id=:job AND g.candidate_sequence=1"""),
                {"job": job},
            )
            # Valid table-sized cache fixture. Payload is storage padding, not an
            # oracle checkpoint and is never decoded by the real worker.
            await c.execute(
                text("""INSERT INTO indicator_checkpoints
                SELECT g.id,g.calculation_start+n*interval '1 second',
                  jsonb_build_object('padding',repeat('x',16000))
                FROM indicator_generations g CROSS JOIN generate_series(1,500)n
                WHERE g.job_id=:job AND g.candidate_sequence>1"""),
                {"job": job},
            )
            allocated: int = (
                await c.execute(text("SELECT pg_total_relation_size('indicator_checkpoints')"))
            ).scalar_one()
        assert allocated > 3 * 1024**3
        first = await collect(builder_engine)
        assert first["checkpoints"] == 1000
        async with migrator_engine.begin() as c:
            # Quiescent state after reclamation, preserving allocated files.
            await c.execute(text("UPDATE indicator_build_jobs SET current_candidate=NULL"))
            await c.execute(text("DELETE FROM indicator_heads"))
            await c.execute(text("DELETE FROM indicator_checkpoints"))
            await c.execute(text("DELETE FROM indicator_generations"))
        await coalesce_jobs(builder_engine)
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
        before = await metadata(migrator_engine)
        for _ in range(3):
            assert await collect(builder_engine) == {
                "journal": 0,
                "checkpoints": 0,
                "generations": 0,
            }
        assert await metadata(migrator_engine) == before
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(text("SELECT count(*) FROM indicator_ready_heads"))
            ).scalar_one() == 1
            remaining: int = (
                await c.execute(text("SELECT pg_total_relation_size('indicator_checkpoints')"))
            ).scalar_one()
        assert remaining > 3 * 1024**3
        record_property("allocated_before_bytes", allocated)
        record_property("allocated_after_bytes", remaining)
    finally:
        async with migrator_engine.begin() as c:
            await c.execute(
                text("ALTER TABLE indicator_checkpoints ALTER COLUMN payload SET STORAGE EXTENDED")
            )
            await c.execute(text("ALTER TABLE indicator_checkpoints RESET (autovacuum_enabled)"))
