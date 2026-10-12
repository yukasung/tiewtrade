"""Explicit host-Docker/isolated-PG integration gate; not collected by ordinary test_*.

Run this file explicitly against the F-11 test Postgres, never the application DB.
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tests.services.indicator_builder.test_recovery import PAUSED
from tiewtrade.infra.indicators.recovery import (
    OwnerStopUnverifiedError,
    ReapResult,
    reap_verified_container,
)
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


async def docker(*arguments: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, error = await asyncio.wait_for(process.communicate(), 10)
    assert process.returncode == 0, error.decode()
    return output.decode().strip()


async def test_real_stopped_container_and_owner_boot_gate_reap_and_fresh_ready(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    owner = uuid4()
    root = Path(__file__).resolve().parents[4]
    program = PAUSED.replace(
        "asyncio.run(run())",
        "from tiewtrade.services.indicator_builder.events import record\n"
        'record("boot",UUID(os.environ["TIEWTRADE_INDICATOR_OWNER"]))\nasyncio.run(run())',
    )
    container = await docker(
        "run",
        "-d",
        "--network",
        "tiewtrade-f11-test-net",
        "--restart",
        "no",
        "--name",
        f"f11-owner-proof-{owner.hex}",
        "-v",
        f"{root}:/workspace:ro",
        "-e",
        "PYTHONPATH=/workspace/backend/src",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        f"TIEWTRADE_INDICATOR_OWNER={owner}",
        "-e",
        "TIEWTRADE_DATABASE_URL_INDICATOR_BUILDER="
        "postgresql+asyncpg://tiewtrade_indicator_builder:dev_indicator_builder@"
        "tiewtrade-f11-test-postgres:5432/tiewtrade",
        "tiewtrade-api:latest",
        "python",
        "-c",
        program,
    )
    try:
        async with asyncio.timeout(8):
            while True:
                old_slot = await slot(migrator_engine)
                old_job = await metadata(migrator_engine)
                if old_slot["owner_instance"] == owner and old_job["current_candidate"] is not None:
                    break
                await asyncio.sleep(0.05)
        async with indicator_writer_session(builder_engine) as session:
            await session.execute(
                "SELECT pg_terminate_backend(:pid)", {"pid": old_slot["owner_backend_pid"]}
            )
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
        with pytest.raises(OwnerStopUnverifiedError):
            await reap_verified_container(
                migrator_engine, container, owner, old_slot["slot_epoch"], old_slot["fence"]
            )
        await docker("kill", container)
        await docker("wait", container)
        with pytest.raises(OwnerStopUnverifiedError):
            await reap_verified_container(
                migrator_engine, container, uuid4(), old_slot["slot_epoch"], old_slot["fence"]
            )
        command = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tiewtrade.services.indicator_builder.main",
            "reap",
            "--container",
            container,
            "--owner",
            str(owner),
            "--slot-epoch",
            str(old_slot["slot_epoch"]),
            "--fence",
            str(old_slot["fence"]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, error = await asyncio.wait_for(command.communicate(), 10)
        assert command.returncode == 0 and not error
        assert json.loads(output)["status"] == ReapResult.REAPED.value
        recovered = await metadata(migrator_engine)
        for key in (
            "attempts_used",
            "cycle_id",
            "last_served_round",
            "first_eligible_at",
            "availability_deadline",
        ):
            assert recovered[key] == old_job[key]
        async with migrator_engine.begin() as c:
            await c.execute(
                text("UPDATE indicator_build_jobs SET retry_not_before=clock_timestamp()")
            )
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
        assert (await slot(migrator_engine))["fence"] > old_slot["fence"]
        logs = await docker("logs", container)
        boot = json.loads(logs.splitlines()[0])
        assert boot["owner"] == str(owner)
    finally:
        # Immutable ID resolves only the disposable test container this test created.
        await docker("rm", "-f", container)
