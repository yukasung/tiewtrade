"""Real PostgreSQL attempt orchestration and injected failure boundaries."""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_staging import only_h4
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.money import OutOfRangeError
from tiewtrade.infra.db.errors import (
    DatabaseRetryableError,
    DatabaseTimeoutError,
    DatabaseUnavailableError,
    IndicatorBuildOwnershipError,
    NotPermittedError,
    SourceProofStateError,
    translate_database_error,
)
from tiewtrade.infra.indicators import scan as scanner
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.codec import CheckpointCodecError
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter, pinned_indicator_writer
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import append_checkpoint, capture_snapshot
from tiewtrade.services.indicator_builder import attempt
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


async def seed(builder: AsyncEngine, admin: AsyncEngine) -> None:
    async with pinned_indicator_writer(builder, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(admin)


async def metadata(admin: AsyncEngine) -> dict[str, Any]:
    async with admin.connect() as c:
        return dict(
            (
                await c.execute(
                    text("SELECT * FROM indicator_build_jobs WHERE base='BTC' AND timeframe='4h'")
                )
            )
            .mappings()
            .one()
        )


async def test_ready_and_no_job_return_lock_and_preserve_head(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.NO_JOB
    await seed(builder_engine, migrator_engine)
    result = await run_attempt(builder_engine, uuid4())
    assert result.status == AttemptStatus.READY
    assert (await metadata(migrator_engine))["attempts_used"] == 0
    assert (await slot(migrator_engine))["state"] == "IDLE"
    assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.NO_JOB


async def test_contender_never_claims_or_opens_scan(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)

    async def forbidden(*args: object) -> None:
        raise AssertionError("contender started scan")

    monkeypatch.setattr(attempt, "scan_staging", forbidden)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        result = await run_attempt(builder_engine, uuid4())
        assert result.status == AttemptStatus.LOCK_BUSY
        assert (await metadata(migrator_engine))["attempts_used"] == 0


@pytest.mark.parametrize(
    "error,expected",
    [
        (OutOfRangeError("private input"), None),
        (DatabaseTimeoutError("private"), AttemptOutcome.TRANSIENT),
        (DatabaseUnavailableError("private"), AttemptOutcome.TRANSIENT),
        (DatabaseRetryableError("private"), AttemptOutcome.TRANSIENT),
        (IndicatorBuildOwnershipError("private"), AttemptOutcome.OWNERSHIP_LOST),
        (SourceProofStateError("private"), AttemptOutcome.SOURCE_CHANGED),
        (TimeoutError("private"), AttemptOutcome.TRANSIENT),
        (CheckpointCodecError("private"), AttemptOutcome.OPERATIONAL),
        (NotPermittedError("private"), AttemptOutcome.OPERATIONAL),
        (RuntimeError("private"), AttemptOutcome.OPERATIONAL),
    ],
)
async def test_typed_failures_after_checkpoint_commit(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected: AttemptOutcome | None,
) -> None:
    await seed(builder_engine, migrator_engine)

    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(IndicatorStream, "feed_batch", fail)
    result = await run_attempt(builder_engine, uuid4())
    j = await metadata(migrator_engine)
    assert "private" not in str(result) and "private" not in str(j)
    assert j["attempts_used"] == 1
    assert (await slot(migrator_engine))["state"] == "IDLE"
    if expected is None:
        assert result.status == AttemptStatus.FAILED_NUMERIC
        assert j["status"] == "FAILED_NUMERIC" and j["retry_not_before"] is None
        assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.NO_JOB
    else:
        assert result.status == AttemptStatus.RELEASED and result.reason == expected
        assert j["status"] == (
            "FAILED_OPERATIONAL" if expected == AttemptOutcome.OPERATIONAL else "QUEUED"
        )
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_ready_heads"))
        ).scalar_one() == 0


@pytest.mark.parametrize("cancel", [False, True])
async def test_deadline_or_cancellation_closes_scan_before_release(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    cancel: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    started = asyncio.Event()

    async def paused(*args: Any) -> None:
        await append_checkpoint(*args)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(scanner, "append_checkpoint", paused)
    if not cancel:
        monkeypatch.setattr(attempt, "ATTEMPT_SECONDS", 0.3)
    task = asyncio.create_task(run_attempt(builder_engine, uuid4()))
    await asyncio.wait_for(started.wait(), 2)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    else:
        result = await asyncio.wait_for(task, 3)
        assert result.status == AttemptStatus.RELEASED
        assert result.reason == AttemptOutcome.OWNERSHIP_LOST
    assert (await slot(migrator_engine))["state"] == "IDLE"
    assert (await metadata(migrator_engine))["attempts_used"] == 1
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None


async def test_failed_terminal_commit_keeps_orphan_and_blocks_new_attempt(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)

    def fail(*args: object, **kwargs: object) -> None:
        raise DatabaseTimeoutError("fixed")

    async def cannot_release(*args: object) -> None:
        raise DatabaseUnavailableError("fixed")

    monkeypatch.setattr(IndicatorStream, "feed_batch", fail)
    monkeypatch.setattr(PinnedIndicatorWriter, "finish", cannot_release)
    assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.ORPHANED
    assert (await slot(migrator_engine))["state"] == "RUNNING"
    assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.NO_JOB
    assert (await metadata(migrator_engine))["attempts_used"] == 1


async def test_shared_retry_budget_stops_after_three_attempts(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)

    def fail(*args: object, **kwargs: object) -> None:
        raise DatabaseTimeoutError("fixed")

    monkeypatch.setattr(IndicatorStream, "feed_batch", fail)
    for count in range(1, 4):
        assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.RELEASED
        j = await metadata(migrator_engine)
        assert j["attempts_used"] == count
        if count < 3:
            # Move only fixture backoff forward; the production runner never resets it.
            async with migrator_engine.begin() as c:
                await c.execute(
                    text("UPDATE indicator_build_jobs SET retry_not_before=clock_timestamp()")
                )
    assert (await metadata(migrator_engine))["status"] == "FAILED_TRANSIENT"
    assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.NO_JOB


@pytest.mark.parametrize("code", ["40001", "40P01"])
def test_driver_retryable_sqlstates_keep_typed_category(code: str) -> None:
    class DriverError(Exception):
        sqlstate = code

    assert isinstance(translate_database_error(DriverError("private")), DatabaseRetryableError)


async def test_local_scan_deadline_keeps_ownership_lost_category(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    ticks = iter((0.0, 1000.0))
    monkeypatch.setattr(scanner, "monotonic", lambda: next(ticks, 1000.0))
    result = await run_attempt(builder_engine, uuid4())
    assert result.status == AttemptStatus.RELEASED
    assert result.reason == AttemptOutcome.OWNERSHIP_LOST
    assert (await metadata(migrator_engine))["failure_reason"] == "OWNERSHIP_LOST"


async def test_source_invalidated_after_scan_is_superseded(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)

    async def scan_then_maintenance(*args: Any) -> object:
        result = await scanner.scan_staging(*args)
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        return result

    monkeypatch.setattr(attempt, "scan_staging", scan_then_maintenance)
    result = await run_attempt(builder_engine, uuid4())
    assert result.status == AttemptStatus.SUPERSEDED
    assert (await metadata(migrator_engine))["failure_reason"] == "SOURCE_CHANGED"
    assert (await slot(migrator_engine))["state"] == "IDLE"


async def test_uncertain_publication_never_releases_or_republishes_success(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    original = PinnedIndicatorWriter.publish_ready

    async def uncertain(*args: Any) -> None:
        await original(*args)
        raise DatabaseUnavailableError("fixed ambiguous acknowledgement")

    monkeypatch.setattr(PinnedIndicatorWriter, "publish_ready", uncertain)
    result = await run_attempt(builder_engine, uuid4())
    assert result.status == AttemptStatus.ORPHANED
    assert (await metadata(migrator_engine))["status"] == "READY"
    assert (await slot(migrator_engine))["state"] == "IDLE"
    assert (await run_attempt(builder_engine, uuid4())).status == AttemptStatus.NO_JOB


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("method", ["commit", "rollback", "close"])
async def test_cancellation_or_deadline_during_source_cleanup_keeps_shutdown_reason(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    cancel: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    entered = asyncio.Event()
    joined = asyncio.Event()
    target: AsyncConnection | None = None
    driver: Any = None
    original = getattr(AsyncConnection, method)

    async def capture(session: Any, claim: Any) -> Any:
        nonlocal target, driver
        target = session._connection
        driver = (await target.get_raw_connection()).driver_connection
        return await capture_snapshot(session, claim)

    async def stalled(connection: AsyncConnection) -> None:
        if connection is target:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                joined.set()
        else:
            await original(connection)

    def fail(*args: object, **kwargs: object) -> None:
        raise CheckpointCodecError("fixed aborted scan")

    monkeypatch.setattr(scanner, "capture_snapshot", capture)
    monkeypatch.setattr(AsyncConnection, method, stalled)
    if method == "rollback":
        monkeypatch.setattr(IndicatorStream, "feed_batch", fail)
    if not cancel:
        monkeypatch.setattr(attempt, "ATTEMPT_SECONDS", 0.75)
    task = asyncio.create_task(run_attempt(builder_engine, uuid4()))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        started = asyncio.get_running_loop().time()
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2.5)
            assert task.cancelled()
        else:
            result = await asyncio.wait_for(task, 2.5)
            assert result.status == AttemptStatus.RELEASED
            assert result.reason == AttemptOutcome.OWNERSHIP_LOST
        assert asyncio.get_running_loop().time() - started < 2.5
        assert joined.is_set() and driver.is_closed()
        assert (await slot(migrator_engine))["state"] == "IDLE"
        j = await metadata(migrator_engine)
        assert j["attempts_used"] == 1 and j["failure_reason"] == "OWNERSHIP_LOST"
        async with indicator_source_session(builder_engine) as source:
            await source.execute("SELECT 1")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("committed", [False, True])
async def test_claim_wait_is_bounded_and_uncertain_owner_never_resumes(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    committed: bool,
    cancel: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    entered = asyncio.Event()
    original = PinnedIndicatorWriter.claim

    async def stalled(writer: PinnedIndicatorWriter, owner: Any) -> Any:
        result = await original(writer, owner) if committed else None
        entered.set()
        await asyncio.Event().wait()
        return result

    async def forbidden(*args: object) -> None:
        raise AssertionError("unconfirmed claim opened source")

    monkeypatch.setattr(PinnedIndicatorWriter, "claim", stalled)
    monkeypatch.setattr(attempt, "scan_staging", forbidden)
    monkeypatch.setattr(attempt, "ATTEMPT_SECONDS", 0.3)
    started = asyncio.get_running_loop().time()
    task = asyncio.create_task(run_attempt(builder_engine, uuid4()))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2.5)
        else:
            result = await asyncio.wait_for(task, 2.5)
            assert result.status == AttemptStatus.ORPHANED
            assert result.reason == AttemptOutcome.OWNERSHIP_LOST
            assert result.job_id is None and result.generation_id is None
        assert asyncio.get_running_loop().time() - started < 2.5
        s = await slot(migrator_engine)
        j = await metadata(migrator_engine)
        assert s["state"] == ("RUNNING" if committed else "IDLE")
        assert j["attempts_used"] == (1 if committed else 0)
        monkeypatch.setattr(PinnedIndicatorWriter, "claim", original)
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            if committed:
                assert await writer.claim(uuid4()) is None
                assert (await metadata(migrator_engine))["attempts_used"] == 1
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
