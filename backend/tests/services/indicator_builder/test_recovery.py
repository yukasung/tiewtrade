"""Stopped-owner verification refuses uncertainty before any restricted DB reap."""

import asyncio
import json
import sys
from copy import deepcopy
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_source import md as md
from tests.services.indicator_builder.test_attempt import metadata, seed
from tiewtrade.infra.db.errors import DatabaseRoleError, IndicatorBuildOwnershipError
from tiewtrade.infra.indicators import recovery
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.recovery import (
    OwnerStopUnverifiedError,
    ReapResult,
    Runner,
    docker_command,
    reap_verified_container,
    verify_stopped_container,
)
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt
from tiewtrade.services.indicator_builder.supervisor import supervise, worker_environment

CONTAINER = "a" * 64


def stopped() -> dict[str, Any]:
    return {
        "id": CONTAINER,
        "restart": "no",
        "state": {
            "Status": "exited",
            "Running": False,
            "Restarting": False,
            "Dead": False,
            "Pid": 0,
            "StartedAt": "2026-10-11T00:00:00Z",
            "FinishedAt": "2026-10-11T00:01:00Z",
        },
    }


def evidence(owner: UUID) -> Runner:
    async def runner(arguments: tuple[str, ...]) -> str:
        if arguments[0] == "logs":
            return json.dumps(
                {"component": "indicator-builder", "event": "boot", "owner": str(owner)}
            )
        return json.dumps(stopped())

    return runner


@pytest.mark.parametrize(
    "fault",
    [
        "running",
        "pid",
        "restart",
        "restarting",
        "created",
        "wrong_id",
        "wrong_owner",
        "no_boot",
        "multiple_boots",
        "changed",
        "daemon",
        "invalid_json",
        "alias",
    ],
)
async def test_unverified_owner_never_opens_db(fault: str) -> None:
    owner = uuid4()
    current = stopped()
    inspected = 0
    if fault == "running":
        current["state"]["Running"] = True
    if fault == "pid":
        current["state"]["Pid"] = 123
    if fault == "restart":
        current["restart"] = "always"
    if fault == "restarting":
        current["state"]["Restarting"] = True
    if fault == "created":
        current["state"]["Status"] = "created"
    if fault == "wrong_id":
        current["id"] = "b" * 64

    async def runner(arguments: tuple[str, ...]) -> str:
        nonlocal inspected
        if fault == "daemon":
            raise OSError("private daemon failure")
        if fault == "invalid_json":
            return "private invalid payload"
        if arguments[0] == "logs":
            line = json.dumps(
                {
                    "component": "indicator-builder",
                    "event": "boot",
                    "owner": str(uuid4() if fault == "wrong_owner" else owner),
                }
            )
            return (
                ""
                if fault == "no_boot"
                else line + "\n" + line
                if fault == "multiple_boots"
                else line
            )
        inspected += 1
        later = deepcopy(current)
        if fault == "changed" and inspected == 2:
            later["state"]["StartedAt"] = "2026-10-11T00:02:00Z"
        return json.dumps(later)

    with pytest.raises(OwnerStopUnverifiedError) as raised:
        # None proves verification fails before inspecting/using a DB engine.
        await reap_verified_container(
            cast(AsyncEngine, None),
            "alias" if fault == "alias" else CONTAINER,
            owner,
            uuid4(),
            1,
            runner=runner,
        )
    assert "private" not in str(raised.value)


async def test_verified_container_is_checked_twice() -> None:
    owner = uuid4()
    calls = []
    original = evidence(owner)

    async def runner(arguments: tuple[str, ...]) -> str:
        calls.append(arguments)
        return await original(arguments)

    await verify_stopped_container(CONTAINER, owner, runner=runner)
    assert [args[0] for args in calls] == ["inspect", "logs", "inspect"]
    assert all(args[-1] == CONTAINER for args in calls)


@pytest.mark.parametrize("failure", ["timeout", "oversized", "stderr", "cancel"])
async def test_docker_probe_failure_is_bounded_and_does_not_leak_output(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    original = asyncio.create_subprocess_exec
    spawned = asyncio.Event()
    children: list[asyncio.subprocess.Process] = []
    program = (
        "import time; time.sleep(60)"
        if failure in ("timeout", "cancel")
        else "import sys; sys.stdout.write('x'*65537); sys.stdout.flush()"
        if failure == "oversized"
        else "import sys; sys.stderr.write('private docker message'); sys.exit(1)"
    )

    async def spawn(*arguments: Any, **options: Any) -> asyncio.subprocess.Process:
        process = await original(sys.executable, "-c", program, **options)
        children.append(process)
        spawned.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(recovery, "COMMAND_SECONDS", 0.1 if failure == "timeout" else 2)
    task = asyncio.create_task(docker_command(("inspect",)))
    try:
        await asyncio.wait_for(spawned.wait(), 2)
        if failure == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        else:
            with pytest.raises(OwnerStopUnverifiedError) as raised:
                await asyncio.wait_for(task, 3)
            assert "private" not in str(raised.value)
        assert all(p.returncode is not None for p in children)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_reap_lock_busy_does_not_change_metadata(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    owner = uuid4()
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(owner)
        assert claim is not None
        before = await metadata(migrator_engine)
        assert (
            await reap_verified_container(
                migrator_engine,
                CONTAINER,
                owner,
                claim.slot_epoch,
                claim.fence,
                runner=evidence(owner),
            )
            is ReapResult.LOCK_BUSY
        )
        assert await metadata(migrator_engine) == before
        from tiewtrade.infra.indicators.claims import AttemptOutcome

        await writer.finish(AttemptOutcome.OPERATIONAL)


@pytest.mark.parametrize("role", ["builder", "api", "market_data"])
async def test_runtime_role_cannot_use_operator_reap(
    prepared: None,
    builder_engine: AsyncEngine,
    api_engine: AsyncEngine,
    md: AsyncEngine,
    role: str,
) -> None:
    engine = {"builder": builder_engine, "api": api_engine, "market_data": md}[role]
    owner = uuid4()
    with pytest.raises(DatabaseRoleError):
        await reap_verified_container(engine, CONTAINER, owner, uuid4(), 1, runner=evidence(owner))


PAUSED = r"""
import asyncio,json,os,sys
from uuid import UUID
from tiewtrade.services.indicator_builder.attempt import create_builder_engine
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import capture_snapshot,initialize,append_checkpoint
from tiewtrade.core.indicators import IndicatorStream
async def run():
    engine=create_builder_engine()
    owner=UUID(os.environ["TIEWTRADE_INDICATOR_OWNER"])
    async with pinned_indicator_writer(engine,connection_mode="direct") as writer:
        claim=await writer.claim(owner)
        async with indicator_source_session(engine) as source:
            snapshot=await capture_snapshot(source,claim)
            await initialize(writer,claim,snapshot)
            await append_checkpoint(writer,claim,snapshot,
                IndicatorStream(claim.base,claim.quote,claim.timeframe,snapshot.as_of),snapshot.calculation.start)
            print(json.dumps({"owner":str(owner),"pid":writer.backend_pid}),flush=True)
            await asyncio.Event().wait()
asyncio.run(run())
"""


async def test_real_owner_backend_loss_blocks_until_process_exit_and_verified_reap(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    owner = uuid4()
    started = asyncio.Event()
    child: asyncio.subprocess.Process | None = None
    pid = 0

    async def spawn(identity: UUID) -> asyncio.subprocess.Process:
        nonlocal child, pid
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            PAUSED,
            env=worker_environment(identity),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert child.stdout is not None
        line = await asyncio.wait_for(child.stdout.readline(), 3)
        pid = json.loads(line)["pid"]
        started.set()
        return child

    parent = asyncio.create_task(supervise(owner, asyncio.Event(), spawn=spawn))
    try:
        await asyncio.wait_for(started.wait(), 4)
        before = await slot(migrator_engine)
        old_job = await metadata(migrator_engine)
        async with indicator_writer_session(builder_engine) as session:
            await session.execute("SELECT pg_terminate_backend(:pid)", {"pid": pid})
        # The source/CPU process remains alive after the pinned DB session disappears.
        assert child is not None and child.returncode is None
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB

        async def alive(arguments: tuple[str, ...]) -> str:
            state = stopped()
            state["state"]["Running"] = True
            return json.dumps(state)

        with pytest.raises(OwnerStopUnverifiedError):
            await reap_verified_container(
                migrator_engine,
                CONTAINER,
                owner,
                before["slot_epoch"],
                before["fence"],
                runner=alive,
            )
        assert (await slot(migrator_engine))["state"] == "RUNNING"
        parent.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(parent, 3)
        assert await child.wait() != 0
        result = await reap_verified_container(
            migrator_engine,
            CONTAINER,
            owner,
            before["slot_epoch"],
            before["fence"],
            runner=evidence(owner),
        )
        assert result is ReapResult.REAPED
        current = await metadata(migrator_engine)
        for key in (
            "attempts_used",
            "cycle_id",
            "last_served_round",
            "first_eligible_at",
            "availability_deadline",
        ):
            assert current[key] == old_job[key]
        assert current["status"] == "QUEUED" and current["failure_reason"] == "OWNERSHIP_LOST"
        assert (
            await reap_verified_container(
                migrator_engine,
                CONTAINER,
                owner,
                before["slot_epoch"],
                before["fence"],
                runner=evidence(owner),
            )
            is ReapResult.STALE
        )
        async with indicator_writer_session(builder_engine) as session:
            with pytest.raises(IndicatorBuildOwnershipError):
                await session.execute(
                    """SELECT heartbeat_indicator_build_claim(
                  :epoch,:fence,:owner,:job,:gen,:token)""",
                    {
                        "epoch": before["slot_epoch"],
                        "fence": before["fence"],
                        "owner": owner,
                        "job": before["job_id"],
                        "gen": before["generation_id"],
                        "token": before["claim_token"],
                    },
                )
        async with migrator_engine.begin() as c:
            await c.execute(
                text("UPDATE indicator_build_jobs SET retry_not_before=clock_timestamp()")
            )
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            fresh = await writer.claim(uuid4())
            assert fresh is not None and fresh.fence > before["fence"]
            from tiewtrade.infra.indicators.claims import AttemptOutcome

            await writer.finish(AttemptOutcome.OPERATIONAL)
        assert (await metadata(migrator_engine))["attempts_used"] == 2
    finally:
        if not parent.done():
            parent.cancel()
            await asyncio.gather(parent, return_exceptions=True)
