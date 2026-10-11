"""G2: observe CPU/source quiescence before writer cleanup on every exit class."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import seed
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.money import OutOfRangeError
from tiewtrade.infra.indicators import scan
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter, pinned_indicator_writer
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import append_checkpoint
from tiewtrade.services.indicator_builder import attempt


@pytest.mark.parametrize(
    "exit_kind", ["success", "numeric", "operational", "timeout", "cancel", "no_job"]
)
async def test_exit_closes_source_and_cpu_before_writer_cleanup_with_two_connections(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    exit_kind: str,
) -> None:
    if exit_kind != "no_job":
        await seed(builder_engine, migrator_engine)
    source_open = False
    cpu_running = False
    checked_out = 0
    peak = 0
    trace: list[str] = []
    unlock_with_live_work: list[tuple[bool, bool]] = []
    paused = asyncio.Event()
    original_feed = IndicatorStream.feed_batch
    original_cleanup = PinnedIndicatorWriter._cleanup
    contender = attempt.create_builder_engine()
    owner_pid: int | None = None

    async def lock_count() -> int:
        async with migrator_engine.connect() as c:
            return int(
                (
                    await c.execute(
                        text("""SELECT count(*) FROM pg_locks
              WHERE locktype='advisory' AND classid=711 AND objid=1 AND objsubid=2
                AND granted AND (CAST(:pid AS integer) IS NULL OR pid=:pid)"""),
                        {"pid": owner_pid},
                    )
                ).scalar_one()
            )

    async def contend(stage: str) -> None:
        assert await lock_count() == 1
        result = await attempt.run_attempt(contender, uuid4())
        assert result.status is attempt.AttemptStatus.LOCK_BUSY
        trace.append(stage + "_contender_blocked")

    def before_sql(*args: Any) -> None:
        statement = str(args[2])
        if "unlock_indicator_build_lock" in statement or "pg_advisory_unlock" in statement:
            # Observe, do not prevent a bad unlock: production catches exceptions
            # and an instrumentation AssertionError could otherwise hide the defect.
            if cpu_running or source_open:
                unlock_with_live_work.append((cpu_running, source_open))
            trace.append("actual_unlock_sql")

    def checkout(*args: Any) -> None:
        nonlocal checked_out, peak
        checked_out += 1
        peak = max(peak, checked_out)

    def checkin(*args: Any) -> None:
        nonlocal checked_out
        checked_out -= 1

    @asynccontextmanager
    async def source(*args: Any, **kwargs: Any) -> Any:
        nonlocal source_open
        try:
            async with indicator_source_session(*args, **kwargs) as session:
                source_open = True
                trace.append("source_open")
                try:
                    yield session
                finally:
                    # Real contender during source teardown, before snapshot close.
                    await contend("source_cleanup")
        finally:
            source_open = False
            trace.append("source_closed")

    def feed(self: IndicatorStream, *args: Any, **kwargs: Any) -> Any:
        nonlocal cpu_running
        cpu_running = True
        try:
            if exit_kind == "numeric":
                raise OutOfRangeError()
            if exit_kind == "operational":
                raise RuntimeError("injected operational error")
            return original_feed(self, *args, **kwargs)
        finally:
            cpu_running = False
            trace.append("cpu_stopped")

    async def checkpoint(*args: Any, **kwargs: Any) -> None:
        await append_checkpoint(*args, **kwargs)
        if exit_kind in {"timeout", "cancel"}:
            paused.set()
            await asyncio.Event().wait()

    async def cleanup(self: PinnedIndicatorWriter) -> None:
        nonlocal owner_pid
        if self._connection.engine is not builder_engine:
            await original_cleanup(self)
            return
        owner_pid = self.backend_pid
        assert not cpu_running and not source_open
        trace.append("writer_cleanup")
        await contend("writer_cleanup")
        await original_cleanup(self)
        assert await lock_count() == 0
        trace.append("actual_lock_released")

    monkeypatch.setattr(scan, "indicator_source_session", source)
    monkeypatch.setattr(scan, "append_checkpoint", checkpoint)
    monkeypatch.setattr(IndicatorStream, "feed_batch", feed)
    monkeypatch.setattr(PinnedIndicatorWriter, "_cleanup", cleanup)
    if exit_kind == "timeout":
        monkeypatch.setattr(attempt, "ATTEMPT_SECONDS", 0.3)
    event.listen(builder_engine.sync_engine, "checkout", checkout)
    event.listen(builder_engine.sync_engine, "checkin", checkin)
    event.listen(builder_engine.sync_engine, "before_cursor_execute", before_sql)
    task = asyncio.create_task(attempt.run_attempt(builder_engine, uuid4()))
    try:
        if exit_kind == "cancel":
            await asyncio.wait_for(paused.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await asyncio.wait_for(task, 5)
            assert (
                result.status.value
                == {
                    "success": "READY",
                    "numeric": "FAILED_NUMERIC",
                    "operational": "RELEASED",
                    "timeout": "RELEASED",
                    "no_job": "NO_JOB",
                }[exit_kind]
            )
        assert checked_out == 0 and peak == (1 if exit_kind == "no_job" else 2)
        assert not unlock_with_live_work
        assert trace[-1] == "actual_lock_released"
        assert "actual_unlock_sql" in trace
        if exit_kind != "no_job":
            assert trace.index("source_closed") < trace.index("writer_cleanup")
            assert trace.index("source_closed") < trace.index("actual_unlock_sql")
            assert "source_cleanup_contender_blocked" in trace
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None  # Returning to the same pool cannot leak the lock.
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        event.remove(builder_engine.sync_engine, "checkout", checkout)
        event.remove(builder_engine.sync_engine, "checkin", checkin)
        event.remove(builder_engine.sync_engine, "before_cursor_execute", before_sql)
        await contender.dispose()
