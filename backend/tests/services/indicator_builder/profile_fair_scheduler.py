"""S1/S3 real process barriers; explicitly run on the isolated Docker test DB."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from time import monotonic_ns
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tests.services.indicator_builder.profile_global_handoff import (
    Probes,
    enable_other,
    evidence,
    no_build,
    ordered_shutdown,
    outcome,
)
from tests.services.indicator_builder.profile_global_handoff import probes as probes
from tests.services.indicator_builder.test_attempt import metadata, seed
from tests.services.indicator_builder.test_scheduler import change_source
from tests.services.indicator_builder.test_scheduler_validation import EPISODE, cli_retry, unchanged
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.recovery import (
    OwnerStopUnverifiedError,
    ReapResult,
    reap_verified_container,
)
from tiewtrade.infra.indicators.scheduling import coalesce_jobs


@asynccontextmanager
async def coalesce_barrier(engine: AsyncEngine) -> AsyncIterator[dict[str, Any]]:
    """Keep real coalesce writes uncommitted until a competing SQL call is observed."""
    trace: dict[str, Any] = {}
    async with engine.begin() as session:
        trace["blocker_pid"] = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        # Test-only stronger control lock makes claim wait instead of SKIP LOCKED.
        await session.execute(
            text("SELECT id FROM indicator_rollout_control WHERE id=1 FOR UPDATE")
        )
        trace["changed"] = (
            await session.execute(text("SELECT public.coalesce_indicator_build_jobs()"))
        ).scalar_one()
        trace["coalesce_uncommitted_ns"] = monotonic_ns()
        yield trace
        trace["release_ns"] = monotonic_ns()
    trace["coalesce_committed_ns"] = monotonic_ns()


async def wait_for_sql_barrier(
    admin: AsyncEngine,
    trace: dict[str, Any],
    function: str,
) -> None:
    async with asyncio.timeout(12), admin.connect() as observer:
        while True:
            rows = (
                (
                    await observer.execute(
                        text("""SELECT a.pid,a.query,a.wait_event_type,
              pg_blocking_pids(a.pid) AS blockers FROM pg_stat_activity a
              WHERE a.pid<>pg_backend_pid()
                AND :blocker=ANY(pg_blocking_pids(a.pid))
                AND EXISTS(SELECT 1 FROM pg_locks l WHERE l.pid=a.pid
                  AND l.locktype='advisory' AND l.classid=711 AND l.objid=1
                  AND l.objsubid=2 AND l.granted)
                AND EXISTS(SELECT 1 FROM pg_locks l WHERE l.pid=a.pid AND NOT l.granted)"""),
                        {"blocker": trace["blocker_pid"]},
                    )
                )
                .mappings()
                .all()
            )
            if rows:
                trace["expected_function"] = function
                trace["blocked_sql"] = [dict(row) for row in rows]
                trace["wait_observed_ns"] = monotonic_ns()
                return
            # Avoid a transaction-cached activity snapshot on the next poll.
            await observer.rollback()
            await asyncio.sleep(0.005)


async def due_now(admin: AsyncEngine) -> None:
    # This profile proves ordering when A is eligible, not 30/60s timing.
    # Exact backoff boundaries are tested with the controlled DB clock separately.
    async with admin.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs
          SET retry_not_before=clock_timestamp() WHERE base='BTC' AND timeframe='4h'""")
        )


def cpu_start(rows: list[dict[str, Any]]) -> int:
    return int(next(row["time_ns"] for row in rows if row.get("step") == "cpu_start"))


async def test_expired_live_owner_requires_verified_reap_before_manual_recovery(
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET
          first_eligible_at=clock_timestamp()-interval '601 seconds',
          availability_deadline=clock_timestamp()-interval '1 second'
          WHERE base='BTC' AND timeframe='4h'""")
        )
    for _ in range(2):
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None and await writer.claim(uuid4()) is not None
            await writer.finish(AttemptOutcome.TRANSIENT)
        await due_now(migrator_engine)
    owner = await probes.start("before_scan")
    await probes.wait(owner, "barrier")
    before = await metadata(migrator_engine)
    assert before["attempts_used"] == 3 and before["deadline_missed_at"] is not None
    # Accelerate expiry only; the real >150s pause is separately evidenced by G3.
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_slot SET
          lease_until=clock_timestamp()-interval '1 second',
          attempt_deadline=clock_timestamp()-interval '1 second'""")
        )
    held = await slot(migrator_engine)
    request = uuid4()
    assert await cli_retry(before["id"], request) == (12, "REJECTED")
    await coalesce_jobs(builder_engine)
    unchanged(before, await metadata(migrator_engine), (*EPISODE, "attempts_used", "claim_token"))
    assert await slot(migrator_engine) == held
    blocked = await probes.finish(await probes.start())
    assert outcome(blocked) == "LOCK_BUSY"
    no_build(blocked)
    with pytest.raises(OwnerStopUnverifiedError):
        await reap_verified_container(
            migrator_engine, owner, probes.owners[owner], held["slot_epoch"], held["fence"]
        )
    await docker("kill", owner)
    await docker("wait", owner)
    orphan = await probes.finish(await probes.start())
    assert outcome(orphan) == "NO_JOB"
    no_build(orphan)
    assert (
        await reap_verified_container(
            migrator_engine, owner, probes.owners[owner], held["slot_epoch"], held["fence"]
        )
        is ReapResult.REAPED
    )
    failed = await metadata(migrator_engine)
    assert failed["status"] == "FAILED_SUPERSEDED" and failed["attempts_used"] == 3
    unchanged(before, failed, EPISODE)
    assert await cli_retry(before["id"], uuid4()) == (12, "REJECTED")
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_build_jobs SET failed_at="
                "clock_timestamp()-interval '601 seconds' WHERE id=:id"
            ),
            {"id": before["id"]},
        )
    assert await cli_retry(before["id"], request) == (12, "REJECTED")
    assert await cli_retry(before["id"], uuid4()) == (0, "QUEUED")
    recovered = await metadata(migrator_engine)
    unchanged(before, recovered, EPISODE)
    assert recovered["attempts_used"] == 0 and recovered["cycle_id"] != before["cycle_id"]
    successor = await probes.finish(await probes.start())
    assert outcome(successor) == "READY"
    evidence(
        "s4-lease-retry",
        {
            "expired_owner": await probes.logs(owner),
            "blocked": blocked,
            "orphan": orphan,
            "successor": successor,
            "episode_preserved": True,
        },
    )


@pytest.mark.parametrize("expired", [False, True])
async def test_two_replicas_serve_stable_b_before_continuously_superseded_a(
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    expired: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    await enable_other(migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET
          first_eligible_at=statement_timestamp()+make_interval(secs=>:remaining)
            -interval '600 seconds',
          availability_deadline=statement_timestamp()+make_interval(secs=>:remaining)
          WHERE base='BTC' AND timeframe='4h'"""),
            {"remaining": -1 if expired else 300},
        )
    initial = await metadata(migrator_engine)
    traces: list[dict[str, Any]] = []
    previous_end = 0
    for base, attempt_number, expected_round in (
        ("BTC", 1, 1),
        ("ETH", 1, 1),
        ("BTC", 2, 2),
        ("BTC", 3, 3),
    ):
        if attempt_number > 1 or base == "ETH":
            await due_now(migrator_engine)
        holder = await probes.start("before_publish")
        await probes.wait(holder, "barrier")
        held = await slot(migrator_engine)
        async with migrator_engine.connect() as c:
            running = (
                (
                    await c.execute(
                        text("SELECT * FROM indicator_build_jobs WHERE id=:id"),
                        {"id": held["job_id"]},
                    )
                )
                .mappings()
                .one()
            )
            assert running["base"] == base and running["attempts_used"] == attempt_number
            assert running["last_served_round"] == held["dispatch_round"] == expected_round
            assert held["attempt_deadline"] - held["last_heartbeat"] <= timedelta(seconds=120)
        contender = await probes.finish(await probes.start())
        assert outcome(contender) == "LOCK_BUSY"
        no_build(contender)
        assert await slot(migrator_engine) == held
        if base == "BTC":
            await change_source(migrator_engine)
        await probes.release(holder)
        finished = await probes.finish(holder)
        assert outcome(finished) == ("SUPERSEDED" if base == "BTC" else "READY")
        ordered_shutdown(finished)
        assert cpu_start(finished) > previous_end
        previous_end = next(
            row["time_ns"] for row in finished if row.get("step") == "writer_closed"
        )
        traces.append(
            {
                "base": base,
                "attempt": attempt_number,
                "round": expected_round,
                "holder": finished,
                "contender": contender,
            }
        )
    after = await metadata(migrator_engine)
    assert after["status"] == "FAILED_SUPERSEDED" and after["attempts_used"] == 3
    for field in ("first_eligible_at", "availability_deadline", "cycle_id"):
        assert after[field] == initial[field]
    assert (after["deadline_missed_at"] is not None) == expired
    evidence("s1-expired" if expired else "s1-unexpired", {"attempts": traces})


async def test_crash_reap_and_coalesce_preserve_served_round_and_committed_budget(
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    await enable_other(migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs
          SET availability_deadline=availability_deadline-interval '1 second'
          WHERE base='BTC' AND timeframe='4h'""")
        )
    first = await probes.start("before_scan")
    await probes.wait(first, "barrier")
    held = await slot(migrator_engine)
    before = await metadata(migrator_engine)
    assert before["attempts_used"] == before["last_served_round"] == 1
    # Several obsolete pending windows collapse to the DB's newest desired bounds,
    # without replacing the running token/served marker/cycle.
    for hours in (4, 8, 12):
        async with migrator_engine.begin() as c:
            await c.execute(
                text("""UPDATE indicator_build_jobs SET
              desired_start=desired_start-make_interval(hours=>:hours),
              desired_end=desired_end-make_interval(hours=>:hours) WHERE id=:id"""),
                {"hours": hours, "id": before["id"]},
            )
        await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
        current = await metadata(migrator_engine)
        for field in (
            "desired_start",
            "desired_end",
            "claim_token",
            "cycle_id",
            "last_served_round",
            "attempts_used",
            "first_eligible_at",
            "availability_deadline",
        ):
            assert current[field] == before[field]
    busy = await probes.finish(await probes.start())
    assert outcome(busy) == "LOCK_BUSY"
    no_build(busy)
    await docker("kill", first)
    await docker("wait", first)
    orphan = await probes.finish(await probes.start())
    assert outcome(orphan) == "NO_JOB"
    no_build(orphan)
    reaper = None
    try:
        async with coalesce_barrier(migrator_engine) as reap_trace:
            reaper = asyncio.create_task(
                reap_verified_container(
                    migrator_engine, first, probes.owners[first], held["slot_epoch"], held["fence"]
                )
            )
            await wait_for_sql_barrier(migrator_engine, reap_trace, "reap_indicator_build_slot")
            assert not reaper.done()
        reaped = await reaper
        reap_trace["reap_completed_ns"] = monotonic_ns()
    finally:
        if reaper is not None:
            if not reaper.done():
                reaper.cancel()
            await asyncio.gather(reaper, return_exceptions=True)
    assert reaped is ReapResult.REAPED
    after = await metadata(migrator_engine)
    for field in (
        "attempts_used",
        "last_served_round",
        "cycle_id",
        "first_eligible_at",
        "availability_deadline",
    ):
        assert after[field] == before[field]
    await due_now(migrator_engine)
    second = await probes.start("before_publish")
    await probes.wait(second, "barrier")
    b = await slot(migrator_engine)
    assert b["job_id"] != held["job_id"] and b["dispatch_round"] == 1
    await probes.release(second)
    assert outcome(await probes.finish(second)) == "READY"
    # Round advancement races coalescing and another replica's claim.
    starting = None
    try:
        async with coalesce_barrier(migrator_engine) as claim_trace:
            starting = asyncio.create_task(probes.start("before_publish"))
            await wait_for_sql_barrier(migrator_engine, claim_trace, "claim_indicator_build_job")
        third = await starting
    finally:
        # Join Docker startup even on failure so fixture cleanup owns its container ID.
        if starting is not None:
            await asyncio.gather(starting, return_exceptions=True)
    # Keep the winner at publication while the second replica competes.
    await probes.wait(third, "barrier")
    fourth = await probes.start("before_publish")

    async def ready_or_blocked(ident: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(12):
            while True:
                rows = await probes.logs(ident)
                if any(row.get("step") in {"barrier", "result"} for row in rows):
                    return rows
                await asyncio.sleep(0.05)

    pending = await asyncio.gather(ready_or_blocked(third), ready_or_blocked(fourth))
    winners = [
        ident
        for ident, rows in zip((third, fourth), pending, strict=True)
        if any(row.get("step") == "barrier" for row in rows)
    ]
    assert len(winners) == 1
    current = await metadata(migrator_engine)
    assert current["attempts_used"] == current["last_served_round"] == 2
    assert current["claim_token"] is not None and current["claim_token"] != before["claim_token"]
    claim_trace["confirmed_claim_ns"] = monotonic_ns()
    await probes.release(winners[0])
    results = await asyncio.gather(probes.finish(third), probes.finish(fourth))
    assert sorted(outcome(result) for result in results) in (
        ["LOCK_BUSY", "READY"],
        ["NO_JOB", "READY"],
    )
    claims = [row for result in results for row in result if row.get("step") == "claim_committed"]
    assert len(claims) == 1 and claims[0]["job"] == str(held["job_id"])
    assert claims[0]["pid"] == claim_trace["blocked_sql"][0]["pid"]
    for trace in (reap_trace, claim_trace):
        assert (
            trace["coalesce_uncommitted_ns"]
            <= trace["wait_observed_ns"]
            <= trace["release_ns"]
            <= trace["coalesce_committed_ns"]
        )
    assert (await metadata(migrator_engine))["last_served_round"] == 2
    evidence(
        "s3-crash-round",
        {
            "before_scan_owner": await probes.logs(first),
            "orphan_contender": orphan,
            "successors": results,
            "committed_attempt_preserved": True,
            "reap_coalesce_barrier": reap_trace,
            "claim_coalesce_barrier": claim_trace,
        },
    )
