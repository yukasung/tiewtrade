"""NC08 opt-in observations; never authoritative trading state."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from time import monotonic, process_time, time
from typing import Any

from tests.infra.execution_market.profile_workload import save

PROFILE = "paired-runtime-v1"
ROW_LIMIT = 100000
CADENCES = {"database": 1.0, "host": 1.0, "docker": 3.0}


def stamp() -> dict[str, Any]:
    return {"monotonic": monotonic(), "wall": time(), "cpu": process_time(), "pid": os.getpid()}


def interval_phase(start: float, end: float, work_start: float, work_end: float) -> str:
    if end <= work_start:
        return "readiness"
    if start >= work_end:
        return "shutdown"
    if start >= work_start and end <= work_end:
        return "measurement"
    return "cross_boundary"


class RuntimeObservation:
    def __init__(self, path: Path, *, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled
        self.phases: list[dict[str, Any]] = []
        self.ticks: list[dict[str, Any]] = []

    def mark(self, phase: str) -> None:
        if self.enabled:
            self.phases.append({"phase": phase, **stamp()})

    async def ticks_until(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            due = monotonic() + 0.1
            await asyncio.sleep(0.1)
            now = stamp()
            lag = max(0.0, now["monotonic"] - due)
            if len(self.ticks) >= ROW_LIMIT:
                raise RuntimeError("NC08_RUNTIME_TRACE_TRUNCATED")
            self.ticks.append(
                {**now, "due": due, "lag_seconds": lag, "missed_intervals": int(lag / 0.1)}
            )

    @asynccontextmanager
    async def observe(self) -> AsyncIterator[None]:
        if not self.enabled:
            yield
            return
        stop = asyncio.Event()
        failure: BaseException | None = None
        self.mark("observer_started")
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(self.ticks_until(stop))
                try:
                    yield
                finally:
                    stop.set()
        except BaseException as error:
            failure = error
            raise
        finally:
            self.mark("observer_closed")
            try:
                save(
                    self.path,
                    {
                        "phases": self.phases,
                        "ticks": self.ticks,
                        "closed": True,
                        "error": None if failure is None else type(failure).__name__,
                    },
                )
            except OSError as cleanup_error:
                if failure is None:
                    raise
                failure.add_note(f"runtime evidence cleanup failed: {type(cleanup_error).__name__}")


async def collect_one(
    family: str, collect: Callable[[], Awaitable[Any]], row: dict[str, Any]
) -> None:
    row.update(family=family, start=stamp())
    try:
        async with asyncio.timeout(10):
            row["value"] = await collect()
    except BaseException as error:
        row.update(missing=True, error=type(error).__name__)
        raise
    finally:
        row["finish"] = stamp()


async def sample_family(
    family: str, collect: Callable[[], Awaitable[Any]], path: Path, stop: asyncio.Event
) -> None:
    cadence = CADENCES[family]
    previous: float | None = None
    rows = 0
    with path.open("x") as stream:
        while not stop.is_set():
            row: dict[str, Any] = {}
            failure: BaseException | None = None
            try:
                await collect_one(family, collect, row)
            except BaseException as error:
                failure = error
                raise
            finally:
                start = row["start"]
                gap = None if previous is None else start["monotonic"] - previous
                row["start_gap_seconds"] = gap
                row["missed_ticks"] = 0 if gap is None else max(0, int(gap / cadence) - 1)
                try:
                    stream.write(json.dumps(row, default=str) + "\n")
                    stream.flush()
                except OSError as cleanup_error:
                    if failure is None:
                        raise
                    failure.add_note(
                        f"resource evidence cleanup failed: {type(cleanup_error).__name__}"
                    )
            rows += 1
            if rows >= ROW_LIMIT:
                raise RuntimeError("NC08_RESOURCE_TRACE_TRUNCATED")
            previous = start["monotonic"]
            # Never overlap or catch up. Slow samples skip ticks before the next future tick.
            elapsed = monotonic() - previous
            delay = cadence - elapsed if elapsed < cadence else cadence
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), delay)


async def resources(
    collectors: dict[str, Callable[[], Awaitable[Any]]], output: Path, stop: asyncio.Event
) -> None:
    if set(collectors) != set(CADENCES):
        raise ValueError("complete observer families required")
    async with asyncio.TaskGroup() as group:
        for family, collect in collectors.items():
            group.create_task(
                sample_family(family, collect, output / f"resource-{family}.jsonl", stop)
            )


async def finish_resources(task: asyncio.Task[None]) -> None:
    """Five-second grace; timeout cancels/joins the owned subprocesses before propagating."""
    try:
        async with asyncio.timeout(5):
            await asyncio.shield(task)
    finally:
        if not task.done():
            task.cancel()
        # Preserve the deadline/primary exception, while TaskGroup retains observer faults.
        await asyncio.gather(task, return_exceptions=True)
