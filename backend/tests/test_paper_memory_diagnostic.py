"""Memory observations preserve units, unknowns, failure propagation and cutoff."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from tests.infra.risk_limits import profile_memory as memory
from tests.infra.risk_limits import profile_workload as workload


def test_meminfo_units_do_not_confuse_pages_bytes_or_unitless_counts() -> None:
    assert memory.meminfo_bytes("MemTotal: 100 kB\nSwapFree: 7 kB\nHugePages_Total: 4") == {
        "MemTotal": 102400,
        "SwapFree": 7168,
    }


def test_snapshot_filters_containers_and_preserves_raw_usage_and_unknowns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = "tiewtrade-f18-memory-test"
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path: {
            "/proc/meminfo": (
                "MemTotal: 100 kB\nMemAvailable: 10 kB\nSwapTotal: 20 kB\nSwapFree: 5 kB"
            ),
            "/proc/vmstat": "pgmajfault 3\npswpin 4\npswpout 5\noom_kill 0",
            "/proc/pressure/memory": "some avg10=1.00 total=2",
        }[str(path)],
    )
    calls = []

    def docker(path: str) -> Any:
        calls.append(path)
        if path == "/containers/json":
            return [{"Id": "a", "Names": ["/" + parent]}, {"Id": "b", "Names": ["/unrelated"]}]
        if "/stats?" in path:
            return {
                "read": "2026-10-29T00:00:00Z",
                "memory_stats": {
                    "usage": 1000,
                    "limit": 2000,
                    "stats": {"inactive_file": 400, "anon": 500},
                },
            }
        return {"State": {"OOMKilled": False, "Running": True}, "RestartCount": 0}

    monkeypatch.setattr(memory, "docker_json", docker)
    row = memory.memory_snapshot(parent)
    assert row["vm_bytes"]["MemAvailable"] == 10240
    assert row["vm_counters"]["pswpout"] == 5
    container = row["containers"][0]
    assert container["usage_bytes"] == 1000 and container["inactive_file_bytes"] == 400
    assert container["swap_bytes"] is None and container["fail_count"] is None
    assert len(row["containers"]) == 1 and len(calls) == 3
    assert row["collection_seconds"] >= 0


async def test_sampler_flushes_and_stops_without_extra_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F18_PARENT_CONTAINER", "tiewtrade-f18-memory-test")
    stop = asyncio.Event()
    calls = []

    def snapshot(parent: str) -> dict[str, Any]:
        calls.append(parent)
        stop.set()
        return {"containers": [{"oom_killed": False}], "vm_counters": {"oom_kill": 0}}

    monkeypatch.setattr(memory, "memory_snapshot", snapshot)
    path = tmp_path / "memory.jsonl"
    await memory.sample_memory(path, stop)
    assert len(calls) == len(path.read_text().splitlines()) == 1


async def test_sampler_oom_stops_workload_and_joins_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F18_PARENT_CONTAINER", "tiewtrade-f18-memory-test")
    monkeypatch.setattr(
        memory,
        "memory_snapshot",
        lambda _: {"containers": [{"oom_killed": True}], "vm_counters": {"oom_kill": 0}},
    )
    stopped = asyncio.Event()

    async def run(args: argparse.Namespace) -> int:
        try:
            await asyncio.Event().wait()
            return 0
        finally:
            stopped.set()

    monkeypatch.setattr(workload, "run", run)
    with pytest.raises(RuntimeError, match="OBSERVED_OOM"):
        await workload.run_memory_diagnostic(argparse.Namespace(output=tmp_path / "diagnostic"))
    assert stopped.is_set()
    assert json.loads((tmp_path / "diagnostic.memory.jsonl").read_text())["containers"][0][
        "oom_killed"
    ]


async def test_window_cancels_and_joins_at_cutoff_without_acceptance_claim() -> None:
    joined = asyncio.Event()

    async def work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    await memory.diagnostic_window(work(), 0.01)
    assert joined.is_set()


async def test_window_preserves_failure_before_cutoff() -> None:
    async def failure() -> None:
        raise TimeoutError("real command deadline")

    with pytest.raises(TimeoutError, match="real command deadline"):
        await memory.diagnostic_window(failure(), 60)


async def test_collector_error_stops_and_joins_workload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F18_PARENT_CONTAINER", "tiewtrade-f18-memory-test")
    stopped = asyncio.Event()

    def broken_snapshot(parent: str) -> dict[str, Any]:
        raise memory.DockerReadError(500)

    async def run(args: argparse.Namespace) -> int:
        try:
            await asyncio.Event().wait()
            return 0
        finally:
            stopped.set()

    monkeypatch.setattr(memory, "memory_snapshot", broken_snapshot)
    monkeypatch.setattr(workload, "run", run)
    with pytest.raises(memory.DockerReadError):
        await workload.run_memory_diagnostic(argparse.Namespace(output=tmp_path / "diagnostic"))
    assert stopped.is_set()


async def test_vm_oom_increment_is_not_lost_when_container_disappears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F18_PARENT_CONTAINER", "tiewtrade-f18-memory-test")
    samples = iter([{"oom_kill": 4}, {"oom_kill": 5}])
    monkeypatch.setattr(
        memory,
        "memory_snapshot",
        lambda _: {
            "containers": [],
            "vm_counters": next(samples),
        },
    )
    with pytest.raises(RuntimeError, match="OBSERVED_OOM"):
        await memory.sample_memory(tmp_path / "oom.jsonl", asyncio.Event())
