"""NC12 bounded F14 snapshot observations and exact final replay."""

from __future__ import annotations

import asyncio
import json
import resource
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from time import monotonic
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_restore import replay_owner_domain
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.positions import read_position_snapshot


def peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


class PositionChecks:
    def __init__(self, engine: AsyncEngine, owners: list[f15.OwnerState], output: Path) -> None:
        self.engine, self.owners, self.output = engine, owners, output
        self.rows: list[dict[str, Any]] = []
        self.query_count: ContextVar[list[int] | None] = ContextVar(
            "snapshot_queries", default=None
        )

    @contextmanager
    def observe_queries(self) -> Iterator[None]:
        # Context-local counters exclude concurrent workload/background queries.
        def query(connection: Any, cursor: Any, *args: Any) -> None:
            counter = self.query_count.get()
            if counter is not None:
                counter[0] += 1
                if cursor.rowcount >= 0:
                    counter[1] += cursor.rowcount
                else:
                    counter[2] += 1

        event.listen(self.engine.sync_engine, "after_cursor_execute", query)
        try:
            yield
        finally:
            event.remove(self.engine.sync_engine, "after_cursor_execute", query)

    async def snapshots(self, *, scheduled: float) -> None:
        async def read(owner: f15.OwnerState) -> None:
            started = monotonic()
            row: dict[str, Any] = {
                "owner": str(owner.user_id),
                "episode": str(owner.wallet.episode_id),
                "scheduled": scheduled,
                "started": started,
            }
            counter = [0, 0, 0]
            token = self.query_count.set(counter)
            try:
                async with asyncio.timeout(60):
                    async with user_session(
                        self.engine, owner.user_id, role=DatabaseRole.ENGINE
                    ) as session:
                        snapshot = await read_position_snapshot(session, owner.wallet.episode_id)
                        if snapshot is None or snapshot.activity.user_id != owner.user_id:
                            raise RuntimeError("INTERNAL_SNAPSHOT_MISSING_OR_WRONG_OWNER")
                        row.update(
                            revision=snapshot.activity.revision,
                            source_sequence=snapshot.activity.source_sequence,
                            positions=len(snapshot.positions),
                        )
                row["outcome"] = "RETURNED"
            except BaseException as error:
                row["outcome"] = type(error).__name__
                raise
            finally:
                self.query_count.reset(token)
                row.update(
                    seconds=monotonic() - started,
                    queries=counter[0],
                    rows_returned=counter[1],
                    rowcount_unknown=counter[2],
                    peak_process_rss_bytes=peak_rss_bytes(),
                )
                self.rows.append(row)
                with (self.output / "position-snapshots.jsonl").open(
                    "a", encoding="utf-8"
                ) as stream:
                    stream.write(json.dumps(row) + "\n")

        with self.observe_queries():
            await f15.bounded_map(self.owners, read, limit=4, join_on_error=True)

    async def observe_endurance(self, started: float, seconds: int) -> None:
        # A fixed schedule; a missed/read-failed minute cannot disappear from the denominator.
        for offset in range(0, seconds, 60):
            scheduled = started + offset
            await asyncio.sleep(max(0, scheduled - monotonic()))
            await self.snapshots(scheduled=scheduled)

    async def final(self, *, expected_periodic: int) -> dict[str, Any]:
        await self.snapshots(scheduled=monotonic())
        replay = []
        with self.observe_queries():
            for owner in self.owners:
                started = monotonic()
                row: dict[str, Any] = {
                    "owner": str(owner.user_id),
                    "episode": str(owner.wallet.episode_id),
                }
                counter = [0, 0, 0]
                token = self.query_count.set(counter)
                try:
                    async with asyncio.timeout(60):
                        row.update(
                            await replay_owner_domain(
                                self.engine,
                                user_id=owner.user_id,
                                wallet_id=owner.wallet.wallet_id,
                                episode_id=owner.wallet.episode_id,
                                active=True,
                            )
                        )
                    row["outcome"] = "RETURNED"
                except BaseException as error:
                    row["outcome"] = type(error).__name__
                    raise
                finally:
                    self.query_count.reset(token)
                    row.update(
                        seconds=monotonic() - started,
                        queries=counter[0],
                        rows_returned=counter[1],
                        rowcount_unknown=counter[2],
                        peak_process_rss_bytes=peak_rss_bytes(),
                    )
                    replay.append(row)
                    f15.save(self.output / "position-replays.json", replay)
        times = [row["seconds"] for row in self.rows]
        p95, p99 = f15.percentile(times, 0.95), f15.percentile(times, 0.99)
        expected = len(self.owners) * (expected_periodic + 1)
        result = {
            "snapshot_samples": len(times),
            "expected_samples": expected,
            "p95": p95,
            "p99": p99,
            "replays": replay,
            "passed": len(times) == expected
            and p95 <= 0.250
            and p99 <= 1
            and all(row["outcome"] == "RETURNED" for row in self.rows)
            and all(row["seconds"] <= 60 for row in replay)
            and all(
                row["peak_process_rss_bytes"] <= f15.MAX_WORKER_RSS_BYTES
                for row in [*replay, *self.rows]
            ),
        }
        f15.save(self.output / "position-result.json", result)
        return result
