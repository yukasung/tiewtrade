"""Opt-in diagnostic observations; no SQL, allocation changes or acceptance verdict."""

from __future__ import annotations

import asyncio
import http.client
import json
import os
import socket
from collections.abc import Awaitable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any


class DockerConnection(http.client.HTTPConnection):
    def __init__(self) -> None:
        super().__init__("localhost", timeout=2)

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/var/run/docker.sock")


class DockerReadError(RuntimeError):
    def __init__(self, status: int) -> None:
        super().__init__(f"F18_MEMORY_DOCKER_HTTP_{status}")
        self.status = status


def docker_json(path: str) -> Any:
    connection = DockerConnection()
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        if response.status != 200:
            raise DockerReadError(response.status)
        return json.loads(response.read())
    finally:
        connection.close()


def meminfo_bytes(raw: str) -> dict[str, int]:
    result = {}
    for line in raw.splitlines():
        key, value = line.split(":", 1)
        parts = value.split()
        if len(parts) == 2 and parts[1] == "kB":
            result[key] = int(parts[0]) * 1024
    return result


def memory_snapshot(parent: str) -> dict[str, Any]:
    before = monotonic()
    observed = datetime.now(UTC).isoformat()
    vm = meminfo_bytes(Path("/proc/meminfo").read_text())
    vm_counters = dict(line.split() for line in Path("/proc/vmstat").read_text().splitlines())
    containers = []
    for container in docker_json("/containers/json"):
        names = [name.lstrip("/") for name in container["Names"]]
        if not any(
            name in {parent, "tiewtrade-f18-release-w1-postgres", "tiewtrade-f18-release-redis"}
            or name.startswith(parent + "-risk-")
            for name in names
        ):
            continue
        identity = container["Id"]
        try:
            stats = docker_json(f"/containers/{identity}/stats?stream=false&one-shot=true")
            inspection = docker_json(f"/containers/{identity}/json")
        except DockerReadError as error:
            if error.status != 404:
                raise
            # Worker cleanup may remove its container between list/stats calls.
            containers.append(
                {"id": identity, "names": names, "disappeared": True, "oom_killed": None}
            )
            continue
        state = inspection["State"]
        memory = stats.get("memory_stats", {})
        details = memory.get("stats", {})
        containers.append(
            {
                "id": identity,
                "names": names,
                "read_at": stats.get("read"),
                "usage_bytes": memory.get("usage"),
                "limit_bytes": memory.get("limit"),
                "inactive_file_bytes": details.get(
                    "inactive_file", details.get("total_inactive_file")
                ),
                "anon_bytes": details.get("anon", details.get("total_rss")),
                "swap_bytes": details.get("swap", details.get("total_swap")),
                "fail_count": memory.get("failcnt"),
                "oom_killed": state["OOMKilled"],
                "running": state["Running"],
                "restart_count": inspection["RestartCount"],
                "cpu_usage_total_ns": stats.get("cpu_stats", {})
                .get("cpu_usage", {})
                .get("total_usage"),
                "cpu_system_ns": stats.get("cpu_stats", {}).get("system_cpu_usage"),
                "online_cpus": stats.get("cpu_stats", {}).get("online_cpus"),
                "throttling": stats.get("cpu_stats", {}).get("throttling_data"),
            }
        )
    return {
        "observed_at": observed,
        "finished_at": datetime.now(UTC).isoformat(),
        "collection_seconds": monotonic() - before,
        "vm_bytes": {k: vm[k] for k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")},
        "vm_counters": {
            k: int(vm_counters[k]) for k in ("pgmajfault", "pswpin", "pswpout", "oom_kill")
        },
        "vm_memory_pressure": Path("/proc/pressure/memory").read_text(),
        "containers": containers,
        "missing_values_are_unknown": True,
    }


async def sample_memory(path: Path, stop: asyncio.Event) -> None:
    parent = os.environ["F18_PARENT_CONTAINER"]
    if not parent.startswith("tiewtrade-f18-"):
        raise RuntimeError("F18_MEMORY_CONTAINER_REJECTED")
    baseline_oom: int | None = None
    with path.open("x") as stream:
        while not stop.is_set():
            row = await asyncio.to_thread(memory_snapshot, parent)
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            oom_count = int(row["vm_counters"]["oom_kill"])
            if baseline_oom is None:
                baseline_oom = oom_count
            if oom_count > baseline_oom or any(
                container["oom_killed"] for container in row["containers"]
            ):
                raise RuntimeError("F18_MEMORY_OBSERVED_OOM")
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=2)


async def diagnostic_window(operation: Awaitable[None], seconds: float) -> None:
    """Cancel/join at observation cutoff; preserve earlier workload failures."""
    started = monotonic()
    task = asyncio.ensure_future(operation)
    try:
        done, _ = await asyncio.wait((task,), timeout=seconds)
        if task in done:
            await task
            await asyncio.sleep(max(0, started + seconds - monotonic()))
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
