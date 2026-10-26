"""Linux-only measurement wrapper for explicit capacity containers.

The real app, authentication, admission and reader remain in use. The optional
file barrier pauses only an already-admitted probe, before any indicator query.
No metrics contain request parameters, credentials, bodies or cursor tokens.
"""

import asyncio
import gc
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID

from sqlalchemy import Result
from starlette.types import Message, Receive, Scope, Send

from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.realtime.admission import RedisAdmission
from tiewtrade.services.api.app import app as real_app
from tiewtrade.services.api.indicator_admission import IndicatorBudget

COUNTS: ContextVar[list[int] | None] = ContextVar("capacity_counts", default=None)
BARRIER: ContextVar[bool] = ContextVar("capacity_barrier", default=False)
GC_EVENTS: ContextVar[dict[str, Any] | None] = ContextVar("capacity_gc_events", default=None)
EXECUTE = UserSession.execute
RESERVE = IndicatorBudget.reserve


def observe_gc(phase: str, info: dict[str, int]) -> None:
    events = GC_EVENTS.get()
    if events is None:
        return
    generation = info["generation"]
    if phase == "start":
        events["started"][generation] = monotonic()
        return
    started = events["started"].pop(generation, None)
    if started is not None:
        events["pauses"].append((generation, monotonic() - started))


gc.callbacks.append(observe_gc)


async def execute(
    self: UserSession, statement: str, parameters: Mapping[str, object] | None = None
) -> Result[Any]:
    counts = COUNTS.get()
    if counts is not None and "from market_candles" in statement.lower():
        counts[0] += 1
    return await EXECUTE(self, statement, parameters)


@asynccontextmanager
async def reserve(
    self: IndicatorBudget, admission: RedisAdmission, user_id: UUID
) -> AsyncIterator[None]:
    async with RESERVE(self, admission, user_id):
        if BARRIER.get():
            Path("/tmp/capacity-entered").write_text("ready", encoding="ascii")
            async with asyncio.timeout(10):
                while not Path("/tmp/capacity-release").exists():
                    await asyncio.sleep(0.005)
        yield


UserSession.execute = execute  # type: ignore[method-assign]
IndicatorBudget.reserve = reserve  # type: ignore[method-assign]


def memory_bytes(field: str) -> int:
    return next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith(field + ":")
    )


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http" or scope["path"] != "/market-data/indicators":
        await real_app(scope, receive, send)
        return
    counts = [0]
    count_token = COUNTS.set(counts)
    barrier_token = BARRIER.set((b"x-capacity-barrier", b"1") in scope["headers"])
    gc_events: dict[str, Any] = {"started": {}, "pauses": []}
    gc_token = GC_EVENTS.set(gc_events)
    baseline = memory_bytes("VmRSS")
    started = previous = monotonic()
    max_lag = 0.0
    status = 0
    body_bytes = 0

    async def watcher() -> None:
        nonlocal previous, max_lag
        while True:
            await asyncio.sleep(0.005)
            now = monotonic()
            max_lag = max(max_lag, now - previous - 0.005)
            previous = now

    async def measured_send(message: Message) -> None:
        nonlocal status, body_bytes
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            body_bytes += len(message.get("body", b""))
        await send(message)

    task = asyncio.create_task(watcher())
    try:
        await real_app(scope, receive, measured_send)
    finally:
        elapsed = monotonic() - started
        max_lag = max(max_lag, monotonic() - previous - 0.005)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        # VmHWM includes earlier process peaks, so this is conservative.
        peak_delta = max(0, memory_bytes("VmHWM") - baseline)
        with Path("/evidence/api-metrics.jsonl").open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(
                    {
                        "recorded_at": str(datetime.now(UTC)),
                        "kind": next(
                            (
                                v.decode("ascii")
                                for k, v in scope["headers"]
                                if k == b"x-capacity-kind"
                                and v in (b"rejected-busy", b"rejected-rate")
                            ),
                            "accepted",
                        ),
                        "status": status,
                        "seconds": elapsed,
                        "max_lag_seconds": max_lag,
                        "rss_delta_upper_bytes": peak_delta,
                        "body_bytes": body_bytes,
                        "candle_queries": counts[0],
                        "gc_collections": len(gc_events["pauses"]),
                        "gc_max_pause_seconds": max(
                            (pause for _, pause in gc_events["pauses"]), default=0.0
                        ),
                        "gc_generations": [generation for generation, _ in gc_events["pauses"]],
                        "frozen_objects": gc.get_freeze_count(),
                        "barrier": BARRIER.get(),
                    }
                )
                + "\n"
            )
        COUNTS.reset(count_token)
        BARRIER.reset(barrier_token)
        GC_EVENTS.reset(gc_token)
