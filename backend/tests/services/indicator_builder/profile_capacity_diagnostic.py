"""Bounded diagnostic using existing probes; emits no acceptance gate result."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

import httpx
from sqlalchemy import text

from tests.services.indicator_builder import profile_capacity as capacity
from tests.services.indicator_builder import profile_capacity_steady as steady
from tiewtrade.infra.db import DatabaseRole, create_engine_for


async def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    original = capacity.runtime_name("api")
    diagnostic = original + "-" + output.name
    inspected = json.loads(await capacity.docker("inspect", original))[0]
    args = [
        "create",
        "--name",
        diagnostic,
        "--network",
        capacity.NETWORK,
        "--cpus=2",
        "--cpuset-cpus=6-7",
        "--memory=1g",
        "-p",
        "127.0.0.1::8000",
        "--mount",
        f"type=bind,source={Path(__file__).resolve().parent},target=/capacity,readonly",
        "--mount",
        f"type=bind,source={output.resolve()},target=/evidence",
    ]
    for value in inspected["Config"]["Env"]:
        args.extend(["-e", value])
    args.extend(
        [
            inspected["Image"],
            "uvicorn",
            "profile_capacity_diagnostic_app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ]
    )
    await capacity.docker(*args)
    setattr(  # noqa: B010 — replace a helper imported into the reused runner module
        steady,
        "runtime_name",
        lambda kind: diagnostic if kind == "api" else capacity.runtime_name(kind),
    )
    source = create_engine_for(DatabaseRole.MARKET_DATA)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    api = create_engine_for(DatabaseRole.API)
    clients: list[httpx.AsyncClient] = []
    stop = asyncio.Event()
    tasks: list[asyncio.Task[None]] = []
    report: dict[str, Any] = {
        "diagnostic_only": True,
        "image": inspected["Image"],
        "max_run_seconds": 360,
        "activities": ["source_producer", "observer", "snapshot", "parity_audit"],
        "rounds": [],
        "observations": [],
    }
    try:
        await capacity.docker("stop", "--time", "10", original)
        await capacity.docker("start", diagnostic)
        clients, users = await steady.login()
        await capacity.docker("start", capacity.runtime_name("builder"))
        async with migrator.connect() as connection:
            ends = {
                row["base"] + "/" + row["timeframe"]: row["end_at"]
                for row in (
                    await connection.execute(
                        text(
                            "SELECT base,timeframe,max(end_at) AS end_at FROM market_candles "
                            "GROUP BY base,timeframe"
                        )
                    )
                ).mappings()
            }
        # Reuse normal append/observer behavior, bounded setup, without changing job state.
        async with asyncio.timeout(180):
            while True:
                await capacity.append(source, ends)
                ready = await capacity.observe(api, users[0])
                if all(row["valid"] for row in ready):
                    break
                await asyncio.sleep(2)
        workload_ends = {
            base + "/" + tf.value: ends[base + "/" + tf.value] for base, tf in capacity.SERIES
        }
        tasks.append(
            asyncio.create_task(
                capacity.maintain_source(source, workload_ends, stop, capacity.SERIES)
            )
        )

        async def observer() -> None:
            while not stop.is_set():
                report["observations"].append(
                    {
                        "at": monotonic(),
                        "series": await capacity.observe(api, users[0]),
                        "metadata": await capacity.snapshot(migrator),
                    }
                )
                await asyncio.sleep(10)

        tasks.append(asyncio.create_task(observer()))
        for index in range(3):
            for task in tasks:
                if task.done():
                    await task
            before = await capacity.docker("exec", diagnostic, "cat", "/sys/fs/cgroup/cpu.stat")
            rejected: list[dict[str, Any]] = []
            started = monotonic()
            probes = await steady.loaded_probes(clients, started, rejected)
            details = [
                {k: v for k, v in row.items() if k != "body"}
                | {
                    "error": row["body"].get("detail"),
                    "refresh": row["body"].get("refresh"),
                }
                for row in probes
            ]
            audit_started = monotonic()
            await capacity.audit(api, users[0], probes)
            for detail, probe in zip(details, probes, strict=True):
                detail["correct"] = probe["correct"]
            after = await capacity.docker("exec", diagnostic, "cat", "/sys/fs/cgroup/cpu.stat")
            report["rounds"].append(
                {
                    "index": index,
                    "cpu_before": before,
                    "cpu_after": after,
                    "rejected": rejected,
                    "probes": details,
                    "audit_seconds": monotonic() - audit_started,
                }
            )
            capacity.save(output / "diagnostic-result.json", report)
            capacity.progress(
                "diagnostic round", index + 1, "statuses", [p["status"] for p in probes]
            )
            if index < 2:
                await asyncio.sleep(max(0, 61 - (monotonic() - started)))
    except BaseException as error:
        report["failure_type"] = type(error).__name__
        raise
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        capacity.save(output / "diagnostic-result.json", report)
        for client in clients:
            await client.aclose()
        await asyncio.gather(source.dispose(), migrator.dispose(), api.dispose())
        await capacity.docker("stop", "--time", "10", diagnostic)
        await capacity.docker("stop", "--time", "10", capacity.runtime_name("builder"))


async def run_native(output: Path, c1: Path, seconds: int = 300) -> int:
    """Run the original scheduler/oracle, retaining separate diagnostic gates."""
    if seconds < 60 or seconds > 2400 or seconds % 60:
        raise ValueError("diagnostic duration must be 60..2400 seconds in whole minutes")
    output.mkdir(parents=True, exist_ok=False)
    metrics = output / "metrics"
    metrics.mkdir()
    for name in ("api-metrics.jsonl", "worker-attempts.jsonl"):
        (metrics / name).touch()
    names: dict[str, str] = {}
    for kind in ("api", "builder"):
        original = capacity.runtime_name(kind)
        inspected = json.loads(await capacity.docker("inspect", original))[0]
        names[kind] = original + "-" + output.name
        args = [
            "create",
            "--name",
            names[kind],
            "--network",
            capacity.NETWORK,
            "--cpus=2",
            "--cpuset-cpus=" + inspected["HostConfig"]["CpusetCpus"],
            "--memory=1g",
            "--mount",
            f"type=bind,source={Path(__file__).resolve().parent},target=/capacity,readonly",
            "--mount",
            f"type=bind,source={metrics.resolve()},target=/evidence",
        ]
        if kind == "api":
            args.extend(["-p", "127.0.0.1::8000"])
        for value in inspected["Config"]["Env"]:
            args.extend(["-e", value])
        command = list(inspected["Config"]["Cmd"])
        if kind == "api":
            command[1] = "profile_capacity_diagnostic_app:app"
        await capacity.docker(*args, inspected["Image"], *command)
    setattr(steady, "runtime_name", lambda kind: names[kind])  # noqa: B010

    async def host_samples() -> None:
        while True:
            process = await asyncio.create_subprocess_exec(
                "vm_stat", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            with (output / "host-vm-stat.jsonl").open("a") as history:
                history.write(
                    json.dumps(
                        {
                            "at": monotonic(),
                            "utc": str(datetime.now(UTC)),
                            "vm_stat": stdout.decode(),
                        }
                    )
                    + "\n"
                )
            await asyncio.sleep(2)

    host = asyncio.create_task(host_samples())
    try:
        async with asyncio.timeout(seconds + 720):
            return await steady.run(
                output / "phase",
                c1,
                load_metrics=metrics / "api-metrics.jsonl",
                metrics_directory=metrics,
                diagnostic_seconds=seconds,
            )
    finally:
        host.cancel()
        await asyncio.gather(host, return_exceptions=True)
        for name in names.values():
            await capacity.docker("stop", "--time", "10", name)


if __name__ == "__main__":
    import sys

    async def bounded() -> None:
        async with asyncio.timeout(360):
            await run(Path(sys.argv[1]))

    if len(sys.argv) in (3, 4):
        raise SystemExit(
            asyncio.run(
                run_native(
                    Path(sys.argv[1]),
                    Path(sys.argv[2]),
                    int(sys.argv[3]) if len(sys.argv) == 4 else 300,
                )
            )
        )
    asyncio.run(bounded())
