"""S2/S3/S4 exact DB-clock boundaries, atomic rounds and recovery combinations."""

import asyncio
import json
import sys
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_global_handoff import enable_other
from tests.services.indicator_builder.test_attempt import metadata, seed
from tests.services.indicator_builder.test_numeric_windows import BOUNDARY, Clock
from tests.services.indicator_builder.test_numeric_windows import db_clock as db_clock
from tests.services.indicator_builder.test_scheduler import change_source
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.infra.db.errors import DatabaseUnavailableError
from tiewtrade.infra.indicators.claims import AttemptOutcome, claim_next
from tiewtrade.infra.indicators.maintenance import RetryResult, retry_job
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter, pinned_indicator_writer
from tiewtrade.infra.indicators.scheduling import coalesce_jobs
from tiewtrade.infra.market_data.indicator_reader import IndicatorDigest
from tiewtrade.services.indicator_builder import attempt, scheduler
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt
from tiewtrade.services.indicator_builder.supervisor import worker_environment

EPISODE = ("first_eligible_at", "availability_deadline", "last_served_round", "deadline_missed_at")


def unchanged(before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        assert after[field] == before[field], field


async def exhaust(
    builder: AsyncEngine,
    admin: AsyncEngine,
    clock: Clock,
    reason: AttemptOutcome,
) -> dict[str, Any]:
    for seconds in (0,) if reason is AttemptOutcome.OPERATIONAL else (0, 30, 90):
        await clock(BOUNDARY + timedelta(seconds=seconds))
        async with pinned_indicator_writer(builder, connection_mode="direct") as writer:
            assert writer is not None
            claim = await writer.claim(uuid4())
            assert claim is not None
            await writer.finish(reason)
    return await metadata(admin)


async def expired_episode(admin: AsyncEngine) -> None:
    async with admin.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET
          first_eligible_at=:start,availability_deadline=:deadline
          WHERE base='BTC' AND timeframe='4h'"""),
            {
                "start": BOUNDARY - timedelta(seconds=601),
                "deadline": BOUNDARY - timedelta(seconds=1),
            },
        )


async def test_mixed_failures_share_three_attempts_exact_backoff_and_no_clock_reset(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(builder_engine, migrator_engine)
    initial = await metadata(migrator_engine)
    original = PinnedIndicatorWriter.publish_ready
    feed_original = IndicatorStream.feed_batch
    hash_original = IndicatorDigest.feed
    core_calls = 0
    hash_calls = 0
    pids: list[int] = []
    reason = "source"

    def feed(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal core_calls
        core_calls += 1
        return feed_original(self, *args, **kwargs)

    def hashed(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal hash_calls
        hash_calls += 1
        return hash_original(self, *args, **kwargs)

    async def terminal(writer: Any, claim: Any) -> Any:
        pids.append(writer.backend_pid)
        if reason == "transient":
            raise DatabaseUnavailableError("fixed failure after real scan")
        await change_source(migrator_engine)
        return await original(writer, claim)

    monkeypatch.setattr(IndicatorStream, "feed_batch", feed)
    monkeypatch.setattr(IndicatorDigest, "feed", hashed)
    monkeypatch.setattr(PinnedIndicatorWriter, "publish_ready", terminal)
    for index, seconds in enumerate((0, 30, 90), start=1):
        await db_clock(BOUNDARY + timedelta(seconds=seconds))
        reason = "transient" if index == 2 else "source"
        old_core, old_hash = core_calls, hash_calls
        result = await run_attempt(builder_engine, uuid4())
        assert result.status is (AttemptStatus.RELEASED if index == 2 else AttemptStatus.SUPERSEDED)
        assert core_calls > old_core and hash_calls > old_hash
        j = await metadata(migrator_engine)
        assert j["attempts_used"] == j["last_served_round"] == index
        unchanged(initial, j, ("cycle_id", "first_eligible_at", "availability_deadline"))
        if index < 3:
            delay = 30 if index == 1 else 60
            assert j["retry_not_before"] == BOUNDARY + timedelta(seconds=seconds + delay)
            await db_clock(j["retry_not_before"] - timedelta(microseconds=1))
            await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
            saved = await metadata(migrator_engine)
            before_core, before_hash = core_calls, hash_calls
            before_slot = await slot(migrator_engine)
            assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
            assert (core_calls, hash_calls) == (before_core, before_hash)
            assert await slot(migrator_engine) == before_slot
            unchanged(
                j, saved, ("attempts_used", "last_served_round", "cycle_id", "retry_not_before")
            )
            await builder_engine.dispose()  # New physical sessions/owner, same durable episode.
    failed = await metadata(migrator_engine)
    assert failed["status"] == "FAILED_SUPERSEDED" and len(set(pids)) == 3
    for seconds in (690, 14400, 28800):
        await db_clock(BOUNDARY + timedelta(seconds=seconds))
        await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
        saved_slot = await slot(migrator_engine)
        before_core, before_hash = core_calls, hash_calls
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
        assert (core_calls, hash_calls) == (before_core, before_hash)
        assert await slot(migrator_engine) == saved_slot
        unchanged(
            failed,
            await metadata(migrator_engine),
            (
                "attempts_used",
                "last_served_round",
                "cycle_id",
                "first_eligible_at",
                "availability_deadline",
            ),
        )


@pytest.mark.parametrize(
    "reason", [AttemptOutcome.SOURCE_CHANGED, AttemptOutcome.TRANSIENT, AttemptOutcome.OPERATIONAL]
)
@pytest.mark.parametrize("event_after", [False, True])
@pytest.mark.parametrize("delta_us", [-1, 0, 1])
async def test_post_failure_event_and_exact_cooldown_preserve_missed_episode(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    reason: AttemptOutcome,
    event_after: bool,
    delta_us: int,
) -> None:
    await seed(builder_engine, migrator_engine)
    await expired_episode(migrator_engine)
    await change_source(migrator_engine)  # A pre-failure event alone is insufficient.
    failed = await exhaust(builder_engine, migrator_engine, db_clock, reason)
    assert failed["deadline_missed_at"] is not None
    if event_after:
        await db_clock(failed["failed_at"] + timedelta(microseconds=1))
        await change_source(migrator_engine)
    await db_clock(failed["failed_at"] + timedelta(seconds=600, microseconds=delta_us))
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    recovered = await metadata(migrator_engine)
    allowed = event_after and delta_us >= 0 and reason is not AttemptOutcome.OPERATIONAL
    assert recovered["status"] == ("QUEUED" if allowed else failed["status"])
    unchanged(failed, recovered, EPISODE)
    assert recovered["attempts_used"] == (0 if allowed else failed["attempts_used"])
    assert (recovered["cycle_id"] != failed["cycle_id"]) == allowed
    stable = await metadata(migrator_engine)
    await coalesce_jobs(builder_engine)
    assert await metadata(migrator_engine) == stable
    result = await run_attempt(builder_engine, uuid4())
    assert result.status is (AttemptStatus.READY if allowed else AttemptStatus.NO_JOB)


async def cli_retry(job: UUID, request: UUID) -> tuple[int, str]:
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tiewtrade.services.indicator_builder.main",
        "retry",
        "--job-id",
        str(job),
        "--request-id",
        str(request),
        env=worker_environment(uuid4()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, error = await asyncio.wait_for(child.communicate(), 5)
        assert not error and child.returncode in (0, 12)
        payload = json.loads(output)
        assert set(payload) == {"component", "event", "status"}
        return child.returncode, payload["status"]
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()


@pytest.mark.parametrize("delta_us", [-1, 0, 1])
async def test_concurrent_duplicate_cli_at_cooldown_boundary_is_durable(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    delta_us: int,
) -> None:
    await seed(builder_engine, migrator_engine)
    await expired_episode(migrator_engine)
    failed = await exhaust(builder_engine, migrator_engine, db_clock, AttemptOutcome.OPERATIONAL)
    await db_clock(failed["failed_at"] + timedelta(seconds=600, microseconds=delta_us))
    request = uuid4()
    results = await asyncio.gather(
        cli_retry(failed["id"], request), cli_retry(failed["id"], request)
    )
    answer = (0, "QUEUED") if delta_us >= 0 else (12, "REJECTED")
    assert list(results) == [answer, answer]
    after = await metadata(migrator_engine)
    unchanged(failed, after, EPISODE)
    assert after["attempts_used"] == (0 if delta_us >= 0 else 1)
    assert (after["cycle_id"] != failed["cycle_id"]) == (delta_us >= 0)
    await db_clock(failed["failed_at"] + timedelta(seconds=601))
    assert await cli_retry(failed["id"], request) == answer
    assert await metadata(migrator_engine) == after
    if delta_us < 0:
        assert await retry_job(builder_engine, failed["id"], uuid4()) is RetryResult.QUEUED


@pytest.mark.parametrize("committed", [False, True])
async def test_round_advance_rollback_or_lost_ack_never_refunds_committed_attempt(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    committed: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        initial = await writer.claim(uuid4())
        assert initial is not None
        await writer.finish(AttemptOutcome.TRANSIENT)
    await db_clock(BOUNDARY + timedelta(seconds=30))
    await coalesce_jobs(builder_engine)
    before = await metadata(migrator_engine)
    before_slot = await slot(migrator_engine)
    original = PinnedIndicatorWriter.claim

    async def uncertain(writer: PinnedIndicatorWriter, owner: UUID) -> Any:
        if committed:
            claim = await original(writer, owner)
            assert claim is not None and claim.dispatch_round == 2
        else:
            with pytest.raises(ValueError, match="rollback"):
                async with writer.transaction() as session:
                    claim = await claim_next(session, owner)
                    assert claim is not None and claim.dispatch_round == 2
                    raise ValueError("rollback")
        raise DatabaseUnavailableError("lost acknowledgement")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unconfirmed claim started CPU/hash")

    monkeypatch.setattr(PinnedIndicatorWriter, "claim", uncertain)
    monkeypatch.setattr(IndicatorStream, "feed_batch", forbidden)
    monkeypatch.setattr(IndicatorDigest, "feed", forbidden)
    result = await run_attempt(builder_engine, uuid4())
    assert result.status is AttemptStatus.ORPHANED
    monkeypatch.setattr(PinnedIndicatorWriter, "claim", original)
    await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
    after = await metadata(migrator_engine)
    unchanged(before, after, ("cycle_id", "first_eligible_at", "availability_deadline"))
    if committed:
        assert after["attempts_used"] == after["last_served_round"] == 2
        assert after["claim_token"] is not None
        assert (await slot(migrator_engine))["dispatch_round"] == 2
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    else:
        assert after == before and await slot(migrator_engine) == before_slot
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            fresh = await writer.claim(uuid4())
            assert fresh is not None and fresh.dispatch_round == 2
            assert (await metadata(migrator_engine))["attempts_used"] == 2
            await writer.finish(AttemptOutcome.OPERATIONAL)


async def test_locked_unserved_job_prevents_advancing_round(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        first = await writer.claim(uuid4())
        assert first is not None
        await writer.finish(AttemptOutcome.TRANSIENT)
    await enable_other(migrator_engine)
    await db_clock(BOUNDARY + timedelta(seconds=30))
    before = await metadata(migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "SELECT id FROM indicator_build_jobs WHERE base='ETH' AND timeframe='4h' FOR UPDATE"
            )
        )
        async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
            assert writer is not None
            assert await writer.claim(uuid4()) is None
        assert (await slot(migrator_engine))["dispatch_round"] == 1
        assert await metadata(migrator_engine) == before
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        other = await writer.claim(uuid4())
        assert other is not None and other.job_id != first.job_id
        assert other.dispatch_round == 1
        await writer.finish(AttemptOutcome.OPERATIONAL)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        next_round = await writer.claim(uuid4())
        assert next_round is not None and next_round.job_id == first.job_id
        assert next_round.dispatch_round == 2
        await writer.finish(AttemptOutcome.OPERATIONAL)


@pytest.mark.parametrize("status", [AttemptStatus.NO_JOB, AttemptStatus.LOCK_BUSY])
async def test_idle_or_contended_scheduler_polls_once_then_waits(
    monkeypatch: pytest.MonkeyPatch,
    status: AttemptStatus,
    builder_engine: AsyncEngine,
) -> None:
    calls: list[str] = []
    entered = asyncio.Event()
    stop = asyncio.Event()

    async def metadata_only(*args: Any) -> None:
        calls.append("metadata")

    async def blocked(*args: Any, **kwargs: Any) -> attempt.AttemptResult:
        calls.append("attempt")
        entered.set()
        return attempt.AttemptResult(status)

    monkeypatch.setattr(scheduler, "collect", metadata_only)
    monkeypatch.setattr(scheduler, "coalesce_jobs", metadata_only)
    monkeypatch.setattr(scheduler, "run_attempt", blocked)
    task = asyncio.create_task(scheduler.run_scheduler(builder_engine, uuid4(), stop))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await asyncio.sleep(0.05)
        assert calls == ["metadata", "metadata", "attempt"]
        assert not task.done()
        stop.set()
        assert await asyncio.wait_for(task, 1) is None
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
