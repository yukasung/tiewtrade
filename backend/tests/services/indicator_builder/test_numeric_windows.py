"""R2-N1..N3: DB-clock boundaries and real core range errors from damaged source.

The isolated DB's high column is widened only for fault injection. Production's
money domain already rejects this corruption. No publisher/error/failed key is
mocked: the regular reader hits Money's range check and the worker publishes it.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.parity_reference import Slot, canonical_digest, reference_points, scan
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tiewtrade.core.indicators import IndicatorPoint, IndicatorStream
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleWindow,
    Timeframe,
    advance,
    expected_opens,
    next_open,
)
from tiewtrade.core.money import Money, OutOfRangeError, Quantity
from tiewtrade.core.money.limits import MAX_ABS
from tiewtrade.infra.db.session import indicator_read_session
from tiewtrade.infra.indicators.codec import decode_checkpoint
from tiewtrade.infra.indicators.scheduling import coalesce_jobs
from tiewtrade.infra.indicators.session import IndicatorSourceSession
from tiewtrade.infra.market_data.indicator_reader import read_indicators
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt

BOUNDARY = datetime(2026, 10, 1, tzinfo=UTC)
Clock = Callable[[datetime], Awaitable[None]]


@pytest_asyncio.fixture
async def db_clock(
    prepared: None,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Clock]:
    originals: list[str] = []
    async with migrator_engine.begin() as c:
        await c.execute(
            text("CREATE TABLE test_indicator_clock_state(moment timestamptz NOT NULL)")
        )
        await c.execute(
            text("INSERT INTO test_indicator_clock_state VALUES(:moment)"), {"moment": BOUNDARY}
        )
        await c.execute(
            text("""CREATE FUNCTION test_indicator_clock() RETURNS timestamptz
          LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT moment FROM public.test_indicator_clock_state $$""")
        )
        await c.execute(text("REVOKE ALL ON FUNCTION test_indicator_clock() FROM PUBLIC"))
        await c.execute(
            text("GRANT EXECUTE ON FUNCTION test_indicator_clock() TO tiewtrade_indicator_builder")
        )
        rows: Sequence[str] = (
            (
                await c.execute(
                    text("""SELECT pg_get_functiondef(p.oid) AS definition
          FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND p.proname LIKE '%indicator%'
            AND pg_get_functiondef(p.oid) LIKE '%clock_timestamp()%'""")
                )
            )
            .scalars()
            .all()
        )
        for definition in rows:
            originals.append(definition)
            await c.execute(
                text(definition.replace("clock_timestamp()", "public.test_indicator_clock()"))
            )
        await c.execute(text("SELECT begin_indicator_source_maintenance()"))
        await c.execute(text("ALTER TABLE market_candles ALTER COLUMN high TYPE numeric"))
    execute = IndicatorSourceSession.execute

    async def clocked_execute(
        session: IndicatorSourceSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        return await execute(
            session,
            statement.replace("clock_timestamp()", "public.test_indicator_clock()"),
            parameters,
        )

    monkeypatch.setattr(IndicatorSourceSession, "execute", clocked_execute)

    async def set_clock(moment: datetime) -> None:
        async with migrator_engine.begin() as c:
            await c.execute(
                text("UPDATE test_indicator_clock_state SET moment=:moment"), {"moment": moment}
            )

    try:
        yield set_clock
    finally:
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text("DELETE FROM market_candles"))
            await c.execute(
                text("ALTER TABLE market_candles ALTER COLUMN high TYPE tiewtrade_money_amount")
            )
            for definition in originals:
                await c.execute(text(definition))
            await c.execute(text("DROP FUNCTION test_indicator_clock()"))
            await c.execute(text("DROP TABLE test_indicator_clock_state"))


async def one_series(builder: AsyncEngine, admin: AsyncEngine, timeframe: Timeframe) -> None:
    await coalesce_jobs(builder)
    async with admin.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET status='FAILED_OPERATIONAL'
          WHERE NOT(base='BTC' AND timeframe=:tf)"""),
            {"tf": timeframe.value},
        )


async def job(admin: AsyncEngine, timeframe: Timeframe) -> dict[str, Any]:
    async with admin.connect() as c:
        return dict(
            (
                await c.execute(
                    text("""SELECT * FROM indicator_build_jobs
          WHERE base='BTC' AND timeframe=:tf"""),
                    {"tf": timeframe.value},
                )
            )
            .mappings()
            .one()
        )


async def insert_bad(admin: AsyncEngine, timeframe: Timeframe, opened: datetime) -> None:
    # Use the existing maintenance protocol even for test-only corrupted source.
    async with admin.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
           finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          VALUES('primary_spot','BTC','USDT',:tf,:opened,:end,1,CAST(:high AS numeric),1,1,0,
            'CLOSED',:opened,:end,:end,1)"""),
            {
                "tf": timeframe.value,
                "opened": opened,
                "end": next_open(opened, timeframe),
                "high": str(MAX_ABS),
            },
        )


async def full_scan_failure(api: AsyncEngine, admin: AsyncEngine, timeframe: Timeframe) -> None:
    current = await job(admin, timeframe)
    async with admin.connect() as c:
        generation = (
            (
                await c.execute(
                    text("SELECT * FROM indicator_generations WHERE id=:id"),
                    {"id": current["current_candidate"]},
                )
            )
            .mappings()
            .one()
        )
    window = CandleWindow(generation["calculation_start"], generation["calculation_end"])
    async with indicator_read_session(api, uuid4()) as session:
        with pytest.raises(OutOfRangeError):
            await read_indicators(
                session,
                "BTC",
                "USDT",
                timeframe,
                window,
                CandleWindow(advance(window.end, timeframe, -2), window.end),
                generation["as_of"],
                monotonic() + 30,
            )


@pytest.mark.parametrize("timeframe", list(Timeframe))
async def test_numeric_key_before_at_after_db_alignment_boundary(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    timeframe: Timeframe,
) -> None:
    before = BOUNDARY - timedelta(microseconds=1)
    await db_clock(before)
    await one_series(builder_engine, migrator_engine, timeframe)
    original = await job(migrator_engine, timeframe)
    await insert_bad(migrator_engine, timeframe, original["desired_start"])
    await insert_bad(migrator_engine, timeframe, next_open(original["desired_start"], timeframe))
    assert (
        await run_attempt(builder_engine, uuid4(), scheduled=True)
    ).status is AttemptStatus.FAILED_NUMERIC
    failed = await job(migrator_engine, timeframe)
    for moment in (before, BOUNDARY):
        await db_clock(moment)
        await asyncio.gather(coalesce_jobs(builder_engine), coalesce_jobs(builder_engine))
        current = await job(migrator_engine, timeframe)
        # At the boundary U changes, so exactly-at is a new key even though L is unchanged.
        if moment == before:
            assert current["status"] == "FAILED_NUMERIC"
            assert current["generation_sequence"] == failed["generation_sequence"]
        else:
            assert current["status"] == "QUEUED"
            assert (
                await run_attempt(builder_engine, uuid4(), scheduled=True)
            ).status is AttemptStatus.FAILED_NUMERIC
    await db_clock(BOUNDARY + timedelta(microseconds=1))
    await coalesce_jobs(builder_engine)
    current = await job(migrator_engine, timeframe)
    assert current["desired_start"] == next_open(failed["desired_start"], timeframe)
    assert current["desired_end"] == BOUNDARY
    assert current["status"] == "QUEUED"
    assert current["first_eligible_at"] == failed["first_eligible_at"]
    assert current["availability_deadline"] == failed["availability_deadline"]
    assert (
        await run_attempt(builder_engine, uuid4(), scheduled=True)
    ).status is AttemptStatus.FAILED_NUMERIC
    await coalesce_jobs(builder_engine)
    assert (await job(migrator_engine, timeframe))["status"] == "FAILED_NUMERIC"
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB


async def recover_numeric_window(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    retained_once: bool,
    observe: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[dict[str, Any], tuple[IndicatorPoint, ...]]:
    tf = Timeframe.H4
    await db_clock(BOUNDARY)
    await one_series(builder_engine, migrator_engine, tf)
    initial = await job(migrator_engine, tf)
    bad_open = initial["desired_start"] + (tf.span if retained_once else timedelta(0))
    await insert_bad(migrator_engine, tf, bad_open)
    healthy: dict[datetime, Candle] = {}
    if retained_once:
        opened = initial["desired_start"]
        price = Money.of(1, "USDT")
        healthy[opened] = Candle(
            "BTC",
            "USDT",
            tf,
            opened,
            opened + tf.span,
            price,
            price,
            price,
            price,
            Quantity.of(1, "BTC"),
            CandleFinality.CLOSED,
            opened,
        )
    for index in range(220):
        opened = BOUNDARY - (220 - index) * tf.span
        close = Money.of(str(100 + index % 17), "USDT")
        healthy[opened] = Candle(
            "BTC",
            "USDT",
            tf,
            opened,
            opened + tf.span,
            close,
            close + Money.of(1, "USDT"),
            close - Money.of(1, "USDT"),
            close,
            Quantity.of(1, "BTC"),
            CandleFinality.CLOSED,
            opened,
        )
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
           finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          VALUES('primary_spot','BTC','USDT','4h',:opened,:end,CAST(:close AS numeric),
            CAST(:high AS numeric),CAST(:low AS numeric),CAST(:close AS numeric),1,
            'CLOSED',:opened,:end,:end,1)"""),
            [
                {
                    "opened": b.open_at,
                    "end": b.end_at,
                    "close": b.close.as_parts()["amount"],
                    "high": b.high.as_parts()["amount"],
                    "low": b.low.as_parts()["amount"],
                }
                for b in healthy.values()
            ],
        )
    with pytest.raises(OutOfRangeError):
        Money.of(MAX_ABS, "USDT")
    assert (
        await run_attempt(builder_engine, uuid4(), scheduled=True)
    ).status is AttemptStatus.FAILED_NUMERIC
    failed = await job(migrator_engine, tf)
    async with migrator_engine.connect() as c:
        failed_manifest = dict(
            (
                await c.execute(
                    text("SELECT * FROM indicator_generations WHERE id=:id"),
                    {"id": failed["current_candidate"]},
                )
            )
            .mappings()
            .one()
        )
    if observe is not None:
        await observe("failed")
    # No failed-key mutation, source correction, publisher mock or restored failed state.
    if retained_once:
        await db_clock(BOUNDARY + timedelta(microseconds=1))
        await coalesce_jobs(builder_engine)
        assert (
            await run_attempt(builder_engine, uuid4(), scheduled=True)
        ).status is AttemptStatus.FAILED_NUMERIC
        if observe is not None:
            await observe("retained")
    recovered_at = (
        BOUNDARY + (tf.span if retained_once else timedelta(0)) + timedelta(microseconds=1)
    )
    await db_clock(recovered_at)
    await coalesce_jobs(builder_engine)
    pending = await job(migrator_engine, tf)
    assert pending["status"] == "QUEUED" and pending["desired_start"] > bad_open
    assert pending["availability_deadline"] == failed["availability_deadline"]
    if observe is not None:
        await observe("pending")
    result = await run_attempt(builder_engine, uuid4(), scheduled=True)
    assert result.status is AttemptStatus.READY
    if observe is not None:
        await observe("ready")
    async with migrator_engine.connect() as c:
        assert (
            dict(
                (
                    await c.execute(
                        text("SELECT * FROM indicator_generations WHERE id=:id"),
                        {"id": failed_manifest["id"]},
                    )
                )
                .mappings()
                .one()
            )
            == failed_manifest
        )
        g = (
            (
                await c.execute(
                    text("SELECT * FROM indicator_generations WHERE id=:id"),
                    {"id": result.generation_id},
                )
            )
            .mappings()
            .one()
        )
        cps = (
            (
                await c.execute(
                    text("""SELECT * FROM indicator_checkpoints
          WHERE generation_id=:id ORDER BY next_open_at"""),
                    {"id": result.generation_id},
                )
            )
            .mappings()
            .all()
        )
        bad_count: int = (
            await c.execute(
                text("SELECT count(*) FROM market_candles WHERE high>=CAST(:max AS numeric)"),
                {"max": str(MAX_ABS)},
            )
        ).scalar_one()
    assert bad_count == 1  # The old source is still damaged; only the calculation window changed.
    window = CandleWindow(g["calculation_start"], g["calculation_end"])
    slots: tuple[Slot, ...] = tuple(
        (moment, healthy.get(moment), healthy[moment].end_at if moment in healthy else None)
        for moment in expected_opens(window, tf)
    )
    oracle = reference_points(slots)
    full = IndicatorStream("BTC", "USDT", tf, g["as_of"])
    assert scan(full, slots, 16, 1000) == oracle
    assert g["dataset_revision"] == canonical_digest(slots, window, tf)
    for cp in cps:
        restored = decode_checkpoint(
            cp["payload"],
            generation_id=str(result.generation_id),
            source="primary_spot",
            base="BTC",
            quote="USDT",
            timeframe=tf,
            as_of=g["as_of"],
            calculation=window,
            next_open_at=cp["next_open_at"],
        )
        suffix = tuple(s for s in slots if s[0] >= cp["next_open_at"])
        assert scan(restored, suffix, 16, 1000) == tuple(
            p for p in oracle if p.open_at >= cp["next_open_at"]
        )
        assert restored.export_state() == full.export_state()
    return dict(g), oracle


@pytest.mark.parametrize("retained_once", [False, True])
async def test_real_numeric_failure_recovers_after_bad_bar_leaves_window_with_oracle(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    retained_once: bool,
) -> None:
    await recover_numeric_window(db_clock, builder_engine, migrator_engine, retained_once)


async def test_append_outside_failed_window_waits_for_db_clock_to_expand_u(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
) -> None:
    tf = Timeframe.H4
    await db_clock(BOUNDARY)
    await one_series(builder_engine, migrator_engine, tf)
    initial = await job(migrator_engine, tf)
    await insert_bad(migrator_engine, tf, initial["desired_start"] + 10 * tf.span)
    assert (
        await run_attempt(builder_engine, uuid4(), scheduled=True)
    ).status is AttemptStatus.FAILED_NUMERIC
    failed = await job(migrator_engine, tf)
    await full_scan_failure(api_engine, migrator_engine, tf)
    await insert_bad(migrator_engine, tf, failed["desired_end"])
    await coalesce_jobs(builder_engine)
    unchanged = await job(migrator_engine, tf)
    assert unchanged["status"] == "FAILED_NUMERIC"
    assert unchanged["failed_calculation_key"] == failed["failed_calculation_key"]
    assert unchanged["generation_sequence"] == failed["generation_sequence"]
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    await db_clock(BOUNDARY + tf.span)
    await coalesce_jobs(builder_engine)
    expanded = await job(migrator_engine, tf)
    assert expanded["desired_end"] == failed["desired_end"] + tf.span
    assert expanded["status"] == "QUEUED"
    assert expanded["availability_deadline"] == failed["availability_deadline"]
    assert (
        await run_attempt(builder_engine, uuid4(), scheduled=True)
    ).status is AttemptStatus.FAILED_NUMERIC
    new_failure = await job(migrator_engine, tf)
    await full_scan_failure(api_engine, migrator_engine, tf)
    assert new_failure["failed_calculation_key"] != failed["failed_calculation_key"]
    assert new_failure["generation_sequence"] == failed["generation_sequence"] + 1
    await coalesce_jobs(builder_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB


@pytest.mark.parametrize("damage", ["floor", "epoch"])
async def test_missing_proof_does_not_reset_numeric_input(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    damage: str,
) -> None:
    await db_clock(BOUNDARY)
    await one_series(builder_engine, migrator_engine, Timeframe.H4)
    initial = await job(migrator_engine, Timeframe.H4)
    await insert_bad(migrator_engine, Timeframe.H4, initial["desired_start"])
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.FAILED_NUMERIC
    failed = await job(migrator_engine, Timeframe.H4)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_source_guard SET revision=revision+1,journal_floor=revision+1"
                if damage == "floor"
                else "UPDATE indicator_source_guard SET epoch=gen_random_uuid()"
            )
        )
    await coalesce_jobs(builder_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    current = await job(migrator_engine, Timeframe.H4)
    assert current["status"] == "FAILED_NUMERIC"
    assert current["failed_calculation_key"] == failed["failed_calculation_key"]
    assert current["generation_sequence"] == failed["generation_sequence"]
