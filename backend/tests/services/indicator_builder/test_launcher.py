"""Real supervised process shutdown, sanitized boot output and role separation."""

import asyncio
import json
import os
import signal
import sys
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.indicators import scan as scanner
from tiewtrade.infra.indicators.staging import append_checkpoint
from tiewtrade.services.indicator_builder import supervisor
from tiewtrade.services.indicator_builder.worker import serve


def test_child_environment_excludes_privileged_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIEWTRADE_DATABASE_URL_MIGRATOR", "private migrator")
    monkeypatch.setenv("TIEWTRADE_DATABASE_URL_AUTH", "private auth")
    monkeypatch.setenv("TIEWTRADE_SEALING_KEY_VENUE_API_SECRET", "private venue")
    monkeypatch.setenv(DatabaseRole.INDICATOR_BUILDER.url_variable, "builder only")
    owner = uuid4()
    environment = supervisor.worker_environment(owner)
    assert environment[DatabaseRole.INDICATOR_BUILDER.url_variable] == "builder only"
    assert environment["TIEWTRADE_INDICATOR_OWNER"] == str(owner)
    assert not any("private" in value for value in environment.values())


async def test_each_launcher_boot_has_new_owner_and_no_restart(
    prepared: None,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode='LEGACY'"))
    owners = []
    for _ in range(2):
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tiewtrade.services.indicator_builder.main",
            "run",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert process.stdout is not None
            boot = json.loads(await asyncio.wait_for(process.stdout.readline(), 3))
            owners.append(boot["owner"])
            assert boot["event"] == "boot"
            worker = json.loads(await asyncio.wait_for(process.stdout.readline(), 3))
            assert worker["event"] == "worker_started" and worker["owner"] == owners[-1]
            process.send_signal(signal.SIGTERM)
            output, error = await asyncio.wait_for(process.communicate(), 4)
            assert process.returncode == 0
            stopped = json.loads(output)
            assert stopped["event"] == "stopped" and stopped["owner"] == owners[-1]
            assert not error and "postgresql" not in output.decode()
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
    assert owners[0] != owners[1]


@pytest.mark.parametrize("cancel", [False, True])
async def test_supervisor_force_stop_waits_for_real_child_exit(
    monkeypatch: pytest.MonkeyPatch,
    cancel: bool,
) -> None:
    started = asyncio.Event()
    child: asyncio.subprocess.Process | None = None

    async def spawn(owner: Any) -> asyncio.subprocess.Process:
        nonlocal child
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            "print('READY',flush=True); time.sleep(60)",
            stdout=asyncio.subprocess.PIPE,
        )
        assert child.stdout is not None
        await child.stdout.readline()
        started.set()
        return child

    monkeypatch.setattr(supervisor, "DRAIN_SECONDS", 0.05)
    stop = asyncio.Event()
    task = asyncio.create_task(supervisor.supervise(uuid4(), stop, spawn=spawn))
    try:
        await asyncio.wait_for(started.wait(), 2)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
        else:
            stop.set()
            result = await asyncio.wait_for(task, 2)
            assert result.forced and result.exit_code != 0
        assert child is not None and child.returncode is not None
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_worker_stop_drains_current_attempt_and_publishes_ready(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    started, resume, stop = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def pause(*args: Any) -> None:
        await append_checkpoint(*args)
        started.set()
        await resume.wait()

    monkeypatch.setattr(scanner, "append_checkpoint", pause)
    task = asyncio.create_task(serve(uuid4(), stop))
    try:
        await asyncio.wait_for(started.wait(), 2)
        stop.set()
        assert not task.done()
        resume.set()
        assert await asyncio.wait_for(task, 3) == 0
        assert (await metadata(migrator_engine))["status"] == "READY"
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_cli_failure_does_not_print_config_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = dict(os.environ)
    environment[DatabaseRole.INDICATOR_BUILDER.url_variable] = "private broken database URL"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tiewtrade.services.indicator_builder.main",
        "run",
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, error = await asyncio.wait_for(process.communicate(), 4)
    assert process.returncode == 13
    assert "private" not in (output + error).decode() and "Traceback" not in error.decode()
