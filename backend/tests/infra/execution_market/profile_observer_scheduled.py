"""OBS-04 bounded fixture captures under load, separate from publisher triggers."""

from __future__ import annotations

import asyncio
import math
import os
from time import monotonic
from typing import Any

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market.profile_publisher_fence import FenceObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session

OFFSETS = tuple(range(15, 300, 30))


class ScheduledObservation:
    def __init__(self, *, w3_prefix: bool = False) -> None:
        if type(w3_prefix) is not bool:
            raise ValueError("scheduled profile must be explicit boolean")
        self.offsets = tuple(range(30, 2400, 60)) if w3_prefix else OFFSETS
        self.window_seconds = 2400 if w3_prefix else 300
        self.slot_seconds = 60 if w3_prefix else 30
        internal.guard_database(dict(os.environ))
        self.observer = FenceObservation(lambda: None)
        self.fixture = create_engine_for(
            DatabaseRole.MARKET_DATA, pool_size=1, max_overflow=0, pool_timeout=0.5
        )
        self.records: list[dict[str, Any]] = []
        self.task: asyncio.Task[None] | None = None
        self.started: float | None = None

    def start(self, started: float) -> None:
        if self.task is not None or not math.isfinite(started):
            raise ValueError("invalid scheduled observer start")
        self.started = started
        self.task = asyncio.create_task(self.run(started))

    async def capture(self, record: dict[str, Any]) -> None:
        # Reuse the original once-only adapter without importing workload at module load.
        from tests.infra.execution_market.profile_observer_diagnostic import capture

        async with market_data_session(self.fixture) as session:
            pid = (await session.execute("SELECT pg_backend_pid()")).scalar_one()
            statement = {
                "backend_pid": pid,
                "stage": "scheduled_fixture_idle",
                "started": monotonic(),
            }
            await capture(self.observer, statement, record)

    async def run(self, started: float) -> None:
        for offset in self.offsets:
            target = started + offset
            await asyncio.sleep(max(0, target - monotonic()))
            now = monotonic()
            record: dict[str, Any] = {
                "target": target,
                "started": now,
                "lateness_seconds": max(0, now - target),
                "outcome": "INCOMPLETE",
            }
            self.records.append(record)
            try:
                deadline = min(target + self.slot_seconds, started + self.window_seconds)
                if now >= deadline:
                    raise ValueError("scheduled observer missed slot")
                async with asyncio.timeout(max(0, deadline - monotonic())):
                    await self.capture(record)
                if monotonic() >= deadline:
                    raise ValueError("scheduled observer crossed slot boundary")
            except BaseException as error:
                record["outcome"] = type(error).__name__
                raise
            finally:
                record["finished"] = monotonic()

    def report(self) -> dict[str, Any]:
        completed = bool(
            self.task is not None
            and self.task.done()
            and not self.task.cancelled()
            and self.task.exception() is None
        )
        return {
            "status": "RECORDED"
            if completed
            and len(self.records) == len(self.offsets)
            and all(row["outcome"] == "RETURNED" for row in self.records)
            else "INCOMPLETE",
            "fixture_only": True,
            "measurement_started": self.started,
            "expected_samples": len(self.offsets),
            "records": self.records,
            "task_completed": completed,
            "task_joined": self.task is not None and self.task.done(),
        }

    async def close(self) -> None:
        primary: BaseException | None = None
        try:
            if self.task is not None:
                if not self.task.done():
                    self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
        except BaseException as error:
            primary = error
        for cleanup in (self.observer.close, self.fixture.dispose):
            try:
                await cleanup()
            except BaseException as error:
                if primary is None:
                    primary = error
                else:
                    primary.add_note(f"scheduled cleanup failed: {type(error).__name__}")
        if primary is not None:
            raise primary
