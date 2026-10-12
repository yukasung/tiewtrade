"""N1..N3 HTTP contracts against real worker failures and a controlled DB clock."""

from collections.abc import AsyncIterator, Mapping
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import register
from tests.api.test_prepared_indicators import admission_state as admission_state
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_numeric_windows import (
    BOUNDARY,
    Clock,
    full_scan_failure,
    insert_bad,
    job,
    one_series,
    recover_numeric_window,
)
from tests.services.indicator_builder.test_numeric_windows import db_clock as db_clock
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money, Scalar
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.claims import AttemptOutcome
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.scheduling import coalesce_jobs
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


@pytest_asyncio.fixture
async def http_clock(
    db_clock: Clock, migrator_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Clock]:
    async with migrator_engine.begin() as c:
        await c.execute(text("GRANT EXECUTE ON FUNCTION test_indicator_clock() TO tiewtrade_api"))
        await c.execute(text("UPDATE indicator_rollout_control SET mode='PREPARED'"))
    execute = UserSession.execute

    async def clocked_execute(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        return await execute(
            session,
            statement.replace("clock_timestamp()", "public.test_indicator_clock()"),
            parameters,
        )

    monkeypatch.setattr(UserSession, "execute", clocked_execute)
    yield db_clock


@pytest.mark.parametrize("retained_once", [False, True])
async def test_numeric_window_http_recovery_matches_independent_oracle(
    http_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
    api_engine: AsyncEngine,
    retained_once: bool,
) -> None:
    register(client)
    responses: dict[str, Any] = {}

    async def observe(stage: str) -> None:
        before = await job(migrator_engine, Timeframe.H4)
        response = client.get(
            "/market-data/indicators",
            params={
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "4h",
                "page_size": 2,
                "start": (BOUNDARY - 4 * Timeframe.H4.span).isoformat(),
                "end": BOUNDARY.isoformat(),
            },
        )
        expected = {"failed": 422, "retained": 422, "pending": 503, "ready": 200}[stage]
        assert response.status_code == expected
        if expected == 422:
            assert response.json() == {"detail": "INDICATOR_NUMERIC_ERROR"}
            assert "retry-after" not in response.headers
            await full_scan_failure(api_engine, migrator_engine, Timeframe.H4)
        elif expected == 503:
            assert response.json() == {"detail": "INDICATOR_DATA_NOT_READY"}
        responses[stage] = response.json()
        assert await job(migrator_engine, Timeframe.H4) == before  # GET cannot retry/build.

    generation, oracle = await recover_numeric_window(
        http_clock, builder_engine, migrator_engine, retained_once, observe
    )
    body = responses["ready"]
    assert body["generation_id"] == str(generation["id"])
    assert body["dataset_revision"] == generation["dataset_revision"]
    points = [p for p in oracle if BOUNDARY - 4 * Timeframe.H4.span <= p.open_at < BOUNDARY][:2]
    assert len(points) == len(body["rows"]) == 2
    for actual, expected in zip(body["rows"], points, strict=True):
        assert actual["open_at"] == expected.open_at.isoformat().replace("+00:00", "Z")
        assert expected.seed_open_at is not None
        assert actual["seed_open_at"] == expected.seed_open_at.isoformat().replace("+00:00", "Z")
        assert actual["finality"] == expected.finality
        for name, value in expected.values.items():
            assert value.value is not None and value.status.value == "READY"
            assert actual["values"][name] == {
                "value": value.value.as_text()
                if isinstance(value.value, Scalar)
                else value.value.as_parts()["amount"],
                "unit": value.value.currency if isinstance(value.value, Money) else None,
                "status": value.status.value,
            }


@pytest.mark.parametrize("timeframe", list(Timeframe))
async def test_same_numeric_key_survives_restart_fence_metadata_and_gc(
    http_clock: Clock,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
    timeframe: Timeframe,
) -> None:
    await http_clock(BOUNDARY - timedelta(microseconds=2))
    await one_series(builder_engine, migrator_engine, timeframe)
    initial = await job(migrator_engine, timeframe)
    await insert_bad(migrator_engine, timeframe, initial["desired_start"])
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.FAILED_NUMERIC
    failed = await job(migrator_engine, timeframe)
    register(client)
    params = {"base": "BTC", "quote": "USDT", "timeframe": timeframe.value, "page_size": 2}
    for _ in range(2):
        response = client.get("/market-data/indicators", params=params)
        assert response.status_code == 422
        assert response.json() == {"detail": "INDICATOR_NUMERIC_ERROR"}
        assert "retry-after" not in response.headers
    # Another series legitimately consumes a fence, without touching the failed input.
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET status='QUEUED'
          WHERE base='ETH' AND timeframe='4h'""")
        )
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("UPDATE market_candles SET last_checked_at=last_checked_at+interval '1 second'")
        )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        claim = await writer.claim(uuid4())
        assert claim is not None and claim.base == "ETH"
        await writer.finish(AttemptOutcome.OPERATIONAL)
    await builder_engine.dispose()  # New connection/owner, no in-memory suppression state.
    await http_clock(BOUNDARY - timedelta(microseconds=1))
    await coalesce_jobs(builder_engine)
    current = await job(migrator_engine, timeframe)
    for key in (
        "failed_calculation_key",
        "generation_sequence",
        "cycle_id",
        "attempts_used",
        "first_eligible_at",
        "availability_deadline",
        "last_served_round",
    ):
        assert current[key] == failed[key]
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    assert client.get("/market-data/indicators", params=params).status_code == 422
    async with migrator_engine.begin() as c:
        await c.execute(
            text("UPDATE indicator_build_jobs SET current_candidate=NULL WHERE id=:id"),
            {"id": failed["id"]},
        )
        await c.execute(
            text("DELETE FROM indicator_generations WHERE job_id=:id"), {"id": failed["id"]}
        )
    await builder_engine.dispose()
    await coalesce_jobs(builder_engine)
    after_gc = await job(migrator_engine, timeframe)
    assert after_gc["failed_calculation_key"] == failed["failed_calculation_key"]
    assert after_gc["generation_sequence"] == failed["generation_sequence"]
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    assert client.get("/market-data/indicators", params=params).status_code == 503
