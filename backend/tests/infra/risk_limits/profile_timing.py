"""Separate the one recovery batch from the normal Paper cycle's progress budget."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic, time
from uuid import UUID


@dataclass
class CycleTiming:
    deadline: asyncio.Timeout
    started: float
    recovery_allowed: bool
    recovery_seconds: float = 0
    recovery_used: bool = False
    recovery_active: bool = False
    trading_completed_at: float | None = None
    trading_elapsed_seconds: float | None = None
    stages: list[dict[str, object]] = field(default_factory=list)


_CURRENT: ContextVar[CycleTiming | None] = ContextVar("paper_cycle_timing", default=None)


@asynccontextmanager
async def cycle_scope(
    path: Path, *, owner: UUID, number: int, recovery_allowed: bool
) -> AsyncIterator[None]:
    started, wall = monotonic(), time()
    timing: CycleTiming | None = None
    outcome = "completed"
    try:
        async with asyncio.timeout(60) as deadline:
            timing = CycleTiming(deadline, started, recovery_allowed)
            token = _CURRENT.set(timing)
            try:
                yield
                elapsed = monotonic() - started
                if elapsed - timing.recovery_seconds > 60 or elapsed > 180:
                    raise TimeoutError("normal cycle budget exceeded")
                if recovery_allowed and not timing.recovery_used:
                    raise RuntimeError("required recovery timing evidence missing")
            finally:
                _CURRENT.reset(token)
    except BaseException as error:
        outcome = type(error).__name__
        raise
    finally:
        if timing is not None:
            elapsed = monotonic() - started
            with path.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "owner": str(owner),
                            "cycle": number,
                            "started_at": wall,
                            "seconds": elapsed,
                            "normal_seconds": elapsed - timing.recovery_seconds,
                            "trading_completed_at": timing.trading_completed_at,
                            "trading_elapsed_seconds": timing.trading_elapsed_seconds,
                            "recovery_seconds": timing.recovery_seconds,
                            "recovery_used": timing.recovery_used,
                            "outcome": outcome,
                            "stages": timing.stages,
                        }
                    )
                    + "\n"
                )


@asynccontextmanager
async def recovery_scope() -> AsyncIterator[None]:
    timing = _CURRENT.get()
    if timing is None or not timing.recovery_allowed or timing.recovery_used:
        raise RuntimeError("one selected recovery phase required")
    original_deadline = timing.deadline.when()
    assert original_deadline is not None
    if original_deadline < monotonic() or timing.deadline.expired():
        raise TimeoutError("normal cycle budget exceeded before recovery")
    timing.recovery_used = True
    timing.recovery_active = True
    started = monotonic()
    timing.deadline.reschedule(min(original_deadline + 120, timing.started + 180))
    try:
        async with asyncio.timeout(120):
            yield
            if monotonic() - started > 120:
                raise TimeoutError("recovery batch budget exceeded")
    finally:
        timing.recovery_active = False
        timing.recovery_seconds = monotonic() - started
        if not timing.deadline.expired():
            timing.deadline.reschedule(
                min(original_deadline + timing.recovery_seconds, timing.started + 180)
            )


@asynccontextmanager
async def recovery_stage(name: str, *, order_id: UUID | None = None) -> AsyncIterator[None]:
    timing = _CURRENT.get()
    if timing is None or not timing.recovery_active:
        raise RuntimeError("recovery stage requires active cycle evidence")
    started, wall = monotonic(), time()
    outcome = "completed"
    try:
        yield
    except BaseException as error:
        outcome = type(error).__name__
        raise
    finally:
        timing.stages.append(
            {
                "name": name,
                "order_id": None if order_id is None else str(order_id),
                "started_at": wall,
                "seconds": monotonic() - started,
                "outcome": outcome,
            }
        )


def trading_completed() -> None:
    timing = _CURRENT.get()
    if timing is None:
        raise RuntimeError("trading completion requires cycle timing evidence")
    timing.trading_completed_at = time()
    timing.trading_elapsed_seconds = monotonic() - timing.started
