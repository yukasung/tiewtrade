"""Approved NC12 profile; explicit test configuration, never a product capacity cap."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tiewtrade.infra.db import DatabaseRole

NAME = "PAPER_INTERNAL20_V1"
NAME_V2 = "PAPER_INTERNAL20_V2"
NAME_V3 = "PAPER_INTERNAL20_V3"


@dataclass(frozen=True, slots=True)
class Phase:
    rate: int
    cycles_per_owner: int
    seconds: int

    @property
    def commands(self) -> int:
        return 20 * self.cycles_per_owner * 5


PHASES = {
    "SMOKE": Phase(2, 6, 300),
    "W1": Phase(2, 36, 1800),
    "W2": Phase(20, 120, 600),
    "W3": Phase(2, 282, 14400),
    "W2_OVERFLOW": Phase(20, 0, 0),
}


PROFILES = {
    NAME: PHASES,
    NAME_V2: {**PHASES, "W2": Phase(10, 120, 1200)},
}

PROFILES[NAME_V3] = {**PROFILES[NAME_V2], "W3": Phase(2, 30, 1800)}


def selected(args: argparse.Namespace) -> bool:
    profile = getattr(args, "acceptance_profile", None)
    if profile is not None and profile not in PROFILES:
        raise ValueError("unknown Paper acceptance profile")
    return profile is not None


def processing_acceptance(
    args: argparse.Namespace, p95: float | None, p99: float | None
) -> dict[str, Any]:
    """Engine timing only; preserve snapshot/protection/recovery and default thresholds."""
    pilot = selected(args)
    p95_limit, p99_limit = (0.5, 2.0) if pilot else (0.25, 1.0)
    applicable = args.phase != "W2_OVERFLOW"
    passed = not applicable or (
        p95 is not None and p99 is not None and 0 <= p95 <= p95_limit and 0 <= p99 <= p99_limit
    )
    target_passed = not applicable or (
        p95 is not None and p99 is not None and 0 <= p95 <= 0.25 and 0 <= p99 <= 1.0
    )
    return {
        "revision": "NC12_SECTION21_PILOT"
        if getattr(args, "acceptance_profile", None) == NAME_V3
        else "NC12_SECTION18_PILOT"
        if getattr(args, "acceptance_profile", None) == NAME_V2
        else "NC12_SECTION16_PILOT"
        if pilot
        else "F15_DEFAULT",
        "applicable": applicable,
        "p95_limit_seconds": p95_limit,
        "p99_limit_seconds": p99_limit,
        "target_p95_seconds": 0.25,
        "target_p99_seconds": 1.0,
        "passed": passed,
        "target_passed": target_passed,
        "performance_warning": pilot and passed and not target_passed,
    }


def validate(args: argparse.Namespace) -> Phase | None:
    if not selected(args):
        return None
    if getattr(args, "worker_only", False):
        if (
            getattr(args, "r8_claim_budget", False) is not True
            or getattr(args, "coordinate_claims", False) is not True
        ):
            raise ValueError("internal Paper worker requires the approved R8/V2 runtime")
        return None
    phase_name = getattr(args, "phase", None)
    phase = (
        PROFILES[args.acceptance_profile].get(phase_name) if isinstance(phase_name, str) else None
    )
    if phase is None:
        raise ValueError("unsupported internal Paper phase")
    expected = {
        "owners": 20,
        "baseline_orders": 20,
        "workers": 20,
        "rate": phase.rate,
        "cycles_per_owner": phase.cycles_per_owner,
        "parent_poll_limit": 4,
    }
    if any(
        type(getattr(args, key, None)) is not int or getattr(args, key) != value
        for key, value in expected.items()
    ):
        raise ValueError("internal Paper profile parameters differ from NC12")
    if any(
        getattr(args, key, None) is not True
        for key in (
            "r8_claim_budget",
            "coordinate_claims",
            "publisher_heartbeat_per_book",
            "final_tail_drain",
        )
    ):
        raise ValueError("internal Paper profile requires the approved runtime flags")
    if getattr(args, "baseline_manifest", None) is not None:
        raise ValueError("internal Paper phases require a fresh isolated baseline")
    return phase


def guard_database(environment: dict[str, str]) -> str:
    """Never let the opt-in profile mutate a normal development/production DB."""
    targets = set()
    for role in ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"):
        parsed = urlparse(environment.get(f"TIEWTRADE_DATABASE_URL_{role}", ""))
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.path.startswith(
            "/tiewtrade_internal20_"
        ):
            raise ValueError("internal Paper profile requires a local isolated internal20 database")
        targets.add((parsed.hostname, parsed.port, parsed.path))
    if len(targets) != 1:
        raise ValueError("internal Paper profile role databases differ")
    return targets.pop()[2].removeprefix("/")


def manifest(args: argparse.Namespace) -> dict[str, object] | None:
    phase = validate(args)
    if phase is None:
        return None
    return {
        "name": args.acceptance_profile,
        "owners": 20,
        "baseline_orders_per_owner": 20,
        "workers": 20,
        "phase": args.phase,
        **asdict(phase),
        "expected_commands": phase.commands,
        "scope": "short internal stability; four-hour Release validation pending"
        if args.acceptance_profile == NAME_V3 and args.phase == "W3"
        else "internal pilot only; not the 100-account profile or F17 Completed",
        "intake": "diagnostic internal commands" if args.phase == "SMOKE" else "authenticated HTTP",
    }


def fault_schedule_for(profile_name: str) -> Path:
    if profile_name not in PROFILES:
        raise ValueError("unknown Paper acceptance profile")
    return Path(__file__).with_name(
        "w3_fault_schedule_internal30.json" if profile_name == NAME_V3 else "w3_fault_schedule.json"
    )


def validate_fault_schedule(path: Path, *, profile_name: str = NAME) -> None:
    expected = fault_schedule_for(profile_name)
    if path.read_bytes() != expected.read_bytes():
        raise ValueError("internal Paper W3 requires the unchanged approved fault schedule")


@asynccontextmanager
async def activated_protocols(
    engine: AsyncEngine, *, protections: bool = False
) -> AsyncIterator[None]:
    """Scoped activation in a guarded isolated fixture; restore every original flag."""
    async with engine.begin() as connection:
        previous = dict(
            (
                await connection.execute(
                    text("""SELECT publication_enabled,
            financial_enabled,admission_enabled FROM risk_protocol_control""")
                )
            )
            .mappings()
            .one()
        )
        protection: bool = (
            await connection.execute(text("SELECT enabled FROM paper_protection_protocol"))
        ).scalar_one()
        await connection.execute(
            text("""UPDATE risk_protocol_control SET
            publication_enabled=true,financial_enabled=true,admission_enabled=true""")
        )
        if protections:
            await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
    try:
        yield
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET
                publication_enabled=:publication_enabled,financial_enabled=:financial_enabled,
                admission_enabled=:admission_enabled"""),
                previous,
            )
            if protections:
                await connection.execute(
                    text("UPDATE paper_protection_protocol SET enabled=:value"),
                    {"value": protection},
                )


def readonly_admin(
    *, source_variable: str = "TIEWTRADE_TEST_ADMIN_URL", database: str | None = None
) -> AsyncEngine:
    """Global test observer only; never handed to API/engine workers."""
    expected = guard_database(dict(os.environ))
    value = os.environ.get(source_variable, "")
    supplied = urlparse(value)
    role = urlparse(os.environ[DatabaseRole.MIGRATOR.url_variable])
    if (supplied.hostname, supplied.port, supplied.path) != (role.hostname, role.port, role.path):
        raise ValueError("internal restore observer must target the same isolated local database")
    target = expected if database is None else database
    if not target.startswith("tiewtrade_internal20_"):
        raise ValueError("internal restore observer requires an isolated target")
    return create_async_engine(
        make_url(value).set(database=target).render_as_string(hide_password=False),
        hide_parameters=True,
        execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True},
    )


async def require_empty_database() -> None:
    observer = readonly_admin()
    try:
        async with observer.connect() as connection:
            occupied: bool = (
                await connection.execute(
                    text("""SELECT EXISTS(SELECT 1 FROM users)
                OR EXISTS(SELECT 1 FROM paper_wallets)""")
                )
            ).scalar_one()
        if occupied:
            raise ValueError("internal Paper campaign requires a newly created empty database")
    finally:
        await observer.dispose()


class EnvironmentNotReadyError(RuntimeError):
    """The fixed environment admission check could not establish readiness."""


def host_load() -> tuple[float, float, float]:
    values = os.getloadavg()
    if (
        not isinstance(values, tuple)
        or len(values) != 3
        or any(
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
            for value in values
        )
    ):
        raise EnvironmentNotReadyError("HOST_LOAD_INVALID")
    return values


def host_observation(root: Path) -> dict[str, Any]:
    cpu = os.cpu_count()
    free = shutil.disk_usage(root).free
    if type(cpu) is not int or cpu <= 0:
        raise EnvironmentNotReadyError("HOST_CPU_INVALID")
    if type(free) is not int or free < 0:
        raise EnvironmentNotReadyError("HOST_DISK_INVALID")
    return {
        "at": datetime.now(UTC).isoformat(),
        "monotonic": monotonic(),
        "logical_cpu": cpu,
        "free_bytes": free,
        "load": host_load(),
    }


async def read_host_command(*command: str) -> str:
    """Only read-only native observers call this; reap their children on failure."""
    process = await asyncio.create_subprocess_exec(
        *command,
        env={**os.environ, "LC_ALL": "C"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(5):
            stdout, _ = await process.communicate()
        if process.returncode != 0:
            raise EnvironmentNotReadyError("HOST_SENSOR_COMMAND_FAILED")
        return stdout.decode("utf-8")
    except BaseException:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
        raise


def parse_cpu_idle(output: str) -> float:
    readings = re.findall(
        r"CPU usage:.*?([+-]?(?:[0-9]+(?:\.[0-9]+)?|nan|inf))% idle", output, re.IGNORECASE
    )
    if len(readings) != 2:
        raise EnvironmentNotReadyError("HOST_CPU_IDLE_INVALID")
    value = float(readings[1])
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise EnvironmentNotReadyError("HOST_CPU_IDLE_INVALID")
    return value


async def mac_readiness() -> dict[str, Any]:
    host_platform = sys.platform
    if host_platform != "darwin":
        raise EnvironmentNotReadyError("HOST_SENSOR_PLATFORM_UNSUPPORTED")
    idle = parse_cpu_idle(await read_host_command("top", "-l", "2", "-s", "1", "-n", "0"))
    raw = (await read_host_command("sysctl", "-n", "kern.memorystatus_vm_pressure_level")).strip()
    if raw not in {"1", "2", "4"}:
        raise EnvironmentNotReadyError("HOST_MEMORY_PRESSURE_INVALID")
    return {"cpu_idle_percent": idle, "memory_pressure_level": int(raw)}


async def environment_preflight(
    path: Path,
    root: Path,
    check_services: Callable[[], Awaitable[dict[str, Any]]],
) -> None:
    """One fixed observation window; never wait until a favorable reading appears."""
    document: dict[str, Any] = {
        "status": "RUNNING",
        "window_seconds": 120,
        "minimum_free_bytes": 2 * 1024**3,
        "readiness_rule": "MACOS_CPU_MEMORY_V2",
        "minimum_mean_cpu_idle_percent": 20,
        "allowed_memory_pressure_levels": [1, 2],
        "load_informational_only": True,
        "samples": [],
        "services": {},
    }
    primary: BaseException | None = None
    try:
        document["services"]["before"] = await check_services()
        started = monotonic()
        for offset in range(0, 121, 20):
            await asyncio.sleep(max(0, started + offset - monotonic()))
            document["observing_offset_seconds"] = offset
            sample = {
                **host_observation(root),
                **(await mac_readiness()),
                "scheduled_offset_seconds": offset,
            }
            document["samples"].append(sample)
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            if sample["memory_pressure_level"] == 4:
                raise EnvironmentNotReadyError("HOST_MEMORY_PRESSURE_CRITICAL")
            if sample["free_bytes"] < document["minimum_free_bytes"]:
                raise EnvironmentNotReadyError("HOST_DISK_HEADROOM_LOW")
        document["mean_cpu_idle_percent"] = sum(
            sample["cpu_idle_percent"] for sample in document["samples"]
        ) / len(document["samples"])
        if document["mean_cpu_idle_percent"] < document["minimum_mean_cpu_idle_percent"]:
            raise EnvironmentNotReadyError("HOST_MEAN_CPU_IDLE_LOW")
        document["services"]["after"] = await check_services()
        document["status"] = "PASSED"
    except BaseException as error:
        primary = error
        document["status"] = "INCOMPLETE"
        document["error_type"] = type(error).__name__
        if isinstance(error, EnvironmentNotReadyError):
            document["reason"] = str(error)
        raise
    finally:
        try:
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            if primary is None:
                raise
            primary.add_note(f"preflight evidence write failed: {type(error).__name__}")


async def run_preflighted(
    path: Path,
    root: Path,
    check_services: Callable[[], Awaitable[dict[str, Any]]],
    workload: Callable[[], Awaitable[int]],
) -> int:
    """The campaign entrypoint must establish readiness before invoking any fixture."""
    await environment_preflight(path, root, check_services)
    return await workload()
