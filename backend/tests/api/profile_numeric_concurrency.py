"""N4: short actual-container numeric/window/crash/GC acceptance on isolated PG."""

import asyncio
import re
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import register
from tests.api.test_numeric_windows import http_clock as http_clock
from tests.api.test_prepared_indicators import admission_state as admission_state
from tests.api.test_prepared_indicators import first
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tests.services.indicator_builder.profile_global_handoff import (
    Probes,
    derived_state,
    evidence,
    no_build,
    outcome,
)
from tests.services.indicator_builder.profile_global_handoff import probes as probes
from tests.services.indicator_builder.test_numeric_windows import (
    BOUNDARY,
    Clock,
    insert_bad,
    job,
    one_series,
)
from tests.services.indicator_builder.test_numeric_windows import db_clock as db_clock
from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.indicators.maintenance import collect
from tiewtrade.infra.indicators.recovery import ReapResult, reap_verified_container
from tiewtrade.infra.indicators.scheduling import coalesce_jobs


@pytest.mark.parametrize("elapsed", [119, 120, 121])
async def test_numeric_deadline_without_gc_or_expired_lease(
    http_clock: Clock,
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    elapsed: int,
) -> None:
    await http_clock(BOUNDARY)
    await one_series(builder_engine, migrator_engine, Timeframe.H4)
    initial = await job(migrator_engine, Timeframe.H4)
    await insert_bad(migrator_engine, Timeframe.H4, initial["desired_start"])
    owner = await probes.start("before_numeric", clocked=True)
    await probes.wait(owner, "barrier")
    held = await slot(migrator_engine)
    moment = BOUNDARY + timedelta(seconds=elapsed)
    await http_clock(moment)
    current = await job(migrator_engine, Timeframe.H4)
    assert held["attempt_deadline"] == BOUNDARY + timedelta(seconds=120)
    assert held["lease_until"] > moment and current["lease_until"] > moment
    async with migrator_engine.connect() as c:
        proof = dict(
            (
                await c.execute(
                    text("""SELECT g.status,g.expires_at,g.source_epoch,
          g.source_fence,s.epoch,s.revision,s.journal_floor,
          indicator_source_triggers_valid() AS triggers
          FROM indicator_generations g CROSS JOIN indicator_source_guard s WHERE g.id=:id"""),
                    {"id": current["current_candidate"]},
                )
            )
            .mappings()
            .one()
        )
    assert proof["status"] == "STAGING" and proof["expires_at"] > moment
    assert proof["source_epoch"] == proof["epoch"] and proof["triggers"]
    assert proof["journal_floor"] <= proof["source_fence"] == proof["revision"]
    await probes.release(owner)
    trace = await probes.finish(owner)
    expected = "FAILED_NUMERIC" if elapsed < 120 else "SUPERSEDED"
    assert outcome(trace) == expected
    assert (
        next(row for row in trace if row.get("step") == "numeric_published")["status"] == expected
    )
    after = await job(migrator_engine, Timeframe.H4)
    assert after["attempts_used"] == 1
    if elapsed >= 120:
        assert after["failure_reason"] == "OWNERSHIP_LOST"
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(text("SELECT count(*) FROM indicator_numeric_failures"))
            ).scalar_one() == 0
    evidence(
        "n4-deadline-" + str(elapsed),
        {"proof": proof, "slot": held, "trace": trace, "after": after},
    )


async def test_multiple_minute_windows_publish_before_deadline(
    http_clock: Clock,
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
) -> None:
    start = BOUNDARY + timedelta(seconds=59)
    await http_clock(start)
    await one_series(builder_engine, migrator_engine, Timeframe.M1)
    initial = await job(migrator_engine, Timeframe.M1)
    await insert_bad(migrator_engine, Timeframe.M1, initial["desired_start"] + timedelta(minutes=5))
    register(client)
    owner = await probes.start("before_numeric", clocked=True)
    await probes.wait(owner, "barrier")
    held = await slot(migrator_engine)
    original = await job(migrator_engine, Timeframe.M1)
    for minute in (1, 2):
        moment = BOUNDARY + timedelta(minutes=minute)
        await http_clock(moment)
        await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
        current = await job(migrator_engine, Timeframe.M1)
        assert current["desired_end"] == initial["desired_end"] + timedelta(minutes=minute)
        assert moment < held["attempt_deadline"] and moment < current["lease_until"]
        for field in (
            "claim_token",
            "cycle_id",
            "attempts_used",
            "current_candidate",
            "first_eligible_at",
            "availability_deadline",
        ):
            assert current[field] == original[field]
    contender = await probes.finish(await probes.start(clocked=True))
    assert outcome(contender) == "LOCK_BUSY"
    no_build(contender)
    await probes.release(owner)
    old_trace = await probes.finish(owner)
    assert outcome(old_trace) == "FAILED_NUMERIC"
    # The still-valid older failure must not mask the newest desired window.
    assert first(client, timeframe="1m").status_code == 503
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    queued = await job(migrator_engine, Timeframe.M1)
    assert queued["status"] == "QUEUED" and queued["cycle_id"] != original["cycle_id"]
    fresh = await probes.start("before_numeric", clocked=True)
    trace = await probes.wait(fresh, "barrier")
    checkpoint = next(row for row in trace if row.get("step") == "checkpoint_attempt")
    assert checkpoint["start"] == queued["desired_start"].isoformat()
    assert checkpoint["end"] == queued["desired_end"].isoformat()
    assert checkpoint["next_open"] == checkpoint["start"]
    await probes.release(fresh)
    final_trace = await probes.finish(fresh)
    assert outcome(final_trace) == "FAILED_NUMERIC"
    assert first(client, timeframe="1m").status_code == 422
    failed = await job(migrator_engine, Timeframe.M1)
    assert failed["attempts_used"] == 1
    for field in ("first_eligible_at", "availability_deadline"):
        assert failed[field] == initial[field]
    no_retry = await probes.finish(await probes.start(clocked=True))
    assert outcome(no_retry) == "NO_JOB"
    no_build(no_retry)
    evidence(
        "n4-live-windows",
        {
            "initial": initial,
            "slot": held,
            "old_trace": old_trace,
            "queued": queued,
            "trace": final_trace,
            "failed": failed,
        },
    )


@pytest.mark.parametrize("fault", ["running", "crash_before", "crash_after"])
async def test_two_replicas_coalesce_latest_window_without_repeating_numeric_input(
    http_clock: Clock,
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    await http_clock(BOUNDARY)
    await one_series(builder_engine, migrator_engine, Timeframe.H4)
    initial = await job(migrator_engine, Timeframe.H4)
    # Retain the real Money error through all three subsequently desired windows.
    await insert_bad(migrator_engine, Timeframe.H4, initial["desired_start"] + timedelta(days=1))
    register(client)

    async def no_venue(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("indicator GET called a venue")

    monkeypatch.setattr(httpx.AsyncClient, "send", no_venue)

    async def get(expected: int) -> None:
        before = await job(migrator_engine, Timeframe.H4)
        derived_before = await derived_state(migrator_engine)
        statements: list[str] = []

        def record_sql(connection: Any, cursor: Any, statement: str, *args: Any) -> None:
            if connection.engine.url.username == "tiewtrade_api":
                statements.append(statement)

        event.listen(Engine, "before_cursor_execute", record_sql)
        try:
            response = first(client)
        finally:
            event.remove(Engine, "before_cursor_execute", record_sql)
        assert statements
        assert all(
            re.search(r"\b(insert|update|delete|truncate|merge)\b", sql, re.I) is None
            for sql in statements
        )
        assert response.status_code == expected, response.text
        assert response.json() == {
            "detail": ("INDICATOR_NUMERIC_ERROR" if expected == 422 else "INDICATOR_DATA_NOT_READY")
        }
        assert "rows" not in response.json()
        assert await job(migrator_engine, Timeframe.H4) == before
        assert await derived_state(migrator_engine) == derived_before

    owner = await probes.start(
        "after_numeric" if fault == "crash_after" else "before_numeric", clocked=True
    )
    started = await probes.wait(owner, "barrier")
    held = await slot(migrator_engine)
    committed = await job(migrator_engine, Timeframe.H4)
    assert committed["attempts_used"] == 1
    if fault == "crash_after":
        assert held["state"] == "IDLE" and committed["status"] == "FAILED_NUMERIC"
        await get(422)
        duplicate = await probes.finish(await probes.start(clocked=True))
        assert outcome(duplicate) == "LOCK_BUSY"  # Commit precedes pinned-session cleanup.
        no_build(duplicate)
        await docker("kill", owner)
        await docker("wait", owner)
        restarted = await probes.finish(await probes.start(clocked=True))
        assert outcome(restarted) == "NO_JOB"
        no_build(restarted)
    else:
        assert held["attempt_deadline"] - BOUNDARY == timedelta(seconds=120)
        duplicate = await probes.finish(await probes.start(clocked=True))
        assert outcome(duplicate) == "LOCK_BUSY"
        no_build(duplicate)

    windows = []
    for count in (1, 2, 3):
        await http_clock(BOUNDARY + count * Timeframe.H4.span)
        # Distinct sessions race the actual coalescer; the owner remains a separate process.
        await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
        await collect(builder_engine)
        current = await job(migrator_engine, Timeframe.H4)
        assert current["desired_end"] == initial["desired_end"] + count * Timeframe.H4.span
        for field in ("first_eligible_at", "availability_deadline"):
            assert current[field] == initial[field]
        if fault != "crash_after":
            for field in ("claim_token", "cycle_id", "attempts_used", "current_candidate"):
                assert current[field] == committed[field]
        windows.append(current)
    await get(503)
    if fault == "running":
        await probes.release(owner)
        old_result = await probes.finish(owner)
        assert outcome(old_result) in ("SUPERSEDED", "RELEASED")
    elif fault == "crash_before":
        await docker("kill", owner)
        await docker("wait", owner)
        blocked = await probes.finish(await probes.start(clocked=True))
        assert outcome(blocked) == "NO_JOB"
        no_build(blocked)
        assert (
            await reap_verified_container(
                migrator_engine, owner, probes.owners[owner], held["slot_epoch"], held["fence"]
            )
            is ReapResult.REAPED
        )

    await http_clock(BOUNDARY + 3 * Timeframe.H4.span + timedelta(seconds=61))
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    newest = await job(migrator_engine, Timeframe.H4)
    fresh = await probes.start("before_numeric", clocked=True)
    fresh_trace = await probes.wait(fresh, "barrier")
    active = await job(migrator_engine, Timeframe.H4)
    assert active["current_candidate"] != committed["current_candidate"]
    assert active["attempts_used"] == (1 if fault == "crash_after" else 2)
    checkpoint = next(row for row in fresh_trace if row.get("step") == "checkpoint_attempt")
    assert checkpoint["start"] == newest["desired_start"].isoformat()
    assert checkpoint["end"] == newest["desired_end"].isoformat()
    assert checkpoint["next_open"] == checkpoint["start"]  # Initial state, no old checkpoint.
    contender = await probes.finish(await probes.start(clocked=True))
    assert outcome(contender) == "LOCK_BUSY"
    no_build(contender)
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(
                text(
                    "SELECT count(*) FROM pg_locks WHERE locktype='advisory' "
                    "AND classid=711 AND objid=1 AND objsubid=2 AND granted"
                )
            )
        ).scalar_one() == 1
    await get(503)
    await probes.release(fresh)
    finished = await probes.finish(fresh)
    assert outcome(finished) == "FAILED_NUMERIC"
    assert next(row for row in finished if row.get("step") == "result")["peak_connections"] == 2
    await get(422)
    failed = await job(migrator_engine, Timeframe.H4)
    for field in ("first_eligible_at", "availability_deadline"):
        assert failed[field] == initial[field]
    # GC a damaged/expired manifest without changing the durable failed key or clock.
    async with migrator_engine.begin() as c:
        await c.execute(
            text("UPDATE indicator_generations SET status='EXPIRED' WHERE id=:id"),
            {"id": failed["current_candidate"]},
        )
    await collect(builder_engine)
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    after_gc = await job(migrator_engine, Timeframe.H4)
    for field in (
        "failed_calculation_key",
        "failed_input_version",
        "cycle_id",
        "attempts_used",
        "first_eligible_at",
        "availability_deadline",
    ):
        assert after_gc[field] == failed[field]
    await get(503)
    for _ in range(2):
        trace = await probes.finish(await probes.start(clocked=True))
        assert outcome(trace) == "NO_JOB"
        no_build(trace)
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(
                text(
                    "SELECT max(n) FROM (SELECT count(*) n FROM indicator_build_jobs "
                    "GROUP BY source,base,quote,timeframe,formula_version) counts"
                )
            )
        ).scalar_one() == 1
    assert (await slot(migrator_engine))["state"] == "IDLE"
    evidence(
        "n4-" + fault,
        {
            "initial": initial,
            "old_trace": started,
            "windows": windows,
            "fresh_trace": finished,
            "after_gc": after_gc,
            "contender": contender,
        },
    )
