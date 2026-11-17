"""Record one approved NC12 phase using the existing profile runners."""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import pathlib
import platform
import re
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
from tests.infra.execution_market import profile_publisher_recovery as clock_recovery
from tests.infra.execution_market import (
    profile_workload as workload,
)
from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose
from tiewtrade.infra.db import DatabaseRole, create_engine_for

__all__ = ["DatabaseRole", "create_engine_for", "internal", "workload"]

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"

_CLEANUP_COUNTS = ("connections", "advisory_locks")
_CLEANUP_OBSERVATIONS = ("observed_at", *_CLEANUP_COUNTS)
_CLEANUP_FIELDS = frozenset((*_CLEANUP_OBSERVATIONS, "backends"))
_BACKEND_FIELDS = ("pid", "role", "state", "backend_type", "transaction_open")


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


def cleanup_query(database: str) -> str:
    if re.fullmatch(r"tiewtrade_internal20_[a-z0-9_]+", database) is None:
        raise ValueError("generated isolated database required")
    return f"""WITH backends AS MATERIALIZED (
        SELECT pid,usename AS role,state,backend_type,xact_start IS NOT NULL AS transaction_open
        FROM pg_stat_activity WHERE datname='{database}')
        SELECT json_build_object('observed_at',clock_timestamp()::text,
        'connections',(SELECT count(*) FROM backends),
        'backends',coalesce((SELECT json_agg(row_to_json(b) ORDER BY pid) FROM backends b),'[]'),
        'advisory_locks',(SELECT count(*) FROM pg_locks l
        JOIN pg_database d ON d.oid=l.database WHERE d.datname='{database}'
        AND l.locktype='advisory'))"""


def cleanup_counts_passed(value: Any) -> bool:
    """Both counters must be present, nonnegative integers and exactly zero."""
    if not isinstance(value, dict) or set(value) != set(_CLEANUP_COUNTS):
        raise ValueError("complete cleanup counts required")
    for name in _CLEANUP_COUNTS:
        if type(value[name]) is not int or value[name] < 0:
            raise ValueError("invalid cleanup count")
    return bool(value["connections"] == 0 and value["advisory_locks"] == 0)


def cleanup_passed(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _CLEANUP_FIELDS:
        raise ValueError("complete cleanup identity required")
    counts_passed = cleanup_counts_passed({name: value[name] for name in _CLEANUP_COUNTS})
    if not isinstance(value["observed_at"], str):
        raise ValueError("cleanup timestamp required")
    timestamp = datetime.fromisoformat(value["observed_at"])
    if timestamp.tzinfo is None:
        raise ValueError("cleanup timestamp must have timezone")
    rows = value["backends"]
    if not isinstance(rows, list) or len(rows) != value["connections"]:
        raise ValueError("cleanup identity count mismatch")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(_BACKEND_FIELDS):
            raise ValueError("invalid backend identity fields")
        if type(row["pid"]) is not int or row["pid"] <= 0:
            raise ValueError("invalid backend pid")
        required = ("state", "backend_type")
        if any(not isinstance(row[k], str) or not row[k] for k in required):
            raise ValueError("missing backend identity")
        if (not isinstance(row["role"], str) or not row["role"]) and (
            row["role"] is not None or row["backend_type"] != "autovacuum worker"
        ):
            raise ValueError("missing backend identity")
        if type(row["transaction_open"]) is not bool:
            raise ValueError("invalid backend transaction observation")
    if len({row["pid"] for row in rows}) != len(rows):
        raise ValueError("duplicate backend identity")
    return counts_passed


async def capture_cleanup(database: str, observations: list[Any]) -> Any:
    """Require exact zero; briefly observe only explicitly identified DB maintenance."""
    for attempt in range(11):
        current = json.loads(
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
                cleanup_query(database),
            )
        )
        observations.append(retained_cleanup(current))
        try:
            passed = cleanup_passed(current)
        except ValueError:
            return current  # Caller retains malformed evidence and rejects it.
        if passed:
            return current
        maintenance = (
            current["advisory_locks"] == 0
            and bool(current["backends"])
            and all(row["backend_type"] == "autovacuum worker" for row in current["backends"])
        )
        if not maintenance or attempt == 10:
            return current
        await asyncio.sleep(1)
    raise AssertionError("bounded cleanup observation did not return")


def retained_cleanup(value: Any) -> dict[str, Any]:
    """Preserve allowlisted observations even when identity validation rejects them."""
    if not isinstance(value, dict):
        return {}
    retained = {name: value[name] for name in _CLEANUP_OBSERVATIONS if name in value}
    if isinstance(value.get("backends"), list):
        retained["backends"] = [
            {name: row[name] for name in _BACKEND_FIELDS if name in row}
            for row in value["backends"]
            if isinstance(row, dict)
        ]
    return retained


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


def profile_authorization(profile: str) -> str:
    """Bind approval to the selected contract without duplicating numeric policy."""
    if profile not in internal.PROFILES:
        raise ValueError("unknown acceptance profile")
    if profile in {internal.RELEASE_TIMING_NAME, internal.NAME_BURST5}:
        document = "paper-timing-acceptance-amendment-20261114.md"
    elif profile == internal.RELEASE_NAME:
        document = "integrated-paper-acceptance-plan.md"
    else:
        document = "internal-paper-acceptance-amendment.md"
    return (
        f"{profile}: specs/features/2026-11-02-tp-sl/{document}; "
        "effective criteria recorded in structured manifest and result fields"
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("CONTROLLED20", "SMOKE", "W1", "W2", "W3", "W2_OVERFLOW"))
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument(
        "--acceptance-profile", choices=tuple(internal.PROFILES), default=internal.NAME
    )
    parser.add_argument("--failure-timeline", action="store_true")
    parser.add_argument("--publisher-clock-recovery", action="store_true")
    parser.add_argument("--publisher-lease-observer", action="store_true")
    parser.add_argument("--publisher-fence-observer", action="store_true")
    parser.add_argument("--publisher-fence-fail-fast", action="store_true")
    parser.add_argument("--publisher-fence-timing", action="store_true")
    parser.add_argument("--observer-scheduled-samples", action="store_true")
    parser.add_argument("--observer-w3-prefix", action="store_true")
    parser.add_argument("--observation-poll-seconds", type=float, choices=(0.25, 1.0), default=0.25)
    args = parser.parse_args()
    from tests.infra.execution_market.profile_publisher_lease_load import (
        validate_options as validate_lease_options,
    )

    try:
        validate_lease_options(args)
    except ValueError as option_error:
        parser.error(str(option_error))
    try:
        clock_recovery.validate_options(args)
    except ValueError as option_error:
        parser.error(str(option_error))
    if getattr(args, "failure_timeline", False) and (
        args.phase != "SMOKE" or args.acceptance_profile != internal.RELEASE_NAME
    ):
        parser.error("failure timeline requires original100 SMOKE")
    if args.phase == "CONTROLLED20":
        if args.acceptance_profile in internal.RELEASE_PROFILES:
            parser.error("CONTROLLED20 is not the original 100-account release profile")
        if args.acceptance_profile == internal.NAME_BURST5:
            parser.error("burst5 profile supports W2 only")
    elif args.phase not in internal.PROFILES[args.acceptance_profile]:
        parser.error("phase is not supported by the selected acceptance profile")
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
            owners=(
                20
                if args.phase == "CONTROLLED20"
                else internal.PROFILES[args.acceptance_profile][args.phase].owners
            ),
            baseline_orders=20,
            cycles_per_owner=0,
            rate=2,
            workers=20,
            r8_claim_budget=True,
            coordinate_claims=True,
            publisher_heartbeat_per_book=True,
            final_tail_drain=True,
            diagnostics=False,
            failure_timeline=getattr(args, "failure_timeline", False),
            publisher_clock_recovery=getattr(args, "publisher_clock_recovery", False),
            publisher_lease_observer=getattr(args, "publisher_lease_observer", False),
            publisher_fence_observer=getattr(args, "publisher_fence_observer", False),
            publisher_fence_fail_fast=getattr(args, "publisher_fence_fail_fast", False),
            publisher_fence_timing=getattr(args, "publisher_fence_timing", False),
            observer_scheduled_samples=getattr(args, "observer_scheduled_samples", False),
            observer_w3_prefix=getattr(args, "observer_w3_prefix", False),
            observation_poll_seconds=getattr(args, "observation_poll_seconds", 0.25),
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
                **clock_recovery.configuration(args),
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
                "authorization": profile_authorization(args.acceptance_profile),
            },
        )
        await internal.require_empty_database()
        return await (
            protection.run(root / "run") if args.phase == "CONTROLLED20" else workload.run(options)
        )

    try:
        async with asyncio.timeout(
            3600 if args.observer_w3_prefix else 1200 if args.phase == "SMOKE" else None
        ):
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
        if isinstance(failure, (AssertionError, workload.CycleBudgetExceededError)):
            status = "FAILED"
        raise
    finally:
        workload_status = status
        unchanged = (
            candidate == hashes()
            and runner_digest == hashlib.sha256(runner.read_bytes()).hexdigest()
        )
        cleanup_query(database)  # Validate fixture identity before any cleanup read.
        cleanup: Any = None
        cleanup_complete = False
        try:
            observations: list[Any] = []
            try:
                cleanup = await capture_cleanup(database, observations)
            finally:
                if len(observations) > 1:
                    workload.save(
                        root / "cleanup-observations.json",
                        {"maximum_wait_seconds": 10, "observations": observations},
                    )
            cleanup_complete = cleanup_passed(cleanup)
            if not cleanup_complete:
                error = error or "CampaignCleanupIncomplete"
        except Exception as failure:
            cleanup = {**retained_cleanup(cleanup), "error_type": type(failure).__name__}
            error = error or type(failure).__name__
        workload.save(root / "cleanup.json", cleanup)
        elapsed = time.monotonic() - start
        if (args.phase == "SMOKE" and elapsed > 1200) or (
            args.observer_w3_prefix and elapsed > 3600
        ):
            error = error or "TimeoutError"
        if not unchanged:
            error = error or "CandidateChanged"
        if error is not None:
            status = "FAILED" if workload_status == "FAILED" else "INCOMPLETE"
            code = 1
        prefix_diagnostic: dict[str, object] = {}
        if args.observer_w3_prefix:
            observed = root / "run" / "result.json"
            prefix_diagnostic = {
                "diagnostic_status": "COMPLETE"
                if error is None
                and unchanged
                and cleanup_complete
                and observed.exists()
                and json.loads(observed.read_text()).get("diagnostic_status") == "COMPLETE"
                else "INCOMPLETE",
                "acceptance_scope": "W3 prefix only; four-hour W3 remains Incomplete",
            }
        workload.save(
            root / "campaign-result.json",
            {
                "status": status,
                "workload_status": workload_status,
                **prefix_diagnostic,
                "cleanup_complete": cleanup_complete,
                "exit_code": code,
                "seconds": elapsed,
                "error_type": error,
                "candidate_unchanged": unchanged,
                "free_bytes_after": shutil.disk_usage(ROOT).free,
                "budget_seconds": 3600
                if args.observer_w3_prefix
                else 1200
                if args.phase == "SMOKE"
                else None,
                "budget_scope": "preflight,fixture,measurement,verification,cleanup",
                **(
                    {"diagnostic_only": True}
                    if (
                        getattr(args, "failure_timeline", False)
                        or getattr(args, "publisher_lease_observer", False)
                    )
                    else {}
                ),
            },
        )
        if not unchanged and sys.exception() is None:
            raise RuntimeError("candidate changed during campaign")
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
