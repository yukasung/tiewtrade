"""Read-only bounded PostgreSQL blocker evidence for one isolated publisher."""

from __future__ import annotations

import asyncio
from collections import Counter, deque
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market.profile_observer_timing import CaptureTiming, LoopLag, TimedEngine
from tests.infra.execution_market.profile_publisher_lease import LeaseTrace


class FenceObservation:
    def __init__(self, current: Callable[[], LeaseTrace | None], *, timing: bool = False) -> None:
        self.timing_enabled = timing
        self.timings: deque[dict[str, Any]] = deque(maxlen=64)
        self.timing_counts: Counter[str] = Counter()
        self.failed_timing: dict[str, Any] | None = None
        self.lag = LoopLag() if timing else None
        self.lag_task: asyncio.Task[None] | None = None
        self.current = current
        self.engine = internal.readonly_admin()
        self.rows: deque[dict[str, Any]] = deque(maxlen=64)
        self.total = 0
        self.errors: Counter[str] = Counter()
        self.failed_observation: dict[str, Any] | None = None
        self.stop = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.cleanup_task: asyncio.Task[None] | None = None

    async def sample(self, statement: dict[str, Any]) -> dict[str, Any]:
        capture_started = monotonic()
        finished_at_start = statement.get("finished")
        initial_trace = self.current()
        publication = None
        if (
            initial_trace is not None
            and initial_trace.statements
            and initial_trace.statements[-1] is statement
        ):
            publication = getattr(initial_trace, "publication", None)
        row: dict[str, Any] = {
            "publisher_pid": statement.get("backend_pid"),
            "stage": statement.get("stage"),
            "statement_started": statement.get("started"),
            "publication_tick": getattr(publication, "tick", None),
            "capture_started": capture_started,
            "capture_phase": "statement_identity",
            "phase_started": capture_started,
            "last_completed_phase": None,
            "activity_interval": None,
            "locks_interval": None,
            "activity_row_count": None,
            "locks_row_count": None,
            "db_now": None,
            "activity": [],
            "locks": [],
            "views_atomic": False,
        }

        def advance(phase: str) -> None:
            row.update(
                last_completed_phase=row["capture_phase"],
                capture_phase=phase,
                phase_started=monotonic(),
            )

        outcome = "UNCONFIRMED"
        try:
            # Keep missing required identity fields a failure, with a diagnostic envelope.
            for key in ("backend_pid", "stage", "started"):
                _ = statement[key]
            advance("checkout")
            async with asyncio.timeout(1):
                async with self.engine.connect() as connection:
                    advance("statement_timeout")
                    await connection.exec_driver_sql("SET LOCAL statement_timeout='500ms'")
                    advance("lock_timeout")
                    await connection.exec_driver_sql("SET LOCAL lock_timeout='200ms'")
                    advance("db_clock")
                    now: datetime = (
                        await connection.execute(text("SELECT clock_timestamp()"))
                    ).scalar_one()
                    row["db_now"] = str(now)
                    advance("activity")
                    row["activity_interval"] = [monotonic(), None]
                    activity = [
                        dict(value)
                        for value in (
                            await connection.execute(
                                text("""
                    SELECT pid,usename,state,xact_start,query_start,wait_event_type,wait_event,
                    pg_blocking_pids(pid) AS blocking_pids
                    FROM pg_stat_activity WHERE datname=current_database()
                    ORDER BY pid LIMIT 129""")
                            )
                        ).mappings()
                    ]
                    row["activity_interval"][1] = monotonic()
                    row["activity_row_count"] = len(activity)
                    if len(activity) > 128:
                        raise ValueError("fence activity evidence exceeds bound")
                    row["activity"] = activity
                    advance("locks")
                    row["locks_interval"] = [monotonic(), None]
                    locks = [
                        dict(value)
                        for value in (
                            await connection.execute(
                                text("""
                    SELECT pid,locktype,database,relation,transactionid,virtualxid,
                    classid,objid,objsubid,mode,granted FROM pg_locks
                    WHERE pid=ANY(CAST(:pids AS int[]))
                    ORDER BY pid,locktype,mode LIMIT 8193"""),
                                {"pids": [value["pid"] for value in activity]},
                            )
                        ).mappings()
                    ]
                    row["locks_interval"][1] = monotonic()
                    row["locks_row_count"] = len(locks)
                    if len(locks) > 8192:
                        raise ValueError("fence lock evidence exceeds bound")
                    row["locks"] = locks
                    advance("session_exit")
            advance("complete")
            outcome = "RETURNED"
        except BaseException as error:
            outcome = type(error).__name__
            raise
        finally:
            capture_finished = monotonic()
            finished_at_end = statement.get("finished")
            current = self.current()
            same_statement = (
                current is not None
                and bool(current.statements)
                and current.statements[-1] is statement
            )
            if finished_at_start is not None:
                association = "COMPLETED_BEFORE_CAPTURE"
            elif same_statement and finished_at_end is None:
                association = "ACTIVE_THROUGH_CAPTURE"
            else:
                association = "OVERLAPPED_OR_UNCONFIRMED"
            row.update(
                observed_at=capture_finished,
                statement_finished_at_start=finished_at_start,
                statement_finished_at_end=finished_at_end,
                statement_association=association,
            )
            if outcome != "RETURNED" and self.failed_observation is None:
                row.update(error_type=outcome, failed_at=datetime.now(UTC).isoformat())
                self.failed_observation = row
        return row

    async def timed_sample(self, statement: dict[str, Any]) -> dict[str, Any]:
        if asyncio.current_task() is not self.task:
            raise ValueError("fence timing requires owned monitor task")
        timing = CaptureTiming()
        record: dict[str, Any] = {
            "spans": timing.spans,
            "outcome": "INCOMPLETE",
            "publisher_pid": statement.get("backend_pid"),
            "stage": statement.get("stage"),
            "statement_started": statement.get("started"),
        }
        engine = self.engine
        self.engine = cast(AsyncEngine, TimedEngine(engine, timing))
        try:
            row = await self.sample(statement)
            record["observation"] = row
            timing.validate()
            if row.get("activity_row_count") is None or row.get("locks_row_count") is None:
                raise ValueError("fence timing evidence incomplete")
            record["outcome"] = "RETURNED"
            return row
        except BaseException as error:
            record["outcome"] = type(error).__name__
            if "observation" not in record:
                record["observation"] = self.failed_observation
            if self.failed_timing is None:
                self.failed_timing = record
            raise
        finally:
            self.engine = engine
            self.timing_counts[record["outcome"]] += 1
            self.timings.append(record)

    def lag_finished(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            # Normal lag shutdown uses its stop event, never task cancellation.
            unexpected = True
        else:
            unexpected = task.exception() is not None or not self.stop.is_set()
        if unexpected:
            self.errors["LoopLagEvidenceLost"] += 1
            if self.task is not None and not self.task.done():
                self.task.cancel()

    async def monitor(self) -> None:
        while not self.stop.is_set():
            trace = self.current()
            statement = trace.statements[-1] if trace is not None and trace.statements else None
            if (
                statement is not None
                and "finished" not in statement
                and monotonic() - statement["started"] >= 1
            ):
                try:
                    row = (
                        await self.timed_sample(statement)
                        if self.timing_enabled
                        else await self.sample(statement)
                    )
                    self.total += 1
                    self.rows.append(row)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.errors[type(error).__name__] += 1
                    return
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stop.wait(), 0.25)

    def start(self) -> None:
        if self.task is not None:
            raise ValueError("fence monitor already started")
        self.task = asyncio.create_task(self.monitor())
        if self.lag is not None:
            self.lag_task = asyncio.create_task(self.lag.run())
            self.lag_task.add_done_callback(self.lag_finished)

    async def _finish_close(self) -> None:
        try:
            if self.task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(self.task), 2)
                except TimeoutError:
                    self.errors["MonitorJoinTimeout"] += 1
                    self.task.cancel()
                except asyncio.CancelledError:
                    if not self.task.cancelled():
                        raise
                finally:
                    if not self.task.done():
                        self.task.cancel()
                    await asyncio.gather(self.task, return_exceptions=True)
        finally:
            try:
                if self.lag is not None:
                    self.lag.stop.set()
                if self.lag_task is not None:
                    await asyncio.gather(self.lag_task, return_exceptions=True)
            finally:
                await self.engine.dispose()

    async def close(self) -> None:
        """Finish owned cleanup before propagating the first caller cancellation."""
        self.stop.set()
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._finish_close())
        first_cancellation: asyncio.CancelledError | None = None
        while not self.cleanup_task.done():
            try:
                await asyncio.shield(self.cleanup_task)
            except asyncio.CancelledError as error:
                first_cancellation = first_cancellation or error
                if self.task is not None and not self.task.done() and not self.task.cancelling():
                    self.task.cancel()
            except BaseException:
                break  # Retrieve the cleanup outcome below, retaining cancellation precedence.
        try:
            self.cleanup_task.result()
        except BaseException as error:
            if first_cancellation is None:
                raise
            first_cancellation.add_note(f"fence cleanup failed: {type(error).__name__}")
        if first_cancellation is not None:
            raise first_cancellation

    def report(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "total_samples": self.total,
            "retained_limit": 64,
            "observations": list(self.rows),
            "errors": dict(self.errors),
            "failed_observation": self.failed_observation,
            "no_query_text": True,
            "task_joined": self.task is not None and self.task.done(),
        }

        if self.timing_enabled:
            lag_joined = self.lag_task is not None and self.lag_task.done()
            lag_completed = bool(
                lag_joined
                and self.lag_task is not None
                and not self.lag_task.cancelled()
                and self.lag_task.exception() is None
            )
            result["timing"] = {
                "status": (
                    "INCOMPLETE"
                    if self.failed_timing is not None
                    or self.errors
                    or (lag_joined and not lag_completed)
                    else "RECORDED"
                    if self.timing_counts
                    else "NO_TRIGGER"
                ),
                "counts": dict(self.timing_counts),
                "recent": list(self.timings),
                "failed": self.failed_timing,
                "retained_limit": 64,
                "loop_lag": self.lag.report() if self.lag is not None else None,
                "lag_task_joined": lag_joined,
                "lag_task_completed": lag_completed,
                "interpretation": "driver and scheduling included; not server-only",
            }
        return result
