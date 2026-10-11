"""Instrument the real attempt inside an isolated container; no ownership stubs."""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic, monotonic_ns, process_time_ns, sleep
from typing import Any
from uuid import UUID

from sqlalchemy import event

from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.infra.indicators import scan
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import append_checkpoint
from tiewtrade.infra.market_data.indicator_reader import IndicatorDigest
from tiewtrade.services.indicator_builder.attempt import create_builder_engine, run_attempt
from tiewtrade.services.indicator_builder.events import record


def emit(step: str, **fields: Any) -> None:
    sys.stdout.write(
        json.dumps({"step": step, "time_ns": monotonic_ns(), "cpu_ns": process_time_ns(), **fields})
        + "\n",
    )
    sys.stdout.flush()


async def run() -> None:
    owner = UUID(os.environ["TIEWTRADE_INDICATOR_OWNER"])
    stage = os.environ.get("PROBE_STAGE", "none")
    gate = Path("/tmp/release-probe")
    held = False

    async def hold(at: str) -> None:
        nonlocal held
        if stage == at and not held:
            held = True
            emit("barrier", stage=at)
            async with asyncio.timeout(240):
                while not gate.exists():
                    await asyncio.sleep(0.01)

    claim_original = PinnedIndicatorWriter.claim
    source_original = indicator_source_session
    checkpoint_original = append_checkpoint
    publish_original = PinnedIndicatorWriter.publish_ready
    numeric_original = PinnedIndicatorWriter.publish_numeric_failure
    cleanup_original = PinnedIndicatorWriter._cleanup
    feed_original = IndicatorStream.feed_batch
    hash_original = IndicatorDigest.feed
    cpu_started = False
    hash_started = False
    cpu_end = 0
    batches = 0
    source_active = False
    cpu_active = False

    async def claim(self: Any, identity: Any) -> Any:
        result = await claim_original(self, identity)
        if result is not None:
            emit(
                "claim_committed",
                pid=self.backend_pid,
                fence=result.fence,
                job=str(result.job_id),
                formula=result.formula_version,
            )
            await hold("before_scan")
        return result

    @asynccontextmanager
    async def source(*args: Any, **kwargs: Any) -> Any:
        nonlocal source_active
        try:
            async with source_original(*args, **kwargs) as session:
                source_active = True
                emit(
                    "source_open",
                    pid=(await session.execute("SELECT pg_backend_pid()")).scalar_one(),
                )
                try:
                    yield session
                finally:
                    await hold("source_cleanup")
        finally:
            source_active = False
            emit("source_closed", last_cpu_end=cpu_end, batches=batches)

    async def checkpoint(*args: Any, **kwargs: Any) -> None:
        emit("checkpoint_attempt")
        await checkpoint_original(*args, **kwargs)
        emit("checkpoint_committed")
        await hold("after_staging")

    async def publish(self: Any, value: Any) -> Any:
        await hold("before_publish")
        emit("ready_attempt")
        result = await publish_original(self, value)
        emit("published", status=result.value)
        return result

    async def numeric(self: Any, value: Any, error: Any) -> Any:
        emit("numeric_attempt")
        result = await numeric_original(self, value, error)
        emit("numeric_published", status=result.value)
        return result

    async def cleanup(self: Any) -> None:
        await cleanup_original(self)
        emit("writer_closed")

    def feed(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal cpu_started, held, cpu_end, batches, cpu_active
        cpu_active = True
        if not cpu_started:
            cpu_started = True
            emit("cpu_start")
        try:
            result = feed_original(self, *args, **kwargs)
            batches += 1
            if stage == "cpu" and not held:
                held = True
                emit("barrier", stage="cpu")
                until = monotonic() + 240
                while not gate.exists():
                    # Keep a genuine synchronous feed call in flight, bounded and observable.
                    sum(range(1000))
                    if monotonic() > until:
                        raise TimeoutError("probe barrier")
                    sleep(0.005)
            return result
        finally:
            cpu_active = False
            cpu_end = monotonic_ns()

    def before_sql(*args: Any) -> None:
        statement = str(args[2])
        if "unlock_indicator_build_lock" in statement or "pg_advisory_unlock" in statement:
            assert not source_active and not cpu_active
            emit("actual_unlock_sql")

    def hashed(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal hash_started
        if not hash_started:
            hash_started = True
            emit("hash_start")
        return hash_original(self, *args, **kwargs)

    for target, name, replacement in (
        (PinnedIndicatorWriter, "claim", claim),
        (PinnedIndicatorWriter, "publish_ready", publish),
        (PinnedIndicatorWriter, "publish_numeric_failure", numeric),
        (PinnedIndicatorWriter, "_cleanup", cleanup),
        (scan, "indicator_source_session", source),
        (scan, "append_checkpoint", checkpoint),
        (IndicatorStream, "feed_batch", feed),
        (IndicatorDigest, "feed", hashed),
    ):
        setattr(target, name, replacement)
    record("boot", owner)
    engine = create_builder_engine()
    event.listen(engine.sync_engine, "before_cursor_execute", before_sql)
    try:
        result = await run_attempt(engine, owner)
        emit("result", status=result.status.value, reason=result.reason)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
