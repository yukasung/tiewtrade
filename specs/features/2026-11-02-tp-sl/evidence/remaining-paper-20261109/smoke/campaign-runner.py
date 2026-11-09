"""Record one approved NC12 phase using the existing profile runners."""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import (
    profile_internal as internal,
)
from tests.infra.execution_market import (
    profile_protections as protection,
)
from tests.infra.execution_market import (
    profile_workload as workload,
)
from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose
from tiewtrade.infra.db import DatabaseRole, create_engine_for

__all__ = ["DatabaseRole", "create_engine_for", "internal", "workload"]

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"


def capture(*command: str) -> str:
    return subprocess.check_output(command, text=True, timeout=30).strip()


def hashes() -> dict[str, str]:
    paths = [
        p
        for part in (
            "backend/src",
            "backend/tests",
            "backend/migrations",
            "frontend/src",
        )
        for p in (ROOT / part).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    paths += [
        ROOT / p
        for p in (
            "backend/uv.lock",
            "backend/pyproject.toml",
            "compose.yaml",
            "config/postgres.env",
            "frontend/package-lock.json",
        )
        if (ROOT / p).exists()
    ]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }


def pin_candidate(root: pathlib.Path, candidate: dict[str, str]) -> None:
    """Bind the selected source inventory and Git delta before any timed observation."""
    scope = (
        "backend/src",
        "backend/tests",
        "backend/migrations",
        "backend/uv.lock",
        "backend/pyproject.toml",
        "frontend/src",
        "frontend/package-lock.json",
        "compose.yaml",
        "config/postgres.env",
    )
    diff = capture("git", "-C", str(ROOT), "diff", "HEAD", "--", *scope)
    (root / "candidate-diff.patch").write_text(diff + "\n")
    workload.save(
        root / "candidate-binding.json",
        {
            "head": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
            "source_status": capture(
                "git",
                "-C",
                str(ROOT),
                "status",
                "--short",
                "--untracked-files=all",
                "--",
                *scope,
            ).splitlines(),
            "diff_sha256": hashlib.sha256((diff + "\n").encode()).hexdigest(),
            "inventory_sha256": hashlib.sha256(
                json.dumps(candidate, sort_keys=True).encode()
            ).hexdigest(),
        },
    )


async def check_services() -> dict[str, Any]:
    containers = json.loads(
        await asyncio.to_thread(
            capture,
            "docker",
            "inspect",
            "tiewtrade-postgres-1",
            "tiewtrade-f18-release-redis",
        )
    )
    states = [
        {
            "name": c["Name"],
            "state": c["State"]["Status"],
            "health": c["State"].get("Health", {}).get("Status"),
            "restart_count": c["RestartCount"],
        }
        for c in containers
    ]
    if (
        len(states) != 2
        or any(c["state"] != "running" for c in states)
        or states[0]["health"] != "healthy"
    ):
        raise internal.EnvironmentNotReadyError("CAMPAIGN_SERVICES_NOT_HEALTHY")
    statuses = await asyncio.to_thread(capture, "docker", "ps", "--format", "{{.Status}}")
    if any("Restarting" in line for line in statuses.splitlines()):
        raise internal.EnvironmentNotReadyError("CONTAINER_RESTART_LOOP")
    postgres = await asyncio.to_thread(
        capture,
        "docker",
        "exec",
        "tiewtrade-postgres-1",
        "pg_isready",
        "-U",
        "postgres",
    )
    redis = await asyncio.to_thread(
        capture, "docker", "exec", "tiewtrade-f18-release-redis", "redis-cli", "PING"
    )
    if not postgres or redis != "PONG":
        raise internal.EnvironmentNotReadyError("REDIS_NOT_READY")
    return {"containers": states, "postgres_ready": bool(postgres), "redis_ping": redis}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("CONTROLLED20", "SMOKE", "W1", "W2", "W3", "W2_OVERFLOW"))
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument(
        "--acceptance-profile", choices=tuple(internal.PROFILES), default=internal.NAME
    )
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    for purpose, value in (
        (KeyPurpose.TOTP_SECRET, b"T"),
        (KeyPurpose.VENUE_API_SECRET, b"V"),
        (KeyPurpose.INDICATOR_CURSOR, b"I"),
    ):
        os.environ[purpose.environment_variable] = "1:" + base64.b64encode(
            value * KEY_BYTES
        ).decode("ascii")
    database = internal.guard_database(dict(os.environ))
    candidate = hashes()
    pin_candidate(root, candidate)
    runner = pathlib.Path(__file__).resolve()
    runner_digest = hashlib.sha256(runner.read_bytes()).hexdigest()
    (root / "campaign-runner.py").write_bytes(runner.read_bytes())
    workload.save(root / "candidate-sha256.json", candidate)
    status = "INCOMPLETE"
    code = 1
    start = time.monotonic()
    error = None

    async def phase_run() -> int:
        free = shutil.disk_usage(ROOT).free
        containers = json.loads(
            capture(
                "docker",
                "inspect",
                "tiewtrade-postgres-1",
                "tiewtrade-f18-release-redis",
            )
        )
        state = [
            {
                "name": c["Name"],
                "state": c["State"]["Status"],
                "health": c["State"].get("Health", {}).get("Status"),
                "restart_count": c["RestartCount"],
                "nano_cpus": c["HostConfig"]["NanoCpus"],
                "memory_limit": c["HostConfig"]["Memory"],
            }
            for c in containers
        ]
        db_settings = json.loads(
            capture(
                "docker",
                "exec",
                "tiewtrade-postgres-1",
                "psql",
                "-U",
                "postgres",
                "-d",
                database,
                "-At",
                "-c",
                """SELECT json_object_agg(name,setting) FROM pg_settings WHERE name IN
                ('server_version','max_connections','shared_buffers','work_mem',
                'maintenance_work_mem','synchronous_commit','fsync','full_page_writes',
                'wal_level','max_wal_size','checkpoint_timeout')""",
            )
        )
        pools = {}
        for role in (
            DatabaseRole.API,
            DatabaseRole.AUTH,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MARKET_DATA,
        ):
            engine = create_engine_for(role)
            pool = cast(QueuePool, engine.pool)
            pools[role.name] = {
                "size": pool.size(),
                "max_overflow": pool._max_overflow,
                "timeout_seconds": pool.timeout(),
            }
            await engine.dispose()
        options = argparse.Namespace(
            acceptance_profile=args.acceptance_profile,
            parent_poll_limit=4,
            phase=args.phase,
            owners=20,
            baseline_orders=20,
            cycles_per_owner=0,
            rate=2,
            workers=20,
            r8_claim_budget=True,
            coordinate_claims=True,
            publisher_heartbeat_per_book=True,
            final_tail_drain=True,
            diagnostics=False,
            worker_only=False,
            baseline_manifest=None,
            fault_schedule=None,
            redis_container=None,
            output=root / "run",
        )
        if args.phase != "CONTROLLED20":
            phase = internal.PROFILES[args.acceptance_profile][args.phase]
            options.cycles_per_owner = phase.cycles_per_owner
            options.rate = phase.rate
            if args.phase == "W3":
                options.fault_schedule = internal.fault_schedule_for(args.acceptance_profile)
                options.redis_container = "tiewtrade-f18-release-redis"
            internal.validate(options)
        schema = capture(
            "docker",
            "exec",
            "tiewtrade-postgres-1",
            "pg_dump",
            "-U",
            "postgres",
            "--schema-only",
            database,
        )
        workload.save(
            root / "manifest.json",
            {
                "phase": args.phase,
                "profile": args.acceptance_profile,
                "started_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
                "git_head": capture("git", "-C", str(ROOT), "rev-parse", "HEAD"),
                "database": database,
                "schema_sha256": hashlib.sha256(schema.encode()).hexdigest(),
                "python": sys.version,
                "platform": platform.platform(),
                "host_cpu": int(capture("sysctl", "-n", "hw.logicalcpu")),
                "host_ram_bytes": int(capture("sysctl", "-n", "hw.memsize")),
                "docker_vm": json.loads(
                    capture(
                        "docker",
                        "info",
                        "--format",
                        '{"cpu":{{.NCPU}},"memory_bytes":{{.MemTotal}}}',
                    )
                ),
                "containers": state,
                "all_containers": capture(
                    "docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"
                ).splitlines(),
                "free_bytes": free,
                "load": os.getloadavg(),
                "processes": capture("ps", "-axo", "pid,pcpu,rss,comm").splitlines(),
                "db_settings": db_settings,
                "pool_defaults": pools,
                "api_pool_overrides": {
                    "paper_mutation": [1, 0, 0.5],
                    "price": [3, 0, 0.5],
                    "indicator": [1, 0, 0.25],
                    "chart": [1, 0, 0.5],
                },
                "api_instances": 0 if args.phase == "CONTROLLED20" else 1,
                "workers": 20,
                "bridge_rounds_per_worker": True,
                "protection_rounds_per_worker": True,
                "claim_limit": 1,
                "round_limit": 20,
                "coordination": "SERIALIZED_CLAIM_V2",
                "busy_backoff_seconds": 0.250,
                "args": vars(options),
                "dataset": (
                    "fresh database; fixture/oracle pinned by source hashes; "
                    "owner IDs emitted by runner"
                ),
                "runner_sha256": runner_digest,
                "authorization": (
                    "NC12 sections5,9,11,12,13,14,15,16,18,19,20,21,22 approved; "
                    "explicit V2 burst10/s; pilot processing500ms/2s; owned pool contract"
                ),
            },
        )
        await internal.require_empty_database()
        return await (
            protection.run(root / "run") if args.phase == "CONTROLLED20" else workload.run(options)
        )

    try:
        async with asyncio.timeout(1200 if args.phase == "SMOKE" else None):
            code = await internal.run_preflighted(
                root / "preflight.json", ROOT, check_services, phase_run
            )
        status = "PASSED" if code == 0 else "FAILED"
        result_file = root / "run" / "result.json"
        if (
            code != 0
            and result_file.exists()
            and json.loads(result_file.read_text()).get("status") == "INCOMPLETE"
        ):
            status = "INCOMPLETE"
    except BaseException as failure:
        error = type(failure).__name__
        raise
    finally:
        unchanged = (
            candidate == hashes()
            and runner_digest == hashlib.sha256(runner.read_bytes()).hexdigest()
        )
        query = f"""SELECT json_build_object('connections',
        (SELECT count(*) FROM pg_stat_activity WHERE datname='{database}'),
        'advisory_locks',(SELECT count(*) FROM pg_locks l
        JOIN pg_database d ON d.oid=l.database WHERE d.datname='{database}'
        AND l.locktype='advisory'))"""
        try:
            cleanup = json.loads(
                await asyncio.to_thread(
                    capture,
                    "docker",
                    "exec",
                    "tiewtrade-postgres-1",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "postgres",
                    "-At",
                    "-c",
                    query,
                )
            )
            if cleanup["connections"] or cleanup["advisory_locks"]:
                status = "INCOMPLETE"
                code = 1
                error = error or "CampaignCleanupIncomplete"
        except Exception as failure:
            cleanup = {"error_type": type(failure).__name__}
            status = "INCOMPLETE"
            code = 1
            error = error or type(failure).__name__
        workload.save(root / "cleanup.json", cleanup)
        elapsed = time.monotonic() - start
        if args.phase == "SMOKE" and elapsed > 1200:
            status = "INCOMPLETE"
            code = 1
            error = error or "TimeoutError"
        if not unchanged:
            status = "INCOMPLETE"
            code = 1
            error = error or "CandidateChanged"
        workload.save(
            root / "campaign-result.json",
            {
                "status": status,
                "exit_code": code,
                "seconds": elapsed,
                "error_type": error,
                "candidate_unchanged": unchanged,
                "free_bytes_after": shutil.disk_usage(ROOT).free,
                "budget_seconds": 1200 if args.phase == "SMOKE" else None,
                "budget_scope": "preflight,fixture,measurement,verification,cleanup",
            },
        )
        if not unchanged:
            raise RuntimeError("candidate changed during campaign")
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
