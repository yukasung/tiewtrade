"""Real-role publication: atomic visibility, source proof, fencing and retry state."""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import job, slot
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_staging import generation, only_h4
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.money import OutOfRangeError
from tiewtrade.infra.db.errors import (
    DatabaseTimeoutError,
    IndicatorBuildConfigurationError,
    IndicatorBuildOwnershipError,
)
from tiewtrade.infra.indicators import pinned as pinned_module
from tiewtrade.infra.indicators import scan as scanner
from tiewtrade.infra.indicators.claims import AttemptOutcome, PublicationResult, publish
from tiewtrade.infra.indicators.claims import heartbeat as original_heartbeat
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.scan import scan_staging
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import append_checkpoint as original_append
from tiewtrade.infra.indicators.staging import capture_snapshot, initialize


async def visible(engine: AsyncEngine, view: str) -> int:
    async with engine.connect() as c:
        return int((await c.execute(text(f"SELECT count(*) FROM {view}"))).scalar_one())


@pytest.mark.parametrize("terminal", ["ready", "numeric", "release"])
async def test_maintenance_expired_candidate_releases_owner_safely(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    terminal: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        await scan_staging(builder_engine, writer, claim)
        before = await job(migrator_engine, claim)
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        # Expiry does not authorize heartbeat/STAGING writes or a spoofed terminal release.
        with pytest.raises(IndicatorBuildOwnershipError):
            async with writer.transaction() as session:
                await session.execute(
                    "SELECT public.heartbeat_indicator_build_claim"
                    "(:epoch,:fence,:owner,:job,:generation,:token)",
                    claim.parameters(),
                )
        with pytest.raises(IndicatorBuildOwnershipError):
            async with writer.transaction() as session:
                await session.execute(
                    "SELECT public.release_indicator_build_claim"
                    "(:epoch,:fence,:owner,:job,:generation,:token,'SOURCE_CHANGED')",
                    claim.parameters() | {"token": uuid4()},
                )
        if terminal == "release":
            await writer.finish(AttemptOutcome.SOURCE_CHANGED)
        elif terminal == "numeric":
            assert await writer.publish_numeric_failure(claim, OutOfRangeError()) == (
                PublicationResult.SUPERSEDED
            )
        else:
            assert await writer.publish_ready(claim) == PublicationResult.SUPERSEDED
        after = await job(migrator_engine, claim)
        assert after["status"] == "QUEUED" and after["failure_reason"] == "SOURCE_CHANGED"
        assert after["retry_not_before"] is not None
        for key in (
            "attempts_used",
            "cycle_id",
            "last_served_round",
            "first_eligible_at",
            "availability_deadline",
        ):
            assert after[key] == before[key]
        assert (await generation(migrator_engine, claim))["status"] == "EXPIRED"
        assert await visible(migrator_engine, "indicator_ready_heads") == 0
        assert await visible(migrator_engine, "indicator_numeric_failures") == 0
        assert (await slot(migrator_engine))["state"] == "IDLE"
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None  # advisory lock was returned after safe terminal commit


@pytest.mark.parametrize("heartbeat_failure", [False, True])
async def test_numeric_error_joins_inflight_heartbeat_before_publication(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    heartbeat_failure: bool,
) -> None:
    eligible = asyncio.Event()
    started = asyncio.Event()
    release = asyncio.Event()

    async def heartbeat(*args: Any) -> object:
        if eligible.is_set():
            started.set()
            await release.wait()
            if heartbeat_failure:
                raise IndicatorBuildOwnershipError("fixed heartbeat failure")
        return await original_heartbeat(*args)

    async def append(*args: Any) -> None:
        await original_append(*args)
        eligible.set()
        await asyncio.wait_for(started.wait(), 2)

    def numeric_failure(*args: object, **kwargs: object) -> None:
        raise OutOfRangeError("private input")

    monkeypatch.setattr(pinned_module, "heartbeat", heartbeat)
    monkeypatch.setattr(scanner, "append_checkpoint", append)
    monkeypatch.setattr(IndicatorStream, "feed_batch", numeric_failure)
    monkeypatch.setattr(scanner, "HEARTBEAT_SECONDS", 0.01)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        task = asyncio.create_task(scan_staging(builder_engine, writer, claim))
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.sleep(0.05)
            assert not task.done()
            release.set()
            if heartbeat_failure:
                with pytest.raises(IndicatorBuildOwnershipError):
                    await asyncio.wait_for(task, 2)
                with pytest.raises(IndicatorBuildOwnershipError):
                    await writer.publish_numeric_failure(claim, OutOfRangeError())
                await writer.finish(AttemptOutcome.OWNERSHIP_LOST)
            else:
                with pytest.raises(OutOfRangeError) as raised:
                    await asyncio.wait_for(task, 2)
                assert await writer.publish_numeric_failure(claim, raised.value) == (
                    PublicationResult.FAILED_NUMERIC
                )
                g = await generation(migrator_engine, claim)
                assert g["dataset_revision"] is None and g["checkpoint_count"] == 1
                assert await visible(migrator_engine, "indicator_numeric_failures") == 1
                assert await visible(migrator_engine, "indicator_ready_checkpoints") == 0
                assert (await job(migrator_engine, claim))["retry_not_before"] is None
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


async def test_ready_atomic_visibility_rollback_and_replay(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        await scan_staging(builder_engine, writer, claim)
        before = await job(migrator_engine, claim)
        with pytest.raises(RuntimeError, match="rollback"):
            async with writer.transaction() as session:
                assert await publish(session, claim, numeric=False) == PublicationResult.READY
                assert await visible(api_engine, "indicator_ready_heads") == 0
                assert await visible(api_engine, "indicator_ready_checkpoints") == 0
                raise RuntimeError("rollback")
        assert (await slot(migrator_engine))["state"] == "RUNNING"
        assert (await generation(migrator_engine, claim))["status"] == "STAGING"
        assert await writer.publish_ready(claim) == PublicationResult.READY
        assert await visible(api_engine, "indicator_ready_heads") == 1
        assert await visible(api_engine, "indicator_ready_checkpoints") == 4
        after = await job(migrator_engine, claim)
        assert after["attempts_used"] == 0
        assert after["cycle_id"] != before["cycle_id"]
        for key in ("last_served_round", "first_eligible_at", "availability_deadline"):
            assert after[key] == before[key]
        with pytest.raises(IndicatorBuildOwnershipError):
            async with writer.transaction() as session:
                await publish(session, claim, numeric=False)
        assert (await slot(migrator_engine))["state"] == "IDLE"


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize(
    "fault",
    [
        "epoch",
        "floor",
        "relevant",
        "reset",
        "trigger",
        "deadline",
        "lease",
        "rollout",
        "outside",
        "other",
    ],
)
async def test_proof_and_ownership_publication(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    numeric: bool,
    fault: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        scanned = await scan_staging(builder_engine, writer, claim)
        before = await job(migrator_engine, claim)
        async with migrator_engine.begin() as c:
            if fault == "epoch":
                await c.execute(text("UPDATE indicator_source_guard SET epoch=gen_random_uuid()"))
            elif fault == "floor":
                await c.execute(
                    text(
                        "UPDATE indicator_source_guard SET revision=revision+1, "
                        "journal_floor=revision+1"
                    )
                )
            elif fault in ("relevant", "reset", "outside", "other"):
                # Privileged fault injection preserves the exact committed journal schema.
                await c.execute(text("UPDATE indicator_source_guard SET revision=revision+1"))
                await c.execute(
                    text("""INSERT INTO indicator_source_changes
                  (epoch,revision,source,base,quote,timeframe,open_at,kind)
                  SELECT epoch,revision,'primary_spot',:base,'USDT','4h',:opened,:kind
                  FROM indicator_source_guard WHERE id=1"""),
                    {
                        "base": "ETH" if fault == "other" else "BTC",
                        "opened": scanned.snapshot.calculation.end
                        if fault == "outside"
                        else scanned.snapshot.calculation.start,
                        "kind": "RESET" if fault == "reset" else "WRITE",
                    },
                )
            elif fault == "trigger":
                await c.execute(
                    text("UPDATE indicator_rollout_control SET source_proof_state='PENDING'")
                )
                await c.execute(
                    text("ALTER TABLE market_candles DISABLE TRIGGER indicator_source_rows")
                )
                await c.execute(
                    text("UPDATE indicator_rollout_control SET source_proof_state='READY'")
                )
            elif fault == "deadline":
                await c.execute(
                    text(
                        "UPDATE indicator_build_slot SET "
                        "attempt_deadline=clock_timestamp()-interval '1 second'"
                    )
                )
            elif fault == "lease":
                await c.execute(
                    text(
                        "UPDATE indicator_build_jobs SET "
                        "lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"
                    ),
                    {"id": claim.job_id},
                )
            else:
                await c.execute(
                    text("UPDATE indicator_rollout_control SET rollout_epoch=gen_random_uuid()")
                )
        try:
            result = (
                await writer.publish_numeric_failure(claim, OutOfRangeError("private"))
                if numeric
                else await writer.publish_ready(claim)
            )
            allowed = fault in ("outside", "other")
            assert (
                result == (PublicationResult.FAILED_NUMERIC if numeric else PublicationResult.READY)
                if allowed
                else result == PublicationResult.SUPERSEDED
            )
            after = await job(migrator_engine, claim)
            if not allowed:
                assert after["attempts_used"] == before["attempts_used"] == 1
                assert after["status"] == "QUEUED"
                assert after["retry_not_before"] is not None
                assert after["last_served_round"] == before["last_served_round"]
            assert (await slot(migrator_engine))["state"] == "IDLE"
        finally:
            if fault == "trigger":
                async with migrator_engine.begin() as c:
                    await c.execute(
                        text("UPDATE indicator_rollout_control SET source_proof_state='PENDING'")
                    )
                    await c.execute(
                        text("ALTER TABLE market_candles ENABLE TRIGGER indicator_source_rows")
                    )
                    await c.execute(
                        text("UPDATE indicator_rollout_control SET source_proof_state='READY'")
                    )


async def test_numeric_incomplete_no_digest_no_retry_and_sanitized_view(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        async with indicator_source_session(builder_engine) as source:
            snapshot = await capture_snapshot(source, claim)
            await initialize(writer, claim, snapshot)
        with pytest.raises(IndicatorBuildConfigurationError):
            await writer.publish_ready(claim)
        assert (
            await writer.publish_numeric_failure(claim, OutOfRangeError("private input"))
            == PublicationResult.FAILED_NUMERIC
        )
        g = await generation(migrator_engine, claim)
        assert g["dataset_revision"] is None
        assert g["checkpoint_count"] == 0
        assert await visible(api_engine, "indicator_numeric_failures") == 1
        assert await visible(api_engine, "indicator_ready_checkpoints") == 0
        assert await visible(api_engine, "indicator_ready_heads") == 0
        j = await job(migrator_engine, claim)
        assert j["attempts_used"] == 1 and j["retry_not_before"] is None
        assert j["failed_input_version"] == {
            "epoch": str(snapshot.fence.epoch),
            "fence": snapshot.fence.revision,
        }
        assert j["failed_calculation_key"]["start"] == snapshot.calculation.start.isoformat(
            timespec="microseconds"
        )
        assert "private" not in str(j)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        assert await writer.claim(uuid4()) is None


@pytest.mark.parametrize("damage", ["digest", "count", "checkpoint"])
async def test_ready_requires_complete_checkpoint_set(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    damage: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        await scan_staging(builder_engine, writer, claim)
        async with migrator_engine.begin() as c:
            sql = {
                "digest": "UPDATE indicator_generations SET dataset_revision=NULL WHERE id=:id",
                "count": "UPDATE indicator_generations SET checkpoint_count=3 WHERE id=:id",
                "checkpoint": """DELETE FROM indicator_checkpoints WHERE generation_id=:id
                  AND next_open_at=(SELECT min(next_open_at) FROM indicator_checkpoints
                  WHERE generation_id=:id)""",
            }[damage]
            await c.execute(text(sql), {"id": claim.generation_id})
        with pytest.raises(IndicatorBuildConfigurationError):
            await writer.publish_ready(claim)
        assert await visible(migrator_engine, "indicator_ready_heads") == 0
        await writer.finish(AttemptOutcome.OPERATIONAL)


async def test_publication_function_privileges(migrator_engine: AsyncEngine) -> None:
    args = "uuid,bigint,uuid,uuid,uuid,uuid"
    async with migrator_engine.connect() as c:
        for role in ("api", "engine", "engine_scan", "auth", "market_data", "indicator_builder"):
            for function in ("ready", "numeric_failure"):
                allowed: bool = (
                    await c.execute(
                        text("SELECT has_function_privilege(:role,:function,'EXECUTE')"),
                        {
                            "role": "tiewtrade_" + role,
                            "function": f"public.publish_indicator_{function}({args})",
                        },
                    )
                ).scalar_one()
                assert allowed is (role == "indicator_builder")
            assert not (
                await c.execute(
                    text("SELECT has_function_privilege(:role,:function,'EXECUTE')"),
                    {
                        "role": "tiewtrade_" + role,
                        "function": f"public.publish_indicator_generation({args},boolean)",
                    },
                )
            ).scalar_one()


async def test_numeric_preserves_old_head_and_atomic_failure_visibility(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        first = await writer.claim(uuid4())
        assert first is not None
        await scan_staging(builder_engine, writer, first)
        await writer.publish_ready(first)
    # Scheduling a subsequent candidate is a privileged fixture until coalescing is implemented.
    async with migrator_engine.begin() as c:
        await c.execute(
            text("UPDATE indicator_build_jobs SET status='QUEUED' WHERE id=:id"),
            {"id": first.job_id},
        )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        second = await writer.claim(uuid4())
        assert second is not None and second.candidate_sequence > first.candidate_sequence
        async with indicator_source_session(builder_engine) as source:
            snapshot = await capture_snapshot(source, second)
            await initialize(writer, second, snapshot)
        with pytest.raises(RuntimeError):
            async with writer.transaction() as session:
                await publish(session, second, numeric=True)
                assert await visible(api_engine, "indicator_numeric_failures") == 0
                raise RuntimeError("rollback")
        await writer.publish_numeric_failure(second, OutOfRangeError("private"))
        async with api_engine.connect() as c:
            assert (
                await c.execute(text("SELECT generation_id FROM indicator_ready_heads"))
            ).scalar_one() == first.generation_id
            row = (
                (await c.execute(text("SELECT * FROM indicator_numeric_failures"))).mappings().one()
            )
            assert row["id"] == second.generation_id
            assert row["candidate_sequence"] == second.candidate_sequence
            assert "payload" not in row and "dataset_revision" not in row


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("numeric", [False, True])
async def test_publication_waits_for_source_writer_commit_or_rollback(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    commit: bool,
    numeric: bool,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        scanned = await scan_staging(builder_engine, writer, claim)
        async with migrator_engine.connect() as source:
            transaction = await source.begin()
            await source.execute(text("SELECT begin_indicator_source_write()"))
            await source.execute(
                text("""INSERT INTO market_candles
              (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
               finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
              VALUES('primary_spot','BTC','USDT','4h',:opened,:ended,1,2,1,1,0,
                'UNCONFIRMED',clock_timestamp(),clock_timestamp(),clock_timestamp(),1)"""),
                {
                    "opened": scanned.snapshot.calculation.start,
                    "ended": scanned.snapshot.calculation.start + claim.timeframe.span,
                },
            )
            # The publication must not skip a writer holding the guard, or wait indefinitely.
            with pytest.raises(DatabaseTimeoutError):
                if numeric:
                    await writer.publish_numeric_failure(claim, OutOfRangeError("private"))
                else:
                    await writer.publish_ready(claim)
            assert (await slot(migrator_engine))["state"] == "RUNNING"
            if commit:
                await transaction.commit()
            else:
                await transaction.rollback()
        result = (
            await writer.publish_numeric_failure(claim, OutOfRangeError("private"))
            if numeric
            else await writer.publish_ready(claim)
        )
        assert result == (
            PublicationResult.SUPERSEDED
            if commit
            else PublicationResult.FAILED_NUMERIC
            if numeric
            else PublicationResult.READY
        )


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("field", ["epoch", "fence", "owner", "job", "generation", "token"])
async def test_raw_publication_rejects_every_stale_identity_field(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    numeric: bool,
    field: str,
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        await scan_staging(builder_engine, writer, claim)
        parameters = claim.parameters()
        parameters[field] = claim.fence + 1 if field == "fence" else uuid4()
        name = "numeric_failure" if numeric else "ready"
        with pytest.raises(IndicatorBuildOwnershipError):
            async with writer.transaction() as session:
                await session.execute(
                    f"SELECT public.publish_indicator_{name}"
                    "(:epoch,:fence,:owner,:job,:generation,:token)",
                    parameters,
                )
        assert (await generation(migrator_engine, claim))["status"] == "STAGING"
        await writer.finish(AttemptOutcome.OPERATIONAL)
