"""Actual-role/physical-session fencing, durable fairness and safe handoff."""

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_source import active as active
from tiewtrade.core.market_data import Timeframe, align_ceil, align_floor, retention_cutoff
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import (
    IndicatorBuildConfigurationError,
    IndicatorBuildCounterError,
    IndicatorBuildOwnershipError,
    NotPermittedError,
)
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.claims import (
    AttemptOutcome,
    BuildClaim,
    claim_next,
    heartbeat,
    release,
    seed_jobs,
)
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.infra.indicators.source import begin_source_write


@pytest_asyncio.fixture
async def builder_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(DatabaseRole.INDICATOR_BUILDER, pool_size=2, max_overflow=0)
    try:
        yield engine
    finally:
        await engine.dispose()


async def clean_metadata(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("UPDATE indicator_build_jobs SET current_candidate=NULL"))
        for table in (
            "indicator_heads",
            "indicator_checkpoints",
            "indicator_generations",
            "indicator_retry_requests",
            "indicator_build_jobs",
        ):
            await connection.execute(text(f"DELETE FROM {table}"))
        await connection.execute(
            text("""UPDATE indicator_build_slot SET state='IDLE',
            slot_epoch=gen_random_uuid(),fence=0,owner_instance=NULL,owner_backend_pid=NULL,
            job_id=NULL,generation_id=NULL,claim_token=NULL,lease_until=NULL,
            attempt_deadline=NULL,last_heartbeat=NULL,dispatch_round=1,dispatch_cursor=-1""")
        )


@pytest_asyncio.fixture
async def prepared(active: None, migrator_engine: AsyncEngine) -> AsyncIterator[None]:
    await clean_metadata(migrator_engine)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("""UPDATE indicator_rollout_control SET mode='PREPARING',
            codec_version=2,protocol_version=1,retention_policy='GRACE' WHERE id=1""")
        )
    try:
        yield
    finally:
        # All test owner scopes/tasks have exited before this privileged reset.
        await clean_metadata(migrator_engine)
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("UPDATE indicator_rollout_control SET mode='LEGACY' WHERE id=1")
            )


async def slot(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as connection:
        return dict(
            (await connection.execute(text("SELECT * FROM indicator_build_slot WHERE id=1")))
            .mappings()
            .one()
        )


async def job(engine: AsyncEngine, claim: BuildClaim) -> dict[str, Any]:
    async with engine.connect() as connection:
        return dict(
            (
                await connection.execute(
                    text("SELECT * FROM indicator_build_jobs WHERE id=:id"), {"id": claim.job_id}
                )
            )
            .mappings()
            .one()
        )


async def reap(engine: AsyncEngine, claim: BuildClaim) -> str:
    async with engine.begin() as connection:
        return str(
            (
                await connection.execute(
                    text("SELECT reap_indicator_build_slot(:owner,:epoch,:fence)"),
                    {
                        "owner": claim.owner_instance,
                        "epoch": claim.slot_epoch,
                        "fence": claim.fence,
                    },
                )
            ).scalar_one()
        )


@pytest.mark.parametrize("cancellation", ["timeout", "cancel"])
async def test_reap_cancellation_releases_lock_and_same_session_can_retry(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    cancellation: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as owner:
        assert owner is not None
        await owner.seed()
        claim = await owner.claim(uuid4())
        assert claim is not None
        # No CPU/source task exists; scope exit stops this owner and leaves an orphan.
    before_slot = await slot(migrator_engine)
    before_job = await job(migrator_engine, claim)
    async with migrator_engine.connect() as reaper, migrator_engine.connect() as blocker:
        try:
            pid: Any = (await reaper.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            await reaper.execute(
                text("SELECT set_config('statement_timeout',:timeout,true)"),
                {"timeout": "300ms" if cancellation == "timeout" else "5s"},
            )
            await blocker.execute(
                text("SELECT id FROM indicator_rollout_control WHERE id=1 FOR UPDATE")
            )
            request = asyncio.create_task(
                reaper.execute(
                    text("SELECT reap_indicator_build_slot(:owner,:epoch,:fence)"),
                    {
                        "owner": claim.owner_instance,
                        "epoch": claim.slot_epoch,
                        "fence": claim.fence,
                    },
                )
            )
            try:
                if cancellation == "cancel":
                    # Cancel only after the helper holds the key and waits on control.
                    async with asyncio.timeout(3):
                        while True:
                            waiting: Any = (
                                await blocker.execute(
                                    text("""SELECT EXISTS(SELECT 1 FROM pg_locks
                                WHERE pid=:pid AND locktype='tuple' AND granted)
                                AND EXISTS(SELECT 1 FROM pg_locks WHERE pid=:pid
                                AND locktype='advisory' AND classid=711 AND objid=1
                                AND objsubid=2 AND granted)"""),
                                    {"pid": pid},
                                )
                            ).scalar_one()
                            if waiting:
                                break
                            await asyncio.sleep(0.01)
                    cancelled: Any = (
                        await blocker.execute(text("SELECT pg_cancel_backend(:pid)"), {"pid": pid})
                    ).scalar_one()
                    assert cancelled
                with pytest.raises(DBAPIError) as error:
                    await asyncio.wait_for(request, 6)
                assert getattr(error.value.orig, "sqlstate", None) == "57014"
            finally:
                if not request.done():
                    request.cancel()
                await asyncio.gather(request, return_exceptions=True)
                await blocker.rollback()
            await reaper.rollback()
            reused_pid: Any = (await reaper.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            assert reused_pid == pid
            held: Any = (
                await reaper.execute(text("SELECT indicator_build_lock_held()"))
            ).scalar_one()
            assert not held
            assert await slot(migrator_engine) == before_slot
            assert await job(migrator_engine, claim) == before_job
            async with pinned_indicator_writer(builder_engine, connection_mode="direct") as other:
                assert other is not None
                assert await other.claim(uuid4()) is None  # Orphan still requires safe reap.
            result: Any = (
                await reaper.execute(
                    text("SELECT reap_indicator_build_slot(:owner,:epoch,:fence)"),
                    {
                        "owner": claim.owner_instance,
                        "epoch": claim.slot_epoch,
                        "fence": claim.fence,
                    },
                )
            ).scalar_one()
            assert result == "REAPED"
            await reaper.commit()
            held = (await reaper.execute(text("SELECT indicator_build_lock_held()"))).scalar_one()
            assert not held
        finally:
            # Failed assertions must not return a leaked session lock to the test pool.
            await reaper.invalidate()
    assert (await slot(migrator_engine))["state"] == "IDLE"
    after_job = await job(migrator_engine, claim)
    assert after_job["attempts_used"] == before_job["attempts_used"]
    assert after_job["last_served_round"] == before_job["last_served_round"]


async def test_seed_fixed_catalog_and_exclusive_claim(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as first:
        assert first is not None
        assert await first.seed() == 40
        assert await first.seed() == 0
        claim = await first.claim(uuid4())
        assert claim is not None
        before = await job(migrator_engine, claim)
        assert before["attempts_used"] == 1 and before["last_served_round"] == 1
        assert before["current_candidate"] is None
        assert claim.attempt_deadline < claim.lease_until
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as second:
            assert second is None
        after = await job(migrator_engine, claim)
        assert after == before
        await asyncio.gather(first.heartbeat(), first.heartbeat())
        live = await slot(migrator_engine)
        assert live["owner_backend_pid"] == first.backend_pid == claim.backend_pid
        assert live["attempt_deadline"] == claim.attempt_deadline
        assert live["lease_until"] > claim.lease_until
        async with migrator_engine.connect() as connection:
            locks: Any = (
                await connection.execute(
                    text("""SELECT count(*) FROM pg_locks
                WHERE locktype='advisory' AND classid=711 AND objid=1 AND objsubid=2 AND granted""")
                )
            ).scalar_one()
            assert locks == 1
        await first.finish(AttemptOutcome.SOURCE_CHANGED)
    assert (await slot(migrator_engine))["state"] == "IDLE"
    released = await job(migrator_engine, claim)
    assert released["status"] == "QUEUED" and released["attempts_used"] == 1
    assert released["retry_not_before"] > live["last_heartbeat"]


async def test_retired_v1_job_is_never_claimed_by_v2_builder(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("""INSERT INTO indicator_build_jobs
          (source,base,quote,timeframe,formula_version,desired_start,desired_end,
           first_eligible_at,availability_deadline,retry_not_before)
          VALUES('primary_spot','BTC','USDT','1m','indicators-v1',
            clock_timestamp()-interval '1 day',clock_timestamp(),
            clock_timestamp()-interval '1 day',clock_timestamp()-interval '1 day',
            clock_timestamp()-interval '1 day')""")
        )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        assert await writer.seed() == 40
        claim = await writer.claim(uuid4())
        assert claim is not None and claim.formula_version == "indicators-v2"
        await writer.finish(AttemptOutcome.SOURCE_CHANGED)
    async with migrator_engine.connect() as connection:
        old_status: str = (
            await connection.execute(
                text("""SELECT status FROM indicator_build_jobs
          WHERE formula_version='indicators-v1'""")
            )
        ).scalar_one()
    assert old_status == "QUEUED"


async def test_no_due_job_and_rollback_do_not_consume_round_or_attempt(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    original = await slot(migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        assert await writer.claim(uuid4()) is None
    assert await slot(migrator_engine) == original
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        with pytest.raises(ValueError, match="rollback"):
            async with writer.transaction() as session:
                assert await claim_next(session, uuid4()) is not None
                raise ValueError("rollback")
    assert await slot(migrator_engine) == original
    async with migrator_engine.connect() as connection:
        count: Any = (
            await connection.execute(
                text("""SELECT count(*) FROM indicator_build_jobs
            WHERE attempts_used<>0 OR last_served_round<>0 OR claim_token IS NOT NULL""")
            )
        ).scalar_one()
        assert count == 0


async def test_seed_bounds_are_utc_and_do_not_leak_session_timezone(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with indicator_writer_session(builder_engine) as session:
        await session.execute("SELECT set_config('TimeZone','America/New_York',true)")
        assert await seed_jobs(session) == 40
        assert (await session.execute("SHOW TimeZone")).scalar_one() == "America/New_York"
    async with migrator_engine.connect() as connection:
        rows = (await connection.execute(text("SELECT * FROM indicator_build_jobs"))).mappings()
        for row in rows:
            timeframe = Timeframe(row["timeframe"])
            expected_start = align_ceil(
                retention_cutoff(row["first_eligible_at"], timeframe), timeframe
            )
            assert row["desired_start"] == expected_start
            assert row["desired_end"] == align_floor(row["first_eligible_at"], timeframe)
        settings: Any = (
            await connection.execute(
                text("""SELECT proconfig FROM pg_proc
            WHERE oid='seed_indicator_build_jobs()'::regprocedure""")
            )
        ).scalar_one()
        assert "TimeZone=UTC" in settings


async def test_pinned_scope_requires_fresh_acquire_for_each_dispatch(
    prepared: None,
    builder_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        first = await writer.claim(uuid4())
        assert first is not None
        await writer.finish(AttemptOutcome.TRANSIENT)
        with pytest.raises(IndicatorBuildOwnershipError, match="fresh acquisition"):
            await writer.claim(uuid4())
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        second = await writer.claim(uuid4())
        assert second is not None and second.job_id != first.job_id and second.fence > first.fence
        await writer.finish(AttemptOutcome.OPERATIONAL)


async def test_durable_fair_round_serves_other_series_before_retry(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        a = await writer.claim(uuid4())
        assert a is not None
        await writer.finish(AttemptOutcome.SOURCE_CHANGED)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("""UPDATE indicator_build_jobs SET status='FAILED_OPERATIONAL'
            WHERE id<>:a AND NOT (base='DOGE' AND timeframe='1m')"""),
            {"a": a.job_id},
        )
        await connection.execute(
            text("""UPDATE indicator_build_jobs SET
            retry_not_before=clock_timestamp()-interval '1 second',
            availability_deadline=clock_timestamp()-interval '10 minutes' WHERE id=:a"""),
            {"a": a.job_id},
        )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        b = await writer.claim(uuid4())
        assert b is not None and b.base == "DOGE" and b.dispatch_round == a.dispatch_round
        await writer.finish(AttemptOutcome.TRANSIENT)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        retry = await writer.claim(uuid4())
        assert retry is not None and retry.job_id == a.job_id
        assert retry.dispatch_round == a.dispatch_round + 1
        assert retry.candidate_sequence == 2 and retry.fence > b.fence
        await writer.finish(AttemptOutcome.OPERATIONAL)
    info = await job(migrator_engine, retry)
    assert info["first_eligible_at"] == (await job(migrator_engine, a))["first_eligible_at"]
    assert info["deadline_missed_at"] is not None


@pytest.mark.parametrize("expiry", ["deadline", "lease"])
async def test_expiry_never_steals_live_session_and_owner_can_release(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    expiry: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        claim = await writer.claim(uuid4())
        assert claim is not None
        async with migrator_engine.begin() as connection:
            column = "attempt_deadline" if expiry == "deadline" else "lease_until"
            await connection.execute(
                text(
                    f"UPDATE indicator_build_slot SET {column}="
                    "clock_timestamp()-interval '1 second'"
                )
            )
            if expiry == "lease":
                await connection.execute(
                    text(
                        "UPDATE indicator_build_jobs SET lease_until="
                        "clock_timestamp()-interval '1 second' WHERE id=:id"
                    ),
                    {"id": claim.job_id},
                )
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as loser:
            assert loser is None
        assert await reap(migrator_engine, claim) == "LOCK_BUSY"
        with pytest.raises(IndicatorBuildOwnershipError):
            await writer.heartbeat()
        await writer.finish(AttemptOutcome.OWNERSHIP_LOST)
    assert (await slot(migrator_engine))["state"] == "IDLE"


async def test_orphan_fails_closed_until_migrator_reap_and_old_identity_is_fenced(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as abandoned:
        assert abandoned is not None
        await abandoned.seed()
        old = await abandoned.claim(uuid4())
        assert old is not None
        # No CPU/source work was opened; exit discards the physical owner session.
    assert (await slot(migrator_engine))["state"] == "RUNNING"
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as contender:
        assert contender is not None
        assert await contender.claim(uuid4()) is None
    assert await reap(migrator_engine, replace(old, fence=old.fence + 1)) == "STALE"
    assert await reap(migrator_engine, old) == "REAPED"
    assert await reap(migrator_engine, old) == "STALE"
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as fresh:
        assert fresh is not None
        claim = await fresh.claim(uuid4())
        assert claim is not None and claim.job_id != old.job_id
        assert claim.fence >= old.fence + 2
        for method in (heartbeat,):
            with pytest.raises(IndicatorBuildOwnershipError):
                async with fresh.transaction() as session:
                    await method(session, old)
        with pytest.raises(IndicatorBuildOwnershipError):
            async with fresh.transaction() as session:
                await release(session, old, AttemptOutcome.TRANSIENT)
        await fresh.finish(AttemptOutcome.OPERATIONAL)
    old_job = await job(migrator_engine, old)
    assert old_job["attempts_used"] == 1 and old_job["last_served_round"] == 1


async def test_shared_three_attempt_budget_and_terminal_supersession(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with indicator_writer_session(builder_engine) as session:
        await seed_jobs(session)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE indicator_build_jobs SET status='FAILED_OPERATIONAL' "
                "WHERE NOT(base='BTC' AND timeframe='1m')"
            )
        )
    first: BuildClaim | None = None
    for used, outcome in enumerate(
        (AttemptOutcome.SOURCE_CHANGED, AttemptOutcome.TRANSIENT, AttemptOutcome.SOURCE_CHANGED), 1
    ):
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            claim = await writer.claim(uuid4())
            assert claim is not None
            if first is None:
                first = claim
            assert claim.candidate_sequence == used
            await writer.finish(outcome)
        info = await job(migrator_engine, claim)
        assert info["attempts_used"] == used
        if used < 3:
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE indicator_build_jobs SET retry_not_before="
                        "clock_timestamp()-interval '1 second' WHERE id=:id"
                    ),
                    {"id": claim.job_id},
                )
        else:
            assert info["status"] == "FAILED_SUPERSEDED" and info["failed_at"] is not None
            assert info["failure_reason"] == "SOURCE_CHANGED"
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        assert await writer.seed() == 0
        assert await writer.claim(uuid4()) is None


@pytest.mark.parametrize(
    "field", ["slot_epoch", "fence", "owner_instance", "job_id", "generation_id", "token"]
)
async def test_spoofed_identity_rejected_without_losing_real_owner(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    field: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        claim = await writer.claim(uuid4())
        assert claim is not None
        changes: dict[str, Any] = {field: claim.fence + 1 if field == "fence" else uuid4()}
        bad = replace(claim, **changes)
        with pytest.raises(IndicatorBuildOwnershipError):
            async with writer.transaction() as session:
                await heartbeat(session, bad)
        await writer.heartbeat()
        await writer.finish(AttemptOutcome.OPERATIONAL)


async def test_reentrant_acquire_rejected_and_pool_reuse_has_no_lock_leak(
    prepared: None,
    builder_engine: AsyncEngine,
) -> None:
    for _ in range(3):
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            with pytest.raises(IndicatorBuildConfigurationError):
                async with writer.transaction() as session:
                    await session.execute("SELECT try_indicator_build_lock()")


async def test_unknown_raw_reentrant_count_discards_physical_connection(
    prepared: None,
    builder_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        old_pid = writer.backend_pid
        async with writer.transaction() as session:
            assert (await session.execute("SELECT pg_try_advisory_lock(711,1)")).scalar_one()
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None and writer.backend_pid != old_pid


async def test_inherited_session_lock_is_discarded_when_acquire_fails(
    prepared: None,
    builder_engine: AsyncEngine,
) -> None:
    async with indicator_writer_session(builder_engine) as session:
        row = (
            (
                await session.execute(
                    "SELECT pg_try_advisory_lock(711,1) AS held,pg_backend_pid() AS pid"
                )
            )
            .mappings()
            .one()
        )
        assert row["held"]
        old_pid = int(row["pid"])
    with pytest.raises(IndicatorBuildConfigurationError):
        async with pinned_indicator_writer(builder_engine, connection_mode="direct"):
            pytest.fail("inherited lock was reused")
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None and writer.backend_pid != old_pid


async def test_global_slot_is_exclusive_across_real_worker_processes(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    child_code = """
import asyncio,json,os
from uuid import uuid4
from tiewtrade.infra.db import DatabaseRole,create_engine_for
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.claims import AttemptOutcome
async def run():
    engine=create_engine_for(DatabaseRole.INDICATOR_BUILDER,pool_size=2,max_overflow=0)
    try:
        async with pinned_indicator_writer(engine,connection_mode='direct') as writer:
            if writer is None: result={'status':'BUSY','process':os.getpid()}
            else:
                claim=await writer.claim(uuid4())
                result={'status':'EMPTY' if claim is None else 'CLAIMED','process':os.getpid()}
                if claim is not None:
                    result['job']=str(claim.job_id)
                    await writer.finish(AttemptOutcome.OPERATIONAL)
        print(json.dumps(result))
    finally: await engine.dispose()
asyncio.run(run())
"""

    async def contender() -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            child_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            output, errors = await asyncio.wait_for(process.communicate(), 5)
            assert process.returncode == 0, errors.decode()
            result: dict[str, Any] = json.loads(output)
            return result
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        assert (await contender())["status"] == "BUSY"
        claim = await writer.claim(uuid4())
        assert claim is not None
        assert (await contender())["status"] == "BUSY"
        assert (await job(migrator_engine, claim))["attempts_used"] == 1
        await writer.finish(AttemptOutcome.SOURCE_CHANGED)
        assert (await slot(migrator_engine))["state"] == "IDLE"
        # Metadata release alone is insufficient until the pinned session unlocks.
        assert (await contender())["status"] == "BUSY"
    next_owner = await contender()
    assert next_owner["status"] == "CLAIMED" and next_owner["job"] != str(claim.job_id)


async def test_backend_pid_and_guc_spoof_cannot_heartbeat_foreign_owner(
    prepared: None,
    builder_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        claim = await writer.claim(uuid4())
        assert claim is not None
        with pytest.raises(IndicatorBuildOwnershipError):
            async with indicator_writer_session(builder_engine) as session:
                await session.execute(
                    "SELECT set_config('tiewtrade.owner_pid',:pid,true)",
                    {"pid": str(claim.backend_pid)},
                )
                await heartbeat(session, claim)
        await writer.heartbeat()
        await writer.finish(AttemptOutcome.OPERATIONAL)


@pytest.mark.parametrize("change", ["rollout_epoch", "mode", "proof", "protocol", "retention"])
async def test_rollout_or_proof_change_invalidates_heartbeat_but_allows_cleanup(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    change: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        claim = await writer.claim(uuid4())
        assert claim is not None
        before = await slot(migrator_engine)
        assignments = {
            "rollout_epoch": "rollout_epoch=gen_random_uuid()",
            "mode": "mode='PAUSED'",
            "proof": "source_proof_state='PENDING'",
            "protocol": "protocol_version=2",
            "retention": "retention_policy='LEGACY'",
        }
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("UPDATE indicator_rollout_control SET " + assignments[change] + " WHERE id=1")
            )
        with pytest.raises(IndicatorBuildOwnershipError):
            await writer.heartbeat()
        after = await slot(migrator_engine)
        assert after["lease_until"] == before["lease_until"]
        await writer.finish(AttemptOutcome.OWNERSHIP_LOST)


async def test_writer_backend_loss_requires_reap_and_never_reconnects_claim(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    from tiewtrade.infra.db.errors import InfraError

    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        old = await writer.claim(uuid4())
        assert old is not None
        async with indicator_writer_session(builder_engine) as killer:
            terminated: Any = (
                await killer.execute("SELECT pg_terminate_backend(:pid)", {"pid": old.backend_pid})
            ).scalar_one()
            assert terminated
        with pytest.raises(InfraError):
            await writer.heartbeat()
        with pytest.raises(IndicatorBuildOwnershipError):
            await writer.finish(AttemptOutcome.TRANSIENT)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as contender:
        assert contender is not None
        assert await contender.claim(uuid4()) is None
    assert await reap(migrator_engine, old) == "REAPED"


async def test_cancelled_owner_scope_keeps_orphan_until_explicit_safe_reap(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    claimed: asyncio.Future[BuildClaim] = asyncio.get_running_loop().create_future()

    async def owner() -> None:
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            await writer.seed()
            claim = await writer.claim(uuid4())
            assert claim is not None
            claimed.set_result(claim)
            await asyncio.Event().wait()

    task = asyncio.create_task(owner())
    old = await asyncio.wait_for(asyncio.shield(claimed), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert task.done()
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as contender:
        assert contender is not None and await contender.claim(uuid4()) is None
    assert await reap(migrator_engine, old) == "REAPED"


@pytest.mark.parametrize("mode", ["transaction", "statement"])
async def test_unsupported_poolers_rejected_before_connect(
    builder_engine: AsyncEngine, mode: Any
) -> None:
    with pytest.raises(IndicatorBuildConfigurationError):
        async with pinned_indicator_writer(builder_engine, connection_mode=mode):
            pytest.fail("unsupported pooler admitted")


@pytest.mark.parametrize("mode", ["LEGACY", "PAUSED"])
async def test_rollout_gate_keeps_job_table_empty(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    mode: str,
) -> None:
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("UPDATE indicator_rollout_control SET mode=:mode WHERE id=1"), {"mode": mode}
        )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        assert await writer.seed() == 0
        assert await writer.claim(uuid4()) is None


async def test_runtime_cannot_bypass_functions_or_reap(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with indicator_writer_session(builder_engine) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("UPDATE indicator_build_slot SET fence=fence+1")
    async with indicator_writer_session(builder_engine) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "SELECT reap_indicator_build_slot(:owner,:epoch,1)",
                {"owner": uuid4(), "epoch": uuid4()},
            )
    async with indicator_writer_session(builder_engine) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                "SELECT complete_indicator_build_attempt(:job,'TRANSIENT')", {"job": uuid4()}
            )
    for role in (DatabaseRole.API, DatabaseRole.MARKET_DATA):
        engine = create_engine_for(role)
        try:
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError) as error:
                    await connection.execute(text("SELECT try_indicator_build_lock()"))
                assert getattr(error.value.orig, "sqlstate", None) == "42501"
        finally:
            await engine.dispose()


@pytest.mark.parametrize("counter", ["fence", "dispatch_round", "generation_sequence"])
async def test_counter_overflow_fails_closed_without_partial_claim(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    counter: str,
) -> None:
    async with indicator_writer_session(builder_engine) as session:
        await seed_jobs(session)
    async with migrator_engine.begin() as connection:
        if counter == "generation_sequence":
            await connection.execute(
                text("UPDATE indicator_build_jobs SET generation_sequence=9223372036854775807")
            )
        else:
            await connection.execute(
                text(f"UPDATE indicator_build_slot SET {counter}=9223372036854775807")
            )
            if counter == "dispatch_round":
                await connection.execute(
                    text("UPDATE indicator_build_jobs SET last_served_round=9223372036854775807")
                )
    before = await slot(migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        with pytest.raises(IndicatorBuildCounterError):
            await writer.claim(uuid4())
    assert await slot(migrator_engine) == before


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "bounds",
        "relevant",
        "other_series",
        "outside_window",
        "epoch_only",
        "lost_coverage",
        "malformed",
        "malformed_date",
    ],
)
async def test_claim_cannot_bypass_numeric_suppression_with_new_token_or_global_revision(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    change: str,
) -> None:
    async with indicator_writer_session(builder_engine) as session:
        await seed_jobs(session)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("""UPDATE indicator_build_jobs SET status='FAILED_OPERATIONAL'
            WHERE NOT(base='BTC' AND timeframe='1m')""")
        )
        await connection.execute(
            text("""UPDATE indicator_build_jobs j SET
            failed_calculation_key=jsonb_build_object('source',j.source,'base',j.base,
              'quote',j.quote,'timeframe',j.timeframe,'formula_version',j.formula_version,
              'start',to_char(j.desired_start AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
              'end',to_char(j.desired_end AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')),
            failed_input_version=jsonb_build_object('epoch',g.epoch,'fence',g.revision)
            FROM indicator_source_guard g WHERE g.id=1 AND j.base='BTC' AND j.timeframe='1m'""")
        )
        bounds = (
            (
                await connection.execute(
                    text("""SELECT desired_start,desired_end
            FROM indicator_build_jobs WHERE base='BTC' AND timeframe='1m'""")
                )
            )
            .mappings()
            .one()
        )
        if change == "bounds":
            await connection.execute(
                text("""UPDATE indicator_build_jobs SET
                desired_start=desired_start+interval '1 minute',
                desired_end=desired_end+interval '1 minute' WHERE status='QUEUED'""")
            )
        elif change == "epoch_only":
            await connection.execute(
                text("UPDATE indicator_source_guard SET epoch=gen_random_uuid()")
            )
        elif change == "malformed":
            await connection.execute(
                text("""UPDATE indicator_build_jobs SET
                failed_calculation_key='"damaged"'::jsonb WHERE status='QUEUED'""")
            )
        elif change == "malformed_date":
            await connection.execute(
                text("""UPDATE indicator_build_jobs SET
                failed_calculation_key=jsonb_set(failed_calculation_key,'{start}',
                  '"not-a-time"'::jsonb) WHERE status='QUEUED'""")
            )
    if change in ("relevant", "other_series", "outside_window", "lost_coverage"):
        md_engine = create_engine_for(DatabaseRole.MARKET_DATA)
        try:
            async with market_data_session(md_engine) as session:
                await begin_source_write(session)
                opened = (
                    bounds["desired_end"]
                    if change == "outside_window"
                    else bounds["desired_end"] - timedelta(minutes=1)
                )
                await session.execute(
                    """INSERT INTO market_candles
                    (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
                     finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                    VALUES('primary_spot',:base,'USDT','1m',:opened,:end,
                      1,1,1,1,0,'OPEN',clock_timestamp(),clock_timestamp(),clock_timestamp(),1)""",
                    {
                        "base": "ETH" if change in ("other_series", "lost_coverage") else "BTC",
                        "opened": opened,
                        "end": opened + timedelta(minutes=1),
                    },
                )
        finally:
            await md_engine.dispose()
        if change == "lost_coverage":
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text("UPDATE indicator_source_guard SET journal_floor=revision")
                )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        if change in ("bounds", "relevant"):
            assert claim is not None
            await writer.finish(AttemptOutcome.OPERATIONAL)
        else:
            assert claim is None
            assert (await slot(migrator_engine))["dispatch_round"] == 1
