"""Approved F1 numeric failure boundary before/after the STAGING commit."""

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tiewtrade.core.money import OutOfRangeError
from tiewtrade.infra.indicators import scan
from tiewtrade.infra.indicators.claims import BuildClaim
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter
from tiewtrade.infra.indicators.session import IndicatorWriterSession
from tiewtrade.infra.indicators.staging import StagingSnapshot, initialize
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


def inject_numeric_boundary(monkeypatch: pytest.MonkeyPatch, committed: bool) -> None:
    execute = IndicatorWriterSession.execute
    injected = False

    async def fail(
        session: IndicatorWriterSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        nonlocal injected
        result = await execute(session, statement, parameters)
        if "SELECT public.initialize_indicator_staging(" in statement and not injected:
            injected = True
            # SQL executed but its transaction must roll back before recovery.
            raise OutOfRangeError("private-numeric-input")
        return result

    async def after_commit(*args: object) -> None:
        raise OutOfRangeError("private-numeric-input")

    if committed:
        # First checkpoint preparation is after the STAGING transaction committed.
        monkeypatch.setattr(scan, "append_checkpoint", after_commit)
    else:
        monkeypatch.setattr(IndicatorWriterSession, "execute", fail)


@pytest.mark.parametrize("committed", [False, True])
async def test_numeric_failure_before_and_after_staging_commit(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    committed: bool,
) -> None:
    await seed(builder_engine, migrator_engine)
    inject_numeric_boundary(monkeypatch, committed)
    result = await run_attempt(builder_engine, uuid4())
    current = await metadata(migrator_engine)
    assert "private-numeric-input" not in str(result) + str(current)
    assert result.status is AttemptStatus.FAILED_NUMERIC
    assert current["status"] == "FAILED_NUMERIC"
    assert current["retry_not_before"] is None
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    async with migrator_engine.connect() as c:
        row = (
            await c.execute(
                text("SELECT status,checkpoint_count,dataset_revision FROM indicator_generations")
            )
        ).one()
        assert tuple(row) == ("FAILED_NUMERIC", 0, None)


@pytest.mark.parametrize("fault", ["write", "rollback", "lease", "epoch"])
async def test_precommit_numeric_preserves_snapshot_and_rejects_stale_proof(
    prepared: None,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    captured: list[StagingSnapshot] = []

    async def boundary(
        writer: PinnedIndicatorWriter, claim: BuildClaim, snapshot: StagingSnapshot
    ) -> None:
        captured.append(snapshot)
        if len(captured) == 1:
            raise OutOfRangeError("private-input")
        assert len(captured) == 2 and captured[0] is snapshot
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE "
                        "usename='tiewtrade_indicator_builder' AND state='idle in transaction'"
                    )
                )
            ).scalar_one() == 0
            await c.rollback()
            transaction = await c.begin()
            if fault in ("write", "rollback"):
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(
                    text("""INSERT INTO market_candles
                  (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
                   finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                  VALUES('primary_spot','BTC','USDT','4h',:lo,:hi,1,1,1,1,0,
                    'CLOSED',:lo,:hi,:hi,1)"""),
                    {
                        "lo": snapshot.calculation.start,
                        "hi": snapshot.calculation.start + claim.timeframe.span,
                    },
                )
            elif fault == "epoch":
                await c.execute(text("UPDATE indicator_source_guard SET epoch=gen_random_uuid()"))
            else:
                await c.execute(
                    text(
                        "UPDATE indicator_build_jobs SET "
                        "lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"
                    ),
                    {"id": claim.job_id},
                )
            if fault == "rollback":
                await transaction.rollback()
            else:
                await transaction.commit()
        await initialize(writer, claim, snapshot)

    monkeypatch.setattr(scan, "initialize", boundary)
    result = await run_attempt(builder_engine, uuid4())
    assert len(captured) == 2
    if fault == "rollback":
        assert result.status is AttemptStatus.FAILED_NUMERIC
    else:
        assert result.status in (AttemptStatus.SUPERSEDED, AttemptStatus.RELEASED)
    current = await metadata(migrator_engine)
    assert current["attempts_used"] == 1
    async with migrator_engine.connect() as c:
        count: int = (
            await c.execute(text("SELECT count(*) FROM indicator_numeric_failures"))
        ).scalar_one()
        assert count == (1 if fault == "rollback" else 0)
