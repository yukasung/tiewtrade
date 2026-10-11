"""Real-role recovery idempotency, proof pruning and fenced GC races."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tests.services.indicator_builder.test_scheduler import numeric, terminal
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.maintenance import RetryResult, collect, retry_job
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


@pytest.mark.parametrize("outcome", list(AttemptOutcome))
async def test_retry_is_atomic_idempotent_and_preserves_episode(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    outcome: AttemptOutcome,
) -> None:
    await seed(builder_engine, migrator_engine)
    await terminal(builder_engine, migrator_engine, outcome)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                """UPDATE indicator_build_jobs SET
                failed_at=clock_timestamp()-interval '600 seconds' WHERE failed_at IS NOT NULL"""
            )
        )
    before = await metadata(migrator_engine)
    identity, request = before["id"], uuid4()
    results = await asyncio.gather(
        retry_job(builder_engine, identity, request),
        retry_job(builder_engine, identity, request),
    )
    assert all(result is RetryResult.QUEUED for result in results)
    after = await metadata(migrator_engine)
    assert after["attempts_used"] == 0 and after["cycle_id"] != before["cycle_id"]
    for name in (
        "first_eligible_at",
        "availability_deadline",
        "last_served_round",
        "deadline_missed_at",
    ):
        assert after[name] == before[name]
    assert await retry_job(builder_engine, identity, request) is RetryResult.QUEUED
    assert await metadata(migrator_engine) == after
    assert await retry_job(builder_engine, identity, uuid4()) is RetryResult.REJECTED


async def test_rejected_request_remains_rejected_after_cooldown(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    await terminal(builder_engine, migrator_engine, AttemptOutcome.OPERATIONAL)
    job = (await metadata(migrator_engine))["id"]
    request = uuid4()
    assert await retry_job(builder_engine, job, request) is RetryResult.REJECTED
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_build_jobs SET failed_at=clock_timestamp()-interval '601 seconds'"
            )
        )
    assert await retry_job(builder_engine, job, request) is RetryResult.REJECTED
    assert await retry_job(builder_engine, job, uuid4()) is RetryResult.QUEUED


async def test_numeric_manifest_gc_does_not_allow_manual_retry(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    await numeric(builder_engine)
    before = await metadata(migrator_engine)
    async with migrator_engine.begin() as c:
        # Preserve the generation expiry CHECK while advancing its test age.
        await c.execute(
            text(
                """UPDATE indicator_generations SET as_of=as_of-interval '7 hours',
                expires_at=expires_at-interval '7 hours',
                calculation_end=calculation_end-interval '7 hours',
                calculation_start=calculation_start-interval '7 hours'"""
            )
        )
    assert (await collect(builder_engine))["generations"] == 1
    after = await metadata(migrator_engine)
    assert after["current_candidate"] is None
    for field in ("failed_calculation_key", "failed_input_version", "cycle_id", "attempts_used"):
        assert after[field] == before[field]
    assert await retry_job(builder_engine, after["id"], uuid4()) is RetryResult.REJECTED


async def test_running_candidate_and_slot_survive_gc_and_retry(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        assert claim is not None
        before = await slot(migrator_engine)
        assert await retry_job(builder_engine, claim.job_id, uuid4()) is RetryResult.REJECTED
        await collect(builder_engine)
        assert await slot(migrator_engine) == before
        await writer.finish(AttemptOutcome.OWNERSHIP_LOST)


async def test_journal_batch_advances_floor_and_expires_dependents_atomically(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    async with migrator_engine.begin() as c:
        # 10,001 events at one committed revision: pruning part must invalidate
        # fences below that revision, even while one event remains.
        await c.execute(text("UPDATE indicator_source_guard SET revision=revision+1"))
        await c.execute(
            text("""INSERT INTO indicator_source_changes
          (epoch,revision,source,base,quote,timeframe,open_at,kind,created_at)
          SELECT epoch,revision,'primary_spot','BTC','USDT','1m',
          clock_timestamp()+n*interval '1 minute','WRITE',clock_timestamp()-interval '7 hours'
          FROM indicator_source_guard CROSS JOIN generate_series(1,10001) n""")
        )
    result = await collect(builder_engine)
    assert result["journal"] == 10000
    async with migrator_engine.connect() as c:
        floor, revision = (
            await c.execute(text("SELECT journal_floor,revision FROM indicator_source_guard"))
        ).one()
        assert floor == revision
        assert (await c.execute(text("SELECT count(*) FROM indicator_heads"))).scalar_one() == 0
    assert (await collect(builder_engine))["journal"] >= 1


@pytest.mark.parametrize(
    "function",
    ["gc_indicator_data()", "retry_indicator_build_job(gen_random_uuid(),gen_random_uuid())"],
)
async def test_api_cannot_execute_maintenance(
    prepared: None,
    api_engine: AsyncEngine,
    function: str,
) -> None:
    async with api_engine.begin() as c:
        from tiewtrade.infra.db.session import _execute

        with pytest.raises(NotPermittedError):
            await _execute(c, f"SELECT public.{function}", None)


async def test_gc_lock_timeout_rolls_back_and_session_remains_usable(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    from tiewtrade.infra.db.errors import DatabaseTimeoutError

    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT 1 FROM indicator_source_guard FOR UPDATE"))
        with pytest.raises(DatabaseTimeoutError):
            await collect(builder_engine)
    assert await collect(builder_engine) == {"journal": 0, "checkpoints": 0, "generations": 0}
    async with indicator_writer_session(builder_engine) as session:
        assert (await session.execute("SELECT 1")).scalar_one() == 1


async def test_expired_lease_gc_preserves_orphan_for_reap(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    from tiewtrade.core.indicators import IndicatorStream
    from tiewtrade.infra.indicators.session import indicator_source_session
    from tiewtrade.infra.indicators.staging import append_checkpoint, capture_snapshot, initialize

    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        assert claim is not None
        async with indicator_source_session(builder_engine) as source:
            snapshot = await capture_snapshot(source, claim)
        await initialize(writer, claim, snapshot)
        await append_checkpoint(
            writer,
            claim,
            snapshot,
            IndicatorStream(claim.base, claim.quote, claim.timeframe, snapshot.as_of),
            snapshot.calculation.start,
        )
        before = await slot(migrator_engine)
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    """UPDATE indicator_build_jobs SET
                    lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"""
                ),
                {"id": claim.job_id},
            )
        assert (await collect(builder_engine))["checkpoints"] == 1
        assert (await metadata(migrator_engine))["current_candidate"] == claim.generation_id
        assert await slot(migrator_engine) == before
        await writer.finish(AttemptOutcome.OWNERSHIP_LOST)
    assert (await collect(builder_engine))["generations"] == 1


async def test_checkpoint_gc_is_bounded_to_1000_rows(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""INSERT INTO indicator_checkpoints(generation_id,next_open_at,payload)
            SELECT g.id,g.calculation_start+n*interval '1 second',c.payload
            FROM indicator_generations g CROSS JOIN generate_series(1,1001) n
            CROSS JOIN LATERAL(SELECT payload FROM indicator_checkpoints
                WHERE generation_id=g.id ORDER BY next_open_at LIMIT 1)c""")
        )
        await c.execute(text("UPDATE indicator_generations SET status='EXPIRED'"))
    first = await collect(builder_engine)
    assert first["checkpoints"] == 1000 and first["generations"] == 0
    second = await collect(builder_engine)
    assert 0 < second["checkpoints"] < 1000 and second["generations"] == 1


async def test_gc_parallel_with_actual_publication_preserves_ready(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    # Maintenance uses its own role-identical pool; the worker pool remains two.
    from tiewtrade.infra.db import DatabaseRole, create_engine_for

    collector = create_engine_for(DatabaseRole.INDICATOR_BUILDER, pool_size=1, max_overflow=0)
    try:
        result, _ = await asyncio.gather(run_attempt(builder_engine, uuid4()), collect(collector))
        assert result.status is AttemptStatus.READY
        assert (await metadata(migrator_engine))["status"] == "READY"
    finally:
        await collector.dispose()


async def test_retry_cli_returns_fixed_result_without_privileged_credentials(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    import json
    import sys

    from tiewtrade.services.indicator_builder.supervisor import worker_environment

    await seed(builder_engine, migrator_engine)
    await terminal(builder_engine, migrator_engine, AttemptOutcome.OPERATIONAL)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_build_jobs SET failed_at=clock_timestamp()-interval '601 seconds'"
            )
        )
    job = (await metadata(migrator_engine))["id"]
    request = uuid4()
    for _ in range(2):
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tiewtrade.services.indicator_builder.main",
            "retry",
            "--job-id",
            str(job),
            "--request-id",
            str(request),
            env=worker_environment(uuid4()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, error = await asyncio.wait_for(process.communicate(), 4)
        assert process.returncode == 0 and not error
        assert json.loads(output) == {
            "component": "indicator-builder",
            "event": "retry",
            "status": "QUEUED",
        }
