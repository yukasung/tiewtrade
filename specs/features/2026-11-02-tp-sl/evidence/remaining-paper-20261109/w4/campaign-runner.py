"""One approved internal W4 using the existing fixture/restore/recovery harness."""

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
import time
from typing import cast
from uuid import uuid4

from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_internal_restore as restore
from tests.infra.execution_market import remaining_paper_campaign as common
from tests.infra.execution_market.profile_publisher_readiness import (
    observe_publisher_readiness,
)
from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose

__all__ = ["common"]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    source = internal.guard_database(dict(os.environ))
    if re.fullmatch(r"tiewtrade_internal20_[a-z0-9_]+", source) is None:
        raise ValueError("isolated restore source name required")
    target = "tiewtrade_internal20_restored_" + uuid4().hex[:12]
    for purpose, value in (
        (KeyPurpose.TOTP_SECRET, b"T"),
        (KeyPurpose.VENUE_API_SECRET, b"V"),
        (KeyPurpose.INDICATOR_CURSOR, b"I"),
    ):
        os.environ[purpose.environment_variable] = (
            "1:" + base64.b64encode(value * KEY_BYTES).decode()
        )
    candidate = common.hashes()
    common.pin_candidate(root, candidate)
    runner = pathlib.Path(__file__).resolve()
    support = pathlib.Path(common.__file__).resolve()
    runner_bytes, support_bytes = runner.read_bytes(), support.read_bytes()
    (root / "campaign-runner.py").write_bytes(runner_bytes)
    (root / "campaign-support.py").write_bytes(support_bytes)
    common.workload.save(root / "candidate-sha256.json", candidate)
    started = time.monotonic()
    status, code, error = "INCOMPLETE", 1, None

    async def phase() -> int:
        await internal.require_empty_database()
        schema = await asyncio.to_thread(
            common.capture,
            "docker",
            "exec",
            "tiewtrade-postgres-1",
            "pg_dump",
            "-U",
            "postgres",
            "--schema-only",
            source,
        )
        pools = {}
        for role in (
            common.DatabaseRole.API,
            common.DatabaseRole.AUTH,
            common.DatabaseRole.ENGINE,
            common.DatabaseRole.ENGINE_SCAN,
            common.DatabaseRole.MIGRATOR,
            common.DatabaseRole.MARKET_DATA,
        ):
            engine = common.create_engine_for(role)
            pools[role.name] = {
                "size": cast(QueuePool, engine.pool).size(),
                "max_overflow": cast(QueuePool, engine.pool)._max_overflow,
                "timeout_seconds": cast(QueuePool, engine.pool).timeout(),
            }
            await engine.dispose()
        containers = json.loads(
            common.capture(
                "docker",
                "inspect",
                "tiewtrade-postgres-1",
                "tiewtrade-f18-release-redis",
            )
        )
        common.workload.save(
            root / "manifest.json",
            {
                "phase": "W4",
                "profile": internal.NAME_V3,
                "source_database": source,
                "target_database": target,
                "git_head": common.capture("git", "-C", str(common.ROOT), "rev-parse", "HEAD"),
                "schema_sha256": hashlib.sha256(schema.encode()).hexdigest(),
                "runner_sha256": hashlib.sha256(runner_bytes).hexdigest(),
                "support_sha256": hashlib.sha256(support_bytes).hexdigest(),
                "platform": platform.platform(),
                "python": platform.python_version(),
                "logical_cpu": os.cpu_count(),
                "host_ram_bytes": int(common.capture("sysctl", "-n", "hw.memsize")),
                "docker_vm": json.loads(
                    common.capture(
                        "docker",
                        "info",
                        "--format",
                        '{"cpu":{{.NCPU}},"memory_bytes":{{.MemTotal}}}',
                    )
                ),
                "processes": common.capture("ps", "-axo", "pid,pcpu,rss,comm").splitlines(),
                "db_settings": json.loads(
                    common.capture(
                        "docker",
                        "exec",
                        "tiewtrade-postgres-1",
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        source,
                        "-At",
                        "-c",
                        "SELECT json_object_agg(name,setting) FROM pg_settings WHERE name IN "
                        "('server_version','max_connections','shared_buffers','work_mem','synchronous_commit',"
                        "'fsync','full_page_writes','wal_level')",
                    )
                ),
                "free_bytes": shutil.disk_usage(common.ROOT).free,
                "load": os.getloadavg(),
                "services": await common.check_services(),
                "pool_defaults": pools,
                "container_limits": [
                    {
                        "name": c["Name"],
                        "nano_cpus": c["HostConfig"]["NanoCpus"],
                        "memory_bytes": c["HostConfig"]["Memory"],
                    }
                    for c in containers
                ],
                "worker_composition": "legacy fixture1worker; sequential integrated recovery",
                "owners": 20,
                "fixture": "original3owners plus17integrated extension owners",
                "intake": "existing W4 fixture; production recovery policy",
                "authorization": "NC12 original W4 and approved sections20/21/22/23 continuation",
            },
        )
        work = root / "run"
        work.mkdir(exist_ok=False)
        build = argparse.Namespace(
            action="build",
            output=work / "fixture",
            fixture=None,
            source_url_env="TIEWTRADE_TEST_ADMIN_URL",
            admin_url_env="TIEWTRADE_TEST_ADMIN_URL",
            target_database=None,
            postgres_container="tiewtrade-postgres-1",
        )
        with observe_publisher_readiness(work / "publisher-readiness-build.json"):
            code = await restore.build(build)
        if code:
            return code
        verify = argparse.Namespace(
            **{
                **vars(build),
                "action": "verify",
                "output": work / "restore",
                "fixture": build.output,
                "target_database": target,
            }
        )
        with observe_publisher_readiness(work / "publisher-readiness-verify.json"):
            return await restore.verify(verify)

    try:
        code = await internal.run_preflighted(
            root / "preflight.json", common.ROOT, common.check_services, phase
        )
        status = "PASSED" if code == 0 else "FAILED"
    except BaseException as failure:
        error = type(failure).__name__
        raise
    finally:
        cleanup = {}
        for database in (source, target):
            query = f"""SELECT json_build_object('connections',
              (SELECT count(*) FROM pg_stat_activity WHERE datname='{database}'),
              'advisory_locks',(SELECT count(*) FROM pg_locks l JOIN pg_database d
                ON d.oid=l.database WHERE d.datname='{database}' AND l.locktype='advisory'))"""
            try:
                cleanup[database] = json.loads(
                    await asyncio.to_thread(
                        common.capture,
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
                if any(cleanup[database].values()):
                    error = error or "CampaignCleanupIncomplete"
            except (OSError, subprocess.SubprocessError, ValueError) as failure:
                cleanup[database] = {"error_type": type(failure).__name__}
                error = error or type(failure).__name__
        unchanged = (
            candidate == common.hashes()
            and runner_bytes == runner.read_bytes()
            and support_bytes == support.read_bytes()
        )
        if not unchanged:
            error = error or "CandidateChanged"
        if error is not None:
            status, code = "INCOMPLETE", 1
        common.workload.save(root / "cleanup.json", cleanup)
        common.workload.save(
            root / "campaign-result.json",
            {
                "phase": "W4",
                "status": status,
                "exit_code": code,
                "error_type": error,
                "seconds": time.monotonic() - started,
                "candidate_unchanged": unchanged,
                "free_bytes_after": shutil.disk_usage(common.ROOT).free,
            },
        )
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
