"""Operator-only verified container stop + compare-identity migrator reap."""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import _assert_role, _begin, _execute

COMMAND_SECONDS = 2.0
MAX_OUTPUT_BYTES = 65_536
_CONTAINER_ID = re.compile(r"[0-9a-f]{64}\Z")
_INSPECT = (
    '{"id":{{json .Id}},"state":{{json .State}},"restart":{{json .HostConfig.RestartPolicy.Name}}}'
)
Runner = Callable[[tuple[str, ...]], Awaitable[str]]


class OwnerStopUnverifiedError(InfraError):
    code = "OWNER_STOP_UNVERIFIED"


class ReapResult(StrEnum):
    REAPED = "REAPED"
    STALE = "STALE"
    LOCK_BUSY = "LOCK_BUSY"


async def docker_command(arguments: tuple[str, ...]) -> str:
    process: asyncio.subprocess.Process | None = None
    try:
        async with asyncio.timeout(COMMAND_SECONDS):
            process = await asyncio.create_subprocess_exec(
                "docker",
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                stdin=asyncio.subprocess.DEVNULL,
            )
            assert process.stdout is not None
            output = bytearray()
            while chunk := await process.stdout.read(min(4096, MAX_OUTPUT_BYTES + 1 - len(output))):
                output.extend(chunk)
                if len(output) > MAX_OUTPUT_BYTES:
                    raise OwnerStopUnverifiedError("owner stop unverified")
            if await process.wait() != 0:
                raise OwnerStopUnverifiedError("owner stop unverified")
            return output.decode("utf-8")
    except asyncio.CancelledError:
        raise
    except Exception:
        raise OwnerStopUnverifiedError("owner stop unverified") from None
    finally:
        if process is not None and process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            async with asyncio.timeout(COMMAND_SECONDS):
                await process.wait()


async def verify_stopped_container(
    container: str,
    owner: UUID,
    *,
    runner: Runner = docker_command,
) -> None:
    if not _CONTAINER_ID.fullmatch(container) or not isinstance(owner, UUID):
        raise OwnerStopUnverifiedError("owner stop unverified")
    try:
        first = json.loads(await runner(("inspect", "--format", _INSPECT, container)))
        state = first["state"]
        started = datetime.fromisoformat(state["StartedAt"])
        finished = datetime.fromisoformat(state["FinishedAt"])
        if (
            first["id"] != container
            or first["restart"] != "no"
            or state["Status"] != "exited"
            or state["Running"] is not False
            or state["Restarting"] is not False
            or state["Dead"] is not False
            or state["Pid"] != 0
            or started.tzinfo is None
            or finished.tzinfo is None
            or started.year <= 1970
            or finished < started
        ):
            raise OwnerStopUnverifiedError("owner stop unverified")
        logs = await runner(("logs", "--since", state["StartedAt"], "--tail", "1000", container))
        owners: list[str] = []
        for line in logs.splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if (
                isinstance(entry, dict)
                and entry.get("component") == "indicator-builder"
                and entry.get("event") == "boot"
            ):
                owners.append(entry.get("owner", ""))
        if owners != [str(owner)]:
            raise OwnerStopUnverifiedError("owner stop unverified")
        # A name/old boot/daemon restart is never sufficient evidence of this owner stopping.
        second = json.loads(await runner(("inspect", "--format", _INSPECT, container)))
        if second != first:
            raise OwnerStopUnverifiedError("owner stop unverified")
    except asyncio.CancelledError:
        raise
    except Exception:
        raise OwnerStopUnverifiedError("owner stop unverified") from None


async def reap_verified_container(
    engine: AsyncEngine,
    container: str,
    owner: UUID,
    epoch: UUID,
    fence: int,
    *,
    runner: Runner = docker_command,
) -> ReapResult:
    if not isinstance(epoch, UUID) or type(fence) is not int or not 0 <= fence <= 2**63 - 1:
        raise OwnerStopUnverifiedError("owner stop unverified")
    await verify_stopped_container(container, owner, runner=runner)
    # Never reconnect/retry ambiguous commit. The caller stops and investigates.
    async with asyncio.timeout(2):
        async with _begin(engine, cleanup_seconds=2) as connection:
            await _assert_role(connection, DatabaseRole.MIGRATOR)
            await _execute(
                connection,
                """SELECT set_config('lock_timeout','200ms',true),
                set_config('statement_timeout','500ms',true)""",
                None,
            )
            result = ReapResult(
                (
                    await _execute(
                        connection,
                        "SELECT public.reap_indicator_build_slot(:owner,:epoch,:fence)",
                        {"owner": owner, "epoch": epoch, "fence": fence},
                    )
                ).scalar_one()
            )
        return result
