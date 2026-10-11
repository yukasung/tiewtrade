"""F4/F5 exact DB-clock retry limits and real-role CLI crash recovery."""

import asyncio
import json
import sys
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_numeric_windows import BOUNDARY, Clock, job, one_series
from tests.services.indicator_builder.test_numeric_windows import db_clock as db_clock
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.indicators import scan
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.scheduling import coalesce_jobs
from tiewtrade.infra.indicators.session import IndicatorSourceSession
from tiewtrade.infra.indicators.staging import StagingSnapshot, append_checkpoint
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt
from tiewtrade.services.indicator_builder.supervisor import worker_environment


async def test_exact_backoff_fresh_aborted_sessions_and_terminal_restart(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = BOUNDARY - timedelta(hours=1)
    await db_clock(start)
    await one_series(builder_engine, migrator_engine, Timeframe.H4)
    initial = await job(migrator_engine, Timeframe.H4)
    sources: list[IndicatorSourceSession] = []
    pids: list[int] = []
    states: list[IndicatorStream] = []
    snapshots: list[StagingSnapshot] = []

    async def capture_state(*args: Any, **kwargs: Any) -> None:
        snapshots.append(args[2])
        states.append(args[3])
        await append_checkpoint(*args, **kwargs)

    async def abort(session: IndicatorSourceSession, *args: object) -> Any:
        sources.append(session)
        pid: int = (await session.execute("SELECT pg_backend_pid()")).scalar_one()
        pids.append(pid)
        # Real PostgreSQL transaction abort, translated by the production session.
        await session.execute("""DO $$ BEGIN RAISE EXCEPTION
          USING ERRCODE='40001',MESSAGE='private-transient-marker'; END $$""")
        raise AssertionError("abort did not occur")

    monkeypatch.setattr(scan, "fetch_rows", abort)
    monkeypatch.setattr(scan, "append_checkpoint", capture_state)
    elapsed = 0
    generations = set()
    for used in (1, 2, 3):
        await db_clock(start + timedelta(seconds=elapsed))
        result = await run_attempt(builder_engine, uuid4())
        assert result.status is AttemptStatus.RELEASED
        assert result.reason is AttemptOutcome.TRANSIENT
        generations.add(result.generation_id)
        current = await job(migrator_engine, Timeframe.H4)
        assert current["attempts_used"] == used
        for field in ("cycle_id", "first_eligible_at", "availability_deadline"):
            assert current[field] == initial[field]
        assert sources[-1]._connection.closed
        if used < 3:
            delay = 30 if used == 1 else 60
            due = start + timedelta(seconds=elapsed + delay)
            assert current["retry_not_before"] == due
            await builder_engine.dispose()  # Actual reconnect with durable budget/backoff.
            await db_clock(due - timedelta(microseconds=1))
            assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
            assert (await job(migrator_engine, Timeframe.H4))["attempts_used"] == used
            elapsed += delay
    assert len(generations) == len(set(pids)) == len(sources) == 3
    assert len({id(state) for state in states}) == 3
    assert len({id(snapshot) for snapshot in snapshots}) == 3
    assert [snapshot.as_of for snapshot in snapshots] == [
        start + timedelta(seconds=seconds) for seconds in (0, 30, 90)
    ]
    assert current["status"] == "FAILED_TRANSIENT"
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    await builder_engine.dispose()
    await db_clock(start + timedelta(seconds=1000))
    await coalesce_jobs(builder_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    after = await job(migrator_engine, Timeframe.H4)
    assert after["attempts_used"] == 3 and after["cycle_id"] == initial["cycle_id"]


async def failed_job(builder: AsyncEngine, admin: AsyncEngine) -> dict[str, Any]:
    await one_series(builder, admin, Timeframe.H4)
    async with pinned_indicator_writer(builder, connection_mode="direct") as writer:
        assert writer is not None and await writer.claim(uuid4()) is not None
        await writer.finish(AttemptOutcome.OPERATIONAL)
    return await job(admin, Timeframe.H4)


async def cli(
    identity: UUID | str, request: UUID | str, program: str | None = None
) -> asyncio.subprocess.Process:
    args = (
        ["-m", "tiewtrade.services.indicator_builder.main"] if program is None else ["-c", program]
    )
    return await asyncio.create_subprocess_exec(
        sys.executable,
        *args,
        "retry",
        "--job-id",
        str(identity),
        "--request-id",
        str(request),
        env=worker_environment(uuid4()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def answer(process: asyncio.subprocess.Process, expected: str) -> None:
    try:
        output, error = await asyncio.wait_for(process.communicate(), 5)
        assert process.returncode == (0 if expected == "QUEUED" else 12)
        assert not error
        assert json.loads(output) == {
            "component": "indicator-builder",
            "event": "retry",
            "status": expected,
        }
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@pytest.mark.parametrize("offset", [-1, 0, 1])
async def test_actual_cli_exact_cooldown_and_ready_recovery(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    offset: int,
) -> None:
    await db_clock(BOUNDARY - timedelta(hours=1))
    before = await failed_job(builder_engine, migrator_engine)
    await db_clock(before["failed_at"] + timedelta(seconds=600, microseconds=offset))
    request = uuid4()
    expected = "REJECTED" if offset < 0 else "QUEUED"
    await answer(await cli(before["id"], request), expected)
    await answer(await cli(before["id"], request), expected)
    if offset < 0:
        assert (await job(migrator_engine, Timeframe.H4))["cycle_id"] == before["cycle_id"]
        await db_clock(before["failed_at"] + timedelta(seconds=601))
        await answer(await cli(before["id"], request), "REJECTED")
        await answer(await cli(before["id"], uuid4()), "QUEUED")
    queued = await job(migrator_engine, Timeframe.H4)
    assert queued["cycle_id"] != before["cycle_id"] and queued["attempts_used"] == 0
    for field in ("first_eligible_at", "availability_deadline", "last_served_round"):
        assert queued[field] == before[field]
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    ready = await job(migrator_engine, Timeframe.H4)
    await answer(await cli(before["id"], uuid4()), "REJECTED")
    after = await job(migrator_engine, Timeframe.H4)
    assert after == ready
    assert after["availability_deadline"] == before["availability_deadline"]


@pytest.mark.parametrize("argument", ["job", "request"])
async def test_retry_cli_rejects_injection_without_echo_or_database_change(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    argument: str,
) -> None:
    await db_clock(BOUNDARY - timedelta(hours=1))
    before = await failed_job(builder_engine, migrator_engine)
    payload = "private-secret-marker'; DROP TABLE indicator_build_jobs; --"
    process = await cli(
        payload if argument == "job" else before["id"],
        payload if argument == "request" else uuid4(),
    )
    try:
        output, error = await asyncio.wait_for(process.communicate(), 5)
        assert process.returncode == 2 and not output
        assert b"UUID_REQUIRED" in error
        assert b"private-secret-marker" not in error and b"Traceback" not in error
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert await job(migrator_engine, Timeframe.H4) == before


@pytest.mark.parametrize("committed", [False, True])
async def test_actual_retry_cli_crash_before_after_commit(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    committed: bool,
) -> None:
    await db_clock(BOUNDARY - timedelta(hours=1))
    before = await failed_job(builder_engine, migrator_engine)
    await db_clock(before["failed_at"] + timedelta(seconds=601))
    request = uuid4()
    program = """
import asyncio,os
import tiewtrade.services.indicator_builder.main as main
from tiewtrade.infra.indicators.session import IndicatorWriterSession
async def barrier():
    os.write(1,b'boundary\\n')
    await asyncio.Event().wait()
"""
    if committed:
        program += """
original=main.retry_job
async def wrapped(*args):
    result=await original(*args)
    await barrier()
    return result
main.retry_job=wrapped
"""
    else:
        program += """
original=IndicatorWriterSession.execute
async def wrapped(self,statement,parameters=None):
    result=await original(self,statement,parameters)
    if 'SELECT public.retry_indicator_build_job(' in statement:
        await barrier()
    return result
IndicatorWriterSession.execute=wrapped
"""
    program += "raise SystemExit(main.main())\n"
    process = await cli(before["id"], request, program)
    try:
        assert process.stdout is not None
        assert await asyncio.wait_for(process.stdout.readline(), 4) == b"boundary\n"
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    observed = await job(migrator_engine, Timeframe.H4)
    assert (observed["cycle_id"] != before["cycle_id"]) is committed
    # Re-send the exact command after inspecting committed state, then duplicate it.
    await asyncio.gather(
        answer(await cli(before["id"], request), "QUEUED"),
        answer(await cli(before["id"], request), "QUEUED"),
    )
    after = await job(migrator_engine, Timeframe.H4)
    assert after["cycle_id"] != before["cycle_id"]
    if committed:
        assert after["cycle_id"] == observed["cycle_id"]
    async with migrator_engine.connect() as c:
        count: int = (
            await c.execute(
                text("SELECT count(*) FROM indicator_retry_requests WHERE request_id=:request"),
                {"request": request},
            )
        ).scalar_one()
        assert count == 1
    assert after["availability_deadline"] == before["availability_deadline"]
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
