"""Bounded instance-local observer timings; no SQL or global instrumentation."""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import monotonic
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine

T = TypeVar("T")
PHASES = (
    "checkout_and_setup",
    "statement_timeout",
    "lock_timeout",
    "db_clock",
    "activity",
    "locks",
    "session_exit",
)


class CaptureTiming:
    """One task and one original sample; timings include driver and scheduling."""

    def __init__(self) -> None:
        self.owner = asyncio.current_task()
        self.spans: list[dict[str, Any]] = []
        self.calls = 0

    async def measure(self, phase: str, operation: Callable[[], Awaitable[T]]) -> T:
        if asyncio.current_task() is not self.owner:
            raise ValueError("observer timing task mismatch")
        if len(self.spans) >= len(PHASES):
            raise ValueError("observer timing bound exceeded")
        span: dict[str, Any] = {"phase": phase, "started": monotonic(), "outcome": "RETURNED"}
        self.spans.append(span)
        try:
            return await operation()
        except BaseException as error:
            span["outcome"] = type(error).__name__
            raise
        finally:
            span["finished"] = monotonic()

    def validate(self) -> None:
        if [span["phase"] for span in self.spans] != list(PHASES):
            raise ValueError("observer timing incomplete")
        previous = 0.0
        for span in self.spans:
            start, end = span["started"], span["finished"]
            if (
                type(start) not in (int, float)
                or type(end) not in (int, float)
                or not math.isfinite(start)
                or not math.isfinite(end)
                or start < previous
                or end < start
                or span["outcome"] != "RETURNED"
            ):
                raise ValueError("observer timing invalid")
            previous = end


class TimedConnection:
    def __init__(self, connection: Any, timing: CaptureTiming) -> None:
        self.connection = connection
        self.timing = timing

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        index = self.timing.calls
        expected = "exec_driver_sql" if index < 2 else "execute"
        if index >= 5 or method != expected:
            raise ValueError("observer call sequence changed")
        self.timing.calls += 1
        return await self.timing.measure(
            PHASES[index + 1], lambda: getattr(self.connection, method)(*args, **kwargs)
        )

    async def exec_driver_sql(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call("exec_driver_sql", *args, **kwargs)

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call("execute", *args, **kwargs)


class TimedEngine:
    def __init__(self, engine: AsyncEngine, timing: CaptureTiming) -> None:
        self.engine = engine
        self.timing = timing

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[TimedConnection]:
        context = self.engine.connect()
        connection = await self.timing.measure("checkout_and_setup", context.__aenter__)
        try:
            yield TimedConnection(connection, self.timing)
        except BaseException as error:
            primary = error
            try:
                await self.timing.measure(
                    "session_exit",
                    lambda: context.__aexit__(type(primary), primary, primary.__traceback__),
                )
            except BaseException as cleanup_error:
                primary.add_note(f"observer session exit failed: {type(cleanup_error).__name__}")
                raise primary from cleanup_error
            raise
        else:
            await self.timing.measure("session_exit", lambda: context.__aexit__(None, None, None))


class LoopLag:
    def __init__(self) -> None:
        self.stop = asyncio.Event()
        self.count = 0
        self.maximum = 0.0
        self.total = 0.0

    async def run(self) -> None:
        while not self.stop.is_set():
            target = monotonic() + 0.05
            try:
                await asyncio.wait_for(self.stop.wait(), 0.05)
            except TimeoutError:
                lag = max(0.0, monotonic() - target)
                self.count += 1
                self.maximum = max(self.maximum, lag)
                self.total += lag

    def report(self) -> dict[str, Any]:
        return {"count": self.count, "maximum_seconds": self.maximum, "total_seconds": self.total}
