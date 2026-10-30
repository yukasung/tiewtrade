"""Explicit RESET workload, independent of positive five-command trading cycles."""

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, time
from uuid import UUID, uuid5

from tests.infra.execution_market.profile_workload import FaultEvent, FaultGate


@dataclass(frozen=True)
class ScheduledReset:
    owner: UUID
    offset_seconds: float
    idempotency_key: UUID


@dataclass
class ResetProgress:
    expected: int
    offered: int = 0
    applied: int = 0
    failed: int = 0

    @property
    def passed(self) -> bool:
        return self.offered == self.applied == self.expected and self.failed == 0


def reset_schedule(
    owners: Sequence[UUID],
    *,
    selected: UUID,
    run_id: UUID,
    faults: Sequence[FaultEvent] = (),
) -> list[ScheduledReset]:
    if len(owners) != 100 or len(set(owners)) != 100 or selected not in owners:
        raise ValueError("100 unique RESET owners required")
    windows = sorted((f.offset_seconds, f.offset_seconds + f.duration_seconds) for f in faults)
    ordered = [owner for owner in owners if owner != selected] + [selected]
    due = 180.0
    result = []
    for owner in ordered:
        for start, end in windows:
            if start <= due < end:
                due = float(end)
        result.append(ScheduledReset(owner, due, uuid5(run_id, f"scheduled-reset:{owner}")))
        due += 1
    return result


async def run_resets(
    plan: Sequence[ScheduledReset],
    *,
    started: float,
    recovery_complete: asyncio.Event,
    apply: Callable[[UUID, UUID], Awaitable[UUID]],
    path: Path,
    progress: ResetProgress,
    gate: FaultGate | None = None,
) -> None:
    previous: float | None = None
    if progress.expected != len(plan):
        raise ValueError("RESET inventory/count mismatch")
    with path.open("a") as stream:
        for item in plan:
            due = started + item.offset_seconds
            if previous is not None:
                due = max(due, previous + 1)
            await asyncio.sleep(max(0, due - monotonic()))
            if not recovery_complete.is_set():
                raise RuntimeError("F18_RECOVERY_NOT_COMPLETE_BEFORE_SCHEDULED_RESET")
            if gate is not None:
                # Do not change the trading gate's active-cycle count or its pause clock.
                while True:
                    await gate.open.wait()
                    if gate.open.is_set():
                        break
            offered = monotonic()
            previous = offered
            progress.offered += 1
            record: dict[str, object] = {
                "owner": str(item.owner),
                "idempotency_key": str(item.idempotency_key),
                "scheduled_offset_seconds": item.offset_seconds,
                "offered_elapsed_seconds": offered - started,
                "offered_at": time(),
            }
            stream.write(json.dumps({**record, "event": "OFFERED"}) + "\n")
            stream.flush()
            try:
                async with asyncio.timeout(60):
                    receipt = await apply(item.owner, item.idempotency_key)
                    if monotonic() - offered > 60:
                        raise TimeoutError("scheduled RESET deadline exceeded")
                progress.applied += 1
                record.update(event="APPLIED", request_id=str(receipt))
            except BaseException as error:
                progress.failed += 1
                record.update(event="FAILED", error_type=type(error).__name__)
                raise
            finally:
                record.update(seconds=monotonic() - offered, completed_at=time())
                stream.write(json.dumps(record) + "\n")
                stream.flush()


async def run_scheduled_work(
    cycles: Awaitable[object], resets: Awaitable[object], faults: Awaitable[object] | None = None
) -> None:
    tasks = [
        asyncio.ensure_future(operation)
        for operation in (cycles, resets, faults)
        if operation is not None
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
