"""Actual-role coalescing, recovery evidence and scheduler/attempt integration."""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tiewtrade.core.market_data import Timeframe, align_ceil, align_floor, retention_cutoff
from tiewtrade.core.money import OutOfRangeError
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import DatabaseTimeoutError, SourceProofStateError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators import scan as scanner
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter, pinned_indicator_writer
from tiewtrade.infra.indicators.scheduling import coalesce_jobs
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.indicators.staging import append_checkpoint, capture_snapshot, initialize
from tiewtrade.services.indicator_builder import scheduler
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


async def change_source(admin: AsyncEngine, *, base: str = "BTC", outside: bool = False) -> None:
    j = await metadata(admin)
    opened = j["desired_end"] - (timedelta(0) if outside else timedelta(hours=4))
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await begin_source_write(session)
            await session.execute(
                """INSERT INTO market_candles
                (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
                 finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                VALUES('primary_spot',:base,'USDT','4h',:opened,:end,
                  1,1,1,1,0,'OPEN',clock_timestamp(),clock_timestamp(),clock_timestamp(),1)
                ON CONFLICT(source,base,quote,timeframe,open_at) DO UPDATE
                  SET close=market_candles.close+1,high=market_candles.high+1""",
                {"base": base, "opened": opened, "end": opened + timedelta(hours=4)},
            )
    finally:
        await engine.dispose()


async def numeric(builder: AsyncEngine) -> None:
    async with pinned_indicator_writer(builder, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        assert claim is not None
        async with indicator_source_session(builder) as session:
            snapshot = await capture_snapshot(session, claim)
        await initialize(writer, claim, snapshot)
        await writer.publish_numeric_failure(claim, OutOfRangeError())


async def terminal(builder: AsyncEngine, admin: AsyncEngine, outcome: AttemptOutcome) -> None:
    for _ in range(3):
        async with pinned_indicator_writer(builder, connection_mode="direct") as writer:
            assert writer is not None
            claim = await writer.claim(uuid4())
            assert claim is not None
            await writer.finish(outcome)
        if outcome is AttemptOutcome.OPERATIONAL:
            break
        async with admin.begin() as c:
            await c.execute(
                text("UPDATE indicator_build_jobs SET retry_not_before=clock_timestamp()")
            )


@pytest.mark.parametrize("mode", ["LEGACY", "PAUSED", "PREPARING", "PREPARED"])
async def test_catalog_and_control_gate(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine, mode: str
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode=:mode"), {"mode": mode})
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    async with migrator_engine.connect() as c:
        rows = (
            (
                await c.execute(
                    text("SELECT *,clock_timestamp() AS observed FROM indicator_build_jobs")
                )
            )
            .mappings()
            .all()
        )
    assert len(rows) == (40 if mode in ("PREPARING", "PREPARED") else 0)
    for j in rows:
        tf = Timeframe(j["timeframe"])
        assert j["desired_start"] == align_ceil(retention_cutoff(j["observed"], tf), tf)
        assert j["desired_end"] == align_floor(j["observed"], tf)
        assert j["attempts_used"] == 0 and j["last_served_round"] == 0
    assert (await slot(migrator_engine))["fence"] == 0


async def test_pending_window_preserves_running_identity_and_queued_budget(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        assert claim is not None
        async with migrator_engine.begin() as c:
            await c.execute(
                text("""UPDATE indicator_build_jobs SET
              desired_start=desired_start-interval '4 hours',
              desired_end=desired_end-interval '4 hours'
              WHERE id=:id"""),
                {"id": claim.job_id},
            )
        before = await metadata(migrator_engine)
        await writer.coalesce()
        after = await metadata(migrator_engine)
        assert after["desired_end"] > before["desired_end"]
        for key in (
            "status",
            "claim_token",
            "cycle_id",
            "attempts_used",
            "last_served_round",
            "first_eligible_at",
            "availability_deadline",
        ):
            assert after[key] == before[key]
        await writer.finish(AttemptOutcome.SOURCE_CHANGED)
    queued = await metadata(migrator_engine)
    await coalesce_jobs(builder_engine)
    assert await metadata(migrator_engine) == queued
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB


@pytest.mark.parametrize("age,queued", [(100, False), (469, False), (471, True), (610, True)])
async def test_ready_refresh_deadline_is_head_age_not_poll_time(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    age: int,
    queued: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    async with migrator_engine.begin() as c:
        h: datetime = (
            await c.execute(
                text("""UPDATE indicator_generations SET
          as_of=statement_timestamp()-make_interval(secs=>:age),
          calculation_end=least(calculation_end,statement_timestamp()-make_interval(secs=>:age)),
          expires_at=statement_timestamp()-make_interval(secs=>:age)+interval '6 hours 10 minutes'
          WHERE status='READY' RETURNING as_of"""),
                {"age": age},
            )
        ).scalar_one()
    await coalesce_jobs(builder_engine)
    j = await metadata(migrator_engine)
    assert (j["status"] == "QUEUED") == queued
    if queued:
        assert j["availability_deadline"] == h + timedelta(seconds=600)
        assert j["first_eligible_at"] == h + timedelta(seconds=470)
        assert (j["deadline_missed_at"] is not None) == (age > 600)
        await coalesce_jobs(builder_engine)
        assert await metadata(migrator_engine) == j


@pytest.mark.parametrize("change", ["relevant", "other_series", "outside", "missing_head"])
async def test_ready_proof_drives_dirty_eligibility(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    change: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    if change == "missing_head":
        async with migrator_engine.begin() as c:
            await c.execute(text("DELETE FROM indicator_heads"))
    else:
        await change_source(
            migrator_engine,
            base="ETH" if change == "other_series" else "BTC",
            outside=change == "outside",
        )
    await coalesce_jobs(builder_engine)
    j = await metadata(migrator_engine)
    assert j["status"] == ("QUEUED" if change in ("relevant", "missing_head") else "READY")
    if j["status"] == "QUEUED":
        assert j["availability_deadline"] - j["first_eligible_at"] == timedelta(seconds=600)


@pytest.mark.parametrize("change", ["none", "relevant", "other_series", "outside", "bounds", "gc"])
async def test_numeric_suppression_survives_poll_and_manifest_gc(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    change: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    await numeric(builder_engine)
    before = await metadata(migrator_engine)
    if change in ("relevant", "other_series", "outside"):
        await change_source(
            migrator_engine,
            base="ETH" if change == "other_series" else "BTC",
            outside=change == "outside",
        )
    elif change == "bounds":
        # A prior aligned failed key, while the DB clock supplies today's desired key.
        async with migrator_engine.begin() as c:
            await c.execute(
                text("""UPDATE indicator_build_jobs SET failed_calculation_key=
              jsonb_set(failed_calculation_key,'{start}',to_jsonb(to_char(
                desired_start-interval '4 hours','YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')))
              ||jsonb_build_object('end',to_char(desired_end-interval '4 hours',
                'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')) WHERE status='FAILED_NUMERIC'""")
            )
    elif change == "gc":
        async with migrator_engine.begin() as c:
            await c.execute(text("UPDATE indicator_build_jobs SET current_candidate=NULL"))
            await c.execute(text("DELETE FROM indicator_generations"))
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    after = await metadata(migrator_engine)
    allowed = change in ("relevant", "bounds")
    assert after["status"] == ("QUEUED" if allowed else "FAILED_NUMERIC")
    assert after["first_eligible_at"] == before["first_eligible_at"]
    assert after["availability_deadline"] == before["availability_deadline"]
    assert after["last_served_round"] == before["last_served_round"]
    if not allowed:
        assert after["attempts_used"] == before["attempts_used"]
        assert after["cycle_id"] == before["cycle_id"]
    stable = await metadata(migrator_engine)
    await coalesce_jobs(builder_engine)
    assert await metadata(migrator_engine) == stable
    if allowed:
        await numeric(builder_engine)
        await coalesce_jobs(builder_engine)
        assert (await metadata(migrator_engine))["status"] == "FAILED_NUMERIC"


@pytest.mark.parametrize(
    "outcome", [AttemptOutcome.TRANSIENT, AttemptOutcome.SOURCE_CHANGED, AttemptOutcome.OPERATIONAL]
)
async def test_terminal_recovery_requires_post_failure_event_and_cooldown(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    outcome: AttemptOutcome,
) -> None:
    await seed(builder_engine, migrator_engine)
    await change_source(migrator_engine)
    await terminal(builder_engine, migrator_engine, outcome)
    failed = await metadata(migrator_engine)
    await coalesce_jobs(builder_engine)
    assert (await metadata(migrator_engine))["status"] == failed["status"]
    await change_source(migrator_engine)
    await coalesce_jobs(builder_engine)
    pending = await metadata(migrator_engine)
    assert pending["status"] == failed["status"]
    assert (pending["recovery_event_revision"] is not None) == (
        outcome != AttemptOutcome.OPERATIONAL
    )
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs
          SET failed_at=failed_at-interval '601 seconds' WHERE base='BTC' AND timeframe='4h'""")
        )
        # Recorded evidence survives journal pruning during cooldown.
        await c.execute(text("DELETE FROM indicator_source_changes"))
        await c.execute(text("UPDATE indicator_source_guard SET journal_floor=revision"))
    await coalesce_jobs(builder_engine)
    recovered = await metadata(migrator_engine)
    assert recovered["status"] == (
        failed["status"] if outcome == AttemptOutcome.OPERATIONAL else "QUEUED"
    )
    for key in ("first_eligible_at", "availability_deadline", "last_served_round"):
        assert recovered[key] == failed[key]
    if outcome != AttemptOutcome.OPERATIONAL:
        assert recovered["attempts_used"] == 0 and recovered["cycle_id"] != failed["cycle_id"]


@pytest.mark.parametrize("change", ["none", "other_series", "outside", "epoch"])
async def test_exhausted_cycle_never_restarts_from_clock_or_unproven_change(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    change: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    await change_source(migrator_engine)
    await terminal(builder_engine, migrator_engine, AttemptOutcome.SOURCE_CHANGED)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET failed_at=failed_at-interval '601 seconds',
          desired_start=desired_start-interval '4 hours',desired_end=desired_end-interval '4 hours'
          WHERE base='BTC' AND timeframe='4h'""")
        )
        if change == "epoch":
            await c.execute(text("UPDATE indicator_source_guard SET epoch=gen_random_uuid()"))
    if change in ("other_series", "outside"):
        await coalesce_jobs(builder_engine)
        await change_source(
            migrator_engine,
            base="ETH" if change == "other_series" else "BTC",
            outside=change == "outside",
        )
    await coalesce_jobs(builder_engine)
    assert (await metadata(migrator_engine))["status"] == "FAILED_SUPERSEDED"
    assert (await metadata(migrator_engine))["attempts_used"] == 3


async def test_scheduler_fails_closed_on_trigger_damage_and_guard_timeout(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT * FROM indicator_source_guard FOR UPDATE"))
        with pytest.raises(DatabaseTimeoutError):
            await coalesce_jobs(builder_engine)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        await c.execute(text("ALTER TABLE market_candles DISABLE TRIGGER indicator_source_rows"))
        await c.execute(text("UPDATE indicator_rollout_control SET source_proof_state='READY'"))
    try:
        with pytest.raises(SourceProofStateError):
            await coalesce_jobs(builder_engine)
    finally:
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text("ALTER TABLE market_candles ENABLE TRIGGER indicator_source_rows"))


async def test_api_cannot_schedule(prepared: None, api_engine: AsyncEngine) -> None:
    # The runtime API cannot invoke the SECURITY DEFINER mutation even via raw SQL.
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        async with api_engine.begin() as c:
            await c.execute(text("SELECT coalesce_indicator_build_jobs()"))


async def test_scheduled_scan_coalesces_using_same_writer_with_pool_two(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    original_append = append_checkpoint
    original_coalesce = PinnedIndicatorWriter.coalesce
    polled = asyncio.Event()
    pids: list[int] = []

    async def pause(*args: Any) -> None:
        await original_append(*args)
        await asyncio.wait_for(polled.wait(), 2)

    async def observe(writer: PinnedIndicatorWriter) -> int:
        result = await original_coalesce(writer)
        pids.append(writer.backend_pid)
        polled.set()
        return result

    monkeypatch.setattr(scanner, "POLL_SECONDS", 0.02)
    monkeypatch.setattr(scanner, "append_checkpoint", pause)
    monkeypatch.setattr(PinnedIndicatorWriter, "coalesce", observe)
    result = await run_attempt(builder_engine, uuid4(), scheduled=True)
    assert result.status is AttemptStatus.READY and pids and len(set(pids)) == 1
    assert (await slot(migrator_engine))["state"] == "IDLE"


async def test_scheduler_stops_on_orphan_without_repolling(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise DatabaseTimeoutError("fixed")

    monkeypatch.setattr(scanner, "capture_snapshot", fail)
    monkeypatch.setattr(PinnedIndicatorWriter, "finish", fail)
    result = await scheduler.run_scheduler(builder_engine, uuid4(), asyncio.Event())
    assert result is not None and result.status is AttemptStatus.ORPHANED
    assert (await metadata(migrator_engine))["attempts_used"] == 1
    assert (await slot(migrator_engine))["state"] == "RUNNING"


async def test_scheduler_stop_drains_and_idle_wait_is_interruptible(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    stop = asyncio.Event()
    original = run_attempt

    async def drain(*args: Any, **kwargs: Any) -> Any:
        stop.set()
        return await original(*args, **kwargs)

    monkeypatch.setattr(scheduler, "run_attempt", drain)
    assert await scheduler.run_scheduler(builder_engine, uuid4(), stop) is None
    assert (await metadata(migrator_engine))["status"] == "READY"
    monkeypatch.setattr(scheduler, "run_attempt", original)
    stop.clear()
    task = asyncio.create_task(scheduler.run_scheduler(builder_engine, uuid4(), stop))
    await asyncio.sleep(0.1)
    assert not task.done()
    stop.set()
    assert await asyncio.wait_for(task, 1) is None


async def test_scheduler_dispatches_two_unserved_series_in_same_round(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET status='QUEUED'
          WHERE base='ETH' AND timeframe='4h'""")
        )
    stop = asyncio.Event()
    seen: list[Any] = []

    async def dispatch(*args: Any, **kwargs: Any) -> Any:
        result = await run_attempt(*args, **kwargs)
        assert result.status is AttemptStatus.READY
        seen.append(result.job_id)
        if len(seen) == 2:
            stop.set()
        return result

    monkeypatch.setattr(scheduler, "run_attempt", dispatch)
    assert await scheduler.run_scheduler(builder_engine, uuid4(), stop) is None
    assert len(set(seen)) == 2
    assert (await slot(migrator_engine))["dispatch_round"] == 1


async def test_cancel_scheduler_during_scheduled_scan_releases_before_propagation(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    started = asyncio.Event()

    async def pause(*args: Any) -> None:
        await append_checkpoint(*args)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(scanner, "append_checkpoint", pause)
    task = asyncio.create_task(scheduler.run_scheduler(builder_engine, uuid4(), asyncio.Event()))
    try:
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert (await slot(migrator_engine))["state"] == "IDLE"
        assert (await metadata(migrator_engine))["attempts_used"] == 1
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
