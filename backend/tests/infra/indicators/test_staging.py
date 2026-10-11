"""Actual-role STAGING protocol, snapshot parity and aborted scan isolation."""

import asyncio
from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.parity_reference import (
    Slot,
    canonical_digest,
    parity_slots,
    reference_points,
    scan,
)
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.market_data import (
    CandleWindow,
    Timeframe,
    align_floor,
    expected_opens,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import (
    IndicatorBuildConfigurationError,
    IndicatorBuildOwnershipError,
    InfraError,
)
from tiewtrade.infra.indicators import pinned as pinned_module
from tiewtrade.infra.indicators import scan as scanner
from tiewtrade.infra.indicators.claims import AttemptOutcome, BuildClaim
from tiewtrade.infra.indicators.claims import heartbeat as claim_heartbeat
from tiewtrade.infra.indicators.codec import decode_checkpoint
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.scan import scan_staging
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.indicators.staging import append_checkpoint, capture_snapshot, initialize, seal
from tiewtrade.infra.market_data.indicator_reader import fetch_rows


async def only_h4(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("""UPDATE indicator_build_jobs SET status='FAILED_OPERATIONAL'
            WHERE NOT(base='BTC' AND timeframe='4h')""")
        )


async def generation(engine: AsyncEngine, claim: BuildClaim) -> dict[str, Any]:
    async with engine.connect() as connection:
        return dict(
            (
                await connection.execute(
                    text("SELECT * FROM indicator_generations WHERE id=:id"),
                    {"id": claim.generation_id},
                )
            )
            .mappings()
            .one()
        )


@pytest.mark.parametrize("warm_count", [1, 14, 199])
async def test_staging_scan_db_digest_and_restored_parity(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine, warm_count: int
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        async with migrator_engine.begin() as c:
            now: Any = (await c.execute(text("SELECT clock_timestamp()"))).scalar_one()
            hi = align_floor(now, Timeframe.H4)
            start = hi - 1220 * Timeframe.H4.span
            fixture = parity_slots(start, warm_count, [i % 17 for i in range(1300)])
            transformed: list[Slot] = []
            for index, (_, bar, fetched) in enumerate(fixture):
                moment = start + index * Timeframe.H4.span
                new_bar = (
                    replace(
                        bar,
                        timeframe=Timeframe.H4,
                        open_at=moment,
                        end_at=moment + Timeframe.H4.span,
                        observed_at=moment,
                    )
                    if bar
                    else None
                )
                new_fetch = (
                    (
                        new_bar.end_at
                        if fetched is not None and bar is not None and fetched >= bar.end_at
                        else moment
                    )
                    if new_bar
                    else None
                )
                transformed.append((moment, new_bar, new_fetch))
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            values = [
                {
                    "opened": m,
                    "end": b.end_at,
                    "o": b.open.as_parts()["amount"],
                    "h": b.high.as_parts()["amount"],
                    "l": b.low.as_parts()["amount"],
                    "close": b.close.as_parts()["amount"],
                    "v": b.volume.as_parts()["quantity"],
                    "finality": b.finality.value,
                    "observed": b.observed_at,
                    "fetched": f,
                }
                for m, b, f in transformed
                if b is not None
            ]
            await c.execute(
                text("""INSERT INTO market_candles(source,base,quote,timeframe,
                open_at,end_at,open,high,low,close,volume,finality,observed_at,fetch_started_at,
                last_checked_at,ingestion_generation) VALUES('primary_spot','BTC','USDT','4h',
                :opened,:end,CAST(:o AS numeric),CAST(:h AS numeric),CAST(:l AS numeric),
                CAST(:close AS numeric),CAST(:v AS numeric),:finality,
                :observed,:fetched,:end,1)"""),
                values,
            )
        claim = await writer.claim(uuid4())
        assert claim is not None
        result = await scan_staging(builder_engine, writer, claim)
        window = result.snapshot.calculation
        all_slots = tuple(
            (m, None, None) for m in expected_opens(CandleWindow(window.start, start), Timeframe.H4)
        ) + tuple(transformed)
        assert result.digest == canonical_digest(all_slots, window, Timeframe.H4)
        full = IndicatorStream("BTC", "USDT", Timeframe.H4, result.snapshot.as_of)
        assert scan(full, all_slots, 16, 1000) == reference_points(all_slots)
        g = await generation(migrator_engine, claim)
        assert g["status"] == "STAGING" and g["dataset_revision"] == result.digest
        assert g["checkpoint_count"] == result.checkpoint_count == 4
        async with migrator_engine.connect() as c:
            rows = (
                (
                    await c.execute(
                        text(
                            "SELECT * FROM indicator_checkpoints WHERE generation_id=:id "
                            "ORDER BY next_open_at"
                        ),
                        {"id": claim.generation_id},
                    )
                )
                .mappings()
                .all()
            )
            visible: Any = (
                await c.execute(text("SELECT count(*) FROM indicator_ready_checkpoints"))
            ).scalar_one()
            assert visible == 0
        for row in rows:
            restored = decode_checkpoint(
                row["payload"],
                generation_id=str(claim.generation_id),
                source=claim.source,
                base=claim.base,
                quote=claim.quote,
                timeframe=claim.timeframe,
                as_of=result.snapshot.as_of,
                calculation=window,
                next_open_at=row["next_open_at"],
            )
            remaining = tuple(slot for slot in all_slots if slot[0] >= row["next_open_at"])
            points = scan(restored, remaining, 16, 1000)
            assert points == tuple(
                p for p in reference_points(all_slots) if p.open_at >= row["next_open_at"]
            )
            assert restored.export_state() == full.export_state()
        await writer.finish(AttemptOutcome.SOURCE_CHANGED)


@pytest.mark.parametrize("failure", ["cancel", "connection", "deadline"])
async def test_aborted_scan_closes_source_and_keeps_unpublished_staging(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    reached = asyncio.Event()
    original = append_checkpoint

    async def paused(*args: Any, **kwargs: Any) -> None:
        await original(*args, **kwargs)
        reached.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(scanner, "append_checkpoint", paused)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        task = asyncio.create_task(scan_staging(builder_engine, writer, claim))
        await asyncio.wait_for(reached.wait(), 5)
        if failure == "connection":
            # Independent test fault injector, outside the worker's two-connection pool.
            killer = create_engine_for(DatabaseRole.INDICATOR_BUILDER)
            try:
                async with killer.begin() as c:
                    await c.execute(
                        text("SELECT pg_terminate_backend(:pid)"), {"pid": claim.backend_pid}
                    )
            finally:
                await killer.dispose()
        elif failure == "deadline":
            async with migrator_engine.begin() as c:
                await c.execute(
                    text(
                        "UPDATE indicator_build_slot SET "
                        "attempt_deadline=clock_timestamp()-interval '1s'"
                    )
                )
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert task.done()
        g = await generation(migrator_engine, claim)
        assert (
            g["status"] == "STAGING"
            and g["dataset_revision"] is None
            and g["checkpoint_count"] == 1
        )
        # The freed second pool slot can open a fresh source (the old source was joined).
        async with indicator_source_session(builder_engine) as source:
            await source.execute("SELECT 1")
        if failure == "connection":
            with pytest.raises(InfraError):
                await writer.heartbeat()
        else:
            await writer.finish(AttemptOutcome.OWNERSHIP_LOST)


async def test_checkpoint_order_seal_and_stale_identity_fail_closed(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine
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
            stream = IndicatorStream(claim.base, claim.quote, claim.timeframe, snapshot.as_of)
            with pytest.raises(IndicatorBuildConfigurationError):
                await seal(writer, claim, "a" * 64)
            await append_checkpoint(writer, claim, snapshot, stream, snapshot.calculation.start)
            with pytest.raises(IndicatorBuildConfigurationError):
                await append_checkpoint(writer, claim, snapshot, stream, snapshot.calculation.start)
            with pytest.raises(IndicatorBuildOwnershipError):
                await initialize(writer, replace(claim, token=uuid4()), snapshot)
            assert (await generation(migrator_engine, claim))["checkpoint_count"] == 1
            async with migrator_engine.begin() as c:
                await c.execute(
                    text(
                        "UPDATE indicator_build_slot SET "
                        "attempt_deadline=clock_timestamp()-interval '1s'"
                    )
                )
            with pytest.raises(IndicatorBuildOwnershipError):
                await append_checkpoint(writer, claim, snapshot, stream, snapshot.calculation.start)
        await writer.finish(AttemptOutcome.OWNERSHIP_LOST)


async def test_snapshot_ignores_committed_write_after_capture(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_fetch = fetch_rows
    changed = False

    async def insert_after_snapshot(*args: Any, **kwargs: Any) -> Any:
        nonlocal changed
        if not changed:
            changed = True
            async with migrator_engine.begin() as c:
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(
                    text("""INSERT INTO market_candles(source,base,quote,timeframe,
                    open_at,end_at,open,high,low,close,volume,finality,observed_at,
                    fetch_started_at,last_checked_at,ingestion_generation)
                    SELECT 'primary_spot','BTC','USDT','4h',calculation_start,
                    calculation_start+interval '4 hours',1,1,1,1,0,'CLOSED',as_of,as_of,as_of,1
                    FROM indicator_generations WHERE status='STAGING'""")
                )
        return await original_fetch(*args, **kwargs)

    monkeypatch.setattr(scanner, "fetch_rows", insert_after_snapshot)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        result = await scan_staging(builder_engine, writer, claim)
        empty: tuple[Slot, ...] = tuple(
            (m, None, None) for m in expected_opens(result.snapshot.calculation, Timeframe.H4)
        )
        assert result.digest == canonical_digest(empty, result.snapshot.calculation, Timeframe.H4)
        async with migrator_engine.connect() as c:
            revision: Any = (
                await c.execute(text("SELECT revision FROM indicator_source_guard"))
            ).scalar_one()
            assert revision > result.snapshot.fence.revision
        # Publication must reject this journal change in the next implementation stage.
        await writer.finish(AttemptOutcome.SOURCE_CHANGED)


async def test_heartbeat_failure_stops_scan_and_disallows_resume(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scanner, "HEARTBEAT_SECONDS", 0.01)
    original_fetch = fetch_rows

    async def expire(*args: Any, **kwargs: Any) -> Any:
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE indicator_build_slot SET "
                    "attempt_deadline=clock_timestamp()-interval '1s'"
                )
            )
        await asyncio.sleep(0.05)
        return await original_fetch(*args, **kwargs)

    monkeypatch.setattr(scanner, "fetch_rows", expire)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        with pytest.raises(IndicatorBuildOwnershipError):
            await scan_staging(builder_engine, writer, claim)
        with pytest.raises(IndicatorBuildOwnershipError):
            await writer.heartbeat()
        assert (await generation(migrator_engine, claim))["dataset_revision"] is None
        async with indicator_source_session(builder_engine) as source:
            await source.execute("SELECT 1")
        await writer.finish(AttemptOutcome.OWNERSHIP_LOST)


async def test_full_m1_scan_is_bounded_and_has_at_most_527_checkpoints(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        claim = await writer.claim(uuid4())
        assert claim is not None and claim.timeframe == Timeframe.M1
        result = await scan_staging(builder_engine, writer, claim)
        assert result.checkpoint_count == 527
        g = await generation(migrator_engine, claim)
        assert g["checkpoint_count"] == 527 and g["status"] == "STAGING"
        await writer.finish(AttemptOutcome.OPERATIONAL)


@pytest.mark.parametrize("field", ["epoch", "fence", "owner", "job", "generation", "token"])
async def test_sql_staging_functions_reject_spoofed_identity(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine, field: str
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
            bad = claim.parameters()
            bad[field] = claim.fence + 1 if field == "fence" else uuid4()
            with pytest.raises(IndicatorBuildOwnershipError):
                async with writer.transaction() as session:
                    await session.execute(
                        "SELECT public.seal_indicator_staging("
                        ":epoch,:fence,:owner,:job,:generation,:token,:digest)",
                        bad | {"digest": "a" * 64},
                    )
            assert (await generation(migrator_engine, claim))["dataset_revision"] is None
        await writer.finish(AttemptOutcome.OPERATIONAL)


@pytest.mark.parametrize("late_failure", [False, True])
async def test_success_waits_for_inflight_heartbeat_before_returning(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    late_failure: bool,
) -> None:
    trigger = asyncio.Event()
    entered = asyncio.Event()
    allow_finish = asyncio.Event()
    original_heartbeat = claim_heartbeat
    original_seal = seal

    async def held_heartbeat(*args: Any) -> Any:
        if trigger.is_set():
            entered.set()
            await allow_finish.wait()
            if late_failure:
                raise IndicatorBuildOwnershipError("injected heartbeat failure")
        return await original_heartbeat(*args)

    async def hold_after_seal(*args: Any) -> None:
        await original_seal(*args)
        trigger.set()
        await asyncio.wait_for(entered.wait(), 2)

    monkeypatch.setattr(scanner, "HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr(pinned_module, "heartbeat", held_heartbeat)
    monkeypatch.setattr(scanner, "seal", hold_after_seal)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        claim = await writer.claim(uuid4())
        assert claim is not None
        task = asyncio.create_task(scan_staging(builder_engine, writer, claim))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            await asyncio.sleep(0.02)
            assert not task.done()
            allow_finish.set()
            if late_failure:
                with pytest.raises(IndicatorBuildOwnershipError):
                    await asyncio.wait_for(task, 2)
            else:
                await asyncio.wait_for(task, 2)
                writer.require_claim(claim)
                await writer.heartbeat()
        finally:
            allow_finish.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await writer.finish(AttemptOutcome.OPERATIONAL)


async def test_dense_scan_releases_previous_rows_before_next_fetch(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import weakref

    class TrackedRow(dict[str, Any]):
        pass

    refs: list[weakref.ReferenceType[TrackedRow]] = []
    peaks: list[int] = []
    original_fetch = fetch_rows

    async def track_rows(*args: Any, **kwargs: Any) -> Any:
        assert not any(ref() is not None for ref in refs), "previous batch retained"
        result = tuple(TrackedRow(row) for row in await original_fetch(*args, **kwargs))
        refs.extend(weakref.ref(row) for row in result)
        peaks.append(sum(ref() is not None for ref in refs))
        return result

    monkeypatch.setattr(scanner, "fetch_rows", track_rows)
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
        await only_h4(migrator_engine)
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_write()"))
            await c.execute(
                text("""INSERT INTO market_candles(source,base,quote,timeframe,
                open_at,end_at,open,high,low,close,volume,finality,observed_at,
                fetch_started_at,last_checked_at,ingestion_generation)
                SELECT 'primary_spot','BTC','USDT','4h',opened,opened+interval '4h',
                1,2,1,1,1,'CLOSED',now(),now(),now(),1
                FROM indicator_build_jobs j CROSS JOIN LATERAL generate_series(
                j.desired_start,j.desired_end-interval '4h',interval '4h') opened
                WHERE j.base='BTC' AND j.timeframe='4h'""")
            )
        claim = await writer.claim(uuid4())
        assert claim is not None
        await scan_staging(builder_engine, writer, claim)
        assert peaks[:2] == [1000, 1000] and max(peaks) == 1000
        assert not any(ref() is not None for ref in refs)
        await writer.finish(AttemptOutcome.OPERATIONAL)


@pytest.mark.parametrize("exit_mode", ["commit", "rollback", "cancel"])
async def test_source_cleanup_timeout_aborts_physical_connection(
    builder_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, exit_mode: str
) -> None:
    from time import monotonic

    from sqlalchemy.ext.asyncio import AsyncConnection

    from tiewtrade.infra.db.errors import DatabaseTimeoutError

    entered = asyncio.Event()
    joined = asyncio.Event()
    target: AsyncConnection | None = None
    method = "commit" if exit_mode == "commit" else "rollback"
    original = getattr(AsyncConnection, method)

    async def stall(connection: AsyncConnection) -> None:
        if connection is target:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                joined.set()
        else:
            await original(connection)

    monkeypatch.setattr(AsyncConnection, method, stall)
    driver: Any = None
    started = monotonic()
    expected_error = asyncio.CancelledError if exit_mode == "cancel" else DatabaseTimeoutError
    with pytest.raises(expected_error):
        async with indicator_source_session(builder_engine) as source:
            target = source._connection
            driver = (await target.get_raw_connection()).driver_connection
            if exit_mode == "rollback":
                raise ValueError("scan aborted")
            if exit_mode == "cancel":
                raise asyncio.CancelledError()
    assert entered.is_set() and joined.is_set()
    assert monotonic() - started < 2.5
    assert driver.is_closed()
    async with indicator_source_session(builder_engine) as fresh:
        await fresh.execute("SELECT 1")
