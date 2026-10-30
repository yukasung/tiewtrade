"""R28: bounded client demand, never an API throughput/admission guarantee."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tiewtrade.infra.db import DatabaseRole, user_session


@dataclass(frozen=True)
class Slot:
    owner: UUID
    cycle: int
    due: float


def demand_slots(owners: Sequence[UUID], cycles: int, rate: int) -> list[Slot]:
    if not owners or len(set(owners)) != len(owners) or cycles < 1 or rate < 1:
        raise ValueError("unique owners, positive cycles/rate required")
    return [
        Slot(owner, number, (number * len(owners) + index) * 5 / rate)
        for number in range(cycles)
        for index, owner in enumerate(owners)
    ]


@dataclass
class Progress:
    owners: Sequence[UUID]
    planned: int
    started: dict[UUID, list[int]] = field(default_factory=dict)
    completed: dict[UUID, list[int]] = field(default_factory=dict)
    decisions: set[tuple[UUID, int]] = field(default_factory=set)
    active: set[UUID] = field(default_factory=set)
    backpressured: int = 0
    failed: int = 0
    peak_active: int = 0

    def decide(self, slot: Slot, start: bool) -> None:
        key = (slot.owner, slot.cycle)
        if key in self.decisions or slot.owner not in self.owners:
            raise ValueError("duplicate or foreign slot")
        if start and slot.owner in self.active:
            raise ValueError("owner already active")
        self.decisions.add(key)
        if start:
            self.active.add(slot.owner)
            self.started.setdefault(slot.owner, []).append(slot.cycle)
            self.peak_active = max(self.peak_active, len(self.active))
        else:
            self.backpressured += 1

    @property
    def counts(self) -> dict[UUID, int]:
        return {owner: len(self.completed.get(owner, [])) for owner in self.owners}

    def summary(self) -> dict[str, object]:
        started, completed = sum(map(len, self.started.values())), sum(self.counts.values())
        return {
            "planned_slots": self.planned,
            "planned_logical_commands": self.planned * 5,
            "started_cycles": started,
            "completed_cycles": completed,
            "not_submitted_backpressure": self.backpressured,
            "active_cycles": len(self.active),
            "failed_cycles": self.failed,
            "peak_active_cycles": self.peak_active,
            "completed_by_owner": {str(o): n for o, n in self.counts.items()},
            "conserved": len(self.decisions) == self.planned == started + self.backpressured,
            "all_started_complete": started == completed and not self.failed and not self.active,
        }


async def run_saturation(
    slots: Sequence[Slot],
    *,
    started: float,
    duration: float,
    drain: float,
    operation: Callable[[UUID, int], Awaitable[None]],
    progress: Progress,
    path: Path,
) -> None:
    if len(slots) != progress.planned or not slots or slots[-1].due >= duration:
        raise ValueError("plan/window mismatch")
    by_key = {(slot.owner, slot.cycle): slot for slot in slots}
    if (
        len(by_key) != len(slots)
        or any(
            slot.owner not in progress.owners or slot.due < 0 or slot.cycle < 0 for slot in slots
        )
        or list(slots) != sorted(slots, key=lambda slot: slot.due)
    ):
        raise ValueError("invalid or duplicate demand plan")
    active: dict[UUID, asyncio.Task[None]] = {}
    with path.open("x") as stream:

        def record(slot: Slot, state: str) -> None:
            stream.write(
                json.dumps(
                    {
                        "owner": str(slot.owner),
                        "cycle": slot.cycle,
                        "due_seconds": slot.due,
                        "state": state,
                        "elapsed_seconds": monotonic() - started,
                        "observed_at": time(),
                    }
                )
                + "\n"
            )
            stream.flush()

        async def work(slot: Slot) -> None:
            try:
                await operation(slot.owner, slot.cycle)
                progress.completed.setdefault(slot.owner, []).append(slot.cycle)
                record(slot, "COMPLETE")
            except BaseException as error:
                progress.failed += 1
                record(slot, "FAILED:" + type(error).__name__)
                raise
            finally:
                progress.active.remove(slot.owner)

        try:
            async with asyncio.timeout_at(started + duration + drain):
                for slot in slots:
                    await asyncio.sleep(max(0, started + slot.due - monotonic()))
                    for owner, task in list(active.items()):
                        if task.done():
                            await task  # Do not reclassify failed work as backpressure.
                            del active[owner]
                    if slot.owner in active:
                        progress.decide(slot, False)
                        record(slot, "NOT_SUBMITTED_BACKPRESSURE")
                        continue
                    if monotonic() >= started + duration:
                        raise TimeoutError("W2 producer missed start-window boundary")
                    progress.decide(slot, True)
                    record(slot, "STARTED")
                    active[slot.owner] = asyncio.create_task(work(slot))
                await asyncio.sleep(max(0, started + duration - monotonic()))
                await asyncio.gather(*active.values())
                if monotonic() - started > duration + drain:
                    raise TimeoutError("W2 global drain exceeded")
        finally:
            for task in active.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*active.values(), return_exceptions=True)
            for owner in list(progress.active):
                # Cancellation can arrive before a newly created coroutine starts.
                progress.failed += 1
                record(by_key[(owner, progress.started[owner][-1])], "FAILED:CancelledBeforeStart")
                progress.active.remove(owner)


def expected_requests(
    owner: f15.OwnerState,
    run_id: UUID,
    slots: Sequence[int],
    baseline: int,
    reseed: int,
) -> set[tuple[str, UUID, UUID]]:
    intents = [f15.baseline(owner, run_id, index) for index in range(baseline + reseed)]
    for number in slots:
        intents.extend(
            (
                f15.market_buy(owner, run_id, number),
                f15.limit_sell(owner, run_id, number),
                f15.market_sell(owner, run_id, number),
            )
        )
    expected = {("NEW", intent.idempotency_key, intent.order_id) for intent in intents}
    expected.update(
        (
            "CANCEL",
            f15.identity(run_id, owner.user_id, n, "cancel-key"),
            f15.limit_sell(owner, run_id, n).order_id,
        )
        for n in slots
    )
    return expected


async def verify_identities(
    engine: AsyncEngine,
    owners: list[f15.OwnerState],
    run_id: UUID,
    progress: Progress,
    baseline: int,
    extra_cancels: dict[UUID, int],
    path: Path,
) -> bool:
    async def one(owner: f15.OwnerState) -> dict[str, object]:
        expected = expected_requests(
            owner,
            run_id,
            progress.completed.get(owner.user_id, []),
            baseline,
            extra_cancels.get(owner.user_id, 0),
        )
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            rows = (
                (
                    await session.execute(
                        """SELECT i.id request_id,i.action,i.idempotency_key,
              i.order_id,r.command_id,r.state intake_state,c.state command_state
              FROM paper_order_requests i
              LEFT JOIN paper_order_request_results r ON r.request_id=i.id
              LEFT JOIN paper_order_command_results c ON c.command_id=r.command_id
              WHERE i.episode_id=:episode ORDER BY i.id""",
                        {"episode": owner.wallet.episode_id},
                    )
                )
                .mappings()
                .all()
            )
            orders = (
                (
                    await session.execute(
                        "SELECT id FROM paper_orders WHERE episode_id=:episode",
                        {"episode": owner.wallet.episode_id},
                    )
                )
                .scalars()
                .all()
            )
        actual = {
            (str(r["action"]), UUID(str(r["idempotency_key"])), UUID(str(r["order_id"])))
            for r in rows
        }
        expected_orders = {order for action, _, order in expected if action == "NEW"}
        return {
            "owner": str(owner.user_id),
            "expected_requests": len(expected),
            "actual_requests": len(rows),
            "rows": [dict(row) for row in rows],
            "passed": actual == expected
            and len(rows) == len(actual)
            and {UUID(str(o)) for o in orders} == expected_orders
            and len(orders) == len(expected_orders)
            and all(
                r["intake_state"] == "TRANSFERRED" and r["command_state"] == "SUCCEEDED"
                for r in rows
            ),
        }

    observations = await f15.bounded_map(owners, one)
    f15.save(path, observations)
    return all(row["passed"] for row in observations)
