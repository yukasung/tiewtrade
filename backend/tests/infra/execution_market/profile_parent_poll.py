"""NC09 test-only parent read admission; no business state or new pool."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AbstractContextManager, asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import profile_internal as internal


def validate_options(args: argparse.Namespace) -> None:
    interval = getattr(args, "observation_poll_seconds", 0.25)
    if type(interval) not in (int, float) or interval not in (0.25, 1.0):
        raise ValueError("unsupported observation polling interval")
    if (
        interval != 0.25
        and getattr(args, "acceptance_profile", None) not in internal.RELEASE_PROFILES
    ):
        raise ValueError("representative polling requires original100 profile")
    if internal.selected(args):
        internal.validate(args)
        return
    value = getattr(args, "parent_poll_limit", None)
    if value is not None and (
        type(value) is not int
        or value != 4
        or getattr(args, "phase", None) != "SMOKE"
        or getattr(args, "worker_only", False)
        or not all(
            getattr(args, key, False)
            for key in (
                "r8_claim_budget",
                "publisher_heartbeat_per_book",
                "diagnostics",
                "final_tail_drain",
            )
        )
    ):
        raise ValueError(
            "parent poll limit4 requires the explicit diagnostic R8 heartbeat tail SMOKE parent"
        )


class ParentPollGate:
    def __init__(self, *, stream_path: Path | None = None, poll_seconds: float = 0.25) -> None:
        if type(poll_seconds) not in (int, float) or poll_seconds not in (0.25, 1.0):
            raise ValueError("unsupported observation polling interval")
        self.poll_seconds = poll_seconds
        self.semaphore = asyncio.Semaphore(4)
        self.active = 0
        self.peak = 0
        self.phase = "baseline"
        self.rows: list[dict[str, Any]] = []
        self.truncated = False
        self.stream_path = stream_path
        self.attempts = 0
        self.finished = 0

    def verify_pool(self, engine: AsyncEngine) -> None:
        pool = engine.pool
        if not isinstance(pool, QueuePool) or pool.size() != 5 or pool._max_overflow != 10:
            raise ValueError("parent poll profile requires unchanged ENGINE pool5+10")

    def scope(self, phase: str, owner: UUID) -> AbstractContextManager[None]:
        # Lazy import: the existing trace module imports the workload harness.
        from tests.infra.risk_limits.profile_pool_timing import operation_scope

        return operation_scope(phase=phase, owner=str(owner), workload_phase=self.phase)

    @asynccontextmanager
    async def permit(self, owner: UUID, kind: str) -> AsyncIterator[None]:
        if self.stream_path is None and len(self.rows) >= 100000:
            self.truncated = True
            raise RuntimeError("NC09_POLL_GATE_TRACE_TRUNCATED")
        row: dict[str, Any] = {
            "owner": str(owner),
            "kind": kind,
            "phase": self.phase,
            "started": monotonic(),
            "acquired": False,
        }
        self.attempts += 1
        if self.stream_path is None:
            self.rows.append(row)
        try:
            await self.semaphore.acquire()
            row.update(acquired=True, acquired_at=monotonic())
            row["gate_wait_seconds"] = row["acquired_at"] - row["started"]
            self.active += 1
            self.peak = max(self.peak, self.active)
            row["active"] = self.active
            with self.scope(kind, owner):
                yield
            row["outcome"] = "RETURNED"
        except BaseException as error:
            row["outcome"] = type(error).__name__
            raise
        finally:
            row["finished"] = monotonic()
            if row["acquired"]:
                self.active -= 1
                self.semaphore.release()
            else:
                row["gate_wait_seconds"] = row["finished"] - row["started"]
            if self.stream_path is not None:
                # Preserve every completed/cancelled attempt without retaining a
                # four-hour polling trace in process memory. No awaited write.
                with self.stream_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row) + "\n")
            self.finished += 1

    def save(self, path: Path) -> None:
        from tests.infra.execution_market.profile_workload import save

        save(
            path,
            {
                "limit": 4,
                "poll_seconds": self.poll_seconds,
                "peak": self.peak,
                "active": self.active,
                "truncated": self.truncated,
                "attempts": self.rows,
                "attempt_count": self.attempts,
                "finished_count": self.finished,
                "attempts_jsonl": self.stream_path,
            },
        )
        if self.active or self.attempts != self.finished:
            raise RuntimeError("NC09_POLL_GATE_LEAK")


def poll_interval(gate: ParentPollGate | None, legacy_default: float) -> float:
    """Share the explicit cadence across DB status and HTTP transfer observation."""
    return legacy_default if gate is None else gate.poll_seconds


class PollOptions(TypedDict, total=False):
    poll_gate: ParentPollGate


def poll_options(gate: ParentPollGate | None) -> PollOptions:
    return {} if gate is None else {"poll_gate": gate}
