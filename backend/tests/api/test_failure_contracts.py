"""F1/F3/F6 numeric classification, proof scope and sanitized HTTP responses."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import register
from tests.api.test_prepared_indicators import admission_state as admission_state
from tests.api.test_prepared_indicators import first
from tests.api.test_prepared_indicators import ready as ready
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata
from tests.services.indicator_builder.test_failure_contracts import inject_numeric_boundary
from tests.services.indicator_builder.test_scheduler import numeric
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


async def queue(admin: AsyncEngine) -> None:
    async with admin.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_build_jobs SET status='QUEUED' "
                "WHERE base='BTC' AND timeframe='4h'"
            )
        )


@pytest.mark.parametrize("committed", [False, True])
async def test_numeric_boundary_http_never_recomputes_or_falls_back(
    ready: dict[str, Any],
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    committed: bool,
) -> None:
    register(client)
    response = first(client)
    assert response.status_code == 200
    token = response.json()["next_cursor"]
    await queue(migrator_engine)
    inject_numeric_boundary(monkeypatch, committed)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.FAILED_NUMERIC
    before = await metadata(migrator_engine)

    def no_compute(*args: object, **kwargs: object) -> None:
        raise AssertionError("numeric GET recomputed input")

    with monkeypatch.context() as guard:
        guard.setattr(IndicatorStream, "feed_batch", no_compute)
        for _ in range(2):
            response = first(client)
            assert response.status_code == 422
            assert response.json() == {"detail": "INDICATOR_NUMERIC_ERROR"}
            assert "retry-after" not in response.headers
            assert "private-numeric-input" not in response.text + caplog.text
            assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.NO_JOB
    assert await metadata(migrator_engine) == before
    # Same source, different candidate: the already valid READY cursor stays valid.
    assert client.get("/market-data/indicators", params={"cursor": token}).status_code == 200


@pytest.mark.parametrize("fault", ["epoch", "floor", "bounds", "expiry", "codec", "gc"])
async def test_failed_manifest_proof_is_required_for_numeric_http(
    ready: dict[str, Any],
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
    fault: str,
) -> None:
    register(client)
    response = first(client)
    assert response.status_code == 200
    token = response.json()["next_cursor"]
    await queue(migrator_engine)
    await numeric(builder_engine)
    assert first(client).status_code == 422
    async with migrator_engine.begin() as c:
        statement = {
            "epoch": "UPDATE indicator_source_guard SET epoch=gen_random_uuid()",
            "floor": "UPDATE indicator_source_guard SET "
            "revision=revision+1,journal_floor=revision+1",
            "bounds": "UPDATE indicator_build_jobs SET desired_start=desired_start+interval '4h'",
            "expiry": "UPDATE indicator_generations SET as_of=as_of-interval '7h',"
            "expires_at=expires_at-interval '7h',calculation_start=calculation_start-interval '7h',"
            "calculation_end=calculation_end-interval '7h' WHERE status='FAILED_NUMERIC'",
            "codec": "UPDATE indicator_generations SET codec_version=2 "
            "WHERE status='FAILED_NUMERIC'",
            "gc": "UPDATE indicator_generations SET status='EXPIRED' WHERE status='FAILED_NUMERIC'",
        }[fault]
        await c.execute(text(statement))
    response = first(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "INDICATOR_DATA_NOT_READY"}
    assert client.get("/market-data/indicators", params={"cursor": token}).status_code == (
        409 if fault in ("epoch", "floor") else 200
    )


async def test_newer_ready_head_is_not_masked_by_older_failure_candidate(
    ready: dict[str, Any],
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    client: TestClient,
) -> None:
    register(client)
    await queue(migrator_engine)
    await numeric(builder_engine)
    failed = await metadata(migrator_engine)
    # A relevant source correction permits a fresh candidate after numeric failure.
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("UPDATE market_candles SET volume=volume+1 WHERE base='BTC' AND timeframe='4h'")
        )
    await queue(migrator_engine)
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    healthy = first(client)
    assert healthy.status_code == 200
    # Fault fixture leaves an older failure view alongside the genuinely newer head.
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_build_jobs SET current_candidate=:candidate,"
                "failed_calculation_key=CAST(:key AS jsonb) WHERE id=:id"
            ),
            {"candidate": failed["current_candidate"], "id": failed["id"], "key": "{}"},
        )
    response = first(client)
    assert response.status_code == 200
    assert response.json()["generation_id"] == healthy.json()["generation_id"]
    assert response.json()["rows"] == healthy.json()["rows"]


async def test_codec_payload_error_is_503_without_private_payload_in_response(
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    register(client)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_checkpoints SET "
                "payload=jsonb_build_object('private-payload-marker','private-value')"
            )
        )
    response = first(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "INDICATOR_DATA_NOT_READY"}
    assert "private-payload-marker" not in response.text + caplog.text
    assert "private-value" not in response.text + caplog.text
