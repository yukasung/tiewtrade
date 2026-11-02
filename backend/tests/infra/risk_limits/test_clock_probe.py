"""NC21 uncertainty/collection/cleanup checks without starting containers or workloads."""

import ast
import asyncio
import copy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.infra.risk_limits import profile_clock_probe as probe


def sample(mono: int, offset: int = 10000, width: int = 2) -> probe.Sample:
    return probe.Sample(
        pid=1,
        mono_before_ns=mono,
        wall_ns=mono + offset,
        mono_after_ns=mono + width,
        resolution_pad_ns=1,
    )


@pytest.mark.parametrize(
    "offset,expected", [(10000, "OVERLAP"), (9000, "OFFSET_DECREASE"), (11000, "OFFSET_INCREASE")]
)
def test_within_domain_offset_movement(offset: int, expected: str) -> None:
    result = probe.movement(sample(100), sample(200, offset), 100)
    assert result["classification"] == expected
    # A backward offset can occur while consecutive wall readings still increase.
    if offset == 9000:
        assert probe.movement(sample(100), sample(10000, offset), 100)["wall_delta_ns"] > 0


def test_slow_read_and_transport_uncertainty_do_not_claim_localization() -> None:
    assert (
        probe.movement(sample(0, width=1000), sample(10000), 100)["classification"]
        == "UNKNOWN_SLOW_READ"
    )
    assert probe.transport(sample(0), sample(50, offset=90000), sample(200), 100)[
        "classification"
    ].startswith("UNKNOWN")
    assert probe.transport(sample(0), sample(50, offset=90000), sample(80, offset=11000), 100)[
        "classification"
    ].startswith("UNKNOWN")
    result = probe.transport(sample(0), sample(50, offset=90000), sample(80), 100)
    assert result["classification"] == "CONDITIONAL_WALL_OFFSET_BOUND"
    assert result["guest_minus_host_low_ns"] <= 80000 <= result["guest_minus_host_high_ns"]
    with pytest.raises(ValueError, match="MONOTONIC_REVERSED"):
        probe.interval(sample(0, width=-1))


def test_journal_cap_and_write_failure_are_explicit() -> None:
    stream = io.StringIO()
    journal = probe.Journal(stream, limit=1)
    journal.append({"sequence": 0})
    with pytest.raises(RuntimeError, match="TRUNCATED"):
        journal.append({"sequence": 1})
    assert journal.count == 1 and len(stream.getvalue().splitlines()) == 1

    class FailedStream(io.StringIO):
        def write(self, value: str) -> int:
            raise OSError("disk failure")

    with pytest.raises(OSError):
        probe.Journal(FailedStream()).append({"sequence": 0})


class Writer:
    def __init__(self) -> None:
        self.closed = False
        self.writes: list[bytes] = []
        self.entered = asyncio.Event()

    def write(self, data: bytes) -> None:
        self.writes.append(data)
        self.entered.set()

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


async def test_collector_sequence_and_full_window_are_deterministic() -> None:
    reader = asyncio.StreamReader(limit=probe.MAX_LINE)
    for seq in range(2):
        reader.feed_data(
            (
                json.dumps({"sequence": seq, "sample": sample(seq * 100000000, 90000000)}) + "\n"
            ).encode()
        )
    writer = Writer()
    stream = io.StringIO()
    clock = 0

    async def sleep(seconds: float) -> None:
        nonlocal clock
        clock += int(seconds * 1e9)

    result = await probe.capture(
        reader,
        writer,
        probe.Journal(stream),
        seconds=0.2,
        rate=10,
        tick=lambda: clock,
        sample=lambda: sample(clock),
        sleep=sleep,
    )
    assert result["complete"] and result["records"] == 2 and result["elapsed_ns"] == 200000000
    assert writer.closed and writer.writes == [b"0\n", b"1\n"]
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert rows[1]["sequence"] == 1 and rows[1]["guest"]["mono_before_ns"] == 100000000


async def test_missing_sequence_and_cancellation_close_channel() -> None:
    reader = asyncio.StreamReader(limit=probe.MAX_LINE)
    reader.feed_data((json.dumps({"sequence": 1, "sample": sample(0)}) + "\n").encode())
    writer = Writer()
    with pytest.raises(RuntimeError, match="SEQUENCE_GAP"):
        await probe.capture(reader, writer, probe.Journal(io.StringIO()), seconds=1, rate=10)
    assert writer.closed
    reader = asyncio.StreamReader(limit=probe.MAX_LINE)
    writer = Writer()
    task = asyncio.create_task(
        probe.capture(reader, writer, probe.Journal(io.StringIO()), seconds=1, rate=10)
    )
    await writer.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert writer.closed


async def test_cleanup_joins_child_and_only_stops_its_own_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = Writer()
    process: Any = SimpleNamespace(stdin=writer, wait=AsyncMock(side_effect=[TimeoutError, 0]))
    stopper = SimpleNamespace(wait=AsyncMock(return_value=0))
    start = AsyncMock(return_value=stopper)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", start)
    await probe.cleanup(process, probe.CONTAINER)
    assert writer.closed and process.wait.await_count == 2
    assert start.call_args.args == ("docker", "stop", "--time", "2", probe.CONTAINER)


def valid_inventory() -> dict[str, Any]:
    return {
        "Name": probe.CONTAINER,
        "Image": probe.IMAGE_ID,
        "Mounts": [],
        "Config": {"User": "65534:65534", "Env": ["PATH=/usr/bin"]},
        "HostConfig": {
            "NanoCpus": 100000000,
            "Memory": 67108864,
            "MemorySwap": 67108864,
            "PidsLimit": 32,
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "Privileged": False,
            "CapAdd": None,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
        },
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("NanoCpus", 200000000),
        ("Memory", 134217728),
        ("ReadonlyRootfs", False),
        ("NetworkMode", "host"),
        ("Privileged", True),
        ("CapAdd", ["SYS_TIME"]),
    ],
)
def test_inventory_rejects_privilege_resource_or_network_expansion(field: str, value: Any) -> None:
    original = valid_inventory()
    assert probe.validate_inventory(original)["no_application_env"]
    bad = copy.deepcopy(original)
    bad["HostConfig"][field] = value
    with pytest.raises(RuntimeError, match="INVENTORY_MISMATCH"):
        probe.validate_inventory(bad)


def test_probe_imports_only_stdlib_and_never_calls_clock_setters() -> None:
    tree = ast.parse(Path(probe.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module is not None and node.module.split(".")[0] in sys.stdlib_module_names
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            assert name not in {"clock_settime", "clock_settime_ns", "adjtime", "settimeofday"}


async def test_delayed_sampling_marks_evidence_incomplete_without_discarding() -> None:
    reader = asyncio.StreamReader(limit=probe.MAX_LINE)
    for seq in range(2):
        reader.feed_data(
            (json.dumps({"sequence": seq, "sample": sample(seq * 100000000)}) + "\n").encode()
        )
    clock = 0
    calls = 0

    async def sleep(seconds: float) -> None:
        nonlocal clock, calls
        clock += int(seconds * 1e9)
        calls += 1
        if calls == 1:
            clock += 100000000

    stream = io.StringIO()
    result = await probe.capture(
        reader,
        Writer(),
        probe.Journal(stream),
        seconds=0.2,
        rate=10,
        tick=lambda: clock,
        sample=lambda: sample(clock),
        sleep=sleep,
    )
    assert not result["complete"] and result["cadence_gaps"] == 1
    assert result["records"] == len(stream.getvalue().splitlines()) == 2


async def test_run_cancellation_preserves_partial_status_and_joins_guest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b'{"event":"READY","pid":1,"clocks":{}}\n')
    writer = Writer()
    child = SimpleNamespace(
        stdin=writer, stdout=reader, returncode=0, wait=AsyncMock(return_value=0)
    )

    async def inspection(*args: str) -> Any:
        if args[0] == "info":
            return {
                "NCPU": 8,
                "MemTotal": 3043373056,
                "ServerVersion": "test",
                "KernelVersion": "test",
            }
        if args[0] == "image":
            return [{"Id": probe.IMAGE_ID, "Architecture": "arm64"}]
        return [valid_inventory()]

    monkeypatch.setattr(probe, "docker_json", inspection)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=child))
    monkeypatch.setattr(probe, "capture", AsyncMock(side_effect=asyncio.CancelledError))
    output = tmp_path / "trace"
    with pytest.raises(asyncio.CancelledError):
        await probe.run(output)
    result = json.loads((output / "result.json").read_text())
    assert not result["complete"] and not result["acceptance_result"]
    assert result["error_type"] == "CancelledError" and result["records_captured"] == 0
    assert writer.closed and child.wait.await_count == 1


def test_transport_never_compares_absolute_monotonic_origins() -> None:
    a = sample(50, 90000)
    other_origin = sample(10**15, 90050 - 10**15)
    assert probe.transport(sample(0), a, sample(80), 100) == probe.transport(
        sample(0), other_origin, sample(80), 100
    )
    assert (
        probe.transport(sample(0), sample(50, width=101), sample(80), 100)["classification"]
        == "UNKNOWN_SLOW_GUEST"
    )
    assert (
        probe.movement(sample(100), sample(50), 100)["classification"] == "UNKNOWN_MONOTONIC_ORDER"
    )


@pytest.mark.parametrize("requests", ["1\n", "true\n", "x" * 4097])
def test_guest_rejects_gaps_non_integer_requests_and_large_messages(
    monkeypatch: pytest.MonkeyPatch,
    requests: str,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(requests))
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    with pytest.raises(ValueError):
        probe.guest()


def test_guest_returns_exact_sequence_and_same_sampler(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO("0\n1\n"))
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(probe, "read_clock", lambda: sample(50))
    probe.guest()
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert rows[0]["event"] == "READY" and "clocks" in rows[0]
    assert [r["sequence"] for r in rows[1:]] == [0, 1]
    assert all(r["sample"] == sample(50) for r in rows[1:])
