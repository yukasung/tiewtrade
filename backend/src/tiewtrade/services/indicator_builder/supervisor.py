"""One child per boot. Stop/wait proves local termination; never restart or reap."""

import asyncio
import os
import signal
import sys
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID

from tiewtrade.infra.db import DatabaseRole
from tiewtrade.services.indicator_builder.attempt import ATTEMPT_SECONDS, CLEANUP_SECONDS

# Does not extend the DB attempt deadline. Reserve source/terminal/pinned cleanup.
DRAIN_SECONDS = ATTEMPT_SECONDS + 3 * CLEANUP_SECONDS
STOP_SECONDS = 2.0
WorkerSpawner = Callable[[UUID], Awaitable[asyncio.subprocess.Process]]
_OS_ENV = frozenset(
    {
        "PATH",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "HOME",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "SYSTEMROOT",
        "WINDIR",
    }
)


@dataclass(frozen=True, slots=True)
class SupervisorResult:
    owner: UUID
    exit_code: int
    forced: bool


def worker_environment(owner: UUID) -> dict[str, str]:
    # Do not inherit migrator/auth/engine/venue credentials into the worker.
    environment = {name: value for name, value in os.environ.items() if name.upper() in _OS_ENV}
    variable = DatabaseRole.INDICATOR_BUILDER.url_variable
    if variable in os.environ:
        environment[variable] = os.environ[variable]
    if "TIEWTRADE_CATALOG_DEPLOYMENT_GENERATION" in os.environ:
        environment["TIEWTRADE_CATALOG_DEPLOYMENT_GENERATION"] = os.environ[
            "TIEWTRADE_CATALOG_DEPLOYMENT_GENERATION"
        ]
    environment["TIEWTRADE_INDICATOR_OWNER"] = str(owner)
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


async def _kill_and_wait(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.kill()
        # wait still must establish that the process has exited.
    async with asyncio.timeout(STOP_SECONDS):
        await process.wait()


async def spawn_worker(owner: UUID) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tiewtrade.services.indicator_builder.worker",
        env=worker_environment(owner),
        stdin=asyncio.subprocess.DEVNULL,
    )


async def supervise(
    owner: UUID,
    stop: asyncio.Event,
    *,
    spawn: WorkerSpawner = spawn_worker,
) -> SupervisorResult:
    if type(owner) is not UUID:
        raise ValueError("builder owner UUID required")
    process = await spawn(owner)
    exited = asyncio.create_task(process.wait())
    requested = asyncio.create_task(stop.wait())
    forced = False
    try:
        await asyncio.wait({exited, requested}, return_when=asyncio.FIRST_COMPLETED)
        if not exited.done():
            with suppress(ProcessLookupError):
                # POSIX worker drains on SIGTERM. Windows termination still leaves
                # durable orphan ownership, which requires operator recovery.
                process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(asyncio.shield(exited), DRAIN_SECONDS)
            except TimeoutError:
                forced = True
                await _kill_and_wait(process)
        return SupervisorResult(owner, await exited, forced)
    except BaseException:
        # Parent task cancellation cannot leave a child computing unattended.
        await _kill_and_wait(process)
        raise
    finally:
        requested.cancel()
        await asyncio.gather(requested, return_exceptions=True)
        if not exited.done():
            exited.cancel()
            await asyncio.gather(exited, return_exceptions=True)
