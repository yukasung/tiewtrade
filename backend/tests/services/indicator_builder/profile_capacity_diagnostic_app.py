"""Opt-in heartbeat diagnostic for asyncio and uvloop; never acceptance evidence.

Records frame locations only, never frame locals or request data.
"""

import asyncio
import importlib
import json
import sys
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from time import (
    clock_gettime,
    monotonic,
    process_time,
    thread_time,
)

from starlette.types import Receive, Scope, Send

measured_app = importlib.import_module("profile_capacity_app").app
EVENTS: deque[dict[str, object]] = deque(maxlen=2000)
STATE: dict[str, float] = {}
HEARTBEAT: asyncio.Task[None] | None = None


def telemetry() -> None:
    while True:
        record: dict[str, object] = {"at": monotonic(), "utc": str(datetime.now(UTC))}
        for name, path in {
            "cpu_stat": "/sys/fs/cgroup/cpu.stat",
            "cpu_pressure": "/proc/pressure/cpu",
            "main_schedstat": "/proc/self/task/1/schedstat",
        }.items():
            try:
                record[name] = Path(path).read_text()
            except OSError:
                record[name] = None
        record["vm_cpu_totals"] = Path("/proc/stat").read_text().splitlines()[0]
        with Path("/evidence/diagnostic-scheduling.jsonl").open("a") as output:
            output.write(json.dumps(record) + "\n")
        threading.Event().wait(1)


async def heartbeat() -> None:
    while True:
        STATE.update(at=monotonic(), thread_cpu=thread_time(), process_cpu=process_time())
        await asyncio.sleep(0.005)


def sample_stacks(ident: int) -> None:
    # Resolve the Linux-only API without depending on the host's time stubs.
    cpu_clock: int = getattr(time, "pthread_getcpuclockid")(ident)  # noqa: B009
    while True:
        threading.Event().wait(0.01)
        previous = STATE.copy()
        now = monotonic()
        if not previous or now - previous["at"] < 0.04:
            continue
        frame = sys._current_frames().get(ident)
        stack: list[dict[str, object]] = []
        while frame is not None and len(stack) < 24:
            stack.append(
                {
                    "file": frame.f_code.co_filename,
                    "line": frame.f_lineno,
                    "function": frame.f_code.co_name,
                }
            )
            frame = frame.f_back
        EVENTS.append(
            {
                "kind": "heartbeat_gap",
                "at": now,
                "wall_seconds": now - previous["at"],
                "thread_cpu_seconds": clock_gettime(cpu_clock) - previous["thread_cpu"],
                "process_cpu_seconds": process_time() - previous["process_cpu"],
                "stack": stack,
            }
        )


def start_monitor() -> None:
    global HEARTBEAT
    if HEARTBEAT is not None:
        return
    loop = asyncio.get_running_loop()
    EVENTS.append(
        {
            "kind": "monitor_started",
            "loop_class": type(loop).__module__ + "." + type(loop).__name__,
            "method": "heartbeat_and_thread_watchdog",
        }
    )
    HEARTBEAT = asyncio.create_task(heartbeat())
    threading.Thread(target=sample_stacks, args=(threading.get_ident(),), daemon=True).start()
    threading.Thread(target=telemetry, daemon=True).start()


def flush_events() -> None:
    records = []
    while EVENTS:
        records.append(EVENTS.popleft())
    if records:
        with Path("/evidence/diagnostic-callbacks.jsonl").open("a") as output:
            for record in records:
                output.write(json.dumps(record) + "\n")


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    start_monitor()
    try:
        await measured_app(scope, receive, send)
    finally:
        flush_events()
