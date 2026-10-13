"""Finite R2-7 fixture correctness check, separate from deferred load acceptance."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_numeric_windows import BOUNDARY, Clock, one_series
from tests.services.indicator_builder.test_numeric_windows import db_clock as db_clock
from tiewtrade.core.market_data import Timeframe
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


async def test_exact_dense_fixture_and_independent_digest(
    db_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await db_clock(BOUNDARY)
    await one_series(builder_engine, migrator_engine, Timeframe.M1)
    start, end = BOUNDARY - timedelta(days=365), BOUNDARY
    async with migrator_engine.begin() as connection:
        await connection.execute(text("SELECT begin_indicator_source_write()"))
        await connection.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
           observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          SELECT 'primary_spot','BTC','USDT','1m',moment,moment+interval '1 minute',
            100,101,99,100,1,'CLOSED',:observed,:observed,:observed,1
          FROM generate_series(CAST(:start AS timestamptz),
            CAST(:end AS timestamptz)-interval '1 minute',interval '1 minute') t(moment)"""),
            {"start": start, "end": end, "observed": BOUNDARY},
        )
        count: int = (
            await connection.execute(text("SELECT count(*) FROM market_candles"))
        ).scalar_one()
    assert count == 525600
    result = await run_attempt(builder_engine, uuid4())
    assert result.status is AttemptStatus.READY, result
    async with migrator_engine.connect() as connection:
        generation = (
            (await connection.execute(text("SELECT * FROM indicator_generations"))).mappings().one()
        )
        checkpoints: int = (
            await connection.execute(text("SELECT count(*) FROM indicator_checkpoints"))
        ).scalar_one()
    assert generation["calculation_start"] == start
    assert generation["calculation_end"] == end
    assert checkpoints == 527
    # Independent canonical serialization of the known SQL fixture; no production
    # digest/core helpers and no 525,600-row Python collection.
    digest = hashlib.sha256()

    def feed(record: list[Any]) -> None:
        digest.update(json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode() + b"\n")

    def stamp(moment: datetime) -> str:
        return moment.isoformat(timespec="microseconds")

    feed([1, "primary_spot", "BTC", "USDT", "1m", "indicators-v2", stamp(start), stamp(end)])
    for index in range(525600):
        opened = start + timedelta(minutes=index)
        feed(
            [
                stamp(opened),
                stamp(opened + timedelta(minutes=1)),
                "100",
                "101",
                "99",
                "100",
                "1",
                "CLOSED",
                stamp(BOUNDARY),
                stamp(BOUNDARY),
            ]
        )
    assert generation["dataset_revision"] == digest.hexdigest()
    evidence = {
        "source_rows": count,
        "logical_slots": 525600,
        "checkpoints": checkpoints,
        "start": stamp(start),
        "end": stamp(end),
        "digest": digest.hexdigest(),
        "status": "READY",
        "capacity_acceptance": "deferred to phase 9",
    }
    destination = Path(
        "../specs/features/2026-10-10-backend-indicators/profiling/exact-fixture.json"
    )
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
