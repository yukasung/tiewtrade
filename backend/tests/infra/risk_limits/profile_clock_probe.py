"""NC21 stdlib-only passive clock comparison. Never imports application or DB code."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from time import get_clock_info, monotonic_ns, time_ns
from typing import Any, TextIO, TypedDict

MAX_RECORDS = 30000
MAX_LINE = 4096
IMAGE = "tiewtrade-f19-set5-runner:20261101"
CONTAINER = "tiewtrade-f19-nc21-clock-r1"
IMAGE_ID = "sha256:75ec49eb0803666de94a6248d9edd5fa258c7b651531dbc5ea3d9ff8b1735f88"


class Sample(TypedDict):
    pid: int
    mono_before_ns: int
    wall_ns: int
    mono_after_ns: int
    resolution_pad_ns: int


def clock_properties() -> dict[str, Any]:
    return {name: vars(get_clock_info(name)) for name in ("time", "monotonic")}


def read_clock() -> Sample:
    # Resolve metadata before the bracket, not between its reads.
    pad = math.ceil(
        (get_clock_info("time").resolution + get_clock_info("monotonic").resolution) * 1e9
    )
    pid = os.getpid()
    before = monotonic_ns()
    wall = time_ns()
    after = monotonic_ns()
    return Sample(
        pid=pid, mono_before_ns=before, wall_ns=wall, mono_after_ns=after, resolution_pad_ns=pad
    )


def interval(sample: Sample) -> tuple[int, int]:
    if sample["mono_after_ns"] < sample["mono_before_ns"]:
        raise ValueError("CLOCK_MONOTONIC_REVERSED")
    pad = sample["resolution_pad_ns"]
    return (
        sample["wall_ns"] - sample["mono_after_ns"] - pad,
        sample["wall_ns"] - sample["mono_before_ns"] + pad,
    )


def movement(previous: Sample, current: Sample, max_read_ns: int) -> dict[str, Any]:
    # These offsets are compared only within one domain. Smooth slew can also move them.
    before, after = interval(previous), interval(current)
    monotonic_order = current["mono_before_ns"] >= previous["mono_after_ns"]
    slow = any(s["mono_after_ns"] - s["mono_before_ns"] > max_read_ns for s in (previous, current))
    low, high = after[0] - before[1], after[1] - before[0]
    return {
        "offset_change_low_ns": low,
        "offset_change_high_ns": high,
        "classification": "UNKNOWN_MONOTONIC_ORDER"
        if not monotonic_order
        else "UNKNOWN_SLOW_READ"
        if slow
        else "OFFSET_DECREASE"
        if high < 0
        else "OFFSET_INCREASE"
        if low > 0
        else "OVERLAP",
        "wall_delta_ns": current["wall_ns"] - previous["wall_ns"],
        "mono_delta_ns": current["mono_before_ns"] - previous["mono_before_ns"],
    }


def transport(before: Sample, guest: Sample, after: Sample, period_ns: int) -> dict[str, Any]:
    host = movement(before, after, period_ns)
    elapsed = after["mono_after_ns"] - before["mono_before_ns"]
    if host["classification"] != "OVERLAP" or not 0 <= elapsed <= period_ns:
        return {"classification": "UNKNOWN_HOST_CHANGE_OR_WIDE_RTT", "rtt_upper_ns": elapsed}
    if guest["mono_after_ns"] - guest["mono_before_ns"] > period_ns:
        return {"classification": "UNKNOWN_SLOW_GUEST", "rtt_upper_ns": elapsed}
    pad = before["resolution_pad_ns"] + guest["resolution_pad_ns"] + after["resolution_pad_ns"]
    return {
        "classification": "CONDITIONAL_WALL_OFFSET_BOUND",
        "rtt_upper_ns": elapsed,
        "guest_minus_host_low_ns": guest["wall_ns"] - after["wall_ns"] - pad,
        "guest_minus_host_high_ns": guest["wall_ns"] - before["wall_ns"] + pad,
    }


class Journal:
    def __init__(self, stream: TextIO, limit: int = MAX_RECORDS) -> None:
        self.stream, self.limit, self.count = stream, limit, 0

    def append(self, row: dict[str, Any]) -> None:
        if self.count >= self.limit:
            raise RuntimeError("CLOCK_TRACE_TRUNCATED")
        encoded = json.dumps(row) + "\n"
        if len(encoded) > MAX_LINE:
            raise RuntimeError("CLOCK_TRACE_RECORD_TOO_LARGE")
        if self.stream.write(encoded) != len(encoded):
            raise OSError("CLOCK_TRACE_SHORT_WRITE")
        self.count += 1
        if self.count % 10 == 0:
            self.stream.flush()


def guest() -> None:
    sys.stdout.write(
        json.dumps({"event": "READY", "pid": os.getpid(), "clocks": clock_properties()}) + "\n"
    )
    sys.stdout.flush()
    sequence = 0
    while line := sys.stdin.readline(MAX_LINE + 1):
        if len(line) > MAX_LINE:
            raise ValueError("CLOCK_REQUEST_TOO_LARGE")
        request = json.loads(line)
        if type(request) is not int or request != sequence or sequence >= MAX_RECORDS:
            raise ValueError("CLOCK_REQUEST_SEQUENCE")
        sys.stdout.write(json.dumps({"sequence": sequence, "sample": read_clock()}) + "\n")
        sys.stdout.flush()
        sequence += 1


async def capture(
    reader: asyncio.StreamReader,
    writer: Any,
    journal: Journal,
    *,
    seconds: float,
    rate: int,
    tick: Callable[[], int] = monotonic_ns,
    sample: Callable[[], Sample] = read_clock,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, Any]:
    expected = math.ceil(seconds * rate)
    if not 0 < expected <= journal.limit or not 1 <= rate <= 10:
        raise ValueError("bounded clock observation required")
    period = 1_000_000_000 // rate
    duration_ns = int(seconds * 1e9)
    started = tick()
    cadence_gaps = 0
    try:
        for sequence in range(expected):
            due = started + sequence * period
            await sleep(max(0, due - tick()) / 1e9)
            if tick() >= started + duration_ns:
                raise RuntimeError("CLOCK_TRACE_WINDOW_INCOMPLETE")
            lag = max(0, tick() - due)
            cadence_gaps += lag >= period
            before = sample()
            writer.write((str(sequence) + "\n").encode())
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout=5)
            after = sample()
            if not raw or len(raw) > MAX_LINE:
                raise RuntimeError("CLOCK_TRACE_RESPONSE_MISSING_OR_OVERSIZED")
            response = json.loads(raw)
            if response["sequence"] != sequence:
                raise RuntimeError("CLOCK_TRACE_SEQUENCE_GAP")
            other: Sample = response["sample"]
            interval(other)
            journal.append(
                {
                    "sequence": sequence,
                    "host_before": before,
                    "guest": other,
                    "host_after": after,
                    "request_lag_ns": lag,
                    "transport": transport(before, other, after, period),
                }
            )
        await sleep(max(0, started + duration_ns - tick()) / 1e9)
        return {
            "expected": expected,
            "records": journal.count,
            "elapsed_ns": tick() - started,
            "complete": journal.count == expected and cadence_gaps == 0,
            "cadence_gaps": cadence_gaps,
        }
    finally:
        writer.close()
        journal.stream.flush()


async def cleanup(process: Any, name: str) -> None:
    if process.stdin is not None:
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        stopper = await asyncio.create_subprocess_exec(
            "docker",
            "stop",
            "--time",
            "2",
            name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(stopper.wait(), timeout=10)
        await asyncio.wait_for(process.wait(), timeout=5)


async def docker_json(*args: str) -> Any:
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    if process.returncode:
        raise RuntimeError("CLOCK_DOCKER_INSPECTION_FAILED")
    return json.loads(stdout)


def validate_inventory(info: dict[str, Any]) -> dict[str, Any]:
    config = info["HostConfig"]
    if not (
        config["NanoCpus"] == 100000000
        and config["Memory"] == 67108864
        and config["MemorySwap"] == 67108864
        and config["PidsLimit"] == 32
        and config["ReadonlyRootfs"]
        and config["NetworkMode"] == "none"
        and not config["Privileged"]
        and not config["CapAdd"]
        and "ALL" in config["CapDrop"]
        and not info["Mounts"]
        and info["Config"]["User"] == "65534:65534"
        and "no-new-privileges" in config["SecurityOpt"]
        and not any(e.startswith("TIEWTRADE_") for e in info["Config"]["Env"])
    ):
        raise RuntimeError("CLOCK_OBSERVER_INVENTORY_MISMATCH")
    return {
        "name": info["Name"],
        "image": info["Image"],
        "host_config": {
            k: config[k]
            for k in (
                "NanoCpus",
                "Memory",
                "MemorySwap",
                "ReadonlyRootfs",
                "NetworkMode",
                "Privileged",
                "CapAdd",
                "CapDrop",
                "SecurityOpt",
                "PidsLimit",
            )
        },
        "mounts": info["Mounts"],
        "user": info["Config"]["User"],
        "no_application_env": True,
    }


async def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).read_text()
    (output / "probe-source.py").write_text(source)
    metadata: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "host_clocks": clock_properties(),
        "seconds": 1200,
        "rate": 10,
        "acceptance_result": False,
        "complete": False,
        "limits": {"records": MAX_RECORDS, "line_bytes": MAX_LINE},
        "transport_assumption": "conditional on no unobserved host wall step during exchange",
    }
    process = None
    try:
        vm = await docker_json("info", "--format", "{{json .}}")
        if vm["NCPU"] != 8 or vm["MemTotal"] != 3043373056:
            raise RuntimeError("CLOCK_VM_PROFILE_MISMATCH")
        image = (await docker_json("image", "inspect", IMAGE))[0]
        if image["Id"] != IMAGE_ID or image["Architecture"] != "arm64":
            raise RuntimeError("CLOCK_IMAGE_PROFILE_MISMATCH")
        metadata["vm"] = {k: vm[k] for k in ("NCPU", "MemTotal", "ServerVersion", "KernelVersion")}
        command = [
            "docker",
            "run",
            "--name",
            CONTAINER,
            "--interactive",
            "--pull",
            "never",
            "--read-only",
            "--network",
            "none",
            "--cpus",
            "0.1",
            "--memory",
            "64m",
            "--memory-swap",
            "64m",
            "--pids-limit",
            "32",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--entrypoint",
            "/app/.venv/bin/python",
            IMAGE_ID,
            "-u",
            "-c",
            source,
            "--guest",
        ]
        metadata["command"] = [*command[: command.index("-c") + 1], "<frozen source>", "--guest"]
        with (output / "guest.stderr").open("wb") as errors:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=errors,
                limit=MAX_LINE,
            )
            assert process.stdout is not None and process.stdin is not None
            ready = json.loads(await asyncio.wait_for(process.stdout.readline(), timeout=20))
            if ready["event"] != "READY":
                raise RuntimeError("CLOCK_OBSERVER_NOT_READY")
            metadata["guest_pid"] = ready["pid"]
            metadata["guest_clocks"] = ready["clocks"]
            metadata["observer"] = validate_inventory((await docker_json("inspect", CONTAINER))[0])
            (output / "inventory.json").write_text(json.dumps(metadata, indent=2) + "\n")
            sys.stdout.write("CLOCK INVENTORY VERIFIED; starting20min/10Hz\n")
            sys.stdout.flush()
            with (output / "samples.jsonl").open("x") as stream:
                journal = Journal(stream)
                try:
                    metadata.update(
                        await capture(process.stdout, process.stdin, journal, seconds=1200, rate=10)
                    )
                finally:
                    metadata["records_captured"] = journal.count
    except BaseException as error:
        metadata.update(complete=False, error_type=type(error).__name__, error_code=str(error))
        raise
    finally:
        try:
            if process is not None:
                await cleanup(process, CONTAINER)
                metadata["guest_returncode"] = process.returncode
                if process.returncode != 0:
                    metadata["complete"] = False
        except BaseException as error:
            metadata.update(complete=False, cleanup_error=type(error).__name__)
            raise
        finally:
            metadata["ended_at"] = datetime.now(UTC).isoformat()
            (output / "result.json").write_text(json.dumps(metadata, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guest", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.guest:
        if args.output is not None:
            parser.error("guest cannot write host evidence")
        guest()
    elif args.output is None:
        parser.error("host output required")
    else:
        asyncio.run(run(args.output))


if __name__ == "__main__":
    main()
